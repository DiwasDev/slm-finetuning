"""
Unit tests for Claude teacher candidate generation interface (TASK-3-TEACHER).
Verifies FR-4, NFR-4, AC-2.
"""

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ingest import ingest_raw_leads
from schema import validate_label_taxonomy
from teacher import (
    build_teacher_prompt,
    extract_candidate_from_teacher_output,
    generate_candidate_record,
)


def test_build_teacher_prompt():
    sample_lead = {
        "name": "Jane Doe",
        "company": "Apex Growth",
        "sector": "marketing",
        "source_id": "REC-marketing-abcdef123456",
        "source_file": "data/marketing.json",
        "source_hash": "c" * 64,
        "lead_context": {
            "website_copy": "We help B2B SaaS scale through paid acquisition.",
            "linkedin_headline": "Founder at Apex Growth",
        },
    }
    prompt = build_teacher_prompt(sample_lead)
    assert "Apex Growth" in prompt
    assert "Noman" in prompt
    assert "GTM AI Engineer" in prompt


def test_extract_valid_teacher_output():
    raw_response = """
    Here is the structured decomposition:
    {
      "pain_point": "Manual ad reporting wastes 15 hours weekly",
      "personalization_angle": "Recent post highlighting Q4 client reporting crunches",
      "subject": "Quick question on Apex reporting workflows",
      "body": "Hey Jane,\\n\\nNoticed your team runs multi-channel campaigns for SaaS..."
    }
    Hope this helps!
    """
    labels = extract_candidate_from_teacher_output(raw_response)
    ok, err = validate_label_taxonomy(labels)
    assert ok, f"Extracted labels failed taxonomy: {err}"
    assert labels["pain_point"] == "Manual ad reporting wastes 15 hours weekly"


def test_extract_invalid_teacher_output_fails():
    bad_response = """
    {
      "pain_point": "Some pain",
      "subject": "No angle and no body"
    }
    """
    try:
        extract_candidate_from_teacher_output(bad_response)
        assert False, "Should have raised ValueError on missing fields"
    except ValueError as e:
        assert "personalization_angle" in str(e) or "failed taxonomy" in str(e)


def test_generate_candidate_from_real_lead():
    marketing_leads = ingest_raw_leads("marketing")
    first_lead = marketing_leads[0]

    cand = generate_candidate_record(first_lead)
    assert cand["candidate_id"].startswith("CAND-marketing-")
    assert cand["state"] == "proposed"
    assert cand["source_id"] == first_lead["source_id"]
    assert cand["source_hash"] == first_lead["source_hash"]
    assert "prompt_hash" in cand["teacher_trace"]
    assert len(cand["teacher_trace"]["prompt_hash"]) == 64

    ok, err = validate_label_taxonomy(cand["labels"])
    assert ok, f"Candidate labels failed taxonomy: {err}"


if __name__ == "__main__":
    test_build_teacher_prompt()
    test_extract_valid_teacher_output()
    test_extract_invalid_teacher_output_fails()
    test_generate_candidate_from_real_lead()
    print("ALL TEACHER TESTS PASSED")

