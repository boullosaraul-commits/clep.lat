#!/usr/bin/env python3
"""Ficha automática mínima CLEP, sin IA generativa."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TPL=json.loads((ROOT/"data/editorial/plantillas.json").read_text(encoding="utf-8"))["paper_abierto"]

def ficha_paper(meta):
    missing=[k for k in TPL["campos_obligatorios"] if not str(meta.get(k,"")).strip()]
    if TPL["oa_obligatorio"] and meta.get("oa_status")!="VERIFICADO":
        missing.append("oa_status=VERIFICADO")
    if missing: raise ValueError("Ficha incompleta: "+", ".join(missing))
    tail=" · ".join(x for x in (str(meta.get("venue","")).strip(),str(meta.get("year","")).strip()) if x)
    authors_line=str(meta["authors"]).strip()+((" · "+tail) if tail else "")
    return TPL["plantilla"].format(title=str(meta["title"]).strip(),authors_line=authors_line,
        summary=str(meta["summary"]).strip(),translation_block=((str(meta.get("translation_label","")).strip()+"\n"+str(meta.get("summary_es","")).strip()+"\n\n") if str(meta.get("summary_es","")).strip() else ""),access_url=str(meta["access_url"]).strip(),
        doi_display=str(meta.get("doi","")).strip() or "Sin DOI identificado")
