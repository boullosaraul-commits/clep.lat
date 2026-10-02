#!/usr/bin/env python3
"""Enriquece candidatos NEP siguiendo el resolvedor oficial de RePEc.

NEP ya entrega un handle permanente RePEc y, normalmente, una URL d.repec.org.
La ruta principal es seguir ese resolvedor hasta la página bibliográfica real.
Sólo como fallback se construyen rutas IDEAS. No se infiere OA: los enlaces de
texto completo pasan a access_url y otra etapa verifica acceso/derechos.
"""
import csv, html, os, re, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/2.3 (+https://clep.lat)"
LIMIT=int(os.getenv("REPEC_ENRICH_LIMIT","120"))

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta={}; self.links=[]; self.title_text=[]; self.in_title=False
    def handle_starttag(self,tag,attrs):
        a={k.lower():v for k,v in attrs}
        if tag=="meta":
            key=(a.get("name") or a.get("property") or "").lower()
            val=a.get("content")
            if key and val:self.meta.setdefault(key,[]).append(html.unescape(val).strip())
        elif tag=="a":
            href=a.get("href")
            if href:self.links.append(href)
        elif tag=="title": self.in_title=True
    def handle_endtag(self,tag):
        if tag=="title": self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title_text.append(data)

def fetch(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xhtml+xml;q=0.9,*/*;q=0.7"
    })
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read(4_000_000).decode("utf-8","replace"),r.geturl()

def handle_from(value):
    value=(value or "").strip()
    if value.lower().startswith("repec:"):return value
    try:
        u=urllib.parse.parse_qs(urllib.parse.urlparse(value).query).get("u",[""])[0]
        return u if u.lower().startswith("repec:") else ""
    except Exception:return ""

def handle_of(r):
    return handle_from(r.get("source_item_id")) or handle_from(r.get("source_url")) or handle_from(r.get("notes"))

def fallback_urls(handle):
    p=handle.split(":")
    if len(p)<4:return []
    code,series=p[1],p[2]; item=":".join(p[3:])
    q=urllib.parse.quote(item,safe="._-")
    return [f"https://ideas.repec.org/p/{code}/{series}/{q}.html",
            f"https://ideas.repec.org/a/{code}/{series}/{q}.html"]

def first(md,*keys):
    for k in keys:
        vals=md.get(k) or []
        if vals:return vals[0]
    return ""

def year_of(s):
    m=re.search(r"\b(?:18|19|20)\d{2}\b",s or "")
    return m.group(0) if m else ""

def absolute(base,url):
    return urllib.parse.urljoin(base,url) if url else ""

def likely_pdf(page,base):
    pdf=first(page.meta,"citation_pdf_url","eprints.document_url")
    if pdf:return absolute(base,pdf)
    for href in page.links:
        u=absolute(base,href)
        low=u.lower().split("?",1)[0]
        if low.endswith(".pdf"):return u
    return ""

def parse_page(text,url,handle):
    p=Page();p.feed(text);md=p.meta
    title=first(md,"citation_title","dc.title","dcterms.title","og:title")
    authors=md.get("citation_author") or md.get("dc.creator") or md.get("dcterms.creator") or []
    # IDEAS pages sometimes expose Dublin Core as DC.Title/DC.Creator; parser lowercases names.
    if not title:
        raw=" ".join(p.title_text).strip()
        raw=re.sub(r"\s*-\s*IDEAS/RePEc\s*$","",raw,flags=re.I)
        if raw and raw.lower() not in {"ideas/repec","ideas"}: title=html.unescape(raw)
    if not title:return None
    bodylow=text.lower()
    # A redirect is accepted only if the destination or page still identifies the requested handle.
    # d.repec.org can legitimately redirect to a publisher page that omits the handle, so exact
    # handle matching is enforced only on ideas.repec.org pages.
    host=urllib.parse.urlparse(url).hostname or ""
    if host.endswith("ideas.repec.org") and "repec:" in bodylow and handle.lower() not in bodylow:
        return None
    abstract=first(md,"citation_abstract","dc.description","dcterms.description","description","og:description")
    doi=first(md,"citation_doi","dc.identifier","dcterms.identifier")
    m=re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",doi or "",flags=re.I)
    doi=m.group(0).rstrip(".,;)") if m else ""
    date=first(md,"citation_publication_date","citation_date","dc.date","dcterms.date","article:published_time")
    venue=first(md,"citation_journal_title","citation_conference_title","citation_technical_report_institution")
    return {
        "title":re.sub(r"\s+"," ",title).strip(),
        "authors":"; ".join(dict.fromkeys(re.sub(r"\s+"," ",x).strip() for x in authors if x.strip())),
        "summary":re.sub(r"\s+"," ",html.unescape(abstract or "")).strip(),
        "access_url":likely_pdf(p,url),"doi":doi,"published_at":date,
        "year":year_of(date),"venue":venue,"ideas_url":url
    }

def candidate_urls(r,h):
    out=[]
    src=(r.get("source_url") or "").strip()
    if src.startswith("https://d.repec.org/"):out.append(src)
    # Canonical NEP resolver if the legacy row no longer retained one.
    if not out:
        out.append("https://d.repec.org/n?"+urllib.parse.urlencode({"u":h}))
    out.extend(fallback_urls(h))
    seen=set();return [u for u in out if not (u in seen or seen.add(u))]

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    enriched=failed=attempted=0
    pending=[r for r in rows if r.get("source_type")=="nep_report" and handle_of(r) and not (r.get("title") or "").strip()]
    for r in pending[:LIMIT]:
        attempted+=1;h=handle_of(r);hit=None;last=[]
        for u in candidate_urls(r,h):
            try:
                text,final=fetch(u); hit=parse_page(text,final,h)
                if hit:break
                last.append("sin metadatos")
            except urllib.error.HTTPError as e:last.append(f"HTTP {e.code}")
            except Exception as e:last.append(type(e).__name__)
        if not hit:
            r["notes"]=((r.get("notes") or "")+" | RePEc pendiente: "+",".join(last[-3:])).strip(" |")
            failed+=1;continue
        r["source_item_id"]=h
        r["title"]=hit["title"];r["authors"]=hit["authors"];r["summary"]=hit["summary"]
        r["access_url"]=hit["access_url"];r["doi"]=hit["doi"];r["published_at"]=hit["published_at"] or hit["year"]
        r["venue"]=hit["venue"];r["publication_year"]=hit["year"];r["content_type"]="paper"
        r["source_name"]="RePEc";r["source_url"]=hit["ideas_url"]
        r["status"]="METADATOS_OBTENIDOS"
        r["notes"]=((r.get("notes") or "")+" | Metadatos bibliográficos resueltos vía RePEc; OA aún por verificar.").strip(" |")
        enriched+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"RePEc: intentados={attempted}; enriquecidos={enriched}; pendientes/error={failed}; backlog={max(0,len(pending)-attempted)}")

if __name__=="__main__":main()
