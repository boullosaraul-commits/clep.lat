#!/usr/bin/env python3
"""Ingesta determinista de libros OA recientes desde DOAB REST.

DOAB es la fuente de identidad/OA. El script no interpreta contenido ni genera
resúmenes. Recupera metadatos declarados y deja la selección temática a las
reglas editoriales.
"""
import csv, hashlib, json, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/2.0 (+https://clep.lat)"

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=45) as r:return json.loads(r.read().decode("utf-8","replace"))

def metadata(item):
    out={}
    raw=item.get("metadata") or []
    if isinstance(raw,dict):
        for k,v in raw.items():
            vals=v if isinstance(v,list) else [v]
            out[k]=[str(x.get("value") if isinstance(x,dict) else x) for x in vals]
    else:
        for x in raw:
            if not isinstance(x,dict):continue
            k=x.get("key") or x.get("name");v=x.get("value")
            if k and v is not None:out.setdefault(k,[]).append(str(v))
    return out

def first(md,*keys):
    for k in keys:
        vals=md.get(k) or []
        if vals:return vals[0].strip()
    return ""

def allv(md,*keys):
    out=[]
    for k in keys:out.extend(md.get(k) or [])
    return [x.strip() for x in out if x and x.strip()]

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    existing={r.get("dedupe_key") for r in rows if r.get("dedupe_key")}
    q='dc.date.accessioned_dt:[NOW-7DAY/DAY TO NOW]'
    url="https://directory.doabooks.org/rest/search?"+urllib.parse.urlencode(
        {"query":q,"expand":"metadata,bitstreams","sort":"dc.date.accessioned_dt","limit":"100"})
    data=get_json(url)
    items=data if isinstance(data,list) else (data.get("items") or data.get("results") or [])
    now=datetime.now(timezone.utc).isoformat(timespec="seconds");added=0
    for item in items:
        if not isinstance(item,dict):continue
        md=metadata(item)
        title=first(md,"dc.title")
        authors=allv(md,"dc.contributor.author","dc.creator")
        year=first(md,"dc.date.issued","dc.date.created")
        ym=re.search(r"\b(?:18|19|20)\d{2}\b",year);year=ym.group(0) if ym else ""
        handle=str(item.get("handle") or first(md,"dc.identifier.uri") or item.get("uuid") or "")
        if not title or not handle:continue
        key=hashlib.sha256(("doab:"+handle).encode()).hexdigest()[:24]
        if key in existing:continue
        doi=first(md,"dc.identifier.doi")
        doi=doi.replace("https://doi.org/","").replace("http://doi.org/","")
        lang=first(md,"dc.language","dc.language.iso")
        abstract=first(md,"dc.description.abstract","dc.description")
        license_text=first(md,"dc.rights","dc.rights.uri","dc.rights.license")
        landing=handle if handle.startswith("http") else "https://directory.doabooks.org/handle/"+handle
        row={k:"" for k in fields}
        row.update({
          "candidate_id":"CAND-"+hashlib.sha256(("doab|"+handle).encode()).hexdigest()[:16].upper(),
          "source_id":"doab-economics","source_type":"doab_rest","source_item_id":handle,
          "detected_at":now,"published_at":year,"title":title,"authors":"; ".join(dict.fromkeys(authors)),
          "summary":abstract,"source_url":landing,"access_url":landing,"doi":doi,"language":lang,
          "area_clep":"libros-economia","flujo_editorial":"novedad","priority":"20",
          "relevance_score":"0","relevance_reasons":"pendiente_reglas","oa_status":"VERIFICADO_FUENTE",
          "access_status":"OFFICIAL_SOURCE_VERIFIED","rights_status":"LINK_ONLY","dedupe_key":key,
          "status":"METADATOS_OBTENIDOS","content_type":"book","source_name":"Directory of Open Access Books (DOAB)",
          "publication_year":year,"notes":"Metadatos DOAB; libro OA indexado por DOAB. Licencia declarada: "+license_text
        })
        rows.append(row);existing.add(key);added+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"DOAB: libros nuevos={added}")

if __name__=="__main__":main()
