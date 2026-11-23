"""Paginated A4 text reports using PDF's standard Western European fonts."""
from textwrap import wrap

def pdf_report(title, reference, author, sections):
    def literal(s):
        return str(s).encode("cp1252","replace").replace(b"\\",b"\\\\").replace(b"(",b"\\(").replace(b")",b"\\)").replace(b"\r",b" ").replace(b"\n",b" ")
    pages=[[]]
    def add(line,heading=False):
        for part in wrap(str(line),84) or [""]:
            if len(pages[-1])>=42:pages.append([])
            pages[-1].append((part,heading))
    for name,items in sections:
        add(name,True)
        if not items:add("No verified records for this section.")
        for row in items:
            add(row["ref"],True)
            for field,value in row["data"].items():
                if value:add(f"{field}: {value}")
        add("")
    objects=[b"",b"",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    ids=[]
    for num,lines in enumerate(pages,1):
        pid=len(objects)+1;ids.append(pid)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {pid+1} 0 R >>".encode())
        stream=bytearray(b"0.08 0.27 0.19 rg\n")
        def line(y,s,size=10,bold=False):
            stream.extend(f"BT /F{2 if bold else 1} {size} Tf 48 {y} Td (".encode()+literal(s)+b") Tj ET\n")
        line(799,"LYCEUM OF ALABANG  /  INSTITUTIONAL EHS&S OFFICE",11,True)
        line(765,title,17,True);line(741,reference+"  |  Prepared by "+author)
        for i,(s,b) in enumerate(lines):line(708-i*15,s,10,b)
        line(38,f"Page {num} of {len(pages)}")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode()+stream+b"endstream")
    objects[0]=b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1]=("<< /Type /Pages /Count "+str(len(ids))+" /Kids ["+" ".join(f"{i} 0 R" for i in ids)+"] >>").encode()
    out=bytearray(b"%PDF-1.4\n");offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out));out.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
    xref=len(out);out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(out)

