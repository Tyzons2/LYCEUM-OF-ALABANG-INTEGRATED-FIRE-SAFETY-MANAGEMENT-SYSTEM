"""Local Fire Safety Management System. Run with Python 3.12."""
import base64, hashlib, hmac, io, json, os, re, secrets, sqlite3, time
from datetime import date, datetime, timedelta
from copy import copy
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from PIL import Image
from catalog import *
from reports import pdf_report

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get("LOA_FIRE_DATA", str(Path.home()/"LOA-Fire-Safety-Data")))
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/"fire.sqlite3"
def connect():
    db=sqlite3.connect(DB,timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("pragma foreign_keys=on")
    return db
with connect() as db:
    db.executescript("""
    create table if not exists users(id integer primary key,email text unique collate nocase,name text,role text,password text);
    create table if not exists sessions(token text primary key,user integer references users,expires real);
    create table if not exists records(id integer primary key,module text,ref text unique,asset integer references records,ident text collate nocase,data text,review text,archived integer default 0,revision integer default 1,created text,unique(module,ident));
    create table if not exists files(id integer primary key,record integer references records,name text,type text,category text,author text,created text,bytes blob);
    create table if not exists audit(id integer primary key,stamp text,user text,module text,action text,ref text,old text,new text);
    create table if not exists batches(id text primary key,owner integer,rows text);
    """)
def now():return datetime.now().isoformat(timespec="seconds")
def natural(v):return [int(t) if i%2 else t.casefold() for i,t in enumerate(re.split(r"(\d+)",v))]
def check(ok,msg):
    if not ok:raise ValueError(msg)
def password(value,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+":"+hashlib.pbkdf2_hmac("sha256",value.encode(),salt.encode(),420000).hex()
def event(db,u,m,a,r="",old="",new=""):
    db.execute("insert into audit(stamp,user,module,action,ref,old,new) values(?,?,?,?,?,?,?)",(now(),u,m,a,r,old,new))
def create(db,m,d,asset=None,review="Pending Verification"):
    ident=d.get("FE #") if m=="fe" else d.get("Equipment ID") if m=="equipment" else None
    n=db.execute("insert into records(module,asset,ident,data,review,created) values(?,?,?,?,?,?)",(m,asset,ident,json.dumps(d),review,now())).lastrowid
    ref=f"LOA-{PREFIX.get(m,m.upper())}-"+("" if m=="fe" else f"{date.today().year}-")+f"{n:04d}"
    db.execute("update records set ref=? where id=?",(ref,n))
    return n,ref
def records(db,m,archived=False):
    rows=[]
    for r in db.execute("select id,ref,data,review,revision,archived,created,asset from records where module=? and archived=?",(m,int(archived))):
        obj=dict(r); obj["data"]=json.loads(r["data"])
        if m=="fe":
            latest=db.execute("select data from records where asset=? and module='inspections' and review='Verified' and archived=0 order by json_extract(data,'$.\u0022Inspection Date\u0022') desc,id desc limit 1",(r["id"],)).fetchone()
            obj["data"]["Equipment Status"]=json.loads(latest[0])["Inspection Result"] if latest else "For Verification"
        rows.append(obj)
    return sorted(rows,key=lambda r:natural(r["data"].get("FE #") or r["ref"]))
def validate(m,d):
    for k in REQUIRED.get(m,[FIELDS[m][0]]):check(d.get(k),"Required field: "+k)
    for k,v in d.items():
        choices=STATUS[m].split("|") if k=="Status" and m in STATUS else CHOICES.get(k)
        if v and choices and not (m=="fe" and k in HEAD):check(v in choices,"Invalid "+k)
        if v and ("Date" in k or "DATE" in k):date.fromisoformat(v)
def workbook(headers,rows):
    book=Workbook(); ws=book.active;ws.title="Records";ws.append(headers)
    for row in rows:
        ws.append(row)
        for cell in ws[ws.max_row]:
            if cell.data_type=="f":cell.data_type="s"
    for c in ws[1]:
        c.font=Font(bold=True,color="FFFFFF");c.fill=PatternFill("solid",fgColor="164D3C")
        ws.column_dimensions[c.column_letter].width=max(19,len(c.value)+4)
    ws.freeze_panes="C2";ws.auto_filter.ref=ws.dimensions;ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation="landscape";ws.page_setup.fitToWidth=1
    out=io.BytesIO();book.save(out);return out.getvalue()
REFILL_DAYS={"+365":365,"+365*3+1":1096}
def registry_export(rows):
    book=load_workbook(ROOT/"registry-layout.xlsx");ws=book["Template"]
    styles=[copy(c._style) for c in ws[2]]
    for index,record in enumerate(rows,2):
        d=record["data"]
        for col,key in enumerate(HEAD,1):
            value=d.get(key) or None
            if value and key in HEAD[4:6]:value=date.fromisoformat(value)
            cell=ws.cell(index,col);cell.value=value;cell._style=copy(styles[col-1])
            if cell.data_type=="f":cell.data_type="s"
        if d.get("_refill_formula") and d.get(HEAD[4]):
            ws.cell(index,6).value=f"=E{index}"+d["_refill_formula"]
        if d.get("_merged_note") and not d.get(HEAD[13]):
            ws.cell(index,14).value=d.get("REMARKS") or None
            if ws.cell(index,14).data_type=="f":ws.cell(index,14).data_type="s"
            ws.merge_cells(start_row=index,start_column=14,end_row=index,end_column=15)
    out=io.BytesIO();book.save(out);return out.getvalue()
class Handler(BaseHTTPRequestHandler):
    def output(self,data,kind="application/json",status=200,headers=None):
        if kind=="application/json":data=json.dumps(data).encode()
        self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)
    def handle_app_request(self,post=False):
        path=urlsplit(self.path);q={k:v[0] for k,v in parse_qs(path.query).items()}
        endpoint=path.path
        if not post and endpoint in ["/","/app.js","/style.css"]:
            file={"/":"index.html","/app.js":"app.js","/style.css":"style.css"}[endpoint]
            try:
                content = (ROOT / file).read_bytes()
            except OSError as exc:
                self.log_error("Cannot read %s: %s", ROOT / file, exc)
                return self.output(
                    f"Unable to read {file}. See the server terminal for details.".encode(),
                    "text/plain; charset=utf-8",
                    500,
                )
            return self.output(content, {"index.html":"text/html; charset=utf-8","app.js":"text/javascript","style.css":"text/css"}[file])
        db=connect()
        try:
            with db:
                body={}
                if post:
                    check(self.headers.get("X-Local-App")=="fire-safety","Invalid request")
                    length=int(self.headers.get("Content-Length",0));check(0<length<=60_000_000,"Invalid request size")
                    body=json.loads(self.rfile.read(length));db.execute("begin immediate")
                cookie=SimpleCookie(self.headers.get("Cookie",""));token=cookie["loa_fire"].value if "loa_fire" in cookie else ""
                user=db.execute("select u.* from users u join sessions s on s.user=u.id where s.token=? and s.expires>?",(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
                setup=not db.execute("select 1 from users limit 1").fetchone()
                if endpoint=="/session":return self.output(dict(setup=setup,user=dict(name=user["name"],role=user["role"]) if user else None))
                if endpoint=="/login" and post:
                    if setup:self.add_user(db,body,ROLES[0])
                    u=db.execute("select * from users where email=?",(body["email"].strip(),)).fetchone()
                    check(u and hmac.compare_digest(password(body["password"],u["password"].split(":")[0]),u["password"]),"Invalid email or password")
                    token=secrets.token_urlsafe(32);db.execute("insert into sessions values(?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),u["id"],time.time()+28800))
                    event(db,u["email"],"users","Sign in");db.commit()
                    return self.output({},headers={"Set-Cookie":f"loa_fire={token}; HttpOnly; SameSite=Strict; Path=/"})
                if not user:return self.output({"error":"Sign in required"} ,status=401)
                role=user["role"];who=user["email"];admin=role==ROLES[0];reviewer=admin or role==ROLES[4]
                if endpoint=="/logout" and post:
                    db.execute("delete from sessions where token=?",(hashlib.sha256(token.encode()).hexdigest(),));db.commit()
                    return self.output({},headers={"Set-Cookie":"loa_fire=; Max-Age=0; Path=/"})
                m=body.get("module",q.get("module","fe"))
                if endpoint=="/config":
                    return self.output(dict(names=NAMES,fields=FIELDS,choices=CHOICES,status=STATUS,required=REQUIRED,roles=ROLES,write=writable(role),admin=admin,reviewer=reviewer))
                if endpoint=="/users":
                    check(admin,"Administrator required")
                    if post:self.add_user(db,body,body["role"]);event(db,who,"users","Create account",body["email"]);db.commit()
                    return self.output([dict(x) for x in db.execute("select name,email,role from users")])
                if endpoint=="/audit":
                    check(admin or role in (ROLES[4],ROLES[9]),"Audit access required")
                    return self.output([dict(x) for x in db.execute("select * from audit order by id desc")])
                check(m in FIELDS or m=="fsmr","Unknown module")
                if endpoint=="/list":
                    archive=q.get("archived")=="1";check(not archive or admin or role==ROLES[9],"Archive access required")
                    return self.output(records(db,m,archive))
                if endpoint=="/files":
                    return self.output([dict(x) for x in db.execute("select id,name,type,category,created,author from files where record=?",(q["id"],))])
                if endpoint=="/file":
                    f=db.execute("select * from files where id=?",(q["id"],)).fetchone();check(f,"Unknown attachment")
                    return self.output(f["bytes"],f["type"],headers={"Content-Disposition":"inline"})
                if endpoint=="/pdf":
                    ref="LOA report "+date.today().isoformat()
                    if m=="fsmr":
                        item=db.execute("select ref,data from records where id=? and module='fsmr'",(q["id"],)).fetchone()
                        check(item,"Report unavailable")
                        snapshot=json.loads(item["data"]);ref=item["ref"]+" / "+snapshot["Reporting Year"]+" / Draft"
                        sections=[(NAMES[key],items) for key,items in snapshot["Sections"].items()]
                        author=snapshot["Prepared By"]
                    else:
                        search=q.get("q","").casefold()
                        sections=[(NAMES[m],[r for r in records(db,m) if search in json.dumps(r,ensure_ascii=False).casefold()])]
                        author=who
                    result=pdf_report(NAMES[m] if m!="fsmr" else "Annual Fire Safety Maintenance Report",ref,author,sections)
                    event(db,who,m,"PDF export",ref);db.commit()
                    return self.output(result,"application/pdf",headers={"Content-Disposition":f'attachment; filename="LOA-{m}.pdf"'})
                if endpoint=="/export":
                    rows=records(db,m);query=q.get("q","").lower();rows=[r for r in rows if query in json.dumps(r,ensure_ascii=False).lower()]
                    cols=FIELDS[m];out=registry_export(rows) if m=="fe" else workbook(cols,[[r["data"].get(k,"") for k in cols] for r in rows]);event(db,who,m,"Excel export");db.commit()
                    return self.output(out,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="LOA-{m}.xlsx"'})
                check(post,"POST required")
                if endpoint=="/fsmr":
                    check(reviewer,"Reviewer required");year=int(body["year"]);check(1900<=year<=2100,"Invalid year")
                    sections={}
                    for key in FIELDS:
                        if key=="settings":continue
                        sections[key]=[]
                        for row in records(db,key)+records(db,key,True):
                            d=row["data"]; stamp=next((d.get(f) for f in ("Inspection Date","Training Date","Drill Date","Incident Date","Completion Date","Verification Date","Issue Date","Activation Date","Review Date") if d.get(f)),row["created"])
                            if row["review"]=="Verified" and stamp.startswith(str(year)):sections[key].append({"ref":row["ref"],"data":d})
                    n,ref=create(db,"fsmr",{"Reporting Year":str(year),"Prepared By":who,"Sections":sections},"" or None,"Draft")
                    event(db,who,"fsmr","Generate report",ref);db.commit();return self.output({"id":n})
                check(m in writable(role),"You do not have write access")
                if endpoint in ("/preview","/import"):
                    check(m=="fe","Registry required")
                    if endpoint=="/preview":
                        raw=base64.b64decode(body["file"],validate=True);check(len(raw)<=5_242_880,"Workbook too large")
                        import zipfile
                        with zipfile.ZipFile(io.BytesIO(raw)) as z:check(sum(f.file_size for f in z.infolist())<32_000_000,"Workbook expands beyond limit")
                        book=load_workbook(io.BytesIO(raw),data_only=False);sheet=book["Template"] if "Template" in book.sheetnames else book.active
                        merged={r.min_row for r in sheet.merged_cells.ranges if r.min_col==14 and r.max_col==15 and r.min_row==r.max_row}
                        it=iter(sheet.values);check(list(next(it,()))==HEAD,"Expected exact 15-column template")
                        result=[];seen=set()
                        for i,values in enumerate(it,2):
                            check(i<=10002,"Maximum 10,000 rows");d={k:(v.date().isoformat() if isinstance(v,datetime) else str(v).strip() if v is not None else "") for k,v in zip(HEAD,values)}
                            if not any(d.values()):continue
                            error=""
                            try:
                                if i in merged:
                                    d["REMARKS"]=d[HEAD[13]];d[HEAD[13]]="";d["_merged_note"]=True
                                suffix=d[HEAD[5]].removeprefix(f"=E{i}")
                                if d[HEAD[5]].startswith(f"=E{i}") and suffix in REFILL_DAYS:
                                    d[HEAD[5]]=(date.fromisoformat(d[HEAD[4]])+timedelta(days=REFILL_DAYS[suffix])).isoformat()
                                    d["_refill_formula"]=suffix
                                validate("fe",d);key=d["FE #"].casefold();check(key not in seen and not db.execute("select 1 from records where module='fe' and ident=?",(d["FE #"],)).fetchone(),"Duplicate FE #");seen.add(key)
                            except ValueError as e:error=str(e)
                            result.append(dict(row=i,data=d,error=error))
                        batch=secrets.token_hex(12);db.execute("insert into batches values(?,?,?)",(batch,user["id"],json.dumps(result)));db.commit();return self.output(dict(batch=batch,rows=result))
                    batch=db.execute("select rows from batches where owner=? and id=?",(user["id"],body["batch"])).fetchone();check(batch,"Preview expired")
                    count=0
                    for row in json.loads(batch[0]):
                        if not row["error"]:
                            _,ref=create(db,"fe",row["data"]);event(db,who,m,"Import equipment",ref);count+=1
                    db.execute("delete from batches where id=?",(body["batch"],));event(db,who,m,"Confirm import",body["batch"],"",str(count));db.commit();return self.output(dict(count=count))
                rid=body.get("id");old=db.execute("select * from records where id=? and module=?",(rid,m)).fetchone() if rid else None
                if rid:
                    check(old and not old["archived"],"Record unavailable");check(old["revision"]==body.get("revision"),"Record changed. Reload before editing.")
                    if role==ROLES[6]:check(json.loads(old["data"]).get("Assigned To","").lower()==who.lower(),"Assigned personnel only")
                if endpoint=="/archive":
                    check(admin and old and body.get("reason","").strip(),"Administrator and archive reason required")
                    db.execute("update records set archived=1,revision=revision+1 where id=?",(rid,));event(db,who,m,"Archive",old["ref"],old["data"],body["reason"])
                elif endpoint=="/review":
                    check(reviewer and old,"Reviewer required");decision=body["decision"];check(decision in ("Verified","Returned for Correction","Rejected"),"Invalid decision")
                    check(body.get("reason","").strip(),"Enter review remarks")
                    if m=="inspections" and decision=="Verified":check(db.execute("select 1 from files where record=?",(rid,)).fetchone(),"Photo evidence required")
                    db.execute("update records set review=?,revision=revision+1 where id=?",(decision,rid));event(db,who,m,decision,old["ref"],old["review"],body["reason"])
                elif endpoint=="/save":
                    d={k:str(body["data"].get(k,"")).strip() for k in FIELDS[m]};validate(m,d)
                    asset=None
                    if role==ROLES[6]:check(d.get("Assigned To","").lower()==who.lower(),"Use your assigned account email")
                    if m in ("maintenance","inspections","capa") and d.get("FE #"):
                        a=db.execute("select id,data,archived from records where module='fe' and ident=?",(d["FE #"],)).fetchone();check(a and (not a["archived"] or old and old["asset"]==a["id"]),"Select an active FE number");asset=a["id"]
                        if m=="inspections":
                            master=json.loads(a["data"]);d.update({k:master.get(k,"") for k in HEAD[:4]})
                    if m=="fe" and old:
                        check(d["FE #"]==old["ident"],"FE number is fixed to preserve history")
                        previous=json.loads(old["data"])
                        if previous.get("_merged_note"):d["_merged_note"]=True
                        suffix=previous.get("_refill_formula")
                        if suffix in REFILL_DAYS and d[HEAD[4]] and d[HEAD[5]]==(date.fromisoformat(d[HEAD[4]])+timedelta(days=REFILL_DAYS[suffix])).isoformat():d["_refill_formula"]=suffix
                    if d.get("Status") in ("Completed","Closed","Verified Compliant"):
                        check(reviewer and (d.get("Resolution") or d.get("Service Findings") or d.get("Remarks")),"Authorized reviewer and resolution notes required")
                    if old:
                        db.execute("update records set data=?,asset=?,ident=?,revision=revision+1,review='Pending Verification' where id=?",(json.dumps(d),asset,d.get("FE #") if m=="fe" else d.get("Equipment ID") if m=="equipment" else None,rid));ref=old["ref"]
                    else:rid,ref=create(db,m,d,asset)
                    event(db,who,m,"Edit" if old else "Create",ref,old["data"] if old else "",json.dumps(d))
                    uploads=body.get("files",[])
                    if m=="inspections":check(len(uploads)+db.execute("select count(*) from files where record=?",(rid,)).fetchone()[0]<=8,"Maximum eight photos")
                    for upload in uploads:
                        raw=base64.b64decode(upload["bytes"],validate=True);check(0<len(raw)<=5242880,"Maximum 5 MB per attachment")
                        if raw.startswith(b"%PDF-") and m not in ("fe","inspections"):typ="application/pdf"
                        else:
                            im=Image.open(io.BytesIO(raw));typ=Image.MIME.get(im.format);check(typ in ("image/jpeg","image/png","image/webp"),"Unsupported image");im.verify()
                        db.execute("insert into files(record,name,type,category,author,created,bytes) values(?,?,?,?,?,?,?)",(rid,upload["name"],typ,upload["category"],who,now(),raw));event(db,who,m,"Attach evidence",ref,"",upload["name"])
                    if m=="inspections" and (d["Inspection Result"] in RESULT[1:5] or any(d[k] in COND[1:5]+["Low Pressure","High Pressure","Damaged Gauge"] for k in HEAD[6:14])):
                        exists=db.execute("select 1 from records where module='capa' and json_extract(data,'$.\u0022Inspection Reference\u0022')=?",(ref,)).fetchone()
                        if not exists:
                            _,c=create(db,"capa",{"Deficiency":d["REMARKS"] or d["Inspection Result"],"Inspection Reference":ref,"FE #":d["FE #"],"LOCATION":d["LOCATION"],"Recommended Action":d["Corrective Action"],"Status":"Open"},asset);event(db,who,"capa","Create from inspection",c)
                else:raise ValueError("Unknown action")
                db.commit();return self.output({"id":rid})
        except sqlite3.IntegrityError:return self.output({"error":"Duplicate identifier or conflicting record. No changes saved."},status=409)
        except Exception as exc:return self.output({"error":str(exc) or "Unable to process request"},status=400)
        finally:db.close()
    def add_user(self,db,b,role):
        check(role in ROLES and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",b["email"].strip()) and b["name"].strip() and len(b["password"])>=12,"Enter name, valid email and at least 12 password characters")
        db.execute("insert into users(email,name,role,password) values(?,?,?,?)",(b["email"].strip(),b["name"].strip(),role,password(b["password"])))
    def do_GET(self):self.handle_app_request()
    def do_POST(self):self.handle_app_request(True)
if __name__=="__main__":
    import sys
    import webbrowser
    port=int(os.getenv("LOA_FIRE_PORT","8765"))
    address=f"http://127.0.0.1:{port}/"
    with ThreadingHTTPServer(("127.0.0.1",port),Handler) as http:
        print(f"Fire Safety Management System: {address}",flush=True)
        if "--open-browser" in sys.argv:
            webbrowser.open(address)
        http.serve_forever()


