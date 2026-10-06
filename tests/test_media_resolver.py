#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from resolver_media import (
    ERROR_METHOD_INVALID,
    ERROR_RESOLUTION_FAILED,
    MEDIA_HIERARCHY,
    MEDIA_METHOD_DETERMINISTIC_CARD,
    MEDIA_METHOD_DETERMINISTIC_CHART,
    MEDIA_METHOD_EXPLICIT_COVER,
    MEDIA_METHOD_EXPLICIT_THUMBNAIL,
    MEDIA_METHOD_OFFICIAL_IMAGE,
    MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
    OUTCOME_ACQUISITION_FAILED,
    OUTCOME_INSUFFICIENT_DATA,
    OUTCOME_RIGHTS_UNVERIFIED,
    RIGHTS_OFFICIAL_CAPTURE,
    RIGHTS_OWN_DETERMINISTIC,
    RIGHTS_VERIFIED,
    MediaResolutionError,
    factual_alt_text,
    resolve_media,
)


class MediaResolverTests(unittest.TestCase):
    def base(self):
        return {
            "candidate_id": "CAND-TEST-001",
            "content_type": "paper",
            "title": "Monetary production and effective demand",
            "authors": "A. Author",
            "publication_year": "2026",
            "source_name": "Example Institute",
        }

    def test_hierarchy_is_frozen_in_expected_order(self):
        self.assertEqual(
            MEDIA_HIERARCHY,
            (
                (1, MEDIA_METHOD_OFFICIAL_IMAGE),
                (2, MEDIA_METHOD_EXPLICIT_COVER),
                (2, MEDIA_METHOD_EXPLICIT_THUMBNAIL),
                (3, MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE),
                (4, MEDIA_METHOD_DETERMINISTIC_CHART),
                (4, MEDIA_METHOD_DETERMINISTIC_CARD),
            ),
        )

    def test_official_image_has_highest_priority(self):
        candidate = self.base()
        candidate.update(
            {
                "official_image_url": "https://example.org/official.png",
                "official_image_rights": "VERIFICADO",
                "official_image_source": "Example Institute",
                "official_image_alt": "Imagen oficial del recurso",
                "cover_url": "https://example.org/cover.jpg",
                "cover_rights": "VERIFICADO",
                "cover_source": "Example Institute",
                "source_url": "https://example.org/resource",
            }
        )
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_OFFICIAL_IMAGE)
        self.assertEqual(result.fallback_level, 1)
        self.assertEqual(result.media_rights_status, RIGHTS_VERIFIED)
        self.assertEqual(result.alt_text, "Imagen oficial del recurso")
        self.assertEqual(len(result.attempts), 1)
        self.assertTrue(result.attempts[0].selected)

    def test_unverified_official_image_falls_back(self):
        candidate = self.base()
        candidate.update(
            {
                "official_image_url": "https://example.org/official.png",
                "official_image_rights": "NO_VERIFICADO",
                "official_image_source": "Example Institute",
            }
        )
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_DETERMINISTIC_CARD)
        self.assertEqual(result.attempts[0].outcome, OUTCOME_RIGHTS_UNVERIFIED)

    def test_cover_precedes_thumbnail(self):
        candidate = self.base()
        candidate.update(
            {
                "cover_url": "https://example.org/cover.jpg",
                "cover_rights": "VERIFICADO",
                "cover_source": "Publisher",
                "thumbnail_url": "https://example.org/thumb.jpg",
                "thumbnail_rights": "VERIFICADO",
                "thumbnail_source": "Publisher",
            }
        )
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_EXPLICIT_COVER)
        self.assertEqual(result.fallback_level, 2)
        self.assertEqual(result.alt_text, f"Portada: {candidate['title']}")

    def test_thumbnail_is_used_when_cover_is_absent(self):
        candidate = self.base()
        candidate.update(
            {
                "thumbnail_url": "https://example.org/thumb.jpg",
                "thumbnail_rights": "VERIFICADO",
                "thumbnail_source": "Video platform",
            }
        )
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_EXPLICIT_THUMBNAIL)
        self.assertEqual(result.alt_text, f"Miniatura: {candidate['title']}")

    def test_official_landing_capture_precedes_deterministic_visuals(self):
        candidate = self.base()
        candidate["source_url"] = "https://example.org/resource"
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE)
        self.assertEqual(result.fallback_level, 3)
        self.assertEqual(result.media_rights_status, RIGHTS_OFFICIAL_CAPTURE)
        self.assertEqual(
            result.alt_text,
            f"Captura de la página oficial: {candidate['title']}",
        )
        self.assertTrue(result.media_path.endswith(".png"))
        self.assertEqual(result.acquisition_payload["kind"], "landing_capture")

    def test_dataset_with_sufficient_points_selects_chart(self):
        candidate = self.base()
        candidate.update(
            {
                "content_type": "dataset_grafica",
                "indicator_or_dataset": "Employment rate",
                "geography": "Mexico",
                "official_source": "INEGI",
                "data_points": [["2025", 60.1], ["2026", 61.2]],
            }
        )
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_DETERMINISTIC_CHART)
        self.assertEqual(result.media_rights_status, RIGHTS_OWN_DETERMINISTIC)
        self.assertEqual(result.alt_text, "Gráfica CLEP: Monetary production and effective demand")
        self.assertTrue(result.media_path.endswith(".svg"))
        self.assertEqual(result.acquisition_payload["kind"], "deterministic_chart")

    def test_dataset_with_insufficient_points_falls_back_to_card(self):
        candidate = self.base()
        candidate.update(
            {
                "content_type": "dataset_grafica",
                "indicator_or_dataset": "Employment rate",
                "official_source": "INEGI",
                "data_points": [["2026", 61.2]],
            }
        )
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_DETERMINISTIC_CARD)
        chart_attempt = next(
            attempt
            for attempt in result.attempts
            if attempt.method == MEDIA_METHOD_DETERMINISTIC_CHART
        )
        self.assertEqual(chart_attempt.outcome, OUTCOME_INSUFFICIENT_DATA)

    def test_card_is_universal_factual_fallback(self):
        candidate = self.base()
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, MEDIA_METHOD_DETERMINISTIC_CARD)
        self.assertEqual(result.media_rights_status, RIGHTS_OWN_DETERMINISTIC)
        self.assertEqual(result.alt_text, f"Tarjeta CLEP: {candidate['title']}")
        self.assertEqual(result.acquisition_payload["kind"], "deterministic_card")

    def test_rejected_method_is_recorded_and_next_priority_is_recomputed(self):
        candidate = self.base()
        candidate.update(
            {
                "official_image_url": "https://example.org/official.png",
                "official_image_rights": "VERIFICADO",
                "official_image_source": "Example Institute",
                "cover_url": "https://example.org/cover.jpg",
                "cover_rights": "VERIFICADO",
                "cover_source": "Publisher",
            }
        )
        result = resolve_media(
            candidate,
            rejected_methods={MEDIA_METHOD_OFFICIAL_IMAGE: "MEDIA_DOWNLOAD_FAILED"},
        )
        self.assertEqual(result.media_method, MEDIA_METHOD_EXPLICIT_COVER)
        self.assertEqual(result.attempts[0].method, MEDIA_METHOD_OFFICIAL_IMAGE)
        self.assertEqual(result.attempts[0].outcome, OUTCOME_ACQUISITION_FAILED)
        self.assertFalse(result.attempts[0].selected)

    def test_unknown_rejected_method_fails_closed(self):
        with self.assertRaises(MediaResolutionError) as ctx:
            resolve_media(self.base(), rejected_methods={"mystery": "failed"})
        self.assertEqual(ctx.exception.code, ERROR_METHOD_INVALID)

    def test_missing_minimum_metadata_fails_closed_with_attempt_trace(self):
        with self.assertRaises(MediaResolutionError) as ctx:
            resolve_media({})
        self.assertEqual(ctx.exception.code, ERROR_RESOLUTION_FAILED)
        self.assertEqual(len(ctx.exception.attempts), len(MEDIA_HIERARCHY))

    def test_same_input_produces_same_resolution(self):
        candidate = self.base()
        first = resolve_media(candidate)
        second = resolve_media(dict(candidate))
        self.assertEqual(first.media_method, second.media_method)
        self.assertEqual(first.media_path, second.media_path)
        self.assertEqual(first.media_url, second.media_url)
        self.assertEqual(first.resolution_fingerprint, second.resolution_fingerprint)
        self.assertEqual(first.acquisition_payload, second.acquisition_payload)
        self.assertEqual(first.attempts, second.attempts)

    def test_fingerprint_changes_when_relevant_card_metadata_changes(self):
        first = resolve_media(self.base())
        changed = self.base()
        changed["title"] = "A different title"
        second = resolve_media(changed)
        self.assertNotEqual(first.resolution_fingerprint, second.resolution_fingerprint)
        self.assertNotEqual(first.media_path, second.media_path)

    def test_alt_text_policy_is_factual(self):
        candidate = self.base()
        self.assertEqual(
            factual_alt_text(MEDIA_METHOD_DETERMINISTIC_CARD, candidate),
            f"Tarjeta CLEP: {candidate['title']}",
        )
        self.assertEqual(
            factual_alt_text(MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE, candidate),
            f"Captura de la página oficial: {candidate['title']}",
        )


if __name__ == "__main__":
    unittest.main()
