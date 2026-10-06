#!/usr/bin/env python3
"""Auditoría estática: sólo preparar_publicacion.py puede producir FICHA_LISTA."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "scripts/editorial", ROOT / "recovery")
AUTHORIZED_WRITERS = {
    (ROOT / "scripts/editorial/preparar_publicacion.py").resolve(),
}


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


class PreparationBypassAuditTests(unittest.TestCase):
    def test_only_preparation_orchestrator_can_write_ficha_lista(self):
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
            "bypass de FICHA_LISTA detectado fuera del orquestador: " + "; ".join(violations),
        )
        self.assertEqual(
            writers,
            ["scripts/editorial/preparar_publicacion.py"],
            f"autoridad FICHA_LISTA inesperada: {writers}",
        )


if __name__ == "__main__":
    unittest.main()
