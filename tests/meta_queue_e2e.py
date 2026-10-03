#!/usr/bin/env python3
"""Fixture y verificación E2E del pipeline Meta con una cola aislada.

setup:
  crea una fila PROGRAMADO realista y una tarjeta SVG determinista.
cleanup:
  exige SCHEDULED + IDs, verifica is_published=false y elimina feed+foto.
Nunca toca data/editorial/cola.csv.
"""
import argparse,csv,json,os,sys,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
REAL=ROOT/"data/editorial/cola.csv"
TMP=ROOT/"tests/tmp_meta_queue.csv"
MEDIA=ROOT/"tests/tmp_meta_card.svg"
API=os.getenv("META_GRAPH_VERSION","v26.0")

SVG='''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500" viewBox="0 0 1200 1500">
<rect width="1200" height="1500" fill="#f5f2e9"/>
<rect width="1200" height="24" fill="#111"/>
<text x="100" y="180" font-family="Arial" font-size="36" font-weight="700">CLEP · E2E</text>
<text x="100" y="340" font-family="Georgia" font-size="70" font-weight="700">Prueba de cola PROGRAMADO</text>
<text x="100" y="470" font-family="Arial" font-size="32">GitHub → reserva durable → foto → feed programado.</text>
<text x="100" y="1410" font-family="Arial" font-size="30" font-weight="700">clep.lat</text>
</svg>'''

def graph_get(object_id,token,fields):
    q=urllib.parse.urlencode({"fields":fields,"access_token":token})
    u=f"https://graph.facebook.com/{API}/{object_id}?{q}"
    try:
        with urllib.request.urlopen(u,timeout=45) as r:return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise RuntimeError(f"GET HTTP {e.code}: {body[:700]}")

def graph_delete(object_id,token):
    data=urllib.parse.urlencode({"access_token":token}).encode()
    req=urllib.request.Request(f"https://graph.facebook.com/{API}/{object_id}",data=data,method="DELETE")
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            out=json.loads(r.read().decode())
            return out is True or (isinstance(out,dict) and out.get("success") is True)
    except urllib.error.HTTPError as e:
        if e.code in {400,404}:return True
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise RuntimeError(f"DELETE HTTP {e.code}: {body[:700]}")

def load(path):
    with path.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);return list(rd),rd.fieldnames

def setup():
    _,fields=load(REAL)
    fields=list(fields or [])
    for x in ["editorial_score","editorial_decision","editorial_policy_fingerprint","candidate_fingerprint"]:
        if x not in fields:fields.append(x)
    tz=ZoneInfo("America/Mexico_City")
    when=datetime.now(tz)+timedelta(days=7)
    # Round to minute; far enough in future to satisfy Meta.
    day=when.date().isoformat();hhmm=when.strftime("%H:%M")
    row={k:"" for k in fields}
    row.update({
      "editorial_id":"E2E-META-QUEUE","flujo_editorial":"novedad","prioridad":"1",
      "estado_editorial":"PROGRAMADO","url_id":"E2E-META-QUEUE",
      "url_original":"https://clep.lat/","titulo_original":"Prueba de cola PROGRAMADO",
      "responsables":"CLEP","tipo_recurso":"paper","anio":str(when.year),"idioma_obra":"es",
      "obra_estado":"OBRA_VERIFICADA","edicion_estado":"EDICION_VERIFICADA","oa_estado":"OA_VERIFICADO",
      "oa_url":"https://clep.lat/","oa_fuente":"CLEP",
      "ficha_es":"PRUEBA TÉCNICA · CLEP\n\nValidación automática del pipeline editorial. Este post queda programado en el futuro y se elimina inmediatamente durante la misma prueba.",
      "fecha_programada":day,"orden_dia":hhmm,
      "notas":"Fixture E2E aislado; no pertenece a la cola de producción.",
      "media_type":"image/svg+xml","media_path":"tests/tmp_meta_card.svg",
      "media_source":"CLEP deterministic E2E card","media_rights_status":"PROPIO_DETERMINISTA",
      "alt_text":"Tarjeta CLEP de prueba técnica",
      "text_method":"deterministic_template","text_template":"paper","text_status":"VERIFICADO",
      "editorial_score":"8.0","editorial_decision":"PUBLISHABLE",
      "editorial_policy_fingerprint":"meta-e2e-policy","candidate_fingerprint":"meta-e2e-candidate"
    })
    MEDIA.write_text(SVG,encoding="utf-8")
    with TMP.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(row)
    print(f"Fixture E2E listo: {day} {hhmm}")

def cleanup():
    token=os.getenv("CLEP_FB_TOKEN")
    if not token:raise SystemExit("Falta CLEP_FB_TOKEN")
    rows,_=load(TMP)
    if len(rows)!=1:raise SystemExit("fixture E2E inválido")
    r=rows[0]
    if r.get("meta_attempt_status")!="SCHEDULED":
        TMP.unlink(missing_ok=True);MEDIA.unlink(missing_ok=True)
        print("E2E cleanup: no llegó a SCHEDULED; no hay objeto Meta que limpiar.")
        return
    post=(r.get("post_nuevo_id") or "").strip();photo=(r.get("meta_photo_id") or "").strip()
    if not post or not photo:raise SystemExit("E2E sin IDs Meta")
    obj=graph_get(post,token,"id,is_published")
    if str(obj.get("id") or "")!=post:raise SystemExit("Meta devolvió otro ID")
    if obj.get("is_published") is True:raise SystemExit("E2E se publicó: abortar limpieza automática")
    ok_post=graph_delete(post,token)
    ok_photo=graph_delete(photo,token)
    if not (ok_post and ok_photo):
        raise SystemExit(f"limpieza incompleta: post={post} photo={photo}")
    print(f"E2E OK: reserva durable -> foto {photo} -> feed {post} -> verificado no publicado -> limpieza OK")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["setup","cleanup"]);a=ap.parse_args()
    setup() if a.mode=="setup" else cleanup()
if __name__=="__main__":main()
