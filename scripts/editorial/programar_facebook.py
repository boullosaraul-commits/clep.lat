#!/usr/bin/env python3
"""Programa en Facebook entradas PROGRAMADO de cola.csv.

No decide qué publicar. Sólo materializa en Meta decisiones editoriales ya
aprobadas. Requiere CLEP_FB_TOKEN y CLEP_FB_PAGE_ID.
"""
import csv, json, os, sys, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
COLA=ROOT/"data/editorial/cola.csv"
CFG=ROOT/"data/editorial/programacion.json"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def graph_post(page_id, token, message, when):
    url=f"https://graph.facebook.com/{API}/{page_id}/feed"
    payload=urllib.parse.urlencode({
        "message":message,
        "published":"false",
        "scheduled_publish_time":str(int(when.timestamp())),
        "access_token":token
    }).encode()
    req=urllib.request.Request(url,data=payload,method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def main():
    token=os.getenv("CLEP_FB_TOKEN")
    page=os.getenv("CLEP_FB_PAGE_ID")
    if not token or not page:
        sys.exit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    tz=ZoneInfo(cfg["timezone"])
    with COLA.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    changed=False
    for r in rows:
        if r.get("estado_editorial")!="PROGRAMADO": continue
        if r.get("post_nuevo_id"): continue
        fecha=r.get("fecha_programada","").strip()
        orden=r.get("orden_dia","").strip()
        message=r.get("ficha_es","").strip()
        if not fecha or not orden or not message: continue
        try:
            when=datetime.fromisoformat(f"{fecha}T{orden}").replace(tzinfo=tz)
        except ValueError:
            print(f"SKIP {r.get('editorial_id')}: fecha/hora inválida",file=sys.stderr); continue
        if when <= datetime.now(tz):
            print(f"SKIP {r.get('editorial_id')}: horario ya pasó",file=sys.stderr); continue
        try:
            result=graph_post(page,token,message,when)
        except Exception as e:
            print(f"ERROR {r.get('editorial_id')}: {e}",file=sys.stderr); continue
        r["post_nuevo_id"]=str(result.get("id",""))
        r["notas"]=(r.get("notas","")+" | programado en Meta").strip(" |")
        changed=True
        print(f"OK {r.get('editorial_id')} -> {r['post_nuevo_id']} @ {when.isoformat()}")
    if changed:
        with COLA.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
if __name__=="__main__": main()
