#!/usr/bin/env python3
"""Reglas operativas centralizadas del pipeline editorial CLEP.

`schema.py` define qué valores/estados/transiciones son estructuralmente válidos.
Este módulo define cuándo una fila puede avanzar operacionalmente. No calcula el
índice editorial: consume `editorial_score` y `editorial_decision` ya producidos
por `calcular_prioridad_editorial.py`.

Durante la migración admite los nombres legacy aún presentes en `cola.csv`, pero
las reglas canónicas se expresan con el contrato v1.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping

from schema import SchemaError, validate_transition as schema_validate_transition

ROOT = Path(__file__).resolve().parents[2]
PRIORITY_CONFIG = ROOT / "data/editorial/prioridad_editorial.json"

ACADEMIC_CANONICAL = {
    "PAPER", "BOOK", "CHAPTER", "REPORT", "POLICY_BRIEF", "SPECIAL_ISSUE",
    "THESIS", "EDITION_TRANSLATION",
}
ACADEMIC_LEGACY = {x.lower() for x in ACADEMIC_CANONICAL}
PUBLISHABLE_DECISIONS = {"PUBLISHABLE", "OUTSTANDING"}
LEGACY_READY_STATES = {"FICHA_LISTA", "APROBADO"}
LEGACY_SCHEDULED_STATES = {"PROGRAMADO", "PUBLICADO", "ORIGINAL_RETIRADO"}
LEGACY_META_AMBIGUOUS = {"IN_FLIGHT", "REVIEW"}
LEGACY_MEDIA_RIGHTS_OK = {"VERIFICADO", "CAPTURA_LANDING_OFICIAL", "PROPIO_DETERMINISTA"}
LEGACY_MEDIA_EXCEPTION = "legacy_media_validation_exception=si"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class RuleResult:
    ok: bool
    code: str = "OK"
    detail: str = ""
    field: str = ""

    def __bool__(self) -> bool:
        return self.ok


class RuleError(ValueError):
    def __init__(self, code: str, detail: str = "", field: str = ""):
        self.code = code
        self.detail = detail
        self.field = field
        msg = code
        if field:
            msg += f" [{field}]"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _score(row: Mapping[str, object]) -> float:
    try:
        return float(row.get("editorial_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _positive_int(value: object) -> bool:
    try:
        return int(_clean(value)) > 0
    except (TypeError, ValueError):
        return False


def _content_type(row: Mapping[str, object]) -> str:
    return _clean(row.get("content_type") or row.get("tipo_recurso"))


def _is_academic(row: Mapping[str, object]) -> bool:
    kind = _content_type(row)
    return kind in ACADEMIC_CANONICAL or kind in ACADEMIC_LEGACY


def _publication_state(row: Mapping[str, object]) -> str:
    return _clean(row.get("publication_status") or row.get("estado_editorial"))


def _preparation_state(row: Mapping[str, object]) -> str:
    return _clean(row.get("preparation_status") or row.get("estado_editorial"))


def _meta_state(row: Mapping[str, object]) -> str:
    return _clean(row.get("meta_status") or row.get("meta_attempt_status"))


def _post_id(row: Mapping[str, object]) -> str:
    return _clean(row.get("meta_post_id") or row.get("post_nuevo_id"))


def _post_text(row: Mapping[str, object]) -> str:
    return _clean(row.get("post_text") or row.get("ficha_es"))


def _media_present(row: Mapping[str, object]) -> bool:
    return bool(_clean(row.get("media_path") or row.get("media_url")))


def _legacy_media_validation_exception(row: Mapping[str, object]) -> bool:
    return (
        _clean(row.get("flujo_editorial")) == "archivo_historico"
        and LEGACY_MEDIA_EXCEPTION in _clean(row.get("notas")).lower()
    )


def check_media_validated(row: Mapping[str, object]) -> RuleResult:
    """Gate material único para planificación y escritura Meta.

    La excepción legacy sólo existe para archivo histórico y debe estar
    documentada literalmente en `notas`. Toda media nueva debe haber pasado
    `validar_media.py` y conservar su certificación material en la cola.
    """
    if not _clean(row.get("media_path")):
        return RuleResult(False, "MEDIA_PATH_NOT_MATERIALIZED", "media_path materializado ausente", "media_path")

    if _legacy_media_validation_exception(row):
        return RuleResult(True)

    status = _clean(row.get("media_validation_status"))
    if status != "VALID":
        return RuleResult(False, "MEDIA_MATERIAL_NOT_VALIDATED", f"media_validation_status={status or '<vacío>'}", "media_validation_status")
    if not _clean(row.get("media_validation_version")):
        return RuleResult(False, "MEDIA_VALIDATION_VERSION_MISSING", "certificación sin versión", "media_validation_version")
    if not _clean(row.get("detected_media_type")):
        return RuleResult(False, "MEDIA_DETECTED_TYPE_MISSING", "certificación sin tipo detectado", "detected_media_type")
    expected_hash = _clean(row.get("media_content_sha256"))
    if not SHA256_RE.fullmatch(expected_hash):
        return RuleResult(False, "MEDIA_HASH_INVALID", "certificación sin SHA-256 material válido", "media_content_sha256")
    if not _positive_int(row.get("media_width")) or not _positive_int(row.get("media_height")):
        return RuleResult(False, "MEDIA_DIMENSIONS_INVALID", "certificación sin dimensiones positivas", "media_width")
    return RuleResult(True)


def publishable_score_threshold() -> float:
    """Devuelve el umbral canónico configurado para PUBLISHABLE.

    Falla cerrado si la política no puede leerse: no inventa un umbral.
    """
    try:
        cfg = json.loads(PRIORITY_CONFIG.read_text(encoding="utf-8"))
        return float(cfg["thresholds"]["publishable"])
    except Exception as exc:
        raise RuleError("POLICY_THRESHOLD_UNAVAILABLE", str(exc), "editorial_score") from exc


def check_publishable(row: Mapping[str, object]) -> RuleResult:
    if not _is_academic(row):
        return RuleResult(False, "NOT_ACADEMIC", "la regla de índice editorial sólo aplica a recursos académicos", "content_type")
    decision = _clean(row.get("editorial_decision"))
    if decision not in PUBLISHABLE_DECISIONS:
        return RuleResult(False, "INVALID_EDITORIAL_DECISION", f"decision={decision or '<vacía>'}", "editorial_decision")
    threshold = publishable_score_threshold()
    score = _score(row)
    if score < threshold:
        return RuleResult(False, "EDITORIAL_SCORE_BELOW_THRESHOLD", f"score={score:g}; threshold={threshold:g}", "editorial_score")

    candidate_state = _clean(row.get("candidate_status"))
    if _clean(row.get("schema_version")) == "1" and candidate_state != "ELIGIBLE":
        return RuleResult(False, "CANDIDATE_NOT_ELIGIBLE", f"candidate_status={candidate_state or '<vacío>'}", "candidate_status")
    return RuleResult(True)


def is_publishable(row: Mapping[str, object]) -> bool:
    return bool(check_publishable(row))


def check_schedulable(row: Mapping[str, object]) -> RuleResult:
    prep = _preparation_state(row)
    pub = _publication_state(row)

    if _clean(row.get("schema_version")) == "1":
        if prep != "READY":
            return RuleResult(False, "PREPARATION_NOT_READY", f"preparation_status={prep or '<vacío>'}", "preparation_status")
        if pub not in {"NOT_QUEUED", "QUEUED"}:
            return RuleResult(False, "PUBLICATION_STATE_NOT_SCHEDULABLE", f"publication_status={pub}", "publication_status")
    else:
        if prep not in LEGACY_READY_STATES:
            return RuleResult(False, "PREPARATION_NOT_READY", f"estado_editorial={prep or '<vacío>'}", "estado_editorial")
        if _clean(row.get("fecha_programada")):
            return RuleResult(False, "ALREADY_SCHEDULED", "fecha_programada ya existe", "fecha_programada")

    if _clean(row.get("text_status")) not in {"VERIFIED", "VERIFICADO"}:
        return RuleResult(False, "TEXT_NOT_VERIFIED", "texto no verificado", "text_status")
    if not _post_text(row):
        return RuleResult(False, "POST_TEXT_MISSING", "texto editorial vacío", "post_text")

    media_status = _clean(row.get("media_status"))
    if _clean(row.get("schema_version")) == "1":
        if media_status != "VERIFIED":
            return RuleResult(False, "MEDIA_NOT_VERIFIED", f"media_status={media_status or '<vacío>'}", "media_status")
    else:
        rights = _clean(row.get("media_rights_status"))
        if rights not in LEGACY_MEDIA_RIGHTS_OK:
            return RuleResult(False, "MEDIA_NOT_VERIFIED", f"media_rights_status={rights or '<vacío>'}", "media_rights_status")
    if not _media_present(row):
        return RuleResult(False, "MEDIA_MISSING", "no existe media_path/media_url", "media_path")
    material = check_media_validated(row)
    if not material:
        return material

    if _is_academic(row):
        pubcheck = check_publishable(row)
        if not pubcheck:
            return pubcheck

    if prep == "QUARANTINED":
        return RuleResult(False, "QUARANTINED", "la fila requiere reprocesamiento explícito", "preparation_status")
    return RuleResult(True)


def is_schedulable(row: Mapping[str, object]) -> bool:
    return bool(check_schedulable(row))


def check_meta_reservable(row: Mapping[str, object]) -> RuleResult:
    """Comprueba si una publicación puede adquirir una reserva Meta durable."""
    pub = _publication_state(row)
    meta = _meta_state(row)
    if _clean(row.get("schema_version")) == "1":
        if pub != "SCHEDULED":
            return RuleResult(False, "PUBLICATION_NOT_SCHEDULED", f"publication_status={pub or '<vacío>'}", "publication_status")
        if meta != "NONE":
            return RuleResult(False, "META_ALREADY_ATTEMPTED", f"meta_status={meta}", "meta_status")
    else:
        if pub != "PROGRAMADO":
            return RuleResult(False, "PUBLICATION_NOT_SCHEDULED", f"estado_editorial={pub or '<vacío>'}", "estado_editorial")
        if meta:
            return RuleResult(False, "META_ALREADY_ATTEMPTED", f"meta_attempt_status={meta}", "meta_attempt_status")
    if _post_id(row):
        return RuleResult(False, "ALREADY_HAS_META_POST", "la fila ya contiene un post ID", "meta_post_id")
    return RuleResult(True)


def check_meta_ready(row: Mapping[str, object]) -> RuleResult:
    """Comprueba si una reserva ya persistida puede materializarse en Meta."""
    pub = _publication_state(row)
    meta = _meta_state(row)

    if _clean(row.get("schema_version")) == "1":
        if pub != "SCHEDULED":
            return RuleResult(False, "PUBLICATION_NOT_SCHEDULED", f"publication_status={pub or '<vacío>'}", "publication_status")
        if meta != "RESERVED":
            return RuleResult(False, "META_RESERVATION_MISSING", f"meta_status={meta or '<vacío>'}", "meta_status")
        if not _clean(row.get("meta_attempt_id")):
            return RuleResult(False, "META_ATTEMPT_ID_MISSING", "reserva sin meta_attempt_id", "meta_attempt_id")
        if not _clean(row.get("meta_payload_hash")):
            return RuleResult(False, "META_PAYLOAD_HASH_MISSING", "reserva sin meta_payload_hash", "meta_payload_hash")
    else:
        if pub != "PROGRAMADO":
            return RuleResult(False, "PUBLICATION_NOT_SCHEDULED", f"estado_editorial={pub or '<vacío>'}", "estado_editorial")
        if meta != "IN_FLIGHT":
            return RuleResult(False, "META_RESERVATION_MISSING", f"meta_attempt_status={meta or '<vacío>'}", "meta_attempt_status")
        if not _clean(row.get("meta_attempted_at")):
            return RuleResult(False, "META_ATTEMPT_TIMESTAMP_MISSING", "IN_FLIGHT sin meta_attempted_at", "meta_attempted_at")

    if _post_id(row):
        return RuleResult(False, "ALREADY_HAS_META_POST", "la fila ya contiene un post ID", "meta_post_id")
    if not _post_text(row):
        return RuleResult(False, "POST_TEXT_MISSING", "texto editorial vacío", "post_text")
    if not _media_present(row):
        return RuleResult(False, "MEDIA_MISSING", "no existe media para publicar", "media_path")
    material = check_media_validated(row)
    if not material:
        return material
    if not _clean(row.get("fecha_programada") or row.get("scheduled_at")):
        return RuleResult(False, "SCHEDULE_MISSING", "fecha programada ausente", "scheduled_at")
    return RuleResult(True)


def is_meta_ready(row: Mapping[str, object]) -> bool:
    return bool(check_meta_ready(row))


def is_meta_ambiguous(row: Mapping[str, object]) -> bool:
    meta = _meta_state(row)
    if _clean(row.get("schema_version")) == "1":
        return meta == "AMBIGUOUS"
    return meta in LEGACY_META_AMBIGUOUS and not _post_id(row)


def validate_transition(domain: str, old_state: str, new_state: str, row: Mapping[str, object] | None = None) -> None:
    """Autoridad operacional de transición.

    La legalidad estructural pertenece a schema.py. Aquí añadimos las barreras
    operativas que impiden retries/rollbacks peligrosos.
    """
    if domain == "meta" and old_state == "AMBIGUOUS" and new_state == "REQUESTED":
        raise RuleError("META_RETRY_REQUIRES_RECONCILIATION", "AMBIGUOUS no puede reintentarse directamente")
    if domain == "publication" and old_state == "PUBLISHED" and new_state == "SCHEDULED":
        raise RuleError("PUBLISHED_ROLLBACK_FORBIDDEN", "una publicación confirmada no vuelve a SCHEDULED")
    if domain == "preparation" and old_state == "QUARANTINED" and new_state != "PENDING":
        raise RuleError("QUARANTINE_REPROCESS_REQUIRED", "QUARANTINED sólo puede volver a PENDING mediante reprocesamiento explícito")
    try:
        schema_validate_transition(domain, old_state, new_state, row)
    except SchemaError as exc:
        raise RuleError("INVALID_TRANSITION", str(exc)) from exc
