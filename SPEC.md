# Product specification — slm-2

> Status: draft. A coding agent must not implement product code until this specification is approved through Genesis.

## Problem

The EmailSLM project requires a verifiable, reproducible ADR-grounded data-labeling and decision pipeline for small language model fine-tuning. The repository contains 48 raw cold-outreach leads across two sectors (34 marketing leads in `data/marketing.json` and 14 accounting leads in `data/accounting.json`), along with architectural principles in `ADRs/ADR-001-dataset-strategy-and-evaluation.md`.

Currently, the raw datasets contain raw context and sent email drafts, but lack decomposed target labels (`pain_point`, `personalization_angle`, `subject`, `body`), structured teacher generation traces, human review states, and cryptographically verifiable provenance. Raw data must remain untouched while producing a validated, high-integrity JSONL dataset suitable for downstream SLM training.

## Users

- **Diwas (GTM AI Engineer / Lead Reviewer):** Inspects candidate labels, applies editorial review, accepts, revises, or rejects records, and verifies training dataset readiness.
- **Teacher Model (Claude Sonnet):** Proposes candidate decomposed labels from raw lead context and historical emails based on the Noman 22-rule cold outreach framework.
- **Downstream SLM Training Pipeline:** Ingests the exported, schema-validated, leakage-free JSONL dataset for LoRA fine-tuning.

## Functional requirements

- FR-1: **ADR Discovery & Ingestion:** The system discovers and parses architectural decisions from `ADRs/` (specifically `ADR-001`), extracting active assumptions, label taxonomy, and evaluation constraints.
- FR-2: **Raw Data Discovery & Stable Identifiers:** The system ingests raw leads from `data/marketing.json` and `data/accounting.json` without modifying the source files, generating deterministic, collision-free record IDs (`REC-<sector>-<hash>`).
- FR-3: **Versioned Label Taxonomy:** The system enforces a strict 4-field label structure: `pain_point` (string), `personalization_angle` (string), `subject` (string), and `body` (string).
- FR-4: **Teacher Candidate Ingestion:** The system accepts candidate labels produced by the Claude teacher model, preserving the raw teacher response, model version, and prompt reference.
- FR-5: **Provenance & Source Hashing:** Every derived record stores the source file path, source record index, SHA-256 hash of the raw record, and generation timestamp.
- FR-6: **Reviewer Decision State Machine:** The system implements a formal decision state machine supporting: `proposed` -> `needs-review` -> `accepted` | `rejected` | `revised` | `uncertain` | `superseded`.
- FR-7: **Single-Reviewer Human Review Interface:** The system provides an interactive CLI or programmatic interface for Diwas to inspect candidates, record approval decisions, make manual edits (`revised`), or reject low-quality drafts with mandatory rationales.
- FR-8: **Schema Validation & Error Handling:** The system validates all derived records and decisions against strict JSON schemas, rejecting malformed data, missing fields, or illegal state transitions.
- FR-9: **Idempotent Execution & Resume:** Rerunning the workflow over unchanged inputs reproduces identical outputs. Interrupted runs resume cleanly from the last valid checkpoint without duplicating decisions.
- FR-10: **Staleness Invalidation:** If source data changes (detected via source hash mismatch), existing derived decisions referencing that record are flagged as `stale` and require re-evaluation.
- FR-11: **SLM Dataset Export:** The system exports approved records into a validated JSONL dataset ready for SLM fine-tuning, containing prompt context and target labels.
- FR-12: **Dataset Isolation & Integrity Audit:** The export verifies 100% partition coverage, checks for duplicate records, verifies that no raw unreviewed records leak into training, and outputs a summary audit report.

## Non-functional requirements

- NFR-1: **Source Immutability:** Raw source files (`data/*.json`, `ADRs/*.md`) must never be modified, renamed, or overwritten.
- NFR-2: **Deterministic Cryptographic Verification:** All record IDs, source hashes, and export signatures must use deterministic SHA-256 hashing.
- NFR-3: **Minimal Overhead (Ponytail):** The implementation must use lightweight, dependency-free Python standard library scripts (Python 3.11+), avoiding bloated external dependencies or complex frameworks.
- NFR-4: **Auditability & Traceability:** Every exported training line in JSONL must map back to a specific decision record, reviewer timestamp, and raw source hash.
- NFR-5: **Privacy & Boundary Protection:** Private lead contact information (emails, phone numbers) must not be logged in public Genesis traces, error logs, or terminal outputs.

## Constraints

- Runtime environment: Python 3.11+ on Windows.
- Storage separation: All derived artifacts must be written to `.genesis/` or a dedicated `artifacts/derived/` folder, never in `data/`.
- Single human reviewer authority: Diwas is the designated reviewer. No automated process may infer or forge human approval.
- Full dataset strategy: Consistent with ADR-001, all 48 curated records are targeted for the training partition without an artificial train/test split.

## Non-goals

- Fine-tuning or executing the SLM model weights.
- Sending live outreach emails or connecting to live email accounts.
- Automated multi-reviewer consensus algorithms or external database backends.
- Modifying raw input files or altering source schemas.

## Acceptance criteria

- AC-1: **Raw Source Immutability:** SHA-256 hashes of `data/accounting.json`, `data/marketing.json`, and `ADRs/ADR-001-dataset-strategy-and-evaluation.md` before and after running any workflow tool are identical.
- AC-2: **Schema Conformance:** 100% of generated candidate labels and decision records pass strict schema validation (all 4 required fields present, correct data types).
- AC-3: **Provenance Reference:** Every decision record contains a verifiable `source_id`, `source_file`, `source_hash`, and generation timestamp matching the raw source data.
- AC-4: **State Transition Enforcement:** The decision engine allows valid transitions (`proposed` -> `accepted`/`rejected`/`revised`/`uncertain`) and rejects invalid transitions (e.g. `rejected` directly to `exported` without re-review).
- AC-5: **Idempotent Processing:** Running the ingestion and decision verification twice on identical raw inputs produces identical output artifacts and identical SHA-256 hashes.
- AC-6: **Stale Record Detection:** If a record's source hash is modified, the validator marks any existing decision for that record as `stale` and prevents export.
- AC-7: **Valid JSONL Dataset Generation:** The export command produces a valid `.jsonl` file containing exactly the `accepted` and `revised` records, properly formatted for SLM fine-tuning.
- AC-8: **Fault Recovery & Resume:** If execution halts mid-process, re-running the command resumes at the unreviewed records without duplicating or overwriting already `accepted` decisions.
- AC-9: **Repository Integrity:** Existing project checkpoints and ADRs remain unchanged, passing `genesis spec check .` with zero errors.

## Risks

- **Risk: Rubric drift during human review.**
  *Mitigation:* ADR-001 Section 3 requires a fixed review rubric; review interface displays rubric prompts during evaluation.
- **Risk: Stylistic mimicry of teacher over user's authentic tone.**
  *Mitigation:* Track the percentage of records edited by Diwas during review; flag if edit rate drops below 30% as warned in ADR-001 KK-3.
- **Risk: Small sample size (N=48).**
  *Mitigation:* Every record undergoes 100% human verification and provenance tracking to guarantee maximum data quality for LoRA.

## Open questions

- None. (All 5 workflow questions regarding label schema, teacher generation, single-reviewer role, JSONL export, and 100% training partition were clarified and locked on 2026-11-12).
