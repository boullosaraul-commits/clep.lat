#!/usr/bin/env python3
"""Materializa en CSV la cuarentena derivada de preparación bloqueada.

Lee únicamente evidencia ya persistida por preparar_publicacion.py:
- notas `preparación bloqueada [...] CODE: detail` abren/actualizan cuarentena;
- status=FICHA_LISTA resuelve una cuarentena abierta.

No reejecuta preparación, no toca Meta y no programa reintentos.
"""
from __future__ import annotations

import argparse
import csv
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cuarentena import QUARANTINE_FIELDS, latest_blocked_note, normalized_row, resolve, upsert_open

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = Path(
    os.getenv("CLEP_CANDIDATES_PATH", str(ROOT / "data/editorial/candidatos.csv"))
).resolve()
DEFAULT_QUARANTINE = Path(
    os.getenv("CLEP_QUARANTINE_PATH", str(ROOT / "data/editorial/cuarentena.csv"))
).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_fields = list(fields)
    for field in QUARANTINE_FIELDS:
        if field not in normalized_fields:
            normalized_fields.append(field)
    if not normalized_fields:
        normalized_fields = list(QUARANTINE_FIELDS)

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
            writer = csv.DictWriter(handle, fieldnames=normalized_fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in normalized_fields})
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


def materialize(candidates: list[dict[str, str]], rows: list[dict[str, str]], now: str) -> tuple[int, int]:
    opened = resolved = 0
    for candidate in candidates:
        cid = (candidate.get("candidate_id") or "").strip()
        if not cid:
            continue
        if (candidate.get("status") or "").strip() == "FICHA_LISTA":
            if resolve(rows, cid, now):
                resolved += 1
            continue
        blocked = latest_blocked_note(candidate.get("notes"))
        if blocked is None:
            continue
        stage, code, detail = blocked
        if upsert_open(
            rows,
            candidate_id=cid,
            stage=stage,
            code=code,
            detail=detail,
            quarantined_at=now,
        ):
            opened += 1
    return opened, resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE)
    parser.add_argument("--now", default="")
    args = parser.parse_args()

    candidates, _ = read_csv(args.candidates.resolve())
    existing, fields = read_csv(args.quarantine.resolve())
    rows = [normalized_row(row) for row in existing]
    now = (args.now or utc_now()).strip()
    opened, resolved_count = materialize(candidates, rows, now)
    written = write_csv_atomic(args.quarantine.resolve(), fields, rows)
    print(
        f"Cuarentena: abiertas/actualizadas={opened}; resueltas={resolved_count}; "
        f"registros={len(rows)}; write={int(written)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
