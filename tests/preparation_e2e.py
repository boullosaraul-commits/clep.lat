#!/usr/bin/env python3
"""E2E offline del Paso 6: candidato -> preparación READY/FICHA_LISTA."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

CAND_FIELDS = [
    "candidate_id", "source_id", "source_type", "source_name", "title", "authors",
    "summary", "content_type", "publication_year", "published_at", "detected_at",
    "access_url", "source_url", "access_status", "oa_status", "status", "language",
    "venue", "notes", "relevance_score", "relevance_reasons", "area_clep", "priority",
    "doi", "editorial_score", "editorial_decision",
]


def run_prepare(env: dict[str, str]) -> str:
    completed = subprocess.run(
        [PY, str(ROOT / "scripts/editorial/preparar_publicacion.py")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise AssertionError(
            f"preparar_publicacion.py rc={completed.returncode}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed.stdout


def read_one(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1, rows
    return rows[0]


def main() -> None:
    created_media: Path | None = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            candidates = tmp / "candidatos.csv"
            queue = tmp / "cola.csv"

            candidate = {
                "candidate_id": "CAND-PREP-E2E",
                "source_id": "offline-fixture",
                "source_type": "fixture",
                "source_name": "Fuente offline",
                "title": "Preparación editorial determinista offline",
                "authors": "Autora de Prueba",
                "summary": "Resumen factual de una prueba offline del pipeline editorial.",
                "content_type": "paper",
                "publication_year": "2026",
                "published_at": "2026-10-06",
                "detected_at": "2026-10-06T12:00:00+00:00",
                # Deliberadamente no HTTPS: la captura queda descartada por contrato
                # y el resolver debe llegar a deterministic_card sin tocar la red.
                "access_url": "urn:clep:offline:preparation-e2e",
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
                "doi": "",
                "editorial_score": "7.0",
                "editorial_decision": "PUBLISHABLE",
            }
            with candidates.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CAND_FIELDS)
                writer.writeheader()
                writer.writerow(candidate)

            with (ROOT / "data/editorial/cola.csv").open(encoding="utf-8", newline="") as handle:
                qfields = list(csv.DictReader(handle).fieldnames or [])
            with queue.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=qfields).writeheader()

            env = os.environ.copy()
            env.update(
                {
                    "CLEP_CANDIDATES_PATH": str(candidates),
                    "CLEP_QUEUE_PATH": str(queue),
                }
            )

            first_stdout = run_prepare(env)
            first = read_one(queue)
            created_media = ROOT / first["media_path"]

            assert first["estado_editorial"] == "FICHA_LISTA", first
            assert first["text_status"] in {"VERIFIED", "VERIFICADO"}, first
            assert first["media_method"] == "deterministic_card", first
            assert first["media_validation_status"] == "VALID", first
            assert first["detected_media_type"] == "image/svg+xml", first
            assert first["media_width"] == "1200" and first["media_height"] == "1500", first
            assert len(first["media_content_sha256"]) == 64, first
            assert len(first["preparation_fingerprint"]) == 64, first
            assert first["preparation_version"] == "1", first
            assert first["media_resolver_version"], first
            assert first["media_fallback_level"], first
            assert first["media_acquisition_method"] == "deterministic_card", first
            assert int(first["media_bytes_size"]) > 0, first
            assert "writes=cola:1" in first_stdout, first_stdout

            stable = {
                key: first[key]
                for key in (
                    "ficha_es",
                    "media_path",
                    "media_content_sha256",
                    "media_resolution_fingerprint",
                    "preparation_fingerprint",
                )
            }

            second_stdout = run_prepare(env)
            second = read_one(queue)
            for key, value in stable.items():
                assert second[key] == value, (key, value, second[key])
            assert "writes=cola:0" in second_stdout, second_stdout
            assert "writes=candidatos:0" in second_stdout, second_stdout

            print("PREPARATION E2E OK: offline, validada e idempotente.")
    finally:
        if created_media is not None:
            try:
                created_media.unlink()
            except FileNotFoundError:
                pass
        for path in (ROOT / "data/editorial/media").glob("CAND-PREP-E2E-*"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    main()
