#!/usr/bin/env python3
"""Descubre novedades académicas no monográficas para CLEP.

Fuentes:
- Crossref REST: descubrimiento bibliográfico reciente por tipo.
- OAI-PMH institucional: metadatos Dublin Core de repositorios oficiales.

No usa IA generativa. Crossref no se interpreta como prueba de acceso abierto.
"""
from __future__ import annotations
import csv, hashlib, html, json, os, re, sys, time, urllib.parse, urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"data/editorial/fuentes.json"
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/3.0 (+https://clep.lat)"

CC_RE=re.compile(r"https?://creativecommons\.org/(?:licenses|publicdomain)/",re.I)
POLICY_RE=re.compile(r"\b(policy brief|policy note|briefing paper|nota de política|informe de política)\b",re.I)
THESIS_RE=re.compile(r"\b(thesis|dissertation|tesis|disertación)\b",re.I)
CHAPTER_RE=re.compile(r"\b(chapter|book chapter|cap[ií]tulo)\b",re.I)
ISSUE_RE=re.compile(r"\b(special issue|special number|n[uú]mero especial|dossier)\b",re.I)
EDITION_RE=re.compile(r"\b(2nd|3rd|4th|5th|second|third|fourth|fifth|revised|new edition|edici[oó]n|revisada|ampliada)\b",re.I)
TRANSLATION_RE=re.compile(r"\b(translation|translated|traducci[oó]n|traducido|traducida)\b",re.I)

def clean(x):
    return re.sub(r"\s+"," ",html.unescape(str(x or ""))).strip()

def hkey(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

def cid(source_id,item_id,dedupe):
    return "CAND-"+hashlib.sha256(f"{source_id}|{item_id}|{dedupe}".encode()).hexdigest()[:16].upper()

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return json.load(r)

def get_xml(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return ET.fromstring(r.read(6_000_000))

def first(seq):
    return clean(seq[0]) if isinstance(seq,list) and seq else clean(seq)

def people(items):
    out=[]
    for p in items or []:
        if not isinstance(p,dict):continue
        name=clean(" ".join(x for x in [p.get("given"),p.get("family")] if x))
        if name:out.append(name)
    return "; ".join(dict.fromkeys(out))

def crossref_date(item):
    for key in ("published-online","published-print","published","issued","created"):
        x=item.get(key)
        if isinstance(x,dict):
            parts=x.get("date-parts")
            if isinstance(parts,list) and parts and parts[0]:
                vals=parts[0]
                y=int(vals[0]);m=int(vals[1]) if len(vals)>1 else 1;d=int(vals[2]) if len(vals)>2 else 1
                try:return date(y,m,d).isoformat(),str(y)
                except ValueError:pass
            dt=x.get("date-time")
            if dt:return clean(dt),clean(dt)[:4]
    return "",""

def crossref_pdf(item):
    for link in item.get("link") or []:
        if not isinstance(link,dict):continue
        u=clean(link.get("URL"));ct=clean(link.get("content-type")).lower()
        if u.startswith("https://") and ("pdf" in ct or urllib.parse.urlparse(u).path.lower().endswith(".pdf")):
            return u
    return ""

def open_license(item):
    for lic in item.get("license") or []:
        if not isinstance(lic,dict):continue
        u=clean(lic.get("URL"))
        if CC_RE.search(u):return u
    return ""

def explicit_revision_or_translation(item):
    title=first(item.get("title"))
    edition=clean(item.get("edition-number"))
    rel=item.get("relation") or {}
    relkeys=" ".join(rel.keys()).lower() if isinstance(rel,dict) else ""
    translation=("translation" in relkeys) or bool(TRANSLATION_RE.search(title))
    revised=bool(edition and edition not in {"1","1st","first"}) or bool(EDITION_RE.search(title))
    return revised or translation,("translation" if translation else "new_edition" if revised else "")

def classify_crossref(item):
    t=clean(item.get("type"))
    title=first(item.get("title"))
    if t=="book-chapter":return "chapter"
    if t in {"report","report-component"}:
        return "policy_brief" if POLICY_RE.search(title) else "report"
    if t=="dissertation":return "thesis"
    if t=="journal-issue":return "special_issue"
    if t in {"book","edited-book","monograph"}:
        ok,kind=explicit_revision_or_translation(item)
        return "edition_translation" if ok else ""
    return ""

def crossref_row(src,item,now):
    kind=classify_crossref(item)
    if not kind:return None
    doi=clean(item.get("DOI")).lower()
    title=first(item.get("title"))
    if not title or not doi:return None
    authors=people(item.get("author")) or people(item.get("editor"))
    publisher=clean(item.get("publisher"))
    if not authors and kind in {"report","policy_brief"}:authors=publisher
    issued,year=crossref_date(item)
    landing=clean(item.get("URL")) or ("https://doi.org/"+doi)
    pdf=crossref_pdf(item);lic=open_license(item)
    access=pdf or landing
    venue=first(item.get("container-title")) or publisher
    notes=[
      "Crossref discovery only",
      "crossref_type="+clean(item.get("type"))
    ]
    if lic:notes.append("open_license_url="+lic)
    if item.get("edition-number"):notes.append("edition_number="+clean(item.get("edition-number")))
    ok,rev=explicit_revision_or_translation(item)
    if rev:notes.append("edition_event="+rev)
    d=hkey("doi:"+doi)
    return {
      "candidate_id":cid(src["id"],doi,d),"source_id":src["id"],"source_type":"crossref_academic",
      "source_item_id":doi,"detected_at":now,"published_at":issued,"title":title,"authors":authors,
      "summary":clean(item.get("abstract")),"source_url":landing,"access_url":access,"doi":doi,
      "language":clean(item.get("language")),"area_clep":src.get("area_clep",""),"flujo_editorial":"novedad",
      "priority":str(src.get("prioridad",30)),"relevance_score":"0","relevance_reasons":"pendiente_reglas",
      "oa_status":"POR_VERIFICAR","dedupe_key":d,"status":"METADATOS_OBTENIDOS","notes":" | ".join(notes),
      "content_type":kind,"source_name":"Crossref","venue":venue,"publication_year":year,
      "access_status":"","rights_status":"LINK_ONLY"
    }

def ingest_crossref(src,rows,fields,seen,dedupes,now):
    days=int(src.get("ventana_dias",21))
    start=(datetime.now(timezone.utc).date()-timedelta(days=days)).isoformat()
    end=datetime.now(timezone.utc).date().isoformat()
    queries=list(src.get("consultas") or [])[:int(os.getenv("ACADEMIC_QUERY_LIMIT","99"))]
    rowcap=min(int(os.getenv("CROSSREF_ROWS",str(src.get("filas_por_consulta",20)))),100)
    allowed=set(src.get("tipos_crossref") or [])
    added=0;seen_doi=set()
    for ctype in allowed:
        for query in queries:
            params={
              "filter":f"from-pub-date:{start},until-pub-date:{end},type:{ctype}",
              "query.bibliographic":query,"rows":str(rowcap),
              "mailto":"contacto@clep.lat"
            }
            url=src["url"]+"?"+urllib.parse.urlencode(params)
            data=None
            for attempt in range(3):
                try:
                    data=get_json(url);break
                except urllib.error.HTTPError as e:
                    if e.code==429 and attempt<2:
                        time.sleep(2*(attempt+1));continue
                    print(f"ERROR {src['id']} {ctype}: {type(e).__name__}: {e}",file=sys.stderr);break
                except Exception as e:
                    print(f"ERROR {src['id']} {ctype}: {type(e).__name__}: {e}",file=sys.stderr);break
            time.sleep(float(os.getenv("CROSSREF_DELAY_SECONDS","1.0")))
            if not data:continue
            for item in (((data or {}).get("message") or {}).get("items") or []):
                doi=clean(item.get("DOI")).lower()
                if not doi or doi in seen_doi:continue
                seen_doi.add(doi)
                row=crossref_row(src,item,now)
                if not row:continue
                pair=(row["source_id"],row["source_item_id"])
                if pair in seen or row["dedupe_key"] in dedupes:continue
                full={k:"" for k in fields};full.update({k:v for k,v in row.items() if k in full})
                rows.append(full);seen.add(pair);dedupes.add(row["dedupe_key"]);added+=1
    print(f"Crossref novedades: nuevos={added}; DOIs examinados={len(seen_doi)}")
    return added

OAI="http://www.openarchives.org/OAI/2.0/"
DC="http://purl.org/dc/elements/1.1/"

def vals(dc,name):
    return [clean(x.text) for x in dc.findall(f"{{{DC}}}{name}") if clean(x.text)]

def classify_oai(types,title,default_kind):
    blob=" ".join(types+[title])
    if POLICY_RE.search(blob):return "policy_brief"
    if THESIS_RE.search(blob):return "thesis"
    if CHAPTER_RE.search(blob):return "chapter"
    if ISSUE_RE.search(blob):return "special_issue"
    if TRANSLATION_RE.search(blob) or EDITION_RE.search(blob):return "edition_translation"
    return default_kind or "report"

def oai_page(src,token=""):
    if token:
        params={"verb":"ListRecords","resumptionToken":token}
    else:
        start=(datetime.now(timezone.utc).date()-timedelta(days=int(src.get("ventana_dias",21)))).isoformat()
        params={"verb":"ListRecords","metadataPrefix":"oai_dc","from":start}
    return get_xml(src["url"]+"?"+urllib.parse.urlencode(params))

def ingest_oai(src,rows,fields,seen,dedupes,now):
    added=0;token="";pages=0
    max_records=int(os.getenv("ACADEMIC_OAI_MAX_RECORDS","200"))
    max_pages=min(int(src.get("max_paginas",3)),10)
    while pages<max_pages:
        try:root=oai_page(src,token)
        except Exception as e:
            print(f"ERROR {src['id']}: {type(e).__name__}: {e}",file=sys.stderr);break
        pages+=1
        for rec in root.findall(f".//{{{OAI}}}record"):
            if added>=max_records:break
            hdr=rec.find(f"{{{OAI}}}header")
            dc=rec.find(f".//{{http://www.openarchives.org/OAI/2.0/oai_dc/}}dc")
            if hdr is None or dc is None:continue
            item_id=clean(hdr.findtext(f"{{{OAI}}}identifier"))
            title=first(vals(dc,"title"))
            if not item_id or not title:continue
            ids=vals(dc,"identifier")
            https=[u for u in ids if u.startswith("https://")]
            http=[u for u in ids if u.startswith("http://")]
            access=(https or http or [""])[0]
            if not access:continue
            kind=classify_oai(vals(dc,"type"),title,src.get("tipo_por_defecto","report"))
            authors="; ".join(dict.fromkeys(vals(dc,"creator")))
            pub=first(vals(dc,"date"))
            ym=re.search(r"\b(?:19|20)\d{2}\b",pub) if pub else None
            year=ym.group(0) if ym else ""
            desc=first(vals(dc,"description"));rights=" ".join(vals(dc,"rights"))
            explicit_oa=bool(CC_RE.search(rights) or re.search(r"\b(open access|acceso abierto)\b",rights,re.I))
            d=hkey("url:"+access)
            pair=(src["id"],item_id)
            if pair in seen or d in dedupes:continue
            row={k:"" for k in fields}
            row.update({
              "candidate_id":cid(src["id"],item_id,d),"source_id":src["id"],"source_type":"academic_oai",
              "source_item_id":item_id,"detected_at":now,"published_at":pub,"title":title,"authors":authors,
              "summary":desc,"source_url":access,"access_url":access,"language":first(vals(dc,"language")),
              "area_clep":src.get("area_clep",""),"flujo_editorial":"novedad","priority":str(src.get("prioridad",25)),
              "relevance_score":"0","relevance_reasons":"pendiente_reglas",
              "oa_status":"VERIFICADO_FUENTE" if explicit_oa else "POR_VERIFICAR","dedupe_key":d,
              "status":"METADATOS_OBTENIDOS",
              "notes":"OAI-PMH institucional"+(" | OA explícito en dc:rights" if explicit_oa else " | derechos OA no inferidos"),
              "content_type":kind,"source_name":src.get("nombre",""),"venue":first(vals(dc,"publisher") or vals(dc,"source")),
              "publication_year":year,"access_status":"OFFICIAL_SOURCE_VERIFIED","rights_status":"LINK_ONLY"
            })
            rows.append(row);seen.add(pair);dedupes.add(d);added+=1
        if added>=max_records:break
        rt=root.find(f".//{{{OAI}}}resumptionToken")
        token=clean(rt.text if rt is not None else "")
        if not token:break
    print(f"OAI {src['id']}: nuevos={added}; páginas={pages}")
    return added

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    seen={(r.get("source_id",""),r.get("source_item_id","")) for r in rows}
    dedupes={r.get("dedupe_key") for r in rows if r.get("dedupe_key")}
    now=datetime.now(timezone.utc).isoformat(timespec="seconds");total=0
    for src in cfg.get("fuentes",[]):
        if not src.get("habilitada"):continue
        if src.get("tipo")=="crossref_academic":
            total+=ingest_crossref(src,rows,fields,seen,dedupes,now)
        elif src.get("tipo")=="academic_oai":
            total+=ingest_oai(src,rows,fields,seen,dedupes,now)
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Novedades académicas no monográficas: total nuevas={total}")

if __name__=="__main__":main()
