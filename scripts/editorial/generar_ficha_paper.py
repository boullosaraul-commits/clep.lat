#!/usr/bin/env python3
"""Construye la ficha CLEP de un paper a partir de metadatos ya verificados.

No inventa ni resume contenido. La pregunta y la traducción deben existir
antes de que la ficha pueda pasar a PROGRAMADO.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TPL=json.loads((ROOT/"data/editorial/plantillas.json").read_text(encoding="utf-8"))["paper_abierto"]

def ficha_paper(meta):
    missing=[k for k in TPL["campos_obligatorios"] if not str(meta.get(k,"")).strip()]
    if TPL["oa_obligatorio"] and meta.get("oa_status")!="VERIFICADO":
        missing.append("oa_status=VERIFICADO")
    if not str(meta.get("question","")).strip(): missing.append("question")
    if not str(meta.get("summary_es","")).strip(): missing.append("summary_es")
    if missing:
        raise ValueError("Ficha incompleta: "+", ".join(missing))
    journal=str(meta.get("venue","")).strip()
    year=str(meta.get("year","")).strip()
    tail=" · ".join(x for x in (journal,year) if x)
    authors_line=str(meta["authors"]).strip()+((" · "+tail) if tail else "")
    return TPL["plantilla"].format(
        title=str(meta["title"]).strip(),
        authors_line=authors_line,
        question=str(meta["question"]).strip(),
        summary=str(meta["summary"]).strip(),
        translation_label=str(meta.get("translation_label","Traducción automática del abstract original")).strip(),
        summary_es=str(meta["summary_es"]).strip(),
        access_url=str(meta["access_url"]).strip(),
        doi_display=str(meta.get("doi","")).strip() or "Sin DOI identificado"
    )

if __name__=="__main__":
    print("Generador de ficha CLEP cargado correctamente.")
