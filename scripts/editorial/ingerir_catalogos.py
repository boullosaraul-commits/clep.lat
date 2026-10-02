#!/usr/bin/env python3
"""Ingesta determinista de catálogos web mediante JSON-LD verificable.

Sólo crea candidatos cuando una página oficial expone metadatos estructurados
(Event o VideoObject). Si no hay JSON-LD suficiente, no infiere ni publica.
"""
from __future__ import annotations
import csv, hashlib, html, json, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"data/editorial/fuentes.json"
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/2.0 (+https://clep.lat)"

RULES={
 "inet-video":("/perspectives/videos/","video"),
 "inet-events":("/events/","convocatoria_evento"),
 "levy-events":("/events/event/","convocatoria_evento"),
}

class PageParser(HTMLParser):
    def __init__(self,base):
        super().__init__();self.base=base;self.links=[];self.in_jsonld=False;self.buf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href"):
            self.links.append(urllib.parse.urljoin(self.base,a["href"]))
        if tag=="script" and (a.get("type") or "").lower()=="application/ld+json":
            self.in_jsonld=True;self.buf.append("")
    def handle_endtag(self,tag):
        if tag=="script" and self.in_jsonld:self.in_jsonld=False
    def handle_data(self,data):
        if self.in_jsonld and self.buf:self.buf[-1]+=data

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req,timeout=35) as r:return r.read(4_000_000).decode("utf-8","replace"),r.geturl()

def objects(x):
    if isinstance(x,list):
        for z in x:yield from objects(z)
    elif isinstance(x,dict):
        if "@graph" in x:yield from objects(x["@graph"])
        yield x

def parse_jsonld(text,base):
    p=PageParser(base);p.feed(text);out=[]
    for raw in p.buf:
        try:d=json.loads(raw)
        except Exception:continue
        out.extend(objects(d))
    return p.links,out

def type_has(obj,name):
    t=obj.get("@type")
    return name in (t if isinstance(t,list) else [t])

def person_name(x):
    if isinstance(x,str):return x.strip()
    if isinstance(x,list):return "; ".join(person_name(y) for y in x if person_name(y))
    if isinstance(x,dict):return str(x.get("name") or "").strip()
    return ""

def image_url(x):
    if isinstance(x,str):return x
    if isinstance(x,list):return image_url(x[0]) if x else ""
    if isinstance(x,dict):return str(x.get("url") or x.get("contentUrl") or "")
    return ""

def canonical(obj,fallback):
    u=obj.get("url") or obj.get("@id") or fallback
    return urllib.parse.urljoin(fallback,str(u))

def candidate_from(obj,kind,url,src,now):
    if kind=="video" and not type_has(obj,"VideoObject"):return None
    if kind=="convocatoria_evento" and not type_has(obj,"Event"):return None
    title=str(obj.get("name") or obj.get("headline") or "").strip()
    if not title:return None
    access=canonical(obj,url)
    if urllib.parse.urlparse(access).scheme!="https":return None
    key=hashlib.sha256((src["id"]+"|"+access).encode()).hexdigest()[:24]
    row={
      "candidate_id":"CAND-"+hashlib.sha256((src["id"]+"|"+access).encode()).hexdigest()[:16].upper(),
      "source_id":src["id"],"source_type":"web_catalog","source_item_id":access,"detected_at":now,
      "title":title,"source_url":access,"access_url":access,"area_clep":src.get("area_clep",""),
      "flujo_editorial":src.get("flujo_editorial","recurso"),"priority":str(src.get("prioridad",50)),
      "relevance_score":"0","relevance_reasons":"pendiente_reglas","oa_status":"NO_APLICA",
      "access_status":"OFFICIAL_SOURCE_VERIFIED","rights_status":"LINK_ONLY","dedupe_key":key,
      "status":"METADATOS_OBTENIDOS","content_type":kind,"source_name":src.get("nombre",""),
      "summary":re.sub(r"\s+"," ",html.unescape(str(obj.get("description") or ""))).strip(),
      "official_image_url":image_url(obj.get("thumbnailUrl") or obj.get("image")),
      "official_image_source":access,"official_image_rights":""
    }
    if kind=="video":
        row["speaker_or_organization"]=person_name(obj.get("creator") or obj.get("author") or obj.get("publisher"))
        row["published_at"]=str(obj.get("uploadDate") or obj.get("datePublished") or "")
    else:
        row["organizer"]=person_name(obj.get("organizer")) or src.get("nombre","")
        row["date_or_deadline"]=str(obj.get("startDate") or "")
        row["published_at"]=str(obj.get("startDate") or "")
    return row

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    existing={r.get("dedupe_key") for r in rows if r.get("dedupe_key")}
    now=datetime.now(timezone.utc).isoformat(timespec="seconds");added=0
    for src in cfg.get("fuentes",[]):
        if src.get("id") not in RULES or not src.get("habilitada"):continue
        pathpart,kind=RULES[src["id"]]
        try:landing,base=fetch(src["url"]);links,_=parse_jsonld(landing,base)
        except Exception as e:
            print(f"ERROR {src['id']}: {type(e).__name__}: {e}");continue
        host=urllib.parse.urlparse(base).netloc
        candidates=[]
        for u in links:
            pu=urllib.parse.urlparse(u)
            if pu.scheme=="https" and pu.netloc==host and pathpart in pu.path:
                candidates.append(u.split("#",1)[0].split("?",1)[0])
        for u in list(dict.fromkeys(candidates))[:30]:
            try:text,final=fetch(u);_,objs=parse_jsonld(text,final)
            except Exception:continue
            for obj in objs:
                row=candidate_from(obj,kind,final,src,now)
                if not row or row["dedupe_key"] in existing:continue
                full={k:"" for k in fields};full.update(row)
                rows.append(full);existing.add(row["dedupe_key"]);added+=1
                break
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Catálogos estructurados: candidatos nuevos={added}")

if __name__=="__main__":main()
