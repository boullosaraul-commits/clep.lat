#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import cuarentena
import ingestar_ad_hoc as adhoc
from schema import SchemaError


class QuarantineRegistryTests(unittest.TestCase):
    def test_latest_blocked_note_is_parsed(self):
        note = (
            "base | preparación bloqueada [TEXT_RENDER] TEXT_BAD: falta resumen "
            "| preparación bloqueada [MEDIA_RESOLVE_ACQUIRE_VALIDATE] MEDIA_DOWNLOAD_FAILED: red caída"
        )
        self.assertEqual(
            cuarentena.latest_blocked_note(note),
            ("MEDIA_RESOLVE_ACQUIRE_VALIDATE", "MEDIA_DOWNLOAD_FAILED", "red caída"),
        )

    def test_same_quarantine_is_exact_noop(self):
        rows = []
        first = cuarentena.upsert_open(
            rows,
            candidate_id="CAND-Q",
            stage="TEXT_RENDER",
            code="TEXT_BAD",
            detail="falta resumen",
            quarantined_at="2026-10-07T10:00:00Z",
        )
        snapshot = [dict(row) for row in rows]
        second = cuarentena.upsert_open(
            rows,
            candidate_id="CAND-Q",
            stage="TEXT_RENDER",
            code="TEXT_BAD",
            detail="falta resumen",
            quarantined_at="2026-10-08T10:00:00Z",
        )
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(rows, snapshot)

    def test_changed_cause_replaces_open_record(self):
        rows = []
        cuarentena.upsert_open(
            rows,
            candidate_id="CAND-Q",
            stage="TEXT_RENDER",
            code="TEXT_BAD",
            detail="falta resumen",
            quarantined_at="2026-10-07T10:00:00Z",
        )
        changed = cuarentena.upsert_open(
            rows,
            candidate_id="CAND-Q",
            stage="MEDIA_RESOLVE_ACQUIRE_VALIDATE",
            code="MEDIA_DOWNLOAD_FAILED",
            detail="red caída",
            quarantined_at="2026-10-08T10:00:00Z",
        )
        self.assertTrue(changed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quarantine_reason"], "MEDIA_ERROR")
        self.assertEqual(rows[0]["error_class"], "TEMPORARY")

    def test_ready_candidate_can_resolve_open_quarantine(self):
        rows = []
        cuarentena.upsert_open(
            rows,
            candidate_id="CAND-Q",
            stage="TEXT_RENDER",
            code="TEXT_BAD",
            detail="falta resumen",
            quarantined_at="2026-10-07T10:00:00Z",
        )
        self.assertTrue(cuarentena.resolve(rows, "CAND-Q", "2026-10-08T10:00:00Z"))
        self.assertEqual(rows[0]["quarantine_status"], "RESOLVED")
        self.assertEqual(rows[0]["resolved_at"], "2026-10-08T10:00:00Z")
        self.assertFalse(cuarentena.resolve(rows, "CAND-Q", "2026-10-09T10:00:00Z"))


class AdHocContractTests(unittest.TestCase):
    def base_request(self):
        return {
            "title": "Un paper desde chat",
            "content_type": "PAPER",
            "access_url": "https://example.org/paper",
            "authors": "Autora Uno",
            "publication_year": "2026",
        }

    def test_request_becomes_canonical_v1_then_operational(self):
        canonical = adhoc.canonical_request(self.base_request(), "request.json")
        self.assertEqual(canonical["schema_version"], 1)
        self.assertEqual(canonical["origin"], "CHAT")
        self.assertEqual(canonical["flow_type"], "AD_HOC")
        self.assertEqual(canonical["candidate_status"], "DISCOVERED")
        self.assertTrue(canonical["candidate_id"].startswith("CAND-CHAT-"))

        row = adhoc.operational_row(canonical)
        self.assertEqual(row["content_type"], "paper")
        self.assertEqual(row["status"], "DETECTADO")
        self.assertEqual(row["origin"], "CHAT")
        self.assertEqual(row["request_schema_version"], "1")

    def test_dataset_and_event_canonical_types_use_productive_adapters(self):
        for canonical_type, expected in (
            ("DATASET", "dataset_grafica"),
            ("CHART", "dataset_grafica"),
            ("EVENT", "convocatoria_evento"),
            ("CALL", "convocatoria_evento"),
        ):
            request = self.base_request()
            request["content_type"] = canonical_type
            row = adhoc.operational_row(adhoc.canonical_request(request))
            self.assertEqual(row["content_type"], expected)

    def test_unsupported_productive_adapter_fails_closed(self):
        request = self.base_request()
        request["content_type"] = "TEACHING_MATERIAL"
        with self.assertRaisesRegex(SchemaError, "no soportado productivamente"):
            adhoc.canonical_request(request)

    def test_non_https_request_fails_closed(self):
        request = self.base_request()
        request["access_url"] = "http://example.org/paper"
        with self.assertRaisesRegex(SchemaError, "HTTPS"):
            adhoc.canonical_request(request)

    def test_ingestion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(self.base_request()), encoding="utf-8")
            rows = []
            added, unchanged = adhoc.ingest_requests([path], rows)
            self.assertEqual((added, unchanged), (1, 0))
            snapshot = [dict(row) for row in rows]
            added, unchanged = adhoc.ingest_requests([path], rows)
            self.assertEqual((added, unchanged), (0, 1))
            self.assertEqual(rows, snapshot)

    def test_explicit_candidate_id_conflict_fails_closed(self):
        first = self.base_request()
        first["candidate_id"] = "CAND-CHAT-FIXED"
        second = dict(first)
        second["title"] = "Otro título"
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "a.json"
            p2 = Path(tmp) / "b.json"
            p1.write_text(json.dumps(first), encoding="utf-8")
            p2.write_text(json.dumps(second), encoding="utf-8")
            rows = []
            adhoc.ingest_requests([p1], rows)
            with self.assertRaisesRegex(SchemaError, "conflicto"):
                adhoc.ingest_requests([p2], rows)


if __name__ == "__main__":
    unittest.main()
