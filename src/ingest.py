"""
ADR and raw source data ingestion with deterministic SHA-256 provenance hashing.
Preserves immutability of data/ and ADRs/ directories.
Uses standard library only (Ponytail: stdlib first).
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).parent.parent
ADR_DIR = REPO_ROOT / "ADRs"
DATA_DIR = REPO_ROOT / "data"

DATA_SOURCES = {
    "marketing": DATA_DIR / "marketing.json",
    "accounting": DATA_DIR / "accounting.json",
}

ADR_SOURCES = [
    ADR_DIR / "ADR-001-dataset-strategy-and-evaluation.md",
]


def compute_sha256_bytes(data: bytes) -> str:
    """Compute hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    with open(path, "rb") as f:
        return compute_sha256_bytes(f.read())


def canonical_record_hash(record: dict) -> str:
    """Compute deterministic SHA-256 hash of a JSON-serializable record."""
    canonical_json = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return compute_sha256_bytes(canonical_json.encode("utf-8"))


def verify_source_immutability() -> dict[str, str]:
    """Verify that all raw source files exist and return their SHA-256 hashes."""
    hashes = {}
    for sector, path in DATA_SOURCES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required raw data source missing: {path}")
        hashes[f"data/{path.name}"] = compute_file_sha256(path)

    for adr_path in ADR_SOURCES:
        if not adr_path.is_file():
            raise FileNotFoundError(f"Required ADR missing: {adr_path}")
        hashes[f"ADRs/{adr_path.name}"] = compute_file_sha256(adr_path)

    return hashes


def parse_adr_metadata(path: Path) -> dict[str, Any]:
    """Parse structured metadata and sections from an ADR Markdown file."""
    if not path.is_file():
        raise FileNotFoundError(f"ADR not found: {path}")

    text = path.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {
        "file": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "hash": compute_sha256_bytes(text.encode("utf-8")),
    }

    # Extract header fields
    for field in ("Status", "Date", "Author", "Scope", "Decision"):
        match = re.search(rf"\*\*{field}:\*\*\s*(.+)", text)
        if match:
            metadata[field.lower()] = match.group(1).strip()

    # Extract informal assumption IDs (e.g. A1, A2...)
    assumptions = re.findall(r"\|\s*(A\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", text)
    if assumptions:
        metadata["assumptions"] = [
            {"id": a[0].strip(), "text": a[1].strip(), "consequence": a[2].strip()}
            for a in assumptions
        ]

    return metadata


def ingest_raw_leads(sector: str) -> list[dict[str, Any]]:
    """
    Ingest raw leads from a sector file without modifying it.
    Assigns deterministic record IDs and provenance hashes.
    """
    if sector not in DATA_SOURCES:
        raise ValueError(f"Unknown sector: '{sector}'. Allowed: {list(DATA_SOURCES.keys())}")

    path = DATA_SOURCES[sector]
    with open(path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    if not isinstance(raw_items, list):
        raise ValueError(f"Expected array of records in {path}, got {type(raw_items).__name__}")

    relative_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    normalized = []

    for idx, item in enumerate(raw_items):
        item_hash = canonical_record_hash(item)
        record_id = f"REC-{sector}-{item_hash[:12]}"

        normalized.append({
            "source_id": record_id,
            "sector": sector,
            "source_file": relative_path,
            "source_index": idx,
            "source_hash": item_hash,
            "name": item.get("name"),
            "email": item.get("email"),
            "company": item.get("company"),
            "website": item.get("website"),
            "linkedin": item.get("linkedin"),
            "lead_context": item.get("lead_context", {}),
            "raw_output_email": item.get("output_email", {}),
        })

    return normalized


def ingest_all_raw_data() -> dict[str, Any]:
    """Ingest both marketing and accounting leads along with ADR metadata."""
    adr_info = parse_adr_metadata(ADR_SOURCES[0])
    marketing_leads = ingest_raw_leads("marketing")
    accounting_leads = ingest_raw_leads("accounting")

    all_leads = marketing_leads + accounting_leads

    # Verify ID uniqueness
    all_ids = [l["source_id"] for l in all_leads]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate record ID generated during ingestion")

    return {
        "adr": adr_info,
        "lead_counts": {
            "marketing": len(marketing_leads),
            "accounting": len(accounting_leads),
            "total": len(all_leads),
        },
        "records": all_leads,
    }

