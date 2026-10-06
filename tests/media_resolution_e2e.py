#!/usr/bin/env python3
"""E2E offline del pipeline resolución → adquisición → validación de media CLEP.

No usa red, Chrome real ni Meta. Sustituye los efectos externos por dobles
locales y materializa todo dentro de un directorio temporal.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import adquirir_media
import validar_media
from adquirir_media import acquire_media
from resolver_media import (
    MEDIA_METHOD_DETERMINISTIC_CARD,
    MEDIA_METHOD_DETERMINISTIC_CHART,
    MEDIA_METHOD_EXPLICIT_COVER,
    MEDIA_METHOD_EXPLICIT_THUMBNAIL,
    MEDIA_METHOD_OFFICIAL_IMAGE,
    MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
    resolve_media,
)
from validar_media import validate_media


def png_fixture(width=1200, height=1500):
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


PNG_BYTES = png_fixture()
SMALL_PNG_BYTES = png_fixture(300, 300)


class FakeHeaders:
    def __init__(self, content_type="image/png"):
        self.content_type = content_type

    def get(self, name, default=None):
        if name.lower() == "content-type":
            return self.content_type
        return default


class FakeResponse:
    def __init__(self, content=PNG_BYTES, content_type="image/png"):
        self.content = content
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return self.content if size != 0 else b""


class OfflineMediaPipelineE2E(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.media_root = self.root / "data/editorial/media"
        self.media_root.mkdir(parents=True)

        self.patches = [
            patch.object(adquirir_media, "ROOT", self.root),
            patch.object(adquirir_media, "MEDIA_ROOT", self.media_root),
            patch.object(validar_media, "ROOT", self.root),
            patch.object(validar_media, "MEDIA_ROOT", self.media_root.resolve()),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tempdir.cleanup()

    @staticmethod
    def fake_capture_run(command, **kwargs):
        del kwargs
        screenshot_arg = next(arg for arg in command if arg.startswith("--screenshot="))
        target = Path(screenshot_arg.split("=", 1)[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_BYTES)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    def validate_acquired(self, resolution, acquired):
        result = validate_media(
            {
                "media_path": acquired.media_path,
                "media_type": acquired.media_type_declared,
                "media_method": resolution.media_method,
                "media_content_sha256": acquired.content_sha256,
                "media_resolution_fingerprint": resolution.resolution_fingerprint,
            }
        )
        return result

    def acquire_validate_twice(self, candidate, expected_method):
        resolution = resolve_media(candidate)
        self.assertEqual(resolution.media_method, expected_method)

        first = acquire_media(resolution)
        first_validation = self.validate_acquired(resolution, first)
        self.assertTrue(first_validation.valid, first_validation.to_dict())
        self.assertFalse(first.reused_existing)
        self.assertTrue((self.root / first.media_path).is_file())

        file_count = len([p for p in self.media_root.rglob("*") if p.is_file()])
        second = acquire_media(resolution)
        second_validation = self.validate_acquired(resolution, second)
        self.assertTrue(second_validation.valid, second_validation.to_dict())
        self.assertTrue(second.reused_existing)
        self.assertEqual(second.media_path, first.media_path)
        self.assertEqual(second.content_sha256, first.content_sha256)
        self.assertEqual(first_validation, second_validation)
        self.assertEqual(
            len([p for p in self.media_root.rglob("*") if p.is_file()]),
            file_count,
        )
        return resolution, first, first_validation

    def test_offline_full_pipeline_all_routes(self):
        scenarios = [
            (
                {
                    "candidate_id": "CAND-OFFICIAL",
                    "content_type": "paper",
                    "title": "Official image item",
                    "source_name": "Example Journal",
                    "official_image_url": "https://example.org/official.png",
                    "official_image_rights": "VERIFICADO",
                    "official_image_source": "Example Journal",
                    "official_image_alt": "Imagen oficial del artículo",
                },
                MEDIA_METHOD_OFFICIAL_IMAGE,
            ),
            (
                {
                    "candidate_id": "CAND-COVER",
                    "content_type": "book",
                    "title": "Book with cover",
                    "source_name": "Example Press",
                    "cover_url": "https://example.org/cover.png",
                    "cover_rights": "VERIFICADO",
                    "cover_source": "Example Press",
                },
                MEDIA_METHOD_EXPLICIT_COVER,
            ),
            (
                {
                    "candidate_id": "CAND-THUMB",
                    "content_type": "video",
                    "title": "Video with thumbnail",
                    "source_name": "Example Channel",
                    "thumbnail_url": "https://example.org/thumb.png",
                    "thumbnail_rights": "VERIFICADO",
                    "thumbnail_source": "Example Channel",
                },
                MEDIA_METHOD_EXPLICIT_THUMBNAIL,
            ),
            (
                {
                    "candidate_id": "CAND-CAPTURE",
                    "content_type": "paper",
                    "title": "Official landing item",
                    "source_name": "Example Repository",
                    "official_landing_url": "https://example.org/item",
                },
                MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
            ),
            (
                {
                    "candidate_id": "CAND-CHART",
                    "content_type": "dataset_grafica",
                    "indicator_or_dataset": "Employment rate",
                    "geography": "Mexico",
                    "source_name": "INEGI",
                    "data_points": [["2025", 60.1], ["2026", 61.2]],
                },
                MEDIA_METHOD_DETERMINISTIC_CHART,
            ),
            (
                {
                    "candidate_id": "CAND-CARD",
                    "content_type": "paper",
                    "title": "Card fallback item",
                    "authors": "A. Author",
                    "publication_year": "2026",
                    "source_name": "Example Series",
                },
                MEDIA_METHOD_DETERMINISTIC_CARD,
            ),
        ]

        acquired_paths = []
        with patch("adquirir_media.urllib.request.urlopen", return_value=FakeResponse()), patch(
            "adquirir_media.shutil.which", return_value="/usr/bin/chromium"
        ), patch("adquirir_media.subprocess.run", side_effect=self.fake_capture_run):
            for candidate, expected_method in scenarios:
                with self.subTest(method=expected_method):
                    _, acquired, validated = self.acquire_validate_twice(candidate, expected_method)
                    self.assertEqual(validated.status, "VALID")
                    acquired_paths.append(acquired.media_path)

        # Cada candidatura termina con un único asset materializado y validado.
        self.assertEqual(len(acquired_paths), len(set(acquired_paths)))
        materialized = [p for p in self.media_root.rglob("*") if p.is_file()]
        self.assertEqual(len(materialized), len(scenarios))

    def test_invalid_materialized_asset_returns_control_to_resolver(self):
        candidate = {
            "candidate_id": "CAND-INVALID-MATERIAL",
            "content_type": "paper",
            "title": "Fallback after invalid official image",
            "source_name": "Example Source",
            "official_image_url": "https://example.org/small.png",
            "official_image_rights": "VERIFICADO",
            "official_image_source": "Example Source",
        }

        first_resolution = resolve_media(candidate)
        self.assertEqual(first_resolution.media_method, MEDIA_METHOD_OFFICIAL_IMAGE)

        with patch(
            "adquirir_media.urllib.request.urlopen",
            return_value=FakeResponse(SMALL_PNG_BYTES),
        ):
            first_acquired = acquire_media(first_resolution)
        first_validation = self.validate_acquired(first_resolution, first_acquired)
        self.assertFalse(first_validation.valid)
        self.assertIn(
            "MEDIA_DIMENSIONS_TOO_SMALL",
            {error.code for error in first_validation.errors},
        )

        rejected_reason = "; ".join(
            f"{error.code}: {error.detail}" for error in first_validation.errors
        )
        second_resolution = resolve_media(
            candidate,
            rejected_methods={first_resolution.media_method: rejected_reason},
        )
        self.assertEqual(second_resolution.media_method, MEDIA_METHOD_DETERMINISTIC_CARD)
        self.assertEqual(second_resolution.attempts[0].outcome, "ACQUISITION_FAILED")

        second_acquired = acquire_media(second_resolution)
        second_validation = self.validate_acquired(second_resolution, second_acquired)
        self.assertTrue(second_validation.valid, second_validation.to_dict())

        # Sólo el segundo asset es publicable; el primero queda como evidencia
        # material rechazada y nunca se confunde con el asset activo final.
        self.assertNotEqual(first_acquired.media_path, second_acquired.media_path)
        self.assertEqual(second_validation.status, "VALID")

    def test_acquisition_failure_returns_control_to_resolver(self):
        candidate = {
            "candidate_id": "CAND-FALLBACK",
            "content_type": "paper",
            "title": "Fallback after failed official image",
            "source_name": "Example Source",
            "official_image_url": "https://example.org/broken.png",
            "official_image_rights": "VERIFICADO",
            "official_image_source": "Example Source",
        }
        first = resolve_media(candidate)
        self.assertEqual(first.media_method, MEDIA_METHOD_OFFICIAL_IMAGE)

        second = resolve_media(
            candidate,
            rejected_methods={
                first.media_method: "MEDIA_DOWNLOAD_FAILED: fixture offline",
            },
        )
        self.assertEqual(second.media_method, MEDIA_METHOD_DETERMINISTIC_CARD)
        self.assertEqual(second.attempts[0].outcome, "ACQUISITION_FAILED")


if __name__ == "__main__":
    unittest.main()
