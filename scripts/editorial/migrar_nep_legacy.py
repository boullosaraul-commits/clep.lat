#!/usr/bin/env python3
"""Migra filas NEP heredadas que guardaron la URL del reporte como identidad/título.

La migración es determinista, idempotente y no inventa metadatos. Extrae el
handle RePEc del parámetro u=, borra títulos que sean URLs y colapsa duplicados
por handle antes del enriquecimiento ReDIF.
"""
import csv, hashlib
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"

def handle_from(value):
    value=(value or "").strip()
    if value.lower().startswith("repec:"):
        return value
    try:
        u=parse_qs(urlparse(value).query).get("u",[""])[0]
        return u if u.lower().startswith("repec:") else ""
    except Exception:
        return ""

def dkey(handle):
    return hashlib.sha256(("repec:"+handle.lower()).encode()).hexdigest()[:24]

def rank(r):
    try: p=int(r.get("priority") or 999)
    except ValueError: p=999
    return (p,r.get("detected_at") or "",r.get("candidate_id") or "")

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f); rows=list(rd); fields=rd.fieldnames
    passthrough=[]; groups={}
    migrated=0
    for r in rows:
        if r.get("source_type")!="nep_report":
            passthrough.append(r); continue
        h=(handle_from(r.get("source_item_id")) or handle_from(r.get("source_url"))
           or handle_from(r.get("title")))
        if not h:
            passthrough.append(r); continue
        if r.get("source_item_id")!=h: migrated+=1
        r["source_item_id"]=h
        if (r.get("title") or "").lower().startswith(("http://","https://")):
            r["title"]=""; r["authors"]=""; r["summary"]=""
            r["published_at"]=""; r["access_url"]=""; r["doi"]=""; r["language"]=""
            r["status"]="METADATOS_PENDIENTES"; r["oa_status"]="POR_VERIFICAR"
        r["dedupe_key"]=dkey(h)
        r["notes"]=("RePEc handle: "+h+" | migrado desde ingestión NEP heredada").strip()
        groups.setdefault(h,[]).append(r)
    kept=[]
    collapsed=0
    for h,rs in groups.items():
        rs.sort(key=rank)
        base=rs[0]
        if len(rs)>1:
            collapsed+=len(rs)-1
            srcs=sorted({x.get("source_id","") for x in rs if x.get("source_id")})
            base["notes"]+=" | reportes NEP: "+", ".join(srcs)
        kept.append(base)
    out=passthrough+kept
    out.sort(key=lambda r:(r.get("detected_at") or "",r.get("candidate_id") or ""))
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(out)
    print(f"Filas NEP migradas: {migrated}; duplicados colapsados: {collapsed}; total: {len(out)}")

if __name__=="__main__": main()
