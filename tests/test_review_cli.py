"""
Unit tests for Diwas human review CLI and decision processing (TASK-5-REVIEW-CLI).
Verifies FR-7, NFR-5, AC-3, AC-8.
"""

import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision import init_decision_store
from review_cli import (
    load_contact_directory,
    load_external_claude_candidates,
    prepare_review_queue,
    render_review_card,
    apply_review_decision,
    run_batch_review,
)


def test_load_contact_directory():
    contacts = load_contact_directory()
    assert len(contacts) > 0, "Expected contacts loaded from data/contact/contact.json"
    sample = next(iter(contacts.values()))
    assert "website" in sample
    assert "linkedin" in sample


def test_load_external_claude_candidates():
    candidates = load_external_claude_candidates()
    # Dataset expanded: 14 accounting + 88 marketing = 102 total
    assert len(candidates) == 102, f"Expected 102 candidate outputs, got {len(candidates)}"
    sample = next(iter(candidates.values()))
    for key in ("pain_point", "personalization_angle", "subject", "body"):
        assert key in sample, f"Missing {key} in sample candidate"


def test_prepare_review_queue_and_resume():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_decisions.json"
        store = init_decision_store(store_path)

        # 1. First run: enqueues all 102 leads
        pending = prepare_review_queue(store, store_path)
        assert len(pending) == 102, f"Expected 102 pending items, got {len(pending)}"
        assert len(store["decisions"]) == 102

        first_item = pending[0]
        first_id = first_item["lead"]["source_id"]

        # 2. Review and accept first lead: verify LinkedIn and Website rendered
        card_text = render_review_card(first_item)
        assert first_id in card_text
        assert "PAIN POINT" in card_text
        assert "Website:" in card_text
        assert "LinkedIn:" in card_text

        rec = apply_review_decision(
            store,
            first_id,
            "accept",
            reviewer="Diwas",
            notes="Strong pain hook",
            store_path=store_path,
        )
        assert rec["state"] == "accepted"
        assert rec["reviewer"] == "Diwas"

        # 3. Simulate process restart / resume: second run should only have 101 pending
        store_resumed = init_decision_store(store_path)
        pending_after_restart = prepare_review_queue(store_resumed, store_path)
        assert len(pending_after_restart) == 101, f"Expected 101 pending after resume, got {len(pending_after_restart)}"
        assert first_id not in [p["lead"]["source_id"] for p in pending_after_restart]


def test_batch_review_actions():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "batch_decisions.json"
        store = init_decision_store(store_path)
        pending = prepare_review_queue(store, store_path)

        batch_actions = [
            {"source_id": pending[0]["lead"]["source_id"], "action": "accept", "notes": "Looks great"},
            {
                "source_id": pending[1]["lead"]["source_id"],
                "action": "revise",
                "notes": "Edited hook",
                "revised_labels": {
                    "pain_point": "Manual reconciliation leak",
                    "personalization_angle": "Article on CPA workloads",
                    "subject": "Custom subject line",
                    "body": "Hi there, Diwas here...",
                },
            },
            {"source_id": pending[2]["lead"]["source_id"], "action": "reject", "notes": "Irrelevant angle"},
            {"source_id": pending[3]["lead"]["source_id"], "action": "uncertain", "notes": "Need to check firm site"},
        ]

        counts = run_batch_review(store, batch_actions, reviewer="Diwas", store_path=store_path)
        assert counts["accepted"] == 1
        assert counts["revised"] == 1
        assert counts["rejected"] == 1
        assert counts["uncertain"] == 1


if __name__ == "__main__":
    test_load_contact_directory()
    test_load_external_claude_candidates()
    test_prepare_review_queue_and_resume()
    test_batch_review_actions()
    print("ALL REVIEW CLI TESTS PASSED")
