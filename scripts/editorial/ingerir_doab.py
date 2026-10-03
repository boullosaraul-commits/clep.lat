#!/usr/bin/env python3
"""Ingesta determinista de libros OA recientes desde DOAB.

Ruta principal: OAI-PMH oficial, que DOAB documenta para cosecha de metadatos.
Se usa oai_dc para evitar depender del endpoint REST que desde GitHub Actions
puede responder 403. No se interpreta el contenido ni se genera texto.
"""
import csv, hashlib, re, urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/2.1 (+https://clep.lat)"
BASE="https://directory.doabooks.org/oai/request"
NS={
 "oai":"http://www.openarchives.org/OAI/2.0/",
 "dc":"http://purl.org/dc/elements/1.1/",
}

def get_xml(params):
    url=BASE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml;q=0.9,*/*;q=0.5"})
    with urllib.request.urlopen(req,timeout=45) as r:
        return ET.fromstring(r.read(8_000_000))

def vals(meta,tag):
    return [re.sub(r"\s+"," ",(x.text or "")).strip() for x in meta.findall(f".//dc:{tag}",NS) if (x.text or "").strip()]

def first(meta,*tags):
    for t in tags:
        v=vals(meta,t)
        if v:return v[0]
    return ""

def handle_from_identifier(identifier):
    p="oai:doabooks.org:"
    return identifier[len(p):] if identifier.startswith(p) else identifier

def doi_from(values):
    for s in values:
        m=re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",s,flags=re.I)
        if m:return m.group(0).rstrip(".,;)")
    return ""

def landing(handle,identifiers):
    for s in identifiers:
        if "directory.doabooks.org/handle/" in s:return s
    return "https://directory.doabooks.org/handle/"+handle

def direct_access(identifiers):
    https=[s.strip() for s in identifiers if s.strip().startswith("https://")]
    for s in https:
        p=urllib.parse.urlparse(s).path.lower()
        if p.endswith(".pdf"):return s
    for s in https:
        p=urllib.parse.urlparse(s).path.lower()
        if p.endswith(".epub"):return s
    return ""

def license_url(rights,identifiers):
    for s in list(rights)+list(identifiers):
        m=re.search(r"https?://creativecommons\.org/(?:licenses|publicdomain)/[^\s<>]+",s,re.I)
        if m:return m.group(0).rstrip(".,;)")
    return ""

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    existing={r.get("dedupe_key") for r in rows if r.get("dedupe_key")}
    since=(datetime.now(timezone.utc)-timedelta(days=14)).date().isoformat()
    params={"verb":"ListRecords","metadataPrefix":"oai_dc","from":since}
    try:
        root=get_xml(params)
    except Exception as e:
        print(f"DOAB OAI no disponible en esta ejecución: {type(e).__name__}: {e}")
        return
    now=datetime.now(timezone.utc).isoformat(timespec="seconds");added=0;seen_records=0
    # Limitamos páginas para mantener el job acotado; resumptionToken permite continuar.
    for page in range(3):
        err=root.find(".//oai:error",NS)
        if err is not None:
            print(f"DOAB OAI: {err.get('code','error')}: {(err.text or '').strip()}")
            break
        for rec in root.findall(".//oai:record",NS):
            header=rec.find("oai:header",NS)
            meta=rec.find("oai:metadata",NS)
            if header is None or meta is None or header.get("status")=="deleted":continue
            identifier=(header.findtext("oai:identifier",default="",namespaces=NS) or "").strip()
            handle=handle_from_identifier(identifier)
            title=first(meta,"title")
            creators=vals(meta,"creator")
            if not title or not handle:continue
            seen_records+=1
            key=hashlib.sha256(("doab:"+handle).encode()).hexdigest()[:24]
            if key in existing:continue
            identifiers=vals(meta,"identifier")
            doi=doi_from(identifiers)
            dates=vals(meta,"date")
            year="";published=""
            for d in dates:
                m=re.search(r"\b(?:18|19|20)\d{2}\b",d)
                if m and not year:year=m.group(0)
                if re.match(r"^(?:18|19|20)\d{2}-\d{2}-\d{2}",d) and not published:
                    published=d[:10]
            if not published:published=year
            languages=vals(meta,"language")
            descs=vals(meta,"description")
            rights=vals(meta,"rights")
            subjects=vals(meta,"subject")
            landing_url=landing(handle,identifiers)
            direct=direct_access(identifiers)
            url=direct or landing_url
            lic=license_url(rights,identifiers)
            row={k:"" for k in fields}
            row.update({
              "candidate_id":"CAND-"+hashlib.sha256(("doab|"+handle).encode()).hexdigest()[:16].upper(),
              "source_id":"doab-economics","source_type":"doab_oai","source_item_id":handle,
              "detected_at":now,"published_at":published,"title":title,
              "authors":"; ".join(dict.fromkeys(creators)),
              "summary":descs[0] if descs else "","source_url":landing_url,"access_url":url,
              "doi":doi,"language":languages[0] if languages else "",
              "area_clep":"libros-economia","flujo_editorial":"novedad","priority":"20",
              "relevance_score":"0","relevance_reasons":"pendiente_reglas",
              "oa_status":"VERIFICADO_FUENTE","access_status":"SOURCE_OA_UNCHECKED",
              "rights_status":"LINK_ONLY","dedupe_key":key,"status":"METADATOS_OBTENIDOS",
              "content_type":"book","source_name":"Directory of Open Access Books (DOAB)",
              "publication_year":year,
              "notes":"Metadatos DOAB vía OAI-PMH; registro de libro OA"
                      +(" | license_url="+lic if lic else "")
                      +(" | direct_access="+direct if direct else "")
                      +" | Derechos declarados: "+"; ".join(rights[:3])
                      +" | Temas: "+"; ".join(subjects[:5])
            })
            rows.append(row);existing.add(key);added+=1
        token=(root.findtext(".//oai:resumptionToken",default="",namespaces=NS) or "").strip()
        if not token:break
        try:root=get_xml({"verb":"ListRecords","resumptionToken":token})
        except Exception as e:
            print(f"DOAB OAI continuación detenida: {type(e).__name__}: {e}");break
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"DOAB OAI: registros vistos={seen_records}; libros nuevos={added}")

if __name__=="__main__":main()
