"""Regresiones de la auditoría, sin llamadas a Facebook ni fuentes externas."""
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))
import adquirir_media
from calidad_visual import VisualCheck, document_check, raster_check
from generar_tarjeta_clep import render
from preparar_publicacion import resolve_acquire_validate_media
from programar_facebook import approved_upload, upload_photo
from resolver_media import resolve_media
from serie_editorial import ACTIVITIES, PUBLICATIONS, RECOMMENDATIONS, editorial_series
import validar_media


class VisualPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/editorial/cola.csv").open() as queue:
            cls.queue = {r["url_id"]: r for r in csv.DictReader(queue)}
        with (ROOT / "data/editorial/candidatos.csv").open() as candidates:
            cls.candidates = {r["candidate_id"]: r for r in csv.DictReader(candidates)}

    def test_historical_rasters_are_not_approved(self):
        # CLACSO, BLS, DOAB, visor PDF y los dos paneles FMI.
        for prefix in ("21ABFBE", "847962C", "CB9D416", "B622193", "B98E614", "59766C4",
                       "845C5F6", "B583918", "00667A6", "04A7C40", "2D4335D", "7B1E0F5"):
            row = next(r for key, r in self.queue.items() if key[5:].startswith(prefix))
            with self.subTest(prefix=prefix):
                content = (ROOT / row["media_path"]).read_bytes()
                if prefix not in {"2D4335D", "7B1E0F5"}:
                    self.assertFalse(raster_check(content, capture_title=row["titulo_original"]).valid)
                else:
                    self.assertEqual(resolve_media(self.candidates[row["url_id"]]).media_method, "deterministic_chart")
                with self.assertRaisesRegex(ValueError, "certificación visual"):
                    approved_upload(row)

    def test_navigation_requires_positive_identity_and_complete_document(self):
        evidence = {"status": 200, "url": "https://publisher.example/article",
                    "mime": "text/html", "ready": True, "title": "Monetary production and effective demand"}
        title = evidence["title"]
        self.assertEqual(document_check(evidence, title).status, "VALID")
        for override, expected in (
            ({"status": 403}, "INVALID"),
            ({"challenge": True}, "INVALID"),
            ({"title": "Calculation error", "headings": [title]}, "INVALID"),
            ({"ready": False}, "UNCERTAIN"),
            ({"title": "Different article"}, "UNCERTAIN"),
            ({"mime": "application/pdf"}, "UNCERTAIN"),
        ):
            self.assertEqual(document_check({**evidence, **override}, title).status, expected)

    def test_fmi_data_and_units_are_preserved(self):
        for key in ("CAND-2D4335DD20896FF2", "CAND-7B1E0F51BCA35BF3"):
            candidate = self.candidates[key]
            result = resolve_media(candidate)
            self.assertEqual(result.media_method, "deterministic_chart")
            self.assertEqual(result.acquisition_payload["unit"], "%")
            self.assertEqual(result.acquisition_payload["points"], json.loads(candidate["data_points_json"]))
            fallback = resolve_media({**candidate, "data_points_json": '[["2026", 1]]'})
            self.assertEqual(fallback.media_method, "deterministic_card")

    def test_blank_rasters_and_altered_dimensions(self):
        buffer = io.BytesIO()
        Image.new("RGB", (1200, 1500), "white").save(buffer, format="PNG")
        self.assertEqual(raster_check(buffer.getvalue()).status, "INVALID")
        self.assertFalse(raster_check(buffer.getvalue(), expected_size=(600, 600)).valid)

    def test_rejected_capture_falls_back_without_reusing_file(self):
        candidate = self.candidates["CAND-CB9D4164E32C0F11"]
        plan = resolve_media(candidate)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / "data/editorial/media"
            media.mkdir(parents=True)
            cached = root / plan.media_path
            cached.write_bytes(b"cached challenge")
            with patch.object(adquirir_media, "ROOT", root), patch.object(adquirir_media, "MEDIA_ROOT", media), \
                 patch.object(validar_media, "ROOT", root), patch.object(validar_media, "MEDIA_ROOT", media), \
                 patch.object(adquirir_media, "capture", return_value=(
                     b"", VisualCheck("INVALID", "challenge fixture"), "HTTP=200"
                 )) as capture:
                result = resolve_acquire_validate_media(candidate, "book")
            capture.assert_called_once()
            self.assertEqual(result["media_method"], "deterministic_card")
            self.assertIn("challenge fixture", result["media_visual_decision"])
            self.assertEqual(cached.read_bytes(), b"cached challenge")

    def test_series_and_october_synopsis_path(self):
        candidate = {"content_type": "paper", "title": "Una obra de terceros", "authors": "A. Autora",
                     "source_url": "https://example.org/paper", "source_name": "Revista", "sinopsis_es": "Síntesis."}
        result = resolve_media(candidate)
        self.assertEqual(result.media_method, "deterministic_card")
        svg = render(result.acquisition_payload)
        for text in (RECOMMENDATIONS, "Síntesis.", "A. Autora", "Revista"):
            self.assertIn(text, svg)
        self.assertEqual(editorial_series(candidate, "convocatoria_evento"), ACTIVITIES)
        self.assertEqual(editorial_series({**candidate, "flujo_editorial": "publicacion_clep"}, "paper"), PUBLICATIONS)
        self.assertEqual(editorial_series({"source_url": "https://clep.lat/publicaciones/traducciones/"}, "edition_translation"), PUBLICATIONS)

    @unittest.skipUnless(shutil.which("rsvg-convert"), "requiere librsvg2-bin")
    def test_final_raster_identity_and_multipart(self):
        import programar_facebook
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / "data/editorial/media"
            media.mkdir(parents=True)
            asset = media / "example.svg"
            asset.write_text(render({"title": "Trabajo y distribución en América Latina",
                                     "source": "Revista", "meta": "A. Autora", "series": RECOMMENDATIONS}))
            row = {"media_path": str(asset.relative_to(root)), "media_type": "image/svg+xml",
                   "media_method": "deterministic_card", "media_source": "CLEP",
                   "media_source_url": "https://example.org/book", "alt_text": "Tarjeta de la obra",
                   "media_content_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                   "media_visual_policy_version": "2", "media_semantic_status": "VALID",
                   "media_editorial_status": "VALID"}
            with patch.object(programar_facebook, "ROOT", root), patch.object(validar_media, "ROOT", root), \
                 patch.object(validar_media, "MEDIA_ROOT", media):
                name, content = approved_upload(row)
                self.assertEqual(name, "example.png")
                self.assertTrue(raster_check(content, expected_size=(1200, 1500)).valid)
                with patch.object(programar_facebook, "http_json", return_value={"id": "photo"}) as request:
                    upload_photo("page", "mock", name, content)
                    self.assertIn(content, request.call_args.args[0].data)
                asset.write_text(asset.read_text().replace("Trabajo", "Trabajos"))
                with self.assertRaises(ValueError):
                    approved_upload(row)


if __name__ == "__main__":
    unittest.main()
