#!/usr/bin/env python3
import copy
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import preparar_publicacion as prep


class FakeTextResult:
    post_text = "Texto determinista"
    source_summary = "Resumen fuente"
    source_summary_es = "Resumen ES"
    editorial_description = "Descripción"
    text_method = "deterministic_template"
    text_template = "paper"
    text_template_version = 1
    text_status = "VERIFIED"
    translation = {"present": False}


def visual_fixture(**overrides):
    data = {
        "media_type": "image/svg+xml",
        "media_path": "data/editorial/media/test.svg",
        "media_source": "CLEP deterministic card",
        "media_source_url": "",
        "media_rights_status": "PROPIO_DETERMINISTA",
        "media_method": "deterministic_card",
        "media_resolver_version": "1",
        "media_fallback_level": "4",
        "media_resolution_fingerprint": "fp",
        "media_acquisition_method": "deterministic_card",
        "media_content_sha256": "a" * 64,
        "media_bytes_size": "1269",
        "media_acquisition_reused": "no",
        "alt_text": "Tarjeta CLEP",
        "media_validation_status": "VALID",
        "media_validation_version": "2",
        "detected_media_type": "image/svg+xml",
        "media_width": "1200",
        "media_height": "1500",
    }
    data.update(overrides)
    return data


class PreparationContractTests(unittest.TestCase):
    def base_row(self):
        return {
            "candidate_id": "CAND-STEP6",
            "content_type": "paper",
            "title": "Paper de prueba",
            "authors": "Autora Uno",
            "publication_year": "2026",
            "access_url": "https://example.org/paper",
            "source_url": "https://example.org/paper",
            "source_name": "Fuente",
            "status": "OA_VERIFICADO",
            "relevance_score": "20",
            "editorial_score": "7.0",
            "editorial_decision": "PUBLISHABLE",
            "oa_status": "OA_VERIFICADO",
            "access_status": "PUBLIC_ACCESS_VERIFIED",
        }

    def test_skipped_precondition_never_runs_text_or_media(self):
        row = self.base_row()
        with patch.object(prep, "eligible", return_value=False), \
             patch.object(prep, "render_result") as render, \
             patch.object(prep, "resolve_acquire_validate_media") as media:
            outcome = prep.prepare_one(row, None, ["editorial_id"], "policy")

        self.assertEqual(outcome.status, prep.PREPARATION_SKIPPED)
        self.assertEqual(outcome.stage, prep.STAGE_PRECONDITION)
        render.assert_not_called()
        media.assert_not_called()

    def test_prepare_one_runs_single_linear_sequence(self):
        row = self.base_row()
        order = []

        def fake_meta(kind, candidate):
            order.append("meta")
            return {"title": candidate["title"]}

        def fake_context(candidate):
            order.append("context")
            return {}

        def fake_render(kind, meta):
            order.append("text")
            return FakeTextResult()

        def fake_media(candidate, kind):
            order.append("media")
            return {"media_rights_status": "PROPIO_DETERMINISTA"}

        def fake_assemble(**kwargs):
            order.append("assemble")
            return {
                "editorial_id": "ED-STEP6",
                "estado_editorial": "FICHA_LISTA",
                "media_rights_status": "PROPIO_DETERMINISTA",
            }

        with patch.object(prep, "eligible", return_value=True), \
             patch.object(prep, "meta_for", side_effect=fake_meta), \
             patch.object(prep, "text_context", side_effect=fake_context), \
             patch.object(prep, "render_result", side_effect=fake_render), \
             patch.object(prep, "resolve_acquire_validate_media", side_effect=fake_media), \
             patch.object(prep, "_assemble_queue_row", side_effect=fake_assemble):
            outcome = prep.prepare_one(row, None, ["editorial_id"], "policy")

        self.assertEqual(order, ["meta", "context", "text", "media", "assemble"])
        self.assertTrue(outcome.ready)
        self.assertEqual(outcome.stage, prep.STAGE_COMPLETE)
        self.assertEqual(outcome.candidate_updates, {"status": "FICHA_LISTA"})
        self.assertEqual(outcome.queue_row["estado_editorial"], "FICHA_LISTA")

    def test_structured_text_failure_returns_blocked_with_canonical_code(self):
        row = self.base_row()
        error = prep.TextRenderError("TEXT_TEST", "texto inválido", "title")
        with patch.object(prep, "eligible", return_value=True), \
             patch.object(prep, "meta_for", return_value={}), \
             patch.object(prep, "text_context", return_value={}), \
             patch.object(prep, "render_result", side_effect=error):
            outcome = prep.prepare_one(row, None, ["editorial_id"], "policy")

        self.assertTrue(outcome.blocked)
        self.assertEqual(outcome.stage, prep.STAGE_TEXT)
        self.assertIsNone(outcome.queue_row)
        self.assertEqual(outcome.error_code, "TEXT_TEST")
        self.assertEqual(outcome.error_detail, "texto inválido")
        self.assertIn("TEXT_RENDER", outcome.candidate_updates["notes"])
        self.assertIn("TEXT_TEST", outcome.candidate_updates["notes"])

    def test_plain_value_error_propagates_fail_closed(self):
        row = self.base_row()
        with patch.object(prep, "eligible", return_value=True), \
             patch.object(prep, "meta_for", return_value={}), \
             patch.object(prep, "text_context", return_value={}), \
             patch.object(prep, "render_result", side_effect=ValueError("bug de contrato")):
            with self.assertRaisesRegex(ValueError, "bug de contrato"):
                prep.prepare_one(row, None, ["editorial_id"], "policy")

    def test_unexpected_failure_propagates_fail_closed(self):
        row = self.base_row()
        with patch.object(prep, "eligible", return_value=True), \
             patch.object(prep, "meta_for", return_value={}), \
             patch.object(prep, "text_context", return_value={}), \
             patch.object(prep, "render_result", side_effect=RuntimeError("bug inesperado")):
            with self.assertRaisesRegex(RuntimeError, "bug inesperado"):
                prep.prepare_one(row, None, ["editorial_id"], "policy")

    def test_prepare_one_does_not_mutate_inputs_before_commit(self):
        row = self.base_row()
        existing = {"editorial_id": "ED-STEP6", "estado_editorial": "REVALIDAR"}
        original_row = copy.deepcopy(row)
        original_existing = copy.deepcopy(existing)

        with patch.object(prep, "eligible", return_value=True), \
             patch.object(prep, "meta_for", return_value={"title": row["title"]}), \
             patch.object(prep, "text_context", return_value={}), \
             patch.object(prep, "render_result", return_value=FakeTextResult()), \
             patch.object(prep, "resolve_acquire_validate_media", return_value=visual_fixture()), \
             patch.object(prep, "candidate_fingerprint", return_value="candidate-fp"):
            outcome = prep.prepare_one(
                row,
                existing,
                [
                    "editorial_id",
                    "estado_editorial",
                    *prep.MEDIA_PROVENANCE_FIELDS,
                    *prep.PREPARATION_PROVENANCE_FIELDS,
                ],
                "policy-fp",
            )

        self.assertTrue(outcome.ready)
        self.assertEqual(row, original_row)
        self.assertEqual(existing, original_existing)
        self.assertIsNot(outcome.queue_row, existing)
        self.assertEqual(outcome.queue_row["estado_editorial"], "FICHA_LISTA")
        self.assertEqual(outcome.queue_row["media_validation_status"], "VALID")
        self.assertEqual(outcome.queue_row["preparation_version"], "1")
        self.assertEqual(len(outcome.queue_row["preparation_fingerprint"]), 64)

    def test_queue_fieldnames_include_complete_provenance_contract(self):
        fields = prep._queue_fieldnames(["editorial_id"])
        for field in (
            "source_summary",
            "media_validation_status",
            "media_content_sha256",
            "media_resolver_version",
            "media_fallback_level",
            "media_acquisition_method",
            "media_bytes_size",
            "preparation_version",
            "preparation_fingerprint",
        ):
            self.assertIn(field, fields)
        self.assertEqual(len(fields), len(set(fields)))

    def test_blocked_note_is_idempotent(self):
        row = {"notes": "base"}
        note = "preparación bloqueada [TEXT_RENDER] TEST: fallo"
        once = prep._append_note(row, note)
        twice = prep._append_note({"notes": once}, note)
        self.assertEqual(once, twice)


class PreparationFingerprintTests(unittest.TestCase):
    def row(self):
        return PreparationContractTests().base_row()

    def test_reuse_flag_does_not_change_preparation_fingerprint(self):
        row = self.row()
        first = visual_fixture(media_acquisition_reused="no")
        second = visual_fixture(media_acquisition_reused="si")
        fp1 = prep._preparation_fingerprint(row, "policy", FakeTextResult(), first)
        fp2 = prep._preparation_fingerprint(row, "policy", FakeTextResult(), second)
        self.assertEqual(fp1, fp2)

    def test_material_hash_change_changes_preparation_fingerprint(self):
        row = self.row()
        first = visual_fixture(media_content_sha256="a" * 64)
        second = visual_fixture(media_content_sha256="b" * 64)
        fp1 = prep._preparation_fingerprint(row, "policy", FakeTextResult(), first)
        fp2 = prep._preparation_fingerprint(row, "policy", FakeTextResult(), second)
        self.assertNotEqual(fp1, fp2)

    def test_text_change_changes_preparation_fingerprint(self):
        row = self.row()
        changed_text = SimpleNamespace(
            post_text="Otro texto",
            source_summary=FakeTextResult.source_summary,
            source_summary_es=FakeTextResult.source_summary_es,
            editorial_description=FakeTextResult.editorial_description,
            text_method=FakeTextResult.text_method,
            text_template=FakeTextResult.text_template,
            text_template_version=FakeTextResult.text_template_version,
            text_status=FakeTextResult.text_status,
            translation=FakeTextResult.translation,
        )
        fp1 = prep._preparation_fingerprint(row, "policy", FakeTextResult(), visual_fixture())
        fp2 = prep._preparation_fingerprint(row, "policy", changed_text, visual_fixture())
        self.assertNotEqual(fp1, fp2)


class AtomicCsvTests(unittest.TestCase):
    def test_same_serialized_content_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.csv"
            rows = [{"a": "1", "b": "2"}]
            first = prep._write_csv_atomic(path, ["a", "b"], rows)
            before = path.stat().st_ino
            second = prep._write_csv_atomic(path, ["a", "b"], rows)
            after = path.stat().st_ino

            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(before, after)

    def test_serialization_failure_preserves_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.csv"
            path.write_text("original\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                prep._write_csv_atomic(path, ["a"], [{"a": "1", "extra": "boom"}])

            self.assertEqual(path.read_text(encoding="utf-8"), "original\n")
            self.assertEqual(list(Path(directory).glob(".queue.csv.*.tmp")), [])


class MediaFallbackContractTests(unittest.TestCase):
    def resolution(self, method):
        return SimpleNamespace(
            media_method=method,
            media_source="Fuente",
            media_source_url="https://example.org",
            media_rights_status="VERIFICADO",
            resolver_version=1,
            fallback_level=1,
            resolution_fingerprint=f"fp-{method}",
            alt_text="Alt",
        )

    def acquired(self, method):
        return SimpleNamespace(
            media_type_declared="image/png",
            media_path=f"data/editorial/media/{method}.png",
            acquisition_method=method,
            content_sha256="a" * 64,
            bytes_written=4096,
            reused_existing=False,
        )

    def valid(self):
        return SimpleNamespace(
            valid=True,
            status="VALID",
            validation_version=2,
            detected_type="image/png",
            width=1200,
            height=1500,
            errors=(),
        )

    def invalid(self, code):
        return SimpleNamespace(
            valid=False,
            errors=(SimpleNamespace(code=code, detail="asset inválido"),),
        )

    def test_acquisition_fallback_requests_next_resolver_method(self):
        first = self.resolution("official_image")
        second = self.resolution("deterministic_card")
        error = prep.MediaAcquisitionError("MEDIA_DOWNLOAD_FAILED", "caída")

        with patch.object(prep, "resolve_media", side_effect=[first, second]) as resolver, \
             patch.object(prep, "acquire_media", side_effect=[error, self.acquired("deterministic_card")]), \
             patch.object(prep, "validate_media", return_value=self.valid()):
            visual = prep.resolve_acquire_validate_media({"candidate_id": "CAND-X"}, "paper")

        self.assertEqual(visual["media_method"], "deterministic_card")
        self.assertEqual(visual["media_resolver_version"], "1")
        self.assertEqual(visual["media_acquisition_method"], "deterministic_card")
        self.assertEqual(visual["media_bytes_size"], "4096")
        self.assertEqual(resolver.call_count, 2)
        rejected = resolver.call_args_list[1].kwargs["rejected_methods"]
        self.assertIn("official_image", rejected)

    def test_validation_fallback_requests_next_resolver_method(self):
        first = self.resolution("official_image")
        second = self.resolution("deterministic_card")

        with patch.object(prep, "resolve_media", side_effect=[first, second]) as resolver, \
             patch.object(
                 prep,
                 "acquire_media",
                 side_effect=[self.acquired("official_image"), self.acquired("deterministic_card")],
             ), \
             patch.object(
                 prep,
                 "validate_media",
                 side_effect=[self.invalid("MEDIA_RASTER_CORRUPT"), self.valid()],
             ):
            visual = prep.resolve_acquire_validate_media({"candidate_id": "CAND-X"}, "paper")

        self.assertEqual(visual["media_method"], "deterministic_card")
        self.assertEqual(resolver.call_count, 2)
        rejected = resolver.call_args_list[1].kwargs["rejected_methods"]
        self.assertIn("official_image", rejected)

    def test_repeated_resolver_method_fails_closed(self):
        repeated = self.resolution("official_image")
        error = prep.MediaAcquisitionError("MEDIA_DOWNLOAD_FAILED", "caída")

        with patch.object(prep, "resolve_media", side_effect=[repeated, repeated]), \
             patch.object(prep, "acquire_media", side_effect=error):
            with self.assertRaises(prep.MediaFallbackError) as ctx:
                prep.resolve_acquire_validate_media({"candidate_id": "CAND-X"}, "paper")

        self.assertEqual(ctx.exception.code, prep.ERROR_MEDIA_METHOD_REPEATED)

    def test_fallback_attempt_limit_is_explicit(self):
        first = self.resolution("official_image")
        second = self.resolution("explicit_cover")
        error = prep.MediaAcquisitionError("MEDIA_DOWNLOAD_FAILED", "caída")

        with patch.object(prep, "MAX_MEDIA_ATTEMPTS", 2), \
             patch.object(prep, "resolve_media", side_effect=[first, second]), \
             patch.object(prep, "acquire_media", side_effect=error):
            with self.assertRaises(prep.MediaFallbackError) as ctx:
                prep.resolve_acquire_validate_media({"candidate_id": "CAND-X"}, "paper")

        self.assertEqual(ctx.exception.code, prep.ERROR_MEDIA_FALLBACK_EXHAUSTED)

    def test_nonfallback_validation_error_stops_immediately(self):
        resolution = self.resolution("official_image")
        with patch.object(prep, "resolve_media", return_value=resolution), \
             patch.object(prep, "acquire_media", return_value=self.acquired("official_image")), \
             patch.object(
                 prep,
                 "validate_media",
                 return_value=self.invalid("MEDIA_HASH_MISMATCH"),
             ):
            with self.assertRaises(prep.MediaValidationBlocked):
                prep.resolve_acquire_validate_media({"candidate_id": "CAND-X"}, "paper")


class InvalidationBoundaryTests(unittest.TestCase):
    def test_scheduled_meta_row_is_not_invalidated(self):
        candidate = {
            "candidate_id": "CAND-LOCKED",
            "editorial_score": "9.0",
            "editorial_decision": "PUBLISHABLE",
        }
        queued = {
            "url_id": "CAND-LOCKED",
            "flujo_editorial": "novedad",
            "estado_editorial": "PROGRAMADO",
            "meta_attempt_status": "SCHEDULED",
            "post_nuevo_id": "123",
            "candidate_fingerprint": "old",
            "editorial_policy_fingerprint": "old",
            "editorial_score": "7.0",
            "editorial_decision": "PUBLISHABLE",
        }
        before = copy.deepcopy(queued)

        count = prep.invalidate_stale_queue_rows(
            [queued], {"CAND-LOCKED": candidate}, "new-policy"
        )

        self.assertEqual(count, 0)
        self.assertEqual(queued, before)


if __name__ == "__main__":
    unittest.main()
