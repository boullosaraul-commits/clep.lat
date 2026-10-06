#!/usr/bin/env python3
"""Compatibilidad legacy para fichas de paper.

DEPRECATED: la autoridad textual es `renderizar_texto.render_result`.
Este módulo no contiene plantillas ni política editorial propias.
"""
from renderizar_texto import render_result


def ficha_paper(meta):
    if meta.get("oa_status") != "VERIFICADO":
        raise ValueError("Ficha incompleta: oa_status=VERIFICADO")
    data = {
        "title": meta.get("title", ""),
        "authors": meta.get("authors", ""),
        "source_or_series": meta.get("venue") or meta.get("source_or_series") or "Fuente verificada",
        "year": meta.get("year", ""),
        "access_url": meta.get("access_url", ""),
        "source_summary": meta.get("source_summary") or meta.get("summary") or "",
        "source_summary_es": meta.get("source_summary_es") or meta.get("summary_es") or "",
        "source_language": meta.get("source_language") or meta.get("language") or "",
        "target_language": meta.get("target_language") or "es",
        "translation_status": meta.get("translation_status", ""),
        "translation_method": meta.get("translation_method", ""),
        "translation_engine": meta.get("translation_engine", ""),
        "translation_engine_version": meta.get("translation_engine_version", ""),
        "translation_disclosure": meta.get("translation_disclosure") or meta.get("translation_label") or "",
    }
    return render_result("paper", data).post_text
