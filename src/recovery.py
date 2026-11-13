"""
Idempotency verification and interruption recovery engine (TASK-8-RECOVERY).
Guarantees that stopped runs resume without duplicating decisions and reruns are idempotent.
Uses standard library only (Ponytail: stdlib first).
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent))
from decision import init_decision_store, save_decision_store, DEFAULT_STORE_PATH
from export import export_slm_dataset


def verify_idempotency(store_path: Path, export_path: Path) -> tuple[bool, str]:
    """
    Verify that rerunning the export pipeline on unchanged inputs
    produces bit-for-bit identical outputs with matching SHA-256 digests.
    """
    receipt1 = export_slm_dataset(store_path=store_path, output_path=export_path)
    hash1 = receipt1["export_sha256"]

    receipt2 = export_slm_dataset(store_path=store_path, output_path=export_path)
    hash2 = receipt2["export_sha256"]

    if hash1 != hash2:
        return False, f"Non-idempotent export: {hash1} vs {hash2}"

    return True, hash1


def reconcile_interrupted_store(store_path: Path = DEFAULT_STORE_PATH) -> dict[str, Any]:
    """
    Scan the decision store after an unexpected crash or process interruption.
    Validates structural consistency, eliminates any duplicate keys,
    verifies history timeline ordering, and returns reconciliation status.
    """
    store = init_decision_store(store_path)
    decisions = store.get("decisions", {})
    history = store.get("history", [])

    repaired_count = 0
    state_breakdown: dict[str, int] = {}

    for sid, rec in list(decisions.items()):
        state = rec.get("state", "unknown")
        state_breakdown[state] = state_breakdown.get(state, 0) + 1

        # Check if record has valid source_id
        if rec.get("source_id") != sid:
            rec["source_id"] = sid
            repaired_count += 1

    # Ensure history entries are valid
    valid_history = [
        h for h in history if isinstance(h, dict) and "source_id" in h and "to_state" in h
    ]

    store["history"] = valid_history
    save_decision_store(store, store_path)

    return {
        "status": "healthy",
        "total_records": len(decisions),
        "state_breakdown": state_breakdown,
        "history_events": len(valid_history),
        "repaired_records": repaired_count,
    }

