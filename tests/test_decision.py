"""
Unit tests for decision state machine engine (TASK-4-DECISION).
Verifies FR-6, FR-10, AC-4, AC-6.
"""

import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision import (
    init_decision_store,
    transition_decision_state,
    detect_and_invalidate_stale,
)


def create_mock_candidate(source_id="REC-marketing-abcdef123456"):
    return {
        "candidate_id": "CAND-marketing-abcdef123456",
        "source_id": source_id,
        "source_file": "data/marketing.json",
        "source_hash": "d" * 64,
        "state": "proposed",
        "labels": {
            "pain_point": "Inefficient lead triage",
            "personalization_angle": "Article on agency operations",
            "subject": "Question about triage",
            "body": "Hey Alex, saw your article...",
        },
    }


def test_decision_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_decisions.json"
        store = init_decision_store(store_path)
        cand = create_mock_candidate()
        sid = cand["source_id"]

        # proposed -> needs-review
        rec = transition_decision_state(store, sid, "needs-review", candidate=cand)
        assert rec["state"] == "needs-review"
        assert len(store["history"]) == 1

        # needs-review -> accepted
        rec2 = transition_decision_state(store, sid, "accepted", reviewer="Diwas", notes="Approved verbatim")
        assert rec2["state"] == "accepted"
        assert rec2["reviewer"] == "Diwas"
        assert len(store["history"]) == 2


def test_revised_transition():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_decisions.json"
        store = init_decision_store(store_path)
        cand = create_mock_candidate("REC-accounting-12345678abcd")
        sid = cand["source_id"]

        transition_decision_state(store, sid, "needs-review", candidate=cand)

        revised_labels = {
            "pain_point": "Manual reconciliation takes 3 days",
            "personalization_angle": "Nick Fair LinkedIn post on review staffing",
            "subject": "Fair & Co tax reconciliation bottleneck?",
            "body": "Hi Nick, noticed your comment on AI in prep work...",
        }

        rec = transition_decision_state(
            store,
            sid,
            "revised",
            reviewer="Diwas",
            notes="Tightened the hook",
            revised_labels=revised_labels,
        )
        assert rec["state"] == "revised"
        assert rec["labels"]["pain_point"] == "Manual reconciliation takes 3 days"


def test_illegal_transition_rejection():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_decisions.json"
        store = init_decision_store(store_path)
        cand = create_mock_candidate("REC-marketing-112233445566")
        sid = cand["source_id"]

        # proposed directly to accepted should fail
        try:
            transition_decision_state(store, sid, "accepted", candidate=cand)
            assert False, "Should reject proposed -> accepted"
        except ValueError as e:
            assert "Illegal transition" in str(e) or "rejected" in str(e)


def test_stale_detection_invalidation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_decisions.json"
        store = init_decision_store(store_path)
        cand = create_mock_candidate("REC-marketing-aabbccddeeff")
        sid = cand["source_id"]

        transition_decision_state(store, sid, "needs-review", candidate=cand)
        transition_decision_state(store, sid, "accepted", reviewer="Diwas")

        # Simulate source lead with mutated hash
        mutated_leads = [{
            "source_id": sid,
            "source_hash": "e" * 64,  # Changed hash
        }]

        stale_ids = detect_and_invalidate_stale(store, mutated_leads)
        assert sid in stale_ids
        assert store["decisions"][sid]["state"] == "superseded"


if __name__ == "__main__":
    test_decision_lifecycle()
    test_revised_transition()
    test_illegal_transition_rejection()
    test_stale_detection_invalidation()
    print("ALL DECISION TESTS PASSED")
