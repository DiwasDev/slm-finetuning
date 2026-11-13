"""
Single-reviewer interactive and programmatic review CLI for Diwas (TASK-5-REVIEW-CLI).
Loads Claude teacher candidates and contact info (LinkedIn, website),
presents lead context and decomposed labels, records editorial decisions,
and updates the decision store.
Uses standard library only (Ponytail: stdlib first).
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent))
from ingest import ingest_all_raw_data
from decision import (
    init_decision_store,
    save_decision_store,
    transition_decision_state,
    DEFAULT_STORE_PATH,
)
from schema import validate_label_taxonomy

DATA_DIR = Path(__file__).parent.parent / "data"
UPDATED_DIR = DATA_DIR / "updated"
CONTACT_PATH = DATA_DIR / "contact" / "contact.json"

UPDATED_SOURCES = {
    "marketing": UPDATED_DIR / "marketing_update.json",
    "accounting": UPDATED_DIR / "accounting_update.json",
}


def load_contact_directory() -> dict[str, dict[str, Any]]:
    """Load contact directory (LinkedIn, website, name, company) keyed by email."""
    if not CONTACT_PATH.is_file():
        return {}
    try:
        with open(CONTACT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {
                item["email"]: item
                for item in data
                if isinstance(item, dict) and "email" in item
            }
    except Exception:
        pass
    return {}


def load_external_claude_candidates() -> dict[str, dict[str, str]]:
    """Load Claude-generated 4-field decompositions keyed by prospect email."""
    candidates_by_email = {}
    for sector, path in UPDATED_SOURCES.items():
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    candidates_by_email.update(data)
    return candidates_by_email


def get_all_review_items(
    store: dict[str, Any],
    store_path: Path = DEFAULT_STORE_PATH,
) -> list[dict[str, Any]]:
    """
    Ingest all raw leads, bind contact details and Claude teacher outputs.
    Returns all 48 leads with active decision states (for dashboard views).
    """
    raw_data = ingest_all_raw_data()
    external_candidates = load_external_claude_candidates()
    contact_dir = load_contact_directory()
    items = []

    for lead in raw_data["records"]:
        source_id = lead["source_id"]
        existing = store["decisions"].get(source_id)
        email = lead.get("email")
        claude_labels = external_candidates.get(email)

        if not claude_labels:
            raw_email = lead.get("raw_output_email", {})
            claude_labels = {
                "pain_point": f"Operational manual bottlenecks at {lead.get('company', 'firm')}",
                "personalization_angle": lead.get("lead_context", {}).get("linkedin_headline", "Leadership"),
                "subject": raw_email.get("subject", "Quick question"),
                "body": raw_email.get("body", ""),
            }

        contact_entry = contact_dir.get(email, {})
        linkedin_url = (
            contact_entry.get("linkedin")
            or lead.get("linkedin")
            or lead.get("lead_context", {}).get("linkedin")
            or "N/A"
        )
        website_url = (
            contact_entry.get("website")
            or lead.get("website")
            or lead.get("lead_context", {}).get("website")
            or "N/A"
        )

        active_labels = existing.get("labels", claude_labels) if existing else claude_labels
        state = existing.get("state", "needs-review") if existing else "needs-review"
        notes = existing.get("notes", "") if existing else ""

        items.append({
            "source_id": source_id,
            "sector": lead.get("sector"),
            "name": lead.get("name"),
            "company": lead.get("company"),
            "email": email,
            "website": website_url,
            "linkedin": linkedin_url,
            "state": state,
            "notes": notes,
            "labels": active_labels,
            "candidate_labels": claude_labels,
        })

    return items


def prepare_review_queue(
    store: dict[str, Any],
    store_path: Path = DEFAULT_STORE_PATH,
) -> list[dict[str, Any]]:
    """
    Ingest all raw leads, bind contact details and Claude teacher outputs.
    Enqueues any unreviewed leads into the decision store as 'needs-review'.
    Returns the list of pending records requiring review.
    """
    raw_data = ingest_all_raw_data()
    external_candidates = load_external_claude_candidates()
    contact_dir = load_contact_directory()
    pending = []

    for lead in raw_data["records"]:
        source_id = lead["source_id"]
        existing = store["decisions"].get(source_id)

        # Skip already completed reviews
        if existing and existing["state"] in {"accepted", "revised", "rejected"}:
            continue

        email = lead.get("email")
        claude_labels = external_candidates.get(email)

        if not claude_labels:
            # Fallback to raw output email if present
            raw_email = lead.get("raw_output_email", {})
            claude_labels = {
                "pain_point": f"Operational manual bottlenecks at {lead.get('company', 'firm')}",
                "personalization_angle": lead.get("lead_context", {}).get("linkedin_headline", "Leadership"),
                "subject": raw_email.get("subject", "Quick question"),
                "body": raw_email.get("body", ""),
            }

        # Merge contact links from contact.json and lead record
        contact_entry = contact_dir.get(email, {})
        linkedin_url = (
            contact_entry.get("linkedin")
            or lead.get("linkedin")
            or lead.get("lead_context", {}).get("linkedin")
            or "N/A"
        )
        website_url = (
            contact_entry.get("website")
            or lead.get("website")
            or lead.get("lead_context", {}).get("website")
            or "N/A"
        )

        candidate_record = {
            "candidate_id": f"CAND-{source_id.replace('REC-', '')}",
            "source_id": source_id,
            "source_file": lead["source_file"],
            "source_hash": lead["source_hash"],
            "state": "proposed",
            "labels": claude_labels,
            "lead_summary": {
                "name": lead.get("name"),
                "company": lead.get("company"),
                "sector": lead.get("sector"),
                "email": email,
                "website": website_url,
                "linkedin": linkedin_url,
                "headline": lead.get("lead_context", {}).get("linkedin_headline"),
                "website_snippet": str(lead.get("lead_context", {}).get("website_copy", ""))[:300],
            },
        }

        # Transition proposed -> needs-review in the store
        if not existing or existing["state"] == "proposed":
            rec = transition_decision_state(
                store,
                source_id,
                "needs-review",
                candidate=candidate_record,
                reviewer="system",
                notes="Enqueued for Diwas review",
            )
            existing = rec

        pending.append({
            "lead": lead,
            "contact": {
                "website": website_url,
                "linkedin": linkedin_url,
            },
            "decision": existing,
            "labels": claude_labels,
        })

    save_decision_store(store, store_path)
    return pending


def render_review_card(item: dict[str, Any]) -> str:
    """
    Format prospect lead, contact links (LinkedIn, website),
    and Claude candidate draft for clear terminal display.
    """
    lead = item.get("lead", {})
    labels = item.get("labels", {})
    contact = item.get("contact", {})
    
    company = lead.get("company", "N/A")
    name = lead.get("name", "N/A")
    sector = lead.get("sector", "N/A")
    website = contact.get("website") or lead.get("website", "N/A")
    linkedin = contact.get("linkedin") or lead.get("linkedin", "N/A")

    card = f"""
================================================================================
REVIEW RECORD: {lead.get('source_id')} [{sector.upper()}]
Prospect: {name} | Company: {company}
Website:  {website}
LinkedIn: {linkedin}
--------------------------------------------------------------------------------
1. PAIN POINT (Diagnostic):
   {labels.get('pain_point')}

2. PERSONALIZATION ANGLE (Evidence Hook):
   {labels.get('personalization_angle')}

3. SUBJECT (Hook):
   {labels.get('subject')}

4. BODY (Message):
{labels.get('body')}
================================================================================
"""
    return card.strip()


def apply_review_decision(
    store: dict[str, Any],
    source_id: str,
    action: str,
    reviewer: str = "Diwas",
    notes: str = "",
    revised_labels: dict[str, str] | None = None,
    store_path: Path = DEFAULT_STORE_PATH,
) -> dict[str, Any]:
    """Apply an editorial review decision to a record in the store."""
    action = action.lower().strip()
    target_state_map = {
        "accept": "accepted",
        "revise": "revised",
        "reject": "rejected",
        "uncertain": "uncertain",
    }
    if action not in target_state_map:
        raise ValueError(f"Invalid review action: '{action}'. Allowed: {list(target_state_map.keys())}")

    target_state = target_state_map[action]
    record = transition_decision_state(
        store,
        source_id,
        target_state,
        reviewer=reviewer,
        notes=notes,
        revised_labels=revised_labels,
    )
    save_decision_store(store, store_path)
    return record


def run_batch_review(
    store: dict[str, Any],
    decisions_list: list[dict[str, Any]],
    reviewer: str = "Diwas",
    store_path: Path = DEFAULT_STORE_PATH,
) -> dict[str, int]:
    """Execute a batch of review decisions programmatically."""
    counts = {"accepted": 0, "revised": 0, "rejected": 0, "uncertain": 0}
    for item in decisions_list:
        sid = item["source_id"]
        action = item["action"]
        notes = item.get("notes", "")
        revised = item.get("revised_labels")
        rec = apply_review_decision(
            store,
            sid,
            action,
            reviewer=reviewer,
            notes=notes,
            revised_labels=revised,
            store_path=store_path,
        )
        state = rec["state"]
        if state in counts:
            counts[state] += 1
    return counts
