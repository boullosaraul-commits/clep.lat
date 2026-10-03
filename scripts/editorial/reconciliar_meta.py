#!/usr/bin/env python3
"""Reconcilia reservas Meta ambiguas sin reintentar publicaciones.

Busca PROGRAMADO + IN_FLIGHT/REVIEW sin post_nuevo_id en la lista de posts
programados de la página. Una coincidencia única de mensaje y hora recupera el
post ID. Cero coincidencias convierte IN_FLIGHT en REVIEW; varias coincidencias
permanecen REVIEW. Si Meta no puede consultarse, termina con error para impedir
nuevos writes en esa ejecución.
"""
import argparse,csv,json,os,re,sys,urllib.error,urllib.parse,urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
COLA=Path(os.getenv("CLEP_QUEUE_PATH",str(ROOT/"data/editorial/cola.csv"))).resolve()
CFG=ROOT/"data/editorial/programacion.json"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def norm(s):return re.sub(r"\s+"," ",str(s or "")).strip()

def graph_get(url,token):
    sep="&" if "?" in url else "?"
    req=urllib.request.Request(url+sep+urllib.parse.urlencode({"access_token":token}))
    try:
        with urllib.request.urlopen(req,timeout=40) as r:return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise RuntimeError(f"Meta HTTP {e.code}: {body[:400]}") from None

def scheduled_objects(page,token):
    fields="id,message,scheduled_publish_time,permalink_url"
    endpoints=[
      f"https://graph.facebook.com/{API}/{page}/scheduled_posts?"+urllib.parse.urlencode({"fields":fields,"limit":"100"}),
      f"https://graph.facebook.com/{API}/{page}/promotable_posts?"+urllib.parse.urlencode({"is_published":"false","fields":fields,"limit":"100"})
    ]
    errors=[]
    for url in endpoints:
        try:
            o=graph_get(url,token)
            if isinstance(o,dict) and isinstance(o.get("data"),list):return o["data"]
        except Exception as e:errors.append(str(e))
    raise RuntimeError("No fue posible consultar posts programados: "+" | ".join(errors))

def target_timestamp(r,tz):
    return int(datetime.fromisoformat(f"{r['fecha_programada']}T{r['orden_dia']}").replace(tzinfo=tz).timestamp())

def obj_timestamp(o):
    x=o.get("scheduled_publish_time")
    if isinstance(x,(int,float)):return int(x)
    if isinstance(x,str):
        if x.isdigit():return int(x)
        try:return int(datetime.fromisoformat(x.replace("Z","+00:00")).timestamp())
        except Exception:return None
    return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--probe",action="store_true");args=ap.parse_args()
    token=os.getenv("CLEP_FB_TOKEN");page=os.getenv("CLEP_FB_PAGE_ID")
    if not token or not page:sys.exit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    if args.probe:
        objects=scheduled_objects(page,token)
        print(f"Meta reconcile probe: lectura OK; programados visibles={len(objects)}")
        return
    cfg=json.loads(CFG.read_text(encoding="utf-8"));tz=ZoneInfo(cfg["timezone"])
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    pending=[r for r in rows if r.get("estado_editorial")=="PROGRAMADO"
             and r.get("meta_attempt_status") in {"IN_FLIGHT","REVIEW"}
             and not (r.get("post_nuevo_id") or "").strip()]
    if not pending:
        print("Meta reconcile: sin intentos ambiguos.")
        return
    objects=scheduled_objects(page,token)
    changed=resolved=ambiguous=missing=0
    for r in pending:
        msg=norm(r.get("ficha_es"));ts=target_timestamp(r,tz)
        matches=[o for o in objects if norm(o.get("message"))==msg
                 and obj_timestamp(o) is not None and abs(obj_timestamp(o)-ts)<=120]
        if len(matches)==1:
            o=matches[0];r["post_nuevo_id"]=str(o.get("id") or "")
            r["post_nuevo_url"]=str(o.get("permalink_url") or "")
            r["meta_attempt_status"]="SCHEDULED"
            r["notas"]=((r.get("notas") or "")+" | Meta reconciliado: feed programado recuperado").strip(" |")
            resolved+=1;changed+=1
        elif len(matches)>1:
            r["meta_attempt_status"]="REVIEW"
            r["notas"]=((r.get("notas") or "")+f" | Meta reconcile ambiguo: {len(matches)} coincidencias").strip(" |")
            ambiguous+=1;changed+=1
        else:
            if r.get("meta_attempt_status")=="IN_FLIGHT":
                r["meta_attempt_status"]="REVIEW";changed+=1
                r["notas"]=((r.get("notas") or "")+" | Meta reconcile: sin feed coincidente; no reintentar automáticamente").strip(" |")
            missing+=1
    if changed:
        with COLA.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Meta reconcile: pendientes={len(pending)}; resueltos={resolved}; ambiguos={ambiguous}; sin_coincidencia={missing}")

if __name__=="__main__":main()
