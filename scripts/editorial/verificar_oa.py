#!/usr/bin/env python3
"""Verifica acceso público y separa acceso vivo de evidencia OA.

La fuente puede acreditar OA, pero la elegibilidad exige además que el enlace
concreto responda. Las verificaciones HTTP son concurrentes y acotadas para que
un backlog grande no bloquee el job diario.
"""
import csv,os,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/3.0 (+https://clep.lat)"
LEGIT_SOURCE_TYPES={"nep_report","doab_rest","doab_oai"}
LEGIT_SOURCE_IDS={"doab-economics"}
ACADEMIC={"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}

def verify_public_url(url,pdf_required=False):
    if not url or urlparse(url).scheme!="https":return False,"",""
    timeout=float(os.getenv("OA_HTTP_TIMEOUT","12"))
    for method in ("HEAD","GET"):
        try:
            headers={"User-Agent":UA,"Accept":"text/html,application/pdf,*/*;q=0.5"}
            if method=="GET":headers["Range"]="bytes=0-2047"
            req=urllib.request.Request(url,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=timeout) as r:
                final=r.geturl();ct=(r.headers.get("Content-Type") or "").lower()
                if urlparse(final).scheme!="https":continue
                if pdf_required:
                    ok=("application/pdf" in ct or urlparse(final).path.lower().endswith(".pdf"))
                else:
                    ok=(200<=getattr(r,"status",200)<400)
                if ok:return True,final,ct
        except Exception:pass
    return False,"",""

def needs_check(r):
    kind=r.get("content_type") or ""
    if kind and kind not in ACADEMIC:return None
    if not r.get("title"):return None
    if r.get("access_status") in {"PUBLIC_ACCESS_VERIFIED","VERIFICADO"}:return None
    url=(r.get("access_url") or "").strip()
    if not url:return None
    if kind in {"paper","book","chapter","thesis","edition_translation"} and not r.get("authors"):return None
    pdf_required=False
    if r.get("source_type")=="crossref_academic":
        if not (url.lower().endswith(".pdf") or "pdf" in url.lower()):return None
        pdf_required=True
    return url,pdf_required

def legitimate_oa(r):
    explicit_open_license="open_license_url=" in (r.get("notes") or "")
    return (r.get("source_type") in LEGIT_SOURCE_TYPES
            or r.get("source_id") in LEGIT_SOURCE_IDS
            or (r.get("source_type")=="crossref_academic" and explicit_open_license)
            or (r.get("source_type")=="academic_oai" and r.get("oa_status")=="VERIFICADO_FUENTE"))

def add_note(r,msg):
    notes=r.get("notes") or ""
    if msg not in notes:r["notes"]=(notes+" | "+msg).strip(" |")

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    limit=int(os.getenv("OA_VERIFY_LIMIT","80"));workers=max(1,min(int(os.getenv("OA_VERIFY_WORKERS","8")),16))
    jobs=[]
    for i,r in enumerate(rows):
        spec=needs_check(r)
        if spec:jobs.append((i,*spec))
    selected=jobs[:limit]
    access_yes=oa_yes=failed=0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(verify_public_url,url,pdf):i for i,url,pdf in selected}
        for fut in as_completed(futs):
            i=futs[fut];r=rows[i]
            try:ok,final,_=fut.result()
            except Exception:ok,final=False,""
            if not ok:
                failed+=1
                if r.get("oa_status") in {"VERIFICADO_FUENTE","OA_VERIFICADO"}:
                    r["access_status"]="ACCESS_FAILED"
                    if r.get("status")=="OA_VERIFICADO":r["status"]="METADATOS_OBTENIDOS"
                continue
            r["access_url"]=final;r["access_status"]="PUBLIC_ACCESS_VERIFIED";r["rights_status"]="LINK_ONLY";access_yes+=1
            if legitimate_oa(r):
                r["oa_status"]="VERIFICADO_FUENTE";r["status"]="OA_VERIFICADO";oa_yes+=1
                add_note(r,"Acceso público verificado; OA respaldado por procedencia/licencia; derechos de reproducción no inferidos.")
            else:
                add_note(r,"Acceso público verificado; OA/licencia no inferidos automáticamente.")

    # Filas ya verificadas por HTTP y con evidencia OA conservan el estado fuerte.
    for r in rows:
        if r.get("access_status") in {"PUBLIC_ACCESS_VERIFIED","VERIFICADO"} and legitimate_oa(r):
            if r.get("oa_status") in {"VERIFICADO","VERIFICADO_FUENTE","OA_VERIFICADO"}:
                r["oa_status"]="VERIFICADO_FUENTE";r["status"]="OA_VERIFICADO"

    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Verificación acceso: candidatos={len(jobs)}; intentados={len(selected)}; vivos={access_yes}; fallidos={failed}; OA+acceso={oa_yes}; pendientes={max(0,len(jobs)-len(selected))}")

if __name__=="__main__":main()
