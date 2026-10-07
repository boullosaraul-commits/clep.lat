#!/usr/bin/env python3
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import ingestar_ad_hoc as adhoc
from planificar import reserve_urgent
from renderizar_texto import render_result
from schema import SchemaError


class UrgentAdHocTests(unittest.TestCase):
    def request(self):
        return {
            "title": "En memoria de una economista",
            "content_type": "INSTITUTIONAL",
            "access_url": "https://example.org/memoria",
            "editorial_text": "CLEP recuerda su obra y contribución.",
            "priority_mode": "URGENT",
            "publish_at": "2026-10-07T18:30:00-06:00",
        }

    def test_institutional_urgent_request_survives_adapter(self):
        canonical = adhoc.canonical_request(self.request())
        self.assertEqual(canonical["content_type"], "INSTITUTIONAL")
        row = adhoc.operational_row(canonical)
        self.assertEqual(row["content_type"], "anuncio_institucional")
        self.assertEqual(row["editorial_text"], "CLEP recuerda su obra y contribución.")
        self.assertEqual(row["priority_mode"], "URGENT")
        self.assertEqual(row["publish_at"], "2026-10-07T18:30:00-06:00")

    def test_urgent_requires_requested_time(self):
        request = self.request()
        request.pop("publish_at")
        with self.assertRaisesRegex(SchemaError, "requiere publish_at"):
            adhoc.canonical_request(request)

    def test_institutional_text_is_deterministic_and_verbatim(self):
        request = self.request()
        result = render_result("anuncio_institucional", request)
        self.assertEqual(result.text_status, "VERIFIED")
        self.assertIn(request["editorial_text"], result.post_text)
        self.assertEqual(result, render_result("anuncio_institucional", request))

    def test_ready_urgent_item_reserves_exact_requested_slot(self):
        tz = ZoneInfo("America/Mexico_City")
        row = {
            "editorial_id": "ED-URGENT-1",
            "origin": "CHAT",
            "flow_type": "AD_HOC",
            "priority_mode": "URGENT",
            "publish_at": "2026-10-07T18:30:00-06:00",
            "estado_editorial": "FICHA_LISTA",
            "notas": "",
        }
        now = datetime(2026, 10, 7, 12, 0, tzinfo=tz)
        reserved = reserve_urgent([row], [row], now, tz)
        self.assertEqual(reserved, [row])
        self.assertEqual(row["fecha_programada"], "2026-10-07")
        self.assertEqual(row["orden_dia"], "18:30")
        self.assertEqual(row["estado_editorial"], "PROGRAMADO")

    def test_urgent_flag_cannot_bypass_readiness(self):
        tz = ZoneInfo("America/Mexico_City")
        row = {
            "editorial_id": "ED-URGENT-BLOCKED",
            "origin": "CHAT",
            "flow_type": "AD_HOC",
            "priority_mode": "URGENT",
            "publish_at": "2026-10-07T18:30:00-06:00",
            "estado_editorial": "PENDIENTE",
        }
        now = datetime(2026, 10, 7, 12, 0, tzinfo=tz)
        self.assertEqual(reserve_urgent([row], [], now, tz), [])
        self.assertEqual(row["estado_editorial"], "PENDIENTE")
        self.assertNotIn("fecha_programada", row)

    def test_requested_slot_collision_fails_closed(self):
        tz = ZoneInfo("America/Mexico_City")
        existing = {
            "fecha_programada": "2026-10-07",
            "orden_dia": "18:30",
            "estado_editorial": "PROGRAMADO",
        }
        urgent = {
            "editorial_id": "ED-URGENT-2",
            "origin": "CHAT",
            "flow_type": "AD_HOC",
            "priority_mode": "URGENT",
            "publish_at": "2026-10-07T18:30:00-06:00",
            "estado_editorial": "FICHA_LISTA",
        }
        now = datetime(2026, 10, 7, 12, 0, tzinfo=tz)
        self.assertEqual(reserve_urgent([existing, urgent], [urgent], now, tz), [])
        self.assertEqual(urgent["estado_editorial"], "FICHA_LISTA")


if __name__ == "__main__":
    unittest.main()
