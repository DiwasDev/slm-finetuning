"""
Unit tests for schema and validators (TASK-1-SCHEMA).
Verifies FR-3, FR-8, NFR-2, NFR-3, AC-2, AC-4.
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema import (
    validate_label_taxonomy,
    validate_provenance,
    validate_state_transition,
    validate_decision_record,
)


def test_valid_label_taxonomy():
    valid = {
        "pain_point": "Manual bookkeeping delays financial statements",
        "personalization_angle": "Referenced post about tax busy season burnout",
        "subject": "Quick question on workflow bottlenecks",
        "body": "Hi John, noticed your firm is handling complex multi-state returns...",
    }
    ok, err = validate_label_taxonomy(valid)
    assert ok, f"Expected valid taxonomy to pass, got error: {err}"


def test_missing_field_fails():
    incomplete = {
        "pain_point": "Manual bookkeeping delays",
        "subject": "Question",
        "body": "Hi John...",
    }
    ok, err = validate_label_taxonomy(incomplete)
    assert not ok, "Expected incomplete taxonomy to fail"
    assert "personalization_angle" in err


def test_extra_field_fails():
    extra = {
        "pain_point": "Manual bookkeeping",
        "personalization_angle": "Post reference",
        "subject": "Hook",
        "body": "Body text",
        "unauthorized_field": "123",
    }
    ok, err = validate_label_taxonomy(extra)
    assert not ok, "Expected extra fields to fail"
    assert "unauthorized_field" in err


def test_provenance_validation():
    valid_prov = {
        "source_id": "REC-marketing-a1b2c3d4",
        "source_file": "data/marketing.json",
        "source_hash": "a" * 64,
    }
    ok, err = validate_provenance(valid_prov)
    assert ok, f"Expected valid provenance to pass, got: {err}"

    # Invalid hash length
    bad_hash = dict(valid_prov, source_hash="too_short")
    ok, err = validate_provenance(bad_hash)
    assert not ok, "Expected short hash to fail"

    # Invalid source_id format
    bad_id = dict(valid_prov, source_id="bad_id_without_prefix")
    ok, err = validate_provenance(bad_id)
    assert not ok, "Expected invalid source_id to fail"


def test_state_transitions():
    # Legal
    ok, _ = validate_state_transition("proposed", "needs-review")
    assert ok
    ok, _ = validate_state_transition("needs-review", "accepted")
    assert ok
    ok, _ = validate_state_transition("needs-review", "revised")
    assert ok
    ok, _ = validate_state_transition("accepted", "superseded")
    assert ok

    # Illegal
    ok, err = validate_state_transition("proposed", "accepted")
    assert not ok, "proposed cannot jump directly to accepted without review"
    ok, err = validate_state_transition("rejected", "accepted")
    assert not ok, "rejected cannot jump directly to accepted"


def test_decision_record():
    valid_decision = {
        "source_id": "REC-accounting-12345678",
        "source_file": "data/accounting.json",
        "source_hash": "b" * 64,
        "state": "accepted",
        "labels": {
            "pain_point": "Tax prep bottlenecks",
            "personalization_angle": "Nick Fair LinkedIn comment",
            "subject": "Fair & Co CPAs question",
            "body": "Hi Nick, noticed your comments on AI in tax prep...",
        },
        "reviewer": "Diwas",
        "reviewed_at": "2026-11-12T15:30:00Z",
        "notes": "Good authentic angle",
    }
    ok, err = validate_decision_record(valid_decision)
    assert ok, f"Expected valid decision to pass, got: {err}"


if __name__ == "__main__":
    test_valid_label_taxonomy()
    test_missing_field_fails()
    test_extra_field_fails()
    test_provenance_validation()
    test_state_transitions()
    test_decision_record()
    print("ALL SCHEMA TESTS PASSED")
