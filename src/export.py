"""
Downstream SLM dataset export generator (TASK-6-EXPORT).
Exports accepted and revised records into verified JSONL format for fine-tuning.
Partitions: train / validation / test (80 / 10 / 10).
Preserves complete cryptographic provenance on every line.
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
from ingest import ingest_all_raw_data
from decision import init_decision_store, DEFAULT_STORE_PATH

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
DEFAULT_EXPORT_PATH = ARTIFACTS_DIR / "slm_train.jsonl"

INSTRUCTION = (
    "Analyze the prospect context according to Noman's 22-rule cold email framework. "
    "Extract the single diagnostic operational pain point, find the evidence-backed "
    "personalization angle, create a low-friction hook subject, and draft a high-reply cold email."
)


def format_instruction_input(lead: dict[str, Any]) -> str:
    """Format raw lead context into a clean instruction input block."""
    context = lead.get("lead_context", {})
    headline = context.get("linkedin_headline", "")
    about = context.get("linkedin_about", "")
    website = context.get("website_copy", "")
    posts = context.get("linkedin_posts", {})
    posts_snippet = " ".join(
        p.get("text", "") for p in posts.values() if isinstance(p, dict)
    )[:600]

    return f"""PROSPECT PROFILE:
- Name: {lead.get('name', '')}
- Company: {lead.get('company', '')}
- Sector: {lead.get('sector', '')}
- Website: {lead.get('website', '')}
- LinkedIn: {lead.get('linkedin', '')}
- Headline: {headline}
- About: {str(about)[:400]}
- Recent Activity: {posts_snippet}
- Website Summary: {str(website)[:600]}""".strip()


def _build_training_example(dec: dict, lead: dict, partition: str) -> dict:
    """Build a single fine-tuning training record."""
    labels = dec["labels"]
    return {
        "id": dec["source_id"],
        "partition": partition,
        "instruction": INSTRUCTION,
        "input": format_instruction_input(lead),
        "output": (
            f"1. PAIN POINT:\n{labels['pain_point']}\n\n"
            f"2. PERSONALIZATION ANGLE:\n{labels['personalization_angle']}\n\n"
            f"3. SUBJECT:\n{labels['subject']}\n\n"
            f"4. BODY:\n{labels['body']}"
        ),
        "labels": labels,
        "provenance": {
            "source_id": dec["source_id"],
            "source_file": dec["source_file"],
            "source_hash": dec["source_hash"],
            "decision_state": dec["state"],
            "reviewer": dec.get("reviewer", "Diwas"),
            "reviewed_at": dec.get("reviewed_at"),
        },
    }


def _write_jsonl(records: list[dict], path: Path) -> str:
    """Write records to JSONL and return SHA-256 of the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def export_slm_dataset(
    store_path: Path = DEFAULT_STORE_PATH,
    output_path: Path = DEFAULT_EXPORT_PATH,
) -> dict[str, Any]:
    """
    Export all reviewed (accepted + revised) decisions into partitioned JSONL datasets.

    When output_path is set, all four split files are written to output_path.parent:
      <dir>/slm_train.jsonl
      <dir>/slm_val.jsonl
      <dir>/slm_test.jsonl
      <dir>/slm_all_partitioned.jsonl

    Returns export receipt with record counts, partition verification, and SHA-256
    hashes for each file.
    """
    store = init_decision_store(store_path)
    decisions = store.get("decisions", {})

    # Ingest raw leads for input context
    raw_data = ingest_all_raw_data()
    leads_by_id = {lead["source_id"]: lead for lead in raw_data["records"]}

    train_recs: list[dict] = []
    val_recs: list[dict] = []
    test_recs: list[dict] = []

    for sid, dec in decisions.items():
        if dec.get("state") not in {"accepted", "revised"}:
            continue
        lead = leads_by_id.get(sid)
        if not lead:
            raise ValueError(f"Decision references unknown source ID: '{sid}'")
        partition = dec.get("partition", "train")
        example = _build_training_example(dec, lead, partition)
        if partition == "train":
            train_recs.append(example)
        elif partition == "validation":
            val_recs.append(example)
        elif partition == "test":
            test_recs.append(example)
        else:
            raise ValueError(f"Unknown partition '{partition}' for record '{sid}'")

    # Determine output directory from output_path
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "slm_train.jsonl"
    val_path   = out_dir / "slm_val.jsonl"
    test_path  = out_dir / "slm_test.jsonl"
    all_path   = out_dir / "slm_all_partitioned.jsonl"

    h_train = _write_jsonl(train_recs, train_path)
    h_val   = _write_jsonl(val_recs, val_path)
    h_test  = _write_jsonl(test_recs, test_path)
    h_all   = _write_jsonl(train_recs + val_recs + test_recs, all_path)

    total = len(train_recs) + len(val_recs) + len(test_recs)

    return {
        "total_exported": total,
        "partitions": {
            "train": {"count": len(train_recs), "sha256": h_train, "file": str(train_path)},
            "validation": {"count": len(val_recs), "sha256": h_val, "file": str(val_path)},
            "test": {"count": len(test_recs), "sha256": h_test, "file": str(test_path)},
        },
        "all_partitioned": {"count": total, "sha256": h_all, "file": str(all_path)},
        "accepted_count": sum(1 for d in decisions.values() if d.get("state") == "accepted"),
        "revised_count": sum(1 for d in decisions.values() if d.get("state") == "revised"),
        # Legacy compat
        "output_file": str(train_path),
        "export_sha256": h_train,
    }
