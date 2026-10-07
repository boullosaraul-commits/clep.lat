#!/usr/bin/env python3
"""Reglas editoriales operativas puras de CLEP.

`schema.py` conserva el contrato estructural/versionado y las máquinas de estado.
Este módulo concentra decisiones de política que antes estaban duplicadas entre
preparación, planificación y verificación. No realiza I/O ni muta registros.
"""
from __future__ import annotations

import re
from typing import Mapping

ACADEMIC_TYPES = {
    "paper", "book", "chapter", "report", "policy_brief", "special_issue",
    "thesis", "edition_translation",
}
AUTHOR_REQUIRED_TYPES = {"paper", "book", "chapter", "thesis", "edition_translation"}
NON_TEXT_TYPES = {
    "actividad_clep", "convocatoria", "convocatoria_evento", "recurso", "video",
    "grafica", "dataset_grafica", "material_didactico", "efemeride", "anuncio_institucional",
}
LEGACY_READY_STATES = {"FICHA_LISTA", "APROBADO"}
LEGACY_MEDIA_RIGHTS_OK = {"VERIFICADO", "CAPTURA_LANDING_OFICIAL", "PROPIO_DETERMINISTA"}
PUBLICABLE_DECISIONS = {"PUBLISHABLE", "OUTSTANDING"}
PUBLIC_ACCESS_OK = {"PUBLIC_ACCESS_VERIFIED", "VERIFICADO"}
OA_OK = {"VERIFICADO", "VERIFICADO_FUENTE", "OA_VERIFICADO"}
CANDIDATE_PREPARABLE_STATES = {"OA_VERIFICADO", "EVALUADO", "LISTO", "FICHA_LISTA", "REVISION_EDITORIAL"}
ACADEMIC_SOURCE_TYPES = {"doab_oai", "doab_rest", "crossref_academic", "academic_oai", "nep_report"}


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def publication_year(row: Mapping[str, object]) -> str:
    raw = clean(row.get("publication_year"))
    if re.fullmatch(r"(?:18|19|20)\d{2}", raw):
        return raw
    match = re.search(r"\b(?:18|19|20)\d{2}\b", str(row.get("published_at") or ""))
    return match.group(0) if match else ""


def access_url(row: Mapping[str, object]) -> str:
    return clean(row.get("access_url") or row.get("source_url"))


def editorial_score(row: Mapping[str, object]) -> float:
    try:
        return float(row.get("editorial_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def relevance_score(row: Mapping[str, object]) -> int:
    try:
        return int(row.get("relevance_score") or 0)
    except (TypeError, ValueError):
        return 0


def academic_publishable(row: Mapping[str, object], *, minimum_score: float = 7.0) -> bool:
    """Decisión editorial mínima común para una novedad académica."""
    return editorial_score(row) >= minimum_score and row.get("editorial_decision") in PUBLICABLE_DECISIONS


def candidate_eligible(row: Mapping[str, object], kind: str) -> bool:
    """Puede el candidato legacy entrar a preparación editorial.

    Es deliberadamente compatible con el CSV legacy durante la migración a v1.
    No reemplaza `schema.validate_candidate`; evita que tres consumidores
    mantengan versiones distintas de la misma política.
    """
    if row.get("status") not in CANDIDATE_PREPARABLE_STATES:
        return False
    if relevance_score(row) < 15:
        return False
    academic = kind in ACADEMIC_TYPES
    if academic and not academic_publishable(row):
        return False

    if row.get("source_id") == "doab-economics" or row.get("source_type") in ACADEMIC_SOURCE_TYPES:
        reasons = str(row.get("relevance_reasons") or "")
        if "decision=PROMOCION_AUTOMATICA" not in reasons and "pluralismo_rescate=si" not in reasons:
            return False

    if not clean(row.get("title")) or not access_url(row):
        return False

    if academic:
        if row.get("oa_status") not in OA_OK or not publication_year(row):
            return False
        if row.get("access_status") not in PUBLIC_ACCESS_OK:
            return False
        if kind in AUTHOR_REQUIRED_TYPES and not clean(row.get("authors")):
            return False
        return True

    return (
        row.get("access_status") in {"OFFICIAL_SOURCE_VERIFIED", *PUBLIC_ACCESS_OK}
        or clean(row.get("source_url")).startswith("https://")
    )


def publication_certified(row: Mapping[str, object]) -> bool:
    """Texto y media mínimos ya certificados para poder planificar."""
    return (
        row.get("text_status") == "VERIFICADO"
        and bool(clean(row.get("ficha_es")))
        and row.get("media_rights_status") in LEGACY_MEDIA_RIGHTS_OK
        and bool(clean(row.get("media_path") or row.get("media_url")))
    )


def schedulable(row: Mapping[str, object]) -> bool:
    """Fila legacy lista y certificada, sin fecha previa, para el planificador."""
    return (
        row.get("estado_editorial") in LEGACY_READY_STATES
        and not clean(row.get("fecha_programada"))
        and publication_certified(row)
    )
