#!/usr/bin/env python3
"""Verificación conservadora de acceso abierto para candidatos CLEP.

Sólo marca VERIFICADO cuando la URL candidata responde por HTTPS sin
autenticación y termina en PDF o declara Content-Type application/pdf.
No intenta eludir paywalls ni inferir licencias.
"""
import csv, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
UA="CLEP-editorial/1.3 (+https://clep.lat)"

def verify(url):
    if not url or urlparse(url).scheme!="https": return False,""
    req=urllib.request.Request(url,headers={"User-Agent":UA},method="HEAD")
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            final=r.geturl(); ct=(r.headers.get("Content-Type") or "").lower()
            ok=(urlparse(final).scheme=="https" and ("application/pdf" in ct or urlparse(final).path.lower().endswith(".pdf")))
            return ok,final
    except Exception:
        # Some repositories reject HEAD; use a tiny ranged GET.
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Range":"bytes=0-1023"})
            with urllib.request.urlopen(req,timeout=20) as r:
                final=r.geturl(); ct=(r.headers.get("Content-Type") or "").lower()
                ok=(urlparse(final).scheme=="https" and ("application/pdf" in ct or urlparse(final).path.lower().endswith(".pdf")))
                return ok,final
        except Exception:return False,""

def main():
    with P.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    yes=0
    for r in rows:
        if r.get("oa_status")=="VERIFICADO": continue
        if not r.get("title") or not r.get("authors") or not r.get("summary"): continue
        ok,final=verify((r.get("access_url") or "").strip())
        if ok:
            r["oa_status"]="VERIFICADO"; r["access_url"]=final
            r["status"]="OA_VERIFICADO"; yes+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(f"OA PDF verificado: {yes}")

if __name__=="__main__":main()
