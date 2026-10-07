#!/usr/bin/env python3
"""Registro persistente e idempotente de cuarentena editorial CLEP.

La cuarentena es una proyección operacional separada de la cola publicable.
Nunca convierte por sí misma un candidato en publicable ni programa reintentos.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping, MutableMapping

QUARANTINE_VERSION = 1
STATUS_OPEN = "OPEN"
STATUS_RESOLVED = "RESOLVED"

QUARANTINE_FIELDS = (
    "quarantine_version",
    "candidate_id",
    "preparation_status",
    "quarantine_status",
    "quarantine_reason",
    "quarantine_error_code",
    "quarantine_step",
    "quarantined_at",
    "resolved_at",
    "error_class",
    "error_detail",
    "quarantine_fingerprint",
)

BLOCK_NOTE_RE = re.compile(
    r"preparación bloqueada \[(?P<stage>[^\]]+)\] "
    r"(?P<code>[^:|]+): (?P<detail>.*?)(?=\s+\|\s+preparación bloqueada \[|$)"
)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def latest_blocked_note(notes: object) -> tuple[str, str, str] | None:
    matches = list(BLOCK_NOTE_RE.finditer(str(notes or "")))
    if not matches:
        return None
    match = matches[-1]
    return (
        clean(match.group("stage")),
        clean(match.group("code")),
        clean(match.group("detail")),
    )


def quarantine_reason(stage: str) -> str:
    stage = clean(stage)
    if stage == "TEXT_RENDER":
        return "TEXT_ERROR"
    if stage == "MEDIA_RESOLVE_ACQUIRE_VALIDATE":
        return "MEDIA_ERROR"
    return "STATE_INCONSISTENCY"


def error_class(code: str) -> str:
    code = clean(code)
    if code in {
        "MEDIA_DOWNLOAD_FAILED",
        "MEDIA_CAPTURE_BROWSER_MISSING",
        "MEDIA_CAPTURE_FAILED",
    }:
        return "TEMPORARY"
    if code == "MEDIA_FALLBACK_EXHAUSTED":
        return "AMBIGUOUS"
    return "PERMANENT"


def fingerprint(candidate_id: str, stage: str, code: str, detail: str) -> str:
    payload = {
        "candidate_id": clean(candidate_id),
        "stage": clean(stage),
        "code": clean(code),
        "detail": clean(detail),
        "version": QUARANTINE_VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _index(rows: list[MutableMapping[str, str]]) -> dict[str, MutableMapping[str, str]]:
    return {
        clean(row.get("candidate_id")): row
        for row in rows
        if clean(row.get("candidate_id"))
    }


def upsert_open(
    rows: list[MutableMapping[str, str]],
    *,
    candidate_id: str,
    stage: str,
    code: str,
    detail: str,
    quarantined_at: str,
) -> bool:
    """Crea/actualiza una cuarentena abierta. Misma causa => no-op exacto."""
    candidate_id = clean(candidate_id)
    quarantined_at = clean(quarantined_at)
    if not candidate_id:
        raise ValueError("candidate_id es obligatorio")
    if not quarantined_at:
        raise ValueError("quarantined_at es obligatorio")
    fp = fingerprint(candidate_id, stage, code, detail)
    existing = _index(rows).get(candidate_id)
    if existing and existing.get("quarantine_status") == STATUS_OPEN and existing.get("quarantine_fingerprint") == fp:
        return False

    payload = {
        "quarantine_version": str(QUARANTINE_VERSION),
        "candidate_id": candidate_id,
        "preparation_status": "QUARANTINED",
        "quarantine_status": STATUS_OPEN,
        "quarantine_reason": quarantine_reason(stage),
        "quarantine_error_code": clean(code) or "UNKNOWN",
        "quarantine_step": clean(stage) or "UNKNOWN",
        "quarantined_at": quarantined_at,
        "resolved_at": "",
        "error_class": error_class(code),
        "error_detail": clean(detail),
        "quarantine_fingerprint": fp,
    }
    if existing is None:
        rows.append(payload)
    else:
        existing.clear()
        existing.update(payload)
    return True


def resolve(rows: list[MutableMapping[str, str]], candidate_id: str, resolved_at: str) -> bool:
    candidate_id = clean(candidate_id)
    resolved_at = clean(resolved_at)
    existing = _index(rows).get(candidate_id)
    if not existing or existing.get("quarantine_status") != STATUS_OPEN:
        return False
    if not resolved_at:
        raise ValueError("resolved_at es obligatorio")
    existing["quarantine_status"] = STATUS_RESOLVED
    existing["resolved_at"] = resolved_at
    return True


def normalized_row(row: Mapping[str, object]) -> dict[str, str]:
    return {field: clean(row.get(field)) for field in QUARANTINE_FIELDS}
