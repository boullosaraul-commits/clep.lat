#!/usr/bin/env python3
"""E2E offline multiformato: candidatos -> preparación completa -> cola.

Cubre las 12 familias efectivamente soportadas por el adaptador textual y media,
con fallback determinista sin red, idempotencia y bloqueo de tipos sin adaptador.
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

SUPPORTED = (
    "paper", "book", "chapter", "report", "policy_brief", "special_issue",
    "thesis", "edition_translation", "dataset_grafica", "convocatoria_evento",
    "video", "recurso",
)
UNSUPPORTED = ("teaching_material", "institutional")

CAND_FIELDS = [
    "candidate_id", "source_id", "source_type", "source_name", "title", "authors",
    "summary", "content_type", "publication_year", "published_at", "detected_at",
    "access_url", "source_url", "access_status", "oa_status", "status", "language",
    "venue", "notes", "relevance_score", "relevance_reasons", "area_clep", "priority",
    "doi", "editorial_score", "editorial_decision", "indicator_or_dataset", "geography",
    "reference_period", "value_or_change", "organizer", "date_or_deadline",
    "speaker_or_organization", "data_points_json",
]


def base_candidate(kind: str, idx: int) -> dict[str, str]:
    row = {field: "" for field in CAND_FIELDS}
    row.update({
        "candidate_id": f"CAND-MULTI-{idx:02d}-{kind.upper()}",
        "source_id": "offline-fixture",
        "source_type": "fixture",
        "source_name": "Fuente offline",
        "title": f"Fixture {kind}",
        "authors": "Autora de Prueba",
        "summary": f"Descripción oficial factual para {kind}.",
        "content_type": kind,
        "publication_year": "2026",
        "published_at": "2026-10-07",
        "detected_at": "2026-10-07T09:00:00+00:00",
        # URN deliberado: invalida captura landing y fuerza fallback offline.
        "access_url": f"urn:clep:offline:{kind}",
        "source_url": "",
        "access_status": "PUBLIC_ACCESS_VERIFIED",
        "oa_status": "OA_VERIFICADO",
        "status": "OA_VERIFICADO",
        "language": "es",
        "venue": "Fixture CLEP",
        "notes": "",
        "relevance_score": "20",
        "relevance_reasons": "fixture offline",
        "area_clep": "metodologia",
        "priority": "20",
        "editorial_score": "7.0",
        "editorial_decision": "PUBLISHABLE",
    })
    if kind == "dataset_grafica":
        row.update({
            "indicator_or_dataset": "Índice de prueba",
            "geography": "México",
            "reference_period": "2026",
            "value_or_change": "102.0",
            "data_points_json": '[["2026-01",100.0],["2026-02",102.0]]',
        })
    elif kind == "convocatoria_evento":
        row.update({"organizer": "CLEP", "date_or_deadline": "2026-10-20"})
    elif kind == "video":
        row["speaker_or_organization"] = "A. Economista"
    elif kind == "edition_translation":
        row["notes"] = "edition_event=translation | edition_number=2"
    return row


def run_prepare(candidates: Path, queue: Path) -> str:
    env = os.environ.copy()
    env.update({"CLEP_CANDIDATES_PATH": str(candidates), "CLEP_QUEUE_PATH": str(queue)})
    result = subprocess.run(
        [PY, str(ROOT / "scripts/editorial/preparar_publicacion.py")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise AssertionError(
            f"preparar_publicacion.py rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    created_media: set[Path] = set()
    try:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            candidates = tmp / "candidatos.csv"
            queue = tmp / "cola.csv"

            rows = [base_candidate(kind, i) for i, kind in enumerate(SUPPORTED, start=1)]
            for offset, kind in enumerate(UNSUPPORTED, start=len(rows) + 1):
                rows.append(base_candidate(kind, offset))

            with candidates.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CAND_FIELDS)
                writer.writeheader()
                writer.writerows(rows)

            with (ROOT / "data/editorial/cola.csv").open(encoding="utf-8", newline="") as handle:
                qfields = list(csv.DictReader(handle).fieldnames or [])
            with queue.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=qfields).writeheader()

            first_stdout = run_prepare(candidates, queue)
            first = read_rows(queue)
            assert len(first) == len(SUPPORTED), (len(first), len(SUPPORTED), first_stdout)

            by_kind = {row["tipo_recurso"]: row for row in first}
            assert set(by_kind) == set(SUPPORTED), (set(by_kind), set(SUPPORTED))

            stable: dict[str, tuple[str, str, str, str]] = {}
            for kind in SUPPORTED:
                row = by_kind[kind]
                assert row["estado_editorial"] == "FICHA_LISTA", (kind, row)
                assert row["text_status"] in {"VERIFIED", "VERIFICADO"}, (kind, row)
                assert row["media_validation_status"] == "VALID", (kind, row)
                assert row["detected_media_type"] == "image/svg+xml", (kind, row)
                assert row["media_width"] == "1200" and row["media_height"] == "1500", (kind, row)
                assert len(row["media_content_sha256"]) == 64, (kind, row)
                assert len(row["preparation_fingerprint"]) == 64, (kind, row)
                assert row["preparation_version"] == "1", (kind, row)
                expected_media = "deterministic_chart" if kind == "dataset_grafica" else "deterministic_card"
                assert row["media_method"] == expected_media, (kind, row["media_method"])
                created_media.add(ROOT / row["media_path"])
                stable[kind] = (
                    row["ficha_es"],
                    row["media_path"],
                    row["media_content_sha256"],
                    row["preparation_fingerprint"],
                )

            # Los tipos canónicos sin adaptador no deben filtrarse accidentalmente a la cola.
            queued_ids = {row["editorial_id"] for row in first}
            for kind in UNSUPPORTED:
                assert not any(kind.upper() in editorial_id for editorial_id in queued_ids), (kind, queued_ids)

            second_stdout = run_prepare(candidates, queue)
            second = read_rows(queue)
            assert len(second) == len(first), (len(first), len(second))
            second_by_kind = {row["tipo_recurso"]: row for row in second}
            for kind, expected in stable.items():
                row = second_by_kind[kind]
                actual = (
                    row["ficha_es"],
                    row["media_path"],
                    row["media_content_sha256"],
                    row["preparation_fingerprint"],
                )
                assert actual == expected, (kind, expected, actual)
            assert "writes=cola:0,candidatos:0" in second_stdout, second_stdout

            print(
                "MULTIFORMAT PREPARATION E2E OK: "
                f"{len(SUPPORTED)} formatos, chart/card deterministas, "
                f"{len(UNSUPPORTED)} tipos bloqueados, idempotencia estable."
            )
    finally:
        for path in created_media:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        for path in (ROOT / "data/editorial/media").glob("CAND-MULTI-*"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    main()
