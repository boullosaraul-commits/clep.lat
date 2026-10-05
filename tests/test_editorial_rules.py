#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from editorial_rules import (
    RuleError,
    check_meta_ready,
    check_meta_reservable,
    check_publishable,
    check_schedulable,
    is_meta_ambiguous,
    is_meta_ready,
    is_publishable,
    is_schedulable,
    publishable_score_threshold,
    validate_transition,
)


class EditorialRulesBase(unittest.TestCase):
    def candidate_v1(self):
        return {
            "schema_version": 1,
            "candidate_id": "CAND-RULES",
            "content_type": "PAPER",
            "candidate_status": "ELIGIBLE",
            "editorial_score": "8.0",
            "editorial_decision": "PUBLISHABLE",
        }

    def publication_v1(self):
        row = self.candidate_v1()
        row.update({
            "editorial_id": "ED-RULES",
            "preparation_status": "READY",
            "publication_status": "NOT_QUEUED",
            "meta_status": "NONE",
            "text_status": "VERIFIED",
            "post_text": "Texto editorial determinista.",
            "media_status": "VERIFIED",
            "media_path": "data/editorial/media/test.svg",
        })
        return row

    def publication_legacy(self):
        return {
            "editorial_id": "ED-LEGACY",
            "content_type": "paper",
            "estado_editorial": "FICHA_LISTA",
            "editorial_score": "8.0",
            "editorial_decision": "PUBLISHABLE",
            "text_status": "VERIFICADO",
            "ficha_es": "Texto editorial determinista.",
            "media_rights_status": "PROPIO_DETERMINISTA",
            "media_path": "data/editorial/media/test.svg",
        }


class PublishableRuleTests(EditorialRulesBase):
    def test_threshold_is_read_from_policy(self):
        self.assertGreaterEqual(publishable_score_threshold(), 0.0)

    def test_valid_v1_candidate_is_publishable(self):
        row = self.candidate_v1()
        self.assertTrue(is_publishable(row))
        self.assertTrue(check_publishable(row).ok)

    def test_review_decision_is_not_publishable(self):
        row = self.candidate_v1()
        row["editorial_decision"] = "REVIEW"
        result = check_publishable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "INVALID_EDITORIAL_DECISION")
        self.assertEqual(result.field, "editorial_decision")
        self.assertIn("REVIEW", result.detail)

    def test_score_below_threshold_is_not_publishable(self):
        row = self.candidate_v1()
        row["editorial_score"] = str(max(0.0, publishable_score_threshold() - 0.1))
        result = check_publishable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "EDITORIAL_SCORE_BELOW_THRESHOLD")
        self.assertEqual(result.field, "editorial_score")
        self.assertIn("threshold=", result.detail)

    def test_v1_candidate_must_be_eligible(self):
        row = self.candidate_v1()
        row["candidate_status"] = "EVALUATED"
        result = check_publishable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "CANDIDATE_NOT_ELIGIBLE")
        self.assertEqual(result.field, "candidate_status")

    def test_nonacademic_resource_uses_other_policy(self):
        row = self.candidate_v1()
        row["content_type"] = "RESOURCE"
        result = check_publishable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "NOT_ACADEMIC")


class SchedulableRuleTests(EditorialRulesBase):
    def test_ready_v1_publication_is_schedulable(self):
        row = self.publication_v1()
        self.assertTrue(is_schedulable(row))
        self.assertTrue(check_schedulable(row).ok)

    def test_text_must_be_verified(self):
        row = self.publication_v1()
        row["text_status"] = "READY"
        result = check_schedulable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "TEXT_NOT_VERIFIED")

    def test_media_must_be_verified(self):
        row = self.publication_v1()
        row["media_status"] = "READY"
        result = check_schedulable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "MEDIA_NOT_VERIFIED")

    def test_missing_media_is_rejected(self):
        row = self.publication_v1()
        row["media_path"] = ""
        result = check_schedulable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "MEDIA_MISSING")

    def test_scheduled_v1_publication_is_not_schedulable_again(self):
        row = self.publication_v1()
        row["publication_status"] = "SCHEDULED"
        result = check_schedulable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "PUBLICATION_STATE_NOT_SCHEDULABLE")

    def test_legacy_ready_row_is_schedulable(self):
        self.assertTrue(is_schedulable(self.publication_legacy()))

    def test_legacy_row_with_existing_date_is_not_schedulable(self):
        row = self.publication_legacy()
        row["fecha_programada"] = "2026-10-06"
        result = check_schedulable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "ALREADY_SCHEDULED")


class MetaReservationRuleTests(EditorialRulesBase):
    def test_v1_scheduled_without_attempt_is_reservable(self):
        row = self.publication_v1()
        row["publication_status"] = "SCHEDULED"
        result = check_meta_reservable(row)
        self.assertTrue(result)

    def test_v1_existing_meta_state_is_not_reservable(self):
        row = self.publication_v1()
        row.update({"publication_status": "SCHEDULED", "meta_status": "RESERVED"})
        result = check_meta_reservable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "META_ALREADY_ATTEMPTED")

    def test_existing_post_id_is_not_reservable(self):
        row = self.publication_v1()
        row.update({"publication_status": "SCHEDULED", "meta_post_id": "123"})
        result = check_meta_reservable(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "ALREADY_HAS_META_POST")

    def test_legacy_programmed_row_is_reservable(self):
        row = self.publication_legacy()
        row["estado_editorial"] = "PROGRAMADO"
        row["fecha_programada"] = "2026-10-06"
        row["orden_dia"] = "10:00"
        self.assertTrue(check_meta_reservable(row))


class MetaReadyRuleTests(EditorialRulesBase):
    def reserved_v1(self):
        row = self.publication_v1()
        row.update({
            "publication_status": "SCHEDULED",
            "meta_status": "RESERVED",
            "meta_attempt_id": "ATTEMPT-1",
            "meta_payload_hash": "sha256:test",
            "scheduled_at": "2026-10-06T10:00:00-06:00",
        })
        return row

    def test_reserved_v1_row_is_meta_ready(self):
        row = self.reserved_v1()
        self.assertTrue(is_meta_ready(row))
        self.assertTrue(check_meta_ready(row).ok)

    def test_meta_attempt_id_is_required(self):
        row = self.reserved_v1()
        row["meta_attempt_id"] = ""
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "META_ATTEMPT_ID_MISSING")
        self.assertEqual(result.field, "meta_attempt_id")

    def test_payload_hash_is_required(self):
        row = self.reserved_v1()
        row["meta_payload_hash"] = ""
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "META_PAYLOAD_HASH_MISSING")
        self.assertEqual(result.field, "meta_payload_hash")

    def test_post_text_is_required(self):
        row = self.reserved_v1()
        row["post_text"] = ""
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "POST_TEXT_MISSING")

    def test_media_is_required(self):
        row = self.reserved_v1()
        row["media_path"] = ""
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "MEDIA_MISSING")

    def test_schedule_is_required(self):
        row = self.reserved_v1()
        row["scheduled_at"] = ""
        row["fecha_programada"] = ""
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "SCHEDULE_MISSING")

    def test_existing_post_id_blocks_meta_write(self):
        row = self.reserved_v1()
        row["meta_post_id"] = "123"
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "ALREADY_HAS_META_POST")

    def test_legacy_in_flight_requires_timestamp(self):
        row = self.publication_legacy()
        row.update({
            "estado_editorial": "PROGRAMADO",
            "meta_attempt_status": "IN_FLIGHT",
            "fecha_programada": "2026-10-06",
            "orden_dia": "10:00",
        })
        result = check_meta_ready(row)
        self.assertFalse(result)
        self.assertEqual(result.code, "META_ATTEMPT_TIMESTAMP_MISSING")

    def test_legacy_in_flight_with_timestamp_is_ready(self):
        row = self.publication_legacy()
        row.update({
            "estado_editorial": "PROGRAMADO",
            "meta_attempt_status": "IN_FLIGHT",
            "meta_attempted_at": "2026-10-05T12:00:00-06:00",
            "fecha_programada": "2026-10-06",
            "orden_dia": "10:00",
        })
        self.assertTrue(check_meta_ready(row))


class AmbiguityAndTransitionTests(EditorialRulesBase):
    def test_v1_ambiguous_meta_is_detected(self):
        row = self.publication_v1()
        row["meta_status"] = "AMBIGUOUS"
        self.assertTrue(is_meta_ambiguous(row))

    def test_legacy_in_flight_without_post_is_ambiguous(self):
        row = self.publication_legacy()
        row["meta_attempt_status"] = "IN_FLIGHT"
        self.assertTrue(is_meta_ambiguous(row))

    def test_legacy_in_flight_with_post_is_not_ambiguous(self):
        row = self.publication_legacy()
        row["meta_attempt_status"] = "IN_FLIGHT"
        row["post_nuevo_id"] = "123"
        self.assertFalse(is_meta_ambiguous(row))

    def test_meta_ambiguous_cannot_retry_directly(self):
        with self.assertRaises(RuleError) as ctx:
            validate_transition("meta", "AMBIGUOUS", "REQUESTED")
        self.assertEqual(ctx.exception.code, "META_RETRY_REQUIRES_RECONCILIATION")

    def test_published_cannot_roll_back(self):
        with self.assertRaises(RuleError) as ctx:
            validate_transition("publication", "PUBLISHED", "SCHEDULED")
        self.assertEqual(ctx.exception.code, "PUBLISHED_ROLLBACK_FORBIDDEN")

    def test_quarantine_requires_explicit_reprocess(self):
        with self.assertRaises(RuleError) as ctx:
            validate_transition("preparation", "QUARANTINED", "READY")
        self.assertEqual(ctx.exception.code, "QUARANTINE_REPROCESS_REQUIRED")

    def test_quarantine_can_return_to_pending(self):
        validate_transition("preparation", "QUARANTINED", "PENDING")

    def test_publication_scheduled_can_become_published(self):
        validate_transition("publication", "SCHEDULED", "PUBLISHED")

    def test_meta_scheduled_can_become_published(self):
        validate_transition("meta", "SCHEDULED", "PUBLISHED")


class CrossStageConsistencyTests(EditorialRulesBase):
    def test_schedulable_academic_row_is_also_publishable(self):
        row = self.publication_v1()
        self.assertTrue(check_schedulable(row))
        self.assertTrue(check_publishable(row))

    def test_legacy_schedulable_academic_row_uses_same_publicability_rule(self):
        row = self.publication_legacy()
        self.assertTrue(check_schedulable(row))
        self.assertTrue(check_publishable(row))

    def test_scheduling_then_reservation_preserves_single_policy_path(self):
        row = self.publication_legacy()
        self.assertTrue(check_schedulable(row))
        row["estado_editorial"] = "PROGRAMADO"
        row["fecha_programada"] = "2026-10-06"
        row["orden_dia"] = "10:00"
        self.assertTrue(check_meta_reservable(row))

    def test_reserved_legacy_row_becomes_meta_ready_without_new_policy_decision(self):
        row = self.publication_legacy()
        row.update({
            "estado_editorial": "PROGRAMADO",
            "fecha_programada": "2026-10-06",
            "orden_dia": "10:00",
        })
        self.assertTrue(check_meta_reservable(row))
        row["meta_attempt_status"] = "IN_FLIGHT"
        row["meta_attempted_at"] = "2026-10-05T12:00:00-06:00"
        self.assertTrue(check_meta_ready(row))


if __name__ == "__main__":
    unittest.main()
