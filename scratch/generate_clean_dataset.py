"""
Generate clean, anonymized dataset and expand to 102 high-quality B2B leads.
14 Accounting + 88 Marketing (34 original + 54 new synthetic agencies).
Strictly adheres to Noman's 22 rules, RFC 2606 reserved domains, and stdlib only.
"""

import hashlib
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

def canonical_hash(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

print("Script template ready.")

