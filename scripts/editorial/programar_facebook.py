#!/usr/bin/env python3
"""Programa posts CLEP en Facebook con texto + imagen obligatorios.

Transacción Meta:
1) sube la imagen como foto no publicada;
2) crea un Page feed post programado adjuntando esa foto;
3) guarda el ID del feed post (no el ID de la foto).

Así el cierre histórico verifica/elimina el objeto correcto.
"""
import csv,json,mimetypes,os,subprocess,sys,urllib.parse,urllib.request,uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
COLA=ROOT/"data/editorial/cola.csv"
CFG=ROOT/"data/editorial/programacion.json"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def media_file(row):
    raw=(row.get("media_path") or "").strip()
    if not raw:raise ValueError("media_path vacío")
    src=(ROOT/raw).resolve()
    if ROOT.resolve() not in src.parents:raise ValueError("media_path fuera del repositorio")
    if not src.is_file():raise ValueError(f"imagen inexistente: {raw}")
    ext=src.suffix.lower()
    if ext==".svg":
        out=src.with_suffix(".png")
        subprocess.run(["rsvg-convert","-w","1200","-h","1500","-o",str(out),str(src)],check=True)
        if not out.is_file() or out.stat().st_size==0:raise ValueError("falló rasterización PNG")
        return out
    if ext in {".png",".jpg",".jpeg",".webp"}:return src
    raise ValueError(f"formato visual no soportado: {ext}")

def multipart(fields,file_field,path):
    boundary="----CLEP"+uuid.uuid4().hex;chunks=[]
    for k,v in fields.items():
        chunks += [f"--{boundary}\r\n".encode(),f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode(),
                   str(v).encode("utf-8"),b"\r\n"]
    ctype=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks += [f"--{boundary}\r\n".encode(),
               f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'.encode(),
               f"Content-Type: {ctype}\r\n\r\n".encode(),path.read_bytes(),b"\r\n",
               f"--{boundary}--\r\n".encode()]
    return boundary,b"".join(chunks)

def post_form(url,fields,timeout=60):
    data=urllib.parse.urlencode(fields).encode()
    req=urllib.request.Request(url,data=data,method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

def upload_photo(page,token,path):
    url=f"https://graph.facebook.com/{API}/{page}/photos"
    boundary,body=multipart({"published":"false","access_token":token},"source",path)
    req=urllib.request.Request(url,data=body,method="POST",headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode())

def schedule_feed(page,token,message,when,photo_id):
    url=f"https://graph.facebook.com/{API}/{page}/feed"
    return post_form(url,{
      "message":message,"published":"false","scheduled_publish_time":str(int(when.timestamp())),
      "attached_media[0]":json.dumps({"media_fbid":str(photo_id)},separators=(",",":")),
      "access_token":token
    })

def delete_object(object_id,token):
    url=f"https://graph.facebook.com/{API}/{object_id}"
    data=urllib.parse.urlencode({"access_token":token}).encode()
    req=urllib.request.Request(url,data=data,method="DELETE")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
    except Exception:return None

def main():
    token=os.getenv("CLEP_FB_TOKEN");page=os.getenv("CLEP_FB_PAGE_ID")
    if not token or not page:sys.exit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    cfg=json.loads(CFG.read_text(encoding="utf-8"));tz=ZoneInfo(cfg["timezone"])
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    changed=False
    for r in rows:
        if r.get("estado_editorial")!="PROGRAMADO" or r.get("post_nuevo_id"):continue
        fecha=(r.get("fecha_programada") or "").strip();hhmm=(r.get("orden_dia") or "").strip()
        message=(r.get("ficha_es") or "").strip()
        if not fecha or not hhmm or not message:continue
        try:when=datetime.fromisoformat(f"{fecha}T{hhmm}").replace(tzinfo=tz)
        except ValueError:
            print(f"SKIP {r.get('editorial_id')}: fecha/hora inválida",file=sys.stderr);continue
        if when<=datetime.now(tz):
            print(f"SKIP {r.get('editorial_id')}: horario ya pasó",file=sys.stderr);continue
        photo_id=""
        try:
            image=media_file(r)
            photo=upload_photo(page,token,image)
            photo_id=str(photo.get("id") or photo.get("post_id") or "")
            if not photo_id:raise RuntimeError("Meta no devolvió ID de foto")
            result=schedule_feed(page,token,message,when,photo_id)
            post_id=str(result.get("id") or "")
            if not post_id:raise RuntimeError("Meta no devolvió ID de post programado")
        except Exception as e:
            if photo_id:delete_object(photo_id,token)
            print(f"ERROR {r.get('editorial_id')}: {e}",file=sys.stderr);continue
        r["post_nuevo_id"]=post_id
        r["notas"]=((r.get("notas") or "")+f" | foto Meta {photo_id}; feed programado {post_id}").strip(" |")
        changed=True
        print(f"OK {r.get('editorial_id')} -> {post_id} @ {when.isoformat()}")
    if changed:
        with COLA.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

if __name__=="__main__":main()
