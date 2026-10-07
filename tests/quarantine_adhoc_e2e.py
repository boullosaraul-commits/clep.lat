#!/usr/bin/env python3
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "scripts/editorial/ingestar_ad_hoc.py"
QUARANTINE = ROOT / "scripts/editorial/actualizar_cuarentena.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        inbox = tmp / "ad_hoc"
        inbox.mkdir()
        candidates = tmp / "candidatos.csv"
        quarantine = tmp / "cuarentena.csv"
        request = inbox / "paper.json"
        request.write_text(
            json.dumps(
                {
                    "title": "Distribución funcional y demanda",
                    "content_type": "PAPER",
                    "access_url": "https://example.org/paper",
                    "authors": "Autora Uno",
                    "publication_year": "2026",
                    "summary": "Análisis poskeynesiano de distribución y demanda.",
                    "language": "es",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        first = run(str(INGEST), "--inbox", str(inbox), "--candidates", str(candidates))
        assert "solicitudes=1" in first.stdout, first.stdout
        rows = read_rows(candidates)
        assert len(rows) == 1
        row = rows[0]
        assert row["origin"] == "CHAT"
        assert row["flow_type"] == "AD_HOC"
        assert row["status"] == "DETECTADO"
        assert row["content_type"] == "paper"
        assert row["candidate_id"].startswith("CAND-CHAT-")

        candidate_bytes = candidates.read_bytes()
        second = run(str(INGEST), "--inbox", str(inbox), "--candidates", str(candidates))
        assert "sin_cambios=1" in second.stdout, second.stdout
        assert candidates.read_bytes() == candidate_bytes, "segunda ingesta debe ser byte-idempotente"

        rows[0]["status"] = "EVALUADO"
        rows[0]["notes"] = (
            rows[0].get("notes", "")
            + " | preparación bloqueada [MEDIA_RESOLVE_ACQUIRE_VALIDATE] "
              "MEDIA_DOWNLOAD_FAILED: upstream temporalmente inaccesible"
        ).strip(" |")
        write_rows(candidates, rows)

        opened = run(
            str(QUARANTINE),
            "--candidates", str(candidates),
            "--quarantine", str(quarantine),
            "--now", "2026-10-07T10:00:00Z",
        )
        assert "abiertas/actualizadas=1" in opened.stdout, opened.stdout
        qrows = read_rows(quarantine)
        assert len(qrows) == 1
        assert qrows[0]["preparation_status"] == "QUARANTINED"
        assert qrows[0]["quarantine_status"] == "OPEN"
        assert qrows[0]["quarantine_reason"] == "MEDIA_ERROR"
        assert qrows[0]["error_class"] == "TEMPORARY"

        quarantine_bytes = quarantine.read_bytes()
        noop = run(
            str(QUARANTINE),
            "--candidates", str(candidates),
            "--quarantine", str(quarantine),
            "--now", "2026-10-08T10:00:00Z",
        )
        assert "abiertas/actualizadas=0" in noop.stdout, noop.stdout
        assert quarantine.read_bytes() == quarantine_bytes, "misma causa debe ser byte-idempotente"

        rows = read_rows(candidates)
        rows[0]["status"] = "FICHA_LISTA"
        write_rows(candidates, rows)
        resolved = run(
            str(QUARANTINE),
            "--candidates", str(candidates),
            "--quarantine", str(quarantine),
            "--now", "2026-10-09T10:00:00Z",
        )
        assert "resueltas=1" in resolved.stdout, resolved.stdout
        qrows = read_rows(quarantine)
        assert qrows[0]["quarantine_status"] == "RESOLVED"
        assert qrows[0]["resolved_at"] == "2026-10-09T10:00:00Z"

    print("quarantine/ad-hoc E2E: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
