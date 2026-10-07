#!/usr/bin/env python3
"""Contrato compartido del producto editorial preparado.

Mantiene una sola definición del fingerprint de preparación. El preparador lo
crea y el verificador lo recompone desde la fila persistida sin decidir política
editorial ni volver a renderizar texto/media.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from estado_editorial import candidate_fingerprint

PREPARATION_VERSION = 1

MEDIA_FINGERPRINT_FIELDS = (
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

TRANSLATION_FLAT_FIELDS = (
    "translation_status",
    "translation_method",
    "translation_engine",
    "translation_engine_version",
    "translation_source_language",
    "translation_target_language",
    "translation_disclosure",
)


def _value(value: object) -> str:
    return str(value or "")


def build_preparation_fingerprint(
    *,
    candidate_fp: str,
    policy_fp: str,
    post_text: str,
    source_summary: str,
    source_summary_es: str,
    editorial_description: str,
    text_method: str,
    text_template: str,
    text_template_version: str,
    text_status: str,
    translation: Mapping[str, Any],
    media: Mapping[str, object],
) -> str:
    """Calcula el fingerprint canónico v1 preservando el algoritmo del Paso 6."""
    payload = {
        "preparation_version": PREPARATION_VERSION,
        "candidate_fingerprint": candidate_fp,
        "editorial_policy_fingerprint": policy_fp,
        "text": {
            "post_text": post_text,
            "source_summary": source_summary,
            "source_summary_es": source_summary_es,
            "editorial_description": editorial_description,
            "text_method": text_method,
            "text_template": text_template,
            "text_template_version": str(text_template_version),
            "text_status": text_status,
            "translation": dict(translation),
        },
        "media": {key: _value(media.get(key)) for key in MEDIA_FINGERPRINT_FIELDS},
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_from_rendered(
    candidate: Mapping[str, object],
    policy_fp: str,
    text_result: Any,
    media: Mapping[str, object],
) -> str:
    """Entrada del orquestador: candidato + resultado del renderer + media validada."""
    return build_preparation_fingerprint(
        candidate_fp=candidate_fingerprint(candidate),
        policy_fp=policy_fp,
        post_text=text_result.post_text,
        source_summary=text_result.source_summary,
        source_summary_es=text_result.source_summary_es,
        editorial_description=text_result.editorial_description,
        text_method=text_result.text_method,
        text_template=text_result.text_template,
        text_template_version=str(text_result.text_template_version),
        text_status=text_result.text_status,
        translation=text_result.translation,
        media=media,
    )


def translation_from_prepared_row(row: Mapping[str, object]) -> dict[str, object]:
    """Reconstruye exactamente la representación plana persistida por el Paso 6."""
    present = any(_value(row.get(field)).strip() for field in TRANSLATION_FLAT_FIELDS)
    if not present:
        return {"present": False}
    return {
        "present": True,
        "text": _value(row.get("source_summary_es")),
        "status": _value(row.get("translation_status")),
        "method": _value(row.get("translation_method")),
        "engine": _value(row.get("translation_engine")),
        "engine_version": _value(row.get("translation_engine_version")),
        "source_language": _value(row.get("translation_source_language")),
        "target_language": _value(row.get("translation_target_language")),
        "disclosure": _value(row.get("translation_disclosure")),
    }


def fingerprint_from_prepared_row(row: Mapping[str, object]) -> str:
    """Recompone el fingerprint v1 desde la fila de cola persistida."""
    text_status = _value(row.get("text_status"))
    if text_status == "VERIFICADO":
        text_status = "VERIFIED"
    return build_preparation_fingerprint(
        candidate_fp=_value(row.get("candidate_fingerprint")),
        policy_fp=_value(row.get("editorial_policy_fingerprint")),
        post_text=_value(row.get("post_text") or row.get("ficha_es")),
        source_summary=_value(row.get("source_summary")),
        source_summary_es=_value(row.get("source_summary_es")),
        editorial_description=_value(row.get("editorial_description")),
        text_method=_value(row.get("text_method")),
        text_template=_value(row.get("text_template")),
        text_template_version=_value(row.get("text_template_version")),
        text_status=text_status,
        translation=translation_from_prepared_row(row),
        media=row,
    )
