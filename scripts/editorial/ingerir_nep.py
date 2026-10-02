#!/usr/bin/env python3
"""Ingesta determinista de páginas oficiales NEP hacia candidatos CLEP."""
import csv, hashlib, html, json, re, sys, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"data/editorial/fuentes.json"
OUT=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/1.0 (+https://clep.lat)"
FIELDS=["candidate_id","source_id","source_type","source_item_id","detected_at","published_at",
"title","authors","summary","source_url","access_url","doi","language","area_clep",
"flujo_editorial","priority","relevance_score","relevance_reasons","oa_status",
"dedupe_key","status","notes"]

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def dedupe_key(title,url):
    base="url:"+url if url else "title:"+re.sub(r"\W+"," ",title.lower()).strip()
    return hashlib.sha256(base.encode()).hexdigest()[:24]

class Parser(HTMLParser):
    def __init__(self,base):
        super().__init__(); self.base=base; self.cur=None; self.items=[]
    def handle_starttag(self,tag,attrs):
        if tag!="a": return
        href=dict(attrs).get("href","")
        absolute=urljoin(self.base,href)
        if "d.repec.org/n?u=" in absolute:
            self.cur={"url":absolute,"text":[]}
    def handle_data(self,data):
        if self.cur is not None: self.cur["text"].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.cur is not None:
            title=clean(" ".join(self.cur["text"]))
            if title: self.items.append((title,self.cur["url"]))
            self.cur=None

def fetch(url):
    if urlparse(url).scheme!="https": raise ValueError("Sólo HTTPS")
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read(3_000_000).decode("utf-8","replace")

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    with OUT.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    seen={(r["source_id"],r["source_item_id"]) for r in rows}
    dedupes={r["dedupe_key"] for r in rows if r.get("dedupe_key")}
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    added=0
    for src in cfg.get("fuentes",[]):
        if not src.get("habilitada") or src.get("tipo")!="nep_report": continue
        try:
            p=Parser(src["url"]); p.feed(fetch(src["url"]))
        except Exception as e:
            print(f"ERROR {src['id']}: {e}",file=sys.stderr); continue
        for title,url in p.items:
            item_id=url; d=dedupe_key(title,url)
            if (src["id"],item_id) in seen or d in dedupes: continue
            row={k:"" for k in FIELDS}
            row.update({
                "candidate_id":"CAND-"+hashlib.sha256(f"{src['id']}|{item_id}".encode()).hexdigest()[:16].upper(),
                "source_id":src["id"],"source_type":"nep_report","source_item_id":item_id,
                "detected_at":now,"title":title,"source_url":url,"access_url":url,
                "area_clep":src.get("area_clep",""),"flujo_editorial":src.get("flujo_editorial","novedad"),
                "priority":str(src.get("prioridad",100)),"relevance_score":"0",
                "relevance_reasons":"pendiente_reglas","oa_status":"POR_VERIFICAR",
                "dedupe_key":d,"status":"DETECTADO",
                "notes":"Detectado en reporte oficial NEP; acceso abierto del documento aún no verificado."
            })
            rows.append(row); seen.add((src["id"],item_id)); dedupes.add(d); added+=1
    with OUT.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"Candidatos NEP nuevos: {added}")
    print(f"Candidatos totales: {len(rows)}")

if __name__=="__main__": main()
