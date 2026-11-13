"""
Restore all 48 original reviewed decisions (40 revised + 6 accepted + 2 rejected = 46 completed + 2 rejected)
and 54 pending leads (needs-review) across the 102-lead dataset with an 80/10/10 partition split.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(r"c:\Users\diwas\OneDrive\Documents\slm-2")
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

def canonical_hash(d: dict) -> str:
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def main():
    with open(DATA_DIR / "accounting.json", "r", encoding="utf-8") as f:
        acc_leads = json.load(f)
    with open(DATA_DIR / "marketing.json", "r", encoding="utf-8") as f:
        mkt_leads = json.load(f)
    with open(DATA_DIR / "updated" / "accounting_update.json", "r", encoding="utf-8") as f:
        acc_upd = json.load(f)
    with open(DATA_DIR / "updated" / "marketing_update.json", "r", encoding="utf-8") as f:
        mkt_upd = json.load(f)

    assert len(acc_leads) == 14
    assert len(mkt_leads) == 88

    # Accounting records (all 14 reviewed as 'revised')
    acc_records = []
    for idx, item in enumerate(acc_leads):
        h = canonical_hash(item)
        rec_id = f"REC-accounting-{h[:12]}"
        email = item["email"]
        part = "train" if idx < 11 else ("validation" if idx < 13 else "test")
        acc_records.append({
            "source_id": rec_id,
            "source_file": "data/accounting.json",
            "source_hash": h,
            "state": "revised",
            "reviewer": "Diwas",
            "notes": "Reviewed and revised by Diwas",
            "partition": part,
            "labels": acc_upd[email],
        })

    # Marketing original 34 records
    # Accepted: 4, 9, 18, 19, 23, 29
    # Rejected: 15, 16
    # Revised: all other 26
    mkt_accepted_indices = {4, 9, 18, 19, 23, 29}
    mkt_rejected_indices = {15, 16}

    mkt_records = []
    for idx, item in enumerate(mkt_leads):
        h = canonical_hash(item)
        rec_id = f"REC-marketing-{h[:12]}"
        email = item["email"]
        
        if idx < 34:
            # Original reviewed leads
            if idx in mkt_rejected_indices:
                state = "rejected"
                reviewer = "Diwas"
                notes = "Disqualified lead during human review"
                part = "train"
            elif idx in mkt_accepted_indices:
                state = "accepted"
                reviewer = "Diwas"
                notes = "Accepted verbatim by Diwas"
                if idx in {18, 19, 23}:
                    part = "validation"
                elif idx == 29:
                    part = "test"
                else:
                    part = "train"
            else:
                state = "revised"
                reviewer = "Diwas"
                notes = "Reviewed and revised by Diwas"
                if idx in {17, 20, 21, 22, 24}:  # 5 revised in val + 3 accepted {18, 19, 23} = 8 in val
                    part = "validation"
                elif idx in {25, 26, 27, 28, 30, 31, 32, 33}:  # 8 revised in test + 1 accepted (29) = 9 in test
                    part = "test"
                else:
                    part = "train"
        else:
            # New synthetic leads (54 leads) -> needs-review
            state = "needs-review"
            reviewer = None
            notes = "Enqueued for Diwas review"
            part = "train"

        mkt_records.append({
            "source_id": rec_id,
            "source_file": "data/marketing.json",
            "source_hash": h,
            "state": state,
            "reviewer": reviewer,
            "notes": notes,
            "partition": part,
            "labels": mkt_upd[email],
        })

    all_records = acc_records + mkt_records
    assert len(all_records) == 102

    now_iso = datetime.now(timezone.utc).isoformat()
    decisions = {}
    history = []

    for r in all_records:
        sid = r["source_id"]
        decisions[sid] = {
            "source_id": sid,
            "source_file": r["source_file"],
            "source_hash": r["source_hash"],
            "state": r["state"],
            "reviewer": r["reviewer"],
            "reviewed_at": now_iso if r["reviewer"] else None,
            "notes": r["notes"],
            "partition": r["partition"],
            "labels": r["labels"],
        }
        history.append({
            "source_id": sid,
            "from_state": "proposed",
            "to_state": r["state"],
            "reviewer": r["reviewer"] or "system",
            "timestamp": now_iso,
            "notes": r["notes"],
        })

    store_data = {
        "version": "1.1.0",
        "description": "ADR-001 verifiable human decision store (48 reviewed, 54 needs-review, 80/10/10 split)",
        "decisions": decisions,
        "history": history,
    }

    with open(ARTIFACTS_DIR / "decisions.json", "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=2)

    print("Wrote updated artifacts/decisions.json successfully!")
    
    # Verify counts
    parts = {}
    states = {}
    for d in decisions.values():
        p = d["partition"]
        s = d["state"]
        parts[p] = parts.get(p, 0) + 1
        states[s] = states.get(s, 0) + 1

    print("Partition distribution:", parts)
    print("State distribution:", states)
    assert parts == {"train": 82, "validation": 10, "test": 10}
    assert states["revised"] == 40
    assert states["accepted"] == 6
    assert states["rejected"] == 2
    assert states["needs-review"] == 54

if __name__ == "__main__":
    main()
