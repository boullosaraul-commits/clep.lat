#!/usr/bin/env python3
"""Verifica en Meta qué posts programados ya fueron publicados.

No elimina nada. Actualiza estado_editorial=PUBLICADO y metadatos de publicación
cuando Meta confirma is_published=true.
"""
import csv,json,os,sys,urllib.parse,urllib.request,urllib.error
from pathlib import Path

from editorial_rules import validate_transition

ROOT=Path(__file__).resolve().parents[2]
COLA=ROOT/"data/editorial/cola.csv"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def graph_get(object_id,token,fields):
    q=urllib.parse.urlencode({"fields":fields,"access_token":token})
    u=f"https://graph.facebook.com/{API}/{object_id}?{q}"
    try:
        with urllib.request.urlopen(u,timeout=30) as r:return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:300]}")

def main():
    token=os.getenv("CLEP_FB_TOKEN")
    if not token:sys.exit("Falta CLEP_FB_TOKEN")
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    changed=0
    for r in rows:
        if r.get("estado_editorial")!="PROGRAMADO":continue
        pid=(r.get("post_nuevo_id") or "").strip()
        if not pid:continue
        try:o=graph_get(pid,token,"id,is_published,permalink_url,created_time")
        except Exception as e:
            print(f"VERIFY {pid}: {e}",file=sys.stderr);continue
        if o.get("is_published") is not True:continue
        validate_transition("publication","SCHEDULED","PUBLISHED")
        validate_transition("meta","SCHEDULED","PUBLISHED")
        r["estado_editorial"]="PUBLICADO"
        r["meta_attempt_status"]="PUBLISHED"
        if o.get("permalink_url"):r["post_nuevo_url"]=o["permalink_url"]
        if o.get("created_time"):r["fecha_publicacion"]=o["created_time"]
        r["notas"]=((r.get("notas") or "")+" | publicación verificada en Meta").strip(" |")
        changed+=1
    if changed:
        with COLA.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Publicaciones verificadas: {changed}")

if __name__=="__main__":main()
