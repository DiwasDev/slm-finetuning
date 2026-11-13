"""
Decision state machine engine, state transition enforcement, and stale detection.
Separates derived decisions from raw data and guarantees immutable provenance.
Uses standard library only (Ponytail: stdlib first).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent))
from schema import (
    validate_state_transition,
    validate_decision_record,
    validate_label_taxonomy,
    VALID_STATES,
)

DEFAULT_STORE_DIR = Path(__file__).parent.parent / "artifacts"
DEFAULT_STORE_PATH = DEFAULT_STORE_DIR / "decisions.json"


def init_decision_store(store_path: Path = DEFAULT_STORE_PATH) -> dict[str, Any]:
    """Initialize or load the derived decision store from disk."""
    if store_path.is_file():
        with open(store_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "description": "Derived ADR decision store for EmailSLM",
        "decisions": {},
        "history": [],
    }


def save_decision_store(store: dict[str, Any], store_path: Path = DEFAULT_STORE_PATH) -> None:
    """Safely persist the decision store to disk."""
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, sort_keys=True)


def transition_decision_state(
    store: dict[str, Any],
    source_id: str,
    target_state: str,
    reviewer: str = "Diwas",
    notes: str = "",
    revised_labels: dict[str, str] | None = None,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Transition a decision record to a new state with strict validation.
    If no prior record exists, creates one from the provided candidate in 'proposed' state.
    """
    existing = store["decisions"].get(source_id)

    if existing is None:
        if candidate is None:
            raise ValueError(f"No existing decision for '{source_id}' and no candidate provided")
        current_state = candidate.get("state", "proposed")
        labels = candidate.get("labels")
        source_file = candidate.get("source_file")
        source_hash = candidate.get("source_hash")
    else:
        current_state = existing["state"]
        labels = existing.get("labels")
        source_file = existing.get("source_file")
        source_hash = existing.get("source_hash")

    # Validate transition
    ok, err = validate_state_transition(current_state, target_state)
    if not ok:
        raise ValueError(f"State transition rejected: {err}")

    # Use revised labels if provided
    final_labels = labels
    if target_state == "revised":
        if not revised_labels:
            raise ValueError("State 'revised' requires revised_labels")
        lbl_ok, lbl_err = validate_label_taxonomy(revised_labels)
        if not lbl_ok:
            raise ValueError(f"Invalid revised labels: {lbl_err}")
        final_labels = revised_labels

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "source_id": source_id,
        "source_file": source_file,
        "source_hash": source_hash,
        "state": target_state,
        "labels": final_labels,
        "reviewer": reviewer,
        "reviewed_at": now_iso,
        "notes": notes,
    }

    # Validate complete record
    rec_ok, rec_err = validate_decision_record(record)
    if not rec_ok:
        raise ValueError(f"Decision record failed schema: {rec_err}")

    # Save to store and append audit history
    store["decisions"][source_id] = record
    store["history"].append({
        "source_id": source_id,
        "from_state": current_state,
        "to_state": target_state,
        "reviewer": reviewer,
        "timestamp": now_iso,
        "notes": notes,
    })

    return record


def detect_and_invalidate_stale(
    store: dict[str, Any],
    current_leads: list[dict[str, Any]],
) -> list[str]:
    """
    Check if raw source hash differs from stored decision hash.
    Marks stale decisions as 'superseded' and records audit event.
    """
    lead_hash_map = {l["source_id"]: l["source_hash"] for l in current_leads}
    stale_ids = []

    for source_id, decision in store["decisions"].items():
        current_hash = lead_hash_map.get(source_id)
        if current_hash is None or current_hash != decision["source_hash"]:
            if decision["state"] in {"accepted", "revised", "needs-review"}:
                old_state = decision["state"]
                decision["state"] = "superseded"
                decision["stale_reason"] = "Source record hash mutated or record deleted"
                store["history"].append({
                    "source_id": source_id,
                    "from_state": old_state,
                    "to_state": "superseded",
                    "reviewer": "system",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": "Invalidated due to source content mutation",
                })
                stale_ids.append(source_id)

    return stale_ids

