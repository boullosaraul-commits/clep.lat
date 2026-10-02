#!/usr/bin/env python3
"""Verifica acceso público y separa acceso de evidencia OA.

PUBLIC_ACCESS_VERIFIED significa sólo que el recurso es accesible sin
autenticación. OA sólo se marca automáticamente cuando la procedencia también
es una fuente académica que declara/distribuye ese acceso (p.ej. RePEc/ReDIF,
DOAB). En ningún caso se infieren derechos de traducción o republicación.
"""
import csv, urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/2.0 (+https://clep.lat)"
LEGIT_SOURCE_TYPES={"nep_report","doab_rest","doab_oai"}
LEGIT_SOURCE_IDS={"doab-economics"}

def verify_public_pdf(url):
    if not url or urlparse(url).scheme!="https":return False,"",""
    for method in ("HEAD","GET"):
        try:
            headers={"User-Agent":UA}
            if method=="GET":headers["Range"]="bytes=0-1023"
            req=urllib.request.Request(url,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=25) as r:
                final=r.geturl();ct=(r.headers.get("Content-Type") or "").lower()
                ok=(urlparse(final).scheme=="https" and ("application/pdf" in ct or urlparse(final).path.lower().endswith(".pdf")))
                if ok:return True,final,ct
        except Exception:pass
    return False,"",""

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    access_yes=oa_yes=0
    for r in rows:
        if r.get("content_type") and r.get("content_type") not in {"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}:continue
        if not r.get("title") or not r.get("authors"):continue
        ok,final,_=verify_public_pdf((r.get("access_url") or "").strip())
        if not ok:continue
        r["access_url"]=final;r["access_status"]="PUBLIC_ACCESS_VERIFIED";r["rights_status"]="LINK_ONLY";access_yes+=1
        explicit_open_license="open_license_url=" in (r.get("notes") or "")
        legitimate=(r.get("source_type") in LEGIT_SOURCE_TYPES or r.get("source_id") in LEGIT_SOURCE_IDS
                    or (r.get("source_type")=="crossref_academic" and explicit_open_license)
                    or (r.get("source_type")=="academic_oai" and r.get("oa_status")=="VERIFICADO_FUENTE"))
        if legitimate:
            r["oa_status"]="VERIFICADO_FUENTE";r["status"]="OA_VERIFICADO";oa_yes+=1
            r["notes"]=((r.get("notes") or "")+" | PDF público verificado; OA respaldado por procedencia académica; derechos de reproducción no inferidos.").strip(" |")
        else:
            r["notes"]=((r.get("notes") or "")+" | PDF público verificado; OA/licencia no inferidos automáticamente.").strip(" |")
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Acceso público PDF verificado: {access_yes}; OA con evidencia de fuente: {oa_yes}")

if __name__=="__main__":main()
