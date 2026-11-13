"""
Verification gate for workflow documentation (TASK-9-DOCS).
Verifies AC-9.
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True

DOCS_PATH = Path(__file__).parent.parent / "docs" / "workflow.md"


def test_docs_exist_and_complete():
    assert DOCS_PATH.is_file(), f"Documentation missing: {DOCS_PATH}"
    content = DOCS_PATH.read_text(encoding="utf-8")
    assert len(content) > 500, "Documentation file too short"

    required_keywords = [
        "ADR-001",
        "pain_point",
        "personalization_angle",
        "LinkedIn",
        "Website",
        "Zero-Leakage",
        "prepare_review_queue",
        "export_slm_dataset",
        "artifacts/slm_train.jsonl",
    ]

    for kw in required_keywords:
        assert kw in content, f"Missing required keyword in documentation: '{kw}'"


if __name__ == "__main__":
    test_docs_exist_and_complete()
    print("ALL DOCS TESTS PASSED")
