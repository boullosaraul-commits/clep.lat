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
import argparse,csv,hashlib,os,json,mimetypes,subprocess,sys,urllib.error,urllib.parse,urllib.request,uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from editorial_rules import check_meta_ready

ROOT=Path(__file__).resolve().parents[2]
COLA=Path(os.getenv("CLEP_QUEUE_PATH",str(ROOT/"data/editorial/cola.csv"))).resolve()
CFG=ROOT/"data/editorial/programacion.json"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def approved_upload(row):
    from calidad_visual import current_visual_approval, raster_check
    from validar_media import validate_media
    from urllib.parse import urlsplit

    if not current_visual_approval(row):
        raise ValueError("media sin certificación visual vigente")
    source = urlsplit(row.get("media_source_url") or "")
    if source.scheme != "https" or not source.hostname or not row.get("media_source") or not row.get("alt_text"):
        raise ValueError("media sin procedencia o descripción factual")
    validation = validate_media(row)
    if not validation.valid:
        raise ValueError(f"media material rechazada: {[issue.code for issue in validation.errors]}")
    src = (ROOT / row["media_path"]).resolve()
    original = src.read_bytes()
    if hashlib.sha256(original).hexdigest() != row.get("media_content_sha256"):
        raise ValueError("la imagen cambió después de validarse")
    if src.suffix.lower() == ".svg":
        content = subprocess.run(
            ["rsvg-convert", "-w", "1200", "-h", "1500"],
            input=original, capture_output=True, check=True, timeout=20,
        ).stdout
        name = src.with_suffix(".png").name
    else:
        name, content = src.name, original
    check = raster_check(content, expected_size=(1200, 1500) if src.suffix.lower() == ".svg" else None)
    if not check.valid:
        raise ValueError(f"activo final {check.status}: {check.reason}")
    return name, content


def http_json(req,token,timeout=60):
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise RuntimeError(f"Meta HTTP {e.code}: {body[:600]}") from None

def multipart(fields,file_field,name,content):
    boundary="----CLEP"+uuid.uuid4().hex;chunks=[]
    for k,v in fields.items():
        chunks += [f"--{boundary}\r\n".encode(),f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode(),
                   str(v).encode("utf-8"),b"\r\n"]
    ctype=mimetypes.guess_type(name)[0] or "application/octet-stream"
    chunks += [f"--{boundary}\r\n".encode(),
               f'Content-Disposition: form-data; name="{file_field}"; filename="{name}"\r\n'.encode(),
               f"Content-Type: {ctype}\r\n\r\n".encode(),content,b"\r\n",
               f"--{boundary}--\r\n".encode()]
    return boundary,b"".join(chunks)

def post_form(url,fields,token):
    data=urllib.parse.urlencode(fields).encode()
    return http_json(urllib.request.Request(url,data=data,method="POST"),token)

def upload_photo(page,token,name,content):
    url=f"https://graph.facebook.com/{API}/{page}/photos"
    boundary,body=multipart({"published":"false","access_token":token},"source",name,content)
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
    mode=(os.getenv("CLEP_META_MODE") or "live").strip().lower()
    token=os.getenv("CLEP_FB_TOKEN");page=os.getenv("CLEP_FB_PAGE_ID")
    if mode!="mock" and (not token or not page):sys.exit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    cfg=json.loads(CFG.read_text(encoding="utf-8"));tz=ZoneInfo(cfg["timezone"])
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    matches=[r for r in rows if r.get("editorial_id")==args.editorial_id]
    if len(matches)!=1:sys.exit("editorial_id no existe o no es único")
    r=matches[0]
    ready=check_meta_ready(r)
    if not ready:
        detail=f": {ready.detail}" if ready.detail else ""
        sys.exit(f"fila no lista para Meta: {ready.code}{detail}")
    fecha=(r.get("fecha_programada") or "").strip();hhmm=(r.get("orden_dia") or "").strip()
    message=(r.get("ficha_es") or "").strip()
    photo_id="";feed_attempted=False;photo_attempted=False
    try:
        when=datetime.fromisoformat(f"{fecha}T{hhmm}").replace(tzinfo=tz)
        if mode!="mock" and when<=datetime.now(tz):raise ValueError("horario programado ya pasó")
        if mode=="mock":
            raw=(r.get("media_path") or "").strip()
            image=(ROOT/raw).resolve()
            if ROOT.resolve() not in image.parents or not image.is_file():
                raise ValueError("imagen mock inexistente o fuera del repositorio")
        else:
            name, content = approved_upload(r)
        if mode=="mock":
            dig=hashlib.sha256((r.get("editorial_id","")+"|"+fecha+"|"+hhmm).encode()).hexdigest()[:16]
            photo_id="mock-photo-"+dig
            post_id="mock-post-"+dig
            r["meta_photo_id"]=photo_id
            r["post_nuevo_id"]=post_id
            r["meta_attempt_status"]="SCHEDULED"
            append_note(r,f"Meta mock foto {photo_id}; feed simulado {post_id}")
            save(rows,fields)
            print(f"MOCK {r.get('editorial_id')} -> {post_id} @ {when.isoformat()}")
            return
        if "media_upload_sha256" not in fields:
            fields.append("media_upload_sha256")
        r["media_upload_sha256"] = hashlib.sha256(content).hexdigest()
        save(rows,fields)
        print(f"MEDIA_APPROVED {r.get('editorial_id')} sha256={r['media_upload_sha256']}")
        photo_attempted=True
        photo=upload_photo(page,token,name,content)
        photo_id=str(photo.get("id") or "")
        if not photo_id:raise RuntimeError("Meta no devolvió photo_id")
        r["meta_photo_id"]=photo_id
        feed_attempted=True
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
        # Una vez iniciado el intento de feed no borramos la foto: el POST pudo
        # haber sido aceptado aunque la respuesta se perdiera. La reconciliación
        # posterior decide si existe el feed; nunca hay retry automático.
        r["meta_attempt_status"]="REVIEW" if photo_attempted else "FAILED"
        if photo_id:r["meta_photo_id"]=photo_id
        append_note(r,f"Meta REVIEW: {type(e).__name__}: {e}; feed_attempted={feed_attempted}; foto_preservada={bool(photo_id)}")
        save(rows,fields)
        print(f"REVIEW {r.get('editorial_id')}: {e}",file=sys.stderr)
        raise SystemExit(2)

if __name__=="__main__":main()
