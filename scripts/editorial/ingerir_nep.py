#!/usr/bin/env python3
"""Ingesta NEP determinista.

NEP se usa para descubrir handles. La ingestión NO intenta inferir título,
autores ni OA desde el texto visible del enlace: conserva el handle RePEc
como identidad bibliográfica para una etapa posterior de enriquecimiento.
"""
import csv, hashlib, html, json, re, sys, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"data/editorial/fuentes.json"
OUT=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/1.1 (+https://clep.lat)"
FIELDS=["candidate_id","source_id","source_type","source_item_id","detected_at","published_at",
"title","authors","summary","source_url","access_url","doi","language","area_clep",
"flujo_editorial","priority","relevance_score","relevance_reasons","oa_status",
"dedupe_key","status","notes","summary_es","translation_engine","translation_status","content_type","source_name","venue","publication_year","access_status","rights_status","official_image_url","official_image_source","official_image_rights","indicator_or_dataset","geography","reference_period","value_or_change","official_source","organizer","date_or_deadline","speaker_or_organization","data_points_json"]

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def repec_handle(url):
    try:
        u=parse_qs(urlparse(url).query).get("u",[""])[0]
        return u if u.lower().startswith("repec:") else ""
    except Exception:
        return ""

def dedupe_key(handle):
    return hashlib.sha256(("repec:"+handle.lower()).encode()).hexdigest()[:24]

class Parser(HTMLParser):
    def __init__(self,base):
        super().__init__(); self.base=base; self.cur=None; self.items=[]
    def handle_starttag(self,tag,attrs):
        if tag!="a": return
        absolute=urljoin(self.base,dict(attrs).get("href",""))
        h=repec_handle(absolute)
        if h: self.cur={"url":absolute,"handle":h}
    def handle_endtag(self,tag):
        if tag=="a" and self.cur is not None:
            self.items.append((self.cur["handle"],self.cur["url"]))
            self.cur=None

def fetch(url):
    if urlparse(url).scheme!="https": raise ValueError("Sólo HTTPS")
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read(3_000_000).decode("utf-8","replace")

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    with OUT.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    seen={(r["source_id"],r["source_item_id"]) for r in rows}
    handles={repec_handle(r.get("source_item_id","")) or r.get("notes","").removeprefix("RePEc handle: ").strip()
             for r in rows}
    handles.discard("")
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    added=0
    for src in cfg.get("fuentes",[]):
        if not src.get("habilitada") or src.get("tipo")!="nep_report": continue
        try:
            p=Parser(src["url"]); p.feed(fetch(src["url"]))
        except Exception as e:
            print(f"ERROR {src['id']}: {e}",file=sys.stderr); continue
        for handle,url in p.items:
            # Un mismo trabajo puede aparecer en varios reportes NEP:
            # se conserva una sola candidatura por handle.
            if handle in handles: continue
            item_id=handle
            row={k:"" for k in FIELDS}
            row.update({
                "candidate_id":"CAND-"+hashlib.sha256(handle.lower().encode()).hexdigest()[:16].upper(),
                "source_id":src["id"],"source_type":"nep_report","source_item_id":item_id,
                "detected_at":now,"source_url":url,
                "area_clep":src.get("area_clep",""),"flujo_editorial":src.get("flujo_editorial","novedad"),
                "priority":str(src.get("prioridad",100)),"relevance_score":"0",
                "relevance_reasons":"pendiente_metadatos","oa_status":"POR_VERIFICAR",
                "dedupe_key":dedupe_key(handle),"status":"METADATOS_PENDIENTES",
                "notes":"RePEc handle: "+handle
            })
            rows.append(row); handles.add(handle); added+=1
    with OUT.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"Candidatos NEP nuevos: {added}")
    print(f"Candidatos totales: {len(rows)}")

if __name__=="__main__": main()
