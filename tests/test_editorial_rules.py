#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from editorial_rules import academic_publishable, candidate_eligible, publication_certified, schedulable


class EditorialRulesTests(unittest.TestCase):
    def academic_candidate(self):
        return {
            "status": "EVALUADO",
            "relevance_score": "70",
            "editorial_score": "8.2",
            "editorial_decision": "PUBLISHABLE",
            "relevance_reasons": "decision=PROMOCION_AUTOMATICA",
            "source_type": "academic_oai",
            "title": "Demand and distribution",
            "authors": "A. Author",
            "publication_year": "2026",
            "access_url": "https://example.org/paper.pdf",
            "oa_status": "VERIFICADO_FUENTE",
            "access_status": "PUBLIC_ACCESS_VERIFIED",
        }

    def test_academic_publishable_is_single_score_decision_gate(self):
        row = self.academic_candidate()
        self.assertTrue(academic_publishable(row))
        row["editorial_score"] = "6.99"
        self.assertFalse(academic_publishable(row))
        row["editorial_score"] = "9.5"
        row["editorial_decision"] = "REVIEW"
        self.assertFalse(academic_publishable(row))

    def test_candidate_eligibility_requires_verified_access_and_metadata(self):
        row = self.academic_candidate()
        self.assertTrue(candidate_eligible(row, "paper"))
        row["access_status"] = "SOURCE_UNCHECKED"
        self.assertFalse(candidate_eligible(row, "paper"))

    def test_candidate_eligibility_preserves_thematic_gate(self):
        row = self.academic_candidate()
        row["relevance_reasons"] = "decision=REVISION_EDITORIAL"
        self.assertFalse(candidate_eligible(row, "paper"))
        row["relevance_reasons"] += ";pluralismo_rescate=si"
        self.assertTrue(candidate_eligible(row, "paper"))

    def test_publication_certification_requires_text_and_media(self):
        row = {
            "text_status": "VERIFICADO",
            "ficha_es": "Texto determinista",
            "media_rights_status": "PROPIO_DETERMINISTA",
            "media_path": "data/editorial/media/x.svg",
        }
        self.assertTrue(publication_certified(row))
        row["media_path"] = ""
        self.assertFalse(publication_certified(row))

    def test_schedulable_adds_ready_state_and_no_prior_date(self):
        row = {
            "estado_editorial": "FICHA_LISTA",
            "fecha_programada": "",
            "text_status": "VERIFICADO",
            "ficha_es": "Texto determinista",
            "media_rights_status": "VERIFICADO",
            "media_url": "https://example.org/image.png",
        }
        self.assertTrue(schedulable(row))
        row["fecha_programada"] = "2026-10-08"
        self.assertFalse(schedulable(row))


if __name__ == "__main__":
    unittest.main()
