#!/usr/bin/env python3
"""Auditor/migrador manual de filas NEP heredadas.

No forma parte del pipeline productivo. `--check` es read-only y falla si
reaparecen identidades/títulos legacy o duplicados por handle. `--apply` es la
única vía que muta candidatos.csv y existe sólo para reparación deliberada.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/editorial/candidatos.csv"


def handle_from(value):
    value = (value or "").strip()
    if value.lower().startswith("repec:"):
        return value
    try:
        candidate = parse_qs(urlparse(value).query).get("u", [""])[0]
        return candidate if candidate.lower().startswith("repec:") else ""
    except Exception:
        return ""


def dkey(handle):
    return hashlib.sha256(("repec:" + handle.lower()).encode()).hexdigest()[:24]


def rank(row):
    try:
        priority = int(row.get("priority") or 999)
    except ValueError:
        priority = 999
    return priority, row.get("detected_at") or "", row.get("candidate_id") or ""


def audit_rows(rows):
    issues = []
    handles = []
    for index, row in enumerate(rows, start=2):
        if row.get("source_type") != "nep_report":
            continue
        handle = (
            handle_from(row.get("source_item_id"))
            or handle_from(row.get("source_url"))
            or handle_from(row.get("title"))
        )
        if not handle:
            continue
        handles.append(handle.lower())
        if row.get("source_item_id") != handle:
            issues.append(f"línea {index}: source_item_id legacy")
        if (row.get("title") or "").lower().startswith(("http://", "https://")):
            issues.append(f"línea {index}: título URL legacy")
        if row.get("dedupe_key") != dkey(handle):
            issues.append(f"línea {index}: dedupe_key legacy")
    counts = Counter(handles)
    for handle, count in sorted(counts.items()):
        if count > 1:
            issues.append(f"handle duplicado {handle}: {count}")
    return issues


def migrate_rows(rows):
    passthrough = []
    groups = {}
    migrated = 0
    for original in rows:
        row = dict(original)
        if row.get("source_type") != "nep_report":
            passthrough.append(row)
            continue
        handle = (
            handle_from(row.get("source_item_id"))
            or handle_from(row.get("source_url"))
            or handle_from(row.get("title"))
        )
        if not handle:
            passthrough.append(row)
            continue
        if row.get("source_item_id") != handle:
            migrated += 1
        row["source_item_id"] = handle
        if (row.get("title") or "").lower().startswith(("http://", "https://")):
            row.update(
                {
                    "title": "",
                    "authors": "",
                    "summary": "",
                    "published_at": "",
                    "access_url": "",
                    "doi": "",
                    "language": "",
                    "status": "METADATOS_PENDIENTES",
                    "oa_status": "POR_VERIFICAR",
                }
            )
        row["dedupe_key"] = dkey(handle)
        marker = "RePEc handle: " + handle
        notes = row.get("notes") or ""
        if marker not in notes:
            notes = (notes + " | " + marker).strip(" |")
        migration_marker = "migrado desde ingestión NEP heredada"
        if migration_marker not in notes:
            notes = (notes + " | " + migration_marker).strip(" |")
        row["notes"] = notes
        groups.setdefault(handle.lower(), []).append(row)

    kept = []
    collapsed = 0
    for _handle, grouped in groups.items():
        grouped.sort(key=rank)
        base = grouped[0]
        if len(grouped) > 1:
            collapsed += len(grouped) - 1
            sources = sorted({x.get("source_id", "") for x in grouped if x.get("source_id")})
            marker = "reportes NEP: " + ", ".join(sources)
            if marker not in (base.get("notes") or ""):
                base["notes"] = ((base.get("notes") or "") + " | " + marker).strip(" |")
        kept.append(base)

    output = passthrough + kept
    output.sort(key=lambda row: (row.get("detected_at") or "", row.get("candidate_id") or ""))
    return output, migrated, collapsed


def load_rows(path=P):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="audita sin escribir")
    mode.add_argument("--apply", action="store_true", help="aplica reparación legacy deliberada")
    args = parser.parse_args(argv)

    rows, fields = load_rows()
    if args.check:
        issues = audit_rows(rows)
        if issues:
            print("NEP legacy detectado:")
            for issue in issues:
                print(" -", issue)
            return 1
        print(f"NEP legacy check OK: {len(rows)} candidatos; sin reparación pendiente.")
        return 0

    output, migrated, collapsed = migrate_rows(rows)
    with P.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    print(
        f"Filas NEP migradas: {migrated}; duplicados colapsados: {collapsed}; total: {len(output)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
