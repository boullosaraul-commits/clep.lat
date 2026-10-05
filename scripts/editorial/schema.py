#!/usr/bin/env python3
"""Contrato editorial versionado para CLEP.

Este módulo define el esquema canónico v1 y validadores mínimos para candidatos
publicaciones y transiciones de estado. Durante la migración se admite lectura
de filas legacy, pero todo código nuevo debe escribir únicamente schema_version=1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

CURRENT_SCHEMA_VERSION = 1
LEGACY_SCHEMA_VERSION = "legacy"

CONTENT_TYPES = {
    "PAPER", "BOOK", "CHAPTER", "REPORT", "POLICY_BRIEF", "SPECIAL_ISSUE",
    "THESIS", "EDITION_TRANSLATION", "DATASET", "CHART", "EVENT", "CALL",
    "VIDEO", "RESOURCE", "TEACHING_MATERIAL", "INSTITUTIONAL",
}

FLOW_TYPES = {"CURRENT", "HISTORICAL", "CLEP_ACTIVITY", "CLEP_PUBLICATION", "RESOURCE", "AD_HOC"}
ORIGINS = {"AUTOMATIC_DISCOVERY", "HISTORICAL_RECOVERY", "MANUAL", "CHAT"}
CANDIDATE_STATUSES = {"DISCOVERED", "EVALUATED", "ACCESS_PENDING", "ACCESS_VERIFIED", "ELIGIBLE", "REJECTED", "ARCHIVED"}
RELEVANCE_DECISIONS = {"AUTO_PROMOTE", "EDITORIAL_REVIEW", "ARCHIVE"}
EDITORIAL_DECISIONS = {"PUBLISHABLE", "OUTSTANDING", "REVIEW", "REJECTED", "INELIGIBLE"}
ACCESS_STATUSES = {"UNKNOWN", "PENDING", "PUBLIC_ACCESS_VERIFIED", "RESTRICTED", "BROKEN", "TIMEOUT", "BLOCKED"}
OA_STATUSES = {"UNKNOWN", "PENDING", "OA_VERIFIED", "NOT_OA", "INSUFFICIENT_EVIDENCE"}
RIGHTS_STATUSES = {"UNKNOWN", "DECLARED_OPEN", "DECLARED_RESTRICTED", "PUBLIC_DOMAIN", "LICENSED"}
TRANSLATION_METHODS = {"NONE", "AUTOMATIC", "HUMAN"}
TRANSLATION_STATUSES = {"NOT_NEEDED", "PENDING", "AUTO_TRANSLATED", "HUMAN_TRANSLATED", "VERIFIED", "FAILED", "UNSUPPORTED_LANGUAGE"}
TEXT_METHODS = {"DETERMINISTIC_TEMPLATE", "HUMAN", "IMPORTED"}
TEXT_STATUSES = {"MISSING", "PENDING", "READY", "VERIFIED", "INVALID", "TEMPLATE_MISSING"}
MEDIA_METHODS = {"OFFICIAL_IMAGE", "OFFICIAL_THUMBNAIL", "OFFICIAL_LANDING_CAPTURE", "DETERMINISTIC_CARD", "DETERMINISTIC_CHART"}
MEDIA_STATUSES = {"MISSING", "PENDING", "READY", "VERIFIED", "INVALID"}
MEDIA_RIGHTS_STATUSES = {"UNKNOWN", "VERIFIED_REUSABLE", "CLEP_OWNED", "CONTEXTUAL_SCREENSHOT", "RESTRICTED"}
PREPARATION_STATUSES = {"PENDING", "TEXT_READY", "MEDIA_READY", "VALIDATED", "READY", "QUARANTINED"}
PUBLICATION_STATUSES = {"NOT_QUEUED", "QUEUED", "SCHEDULED", "PUBLISHED", "RETIRED", "CANCELLED"}
META_STATUSES = {"NONE", "RESERVED", "REQUESTED", "SCHEDULED", "PUBLISHED", "FAILED", "AMBIGUOUS", "DELETED"}
QUARANTINE_REASONS = {"SCHEMA_ERROR", "METADATA_INCOMPLETE", "ACCESS_ERROR", "TRANSLATION_ERROR", "TEXT_ERROR", "MEDIA_ERROR", "POLICY_ERROR", "SCHEDULING_ERROR", "META_ERROR", "STATE_INCONSISTENCY", "UNKNOWN"}
ERROR_CLASSES = {"TEMPORARY", "PERMANENT", "AMBIGUOUS"}

ENUMS = {
    "content_type": CONTENT_TYPES,
    "flow_type": FLOW_TYPES,
    "origin": ORIGINS,
    "candidate_status": CANDIDATE_STATUSES,
    "relevance_decision": RELEVANCE_DECISIONS,
    "editorial_decision": EDITORIAL_DECISIONS,
    "access_status": ACCESS_STATUSES,
    "oa_status": OA_STATUSES,
    "rights_status": RIGHTS_STATUSES,
    "translation_method": TRANSLATION_METHODS,
    "translation_status": TRANSLATION_STATUSES,
    "text_method": TEXT_METHODS,
    "text_status": TEXT_STATUSES,
    "media_method": MEDIA_METHODS,
    "media_status": MEDIA_STATUSES,
    "media_rights_status": MEDIA_RIGHTS_STATUSES,
    "preparation_status": PREPARATION_STATUSES,
    "publication_status": PUBLICATION_STATUSES,
    "meta_status": META_STATUSES,
    "quarantine_reason": QUARANTINE_REASONS,
    "error_class": ERROR_CLASSES,
}

LEGACY_ENUM_MAPS = {
    "content_type": {
        "paper": "PAPER", "book": "BOOK", "chapter": "CHAPTER", "report": "REPORT",
        "policy_brief": "POLICY_BRIEF", "special_issue": "SPECIAL_ISSUE", "thesis": "THESIS",
        "edition_translation": "EDITION_TRANSLATION", "video": "VIDEO", "recurso": "RESOURCE",
    },
    "translation_status": {"AUTOMATICA": "AUTO_TRANSLATED"},
    "relevance_decision": {
        "PROMOCION_AUTOMATICA": "AUTO_PROMOTE", "REVISION_EDITORIAL": "EDITORIAL_REVIEW", "ARCHIVADO": "ARCHIVE",
    },
}

CANDIDATE_REQUIRED = {"schema_version", "candidate_id", "source_id", "source_type", "title", "content_type", "candidate_status"}
PUBLICATION_REQUIRED = {"schema_version", "candidate_id", "editorial_id", "title", "content_type", "preparation_status", "publication_status", "meta_status"}

TRANSITIONS = {
    "candidate": {
        "DISCOVERED": {"EVALUATED", "ARCHIVED"},
        "EVALUATED": {"ACCESS_PENDING", "REJECTED", "ARCHIVED"},
        "ACCESS_PENDING": {"ACCESS_VERIFIED", "REJECTED", "ARCHIVED"},
        "ACCESS_VERIFIED": {"ELIGIBLE", "REJECTED", "ARCHIVED"},
        "ELIGIBLE": {"REJECTED", "ARCHIVED"},
        "REJECTED": set(),
        "ARCHIVED": set(),
    },
    "translation": {
        "PENDING": {"AUTO_TRANSLATED", "HUMAN_TRANSLATED", "FAILED", "UNSUPPORTED_LANGUAGE"},
        "AUTO_TRANSLATED": {"VERIFIED"},
        "HUMAN_TRANSLATED": {"VERIFIED"},
        "NOT_NEEDED": set(), "VERIFIED": set(), "FAILED": set(), "UNSUPPORTED_LANGUAGE": set(),
    },
    "text": {
        "MISSING": {"PENDING"},
        "PENDING": {"READY", "INVALID", "TEMPLATE_MISSING"},
        "READY": {"VERIFIED", "INVALID"},
        "VERIFIED": set(), "INVALID": set(), "TEMPLATE_MISSING": set(),
    },
    "media": {
        "MISSING": {"PENDING"},
        "PENDING": {"READY", "INVALID"},
        "READY": {"VERIFIED", "INVALID"},
        "VERIFIED": set(), "INVALID": set(),
    },
    "preparation": {
        "PENDING": {"TEXT_READY", "MEDIA_READY", "QUARANTINED"},
        "TEXT_READY": {"VALIDATED", "QUARANTINED"},
        "MEDIA_READY": {"VALIDATED", "QUARANTINED"},
        "VALIDATED": {"READY", "QUARANTINED"},
        "READY": set(),
        "QUARANTINED": {"PENDING"},
    },
    "publication": {
        "NOT_QUEUED": {"QUEUED"},
        "QUEUED": {"SCHEDULED", "CANCELLED"},
        "SCHEDULED": {"PUBLISHED", "CANCELLED"},
        "PUBLISHED": {"RETIRED"},
        "RETIRED": set(), "CANCELLED": set(),
    },
    "meta": {
        "NONE": {"RESERVED"},
        "RESERVED": {"REQUESTED"},
        "REQUESTED": {"SCHEDULED", "FAILED", "AMBIGUOUS"},
        "SCHEDULED": {"PUBLISHED", "FAILED", "DELETED"},
        "PUBLISHED": set(), "FAILED": set(), "AMBIGUOUS": set(), "DELETED": set(),
    },
}

class SchemaError(ValueError):
    pass


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def detect_schema_version(row: Mapping[str, object]):
    raw = row.get("schema_version")
    if _blank(raw):
        return LEGACY_SCHEMA_VERSION
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"schema_version inválido: {raw!r}") from exc


def validate_schema_version(row: Mapping[str, object]) -> int:
    version = detect_schema_version(row)
    if version == LEGACY_SCHEMA_VERSION:
        raise SchemaError("fila legacy: requiere normalización antes de validarse como v1")
    if version != CURRENT_SCHEMA_VERSION:
        raise SchemaError(f"schema_version no soportado: {version}")
    return version


def validate_enum(field: str, value: object) -> None:
    if field not in ENUMS:
        raise SchemaError(f"enum desconocido: {field}")
    if value not in ENUMS[field]:
        raise SchemaError(f"{field} inválido: {value!r}")


def _require(row: Mapping[str, object], fields: Iterable[str]) -> None:
    missing = [field for field in fields if _blank(row.get(field))]
    if missing:
        raise SchemaError("campos obligatorios ausentes: " + ", ".join(sorted(missing)))


def _validate_known_enums(row: Mapping[str, object]) -> None:
    for field, allowed in ENUMS.items():
        value = row.get(field)
        if _blank(value):
            continue
        if value not in allowed:
            raise SchemaError(f"{field} inválido: {value!r}")


def _validate_translation(row: Mapping[str, object]) -> None:
    status = row.get("translation_status")
    if status == "AUTO_TRANSLATED":
        required = {"translation_method", "translation_engine", "source_summary", "source_summary_es"}
        _require(row, required)
        if row.get("translation_method") != "AUTOMATIC":
            raise SchemaError("AUTO_TRANSLATED requiere translation_method=AUTOMATIC")
    if status == "HUMAN_TRANSLATED":
        _require(row, {"translation_method", "source_summary_es"})
        if row.get("translation_method") != "HUMAN":
            raise SchemaError("HUMAN_TRANSLATED requiere translation_method=HUMAN")


def validate_candidate(row: Mapping[str, object]) -> None:
    validate_schema_version(row)
    _require(row, CANDIDATE_REQUIRED)
    _validate_known_enums(row)
    _validate_translation(row)
    if row.get("candidate_status") == "ACCESS_VERIFIED" and row.get("access_status") != "PUBLIC_ACCESS_VERIFIED":
        raise SchemaError("ACCESS_VERIFIED requiere access_status=PUBLIC_ACCESS_VERIFIED")
    if row.get("candidate_status") == "ELIGIBLE":
        if row.get("access_status") != "PUBLIC_ACCESS_VERIFIED":
            raise SchemaError("ELIGIBLE requiere acceso público verificado")
        if row.get("editorial_decision") not in {"PUBLISHABLE", "OUTSTANDING"}:
            raise SchemaError("ELIGIBLE requiere decisión editorial publicable")


def validate_publication(row: Mapping[str, object]) -> None:
    validate_schema_version(row)
    _require(row, PUBLICATION_REQUIRED)
    _validate_known_enums(row)
    _validate_translation(row)
    if row.get("preparation_status") in {"VALIDATED", "READY"}:
        if row.get("text_status") != "VERIFIED" or row.get("media_status") != "VERIFIED":
            raise SchemaError("preparation VALIDATED/READY requiere texto y media verificados")
    if row.get("preparation_status") == "READY":
        if row.get("candidate_status") != "ELIGIBLE":
            raise SchemaError("preparation READY requiere candidate_status=ELIGIBLE")
        if row.get("editorial_decision") not in {"PUBLISHABLE", "OUTSTANDING"}:
            raise SchemaError("preparation READY requiere decisión editorial publicable")
    if row.get("meta_status") == "RESERVED":
        _require(row, {"meta_attempt_id", "meta_payload_hash"})
    if row.get("publication_status") == "QUEUED" and row.get("preparation_status") != "READY":
        raise SchemaError("publication QUEUED requiere preparation READY")
    if row.get("publication_status") == "SCHEDULED":
        if row.get("preparation_status") != "READY" or row.get("meta_status") != "SCHEDULED" or _blank(row.get("meta_post_id")):
            raise SchemaError("publication SCHEDULED requiere preparación lista y Meta programado")
    if row.get("publication_status") == "PUBLISHED":
        if row.get("meta_status") != "PUBLISHED" or _blank(row.get("meta_post_id")) or _blank(row.get("published_at_meta")):
            raise SchemaError("publication PUBLISHED requiere publicación Meta verificada")
    if row.get("preparation_status") == "QUARANTINED":
        _require(row, {"quarantine_reason", "quarantine_error_code", "quarantine_step", "quarantined_at"})


def validate_transition(domain: str, old_state: str, new_state: str, row: Mapping[str, object] | None = None) -> None:
    if domain not in TRANSITIONS:
        raise SchemaError(f"dominio de transición desconocido: {domain}")
    if old_state not in TRANSITIONS[domain]:
        raise SchemaError(f"estado origen desconocido para {domain}: {old_state}")
    if new_state not in TRANSITIONS[domain][old_state]:
        raise SchemaError(f"transición no permitida: {domain} {old_state}->{new_state}")
    if row is None:
        return
    probe = dict(row)
    field = {
        "candidate": "candidate_status", "translation": "translation_status", "text": "text_status",
        "media": "media_status", "preparation": "preparation_status", "publication": "publication_status",
        "meta": "meta_status",
    }[domain]
    probe[field] = new_state
    if "editorial_id" in probe or "publication_status" in probe:
        validate_publication(probe)
    else:
        validate_candidate(probe)


def normalize_legacy_enum(field: str, value: object):
    if _blank(value):
        return value
    mapping = LEGACY_ENUM_MAPS.get(field, {})
    if value in mapping:
        return mapping[value]
    if field in ENUMS and value in ENUMS[field]:
        return value
    raise SchemaError(f"valor legacy sin mapeo para {field}: {value!r}")
