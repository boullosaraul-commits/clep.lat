#!/usr/bin/env python3
"""Auditoría estática de autoridades y fronteras legacy del pipeline CLEP."""
from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITORIAL = ROOT / "scripts/editorial"
RECOVERY = ROOT / "recovery"
WORKFLOWS = ROOT / ".github/workflows"
sys.path.insert(0, str(EDITORIAL))

from migrar_nep_legacy import audit_rows, load_rows

SCAN_ROOTS = (EDITORIAL, RECOVERY)
PRODUCTIVE_WRITER = (EDITORIAL / "preparar_publicacion.py").resolve()
HISTORICAL_EXCEPTION = (RECOVERY / "historical_worker.py").resolve()
AUTHORIZED_WRITERS = {PRODUCTIVE_WRITER, HISTORICAL_EXCEPTION}
LEGACY_CONTRACT_PATH = ROOT / "data/editorial/legacy_contract.json"


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _subscript_key(node: ast.Subscript):
    return _literal(node.slice)


def editorial_state_writes(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = _literal(node.value)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, str):
                for target in targets:
                    if isinstance(target, ast.Subscript) and _subscript_key(target) == "estado_editorial":
                        hits.append((value, node.lineno))
        if isinstance(node, ast.Dict):
            for key, value_node in zip(node.keys, node.values):
                if _literal(key) == "estado_editorial":
                    value = _literal(value_node)
                    if isinstance(value, str):
                        hits.append((value, node.lineno))
    return sorted(set(hits), key=lambda item: (item[1], item[0]))


def ficha_lista_writes(path: Path) -> list[int]:
    return [line for state, line in editorial_state_writes(path) if state == "FICHA_LISTA"]


def historical_exception_is_scoped(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return (
        '"flujo_editorial":"archivo_historico"' in text
        or '"flujo_editorial": "archivo_historico"' in text
    )


def imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == module_name for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module == module_name:
            return True
    return False


class PreparationBypassAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(LEGACY_CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_only_authorized_writers_can_write_ficha_lista(self):
        violations: list[str] = []
        writers: list[str] = []
        for root in SCAN_ROOTS:
            for path in sorted(root.rglob("*.py")):
                hits = ficha_lista_writes(path)
                if not hits:
                    continue
                resolved = path.resolve()
                rel = path.relative_to(ROOT)
                if resolved in AUTHORIZED_WRITERS:
                    writers.append(str(rel))
                else:
                    violations.append(f"{rel}:{','.join(map(str, hits))}")
        self.assertEqual(
            violations,
            [],
            "bypass de FICHA_LISTA detectado fuera de las autoridades: " + "; ".join(violations),
        )
        self.assertEqual(
            sorted(writers),
            ["recovery/historical_worker.py", "scripts/editorial/preparar_publicacion.py"],
            f"autoridades FICHA_LISTA inesperadas: {writers}",
        )

    def test_historical_exception_is_explicitly_archive_scoped_and_narrow(self):
        self.assertTrue(
            historical_exception_is_scoped(HISTORICAL_EXCEPTION),
            "historical_worker.py sólo puede conservar la excepción si escribe archivo_historico",
        )
        states = {state for state, _line in editorial_state_writes(HISTORICAL_EXCEPTION)}
        self.assertEqual(
            states,
            {"FICHA_LISTA"},
            f"historical_worker.py no puede escribir estados adicionales: {sorted(states)}",
        )
        text = HISTORICAL_EXCEPTION.read_text(encoding="utf-8")
        self.assertNotIn("programar_facebook", text)
        self.assertNotIn('"post_nuevo_id"', text)

    def test_legacy_contract_has_exactly_one_historical_exception(self):
        exceptions = self.contract["historical_exceptions"]
        self.assertEqual(list(exceptions), ["recovery/historical_worker.py"])
        spec = exceptions["recovery/historical_worker.py"]
        self.assertEqual(spec["required_flow"], "archivo_historico")
        self.assertEqual(spec["allowed_direct_editorial_states"], ["FICHA_LISTA"])
        self.assertFalse(spec["may_schedule"])
        self.assertFalse(spec["may_publish_meta"])

    def test_manual_legacy_tools_are_never_invoked_by_workflows(self):
        tools = self.contract["manual_only_tools"]
        for rel, spec in tools.items():
            self.assertTrue((ROOT / rel).exists(), rel)
            self.assertFalse(spec["automatic_invocation_allowed"], rel)
            for workflow in sorted(WORKFLOWS.glob("*.yml")):
                self.assertNotIn(
                    rel,
                    workflow.read_text(encoding="utf-8"),
                    f"{workflow.relative_to(ROOT)} invoca herramienta manual legacy {rel}",
                )

    def test_legacy_shims_do_not_regain_productive_authority(self):
        shims = self.contract["compatibility_shims"]
        paper_shim = ROOT / "scripts/editorial/generar_ficha_paper.py"
        promote_shim = ROOT / "scripts/editorial/promover_candidatos.py"
        self.assertIn(str(paper_shim.relative_to(ROOT)), shims)
        self.assertIn(str(promote_shim.relative_to(ROOT)), shims)
        self.assertEqual(ficha_lista_writes(paper_shim), [])
        self.assertEqual(ficha_lista_writes(promote_shim), [])
        self.assertIn("renderizar_texto", paper_shim.read_text(encoding="utf-8"))
        self.assertIn("preparar_publicacion", promote_shim.read_text(encoding="utf-8"))

        consumers = []
        for root in SCAN_ROOTS:
            for path in sorted(root.rglob("*.py")):
                if path.resolve() == paper_shim.resolve():
                    continue
                if imports_module(path, "generar_ficha_paper"):
                    consumers.append(str(path.relative_to(ROOT)))
        self.assertEqual(consumers, [], f"shim generar_ficha_paper volvió a producción: {consumers}")

    def test_current_candidate_store_needs_no_nep_legacy_repair(self):
        rows, _fields = load_rows()
        issues = audit_rows(rows)
        self.assertEqual(issues, [], "candidatos.csv volvió a requerir migración NEP: " + "; ".join(issues[:20]))


if __name__ == "__main__":
    unittest.main()
