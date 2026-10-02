#!/usr/bin/env python3
"""Prueba de integración Meta sin publicación pública.

Sube una foto no publicada, crea un Page feed post programado siete días en el
futuro, verifica que Meta devuelve y expone el ID del feed post y elimina ambos
objetos inmediatamente. No toca cola.csv.

Si la limpieza falla, termina con error e imprime únicamente los IDs de Meta
para permitir retiro manual; nunca imprime tokens.
"""
import json,mimetypes,os,subprocess,tempfile,urllib.parse,urllib.request,urllib.error,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path

API=os.getenv("META_GRAPH_VERSION","v26.0")

SVG='''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500">
<rect width="1200" height="1500" fill="#f5f2e9"/>
<rect width="1200" height="24" fill="#111"/>
<text x="100" y="250" font-family="Arial" font-size="46" font-weight="700">CLEP · PRUEBA TÉCNICA</text>
<text x="100" y="390" font-family="Georgia" font-size="70" font-weight="700">Integración GitHub → Meta</text>
<text x="100" y="500" font-family="Arial" font-size="34">Objeto programado de prueba; se elimina automáticamente.</text>
<text x="100" y="1420" font-family="Arial" font-size="32" font-weight="700">clep.lat</text>
</svg>'''

def multipart(fields,file_field,path):
    boundary="----CLEPSMOKE"+uuid.uuid4().hex
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

def http_json(req,token,timeout=60):
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise RuntimeError(f"Meta HTTP {e.code}: {body[:1000]}") from None

def post_form(url,fields,token):
    data=urllib.parse.urlencode(fields).encode()
    req=urllib.request.Request(url,data=data,method="POST")
    return http_json(req,token)

def upload_photo(page,token,path):
    url=f"https://graph.facebook.com/{API}/{page}/photos"
    boundary,body=multipart({"published":"false","access_token":token},"source",path)
    req=urllib.request.Request(url,data=body,method="POST",
        headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})
    return http_json(req,token,timeout=90)

def graph_get(object_id,token,fields):
    q=urllib.parse.urlencode({"fields":fields,"access_token":token})
    with urllib.request.urlopen(f"https://graph.facebook.com/{API}/{object_id}?{q}",timeout=45) as r:
        return json.loads(r.read().decode())

def graph_delete(object_id,token):
    data=urllib.parse.urlencode({"access_token":token}).encode()
    req=urllib.request.Request(f"https://graph.facebook.com/{API}/{object_id}",data=data,method="DELETE")
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            out=json.loads(r.read().decode())
            return out is True or (isinstance(out,dict) and out.get("success") is True)
    except urllib.error.HTTPError as e:
        # Already absent is an acceptable cleanup result only after deleting a
        # parent feed post that may have removed the attached unpublished photo.
        if e.code in {400,404}:return True
        raise

def main():
    token=os.environ.get("CLEP_FB_TOKEN");page=os.environ.get("CLEP_FB_PAGE_ID")
    if not token or not page:raise SystemExit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    photo_id=post_id=""
    cleanup_errors=[]
    with tempfile.TemporaryDirectory() as td:
        svg=Path(td)/"smoke.svg";png=Path(td)/"smoke.png"
        svg.write_text(SVG,encoding="utf-8")
        subprocess.run(["rsvg-convert","-w","1200","-h","1500","-o",str(png),str(svg)],check=True)
        try:
            photo=upload_photo(page,token,png)
            photo_id=str(photo.get("id") or "")
            if not photo_id:raise RuntimeError("Meta no devolvió photo_id")
            when=datetime.now(timezone.utc)+timedelta(days=7)
            feed=post_form(f"https://graph.facebook.com/{API}/{page}/feed",{
              "message":"CLEP · prueba técnica automática de integración. Este objeto se elimina antes de publicarse.",
              "published":"false","scheduled_publish_time":str(int(when.timestamp())),
              "attached_media[0]":json.dumps({"media_fbid":photo_id},separators=(",",":")),
              "access_token":token
            },token)
            post_id=str(feed.get("id") or "")
            if not post_id:raise RuntimeError("Meta no devolvió feed post ID")
            obj=graph_get(post_id,token,"id,is_published")
            if str(obj.get("id") or "")!=post_id:raise RuntimeError("ID recuperado no coincide")
            if obj.get("is_published") is True:raise RuntimeError("el smoke test apareció como publicado")
            print(f"SMOKE OK: photo_id={photo_id}; feed_post_id={post_id}; is_published={obj.get('is_published')}")
        finally:
            if post_id:
                try:
                    if not graph_delete(post_id,token):cleanup_errors.append("feed post")
                except Exception:cleanup_errors.append("feed post")
            if photo_id:
                try:
                    if not graph_delete(photo_id,token):cleanup_errors.append("photo")
                except Exception:cleanup_errors.append("photo")
            if cleanup_errors:
                raise RuntimeError("FALLÓ LIMPIEZA META; revisar manualmente IDs "
                                   f"feed={post_id or '-'} photo={photo_id or '-'}; objetos: {', '.join(cleanup_errors)}")
            if post_id or photo_id:
                print("CLEANUP OK: objetos de prueba retirados.")

if __name__=="__main__":main()
