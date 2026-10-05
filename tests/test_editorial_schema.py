#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from schema import (
    CURRENT_SCHEMA_VERSION,
    SchemaError,
    detect_schema_version,
    normalize_legacy_enum,
    validate_candidate,
    validate_publication,
    validate_schema_version,
    validate_transition,
)


class SchemaVersionTests(unittest.TestCase):
    def test_missing_version_is_legacy(self):
        self.assertEqual(detect_schema_version({}), "legacy")

    def test_v1_is_accepted(self):
        self.assertEqual(validate_schema_version({"schema_version": 1}), CURRENT_SCHEMA_VERSION)

    def test_future_version_is_rejected(self):
        with self.assertRaises(SchemaError):
            validate_schema_version({"schema_version": 2})

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(SchemaError):
            validate_schema_version({"schema_version": "banana"})


class LegacyEnumTests(unittest.TestCase):
    def test_content_type_maps(self):
        self.assertEqual(normalize_legacy_enum("content_type", "paper"), "PAPER")

    def test_translation_status_maps(self):
        self.assertEqual(normalize_legacy_enum("translation_status", "AUTOMATICA"), "AUTO_TRANSLATED")

    def test_unknown_legacy_value_fails_closed(self):
        with self.assertRaises(SchemaError):
            normalize_legacy_enum("content_type", "mystery_type")


class CandidateContractTests(unittest.TestCase):
    def base(self):
        return {
            "schema_version": 1,
            "candidate_id": "CAND-TEST",
            "source_id": "test-source",
            "source_type": "academic_oai",
            "title": "A test paper",
            "content_type": "PAPER",
            "candidate_status": "EVALUATED",
            "editorial_decision": "REVIEW",
            "access_status": "PENDING",
        }

    def test_minimal_candidate_is_valid(self):
        validate_candidate(self.base())

    def test_missing_required_field_is_rejected(self):
        row = self.base()
        del row["title"]
        with self.assertRaises(SchemaError):
            validate_candidate(row)

    def test_unknown_enum_is_rejected(self):
        row = self.base()
        row["content_type"] = "ARTICLEISH"
        with self.assertRaises(SchemaError):
            validate_candidate(row)

    def test_access_verified_requires_live_access(self):
        row = self.base()
        row["candidate_status"] = "ACCESS_VERIFIED"
        row["access_status"] = "PENDING"
        with self.assertRaises(SchemaError):
            validate_candidate(row)

    def test_eligible_requires_publishable_decision(self):
        row = self.base()
        row["candidate_status"] = "ELIGIBLE"
        row["access_status"] = "PUBLIC_ACCESS_VERIFIED"
        row["editorial_decision"] = "REVIEW"
        with self.assertRaises(SchemaError):
            validate_candidate(row)

    def test_auto_translation_requires_provenance(self):
        row = self.base()
        row.update({
            "translation_status": "AUTO_TRANSLATED",
            "translation_method": "AUTOMATIC",
            "source_summary": "Original abstract",
            "source_summary_es": "Resumen traducido",
        })
        with self.assertRaises(SchemaError):
            validate_candidate(row)

    def test_auto_translation_with_engine_is_valid(self):
        row = self.base()
        row.update({
            "translation_status": "AUTO_TRANSLATED",
            "translation_method": "AUTOMATIC",
            "translation_engine": "argos",
            "source_summary": "Original abstract",
            "source_summary_es": "Resumen traducido",
        })
        validate_candidate(row)


class PublicationContractTests(unittest.TestCase):
    def base(self):
        return {
            "schema_version": 1,
            "candidate_id": "CAND-TEST",
            "editorial_id": "ED-TEST",
            "title": "A test paper",
            "content_type": "PAPER",
            "preparation_status": "PENDING",
            "publication_status": "NOT_QUEUED",
            "meta_status": "NONE",
        }

    def ready(self):
        row = self.base()
        row.update({
            "preparation_status": "READY",
            "text_status": "VERIFIED",
            "media_status": "VERIFIED",
            "candidate_status": "ELIGIBLE",
            "editorial_decision": "PUBLISHABLE",
        })
        return row

    def test_minimal_publication_is_valid(self):
        validate_publication(self.base())

    def test_validated_requires_verified_text_and_media(self):
        row = self.base()
        row.update({
            "preparation_status": "VALIDATED",
            "text_status": "READY",
            "media_status": "VERIFIED",
        })
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_validated_with_verified_text_and_media_is_valid(self):
        row = self.base()
        row.update({
            "preparation_status": "VALIDATED",
            "text_status": "VERIFIED",
            "media_status": "VERIFIED",
        })
        validate_publication(row)

    def test_ready_requires_verified_text_and_media(self):
        row = self.ready()
        row["text_status"] = "READY"
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_ready_requires_eligible_candidate(self):
        row = self.ready()
        row["candidate_status"] = "EVALUATED"
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_ready_requires_publishable_decision(self):
        row = self.ready()
        row["editorial_decision"] = "REVIEW"
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_ready_with_all_invariants_is_valid(self):
        validate_publication(self.ready())

    def test_meta_reserved_requires_persisted_reservation(self):
        row = self.base()
        row["meta_status"] = "RESERVED"
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_meta_reserved_with_attempt_and_payload_is_valid(self):
        row = self.base()
        row.update({
            "meta_status": "RESERVED",
            "meta_attempt_id": "ATTEMPT-1",
            "meta_payload_hash": "sha256:test",
        })
        validate_publication(row)

    def test_queued_requires_ready_preparation(self):
        row = self.base()
        row["publication_status"] = "QUEUED"
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_scheduled_requires_meta_post(self):
        row = self.ready()
        row.update({
            "publication_status": "SCHEDULED",
            "meta_status": "SCHEDULED",
        })
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_published_requires_meta_verification(self):
        row = self.ready()
        row.update({
            "publication_status": "PUBLISHED",
            "meta_status": "PUBLISHED",
            "meta_post_id": "123",
        })
        with self.assertRaises(SchemaError):
            validate_publication(row)

    def test_quarantine_requires_audit_fields(self):
        row = self.base()
        row["preparation_status"] = "QUARANTINED"
        row["quarantine_reason"] = "SCHEMA_ERROR"
        with self.assertRaises(SchemaError):
            validate_publication(row)


class TransitionTests(unittest.TestCase):
    def test_candidate_forward_transition_is_allowed(self):
        validate_transition("candidate", "DISCOVERED", "EVALUATED")

    def test_candidate_skip_is_rejected(self):
        with self.assertRaises(SchemaError):
            validate_transition("candidate", "DISCOVERED", "ELIGIBLE")

    def test_meta_ambiguous_does_not_retry_directly(self):
        with self.assertRaises(SchemaError):
            validate_transition("meta", "AMBIGUOUS", "REQUESTED")

    def test_published_cannot_go_back_to_scheduled(self):
        with self.assertRaises(SchemaError):
            validate_transition("publication", "PUBLISHED", "SCHEDULED")

    def test_quarantine_can_only_reprocess_to_pending(self):
        validate_transition("preparation", "QUARANTINED", "PENDING")
        with self.assertRaises(SchemaError):
            validate_transition("preparation", "QUARANTINED", "READY")


if __name__ == "__main__":
    unittest.main()
