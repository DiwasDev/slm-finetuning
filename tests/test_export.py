"""
Unit tests for downstream SLM dataset export (TASK-6-EXPORT).
Verifies FR-11, NFR-4, AC-7.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision import init_decision_store
from export import export_slm_dataset, format_instruction_input
from review_cli import prepare_review_queue, apply_review_decision


def test_format_instruction_input():
    sample_lead = {
        "name": "Warren Ellis",
        "company": "Wizard Growth Partners",
        "sector": "marketing",
        "website": "https://wizard-growth.example",
        "linkedin": "https://www.linkedin.com/in/warren-ellis-growth",
        "lead_context": {
            "linkedin_headline": "Co-Founder at Wizard Growth Partners",
            "website_copy": "Get More Leads with Expert Digital Marketing",
        },
    }
    input_text = format_instruction_input(sample_lead)
    assert "Warren Ellis" in input_text
    assert "Wizard Growth Partners" in input_text
    assert "wizard-growth.example" in input_text


def test_export_slm_dataset_integrity():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "decisions.json"
        export_path = Path(tmpdir) / "slm_train.jsonl"
        store = init_decision_store(store_path)

        pending = prepare_review_queue(store, store_path)
        # Dataset has 102 leads (88 marketing + 14 accounting)
        assert len(pending) == 102, f"Expected 102 pending, got {len(pending)}"

        # Accept 2 records, revise 1, reject 1
        id1 = pending[0]["lead"]["source_id"]
        id2 = pending[1]["lead"]["source_id"]
        id3 = pending[2]["lead"]["source_id"]
        id4 = pending[3]["lead"]["source_id"]

        apply_review_decision(store, id1, "accept", reviewer="Diwas", store_path=store_path)
        apply_review_decision(store, id2, "accept", reviewer="Diwas", store_path=store_path)
        apply_review_decision(
            store,
            id3,
            "revise",
            reviewer="Diwas",
            revised_labels={
                "pain_point": "Manual reporting leak",
                "personalization_angle": "Post on reporting",
                "subject": "Question on reporting",
                "body": "Hi there...",
            },
            store_path=store_path,
        )
        apply_review_decision(store, id4, "reject", reviewer="Diwas", notes="Bad lead", store_path=store_path)

        # Export dataset
        summary = export_slm_dataset(store_path=store_path, output_path=export_path)
        assert summary["total_exported"] == 3
        assert summary["accepted_count"] == 2
        assert summary["revised_count"] == 1
        assert len(summary["export_sha256"]) == 64

        # Verify exported JSONL lines
        with open(export_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 3

        for line in lines:
            record = json.loads(line)
            assert "instruction" in record
            assert "input" in record
            assert "output" in record
            assert "provenance" in record
            assert record["provenance"]["decision_state"] in {"accepted", "revised"}
            assert record["id"] != id4, "Rejected lead must not leak into export"


if __name__ == "__main__":
    test_format_instruction_input()
    test_export_slm_dataset_integrity()
    print("ALL EXPORT TESTS PASSED")

