#!/usr/bin/env python3
"""Materializa UNA reserva IN_FLIGHT en Facebook con texto + imagen.

Contrato de seguridad:
- la fila debe haber sido marcada IN_FLIGHT y committeada antes de este script;
- requiere --editorial-id;
- éxito: guarda feed post ID, photo ID y SCHEDULED;
- cualquier error: marca REVIEW y nunca reintenta automáticamente.

Esto evita duplicados automáticos si un runner cae después de que Meta acepte
el post pero antes de que GitHub reciba el estado final.
"""
import argparse,csv,os,json,mimetypes,os,subprocess,sys,urllib.error,urllib.parse,urllib.request,uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
COLA=Path(os.getenv("CLEP_QUEUE_PATH",str(ROOT/"data/editorial/cola.csv"))).resolve()
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

def http_json(req,token,timeout=60):
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise RuntimeError(f"Meta HTTP {e.code}: {body[:600]}") from None

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

def post_form(url,fields,token):
    data=urllib.parse.urlencode(fields).encode()
    return http_json(urllib.request.Request(url,data=data,method="POST"),token)

def upload_photo(page,token,path):
    url=f"https://graph.facebook.com/{API}/{page}/photos"
    boundary,body=multipart({"published":"false","access_token":token},"source",path)
    req=urllib.request.Request(url,data=body,method="POST",
        headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})
    return http_json(req,token,timeout=90)

def schedule_feed(page,token,message,when,photo_id):
    return post_form(f"https://graph.facebook.com/{API}/{page}/feed",{
      "message":message,"published":"false","scheduled_publish_time":str(int(when.timestamp())),
      "attached_media[0]":json.dumps({"media_fbid":str(photo_id)},separators=(",",":")),
      "access_token":token
    },token)

def delete_object(object_id,token):
    data=urllib.parse.urlencode({"access_token":token}).encode()
    req=urllib.request.Request(f"https://graph.facebook.com/{API}/{object_id}",data=data,method="DELETE")
    try:
        out=http_json(req,token,timeout=30)
        return out is True or (isinstance(out,dict) and out.get("success") is True)
    except Exception:return False

def append_note(r,msg):
    r["notas"]=((r.get("notas") or "")+" | "+msg).strip(" |")

def save(rows,fields):
    with COLA.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--editorial-id",required=True)
    args=ap.parse_args()
    token=os.getenv("CLEP_FB_TOKEN");page=os.getenv("CLEP_FB_PAGE_ID")
    if not token or not page:sys.exit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    cfg=json.loads(CFG.read_text(encoding="utf-8"));tz=ZoneInfo(cfg["timezone"])
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    matches=[r for r in rows if r.get("editorial_id")==args.editorial_id]
    if len(matches)!=1:sys.exit("editorial_id no existe o no es único")
    r=matches[0]
    if r.get("estado_editorial")!="PROGRAMADO":sys.exit("fila no está PROGRAMADO")
    if r.get("meta_attempt_status")!="IN_FLIGHT":sys.exit("fila no tiene reserva IN_FLIGHT")
    if r.get("post_nuevo_id"):sys.exit("fila ya tiene post_nuevo_id")
    fecha=(r.get("fecha_programada") or "").strip();hhmm=(r.get("orden_dia") or "").strip()
    message=(r.get("ficha_es") or "").strip()
    photo_id=""
    try:
        when=datetime.fromisoformat(f"{fecha}T{hhmm}").replace(tzinfo=tz)
        if when<=datetime.now(tz):raise ValueError("horario programado ya pasó")
        image=media_file(r)
        photo=upload_photo(page,token,image)
        photo_id=str(photo.get("id") or "")
        if not photo_id:raise RuntimeError("Meta no devolvió photo_id")
        r["meta_photo_id"]=photo_id
        feed=schedule_feed(page,token,message,when,photo_id)
        post_id=str(feed.get("id") or "")
        if not post_id:raise RuntimeError("Meta no devolvió feed post ID")
        r["post_nuevo_id"]=post_id
        r["meta_attempt_status"]="SCHEDULED"
        append_note(r,f"foto Meta {photo_id}; feed programado {post_id}")
        save(rows,fields)
        print(f"OK {r.get('editorial_id')} -> {post_id} @ {when.isoformat()}")
        return
    except Exception as e:
        # Si conocimos un photo_id pero no obtuvimos feed ID, intentamos limpiar.
        # Aun así REVIEW es conservador: una respuesta de red ambigua nunca se
        # reintenta automáticamente.
        cleaned=False
        if photo_id and not r.get("post_nuevo_id"):
            cleaned=delete_object(photo_id,token)
        r["meta_attempt_status"]="REVIEW"
        if photo_id:r["meta_photo_id"]=photo_id
        append_note(r,f"Meta REVIEW: {type(e).__name__}: {e}; foto_limpiada={cleaned}")
        save(rows,fields)
        print(f"REVIEW {r.get('editorial_id')}: {e}",file=sys.stderr)
        raise SystemExit(2)

if __name__=="__main__":main()
