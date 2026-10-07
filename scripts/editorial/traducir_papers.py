#!/usr/bin/env python3
"""Traduce título y abstract EN→ES con Argos Translate antes de preparar papers.

No resume ni interpreta. Conserva autores literalmente. Falla cerrado si un paper
en inglés carece de abstract, autores o traducción disponible.
"""
from __future__ import annotations

import csv
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = Path(os.getenv("CLEP_CANDIDATES_PATH", ROOT / "data/editorial/candidatos.csv"))

TRANSLATION_FIELDS = (
    "title_original", "title_es", "summary_es", "source_summary_es",
    "translation_status", "translation_method", "translation_engine",
    "translation_engine_version", "source_language", "target_language",
    "translation_disclosure",
)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _translator():
    try:
        import argostranslate.translate as translate
        import argostranslate
    except ImportError as exc:
        raise RuntimeError("ARGOS_NOT_INSTALLED") from exc
    installed = translate.get_installed_languages()
    source = next((lang for lang in installed if lang.code == "en"), None)
    target = next((lang for lang in installed if lang.code == "es"), None)
    if not source or not target:
        raise RuntimeError("ARGOS_EN_ES_MODEL_MISSING")
    translation = source.get_translation(target)
    version = clean(getattr(argostranslate, "__version__", "")) or "installed"
    return translation.translate, version


def translate_rows(rows, translate_fn, engine_version="installed"):
    changed = 0
    for row in rows:
        if clean(row.get("content_type")).lower() != "paper":
            continue
        language = clean(row.get("source_language") or row.get("language")).lower()
        if language not in {"en", "eng", "english", "inglés", "ingles"}:
            continue
        title = clean(row.get("title_original") or row.get("title"))
        authors = clean(row.get("authors"))
        abstract = clean(row.get("source_summary") or row.get("summary") or row.get("abstract") or row.get("description"))
        if not title:
            raise RuntimeError(f"PAPER_TITLE_MISSING:{row.get('candidate_id','')}")
        if not authors:
            raise RuntimeError(f"PAPER_AUTHORS_MISSING:{row.get('candidate_id','')}")
        if not abstract:
            raise RuntimeError(f"PAPER_ABSTRACT_MISSING:{row.get('candidate_id','')}")
        title_es = clean(row.get("title_es")) or clean(translate_fn(title))
        summary_es = clean(row.get("source_summary_es") or row.get("summary_es")) or clean(translate_fn(abstract))
        if not title_es or not summary_es:
            raise RuntimeError(f"PAPER_TRANSLATION_EMPTY:{row.get('candidate_id','')}")
        row["title_original"] = title
        row["title_es"] = title_es
        # meta_for currently consumes title; preserve both without touching author names.
        row["title"] = f"{title} — ES: {title_es}"
        row["summary_es"] = summary_es
        row["source_summary_es"] = summary_es
        row["source_language"] = "en"
        row["target_language"] = "es"
        row["translation_status"] = "VERIFIED"
        row["translation_method"] = "machine_translation"
        row["translation_engine"] = "argos-translate"
        row["translation_engine_version"] = engine_version
        row["translation_disclosure"] = "ES · Traducción automática del abstract original"
        changed += 1
    return changed


def main():
    if not CANDIDATES.exists():
        raise SystemExit(f"no existe {CANDIDATES}")
    with CANDIDATES.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    for field in TRANSLATION_FIELDS:
        if field not in fields:
            fields.append(field)
    translate_fn, version = _translator()
    changed = translate_rows(rows, translate_fn, version)
    if changed:
        tmp = CANDIDATES.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(CANDIDATES)
    print(f"paper translations updated: {changed}")


if __name__ == "__main__":
    main()
