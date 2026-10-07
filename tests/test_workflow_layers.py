#!/usr/bin/env python3
"""Regresiones de arquitectura para separar offline, red, Meta y composición productiva."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"

LAYERS = {
    "offline": {
        "editorial-ci.yml",
        "editorial-check.yml",
        "editorial-plan.yml",
    },
    "network": {
        "editorial-network-smoke.yml",
        "editorial-ingest.yml",
        "historical-recovery.yml",
    },
    "meta": {
        "meta-queue-e2e.yml",
        "meta-smoke-test.yml",
        "facebook-publish.yml",
    },
    "mixed": {
        "daily-editorial.yml",
    },
}

META_TOKENS = (
    "CLEP_FB_TOKEN",
    "CLEP_FB_PAGE_ID",
    "graph.facebook.com",
    "programar_facebook.py",
    "marcar_intento_meta.py",
    "reconciliar_meta.py",
    "verificar_meta.py",
    "verificar_publicaciones_facebook.py",
    "cerrar_reemplazos_facebook.py",
)

NETWORK_SCRIPT_TOKENS = (
    "ingerir_feeds.py",
    "ingerir_nep.py",
    "enriquecer_repec.py",
    "ingerir_doab.py",
    "ingerir_novedades_academicas.py",
    "ingerir_catalogos.py",
    "detectar_actualizaciones.py",
    "verificar_oa.py",
    "historical_worker.py",
)


def text(name: str) -> str:
    return (WF / name).read_text(encoding="utf-8")


class WorkflowLayerTests(unittest.TestCase):
    def test_every_workflow_has_exactly_one_layer(self):
        actual = {p.name for p in WF.glob("*.yml")}
        declared = set().union(*LAYERS.values())
        self.assertEqual(actual, declared, f"workflows sin clasificar o contrato obsoleto: actual={sorted(actual)} declared={sorted(declared)}")

    def test_layers_are_disjoint(self):
        seen: set[str] = set()
        for layer, names in LAYERS.items():
            overlap = seen & names
            self.assertFalse(overlap, f"workflow(s) en múltiples capas ({layer}): {sorted(overlap)}")
            seen |= names

    def test_offline_workflows_do_not_contain_meta_or_network_actions(self):
        violations: list[str] = []
        for name in sorted(LAYERS["offline"]):
            body = text(name)
            for token in (*META_TOKENS, *NETWORK_SCRIPT_TOKENS):
                if token in body:
                    violations.append(f"{name}: {token}")
        self.assertEqual(violations, [], "capa offline cruzó frontera de red/Meta: " + "; ".join(violations))

    def test_network_workflows_do_not_write_meta(self):
        violations: list[str] = []
        forbidden = (
            "programar_facebook.py",
            "marcar_intento_meta.py",
            "cerrar_reemplazos_facebook.py",
        )
        for name in sorted(LAYERS["network"]):
            body = text(name)
            for token in forbidden:
                if token in body:
                    violations.append(f"{name}: {token}")
        self.assertEqual(violations, [], "workflow de red contiene escritura Meta productiva: " + "; ".join(violations))

    def test_meta_workflows_are_explicitly_meta_scoped(self):
        for name in sorted(LAYERS["meta"]):
            body = text(name)
            self.assertTrue(
                any(token in body for token in META_TOKENS),
                f"{name} está clasificado como Meta pero no contiene ninguna operación Meta explícita",
            )

    def test_daily_is_the_only_mixed_composition(self):
        self.assertEqual(LAYERS["mixed"], {"daily-editorial.yml"})
        body = text("daily-editorial.yml")
        self.assertTrue(any(token in body for token in NETWORK_SCRIPT_TOKENS), "daily debe componer la capa de red")
        self.assertTrue(any(token in body for token in META_TOKENS), "daily debe componer la capa Meta")


if __name__ == "__main__":
    unittest.main()
