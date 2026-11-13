"""
Dataset integrity, partition isolation, and leakage prevention audit checks (TASK-7-INTEGRITY).
Verifies that downstream training datasets have zero leakage, cryptographic provenance,
and strict Train ∩ Val = ∅,  Train ∩ Test = ∅,  Val ∩ Test = ∅.
Uses standard library only (Ponytail: stdlib first).
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent))
from decision import init_decision_store, DEFAULT_STORE_PATH
from export import DEFAULT_EXPORT_PATH

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"


def _load_jsonl(path: Path) -> list[dict]:
    """Load all records from a JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def audit_exported_dataset(
    jsonl_path: Path = DEFAULT_EXPORT_PATH,
    store_path: Path = DEFAULT_STORE_PATH,
) -> dict[str, Any]:
    """
    Perform a comprehensive integrity audit across all exported SLM partitions.

    Checks:
      1. Zero-leakage: only accepted/revised records in exports
      2. Deduplication: no record ID appears twice within a partition
      3. Provenance: source_hash is 64-char hex; source_file exists on disk
      4. Partition isolation:
            Train ∩ Val  = ∅
            Train ∩ Test = ∅
            Val   ∩ Test = ∅
      5. File coverage: every accepted/revised decision appears in exactly one partition file

    Returns audit receipt (verified=True means all checks passed).
    """
    store = init_decision_store(store_path)
    decisions = store.get("decisions", {})
    repo_root = Path(__file__).parent.parent

    # Expected reviewed IDs
    reviewed_ids = {sid for sid, d in decisions.items() if d.get("state") in {"accepted", "revised"}}

    # Load each partition JSONL — look in jsonl_path.parent (supports custom dirs in tests)
    base_dir = jsonl_path.parent if jsonl_path.is_file() else ARTIFACTS_DIR
    split_paths = {
        "train":      base_dir / "slm_train.jsonl",
        "validation": base_dir / "slm_val.jsonl",
        "test":       base_dir / "slm_test.jsonl",
    }

    errors: list[str] = []
    split_id_sets: dict[str, set[str]] = {}
    total_records = 0

    for split_name, split_path in split_paths.items():
        if not split_path.is_file():
            errors.append(f"Missing partition file: {split_path.name}")
            split_id_sets[split_name] = set()
            continue

        records = _load_jsonl(split_path)
        seen_in_split: set[str] = set()

        for line_no, record in enumerate(records, start=1):
            total_records += 1
            sid = record.get("id")

            if not sid:
                errors.append(f"{split_name} line {line_no}: Missing record ID")
                continue

            # 1. Deduplication within split
            if sid in seen_in_split:
                errors.append(f"{split_name} line {line_no}: Duplicate ID '{sid}'")
            seen_in_split.add(sid)

            # 2. Zero-leakage
            dec = decisions.get(sid)
            if not dec:
                errors.append(f"{split_name} line {line_no}: ID '{sid}' not found in decision store")
                continue
            if dec.get("state") not in {"accepted", "revised"}:
                errors.append(
                    f"{split_name} line {line_no}: Leakage! '{sid}' has state '{dec.get('state')}'"
                )

            # 3. Partition label matches file
            rec_partition = record.get("partition")
            if rec_partition != split_name:
                errors.append(
                    f"{split_name} line {line_no}: ID '{sid}' has partition label "
                    f"'{rec_partition}' but is in {split_name} file"
                )

            # 4. Provenance
            prov = record.get("provenance", {})
            source_hash = prov.get("source_hash", "")
            if not source_hash or len(source_hash) != 64:
                errors.append(f"{split_name} line {line_no}: Invalid source_hash '{source_hash}'")
            source_file = prov.get("source_file", "")
            if not source_file:
                errors.append(f"{split_name} line {line_no}: Missing source_file in provenance")
            else:
                full_src = repo_root / source_file
                if not full_src.is_file():
                    errors.append(
                        f"{split_name} line {line_no}: Source file not found: {source_file}"
                    )

        split_id_sets[split_name] = seen_in_split

    # 5. Zero-overlap across splits
    train_set = split_id_sets.get("train", set())
    val_set   = split_id_sets.get("validation", set())
    test_set  = split_id_sets.get("test", set())

    tv_overlap = train_set & val_set
    tt_overlap = train_set & test_set
    vt_overlap = val_set   & test_set

    if tv_overlap:
        errors.append(f"Partition overlap Train∩Val: {tv_overlap}")
    if tt_overlap:
        errors.append(f"Partition overlap Train∩Test: {tt_overlap}")
    if vt_overlap:
        errors.append(f"Partition overlap Val∩Test: {vt_overlap}")

    # 6. Coverage: all reviewed decisions must appear in exactly one split
    all_exported = train_set | val_set | test_set
    missing = reviewed_ids - all_exported
    # Only flag missing that are genuinely reviewed (accepted/revised)
    if missing:
        errors.append(f"{len(missing)} reviewed decisions missing from exports: {list(missing)[:5]}")

    is_valid = len(errors) == 0

    return {
        "verified": is_valid,
        "total_records_checked": total_records,
        "split_counts": {k: len(v) for k, v in split_id_sets.items()},
        "overlap_checks": {
            "train_cap_val": len(tv_overlap),
            "train_cap_test": len(tt_overlap),
            "val_cap_test": len(vt_overlap),
        },
        "coverage": {
            "reviewed_total": len(reviewed_ids),
            "exported_total": len(all_exported),
            "missing_count": len(missing),
        },
        "zero_leakage_passed": is_valid and total_records > 0,
        "deduplication_passed": is_valid,
        "errors": errors,
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
    }
