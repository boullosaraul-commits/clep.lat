#!/usr/bin/env python3
"""E2E offline del pipeline resolución → adquisición de media CLEP.

No usa red, Chrome real ni Meta. Sustituye los efectos externos por dobles
locales y materializa todo dentro de un directorio temporal.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import adquirir_media
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


PNG_BYTES = b"\x89PNG\r\n\x1a\nCLEP-offline-fixture"


class FakeHeaders:
    def get(self, name, default=None):
        if name.lower() == "content-type":
            return "image/png"
        return default


class FakeResponse:
    headers = FakeHeaders()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return PNG_BYTES if size != 0 else b""


class OfflineMediaResolutionE2E(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.media_root = self.root / "data/editorial/media"
        self.root_patch = patch.object(adquirir_media, "ROOT", self.root)
        self.media_patch = patch.object(adquirir_media, "MEDIA_ROOT", self.media_root)
        self.root_patch.start()
        self.media_patch.start()

    def tearDown(self):
        self.media_patch.stop()
        self.root_patch.stop()
        self.tempdir.cleanup()

    @staticmethod
    def fake_capture_run(command, **kwargs):
        del kwargs
        screenshot_arg = next(arg for arg in command if arg.startswith("--screenshot="))
        target = Path(screenshot_arg.split("=", 1)[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_BYTES + b"-capture")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    def acquire_twice(self, candidate, expected_method):
        resolution = resolve_media(candidate)
        self.assertEqual(resolution.media_method, expected_method)

        first = acquire_media(resolution)
        self.assertFalse(first.reused_existing)
        self.assertTrue((self.root / first.media_path).is_file())

        file_count = len([p for p in self.media_root.rglob("*") if p.is_file()])
        second = acquire_media(resolution)
        self.assertTrue(second.reused_existing)
        self.assertEqual(second.media_path, first.media_path)
        self.assertEqual(second.content_sha256, first.content_sha256)
        self.assertEqual(
            len([p for p in self.media_root.rglob("*") if p.is_file()]),
            file_count,
        )
        return resolution, first

    def test_offline_resolution_and_acquisition_all_routes(self):
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
                    _, acquired = self.acquire_twice(candidate, expected_method)
                    acquired_paths.append(acquired.media_path)

        # Una candidatura produce un único asset activo y cada escenario queda
        # materializado exactamente una vez pese al segundo intento idempotente.
        self.assertEqual(len(acquired_paths), len(set(acquired_paths)))
        materialized = [p for p in self.media_root.rglob("*") if p.is_file()]
        self.assertEqual(len(materialized), len(scenarios))

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
        # Sin landing explícita/URL de acceso ni gráfica aplicable, la autoridad
        # única vuelve a recorrer la jerarquía y cae en la tarjeta determinista.
        self.assertEqual(second.media_method, MEDIA_METHOD_DETERMINISTIC_CARD)
        self.assertEqual(second.attempts[0].outcome, "ACQUISITION_FAILED")


if __name__ == "__main__":
    unittest.main()
