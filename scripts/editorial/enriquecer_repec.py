#!/usr/bin/env python3
"""Enriquece candidatos NEP desde la página bibliográfica IDEAS/RePEc.

Ruta principal para papers:
  RePEc:aaa:series:item -> https://ideas.repec.org/p/aaa/series/item.html

Se leen únicamente metadatos HTML declarados por IDEAS. No se infiere OA:
citation_pdf_url pasa a access_url y la verificación de acceso/OA ocurre después.
Procesa un lote acotado por ejecución para evitar que el backlog heredado
monopolice el workflow.
"""
import csv, html, os, re, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/2.2 (+https://clep.lat)"
LIMIT=int(os.getenv("REPEC_ENRICH_LIMIT","120"))

class Meta(HTMLParser):
    def __init__(self):
        super().__init__();self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag!="meta":return
        a={k.lower():v for k,v in attrs}
        key=(a.get("name") or a.get("property") or "").lower()
        val=a.get("content")
        if key and val:self.meta.setdefault(key,[]).append(html.unescape(val).strip())

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read(3_000_000).decode("utf-8","replace"),r.geturl()

def handle_of(r):
    h=(r.get("source_item_id") or "").strip()
    return h if h.lower().startswith("repec:") else ""

def urls_for(handle):
    p=handle.split(":")
    if len(p)<4:return []
    code,series=p[1],p[2]
    item=":".join(p[3:])
    item=urllib.parse.quote(item,safe="._-")
    # NEP announces research papers overwhelmingly through /p/. /a/ is a
    # conservative fallback for article-series handles.
    return [f"https://ideas.repec.org/p/{code}/{series}/{item}.html",
            f"https://ideas.repec.org/a/{code}/{series}/{item}.html"]

def first(md,*keys):
    for k in keys:
        vals=md.get(k) or []
        if vals:return vals[0]
    return ""

def year_of(s):
    m=re.search(r"\b(?:18|19|20)\d{2}\b",s or "")
    return m.group(0) if m else ""

def parse_page(text,url,handle):
    parser=Meta();parser.feed(text);md=parser.meta
    title=first(md,"citation_title","dc.title","og:title")
    authors=md.get("citation_author") or md.get("dc.creator") or []
    if not title or not authors:return None
    # Require the exact RePEc handle in the page body when present in order to
    # avoid accepting a redirect to an unrelated item.
    if "repec:" in text.lower() and handle.lower() not in text.lower():return None
    abstract=first(md,"citation_abstract","dc.description","description")
    pdf=first(md,"citation_pdf_url")
    doi=first(md,"citation_doi").replace("https://doi.org/","").replace("http://doi.org/","")
    date=first(md,"citation_publication_date","dc.date","article:published_time")
    venue=first(md,"citation_journal_title","citation_conference_title")
    return {"title":title,"authors":"; ".join(dict.fromkeys(x for x in authors if x)),
            "summary":abstract,"access_url":pdf,"doi":doi,"published_at":date,
            "year":year_of(date),"venue":venue,"ideas_url":url}

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    enriched=failed=attempted=0
    pending=[r for r in rows if r.get("source_type")=="nep_report" and handle_of(r) and not (r.get("title") or "").strip()]
    for r in pending[:LIMIT]:
        attempted+=1;h=handle_of(r);hit=None;last=""
        for u in urls_for(h):
            try:
                text,final=fetch(u);hit=parse_page(text,final,h)
                if hit:break
            except urllib.error.HTTPError as e:
                last=f"HTTP {e.code}"
            except Exception as e:
                last=type(e).__name__
        if not hit:
            r["notes"]=((r.get("notes") or "")+f" | IDEAS/RePEc pendiente: {last or 'sin metadatos'}").strip(" |")
            failed+=1;continue
        r["title"]=hit["title"];r["authors"]=hit["authors"];r["summary"]=hit["summary"]
        r["access_url"]=hit["access_url"];r["doi"]=hit["doi"];r["published_at"]=hit["published_at"] or hit["year"]
        r["venue"]=hit["venue"];r["publication_year"]=hit["year"];r["content_type"]="paper"
        r["source_name"]="IDEAS/RePEc";r["source_url"]=hit["ideas_url"]
        r["status"]="METADATOS_OBTENIDOS"
        r["notes"]=((r.get("notes") or "")+" | Metadatos obtenidos de IDEAS/RePEc; OA aún por verificar.").strip(" |")
        enriched+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"RePEc/IDEAS: intentados={attempted}; enriquecidos={enriched}; pendientes/error={failed}; backlog={max(0,len(pending)-attempted)}")

if __name__=="__main__":main()
