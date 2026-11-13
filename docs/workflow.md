# ADR Data-Labeling & Decision Workflow Guide

> Project: **EmailSLM** | Repository: **slm-2** | Author: **Diwas (GTM AI Engineer)**

This repository implements a verifiable, provenance-tracked ADR data-labeling and decision workflow for small language model (SLM) cold outreach fine-tuning.

---

## 1. Architectural Foundations (ADR-001)

As documented in [`ADRs/ADR-001-dataset-strategy-and-evaluation.md`](../ADRs/ADR-001-dataset-strategy-and-evaluation.md):
- **100% Training Partition:** The 48 curated leads (34 marketing + 14 accounting) are allocated to training. Evaluation is conducted live in production against manual reply rate parity ($R_{\text{model}} \ge R_{\text{manual}}$) and editorial acceptance ($Q_{\text{model}} \ge 0.75$).
- **Immutable Raw Data:** Raw files in `data/` and decisions in `ADRs/` are strictly read-only. All derived candidates, editorial decisions, and training outputs live in `artifacts/`.
- **4-Field Label Taxonomy:**
  1. `pain_point`: Diagnostic operational bottleneck / time-profit leak.
  2. `personalization_angle`: Specific verifiable hook from LinkedIn post / website.
  3. `subject`: Pattern-interrupt subject line adhering to Noman's 22 rules.
  4. `body`: Outreach email copy signed off with `Regards,\nDiwas`.

---

## 2. Directory Structure

```text
slm-2/
├── ADRs/                                     # Architectural Decision Records
│   └── ADR-001-dataset-strategy-and-evaluation.md
├── data/                                     # IMMUTABLE raw inputs & candidate sources
│   ├── accounting.json                       # 14 raw accounting firm leads
│   ├── marketing.json                        # 34 raw marketing agency leads
│   ├── contact/
│   │   └── contact.json                      # Enriched contact directory (LinkedIn, website)
│   └── updated/
│       ├── accounting_update.json            # Pre-generated Claude decompositions (14)
│       └── marketing_update.json             # Pre-generated Claude decompositions (34)
├── src/                                      # Python 3.11+ stdlib modules
│   ├── schema.py                             # 4-field taxonomy & decision state validators
│   ├── ingest.py                             # Raw data & ADR ingestion, SHA-256 hashing
│   ├── teacher.py                            # Claude teacher prompt & trace generation
│   ├── decision.py                           # State machine engine & stale detector
│   ├── review_cli.py                         # Single-reviewer CLI with LinkedIn/website display
│   ├── export.py                             # SLM training dataset JSONL generator
│   ├── audit.py                              # Zero-leakage & partition integrity auditor
│   └── recovery.py                           # Fault tolerance, resume & idempotency engine
├── artifacts/                                # Generated / derived artifacts
│   ├── decisions.json                        # Current decision store with audit history
│   └── slm_train.jsonl                       # Downstream training dataset
└── docs/
    ├── workflow.md                           # This guide
    └── show-me-adr-workflow.html             # Visual dashboard
```

---

## 3. Step-by-Step Execution Guide

### Step 1: Ingest Raw Data and Prepare Review Queue
```python
from decision import init_decision_store
from review_cli import prepare_review_queue

store = init_decision_store()
pending = prepare_review_queue(store)
print(f"Total pending review: {len(pending)}")
```
This binds each prospect lead with their contact links (`data/contact/contact.json`) and Claude teacher draft (`data/updated/`), assigning deterministic IDs (`REC-<sector>-<hash>`).

### Step 2: Human Review (Diwas Editorial Gate)
Run the review session. Each card displays:
- Record ID and Sector
- Prospect Name and Company
- **Website URL**
- **LinkedIn Profile URL**
- 4-field candidate decomposition (`pain_point`, `personalization_angle`, `subject`, `body`)

Supported actions:
- `accept`: Approve verbatim.
- `revise`: Provide adjusted copy (tracked to monitor voice drift; aim for $\ge 30\%$ human edits).
- `reject`: Disqualify irrelevant or low-signal leads.
- `uncertain`: Hold for a second pass.

```python
from review_cli import apply_review_decision

apply_review_decision(store, source_id="REC-marketing-...", action="accept", notes="Strong diagnostic hook")
```

### Step 3: Export SLM Dataset (JSONL)
```python
from export import export_slm_dataset

receipt = export_slm_dataset()
print("Export summary:", receipt)
```
Generates `artifacts/slm_train.jsonl` with full cryptographic provenance on every line.

### Step 4: Verify Zero-Leakage & Integrity Audit
```python
from audit import audit_exported_dataset

audit_report = audit_exported_dataset()
assert audit_report["verified"] is True
print("Zero leakage verified:", audit_report["zero_leakage_passed"])
```

### Step 5: Crash Recovery & Resume
If review or export is interrupted, simply rerun `prepare_review_queue()`. Already approved or rejected decisions in `artifacts/decisions.json` are retained and skipped, never duplicated.

