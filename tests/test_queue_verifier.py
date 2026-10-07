#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import verificar_cola as verifier
from preparation_contract import fingerprint_from_prepared_row


class QueueVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_dir = ROOT / "data/editorial/media"
        cls.media_dir.mkdir(parents=True, exist_ok=True)
        cls.media_path = cls.media_dir / "TEST-STEP7-QUEUE-VERIFIER.svg"
        cls.media_bytes = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500" '
            'viewBox="0 0 1200 1500"><rect width="1200" height="1500"/></svg>'
        ).encode("utf-8")
        cls.media_path.write_bytes(cls.media_bytes)
        cls.media_sha = hashlib.sha256(cls.media_bytes).hexdigest()
        cls.cfg = json.loads(verifier.CFG.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.media_path.unlink()
        except FileNotFoundError:
            pass

    def base_row(self, *, editorial_id="ED-STEP7-A", state="PROGRAMADO", time="07:00"):
        return {
            "editorial_id": editorial_id,
            "flujo_editorial": "novedad",
            "estado_editorial": state,
            "tipo_recurso": "recurso",
            "fecha_programada": "2026-10-08" if state in verifier.LEGACY_SCHEDULED_STATES else "",
            "orden_dia": time if state in verifier.LEGACY_SCHEDULED_STATES else "",
            "ficha_es": "RECURSO · CLEP\n\nFixture determinista de verificación.",
            "text_method": "deterministic_template",
            "text_template": "recurso",
            "text_status": "VERIFICADO",
            "media_type": "image/svg+xml",
            "media_path": str(self.media_path.relative_to(ROOT)),
            "media_source": "CLEP deterministic card",
            "media_rights_status": "PROPIO_DETERMINISTA",
            "media_method": "deterministic_card",
            "media_validation_status": "VALID",
            "media_validation_version": "2",
            "detected_media_type": "image/svg+xml",
            "media_content_sha256": self.media_sha,
            "media_width": "1200",
            "media_height": "1500",
            "meta_attempt_status": "",
            "post_nuevo_id": "",
            "notas": "fixture step7",
        }

    def codes(self, rows, *, policy=""):
        return {
            issue.code
            for issue in verifier.verify_rows(rows, cfg=self.cfg, current_policy_fp=policy)
            if issue.severity == verifier.SEVERITY_ERROR
        }

    def warnings(self, rows, *, policy=""):
        return {
            issue.code
            for issue in verifier.verify_rows(rows, cfg=self.cfg, current_policy_fp=policy)
            if issue.severity == verifier.SEVERITY_WARNING
        }

    def test_valid_programmed_row_rehashes_and_passes(self):
        self.assertEqual(self.codes([self.base_row()]), set())

    def test_material_hash_mismatch_is_detected_from_real_file(self):
        row = self.base_row()
        row["media_content_sha256"] = "0" * 64
        self.assertIn("MEDIA_HASH_MISMATCH", self.codes([row]))

    def test_detected_media_type_drift_is_detected(self):
        row = self.base_row()
        row["detected_media_type"] = "image/png"
        self.assertIn("MEDIA_DETECTED_TYPE_DRIFT", self.codes([row]))

    def prepared_row(self):
        row = self.base_row(state="FICHA_LISTA")
        row.update(
            {
                "candidate_fingerprint": "a" * 64,
                "editorial_policy_fingerprint": "b" * 64,
                "preparation_version": "1",
                "text_template_version": "1",
                "source_summary": "Resumen fuente",
                "source_summary_es": "",
                "editorial_description": "Resumen fuente",
                "media_resolver_version": "1",
                "media_fallback_level": "1",
                "media_resolution_fingerprint": "c" * 64,
                "media_acquisition_method": "deterministic_card",
                "media_bytes_size": str(len(self.media_bytes)),
                "alt_text": "Tarjeta CLEP: fixture",
            }
        )
        row["preparation_fingerprint"] = fingerprint_from_prepared_row(row)
        return row

    def test_preparation_fingerprint_is_recomputed(self):
        row = self.prepared_row()
        row["ficha_es"] += " alterado"
        self.assertIn(
            "PREPARATION_FINGERPRINT_MISMATCH",
            self.codes([row], policy="b" * 64),
        )

    def test_preparation_policy_staleness_is_detected(self):
        row = self.prepared_row()
        self.assertIn(
            "PREPARATION_POLICY_STALE",
            self.codes([row], policy="d" * 64),
        )

    def test_schedule_duplicate_is_detected(self):
        first = self.base_row(editorial_id="ED-STEP7-A", time="07:00")
        second = self.base_row(editorial_id="ED-STEP7-B", time="07:00")
        self.assertIn("SCHEDULE_TIME_DUPLICATE", self.codes([first, second]))

    def test_schedule_gap_uses_configured_minimum(self):
        first = self.base_row(editorial_id="ED-STEP7-A", time="07:00")
        second = self.base_row(editorial_id="ED-STEP7-B", time="07:30")
        self.assertIn("SCHEDULE_GAP_TOO_SMALL", self.codes([first, second]))

    def test_meta_ambiguous_requires_reconciliation(self):
        row = self.base_row()
        row["meta_attempt_status"] = "REVIEW"
        self.assertIn("META_AMBIGUOUS_REQUIRES_RECONCILIATION", self.codes([row]))

    def test_revalidar_with_meta_evidence_is_warning_not_permission(self):
        row = self.base_row(state="REVALIDAR")
        row["meta_attempt_status"] = "SCHEDULED"
        row["post_nuevo_id"] = "meta-post-1"
        self.assertEqual(self.codes([row]), set())
        self.assertIn("META_LOCAL_DIVERGENCE_RECONCILE", self.warnings([row]))

    def test_invalid_v1_schema_is_structured(self):
        row = {"schema_version": "1", "editorial_id": "ED-V1"}
        self.assertIn("SCHEMA_INVALID", self.codes([row]))

    def test_legacy_ready_without_certificate_warns_but_does_not_claim_ready(self):
        row = self.base_row(state="FICHA_LISTA")
        row["media_validation_status"] = ""
        row["media_validation_version"] = ""
        row["detected_media_type"] = ""
        row["media_content_sha256"] = ""
        self.assertEqual(self.codes([row]), set())
        warnings = self.warnings([row])
        self.assertIn("LEGACY_READY_NOT_SCHEDULABLE", warnings)
        self.assertIn("LEGACY_READY_MEDIA_NOT_CERTIFIED", warnings)


if __name__ == "__main__":
    unittest.main()
