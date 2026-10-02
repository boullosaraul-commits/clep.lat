#!/usr/bin/env python3
"""Programa publicaciones CLEP con imagen obligatoria en Facebook.

Las tarjetas SVG se rasterizan localmente en GitHub Actions antes del envío.
No publica texto solo.
"""
import csv, json, mimetypes, os, subprocess, sys, urllib.parse, urllib.request, uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
COLA=ROOT/"data/editorial/cola.csv"
CFG=ROOT/"data/editorial/programacion.json"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def png_for(row):
    raw=(row.get("media_path") or "").strip()
    if not raw: raise ValueError("media_path vacío")
    src=(ROOT/raw).resolve()
    if ROOT.resolve() not in src.parents: raise ValueError("media_path fuera del repositorio")
    if not src.is_file(): raise ValueError(f"imagen inexistente: {raw}")
    if src.suffix.lower()==".png": return src
    if src.suffix.lower()!=".svg": raise ValueError("formato visual no soportado")
    out=src.with_suffix(".png")
    subprocess.run(["rsvg-convert","-w","1200","-h","1500","-o",str(out),str(src)],check=True)
    if not out.is_file() or out.stat().st_size==0: raise ValueError("falló rasterización PNG")
    return out

def multipart(fields, file_field, path):
    boundary="----CLEP"+uuid.uuid4().hex
    chunks=[]
    for k,v in fields.items():
        chunks += [f"--{boundary}\r\n".encode(),
                   f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode(),
                   str(v).encode("utf-8"),b"\r\n"]
    ctype=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks += [f"--{boundary}\r\n".encode(),
               f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'.encode(),
               f"Content-Type: {ctype}\r\n\r\n".encode(),path.read_bytes(),b"\r\n",
               f"--{boundary}--\r\n".encode()]
    return boundary,b"".join(chunks)

def graph_photo(page_id,token,message,when,path):
    url=f"https://graph.facebook.com/{API}/{page_id}/photos"
    fields={"message":message,"published":"false",
            "scheduled_publish_time":str(int(when.timestamp())),
            "access_token":token}
    boundary,body=multipart(fields,"source",path)
    req=urllib.request.Request(url,data=body,method="POST",
        headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.loads(r.read().decode())

def main():
    token=os.getenv("CLEP_FB_TOKEN"); page=os.getenv("CLEP_FB_PAGE_ID")
    if not token or not page: sys.exit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    cfg=json.loads(CFG.read_text(encoding="utf-8")); tz=ZoneInfo(cfg["timezone"])
    with COLA.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    changed=False
    for r in rows:
        if r.get("estado_editorial")!="PROGRAMADO" or r.get("post_nuevo_id"): continue
        fecha=(r.get("fecha_programada") or "").strip()
        orden=(r.get("orden_dia") or "").strip()
        message=(r.get("ficha_es") or "").strip()
        if not fecha or not orden or not message: continue
        try: when=datetime.fromisoformat(f"{fecha}T{orden}").replace(tzinfo=tz)
        except ValueError:
            print(f"SKIP {r.get('editorial_id')}: fecha/hora inválida",file=sys.stderr); continue
        if when<=datetime.now(tz):
            print(f"SKIP {r.get('editorial_id')}: horario ya pasó",file=sys.stderr); continue
        try:
            image=png_for(r)
            result=graph_photo(page,token,message,when,image)
        except Exception as e:
            print(f"ERROR {r.get('editorial_id')}: {e}",file=sys.stderr); continue
        post_id=str(result.get("post_id") or result.get("id") or "")
        if not post_id:
            print(f"ERROR {r.get('editorial_id')}: Meta no devolvió ID",file=sys.stderr); continue
        r["post_nuevo_id"]=post_id
        r["notas"]=((r.get("notas") or "")+" | imagen rasterizada y programada en Meta").strip(" |")
        changed=True
        print(f"OK {r.get('editorial_id')} -> {post_id} @ {when.isoformat()}")
    if changed:
        with COLA.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

if __name__=="__main__": main()
