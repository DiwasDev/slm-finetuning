"""
Unit tests for dataset integrity and leakage audit (TASK-7-INTEGRITY).
Verifies FR-12, AC-5, AC-9.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit import audit_exported_dataset
from decision import init_decision_store
from export import export_slm_dataset
from review_cli import prepare_review_queue, apply_review_decision


def test_audit_valid_dataset():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "decisions.json"
        export_path = Path(tmpdir) / "slm_train.jsonl"
        store = init_decision_store(store_path)

        pending = prepare_review_queue(store, store_path)
        id1 = pending[0]["lead"]["source_id"]
        id2 = pending[1]["lead"]["source_id"]

        apply_review_decision(store, id1, "accept", reviewer="Diwas", store_path=store_path)
        apply_review_decision(
            store,
            id2,
            "revise",
            reviewer="Diwas",
            revised_labels={
                "pain_point": "Manual reconciliation",
                "personalization_angle": "Angle",
                "subject": "Subject",
                "body": "Body",
            },
            store_path=store_path,
        )

        export_slm_dataset(store_path=store_path, output_path=export_path)

        receipt = audit_exported_dataset(jsonl_path=export_path, store_path=store_path)
        assert receipt["verified"] is True
        assert receipt["total_records_checked"] == 2
        assert receipt["zero_leakage_passed"] is True
        assert receipt["deduplication_passed"] is True
        assert len(receipt["errors"]) == 0


def test_audit_detects_leakage():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "decisions.json"
        export_path = Path(tmpdir) / "slm_train.jsonl"
        store = init_decision_store(store_path)

        pending = prepare_review_queue(store, store_path)
        id1 = pending[0]["lead"]["source_id"]
        id_rejected = pending[1]["lead"]["source_id"]

        apply_review_decision(store, id1, "accept", reviewer="Diwas", store_path=store_path)
        apply_review_decision(store, id_rejected, "reject", reviewer="Diwas", store_path=store_path)

        # Deliberately inject a leaked rejected record into the export
        leaked_record = {
            "id": id_rejected,
            "partition": "train",
            "instruction": "Test",
            "input": "Context",
            "output": "Output",
            "labels": {"pain_point": "P", "personalization_angle": "A", "subject": "S", "body": "B"},
            "provenance": {
                "source_id": id_rejected,
                "source_file": "data/marketing.json",
                "source_hash": "f" * 64,
                "decision_state": "rejected",
            },
        }

        with open(export_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(leaked_record) + "\n")

        receipt = audit_exported_dataset(jsonl_path=export_path, store_path=store_path)
        assert receipt["verified"] is False
        assert any("Leakage" in err for err in receipt["errors"]), "Audit failed to catch leaked rejected record!"


if __name__ == "__main__":
    test_audit_valid_dataset()
    test_audit_detects_leakage()
    print("ALL AUDIT TESTS PASSED")

