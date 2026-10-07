#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from renderizar_texto import (
    TextRenderError,
    factual_fallback,
    render,
    render_result,
    supported_content_types,
)


class UnifiedTextRendererTests(unittest.TestCase):
    def samples(self):
        return {
            "paper": {"title":"A Monetary Paper","authors":"A. Author","source_or_series":"Working Paper Series","year":"2026","access_url":"https://example.org/p"},
            "book": {"title":"A Book","authors_or_editors":"A. Author","year":"2026","access_url":"https://example.org/b"},
            "chapter": {"title":"A Chapter","authors":"A. Author","container_title":"A Book","year":"2026","access_url":"https://example.org/c"},
            "report": {"title":"A Report","authors_or_institution":"CEPAL","year":"2026","access_url":"https://example.org/r"},
            "policy_brief": {"title":"A Policy Brief","authors_or_institution":"ILO","year":"2026","access_url":"https://example.org/pb"},
            "special_issue": {"title":"Special Issue","journal":"Example Journal","year":"2026","access_url":"https://example.org/s"},
            "thesis": {"title":"A Thesis","authors":"A. Author","institution":"UNAM","year":"2026","access_url":"https://example.org/t"},
            "edition_translation": {"title":"A Translation","authors_or_editors":"A. Author","edition_note":"traducción","year":"2026","access_url":"https://example.org/e"},
            "dataset_grafica": {"indicator_or_dataset":"Employment rate","geography":"Mexico","reference_period":"2026","value_or_change":"61.2%","official_source":"INEGI","access_url":"https://example.org/d"},
            "convocatoria_evento": {"title":"Seminario","organizer":"CLEP","date_or_deadline":"2026-10-20","access_url":"https://example.org/a"},
            "video": {"title":"Lecture","speaker_or_organization":"A. Economist","access_url":"https://example.org/v"},
            "recurso": {"title":"Open Resource","source":"Example Institution","access_url":"https://example.org/x"},
            "anuncio_institucional": {"title":"Memoria institucional","editorial_text":"Texto editorial humano y factual.","access_url":"https://example.org/memoria"},
        }

    def test_all_declared_types_render(self):
        samples = self.samples()
        self.assertEqual(set(samples), set(supported_content_types()))
        for kind, data in samples.items():
            with self.subTest(kind=kind):
                result = render_result(kind, data)
                self.assertEqual(result.content_type, kind)
                self.assertEqual(result.text_method, "deterministic_template")
                self.assertEqual(result.text_status, "VERIFIED")
                self.assertTrue(result.text_template)
                self.assertGreaterEqual(result.text_template_version, 1)
                self.assertTrue(result.post_text)
                self.assertEqual(result.post_text, render(kind, data))

    def test_same_input_same_output(self):
        data = self.samples()["paper"]
        self.assertEqual(render_result("paper", data), render_result("paper", data))

    def test_unicode_is_preserved(self):
        data = self.samples()["book"]
        data = dict(data, title="Economía política, crédito y reproducción")
        text = render("book", data)
        self.assertIn("Economía política, crédito y reproducción", text)

    def test_unknown_type_fails_closed(self):
        with self.assertRaises(TextRenderError) as ctx:
            render_result("unknown", {"title":"X","access_url":"https://example.org"})
        self.assertEqual(ctx.exception.code, "TEMPLATE_MISSING")

    def test_missing_required_metadata_fails_closed(self):
        data = self.samples()["paper"].copy()
        data["authors"] = ""
        with self.assertRaises(TextRenderError) as ctx:
            render_result("paper", data)
        self.assertEqual(ctx.exception.code, "INSUFFICIENT_METADATA")
        self.assertEqual(ctx.exception.field, "authors")

    def test_factual_fallback_does_not_invent_summary(self):
        data = {"title":"A Book","authors":"A. Author","year":"2026","access_url":"https://example.org/b"}
        text = factual_fallback("book", data)
        self.assertIn("A Book", text)
        self.assertIn("A. Author", text)
        self.assertNotIn("argues", text.lower())
        self.assertNotIn("demuestra", text.lower())

    def test_factual_fallback_requires_title_and_access(self):
        with self.assertRaises(TextRenderError) as ctx:
            factual_fallback("book", {"title":"A Book"})
        self.assertEqual(ctx.exception.code, "INSUFFICIENT_METADATA")
        self.assertEqual(ctx.exception.field, "access_url")

    def test_spanish_source_summary_has_priority(self):
        data = self.samples()["paper"].copy()
        data.update({"source_summary":"Resumen oficial en español.","source_language":"es"})
        result = render_result("paper", data)
        self.assertEqual(result.editorial_description, "Resumen oficial en español.")
        self.assertFalse(result.translation["present"])

    def test_non_spanish_summary_without_translation_uses_factual_fallback(self):
        data = self.samples()["paper"].copy()
        data.update({"source_summary":"Official English abstract.","source_language":"en"})
        result = render_result("paper", data)
        self.assertIn("paper: A Monetary Paper", result.editorial_description)
        self.assertNotEqual(result.editorial_description, data["source_summary"])

    def test_verified_non_generative_translation_is_accepted(self):
        data = self.samples()["paper"].copy()
        data.update({
            "source_summary":"Official English abstract.",
            "source_summary_es":"Resumen traducido automáticamente.",
            "source_language":"en",
            "target_language":"es",
            "translation_status":"VERIFIED",
            "translation_method":"machine_translation",
            "translation_engine":"argos-translate",
            "translation_engine_version":"1.9",
            "translation_disclosure":"ES · Traducción automática",
        })
        result = render_result("paper", data)
        self.assertEqual(result.editorial_description, "Resumen traducido automáticamente.")
        self.assertTrue(result.translation["present"])
        self.assertEqual(result.translation["engine"], "argos-translate")

    def test_translation_without_provenance_fails_closed(self):
        data = self.samples()["paper"].copy()
        data.update({"source_summary_es":"Resumen traducido.","source_language":"en"})
        with self.assertRaises(TextRenderError) as ctx:
            render_result("paper", data)
        self.assertEqual(ctx.exception.code, "TRANSLATION_PROVENANCE_MISSING")

    def test_generative_translation_is_forbidden(self):
        data = self.samples()["paper"].copy()
        data.update({
            "source_summary_es":"Resumen traducido.",
            "source_language":"en",
            "target_language":"es",
            "translation_status":"VERIFIED",
            "translation_method":"llm_translation",
            "translation_engine":"gpt",
            "translation_disclosure":"ES · Traducción automática",
        })
        with self.assertRaises(TextRenderError) as ctx:
            render_result("paper", data)
        self.assertEqual(ctx.exception.code, "GENERATIVE_TRANSLATION_FORBIDDEN")

    def test_long_required_text_fails_instead_of_silently_truncating(self):
        data = self.samples()["paper"].copy()
        data["title"] = "X" * 1000
        with self.assertRaises(TextRenderError) as ctx:
            render_result("paper", data)
        self.assertEqual(ctx.exception.code, "TEXT_OVERFLOW")


if __name__ == "__main__":
    unittest.main()
