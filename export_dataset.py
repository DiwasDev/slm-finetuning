"""
Dataset Export and Zero-Leakage Audit Runner.
Run: python export_dataset.py
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent / "src"))

from export import export_slm_dataset, DEFAULT_EXPORT_PATH
from audit import audit_exported_dataset
from decision import DEFAULT_STORE_PATH


def main():
    print("=======================================================")
    print("  EMAIL-SLM DATASET EXPORT & ZERO-LEAKAGE AUDIT")
    print("=======================================================\n")

    print("1. Exporting approved decisions from artifacts/decisions.json...")
    try:
        receipt = export_slm_dataset(store_path=DEFAULT_STORE_PATH, output_path=DEFAULT_EXPORT_PATH)
    except Exception as e:
        print(f"Export failed: {e}")
        return

    print(f"   -> Output File:    {receipt['output_file']}")
    print(f"   -> Total Examples: {receipt['total_exported']}")
    print(f"   -> Accepted:       {receipt['accepted_count']}")
    print(f"   -> Revised:        {receipt['revised_count']}")
    print(f"   -> SHA-256 Digest: {receipt['export_sha256']}\n")

    print("2. Running cryptographic integrity and leakage audit...")
    audit = audit_exported_dataset(jsonl_path=DEFAULT_EXPORT_PATH, store_path=DEFAULT_STORE_PATH)

    print(f"   -> Audit Verified: {audit['verified']}")
    print(f"   -> Zero Leakage:   {audit['zero_leakage_passed']}")
    print(f"   -> Deduplication:  {audit['deduplication_passed']}")
    print(f"   -> Checked Records:{audit['total_records_checked']}")

    if audit["errors"]:
        print("\n   [!] Audit detected errors:")
        for err in audit["errors"]:
            print(f"       - {err}")
    else:
        print("\n[SUCCESS] Dataset is validated, leakage-free, and ready for SLM training!")


if __name__ == "__main__":
    main()

