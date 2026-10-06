#!/usr/bin/env python3
"""Preparación editorial atómica CLEP: texto + media + procedencia.

La preparación no decide qué media usar. La autoridad de prioridad es
`resolver_media.py`; `adquirir_media.py` materializa la resolución elegida y
`validar_media.py` certifica físicamente el asset antes de FICHA_LISTA.

Paso 6: este módulo actúa como orquestador. La unidad de trabajo es
`prepare_one()`: valida precondiciones, renderiza texto, resuelve/adquiere/
valida media y sólo entonces construye una fila completa lista para persistir.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from adquirir_media import MediaAcquisitionError, acquire_media
from editorial_rules import check_publishable
from estado_editorial import QUEUE_DERIVED_FIELDS, candidate_fingerprint, policy_fingerprint
from media_fallback_policy import acquisition_can_fallback, validation_can_fallback
from renderizar_texto import TextRenderError, render_result
from resolver_media import ALLOWED_MEDIA_METHODS, MediaResolutionError, resolve_media
from validar_media import validate_media

C = Path(
    os.getenv("CLEP_CANDIDATES_PATH", str(ROOT / "data/editorial/candidatos.csv"))
).resolve()
Q = Path(os.getenv("CLEP_QUEUE_PATH", str(ROOT / "data/editorial/cola.csv"))).resolve()

PREPARATION_VERSION = 1

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
    "media_resolver_version",
    "media_fallback_level",
    "media_resolution_fingerprint",
    "media_acquisition_method",
    "media_content_sha256",
    "media_bytes_size",
    "media_acquisition_reused",
    "alt_text",
    "media_validation_status",
    "media_validation_version",
    "detected_media_type",
    "media_width",
    "media_height",
)
PREPARATION_PROVENANCE_FIELDS = (
    "preparation_version",
    "preparation_fingerprint",
)

PREPARATION_READY = "READY"
PREPARATION_BLOCKED = "BLOCKED"
PREPARATION_SKIPPED = "SKIPPED"

STAGE_PRECONDITION = "PRECONDITION"
STAGE_TEXT = "TEXT_RENDER"
STAGE_MEDIA = "MEDIA_RESOLVE_ACQUIRE_VALIDATE"
STAGE_ASSEMBLE = "ASSEMBLE"
STAGE_COMPLETE = "COMPLETE"

MAX_MEDIA_ATTEMPTS = len(ALLOWED_MEDIA_METHODS)
ERROR_MEDIA_FALLBACK_EXHAUSTED = "MEDIA_FALLBACK_EXHAUSTED"
ERROR_MEDIA_METHOD_REPEATED = "MEDIA_METHOD_REPEATED"


class MediaValidationBlocked(RuntimeError):
    code = "MEDIA_VALIDATION_BLOCKED"

    def __init__(self, result):
        self.result = result
        self.detail = "; ".join(
            f"{issue.code}: {issue.detail}" for issue in result.errors
        ) or "media inválida"
        super().__init__(self.detail)


class MediaFallbackError(RuntimeError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class PreparationOutcome:
    """Contrato de una preparación individual sin persistencia parcial."""

    status: str
    candidate_id: str
    stage: str
    queue_row: dict[str, str] | None = None
    candidate_updates: dict[str, str] | None = None
    error_code: str = ""
    error_detail: str = ""

    @property
    def ready(self) -> bool:
        return self.status == PREPARATION_READY

    @property
    def blocked(self) -> bool:
        return self.status == PREPARATION_BLOCKED


EXPECTED_PREPARATION_ERRORS = (
    TextRenderError,
    MediaResolutionError,
    MediaAcquisitionError,
    MediaValidationBlocked,
    MediaFallbackError,
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
    """Adapta provenance textual; no decide plantilla, resumen ni fallback."""
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
    """Adapta campos de candidato al contrato del renderer; no renderiza texto."""
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
    raise TextRenderError(
        "CONTENT_TYPE_UNSUPPORTED",
        f"tipo no soportado por adaptador: {kind}",
        "content_type",
    )


def eligible(row, kind):
    # Temporal durante Paso 6: la política se extraerá en la tanda correspondiente.
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


def resolve_acquire_validate_media(row, kind):
    """Orquesta media sin decidir prioridad ni clasificar fallos localmente."""
    candidate = dict(row)
    candidate["content_type"] = kind
    rejected_methods: dict[str, str] = {}
    attempted_methods: set[str] = set()

    for _ in range(MAX_MEDIA_ATTEMPTS):
        resolution = resolve_media(candidate, rejected_methods=rejected_methods)
        method = resolution.media_method
        if method in attempted_methods:
            raise MediaFallbackError(
                ERROR_MEDIA_METHOD_REPEATED,
                f"resolver devolvió de nuevo método ya rechazado: {method}",
            )
        attempted_methods.add(method)

        try:
            acquired = acquire_media(resolution)
        except MediaAcquisitionError as exc:
            if not acquisition_can_fallback(exc):
                raise
            rejected_methods[method] = f"{exc.code}: {exc.detail}"
            continue

        visual = {
            "media_type": acquired.media_type_declared,
            "media_path": acquired.media_path,
            "media_source": resolution.media_source,
            "media_source_url": resolution.media_source_url,
            "media_rights_status": resolution.media_rights_status,
            "media_method": method,
            "media_resolver_version": str(resolution.resolver_version),
            "media_fallback_level": str(resolution.fallback_level),
            "media_resolution_fingerprint": resolution.resolution_fingerprint,
            "media_acquisition_method": acquired.acquisition_method,
            "media_content_sha256": acquired.content_sha256,
            "media_bytes_size": str(acquired.bytes_written),
            "media_acquisition_reused": "si" if acquired.reused_existing else "no",
            "alt_text": resolution.alt_text,
        }
        validation = validate_media(visual)
        if not validation.valid:
            if validation_can_fallback(validation):
                reason = "; ".join(
                    f"{issue.code}: {issue.detail}" for issue in validation.errors
                )
                rejected_methods[method] = f"validation: {reason}"
                continue
            raise MediaValidationBlocked(validation)

        visual.update(
            {
                "media_validation_status": validation.status,
                "media_validation_version": str(validation.validation_version),
                "detected_media_type": validation.detected_type,
                "media_width": str(validation.width or ""),
                "media_height": str(validation.height or ""),
            }
        )
        return visual

    raise MediaFallbackError(
        ERROR_MEDIA_FALLBACK_EXHAUSTED,
        f"se agotaron {MAX_MEDIA_ATTEMPTS} intentos de media; rechazados={rejected_methods}",
    )


def _queue_fieldnames(existing_fields):
    fields = list(existing_fields or [])
    for field in (
        QUEUE_DERIVED_FIELDS
        + TEXT_PROVENANCE_FIELDS
        + MEDIA_PROVENANCE_FIELDS
        + PREPARATION_PROVENANCE_FIELDS
    ):
        if field not in fields:
            fields.append(field)
    return fields


def _append_note(row: Mapping[str, Any], note: str) -> str:
    current = str(row.get("notes") or "").strip()
    if note in current:
        return current
    return (current + f" | {note}").strip(" |")


def _preparation_fingerprint(
    row: Mapping[str, str],
    policy_fp: str,
    text_result,
    visual: Mapping[str, str],
) -> str:
    """Fingerprint del producto preparado, excluyendo metadata operacional mutable."""
    payload = {
        "preparation_version": PREPARATION_VERSION,
        "candidate_fingerprint": candidate_fingerprint(row),
        "editorial_policy_fingerprint": policy_fp,
        "text": {
            "post_text": text_result.post_text,
            "source_summary": text_result.source_summary,
            "source_summary_es": text_result.source_summary_es,
            "editorial_description": text_result.editorial_description,
            "text_method": text_result.text_method,
            "text_template": text_result.text_template,
            "text_template_version": str(text_result.text_template_version),
            "text_status": text_result.text_status,
            "translation": text_result.translation,
        },
        "media": {
            key: str(visual.get(key) or "")
            for key in (
                "media_type",
                "media_path",
                "media_source",
                "media_source_url",
                "media_rights_status",
                "media_method",
                "media_resolver_version",
                "media_fallback_level",
                "media_resolution_fingerprint",
                "media_acquisition_method",
                "media_content_sha256",
                "media_bytes_size",
                "alt_text",
                "media_validation_status",
                "media_validation_version",
                "detected_media_type",
                "media_width",
                "media_height",
            )
        },
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _assemble_queue_row(
    row: Mapping[str, str],
    kind: str,
    qexisting: Mapping[str, str] | None,
    qfields: list[str],
    policy_fp: str,
    text_result,
    visual: Mapping[str, str],
) -> dict[str, str]:
    """Construye una fila completa en memoria; no muta cola ni candidato."""
    queued = dict(qexisting) if qexisting is not None else {key: "" for key in qfields}
    for field in qfields:
        queued.setdefault(field, "")

    cid = row.get("candidate_id") or ""
    translation = text_result.translation if text_result.translation.get("present") else {}
    preparation_fp = _preparation_fingerprint(row, policy_fp, text_result, visual)
    queued.update(
        {
            "editorial_id": queued.get("editorial_id") or "ED-" + cid.removeprefix("CAND-"),
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
            if kind in {
                "paper", "book", "chapter", "report", "policy_brief",
                "special_issue", "thesis", "edition_translation",
            }
            else "NO_APLICA",
            "oa_estado": "OA_VERIFICADO"
            if kind in {
                "paper", "book", "chapter", "report", "policy_brief",
                "special_issue", "thesis", "edition_translation",
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
            "preparation_version": str(PREPARATION_VERSION),
            "preparation_fingerprint": preparation_fp,
            **visual,
        }
    )
    return queued


def _error_code(exc: BaseException) -> str:
    return clean(getattr(exc, "code", "")) or type(exc).__name__


def _error_detail(exc: BaseException) -> str:
    return clean(getattr(exc, "detail", "")) or str(exc)


def prepare_one(
    row: Mapping[str, str],
    qexisting: Mapping[str, str] | None,
    qfields: list[str],
    policy_fp: str,
) -> PreparationOutcome:
    """Ejecuta una preparación lineal sin persistir estados intermedios.

    Contrato:
    - SKIPPED: la fila no cumple precondiciones y no se modifica.
    - BLOCKED: fallo editorial estructurado; devuelve sólo diagnóstico.
    - READY: devuelve fila de cola completa + actualización final del candidato.
    Los errores inesperados no se degradan silenciosamente a BLOCKED: se propagan.
    """
    cid = row.get("candidate_id") or ""
    kind = ctype(row)
    if not eligible(row, kind):
        return PreparationOutcome(
            status=PREPARATION_SKIPPED,
            candidate_id=cid,
            stage=STAGE_PRECONDITION,
        )

    stage = STAGE_TEXT
    try:
        meta = meta_for(kind, row)
        meta.update(text_context(row))
        text_result = render_result(kind, meta)

        stage = STAGE_MEDIA
        visual = resolve_acquire_validate_media(row, kind)

        stage = STAGE_ASSEMBLE
        queued = _assemble_queue_row(
            row=row,
            kind=kind,
            qexisting=qexisting,
            qfields=qfields,
            policy_fp=policy_fp,
            text_result=text_result,
            visual=visual,
        )
    except EXPECTED_PREPARATION_ERRORS as exc:
        code = _error_code(exc)
        detail = _error_detail(exc)
        return PreparationOutcome(
            status=PREPARATION_BLOCKED,
            candidate_id=cid,
            stage=stage,
            candidate_updates={
                "notes": _append_note(
                    row,
                    f"preparación bloqueada [{stage}] {code}: {detail}",
                )
            },
            error_code=code,
            error_detail=detail,
        )

    return PreparationOutcome(
        status=PREPARATION_READY,
        candidate_id=cid,
        stage=STAGE_COMPLETE,
        queue_row=queued,
        candidate_updates={"status": "FICHA_LISTA"},
    )


def invalidate_stale_queue_rows(queue, cmap, policy_fp):
    """Invalida sólo filas locales no publicadas ni reservadas en Meta."""
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
            "FICHA_LISTA", "APROBADO", "PROGRAMADO", "REVALIDAR",
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
    return invalidated


def _write_csv_atomic(path: Path, fieldnames, rows) -> bool:
    """Serializa completo, fsync y reemplaza sólo si los bytes cambian."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())

        new_bytes = temp_path.read_bytes()
        if path.exists() and path.read_bytes() == new_bytes:
            temp_path.unlink()
            return False
        os.replace(temp_path, path)
        temp_path = None
        return True
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main():
    with C.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        candidates = list(reader)
        cfields = reader.fieldnames
    with Q.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        queue = list(reader)
        qfields = _queue_fieldnames(reader.fieldnames)

    policy_fp = policy_fingerprint()
    cmap = {row.get("candidate_id"): row for row in candidates if row.get("candidate_id")}
    existing = {row.get("url_id", ""): row for row in queue if row.get("url_id")}
    invalidated = invalidate_stale_queue_rows(queue, cmap, policy_fp)

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

        outcome = prepare_one(row, qexisting, qfields, policy_fp)
        if outcome.status == PREPARATION_SKIPPED:
            continue
        if outcome.blocked:
            if outcome.candidate_updates:
                row.update(outcome.candidate_updates)
            blocked += 1
            continue

        if not outcome.ready or outcome.queue_row is None:
            raise RuntimeError(f"resultado de preparación inconsistente para {cid}")

        # Único punto de aplicación: no hay mutación parcial durante prepare_one().
        if qexisting is None:
            queue.append(outcome.queue_row)
            existing[cid] = outcome.queue_row
        else:
            qexisting.clear()
            qexisting.update(outcome.queue_row)
        if outcome.candidate_updates:
            row.update(outcome.candidate_updates)

        prepared += 1
        rights = outcome.queue_row.get("media_rights_status", "")
        visual_counts[rights] = visual_counts.get(rights, 0) + 1

    queue_written = _write_csv_atomic(Q, qfields, queue)
    candidates_written = _write_csv_atomic(C, cfields, candidates)

    print(
        f"Preparados atómicamente: {prepared}; invalidados={invalidated}; "
        f"bloqueados: {blocked}; visuales={visual_counts}; "
        f"writes=cola:{int(queue_written)},candidatos:{int(candidates_written)}"
    )


if __name__ == "__main__":
    main()
