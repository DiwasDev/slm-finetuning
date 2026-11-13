"""
Schema definitions and validators for ADR data-labeling and decision workflow.
Enforces 4-field taxonomy, provenance attributes, and decision state transitions.
Uses standard library only (Ponytail: stdlib first, zero external dependencies).
"""

import re
import sys
from datetime import datetime
from typing import Any

sys.dont_write_bytecode = True

# Allowed 4-field label taxonomy keys
LABEL_FIELDS = ("pain_point", "personalization_angle", "subject", "body")

# Valid lifecycle states for decisions
VALID_STATES = {
    "proposed",
    "needs-review",
    "accepted",
    "rejected",
    "revised",
    "uncertain",
    "superseded",
}

# Permitted state transitions
LEGAL_TRANSITIONS = {
    "proposed": {"needs-review", "rejected"},
    "needs-review": {"accepted", "rejected", "revised", "uncertain"},
    "accepted": {"accepted", "revised", "superseded", "rejected"},
    "revised": {"revised", "accepted", "superseded", "rejected"},
    "rejected": {"needs-review"},
    "uncertain": {"needs-review", "rejected"},
    "superseded": {"needs-review"},
}

SHA256_REGEX = re.compile(r"^[a-f0-9]{64}$")
RECORD_ID_REGEX = re.compile(r"^REC-[a-zA-Z0-9_-]+-[a-f0-9]{8,64}$")


def validate_label_taxonomy(record: Any) -> tuple[bool, str | None]:
    """Verify that a record strictly contains the 4 non-empty string label fields."""
    if not isinstance(record, dict):
        return False, "Label record must be a JSON object / dictionary"
    
    for field in LABEL_FIELDS:
        if field not in record:
            return False, f"Missing required label field: '{field}'"
        val = record[field]
        if not isinstance(val, str) or not val.strip():
            return False, f"Label field '{field}' must be a non-empty string"
            
    extra_fields = set(record.keys()) - set(LABEL_FIELDS)
    if extra_fields:
        return False, f"Unexpected extra fields in label taxonomy: {sorted(list(extra_fields))}"

    return True, None


def validate_provenance(record: Any) -> tuple[bool, str | None]:
    """Verify that provenance attributes are valid and well-formed."""
    if not isinstance(record, dict):
        return False, "Record must be a dictionary"

    for field in ("source_id", "source_file", "source_hash"):
        if field not in record or not isinstance(record[field], str) or not record[field].strip():
            return False, f"Missing or invalid provenance field: '{field}'"

    if not RECORD_ID_REGEX.match(record["source_id"]):
        return False, f"Invalid source_id format: '{record['source_id']}'"

    if not SHA256_REGEX.match(record["source_hash"]):
        return False, f"Invalid source_hash; must be 64-char hex SHA-256: '{record['source_hash']}'"

    return True, None


def validate_state_transition(from_state: str, to_state: str) -> tuple[bool, str | None]:
    """Verify whether a lifecycle state transition is legal."""
    if from_state not in VALID_STATES:
        return False, f"Unknown origin state: '{from_state}'"
    if to_state not in VALID_STATES:
        return False, f"Unknown destination state: '{to_state}'"

    allowed = LEGAL_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        return False, f"Illegal transition from '{from_state}' to '{to_state}'. Allowed: {sorted(list(allowed))}"

    return True, None


def validate_decision_record(record: Any) -> tuple[bool, str | None]:
    """Verify a complete decision record."""
    if not isinstance(record, dict):
        return False, "Decision record must be a dictionary"

    # 1. Provenance
    prov_ok, prov_err = validate_provenance(record)
    if not prov_ok:
        return False, f"Provenance error: {prov_err}"

    # 2. Decision State
    state = record.get("state")
    if not state or state not in VALID_STATES:
        return False, f"Invalid or missing decision state: '{state}'"

    # 3. Label content (for accepted/revised/proposed states)
    if state in {"proposed", "accepted", "revised"}:
        label_data = record.get("labels")
        if not label_data:
            return False, f"Decision in state '{state}' must include 'labels'"
        lbl_ok, lbl_err = validate_label_taxonomy(label_data)
        if not lbl_ok:
            return False, f"Invalid labels in decision: {lbl_err}"

    # 4. Review metadata if reviewed
    if state in {"accepted", "rejected", "revised", "uncertain"}:
        if not record.get("reviewer"):
            return False, "Reviewed decision must specify 'reviewer'"
        if not record.get("reviewed_at"):
            return False, "Reviewed decision must specify 'reviewed_at' timestamp"
        try:
            datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False, f"Invalid ISO timestamp for reviewed_at: '{record.get('reviewed_at')}'"

    return True, None
