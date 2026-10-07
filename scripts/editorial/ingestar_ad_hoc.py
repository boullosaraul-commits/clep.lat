#!/usr/bin/env python3
"""Ingesta determinista de solicitudes ad hoc creadas desde chat.

La interfaz de chat escribe JSON canónico v1 en data/editorial/ad_hoc/*.json.
Este adaptador valida ese contrato y lo proyecta al CSV operacional legacy que
consume actualmente el pipeline. La solicitud v1 permanece como fuente trazable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from schema import CURRENT_SCHEMA_VERSION, SchemaError, validate_candidate

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOX = Path(
    os.getenv("CLEP_ADHOC_INBOX", str(ROOT / "data/editorial/ad_hoc"))
).resolve()
DEFAULT_CANDIDATES = Path(
    os.getenv("CLEP_CANDIDATES_PATH", str(ROOT / "data/editorial/candidatos.csv"))
).resolve()

CONTENT_TYPE_TO_OPERATIONAL = {
    "PAPER": "paper",
    "BOOK": "book",
    "CHAPTER": "chapter",
    "REPORT": "report",
    "POLICY_BRIEF": "policy_brief",
    "SPECIAL_ISSUE": "special_issue",
    "THESIS": "thesis",
    "EDITION_TRANSLATION": "edition_translation",
    "DATASET": "dataset_grafica",
    "CHART": "dataset_grafica",
    "EVENT": "convocatoria_evento",
    "CALL": "convocatoria_evento",
    "VIDEO": "video",
    "RESOURCE": "recurso",
}

DEFAULT_FIELDS = [
    "candidate_id", "source_id", "source_type", "content_type", "title", "authors",
    "summary", "summary_es", "publication_year", "published_at", "language", "venue",
    "source_name", "source_url", "access_url", "doi", "area_clep", "notes", "status",
    "relevance_score", "relevance_reasons", "editorial_score", "editorial_decision",
    "oa_status", "access_status", "flow_type", "origin", "request_schema_version",
    "request_file", "indicator_or_dataset", "geography", "reference_period",
    "value_or_change", "organizer", "date_or_deadline", "speaker_or_organization",
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _https(value: object) -> bool:
    return clean(value).startswith("https://")


def deterministic_candidate_id(title: str, url: str) -> str:
    raw = json.dumps(
        {"title": clean(title).casefold(), "url": clean(url)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    return f"CAND-CHAT-{digest}"


def canonical_request(raw: Mapping[str, Any], request_file: str = "") -> dict[str, Any]:
    title = clean(raw.get("title"))
    content_type = clean(raw.get("content_type")).upper()
    url = clean(raw.get("access_url") or raw.get("source_url"))
    if not title:
        raise SchemaError("solicitud ad hoc sin title")
    if content_type not in CONTENT_TYPE_TO_OPERATIONAL:
        raise SchemaError(f"content_type ad hoc no soportado productivamente: {content_type!r}")
    if not _https(url):
        raise SchemaError("solicitud ad hoc requiere access_url/source_url HTTPS")

    candidate_id = clean(raw.get("candidate_id")) or deterministic_candidate_id(title, url)
    row: dict[str, Any] = dict(raw)
    row.update(
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "source_id": clean(raw.get("source_id")) or "chat",
            "source_type": clean(raw.get("source_type")) or "chat_ad_hoc",
            "title": title,
            "content_type": content_type,
            "candidate_status": "DISCOVERED",
            "flow_type": "AD_HOC",
            "origin": "CHAT",
            "access_status": clean(raw.get("access_status")) or "UNKNOWN",
            "oa_status": clean(raw.get("oa_status")) or "UNKNOWN",
            "rights_status": clean(raw.get("rights_status")) or "UNKNOWN",
            "source_url": clean(raw.get("source_url")) or url,
            "access_url": url,
        }
    )
    if request_file:
        row["request_file"] = request_file
    validate_candidate(row)
    return row


def operational_row(request: Mapping[str, Any]) -> dict[str, str]:
    kind = CONTENT_TYPE_TO_OPERATIONAL[clean(request.get("content_type")).upper()]
    request_file = clean(request.get("request_file"))
    note_parts = ["origin=CHAT", "flow_type=AD_HOC", "request_schema_version=1"]
    if request_file:
        note_parts.append(f"request_file={request_file}")
    supplied_notes = clean(request.get("notes"))
    if supplied_notes:
        note_parts.append(supplied_notes)

    return {
        "candidate_id": clean(request.get("candidate_id")),
        "source_id": clean(request.get("source_id")) or "chat",
        "source_type": "chat_ad_hoc",
        "content_type": kind,
        "title": clean(request.get("title")),
        "authors": clean(request.get("authors")),
        "summary": clean(request.get("summary") or request.get("source_summary")),
        "summary_es": clean(request.get("summary_es") or request.get("source_summary_es")),
        "publication_year": clean(request.get("publication_year")),
        "published_at": clean(request.get("published_at")),
        "language": clean(request.get("language") or request.get("source_language")),
        "venue": clean(request.get("venue")),
        "source_name": clean(request.get("source_name")) or "Chat ad hoc",
        "source_url": clean(request.get("source_url")),
        "access_url": clean(request.get("access_url")),
        "doi": clean(request.get("doi")),
        "area_clep": clean(request.get("area_clep")),
        "notes": " | ".join(note_parts),
        "status": "DETECTADO",
        "relevance_score": "",
        "relevance_reasons": "",
        "editorial_score": "",
        "editorial_decision": "",
        "oa_status": "UNKNOWN",
        "access_status": "UNKNOWN",
        "flow_type": "AD_HOC",
        "origin": "CHAT",
        "request_schema_version": "1",
        "request_file": request_file,
        "indicator_or_dataset": clean(request.get("indicator_or_dataset")),
        "geography": clean(request.get("geography")),
        "reference_period": clean(request.get("reference_period")),
        "value_or_change": clean(request.get("value_or_change")),
        "organizer": clean(request.get("organizer")),
        "date_or_deadline": clean(request.get("date_or_deadline")),
        "speaker_or_organization": clean(request.get("speaker_or_organization")),
    }


def read_candidates(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_candidates_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> bool:
    merged_fields = list(fields)
    for field in DEFAULT_FIELDS:
        if field not in merged_fields:
            merged_fields.append(field)
    for row in rows:
        for field in row:
            if field not in merged_fields:
                merged_fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=merged_fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in merged_fields})
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


def ingest_requests(
    request_paths: list[Path], candidates: list[dict[str, str]]
) -> tuple[int, int]:
    by_id = {clean(row.get("candidate_id")): row for row in candidates if clean(row.get("candidate_id"))}
    added = unchanged = 0
    for path in sorted(request_paths, key=lambda p: p.as_posix()):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SchemaError(f"solicitud ad hoc debe ser objeto JSON: {path}")
        canonical = canonical_request(raw, path.as_posix())
        projected = operational_row(canonical)
        cid = projected["candidate_id"]
        existing = by_id.get(cid)
        if existing is None:
            candidates.append(projected)
            by_id[cid] = projected
            added += 1
            continue
        if clean(existing.get("title")) != projected["title"] or clean(existing.get("access_url") or existing.get("source_url")) != projected["access_url"]:
            raise SchemaError(f"conflicto de candidate_id ad hoc: {cid}")
        changed = False
        for key, value in projected.items():
            if value and not clean(existing.get(key)):
                existing[key] = value
                changed = True
        if changed:
            added += 1
        else:
            unchanged += 1
    return added, unchanged


def request_paths(inbox: Path, explicit: list[Path]) -> list[Path]:
    if explicit:
        return [path.resolve() for path in explicit]
    if not inbox.exists():
        return []
    return [path for path in inbox.glob("*.json") if path.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--request", type=Path, action="append", default=[])
    args = parser.parse_args()

    paths = request_paths(args.inbox.resolve(), args.request)
    rows, fields = read_candidates(args.candidates.resolve())
    added, unchanged = ingest_requests(paths, rows)
    written = write_candidates_atomic(args.candidates.resolve(), fields, rows) if paths else False
    print(
        f"Ad hoc: solicitudes={len(paths)}; añadidas/actualizadas={added}; "
        f"sin_cambios={unchanged}; write={int(written)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
