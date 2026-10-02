#!/usr/bin/env python3
"""Enriquece candidatos NEP usando el gateway OAI-PMH oficial de RePEc.

NEP aporta handles permanentes. Para cada handle se solicita un GetRecord en
oai_dc a oai.repec.org. Esto evita scraping de IDEAS y evita construir URLs a
partir de supuestos sobre series. El acceso abierto no se infiere aquí.
"""
import csv, html, os, re, urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/3.0 (+https://clep.lat)"
LIMIT=int(os.getenv("REPEC_ENRICH_LIMIT","40"))
BASE="https://oai.repec.org/"
NS={"oai":"http://www.openarchives.org/OAI/2.0/","dc":"http://purl.org/dc/elements/1.1/"}

def handle_from(value):
    value=(value or "").strip()
    if value.lower().startswith("repec:"):return value
    try:
        u=urllib.parse.parse_qs(urllib.parse.urlparse(value).query).get("u",[""])[0]
        return u if u.lower().startswith("repec:") else ""
    except Exception:return ""

def handle_of(r):
    h=handle_from(r.get("source_item_id")) or handle_from(r.get("source_url"))
    if h:return h
    m=re.search(r"RePEc:[^\s|]+",r.get("notes") or "",flags=re.I)
    return m.group(0) if m else ""

def fetch_record(handle):
    q=urllib.parse.urlencode({"verb":"GetRecord","identifier":handle,"metadataPrefix":"oai_dc"})
    req=urllib.request.Request(BASE+"?"+q,headers={"User-Agent":UA,"Accept":"application/xml,text/xml;q=0.9,*/*;q=0.5"})
    with urllib.request.urlopen(req,timeout=15) as r:
        root=ET.fromstring(r.read(2_000_000))
    err=root.find(".//oai:error",NS)
    if err is not None:
        raise RuntimeError(f"OAI {err.get('code','error')}")
    meta=root.find(".//oai:metadata",NS)
    if meta is None:raise RuntimeError("OAI sin metadata")
    return meta

def vals(meta,tag):
    return [re.sub(r"\s+"," ",html.unescape((x.text or ""))).strip()
            for x in meta.findall(f".//dc:{tag}",NS) if (x.text or "").strip()]

def first(meta,*tags):
    for t in tags:
        v=vals(meta,t)
        if v:return v[0]
    return ""

def year_of(values):
    for s in values:
        m=re.search(r"\b(?:18|19|20)\d{2}\b",s or "")
        if m:return m.group(0)
    return ""

def doi_of(values):
    for s in values:
        m=re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",s,flags=re.I)
        if m:return m.group(0).rstrip(".,;)")
    return ""

def choose_access(identifiers):
    # Preferir enlace directo de archivo; si no existe, conservar primera URL pública.
    urls=[x for x in identifiers if x.lower().startswith(("http://","https://"))]
    for u in urls:
        if u.lower().split("?",1)[0].endswith(".pdf"):return u
    return urls[0] if urls else ""

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    pending=[r for r in rows if r.get("source_type")=="nep_report" and handle_of(r) and not (r.get("title") or "").strip()]
    attempted=enriched=failed=0
    for r in pending[:LIMIT]:
        attempted+=1;h=handle_of(r)
        try:
            meta=fetch_record(h)
            titles=vals(meta,"title");creators=vals(meta,"creator")
            if not titles:raise RuntimeError("OAI sin título")
            identifiers=vals(meta,"identifier");dates=vals(meta,"date")
            r["source_item_id"]=h
            r["title"]=titles[0]
            r["authors"]="; ".join(dict.fromkeys(creators))
            r["summary"]=first(meta,"description")
            r["language"]=first(meta,"language")
            r["doi"]=doi_of(identifiers)
            r["access_url"]=choose_access(identifiers)
            r["published_at"]=dates[0] if dates else ""
            r["publication_year"]=year_of(dates)
            r["venue"]=first(meta,"publisher","source")
            r["content_type"]="paper";r["source_name"]="RePEc OAI-PMH"
            r["status"]="METADATOS_OBTENIDOS"
            r["notes"]=((r.get("notes") or "")+" | Metadatos obtenidos por OAI-PMH oficial de RePEc; OA aún por verificar.").strip(" |")
            enriched+=1
        except Exception as e:
            r["notes"]=((r.get("notes") or "")+f" | RePEc OAI pendiente: {type(e).__name__}: {e}").strip(" |")
            failed+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"RePEc OAI: intentados={attempted}; enriquecidos={enriched}; pendientes/error={failed}; backlog={max(0,len(pending)-attempted)}")

if __name__=="__main__":main()
