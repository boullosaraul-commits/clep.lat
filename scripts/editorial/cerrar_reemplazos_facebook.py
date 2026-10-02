#!/usr/bin/env python3
"""Cierra reemplazos históricos de Facebook de forma conservadora.

Sólo retira un post original cuando:
1) la fila pertenece a archivo_historico;
2) existe post_original_id;
3) existe post_nuevo_id;
4) Meta confirma que el post nuevo existe y está publicado;
5) Meta confirma que el post original todavía existe.

Si el borrado falla, no marca el original como retirado.
"""
import csv, json, os, sys, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
COLA=ROOT/"data/editorial/cola.csv"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def graph_get(object_id, token, fields):
    q=urllib.parse.urlencode({"fields":fields,"access_token":token})
    url=f"https://graph.facebook.com/{API}/{object_id}?{q}"
    try:
        with urllib.request.urlopen(url,timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors="replace")
        raise RuntimeError(f"GET {object_id}: HTTP {e.code}: {body[:300]}")

def graph_delete(object_id, token):
    url=f"https://graph.facebook.com/{API}/{object_id}"
    data=urllib.parse.urlencode({"access_token":token}).encode()
    req=urllib.request.Request(url,data=data,method="DELETE")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors="replace")
        raise RuntimeError(f"DELETE {object_id}: HTTP {e.code}: {body[:300]}")

def is_published(obj):
    # scheduled posts commonly expose is_published=false until publication.
    if "is_published" in obj:
        return obj.get("is_published") is True
    # If Meta does not return the field, require a permalink as evidence that
    # the object is addressable as a published post.
    return bool(obj.get("permalink_url"))

def append_note(row, note):
    old=(row.get("notas") or "").strip()
    row["notas"]=(old+" | "+note).strip(" |")

def main():
    token=os.getenv("CLEP_FB_TOKEN")
    if not token: sys.exit("Falta CLEP_FB_TOKEN")
    with COLA.open(encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f); rows=list(reader); fields=reader.fieldnames
    changed=False
    for r in rows:
        if r.get("flujo_editorial")!="archivo_historico": continue
        if (r.get("original_retirado") or "").lower()=="true": continue
        old=(r.get("post_original_id") or "").strip()
        new=(r.get("post_nuevo_id") or "").strip()
        if not old or not new: continue
        try:
            new_obj=graph_get(new,token,"id,is_published,permalink_url,created_time")
        except Exception as e:
            print(f"KEEP {old}: no se pudo verificar reemplazo {new}: {e}",file=sys.stderr)
            continue
        if not is_published(new_obj):
            print(f"KEEP {old}: reemplazo {new} todavía no está publicado")
            continue
        try:
            graph_get(old,token,"id,permalink_url")
        except Exception as e:
            print(f"REVIEW {old}: no se pudo verificar original: {e}",file=sys.stderr)
            append_note(r,"revisión manual: original no verificable antes de retiro")
            changed=True
            continue
        try:
            result=graph_delete(old,token)
        except Exception as e:
            print(f"KEEP {old}: falló retiro: {e}",file=sys.stderr)
            append_note(r,"falló retiro automático; conservar referencias")
            changed=True
            continue
        if result is True or result.get("success") is True:
            now=datetime.now(timezone.utc).isoformat()
            r["original_retirado"]="true"
            r["fecha_retiro"]=now
            r["post_nuevo_url"]=new_obj.get("permalink_url","")
            r["fecha_publicacion"]=new_obj.get("created_time","")
            r["estado_editorial"]="ORIGINAL_RETIRADO"
            append_note(r,"reemplazo verificado en Meta; original retirado después de verificación")
            changed=True
            print(f"OK {old} retirado después de verificar {new}")
        else:
            print(f"KEEP {old}: Meta no confirmó DELETE: {result}",file=sys.stderr)
    if changed:
        with COLA.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

if __name__=="__main__": main()
