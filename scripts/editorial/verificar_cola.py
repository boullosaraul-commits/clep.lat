#!/usr/bin/env python3
"""Verificador fail-closed de la cola editorial CLEP.

El verificador no decide qué publicar ni reimplementa el pipeline. Comprueba
invariantes persistidos y delega la autoridad a:
- schema.py para estructura v1;
- editorial_rules.py para gates operativos;
- validar_media.py para certificación física real;
- preparation_contract.py para fingerprint de preparación;
- programacion.json para límites de agenda.

Las filas legacy consumadas se conservan auditables sin exigir retrospectivamente
campos que no existían. Las filas accionables o preparadas con el contrato nuevo
sí fallan cerrado ante cualquier inconsistencia.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from editorial_rules import (
    LEGACY_MEDIA_EXCEPTION,
    check_media_validated,
    check_meta_ready,
    check_publishable,
    check_schedulable,
    is_meta_ambiguous,
)
from estado_editorial import policy_fingerprint
from preparation_contract import PREPARATION_VERSION, fingerprint_from_prepared_row
from schema import SchemaError, detect_schema_version, validate_publication
from validar_media import VALIDATION_VERSION, validate_media

COLA = Path(os.getenv("CLEP_QUEUE_PATH", str(ROOT / "data/editorial/cola.csv"))).resolve()
CFG = ROOT / "data/editorial/programacion.json"

LEGACY_FLOWS = {
    "archivo_historico", "novedad", "recurso", "actividad_clep", "publicacion_clep", "otro"
}
LEGACY_STATES = {
    "IDENTIFICANDO", "OBRA_VERIFICADA", "EDICION_VERIFICADA", "OA_VERIFICADO",
    "FICHA_LISTA", "APROBADO", "REVALIDAR", "PROGRAMADO", "PUBLICADO",
    "ORIGINAL_RETIRADO", "DESCARTADO",
}
LEGACY_READY_STATES = {"FICHA_LISTA", "APROBADO"}
LEGACY_SCHEDULED_STATES = {"PROGRAMADO", "PUBLICADO", "ORIGINAL_RETIRADO"}
LEGACY_DEEP_VERIFY_STATES = {"PROGRAMADO"}
LEGACY_META_ATTEMPTS = {"", "IN_FLIGHT", "SCHEDULED", "REVIEW", "PUBLISHED", "FAILED"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"

PREPARATION_REQUIRED_FIELDS = (
    "candidate_fingerprint",
    "editorial_policy_fingerprint",
    "preparation_version",
    "preparation_fingerprint",
    "text_method",
    "text_template",
    "text_template_version",
    "media_path",
    "media_source",
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


@dataclass(frozen=True)
class VerificationIssue:
    severity: str
    code: str
    line: int
    detail: str
    field: str = ""

    def render(self) -> str:
        location = f"línea {self.line}" if self.line else "cola"
        field = f" [{self.field}]" if self.field else ""
        return f"{self.severity} {self.code} — {location}{field}: {self.detail}"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    return _clean(value).lower() in {"1", "true", "yes", "si", "sí"}


def _positive_int(value: object) -> bool:
    try:
        return int(_clean(value)) > 0
    except (TypeError, ValueError):
        return False


def _valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def _is_v1(row: Mapping[str, object]) -> bool:
    try:
        return detect_schema_version(row) == 1
    except SchemaError:
        return False


def _is_historical(row: Mapping[str, object]) -> bool:
    return _clean(row.get("flow_type")) == "HISTORICAL" or _clean(row.get("flujo_editorial")) == "archivo_historico"


def _legacy_media_exception(row: Mapping[str, object]) -> bool:
    return _is_historical(row) and LEGACY_MEDIA_EXCEPTION in _clean(row.get("notas")).lower()


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


def _has_preparation_contract(row: Mapping[str, object]) -> bool:
    return bool(_clean(row.get("preparation_version")) or _clean(row.get("preparation_fingerprint")))


def _is_scheduled(row: Mapping[str, object]) -> bool:
    if _is_v1(row):
        return _publication_state(row) in {"SCHEDULED", "PUBLISHED", "RETIRED"}
    return _publication_state(row) in LEGACY_SCHEDULED_STATES


def _requires_deep_verification(row: Mapping[str, object]) -> bool:
    if _has_preparation_contract(row):
        return True
    if _is_v1(row):
        return _preparation_state(row) in {"VALIDATED", "READY"} or _publication_state(row) in {"QUEUED", "SCHEDULED"}
    return _publication_state(row) in LEGACY_DEEP_VERIFY_STATES


def _scheduled_day_time(row: Mapping[str, object]) -> tuple[str, str]:
    day = _clean(row.get("fecha_programada"))
    tm = _clean(row.get("orden_dia"))
    scheduled_at = _clean(row.get("scheduled_at"))
    if scheduled_at and (not day or not tm):
        try:
            parsed = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            day = day or parsed.date().isoformat()
            tm = tm or parsed.strftime("%H:%M")
    return day, tm


def _add(
    issues: list[VerificationIssue],
    code: str,
    line: int,
    detail: str,
    field: str = "",
    severity: str = SEVERITY_ERROR,
) -> None:
    issues.append(VerificationIssue(severity, code, line, detail, field))


def _verify_structure(row: Mapping[str, object], line: int, issues: list[VerificationIssue]) -> None:
    raw_version = _clean(row.get("schema_version"))
    if raw_version:
        try:
            validate_publication(row)
        except SchemaError as exc:
            _add(issues, "SCHEMA_INVALID", line, str(exc), "schema_version")
        return

    flow = _clean(row.get("flujo_editorial"))
    state = _clean(row.get("estado_editorial"))
    if flow not in LEGACY_FLOWS:
        _add(issues, "LEGACY_FLOW_INVALID", line, f"flujo_editorial={flow or '<vacío>'}", "flujo_editorial")
    if state not in LEGACY_STATES:
        _add(issues, "LEGACY_STATE_INVALID", line, f"estado_editorial={state or '<vacío>'}", "estado_editorial")

    if _is_historical(row) and state == "FICHA_LISTA":
        for field, expected in (
            ("obra_estado", "OBRA_VERIFICADA"),
            ("edicion_estado", "EDICION_VERIFICADA"),
            ("oa_estado", "OA_VERIFICADO"),
        ):
            if _clean(row.get(field)) != expected:
                _add(issues, "HISTORICAL_READY_INCOMPLETE", line, f"{field} debe ser {expected}", field)
    if _is_historical(row) and _truthy(row.get("original_retirado")) and not _post_id(row):
        _add(issues, "HISTORICAL_RETIRED_WITHOUT_REPLACEMENT", line, "original retirado sin post nuevo", "post_nuevo_id")


def _verify_text(row: Mapping[str, object], line: int, cfg: Mapping[str, object], issues: list[VerificationIssue]) -> None:
    if not _requires_deep_verification(row):
        if _publication_state(row) in LEGACY_READY_STATES:
            sched = check_schedulable(row)
            if not sched:
                _add(
                    issues,
                    "LEGACY_READY_NOT_SCHEDULABLE",
                    line,
                    f"{sched.code}: {sched.detail}",
                    sched.field,
                    SEVERITY_WARNING,
                )
        return

    text = _post_text(row)
    if not text:
        _add(issues, "POST_TEXT_MISSING", line, "texto editorial vacío", "ficha_es")
        return
    text_policy = cfg.get("text_policy", {})
    max_chars = int(text_policy.get("max_chars", 900))
    max_paragraphs = int(text_policy.get("max_paragraphs", 5))
    if len(text) > max_chars:
        _add(issues, "TEXT_OVERFLOW", line, f"{len(text)} > {max_chars} caracteres", "ficha_es")
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) > max_paragraphs:
        _add(issues, "TEXT_TOO_MANY_PARAGRAPHS", line, f"{len(paragraphs)} > {max_paragraphs}", "ficha_es")
    if _clean(row.get("text_status")) not in {"VERIFIED", "VERIFICADO"}:
        _add(issues, "TEXT_NOT_VERIFIED", line, "text_status no está verificado", "text_status")
    if not _clean(row.get("text_method")):
        _add(issues, "TEXT_METHOD_MISSING", line, "text_method ausente", "text_method")
    if not _clean(row.get("text_template")):
        _add(issues, "TEXT_TEMPLATE_MISSING", line, "text_template ausente", "text_template")
    if _has_preparation_contract(row) and not _positive_int(row.get("text_template_version")):
        _add(issues, "TEXT_TEMPLATE_VERSION_INVALID", line, "text_template_version debe ser positivo", "text_template_version")

    translation_fields = (
        "translation_status", "translation_method", "translation_engine",
        "translation_source_language", "translation_target_language", "translation_disclosure",
    )
    if any(_clean(row.get(field)) for field in translation_fields):
        missing = [field for field in translation_fields if not _clean(row.get(field))]
        if missing:
            _add(issues, "TRANSLATION_PROVENANCE_INCOMPLETE", line, ", ".join(missing), missing[0])
        method_engine = (_clean(row.get("translation_method")) + " " + _clean(row.get("translation_engine"))).lower()
        if any(token in method_engine for token in ("generative", "llm", "gpt", "gemini", "claude")):
            _add(issues, "GENERATIVE_TRANSLATION_FORBIDDEN", line, "traducción generativa detectada", "translation_method")


def _verify_media(row: Mapping[str, object], line: int, issues: list[VerificationIssue]) -> None:
    deep = _requires_deep_verification(row)
    material_gate = check_media_validated(row)
    if not deep:
        if _publication_state(row) in LEGACY_READY_STATES and not material_gate:
            _add(
                issues,
                "LEGACY_READY_MEDIA_NOT_CERTIFIED",
                line,
                f"{material_gate.code}: {material_gate.detail}",
                material_gate.field,
                SEVERITY_WARNING,
            )
        return

    if not material_gate:
        _add(issues, material_gate.code, line, material_gate.detail, material_gate.field)
        return
    if _legacy_media_exception(row):
        _add(
            issues,
            "LEGACY_MEDIA_VALIDATION_EXCEPTION",
            line,
            "archivo histórico conserva excepción material documentada",
            "notas",
            SEVERITY_WARNING,
        )
        return

    result = validate_media(row)
    if not result.valid:
        for error in result.errors:
            _add(issues, error.code, line, error.detail, error.field)
        return

    persisted_version = _clean(row.get("media_validation_version"))
    if persisted_version != str(result.validation_version):
        _add(
            issues,
            "MEDIA_VALIDATION_VERSION_STALE",
            line,
            f"persistida={persisted_version or '<vacío>'}; actual={result.validation_version}",
            "media_validation_version",
        )
    if result.validation_version != VALIDATION_VERSION:
        _add(issues, "MEDIA_VALIDATOR_VERSION_INTERNAL_MISMATCH", line, f"resultado={result.validation_version}; módulo={VALIDATION_VERSION}")
    if _clean(row.get("detected_media_type")) != result.detected_type:
        _add(
            issues,
            "MEDIA_DETECTED_TYPE_DRIFT",
            line,
            f"persistido={_clean(row.get('detected_media_type'))}; real={result.detected_type}",
            "detected_media_type",
        )
    if _clean(row.get("media_width")) != str(result.width or "") or _clean(row.get("media_height")) != str(result.height or ""):
        _add(
            issues,
            "MEDIA_DIMENSIONS_DRIFT",
            line,
            f"persistidas={_clean(row.get('media_width'))}x{_clean(row.get('media_height'))}; reales={result.width}x{result.height}",
            "media_width",
        )
    if _clean(row.get("media_bytes_size")) and _clean(row.get("media_bytes_size")) != str(result.bytes_size):
        _add(
            issues,
            "MEDIA_BYTES_SIZE_DRIFT",
            line,
            f"persistido={_clean(row.get('media_bytes_size'))}; real={result.bytes_size}",
            "media_bytes_size",
        )


def _verify_preparation(
    row: Mapping[str, object],
    line: int,
    current_policy_fp: str,
    issues: list[VerificationIssue],
) -> None:
    if not _has_preparation_contract(row):
        return
    missing = [field for field in PREPARATION_REQUIRED_FIELDS if not _clean(row.get(field))]
    if missing:
        _add(issues, "PREPARATION_PROVENANCE_INCOMPLETE", line, ", ".join(missing), missing[0])
        return
    if _clean(row.get("preparation_version")) != str(PREPARATION_VERSION):
        _add(
            issues,
            "PREPARATION_VERSION_UNSUPPORTED",
            line,
            f"persistida={_clean(row.get('preparation_version'))}; soportada={PREPARATION_VERSION}",
            "preparation_version",
        )
    stored = _clean(row.get("preparation_fingerprint"))
    if not SHA256_RE.fullmatch(stored):
        _add(issues, "PREPARATION_FINGERPRINT_INVALID", line, "fingerprint no es SHA-256", "preparation_fingerprint")
        return
    recomputed = fingerprint_from_prepared_row(row)
    if stored.lower() != recomputed.lower():
        _add(
            issues,
            "PREPARATION_FINGERPRINT_MISMATCH",
            line,
            f"persistido={stored}; recalculado={recomputed}",
            "preparation_fingerprint",
        )
    stored_policy = _clean(row.get("editorial_policy_fingerprint"))
    if stored_policy and current_policy_fp and stored_policy != current_policy_fp:
        _add(
            issues,
            "PREPARATION_POLICY_STALE",
            line,
            "la preparación fue producida con una política editorial distinta de la vigente",
            "editorial_policy_fingerprint",
        )


def _verify_meta(row: Mapping[str, object], line: int, issues: list[VerificationIssue]) -> None:
    state = _publication_state(row)
    meta = _meta_state(row)
    post_id = _post_id(row)

    if is_meta_ambiguous(row):
        if state == "REVALIDAR" or _preparation_state(row) == "QUARANTINED":
            _add(
                issues,
                "META_RECONCILIATION_REQUIRED",
                line,
                "estado Meta ambiguo está inmovilizado y requiere reconciliación explícita",
                "meta_status",
                SEVERITY_WARNING,
            )
        else:
            _add(
                issues,
                "META_AMBIGUOUS_REQUIRES_RECONCILIATION",
                line,
                "estado Meta ambiguo: no puede reintentarse ni avanzar",
                "meta_status",
            )

    if _is_v1(row):
        if meta == "RESERVED":
            ready = check_meta_ready(row)
            if not ready:
                _add(issues, ready.code, line, ready.detail, ready.field)
        return

    if meta not in LEGACY_META_ATTEMPTS:
        _add(issues, "LEGACY_META_STATUS_INVALID", line, f"meta_attempt_status={meta}", "meta_attempt_status")
    if state == "PROGRAMADO":
        if not _clean(row.get("fecha_programada")) or not _clean(row.get("orden_dia")):
            _add(issues, "SCHEDULE_MISSING", line, "PROGRAMADO sin fecha/hora", "fecha_programada")
        if meta == "IN_FLIGHT":
            ready = check_meta_ready(row)
            if not ready:
                _add(issues, ready.code, line, ready.detail, ready.field)
        if post_id and meta != "SCHEDULED":
            _add(issues, "META_POST_WITHOUT_SCHEDULED_STATUS", line, "PROGRAMADO tiene post ID pero Meta no está SCHEDULED", "meta_attempt_status")
        if meta == "SCHEDULED" and not post_id:
            _add(issues, "META_SCHEDULED_WITHOUT_POST", line, "Meta SCHEDULED sin post ID", "post_nuevo_id")
    elif state == "PUBLICADO":
        if meta and meta != "PUBLISHED":
            _add(issues, "PUBLISHED_META_STATUS_MISMATCH", line, f"PUBLICADO con meta_attempt_status={meta}", "meta_attempt_status")
        if not post_id:
            _add(issues, "PUBLISHED_WITHOUT_META_POST", line, "PUBLICADO sin post_nuevo_id", "post_nuevo_id")
    elif state == "REVALIDAR" and (post_id or meta == "SCHEDULED"):
        _add(
            issues,
            "META_LOCAL_DIVERGENCE_RECONCILE",
            line,
            "fila local REVALIDAR conserva evidencia Meta; no avanzar hasta reconciliar",
            "estado_editorial",
            SEVERITY_WARNING,
        )


def _source_key(row: Mapping[str, object]) -> str:
    notes = _clean(row.get("notas"))
    match = re.search(r"venue=([^;|]+)", notes, re.IGNORECASE)
    if match and match.group(1).strip():
        return match.group(1).strip().lower()
    return _clean(row.get("oa_fuente")).lower()


def _is_doab(row: Mapping[str, object]) -> bool:
    text = " ".join(
        [_clean(row.get("oa_fuente")), _clean(row.get("notas")), _clean(row.get("url_original"))]
    ).lower()
    return "doab" in text or "directory of open access books" in text


def _verify_schedule(
    rows_with_lines: Iterable[tuple[int, Mapping[str, object]]],
    cfg: Mapping[str, object],
    issues: list[VerificationIssue],
) -> None:
    current_cfg = cfg.get("contenido_actual", {})
    new_cfg = current_cfg.get("nuevos", {})
    no_text_cfg = current_cfg.get("no_textos", {})
    hist_cfg = cfg.get("archivo_historico", {})
    diversity = new_cfg.get("diversidad", {})
    elastic = new_cfg.get("regla_elastica", {})

    total_cap = int(cfg.get("maximo_total_diario", len(cfg.get("slots_preferentes", [])) or 17))
    new_normal = int(new_cfg.get("maximo_diario_inicial", 6))
    new_exceptional = int(new_cfg.get("maximo_diario_excepcional", new_normal))
    high_threshold = float(elastic.get("umbral_indice_editorial_10", 9))
    high_required = int(elastic.get("minimo_candidatos_sobresalientes_para_expandir", 5))
    hist_cap = int(hist_cfg.get("maximo_diario_inicial", 6))
    nontext_cap = int(no_text_cfg.get("maximo_diario_inicial", 4))
    nontext_types = set(no_text_cfg.get("tipos", [])) | {"convocatoria_evento", "dataset_grafica"}
    same_type_cap = int(diversity.get("maximo_mismo_tipo_diario", 3))
    same_source_cap = int(diversity.get("maximo_misma_institucion_serie_diario", 2))
    doab_cfg = diversity.get("doab", {})
    doab_cap = int(doab_cfg.get("maximo_diario_excepcional", doab_cfg.get("maximo_diario_normal", 2)))
    min_gap = int(cfg.get("minimum_gap_minutes", 60))

    daily: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "hist": 0,
            "new": 0,
            "nontext": 0,
            "high": 0,
            "doab": 0,
            "types": Counter(),
            "sources": Counter(),
            "times": [],
        }
    )

    for line, row in rows_with_lines:
        day, tm = _scheduled_day_time(row)
        scheduled = _is_scheduled(row)
        if day:
            try:
                date.fromisoformat(day)
            except ValueError:
                _add(issues, "SCHEDULE_DATE_INVALID", line, f"fecha={day}", "fecha_programada")
        if tm and not _valid_time(tm):
            _add(issues, "SCHEDULE_TIME_INVALID", line, f"hora={tm}; se espera HH:MM", "orden_dia")
        if scheduled and (not day or not tm):
            _add(issues, "SCHEDULE_MISSING", line, "estado programado/publicado sin fecha y hora completas")
        if not scheduled and (day or tm) and _publication_state(row) != "REVALIDAR":
            _add(
                issues,
                "SCHEDULE_FIELDS_WITHOUT_SCHEDULED_STATE",
                line,
                "fecha/hora presentes en fila que no está programada",
                "fecha_programada",
            )
        if not scheduled or not day:
            continue

        bucket = daily[day]
        if tm and _valid_time(tm):
            bucket["times"].append((tm, line))
        if _is_historical(row):
            bucket["hist"] += 1
            continue
        typ = _clean(row.get("content_type") or row.get("tipo_recurso") or "otro")
        if typ in nontext_types:
            bucket["nontext"] += 1
            continue
        bucket["new"] += 1
        try:
            score = float(row.get("editorial_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if score >= high_threshold:
            bucket["high"] += 1
        publishable = check_publishable(row)
        if not publishable:
            _add(issues, publishable.code, line, publishable.detail, publishable.field)
        if _is_doab(row):
            bucket["doab"] += 1
        bucket["types"][typ] += 1
        source = _source_key(row)
        if source:
            bucket["sources"][source] += 1

    for day, bucket in sorted(daily.items()):
        total = bucket["hist"] + bucket["new"] + bucket["nontext"]
        if total > total_cap:
            _add(issues, "DAILY_TOTAL_CAP_EXCEEDED", 0, f"{day}: total={total} > {total_cap}")
        if bucket["hist"] > hist_cap:
            _add(issues, "DAILY_HISTORICAL_CAP_EXCEEDED", 0, f"{day}: históricos={bucket['hist']} > {hist_cap}")
        if bucket["nontext"] > nontext_cap:
            _add(issues, "DAILY_NONTEXT_CAP_EXCEEDED", 0, f"{day}: no-texto={bucket['nontext']} > {nontext_cap}")
        if bucket["new"] > new_exceptional:
            _add(issues, "DAILY_CURRENT_CAP_EXCEEDED", 0, f"{day}: novedades={bucket['new']} > {new_exceptional}")
        elif bucket["new"] > new_normal and bucket["high"] < high_required:
            _add(
                issues,
                "DAILY_ELASTIC_CAP_REQUIREMENT_NOT_MET",
                0,
                f"{day}: novedades={bucket['new']} > {new_normal}, pero sobresalientes={bucket['high']} < {high_required}",
            )
        if bucket["doab"] > doab_cap:
            _add(issues, "DAILY_DOAB_CAP_EXCEEDED", 0, f"{day}: DOAB={bucket['doab']} > {doab_cap}")
        for typ, count in bucket["types"].items():
            if count > same_type_cap:
                _add(issues, "DAILY_TYPE_CAP_EXCEEDED", 0, f"{day}: tipo {typ}={count} > {same_type_cap}")
        for source, count in bucket["sources"].items():
            if count > same_source_cap:
                _add(issues, "DAILY_SOURCE_CAP_EXCEEDED", 0, f"{day}: fuente/serie {source}={count} > {same_source_cap}")

        times = bucket["times"]
        counts = Counter(tm for tm, _ in times)
        for tm, count in sorted(counts.items()):
            if count > 1:
                lines = [str(line) for value, line in times if value == tm]
                _add(issues, "SCHEDULE_TIME_DUPLICATE", 0, f"{day} {tm}: líneas {', '.join(lines)}")
        minutes = sorted((int(tm[:2]) * 60 + int(tm[3:]), tm, line) for tm, line in times)
        for (left, left_tm, left_line), (right, right_tm, right_line) in zip(minutes, minutes[1:]):
            if right - left < min_gap:
                _add(
                    issues,
                    "SCHEDULE_GAP_TOO_SMALL",
                    0,
                    f"{day}: {left_tm} (línea {left_line}) → {right_tm} (línea {right_line}) = {right-left} min < {min_gap}",
                )


def verify_rows(
    rows: list[Mapping[str, object]],
    *,
    cfg: Mapping[str, object] | None = None,
    current_policy_fp: str | None = None,
) -> list[VerificationIssue]:
    cfg = cfg or json.loads(CFG.read_text(encoding="utf-8"))
    current_policy_fp = current_policy_fp if current_policy_fp is not None else policy_fingerprint()
    issues: list[VerificationIssue] = []

    ids = Counter(_clean(row.get("editorial_id")) for row in rows if _clean(row.get("editorial_id")))
    for editorial_id, count in sorted(ids.items()):
        if count > 1:
            _add(issues, "EDITORIAL_ID_DUPLICATE", 0, f"{editorial_id}: {count} registros", "editorial_id")

    rows_with_lines = list(enumerate(rows, start=2))
    for line, row in rows_with_lines:
        _verify_structure(row, line, issues)
        _verify_text(row, line, cfg, issues)
        _verify_media(row, line, issues)
        _verify_preparation(row, line, current_policy_fp, issues)
        _verify_meta(row, line, issues)

    _verify_schedule(rows_with_lines, cfg, issues)
    return issues


def main() -> int:
    with COLA.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    issues = verify_rows(rows)
    errors = [issue for issue in issues if issue.severity == SEVERITY_ERROR]
    warnings = [issue for issue in issues if issue.severity == SEVERITY_WARNING]

    print("CLEP — VERIFICACIÓN DE COLA")
    print("=" * 72)
    print(f"Registros: {len(rows)}")
    print(f"Errores: {len(errors)} | Advertencias: {len(warnings)}")

    if errors:
        print("\nERRORES")
        for issue in errors:
            print(" -", issue.render())
    if warnings:
        print("\nADVERTENCIAS")
        for issue in warnings:
            print(" -", issue.render())
    if errors:
        return 1
    print("\nOK — cola sin inconsistencias bloqueantes; warnings requieren seguimiento pero no habilitan avance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
