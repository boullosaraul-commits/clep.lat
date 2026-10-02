#!/usr/bin/env python3
"""Traduce abstracts a español con Argos Translate (OpenNMT), sin LLM."""
import csv
from pathlib import Path
import argostranslate.package, argostranslate.translate

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
TARGET="es"

def norm(code):
    c=(code or "").strip().lower().replace("_","-")
    aliases={"eng":"en","spa":"es","por":"pt","fra":"fr","fre":"fr","deu":"de","ger":"de","ita":"it"}
    return aliases.get(c,c.split("-")[0])

def install_pair(src):
    argostranslate.package.update_package_index()
    packs=argostranslate.package.get_available_packages()
    pkg=next((p for p in packs if p.from_code==src and p.to_code==TARGET),None)
    if not pkg: return False
    argostranslate.package.install_from_path(pkg.download()); return True

def main():
    with P.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    installed=set(); translated=0; skipped=0
    # candidate CSV deliberately remains bibliographic; translation is appended to notes
    # until its own schema columns are introduced in a migration.
    for r in rows:
        abstract=(r.get("summary") or "").strip(); src=norm(r.get("language"))
        if not abstract or not src or src=="es": skipped+=1; continue
        if (r.get("translation_status") or "")=="AUTOMATICA" and (r.get("summary_es") or "").strip(): continue
        if src not in installed:
            try:
                if not install_pair(src): skipped+=1; continue
                installed.add(src)
            except Exception:
                skipped+=1; continue
        try:
            es=argostranslate.translate.translate(abstract,src,TARGET).strip()
        except Exception:
            skipped+=1; continue
        if not es: skipped+=1; continue
        r["summary_es"]=es
        r["translation_engine"]=f"argos:{src}->es"
        r["translation_status"]="AUTOMATICA"
        translated+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(f"Abstracts traducidos: {translated}")
    print(f"Omitidos/no soportados: {skipped}")

if __name__=="__main__": main()
