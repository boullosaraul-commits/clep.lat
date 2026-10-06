#!/usr/bin/env python3
"""Preparación editorial atómica CLEP: texto + media + procedencia.

La preparación no decide qué media usar. La autoridad de prioridad es
`resolver_media.py`; `adquirir_media.py` materializa la resolución elegida.
La validación física completa pertenece al Paso 5 (`validar_media.py`).
"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from adquirir_media import (
    MediaAcquisitionError,
    acquire_media,
    is_fallback_acquisition_error,
)
from editorial_rules import check_publishable
from estado_editorial import QUEUE_DERIVED_FIELDS, candidate_fingerprint, policy_fingerprint
from renderizar_texto import render_result
from resolver_media import MediaResolutionError, resolve_media

C = Path(
    os.getenv("CLEP_CANDIDATES_PATH", str(ROOT / "data/editorial/candidatos.csv"))
).resolve()
Q = Path(os.getenv("CLEP_QUEUE_PATH", str(ROOT / "data/editorial/cola.csv"))).resolve()

TEXT_PROVENANCE_FIELDS = (
    "source_summary",
    "source_summary_es",
    "editorial_description",
    "text_template_version",
    "translation_status",
    "translation_method",
    "translation_engine",
    "translation_engine_version",
    "translation_source_language",
    "translation_target_language",
    "translation_disclosure",
)
MEDIA_PROVENANCE_FIELDS = (
    "media_type",
    "media_path",
    "media_source",
    "media_source_url",
    "media_rights_status",
    "media_method",
    "media_resolution_fingerprint",
    "media_content_sha256",
    "media_acquisition_reused",
    "alt_text",
)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def year(row):
    value = clean(row.get("publication_year"))
    if re.fullmatch(r"(?:18|19|20)\d{2}", value):
        return value
    match = re.search(r"\b(?:18|19|20)\d{2}\b", row.get("published_at") or "")
    return match.group(0) if match else ""


def source_name(row):
    return clean(
        row.get("source_name")
        or row.get("official_source")
        or row.get("source_id")
        or row.get("source_type")
        or "Fuente verificada"
    )


def ctype(row):
    return clean(
        row.get("content_type")
        or ("paper" if row.get("source_type") in {"nep_report", "rss"} else "recurso")
    )


def access(row):
    return clean(row.get("access_url") or row.get("source_url"))


def text_context(row):
    """Metadata textual común. No genera ni traduce contenido."""
    return {
        "source_summary": clean(
            row.get("source_summary")
            or row.get("summary")
            or row.get("abstract")
            or row.get("description")
        ),
        "source_summary_es": clean(
            row.get("source_summary_es")
            or row.get("summary_es")
            or row.get("abstract_es")
            or row.get("description_es")
        ),
        "source_language": clean(row.get("source_language") or row.get("language")),
        "target_language": clean(row.get("target_language") or "es"),
        "translation_status": clean(row.get("translation_status")),
        "translation_method": clean(row.get("translation_method")),
        "translation_engine": clean(row.get("translation_engine")),
        "translation_engine_version": clean(row.get("translation_engine_version")),
        "translation_disclosure": clean(
            row.get("translation_disclosure") or row.get("translation_label")
        ),
    }


def meta_for(kind, row):
    url = access(row)
    if kind == "paper":
        return {
            "title": clean(row.get("title")),
            "authors": clean(row.get("authors")),
            "source_or_series": clean(row.get("venue") or source_name(row)),
            "year": year(row),
            "access_url": url,
        }
    if kind == "book":
        return {
            "title": clean(row.get("title")),
            "authors_or_editors": clean(row.get("authors")),
            "year": year(row),
            "access_url": url,
        }
    if kind == "chapter":
        return {
            "title": clean(row.get("title")),
            "authors": clean(row.get("authors")),
            "container_title": clean(row.get("venue") or source_name(row)),
            "year": year(row),
            "access_url": url,
        }
    if kind in {"report", "policy_brief"}:
        return {
            "title": clean(row.get("title")),
            "authors_or_institution": clean(
                row.get("authors") or row.get("venue") or source_name(row)
            ),
            "year": year(row),
            "access_url": url,
        }
    if kind == "special_issue":
        return {
            "title": clean(row.get("title")),
            "journal": clean(row.get("venue") or source_name(row)),
            "year": year(row),
            "access_url": url,
        }
    if kind == "thesis":
        return {
            "title": clean(row.get("title")),
            "authors": clean(row.get("authors")),
            "institution": clean(row.get("venue") or source_name(row)),
            "year": year(row),
            "access_url": url,
        }
    if kind == "edition_translation":
        notes = row.get("notes") or ""
        edition_match = re.search(r"edition_number=([^|]+)", notes)
        note = (
            "traducción"
            if "edition_event=translation" in notes
            else clean(edition_match.group(1) if edition_match else "nueva edición")
        )
        return {
            "title": clean(row.get("title")),
            "authors_or_editors": clean(row.get("authors")),
            "edition_note": note,
            "year": year(row),
            "access_url": url,
        }
    if kind == "dataset_grafica":
        return {
            "indicator_or_dataset": clean(
                row.get("indicator_or_dataset") or row.get("title")
            ),
            "geography": clean(row.get("geography")),
            "reference_period": clean(row.get("reference_period")),
            "value_or_change": clean(row.get("value_or_change")),
            "official_source": source_name(row),
            "access_url": url,
        }
    if kind == "convocatoria_evento":
        return {
            "title": clean(row.get("title")),
            "organizer": clean(row.get("organizer") or source_name(row)),
            "date_or_deadline": clean(row.get("date_or_deadline")),
            "access_url": url,
            "date_label": "Fecha",
        }
    if kind == "video":
        return {
            "title": clean(row.get("title")),
            "speaker_or_organization": clean(
                row.get("speaker_or_organization")
                or row.get("authors")
                or source_name(row)
            ),
            "access_url": url,
        }
    if kind == "recurso":
        return {
            "title": clean(row.get("title")),
            "source": source_name(row),
            "access_url": url,
        }
    raise ValueError(f"tipo no soportado: {kind}")


def eligible(row, kind):
    # La preparación nunca sustituye a la decisión de pertinencia.
    academic = {
        "paper",
        "book",
        "chapter",
        "report",
        "policy_brief",
        "special_issue",
        "thesis",
        "edition_translation",
    }
    if row.get("status") not in {
        "OA_VERIFICADO",
        "EVALUADO",
        "LISTO",
        "FICHA_LISTA",
        "REVISION_EDITORIAL",
    }:
        return False
    try:
        relevance = int(row.get("relevance_score") or 0)
    except ValueError:
        relevance = 0
    if relevance < 15:
        return False
    if kind in academic and not check_publishable(row):
        return False
    if row.get("source_id") == "doab-economics" or row.get("source_type") in {
        "doab_oai",
        "doab_rest",
        "crossref_academic",
        "academic_oai",
        "nep_report",
    }:
        reasons = row.get("relevance_reasons") or ""
        if (
            "decision=PROMOCION_AUTOMATICA" not in reasons
            and "pluralismo_rescate=si" not in reasons
        ):
            return False
    if not clean(row.get("title")) or not access(row):
        return False
    if kind in academic:
        if row.get("oa_status") not in {
            "VERIFICADO",
            "VERIFICADO_FUENTE",
            "OA_VERIFICADO",
        } or not year(row):
            return False
        if row.get("access_status") not in {"PUBLIC_ACCESS_VERIFIED", "VERIFICADO"}:
            return False
        if kind in {
            "paper",
            "book",
            "chapter",
            "thesis",
            "edition_translation",
        } and not clean(row.get("authors")):
            return False
        return True
    return row.get("access_status") in {
        "OFFICIAL_SOURCE_VERIFIED",
        "PUBLIC_ACCESS_VERIFIED",
        "VERIFICADO",
    } or clean(row.get("source_url")).startswith("https://")


def resolve_and_acquire_media(row, kind):
    """Pide media al resolver y materializa; nunca elige el siguiente fallback."""
    candidate = dict(row)
    candidate["content_type"] = kind
    rejected_methods: dict[str, str] = {}

    while True:
        resolution = resolve_media(candidate, rejected_methods=rejected_methods)
        try:
            acquired = acquire_media(resolution)
        except MediaAcquisitionError as exc:
            if not is_fallback_acquisition_error(exc):
                raise
            rejected_methods[resolution.media_method] = f"{exc.code}: {exc.detail}"
            continue

        return {
            "media_type": acquired.media_type_declared,
            "media_path": acquired.media_path,
            "media_source": resolution.media_source,
            "media_source_url": resolution.media_source_url,
            "media_rights_status": resolution.media_rights_status,
            "media_method": resolution.media_method,
            "media_resolution_fingerprint": resolution.resolution_fingerprint,
            "media_content_sha256": acquired.content_sha256,
            "media_acquisition_reused": "si" if acquired.reused_existing else "no",
            "alt_text": resolution.alt_text,
        }


def main():
    with C.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        candidates = list(reader)
        cfields = reader.fieldnames
    with Q.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        queue = list(reader)
        qfields = list(reader.fieldnames or [])

    for field in QUEUE_DERIVED_FIELDS:
        if field not in qfields:
            qfields.append(field)
    for field in TEXT_PROVENANCE_FIELDS:
        if field not in qfields:
            qfields.append(field)
    for field in MEDIA_PROVENANCE_FIELDS:
        if field not in qfields:
            qfields.append(field)

    policy_fp = policy_fingerprint()
    cmap = {row.get("candidate_id"): row for row in candidates if row.get("candidate_id")}
    existing = {row.get("url_id", ""): row for row in queue if row.get("url_id")}
    invalidated = 0

    for queued in queue:
        if queued.get("flujo_editorial") == "archivo_historico":
            continue
        cid = queued.get("url_id") or ""
        row = cmap.get(cid)
        if not row:
            continue
        if queued.get("estado_editorial") in {"PUBLICADO", "ORIGINAL_RETIRADO"}:
            continue
        if queued.get("meta_attempt_status") == "SCHEDULED" or queued.get("post_nuevo_id"):
            continue
        candidate_fp = candidate_fingerprint(row)
        changed = (
            queued.get("candidate_fingerprint") != candidate_fp
            or queued.get("editorial_policy_fingerprint") != policy_fp
            or queued.get("editorial_score") != (row.get("editorial_score") or "")
            or queued.get("editorial_decision") != (row.get("editorial_decision") or "")
        )
        queued["editorial_score"] = row.get("editorial_score") or ""
        queued["editorial_decision"] = row.get("editorial_decision") or ""
        queued["candidate_fingerprint"] = candidate_fp
        queued["editorial_policy_fingerprint"] = policy_fp
        if changed and queued.get("estado_editorial") in {
            "FICHA_LISTA",
            "APROBADO",
            "PROGRAMADO",
            "REVALIDAR",
        }:
            queued["estado_editorial"] = "REVALIDAR"
            queued["fecha_programada"] = ""
            queued["orden_dia"] = ""
            queued["meta_attempt_status"] = ""
            queued["meta_attempted_at"] = ""
            queued["notas"] = (
                (queued.get("notas") or "")
                + " | invalidada para revalidación por cambio de candidato/política"
            ).strip(" |")
            invalidated += 1

    prepared = blocked = 0
    visual_counts = {
        "VERIFICADO": 0,
        "CAPTURA_LANDING_OFICIAL": 0,
        "PROPIO_DETERMINISTA": 0,
    }

    for row in candidates:
        cid = row.get("candidate_id") or ""
        qexisting = existing.get(cid)
        if qexisting and qexisting.get("estado_editorial") != "REVALIDAR":
            continue
        kind = ctype(row)
        if not eligible(row, kind):
            continue

        try:
            meta = meta_for(kind, row)
            meta.update(text_context(row))
            text_result = render_result(kind, meta)
            visual = resolve_and_acquire_media(row, kind)
        except (MediaResolutionError, MediaAcquisitionError, Exception) as exc:
            row["notes"] = (
                (row.get("notes") or "")
                + f" | preparación bloqueada: {type(exc).__name__}: {exc}"
            ).strip(" |")
            blocked += 1
            continue

        queued = qexisting if qexisting is not None else {key: "" for key in qfields}
        for field in qfields:
            queued.setdefault(field, "")
        translation = text_result.translation if text_result.translation.get("present") else {}
        queued.update(
            {
                "editorial_id": queued.get("editorial_id")
                or "ED-" + cid.removeprefix("CAND-"),
                "flujo_editorial": row.get("flujo_editorial") or "novedad",
                "prioridad": row.get("priority") or queued.get("prioridad") or "100",
                "estado_editorial": "FICHA_LISTA",
                "url_id": cid,
                "url_original": row.get("source_url", ""),
                "titulo_original": clean(row.get("title")),
                "responsables": clean(row.get("authors")),
                "tipo_recurso": kind,
                "anio": year(row),
                "idioma_obra": row.get("language", ""),
                "obra_estado": "OBRA_VERIFICADA",
                "edicion_estado": "EDICION_VERIFICADA"
                if kind
                in {
                    "paper",
                    "book",
                    "chapter",
                    "report",
                    "policy_brief",
                    "special_issue",
                    "thesis",
                    "edition_translation",
                }
                else "NO_APLICA",
                "oa_estado": "OA_VERIFICADO"
                if kind
                in {
                    "paper",
                    "book",
                    "chapter",
                    "report",
                    "policy_brief",
                    "special_issue",
                    "thesis",
                    "edition_translation",
                }
                else "NO_APLICA",
                "doi": row.get("doi", ""),
                "oa_url": access(row),
                "oa_fuente": source_name(row),
                "area_clep": row.get("area_clep", ""),
                "licencia": clean(
                    (re.search(r"license_url=([^|;\\s]+)", row.get("notes") or "") or [None, ""])[1]
                ),
                "ficha_es": text_result.post_text,
                "source_summary": text_result.source_summary,
                "source_summary_es": text_result.source_summary_es,
                "editorial_description": text_result.editorial_description,
                "notas": (
                    f"Origen {source_name(row)}; relevance_score={row.get('relevance_score') or '0'}; "
                    f"editorial_score={row.get('editorial_score') or '0'}; "
                    f"editorial_decision={row.get('editorial_decision') or ''}; "
                    f"venue={clean(row.get('venue'))}; preparación atómica determinista sin IA generativa."
                ),
                "text_method": text_result.text_method,
                "text_template": text_result.text_template,
                "text_template_version": str(text_result.text_template_version),
                "text_status": "VERIFICADO"
                if text_result.text_status == "VERIFIED"
                else text_result.text_status,
                "translation_status": translation.get("status", ""),
                "translation_method": translation.get("method", ""),
                "translation_engine": translation.get("engine", ""),
                "translation_engine_version": translation.get("engine_version", ""),
                "translation_source_language": translation.get("source_language", ""),
                "translation_target_language": translation.get("target_language", ""),
                "translation_disclosure": translation.get("disclosure", ""),
                "editorial_score": row.get("editorial_score") or "",
                "editorial_decision": row.get("editorial_decision") or "",
                "editorial_policy_fingerprint": policy_fp,
                "candidate_fingerprint": candidate_fingerprint(row),
                **visual,
            }
        )
        if qexisting is None:
            queue.append(queued)
            existing[cid] = queued
        row["status"] = "FICHA_LISTA"
        prepared += 1
        visual_counts[visual["media_rights_status"]] = (
            visual_counts.get(visual["media_rights_status"], 0) + 1
        )

    with Q.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=qfields)
        writer.writeheader()
        writer.writerows(queue)
    with C.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=cfields)
        writer.writeheader()
        writer.writerows(candidates)

    print(
        f"Preparados atómicamente: {prepared}; invalidados={invalidated}; "
        f"bloqueados: {blocked}; visuales={visual_counts}"
    )


if __name__ == "__main__":
    main()
