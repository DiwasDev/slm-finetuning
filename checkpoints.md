# Checkpoints

## Checkpoint Log

### 2026-11-12 — ADRs Folder Created

An `ADRs/` directory has been created at the project root:
`c:\Users\diwas\OneDrive\Documents\slm-2\ADRs\`

**Purpose:** Architectural Decision Records. Any agent working on this project should read the ADRs before making any pipeline, training, or evaluation decisions. The ADRs contain:
- Assumptions (mathematical + informal)
- Failure modes (Known Knowns, Known Unknowns, Unknown Unknowns, Unknown Knowns)
- Considerations
- Research clusters with open research questions

**Current ADRs:**
| File | Decision Captured |
|------|------------------|
| `ADR-001-dataset-strategy-and-evaluation.md` | Why we use the full dataset for training with no train/test split; in-production evaluation strategy; all failure modes and research questions |

**Status:** Plan only. No code has been written. No pipeline has been built. Data has been read and understood.

---

*Add new checkpoint entries below this line, newest first.*

### 2026-11-13 — Verifiable ADR Data-Labeling & Decision Workflow Integrated

Genesis harness adopted and 9-task implementation plan completed:
- **Specification (`SPEC.md`):** 26 requirements covering ADR discovery, 4-field label taxonomy, Claude teacher traces, single-reviewer (Diwas) decision state machine, and JSONL SLM training export.
- **Source Ingestion (`src/ingest.py`):** Ingests all 48 raw leads (34 marketing in `data/marketing.json` + 14 accounting in `data/accounting.json`) with deterministic `REC-<sector>-<hash>` IDs and SHA-256 provenance while keeping raw source files immutable.
- **Claude Teacher Integration (`src/teacher.py`):** Ingests 48 pre-generated Claude Sonnet decompositions from `data/updated/` (`accounting_update.json` + `marketing_update.json`), validated against the strict 4-field taxonomy (`pain_point`, `personalization_angle`, `subject`, `body`).
- **Contact Directory Display (`src/review_cli.py`):** Enriched with `data/contact/contact.json` to display live LinkedIn profile links and company website URLs during review.
- **Decision Engine (`src/decision.py`):** State transitions (`proposed` -> `needs-review` -> `accepted` / `revised` / `rejected` / `uncertain`), audit history logging, and automatic stale invalidation on source data changes.
- **Dataset Export & Audit (`src/export.py`, `src/audit.py`):** Exports approved decisions into `artifacts/slm_train.jsonl` with full cryptographic provenance and executes zero-leakage / partition isolation audit.
- **Recovery Engine (`src/recovery.py`):** Idempotent re-runs and interruption recovery without duplicate decisions.
- **All 9 Executable Gates Passed:** 100% test pass rate across all test suites.


