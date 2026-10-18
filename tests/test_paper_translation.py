#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))
from traducir_papers import translate_rows


class PaperTranslationTests(unittest.TestCase):
    def row(self, **overrides):
        row = {
            "candidate_id":"CAND-PAPER-1", "content_type":"paper",
            "title":"Original title", "authors":"Alice Example; Bob Example",
            "summary":"Original abstract.", "language":"en",
        }
        row.update(overrides)
        return row

    def test_translates_title_and_abstract_but_not_authors(self):
        row = self.row()
        calls = []
        def tr(text):
            calls.append(text)
            return {"Original title":"Título traducido", "Original abstract.":"Resumen traducido."}[text]
        self.assertEqual(translate_rows([row], tr, "test"), 1)
        self.assertEqual(calls, ["Original title", "Original abstract."])
        self.assertEqual(row["authors"], "Alice Example; Bob Example")
        self.assertEqual(row["title_original"], "Original title")
        self.assertEqual(row["title_es"], "Título traducido")
        self.assertIn("Título traducido", row["title"])
        self.assertEqual(row["source_summary_es"], "Resumen traducido.")
        self.assertEqual(row["translation_engine"], "argos-translate")
        self.assertEqual(row["translation_status"], "VERIFIED")

    def test_incomplete_papers_blocked_without_aborting_valid_rows(self):
        for field, code in (("title", "TITLE"), ("authors", "AUTHORS"), ("summary", "ABSTRACT")):
            with self.subTest(field=field):
                bad = self.row(**{field: ""})
                good = self.row(candidate_id="VALID")
                calls = []
                def tr(text):
                    calls.append(text)
                    return "ES " + text
                with self.assertWarnsRegex(RuntimeWarning, f"PAPER_{code}_MISSING"):
                    self.assertEqual(translate_rows([bad, good], tr), 2)
                self.assertEqual(bad["translation_status"], "BLOCKED")
                self.assertEqual(good["translation_status"], "VERIFIED")
                self.assertEqual(len(calls), 2)
                with self.assertWarns(RuntimeWarning):
                    self.assertEqual(translate_rows([bad], tr), 0)

    def test_archived_incomplete_paper_is_untouched(self):
        row = self.row(status="ARCHIVADO", authors="")
        original = dict(row)
        self.assertEqual(translate_rows([row], lambda _: self.fail("archived paper translated")), 0)
        self.assertEqual(row, original)

    def test_empty_translation_still_aborts(self):
        with self.assertRaisesRegex(RuntimeError, "PAPER_TRANSLATION_EMPTY"):
            translate_rows([self.row()], lambda _: "")

    def test_non_english_paper_is_untouched(self):
        row = self.row(language="es")
        original = dict(row)
        self.assertEqual(translate_rows([row], lambda x: "NO", "test"), 0)
        self.assertEqual(row, original)


if __name__ == "__main__":
    unittest.main()
