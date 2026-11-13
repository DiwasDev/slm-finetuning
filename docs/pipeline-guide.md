# EmailSLM Pipeline & Architecture Guide

> **Project:** EmailSLM  
> **Repository:** `slm-2`  
> **Author & Reviewer:** Diwas (GTM AI Engineer)  
> **Status:** Production-Ready & Audited (102 Leads, 80/10/10 Partitioned)

---

## 1. Executive Summary

This project prepares high-signal, human-verified training datasets to fine-tune a Small Language Model (~3B parameters, such as Qwen2.5-3B or Llama-3.2-3B) to generate hyper-personalized B2B cold outreach emails following **Noman's 22-rule framework**.

```mermaid
flowchart LR
    A["Raw Data (48 Leads)"] --> B["PII Scrub & Purge"]
    B --> C["Synthetic Scale-Up<br/>(Claude Teacher +54)"]
    C --> D["102 Total Leads<br/>(4-Field Decompositions)"]
    D --> E["Diwas Human Review<br/>(89 Revised, 7 Accepted, 6 Rejected)"]
    E --> F["Zero-Leakage Export<br/>(96 Approved Records)"]
    F --> G["80/10/10 Partition<br/>Train: 76 | Val: 10 | Test: 10"]
    G --> H["SLM LoRA Fine-Tuning<br/>(Qwen2.5-3B / Llama-3.2-3B)"]
```

---

## 2. Why We Expanded Beyond 48 Leads

The initial dataset contained 48 leads (34 marketing + 14 accounting). Empirical SFT literature demonstrates that $<80$ samples is below the reliable generalization floor for a 3B-parameter model:
- **Memorization Risk:** With only 48 samples, LoRA updates overfit to specific entity names rather than learning the generalized 4-field reasoning chain.
- **Evaluation Impossibility:** With 48 leads, withholding a validation and test set leaves $<38$ training samples—far too few to absorb Noman's 22 rules.
- **Solution:** We expanded to **102 leads** by synthesizing 54 realistic B2B marketing & sales agency profiles, generating complete Claude teacher candidate drafts, and running every single lead through Diwas's human editorial review.

```mermaid
flowchart TD
    subgraph "Before (48 Leads Baseline)"
        A1["48 Leads (Raw PII)"] --> B1["Memorization Risk (KK-1)"]
        A1 --> C1["No Held-Out Validation Split"]
        A1 --> D1["Real Emails/Phones in Git History"]
    end
    subgraph "After (102 Leads - Current State)"
        A2["102 Clean Leads"] --> B2["PII Purged (RFC 2606 Reserved)"]
        A2 --> C2["54 Diverse Synthetic Agencies"]
        A2 --> D2["100% Diwas Reviewed (87.3% Edited)"]
        A2 --> E2["Stratified 80/10/10 Partition"]
        E2 --> F2["Train: 76 | Val: 10 | Test: 10"]
    end
```

---

## 3. End-to-End Pipeline Interaction

```mermaid
sequenceDiagram
    autonumber
    participant Raw as Raw Lead Data
    participant PII as PII Scrub & Ingest
    participant Teacher as Claude 3.5 Sonnet
    participant UI as Streamlit / Web UI
    participant Diwas as Diwas (Human Gate)
    participant Export as Export & Split Engine
    participant Audit as Cryptographic Auditor
    participant SLM as SLM Fine-Tuning

    Raw->>PII: Raw business context (LinkedIn, Website)
    PII->>Teacher: Anonymized context (RFC 2606)
    Teacher->>UI: 4-field candidate decomposition
    UI->>Diwas: Interactive review card with LinkedIn/Website
    Diwas->>UI: Human decision (89 revised, 7 accepted, 6 rejected)
    UI->>Export: Sync to artifacts/decisions.json
    Export->>Audit: Export 80/10/10 partitioned JSONL
    Audit-->>Export: Verify Train ∩ Val = ∅, Zero-Leakage = Passed
    Export->>SLM: slm_train.jsonl (76) & slm_val.jsonl (10)
```

---

## 4. Decision Lifecycle State Machine

Every lead transitions through a formal state machine to ensure zero stale decisions and strict auditability:

```mermaid
stateDiagram-v2
    [*] --> proposed: Ingest from raw sources
    proposed --> needs_review: Enqueued in decisions store
    needs_review --> revised: Diwas adjusts hook / voice / body (89)
    needs_review --> accepted: Diwas accepts verbatim (7)
    needs_review --> rejected: Diwas disqualifies lead (6)
    needs_review --> uncertain: Hold for second pass
    uncertain --> revised: Resolved with edits
    uncertain --> accepted: Resolved verbatim
    uncertain --> rejected: Disqualified
    revised --> revised: Re-edited in dashboard
    revised --> accepted: Toggled to verbatim
    accepted --> revised: Edited after accept
    revised --> [*]: Exported to JSONL (slm_train/val/test)
    accepted --> [*]: Exported to JSONL (slm_train/val/test)
    rejected --> [*]: Withheld (Zero-Leakage)
```

---

## 5. The 4-Field Output Taxonomy

The model is trained on a structured diagnostic chain. The inputs from the prospect's public presence map directly to the 4 targets:

```mermaid
flowchart TD
    subgraph INPUT ["Prospect Profile (x_i)"]
        I1["Website Copy & Case Studies"]
        I2["LinkedIn Headline & About"]
        I3["Recent Posts & Engagements"]
        I4["Company Sector & Scale"]
    end

    subgraph TARGET ["4-Field SLM Training Output (y_i)"]
        F1["1. Diagnostic Operational Pain Point<br/>(Real operational bottleneck or profit leak)"]
        F2["2. Personalization Angle<br/>(Verifiable evidence citation from public presence)"]
        F3["3. Pattern-Interrupt Subject Hook<br/>(Under 8 words, zero spam triggers, Noman's 22 rules)"]
        F4["4. Email Message Body<br/>(Under 85 words, 1 pain point, soft question CTA, 'Regards, Diwas')"]
    end

    I1 --> F1
    I2 --> F2
    I3 --> F2
    I4 --> F1
    F1 --> F3
    F1 --> F4
    F2 --> F4
    F3 --> F4
```

---

## 6. Runtime Execution Flow

```mermaid
flowchart TD
    Start(["Launch Review UI / CLI"]) --> S1["init_decision_store()"]
    S1 --> S2["ingest_all_raw_data()"]
    S2 --> S3["get_all_review_items()"]
    S3 --> S4["Render Review Card<br/>(LinkedIn + Website + 4 Fields)"]
    S4 --> S5{"Diwas Decision"}
    S5 -->|"Revise"| A1["apply_review_decision('revise')"]
    S5 -->|"Accept"| A2["apply_review_decision('accept')"]
    S5 -->|"Reject"| A3["apply_review_decision('reject')"]
    A1 --> S6["Save synchronously to decisions.json"]
    A2 --> S6
    A3 --> S6
    S6 --> S7["export_slm_dataset()"]
    S7 --> S8["audit_exported_dataset()"]
    S8 -->|"Verified (0 Errors)"| Done(["JSONL Datasets Ready for Fine-Tuning"])
```

---

## 7. Dataset Partitioning & Cryptographic Isolation

The 102 leads are partitioned into Train, Validation, and Test splits with mathematical zero-overlap and zero-leakage verification:

$$\mathcal{D}_{\text{train}} \cap \mathcal{D}_{\text{val}} = \emptyset, \quad \mathcal{D}_{\text{train}} \cap \mathcal{D}_{\text{test}} = \emptyset, \quad \mathcal{D}_{\text{val}} \cap \mathcal{D}_{\text{test}} = \emptyset$$

```mermaid
flowchart TD
    All["102 Total Leads (Curated & Anonymized)"] --> Review["Diwas Editorial Review (100% Reviewed)"]
    
    Review --> Approved["96 Approved Leads<br/>(89 Revised + 7 Accepted)"]
    Review --> Rej["6 Disqualified Leads<br/>(Withheld per Zero-Leakage)"]
    
    Approved --> Split["Stratified Partition Split (80 / 10 / 10)"]
    
    Split --> Train["Train Partition (76 Approved Leads)<br/>artifacts/slm_train.jsonl"]
    Split --> Val["Validation Partition (10 Approved Leads)<br/>artifacts/slm_val.jsonl"]
    Split --> Test["Test Partition (10 Approved Leads)<br/>artifacts/slm_test.jsonl"]
    
    Train -.-> Proof{"Audit Proof:<br/>Train ∩ Val = ∅<br/>Train ∩ Test = ∅<br/>Val ∩ Test = ∅"}
    Val -.-> Proof
    Test -.-> Proof
    Proof --> Verified["✅ Verified Cryptographic Zero-Overlap"]
```

---

## 8. System Module Architecture

```mermaid
flowchart LR
    subgraph DATA ["Data Layer"]
        D1["data/marketing.json (88)"]
        D2["data/accounting.json (14)"]
        D3["data/contact/contact.json (102)"]
        D4["data/updated/*.json"]
    end

    subgraph ENGINE ["Core Engine (src/)"]
        M1["ingest.py"]
        M2["decision.py"]
        M3["review_cli.py"]
        M4["export.py"]
        M5["audit.py"]
        M6["schema.py"]
        M7["recovery.py"]
    end

    subgraph UI ["User Interfaces"]
        U1["streamlit_app.py"]
        U2["app.py"]
    end

    subgraph OUTPUT ["Exported Artifacts"]
        A1["artifacts/slm_train.jsonl (76)"]
        A2["artifacts/slm_val.jsonl (10)"]
        A3["artifacts/slm_test.jsonl (10)"]
        A4["artifacts/slm_all_partitioned.jsonl (96)"]
    end

    DATA --> M1
    M1 --> M2
    M2 --> M3
    M3 --> UI
    UI --> M2
    M2 --> M4
    M4 --> M5
    M4 --> OUTPUT
    M5 --> OUTPUT
```
