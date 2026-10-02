#!/usr/bin/env python3
"""Enriquece candidatos NEP consultando metadatos ReDIF del archivo proveedor.

Resolución:
  RePEc:aaa:series:item -> archivo aaa -> URL base -> serie -> ficheros ReDIF
El script sólo completa campos que encuentra literalmente en ReDIF.
No declara OA: File-URL pasa a access_url pero oa_status queda POR_VERIFICAR.
"""
import csv, re, urllib.request
from pathlib import Path
from urllib.parse import urljoin

ROOT=Path(__file__).resolve().parents[2]
IN=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/1.2 (+https://clep.lat)"
ARCHIVES="https://ideas.repec.org/getdata.html"

def get(url,limit=8_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read(limit).decode("utf-8","replace")

def fields(block):
    out={}
    key=None
    for line in block.splitlines():
        m=re.match(r"^([A-Za-z][A-Za-z0-9-]*):\s*(.*)$",line)
        if m:
            key=m.group(1).lower(); out.setdefault(key,[]).append(m.group(2).strip())
        elif key and line[:1].isspace() and out[key]:
            out[key][-1]+=" "+line.strip()
    return out

def handle_of(r):
    x=r.get("source_item_id","")
    return x if x.lower().startswith("repec:") else ""

def archive_base(code):
    # RePEc's archive registry is a flat ReDIF file exposed by EconPapers.
    txt=get("https://econpapers.repec.org/RePEc/"+code+"/"+code+"arch.rdf")
    f=fields(txt)
    return (f.get("url") or [""])[0]

def candidate_files(base,code,series):
    # Common RePEc layout: series directory contains one or more rdf/redif files.
    # Directory listings are parsed only to locate metadata files, never bibliographic HTML.
    page=get(urljoin(base,series+"/"))
    hrefs=re.findall(r'href=["\']([^"\']+\.(?:rdf|redif))["\']',page,re.I)
    return [urljoin(base,series+"/"+h) for h in hrefs]

def find_record(text,handle):
    chunks=re.split(r"(?=^Template-Type:)",text,flags=re.M)
    target=handle.lower()
    for b in chunks:
        f=fields(b)
        if any(x.lower()==target for x in f.get("handle",[])): return f
    return None

def main():
    with IN.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    cache_base={}; cache_files={}; cache_text={}
    enriched=0; failed=0
    for r in rows:
        h=handle_of(r)
        if not h or r.get("title"): continue
        p=h.split(":")
        if len(p)<4: continue
        code,series=p[1],p[2]
        try:
            base=cache_base.setdefault(code,archive_base(code))
            if not base: raise ValueError("archivo sin URL")
            key=(code,series)
            if key not in cache_files: cache_files[key]=candidate_files(base,code,series)
            rec=None
            for u in cache_files[key]:
                if u not in cache_text: cache_text[u]=get(u)
                rec=find_record(cache_text[u],h)
                if rec: break
            if not rec: raise ValueError("handle no encontrado en ReDIF")
            r["title"]=(rec.get("title") or [""])[0]
            r["authors"]="; ".join(rec.get("author-name",[]))
            r["summary"]=(rec.get("abstract") or [""])[0]
            r["published_at"]=(rec.get("creation-date") or rec.get("year") or [""])[0]
            files=rec.get("file-url",[])
            if files: r["access_url"]=files[0]
            r["doi"]=(rec.get("doi") or [""])[0].removeprefix("https://doi.org/")
            r["language"]=(rec.get("language") or [""])[0]
            r["status"]="METADATOS_OBTENIDOS"
            r["notes"]=(r.get("notes","")+" | Metadatos obtenidos del ReDIF del proveedor; OA aún por verificar.").strip(" |")
            enriched+=1
        except Exception as e:
            r["notes"]=(r.get("notes","")+f" | Error metadatos: {type(e).__name__}: {e}").strip(" |")
            failed+=1
    with IN.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    print(f"Metadatos obtenidos: {enriched}")
    print(f"Pendientes/error: {failed}")

if __name__=="__main__": main()
