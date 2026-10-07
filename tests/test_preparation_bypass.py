#!/usr/bin/env python3
"""Auditoría estática de escritores de FICHA_LISTA.

La autoridad productiva es preparar_publicacion.py. La única excepción permitida
es recovery/historical_worker.py, restringida al flujo archivo_historico y
cubierta por la excepción legacy histórica ya documentada.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "scripts/editorial", ROOT / "recovery")
PRODUCTIVE_WRITER = (ROOT / "scripts/editorial/preparar_publicacion.py").resolve()
HISTORICAL_EXCEPTION = (ROOT / "recovery/historical_worker.py").resolve()
AUTHORIZED_WRITERS = {PRODUCTIVE_WRITER, HISTORICAL_EXCEPTION}


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _subscript_key(node: ast.Subscript):
    return _literal(node.slice)


def ficha_lista_writes(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: list[int] = []

    for node in ast.walk(tree):
        # row["estado_editorial"] = "FICHA_LISTA"
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = _literal(node.value)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if value == "FICHA_LISTA":
                for target in targets:
                    if isinstance(target, ast.Subscript) and _subscript_key(target) == "estado_editorial":
                        lines.append(node.lineno)

        # {"estado_editorial": "FICHA_LISTA"} y queued.update({...})
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if _literal(key) == "estado_editorial" and _literal(value) == "FICHA_LISTA":
                    lines.append(node.lineno)

    return sorted(set(lines))


def historical_exception_is_scoped(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return '"flujo_editorial":"archivo_historico"' in text or '"flujo_editorial": "archivo_historico"' in text


class PreparationBypassAuditTests(unittest.TestCase):
    def test_only_authorized_writers_can_write_ficha_lista(self):
        violations: list[str] = []
        writers: list[str] = []

        for root in SCAN_ROOTS:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.py")):
                hits = ficha_lista_writes(path)
                if not hits:
                    continue
                resolved = path.resolve()
                rel = path.relative_to(ROOT)
                if resolved in AUTHORIZED_WRITERS:
                    writers.append(str(rel))
                    continue
                violations.append(f"{rel}:{','.join(map(str, hits))}")

        self.assertEqual(
            violations,
            [],
            "bypass de FICHA_LISTA detectado fuera de las autoridades: " + "; ".join(violations),
        )
        self.assertEqual(
            sorted(writers),
            [
                "recovery/historical_worker.py",
                "scripts/editorial/preparar_publicacion.py",
            ],
            f"autoridades FICHA_LISTA inesperadas: {writers}",
        )

    def test_historical_exception_is_explicitly_archive_scoped(self):
        self.assertTrue(
            historical_exception_is_scoped(HISTORICAL_EXCEPTION),
            "historical_worker.py sólo puede conservar la excepción si escribe flujo_editorial=archivo_historico",
        )


if __name__ == "__main__":
    unittest.main()
