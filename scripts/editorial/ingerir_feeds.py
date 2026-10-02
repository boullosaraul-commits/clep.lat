#!/usr/bin/env python3
"""Ingesta determinista de RSS/Atom hacia candidatos editoriales CLEP.

No publica en redes, no usa LLM y no modifica cola.csv.
"""
import csv, hashlib, html, json, re, sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"data/editorial/fuentes.json"
OUT=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/1.0 (+https://clep.lat)"

FIELDS=["candidate_id","source_id","source_type","source_item_id","detected_at","published_at",
"title","authors","summary","source_url","access_url","doi","language","area_clep",
"flujo_editorial","priority","relevance_score","relevance_reasons","oa_status",
"dedupe_key","status","notes"]

def txt(el,name):
    x=el.find(name)
    return (x.text or "").strip() if x is not None else ""

def strip_tags(s):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s or ""))).strip()

def key(title,doi,url):
    if doi: base="doi:"+doi.lower().strip()
    elif url: base="url:"+url.strip()
    else: base="title:"+re.sub(r"\W+"," ",title.lower()).strip()
    return hashlib.sha256(base.encode()).hexdigest()[:24]

def cid(source_id,item_id,dedupe):
    return "CAND-"+hashlib.sha256(f"{source_id}|{item_id}|{dedupe}".encode()).hexdigest()[:16].upper()

def fetch(url):
    p=urlparse(url)
    if p.scheme!="https": raise ValueError("Sólo se admiten feeds HTTPS")
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req,timeout=30) as r:
        data=r.read(3_000_000)
    return ET.fromstring(data)

def entries(root):
    # RSS
    for item in root.findall(".//item"):
        title=txt(item,"title"); link=txt(item,"link"); guid=txt(item,"guid") or link or title
        desc=txt(item,"description"); pub=txt(item,"pubDate")
        yield title,link,guid,desc,pub
    # Atom
    ns="{http://www.w3.org/2005/Atom}"
    for e in root.findall(f".//{ns}entry"):
        title=txt(e,f"{ns}title"); guid=txt(e,f"{ns}id") or title
        link=""
        for l in e.findall(f"{ns}link"):
            if l.attrib.get("rel","alternate")=="alternate" and l.attrib.get("href"):
                link=l.attrib["href"]; break
        desc=txt(e,f"{ns}summary") or txt(e,f"{ns}content")
        pub=txt(e,f"{ns}published") or txt(e,f"{ns}updated")
        yield title,link,guid,desc,pub

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    existing=[]
    if OUT.exists():
        with OUT.open(encoding="utf-8",newline="") as f: existing=list(csv.DictReader(f))
    seen={(r["source_id"],r["source_item_id"]) for r in existing}
    dedupes={r["dedupe_key"] for r in existing if r.get("dedupe_key")}
    added=0
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")

    for src in cfg.get("fuentes",[]):
        if not src.get("habilitada"): continue
        if src.get("tipo")!="rss": continue
        url=(src.get("url") or "").strip()
        if not url: continue
        try: root=fetch(url)
        except Exception as e:
            print(f"ERROR {src['id']}: {e}",file=sys.stderr); continue

        for title,link,item_id,summary,published in entries(root):
            title=strip_tags(title); summary=strip_tags(summary)
            if not title: continue
            d=key(title,"",link)
            pair=(src["id"],item_id)
            if pair in seen or d in dedupes: continue
            row={k:"" for k in FIELDS}
            row.update({
                "candidate_id":cid(src["id"],item_id,d),
                "source_id":src["id"],"source_type":"rss","source_item_id":item_id,
                "detected_at":now,"published_at":published,"title":title,
                "summary":summary,"source_url":link,"access_url":link,
                "area_clep":src.get("area_clep",""),"flujo_editorial":src.get("flujo_editorial","novedad"),
                "priority":str(src.get("prioridad",100)),"relevance_score":"0",
                "relevance_reasons":"pendiente_reglas","oa_status":"POR_VERIFICAR",
                "dedupe_key":d,"status":"DETECTADO"
            })
            existing.append(row); seen.add(pair); dedupes.add(d); added+=1

    with OUT.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(existing)
    print(f"Candidatos nuevos: {added}")
    print(f"Candidatos totales: {len(existing)}")

if __name__=="__main__": main()
