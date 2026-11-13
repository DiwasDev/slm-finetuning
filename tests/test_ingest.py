"""
Unit tests for ADR and raw data ingestion (TASK-2-INGEST).
Verifies FR-1, FR-2, FR-5, NFR-1, AC-1, AC-3.
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ingest import (
    verify_source_immutability,
    parse_adr_metadata,
    ingest_raw_leads,
    ingest_all_raw_data,
    canonical_record_hash,
)


def test_immutability_hashes():
    initial_hashes = verify_source_immutability()
    assert "data/marketing.json" in initial_hashes
    assert "data/accounting.json" in initial_hashes
    assert "ADRs/ADR-001-dataset-strategy-and-evaluation.md" in initial_hashes

    # Run again and ensure hashes match
    second_hashes = verify_source_immutability()
    assert initial_hashes == second_hashes, "Source file hashes changed!"


def test_adr_parsing():
    adr_path = Path(__file__).parent.parent / "ADRs" / "ADR-001-dataset-strategy-and-evaluation.md"
    meta = parse_adr_metadata(adr_path)
    assert meta["status"] == "Active"
    assert "Diwas" in meta["author"]
    assert "EmailSLM" in meta["scope"]
    assert len(meta["hash"]) == 64
    assert len(meta["assumptions"]) >= 8
    assert meta["assumptions"][0]["id"] == "A1"


def test_marketing_ingestion():
    leads = ingest_raw_leads("marketing")
    # Dataset expanded to 88 marketing leads (34 original + 54 synthetic)
    assert len(leads) == 88, f"Expected 88 marketing leads, got {len(leads)}"

    first = leads[0]
    assert first["source_id"].startswith("REC-marketing-")
    assert first["source_file"] == "data/marketing.json"
    assert len(first["source_hash"]) == 64
    assert "subject" in first["raw_output_email"]


def test_accounting_ingestion():
    leads = ingest_raw_leads("accounting")
    assert len(leads) == 14, f"Expected 14 accounting leads, got {len(leads)}"

    first = leads[0]
    assert first["source_id"].startswith("REC-accounting-")
    assert first["source_file"] == "data/accounting.json"
    assert len(first["source_hash"]) == 64
    assert "subject" in first["raw_output_email"]


def test_ingest_all_integrity():
    data = ingest_all_raw_data()
    # Dataset expanded: 88 marketing + 14 accounting = 102 total
    assert data["lead_counts"]["total"] == 102
    assert data["lead_counts"]["marketing"] == 88
    assert data["lead_counts"]["accounting"] == 14
    assert len(data["records"]) == 102

    # All record IDs must be unique
    ids = [r["source_id"] for r in data["records"]]
    assert len(ids) == len(set(ids)), "Found duplicate source IDs"


def test_canonical_record_hash_deterministic():
    r1 = {"b": 2, "a": 1, "nested": {"y": "yes", "x": "no"}}
    r2 = {"a": 1, "b": 2, "nested": {"x": "no", "y": "yes"}}
    h1 = canonical_record_hash(r1)
    h2 = canonical_record_hash(r2)
    assert h1 == h2, "Canonical hash should be deterministic regardless of key order"


if __name__ == "__main__":
    test_immutability_hashes()
    test_adr_parsing()
    test_marketing_ingestion()
    test_accounting_ingestion()
    test_ingest_all_integrity()
    test_canonical_record_hash_deterministic()
    print("ALL INGESTION TESTS PASSED")

