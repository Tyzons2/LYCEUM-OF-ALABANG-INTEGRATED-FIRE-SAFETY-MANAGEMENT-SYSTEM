"""Exercise local request handlers against an isolated database without opening a port."""
import tempfile, os, io, json, base64
from pathlib import Path
import unittest
from unittest.mock import patch
import server

class Workflow(unittest.TestCase):
    def setUp(self):
        self.db=server.DATA / ("qa-"+os.urandom(8).hex()+".sqlite3")
        self.addCleanup(self.db.unlink, missing_ok=True)
        
        with server.connect() as original:
            import sqlite3
            with sqlite3.connect(self.db) as dest:
                # Copy schema only so test runs never depend on real accounts.
                for row in original.execute("select sql from sqlite_master where type='table' and name not like 'sqlite_%'"):
                    dest.execute(row[0])
            dest.close()
        self.patch=patch.object(server,"DB",self.db);self.patch.start();self.addCleanup(self.patch.stop)
        self.cookie=""
    def call(self,path,data=None,ok=True):
        h=object.__new__(server.Handler);h.path=path
        raw=json.dumps(data).encode();h.rfile=io.BytesIO(raw)
        h.headers={"Cookie":self.cookie,"X-Local-App":"fire-safety","Content-Length":str(len(raw))}
        def output(body,kind="application/json",status=200,headers=None):
            self.assertEqual(status==200,ok,str(body)[:300])
            if headers and "Set-Cookie" in headers:self.cookie=headers["Set-Cookie"].split(";")[0]
            return body
        h.output=output
        return h.handle_app_request(data is not None)
    def test_lifecycle(self):
        c=self.call
        c("/list",ok=False)
        c("/login",dict(email="admin@example.test",name="Test",password="test-password-123"))
        fe={"FE #":"FE-10","LOCATION":"Test location","TYPE OF FE":"CO2","WEIGHT":"5 kg"}
        asset=c("/save",dict(module="fe",data=fe))["id"]
        c("/save",dict(module="fe",data=fe),ok=False)
        fe2={**fe,"FE #":"FE-2"}
        sheet=server.workbook(server.HEAD,[[r.get(k,"") for k in server.HEAD] for r in [fe,fe2]])
        preview=c("/preview",dict(module="fe",file=base64.b64encode(sheet).decode()))
        self.assertTrue(preview["rows"][0]["error"])
        self.assertEqual(c("/import",dict(module="fe",batch=preview["batch"]))["count"],1)
        self.assertEqual(c("/list?module=fe")[0]["data"]["FE #"],"FE-2")
        image=io.BytesIO();server.Image.new("RGB",(2,2)).save(image,"PNG")
        photo=dict(bytes=base64.b64encode(image.getvalue()).decode(),name="test.png",category="Gauge")
        data={**dict.fromkeys(server.HEAD[6:14],"Good"),"PRESSURE GAUGE":"Low Pressure","FE #":"FE-10","Inspection Date":"2026-01-02","Inspector":"Tester","Inspection Result":"Defective"}
        rid=c("/save",dict(module="inspections",data=data,files=[photo]))["id"]
        self.assertEqual(c("/file?id="+str(c("/files?id="+str(rid))[0]["id"])),image.getvalue())
        c("/review",dict(module="inspections",id=rid,revision=1,decision="Verified",reason="Evidence reviewed"))
        self.assertEqual(c("/list?module=fe")[1]["data"]["Equipment Status"],"Defective")
        self.assertEqual(len(c("/list?module=capa")),1)
        c("/fsmr",dict(year=2026))
        self.assertEqual(len(c("/list?module=fsmr")[0]["data"]["Sections"]["inspections"]),1)
        c("/archive",dict(module="inspections",id=rid,revision=2,reason="Test archive"))
        self.assertEqual(len(c("/list?module=inspections&archived=1")),1)
        self.assertEqual(c("/list?module=fe")[1]["data"]["Equipment Status"],"For Verification")
        self.assertTrue(c("/export?module=fe").startswith(b"PK"))
        self.assertGreater(len(c("/audit")),5)
        c("/users",dict(name="Reader",role=server.ROLES[-1],email="read@example.test",password="test-password-123"))
        c("/logout",{});c("/login",dict(email="read@example.test",password="test-password-123"))
        c("/save",dict(module="fe",data=fe),ok=False)
        c("/users",ok=False)

if __name__=="__main__":unittest.main()


