#!/usr/bin/env python3
"""Structural acceptance contract for the completed 18-step CLEP roadmap.

This suite does not replace behavioral unit/E2E tests. It prevents future edits
from silently removing a completed architectural boundary or production stage.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITORIAL = ROOT / "scripts" / "editorial"
WORKFLOWS = ROOT / ".github" / "workflows"


class RoadmapCompletionTests(unittest.TestCase):
    def test_steps_1_to_8_canonical_components_exist(self):
        required = {
            "schema.py",
            "editorial_rules.py",
            "renderizar_texto.py",
            "resolver_media.py",
            "adquirir_media.py",
            "validar_media.py",
            "preparar_publicacion.py",
            "verificar_cola.py",
        }
        self.assertTrue(required.issubset({p.name for p in EDITORIAL.iterdir()}))

    def test_steps_9_10_16_have_offline_e2e_and_layer_separation(self):
        required_tests = {
            "multiformat_preparation_e2e.py",
            "editorial_e2e.py",
            "test_workflow_layers.py",
        }
        tests = {p.name for p in (ROOT / "tests").iterdir()}
        self.assertTrue(required_tests.issubset(tests))
        self.assertTrue((WORKFLOWS / "editorial-network-smoke.yml").exists())
        self.assertTrue((WORKFLOWS / "meta-queue-e2e.yml").exists())
        self.assertTrue((WORKFLOWS / "meta-smoke-test.yml").exists())

    def test_steps_11_12_17_daily_pipeline_is_automatic_and_meta_hardened(self):
        daily = (WORKFLOWS / "daily-editorial.yml").read_text(encoding="utf-8")
        self.assertIn("schedule:", daily)
        self.assertIn("reconciliar_meta.py", daily)
        self.assertIn("marcar_intento_meta.py", daily)
        self.assertIn("programar_facebook.py", daily)
        self.assertIn("verificar_publicaciones_facebook.py", daily)
        self.assertLess(daily.index("marcar_intento_meta.py"), daily.index("programar_facebook.py"))
        self.assertIn("without automatic retry", daily)

    def test_steps_13_14_quarantine_and_ad_hoc_share_daily_pipeline(self):
        daily = (WORKFLOWS / "daily-editorial.yml").read_text(encoding="utf-8")
        self.assertTrue((EDITORIAL / "cuarentena.py").exists())
        self.assertTrue((EDITORIAL / "actualizar_cuarentena.py").exists())
        self.assertTrue((EDITORIAL / "ingestar_ad_hoc.py").exists())
        self.assertIn("ingestar_ad_hoc.py", daily)
        self.assertIn("actualizar_cuarentena.py", daily)
        self.assertLess(daily.index("ingestar_ad_hoc.py"), daily.index("preparar_publicacion.py"))

    def test_step_15_cloudflare_is_not_coupled_to_editorial_workflows(self):
        editorial_workflows = [
            "daily-editorial.yml",
            "editorial-check.yml",
            "editorial-ci.yml",
            "editorial-ingest.yml",
            "editorial-network-smoke.yml",
            "editorial-plan.yml",
            "facebook-publish.yml",
            "historical-recovery.yml",
            "meta-queue-e2e.yml",
            "meta-smoke-test.yml",
        ]
        for name in editorial_workflows:
            text = (WORKFLOWS / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("wrangler", text, name)
            self.assertNotIn("cloudflare", text, name)

    def test_step_18_regressions_are_mandatory_in_ci(self):
        ci = (WORKFLOWS / "editorial-ci.yml").read_text(encoding="utf-8")
        for test in (
            "test_editorial_schema.py",
            "test_editorial_rules.py",
            "test_text_renderer.py",
            "test_media_resolver.py",
            "test_media_validator.py",
            "test_preparar_publicacion.py",
            "test_preparation_bypass.py",
            "test_queue_verifier.py",
            "test_workflow_layers.py",
            "test_quarantine_adhoc.py",
            "editorial_e2e.py",
        ):
            self.assertIn(test, ci)


if __name__ == "__main__":
    unittest.main()
