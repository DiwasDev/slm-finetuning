"""
Unit tests for idempotency and interruption recovery (TASK-8-RECOVERY).
Verifies FR-9, AC-5, AC-8.
"""

import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision import init_decision_store
from recovery import verify_idempotency, reconcile_interrupted_store
from review_cli import prepare_review_queue, apply_review_decision


def test_idempotency():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "decisions.json"
        export_path = Path(tmpdir) / "slm_train.jsonl"
        store = init_decision_store(store_path)

        pending = prepare_review_queue(store, store_path)
        id1 = pending[0]["lead"]["source_id"]
        apply_review_decision(store, id1, "accept", reviewer="Diwas", store_path=store_path)

        ok, digest = verify_idempotency(store_path, export_path)
        assert ok, "Export must be deterministic and idempotent"
        assert len(digest) == 64


def test_reconciliation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "decisions.json"
        store = init_decision_store(store_path)

        pending = prepare_review_queue(store, store_path)
        id1 = pending[0]["lead"]["source_id"]
        apply_review_decision(store, id1, "accept", reviewer="Diwas", store_path=store_path)

        report = reconcile_interrupted_store(store_path)
        assert report["status"] == "healthy"
        # Dataset expanded to 102 leads
        assert report["total_records"] == 102
        assert report["state_breakdown"].get("accepted") == 1
        assert report["state_breakdown"].get("needs-review") == 101


if __name__ == "__main__":
    test_idempotency()
    test_reconciliation()
    print("ALL RECOVERY TESTS PASSED")

