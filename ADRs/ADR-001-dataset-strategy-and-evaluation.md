~# ADR-001: Dataset Strategy, Assumptions, Failure Modes & Research Clusters

**Status:** Active  
**Date:** 2026-11-12  
**Author:** Diwas (GTM AI Engineer)  
**Scope:** EmailSLM — Cold Outreach Fine-Tuning Pipeline  
**Decision:** Use full dataset for training; defer held-out evaluation to live production usage.

---

## Context

We are fine-tuning a small language model (SLM, ~3B parameters) to draft cold outreach emails
targeting American businesses. The email must follow a specific style (Noman's 22-rule framework),
surface a personalized pain point from lead context (LinkedIn + website), and produce a reply-worthy
message — without Diwas spending time writing each one manually.

The dataset is small (~34 marketing + ~14 accounting leads). Rather than splitting it into
train/val/test (which would waste scarce signal), we commit the full curated set to training and
evaluate the model's real-world performance in-production: when Diwas uses the model to draft
future emails, the reply rate and his own editorial judgment become the ground truth.

---

## 1. Assumptions

### 1.1 Informal Assumptions

| # | Assumption | Consequence if Wrong |
|---|-----------|---------------------|
| A1 | Claude Sonnet rewrites are a valid proxy for "good emails" | Labels are systematically biased toward Claude's voice, not Diwas's |
| A2 | Noman's framework is complete and stable (won't change) | Model learns a framework that is later deprecated |
| A3 | Marketing and accounting ICPs share enough structural overlap that the model can generalize from one to the other | OOD performance on accounting leads collapses |
| A4 | In-production reply rate is a reliable signal of model quality | Confounded by list quality, timing, economic conditions, subject line alone |
| A5 | 48 ± clean samples are sufficient for LoRA to absorb the stylistic pattern | Model memorizes examples instead of learning the generalization |
| A6 | The pain point and personalization angle in Y are independently meaningful signals, not just ornamental reasoning | Loss on these fields does not propagate useful gradient |
| A7 | Human review by Diwas is consistent (same rubric applied to record 1 and record 48) | Label drift introduces noise that the model cannot escape |
| A8 | The base model (Qwen2.5-3B / Llama3.2-3B) has sufficient prior knowledge of B2B language | Fine-tuning does not start from a cold start on domain vocabulary |

---

### 1.2 Mathematical Formulation of the System

Let the full dataset be:

$$\mathcal{D} = \{(x_i,\, y_i)\}_{i=1}^{N}, \quad N \approx 48$$

where each example is:

$$x_i = \bigl[\,\text{website\_copy}_i,\; \text{linkedin\_headline}_i,\; \text{linkedin\_about}_i,\; \text{linkedin\_posts}_i,\; \text{linkedin\_comments}_i\,\bigr]$$

$$y_i = \bigl\{\,\underbrace{\text{pain\_point}_i}_{\text{diagnostic}},\; \underbrace{\text{personalization\_angle}_i}_{\text{evidence trace}},\; \underbrace{\text{subject}_i}_{\text{hook}},\; \underbrace{\text{body}_i}_{\text{message}}\,\bigr\}$$

**Label generation (teacher pass):** The candidate label is produced by a teacher model $\mathcal{T}$ (Claude Sonnet) conditioned on a fixed style policy $\pi$ (Noman's framework):

$$\tilde{y}_i = \mathcal{T}(x_i \mid \pi)$$

**Human gate:** Diwas applies a review function $H$ over the candidate:

$$y_i = H(\tilde{y}_i) \in \{\tilde{y}_i,\; \hat{y}_i^{\text{edit}},\; \emptyset\}$$

where $\emptyset$ denotes rejection (record dropped from $\mathcal{D}$).

**Fine-tuning objective:** We minimize the standard autoregressive cross-entropy over all tokens in the output:

$$\theta^* = \arg\min_{\theta} \; \mathcal{L}(\theta;\, \mathcal{D}) = -\sum_{i=1}^{N} \sum_{t=1}^{|y_i|} \log P_\theta\!\left(y_i^{(t)} \;\middle|\; x_i,\; \pi,\; y_i^{(<t)}\right)$$

**LoRA constraint:** We do not update the full parameter matrix $W$. Instead, we learn low-rank residuals:

$$W' = W + \Delta W = W + \frac{\alpha}{r} \cdot B A, \quad A \in \mathbb{R}^{r \times d},\; B \in \mathbb{R}^{d \times r},\; r \ll d$$

**In-production evaluation signal:** Let future emails be indexed by $t \in \{1, 2, \ldots, T\}$. For each, Diwas records:

$$r_t \in \{0, 1\} \quad \text{(reply received or not)}$$
$$q_t \in \{-1, 0, 1\} \quad \text{(Diwas's editorial judgment: reject / passable / good)}$$

The POC is validated when both of the following hold over a window of $T \geq 30$ future sends:

$$\hat{R}_{\text{model}} = \frac{1}{T}\sum_{t=1}^{T} r_t \;\geq\; \hat{R}_{\text{manual}} \quad \text{(reply rate parity)}$$

$$\hat{Q}_{\text{model}} = \frac{1}{T}\sum_{t=1}^{T} \mathbf{1}[q_t \geq 0] \;\geq\; 0.75 \quad \text{(75\% of drafts need no major rewrite)}$$

---

## 2. Failure Modes — Known & Unknown Framework

The framework has four quadrants. We populate all four.

---

### Quadrant I — Known Knowns
*Things we know, and we know we know them.*

| ID | Failure Mode | Why We Know It | Mitigation |
|----|-------------|---------------|------------|
| KK-1 | Dataset is too small for reliable SFT | Empirical SFT literature: <80 samples is below the reliable floor | Accept the risk; treat this as a POC, not a production model |
| KK-2 | Label noise from inconsistent human review | Diwas reviews 48 records across multiple sessions; rubric drift is likely | Write a fixed review rubric before review begins; date-stamp each review session |
| KK-3 | Model mimics Claude's voice, not Diwas's | Teacher labels are Claude outputs; the model learns Claude-style prose | Diwas must edit at least 30% of records rather than keeping Claude output verbatim |
| KK-4 | LoRA forgetting: model loses instruction-following after fine-tune | Well-documented in LocalLLaMA community; narrow SFT causes regression | Add a 10% replay buffer of general instruction data during SFT |
| KK-5 | Reply rate is a noisy metric | Confounded by list quality, send time, deliverability, subject line | Collect editorial quality score $q_t$ alongside $r_t$; don't rely on reply rate alone |

---

### Quadrant II — Known Unknowns
*Things we know we do not know yet.*

| ID | Failure Mode | What We Don't Know | What Would Tell Us |
|----|-------------|-------------------|-------------------|
| KU-1 | Optimal LoRA rank for this task and base model | We don't know if $r=16$, $r=32$, or $r=64$ is right for this domain | Ablation study: train 3 variants, compare on first 10 in-production emails |
| KU-2 | Whether the accounting ICP transfers from the marketing training set | Structurally similar (B2B outreach) but different pain points and language register | First 14 accounting emails out of the model become the OOD validation set |
| KU-3 | Whether `pain_point_identified` and `personalization_angle` as output fields actually improve body quality vs. just predicting body directly | Chain-of-thought in Y is theoretically helpful but unverified here | Train two variants: one with CoT fields in Y, one without; compare body quality |
| KU-4 | The right base model: Qwen2.5-3B vs Llama3.2-3B vs Mistral-3B | Different base models have different priors on business language | Start with Qwen2.5-3B (better multilingual + formatting); switch if quality is poor |
| KU-5 | How many future sends are needed before the POC signal is statistically meaningful | $T=30$ is a guess; depends on baseline reply rate variance | Use a one-sided proportion test: $H_0: R_{\text{model}} = R_{\text{manual}}$; compute required $T$ once baseline $\hat{R}_{\text{manual}}$ is known |

---

### Quadrant III — Unknown Unknowns
*Things we don't know that we don't know. These are the dangerous ones.*

| ID | Potential Failure Mode | Why It's Dangerous |
|----|----------------------|-------------------|
| UU-1 | The model learns to write emails that *look* like Diwas's style but systematically miss the pain point in ways that are hard to notice without sending | A model that writes fluent, well-formatted emails gets approved; only real send data reveals it never surfaces the actual pain — by then the pipeline is in production |
| UU-2 | The fine-tune shifts the model's formatting behavior in ways that break prompt-based workflows elsewhere | LoRA adapters are layered on top; if Diwas later uses the same base model for other tasks, residual adapter effects may surface unexpectedly |
| UU-3 | Personalization signals in LinkedIn data become stale | Posts from November 2026 were signal-rich; posts from 2027 may be from different platform behavior or LinkedIn API restrictions — the training distribution drifts |
| UU-4 | A reply to an AI-written email creates a trust asymmetry: the lead expects Diwas, but the follow-up conversation is now mismatched | Not a model failure but a downstream consequence of deploying this pipeline that neither Diwas nor the model is equipped to handle at scale |
| UU-5 | The framework itself is wrong for this ICP | Noman's rules were validated on a different sender, list, and offer — they may not generalize to Diwas's specific positioning and American B2B market |

---

### Quadrant IV — Unknown Knowns
*Things we implicitly know but have not made explicit — tacit assumptions that could silently break.*

| ID | Tacit Knowledge at Risk |
|----|------------------------|
| UK-1 | Diwas's read of a "good email" is internally consistent — but it has never been written down as a rubric, only internalized. If this tacit standard shifts, the entire label set becomes incomparable |
| UK-2 | The outreach is for Diwas's specific service offer (GTM AI Engineering / AI agents for agencies). This is baked into every email but never stated as a formal prior in the system prompt. If the offer changes, every label becomes wrong |
| UK-3 | "American businesses" implies a cultural register (directness, low-context, ROI-first framing). This is never stated explicitly in the training data or the system prompt — it's tacit |

---

## 3. Considerations

| Priority | Consideration |
|----------|--------------|
| 🔴 Critical | Before labeling begins, write Diwas's service offer description as a fixed string. It becomes part of every $x_i$ and the system prompt. |
| 🔴 Critical | Establish a 1-page review rubric before human review. This prevents label drift across sessions. |
| 🟠 High | The pain point and personalization angle in $y_i$ must be verified independently of the email body — they are diagnostic, not decorative. |
| 🟠 High | Track whether Diwas keeps, edits, or rejects each Claude draft, and in what ratio. If >80% are kept verbatim, the model is learning Claude, not Diwas. |
| 🟡 Medium | The POC evaluation window ($T \geq 30$) must include enough time for replies to come in — budget at least 2–3 weeks of active sending before claiming results. |
| 🟡 Medium | The accounting ICP dataset (14 leads) should not be labeled by Claude first — Diwas should write those himself to introduce genuine voice diversity. |
| 🟢 Low | LoRA rank and hyperparameters are secondary to data quality. Do not optimize them until at least 60 clean samples exist. |

---

## 4. Research Clusters

These are the open research questions that must be answered to move from POC to a defensible, scalable system. They are organized using the X/Y (Known/Unknown) framework.

---

### Research Cluster 1 — Data Quality & Label Validity
**Core question: How do we know the labels (Y) are right?**

| Sub-question | Known (X) | Unknown (Y) |
|-------------|-----------|-------------|
| Are Claude-generated rewrites valid training labels? | Claude can follow Noman's rules syntactically | Whether Claude captures Diwas's specific positioning instinct |
| Does human editing actually improve label quality or just introduce noise? | Human review exists as a step | No rubric for what constitutes a "correct" edit |
| How consistent is Diwas's review judgment across the full dataset? | 48 records reviewed by one person | Inter-rater reliability is unmeasurable with one rater |
| Is $N=48$ enough for LoRA to generalize vs. memorize? | SFT literature suggests ~80–150 for reliable generalization | Exact threshold for this task, base model, and domain |

**Research direction:** Few-shot SFT data efficiency literature (Alpaca, LIMA "Less Is More for Alignment"). LIMA (Zhou et al., 2023) showed 1,000 carefully curated samples match 52K noisy ones — quality over quantity is the right prior. The question is whether 48 high-quality samples is above the meaningful floor.

---

### Research Cluster 2 — Bias & Distribution
**Core question: How do we ensure the model is not biased toward the wrong things?**

| Sub-question | Known (X) | Unknown (Y) |
|-------------|-----------|-------------|
| Is there systematic bias in what LinkedIn/website data the pipeline captures? | Leads with richer LinkedIn profiles will produce better $x_i$ features | Whether sparse profiles (like Rodrigo Timaure's — no About section) systematically produce worse outputs |
| Does the model learn Diwas's voice or Claude's voice? | Labels are Claude-generated by default | Degree of stylistic drift without sufficient Diwas-edited samples |
| Are American business cultural norms implicit in the training data? | The leads are US-based companies | Whether the base model's prior knowledge of American B2B writing is sufficient or if it needs explicit conditioning |
| Does the marketing ICP bias the model against the accounting ICP? | Both are in the training set | Whether the model's attention mechanism gives disproportionate weight to whichever ICP has more samples |

**Research direction:** Dataset cartography (Swayamdipta et al., 2020) — mapping training examples by confidence and variability to identify easy, ambiguous, and hard-to-learn samples. For a 48-sample dataset, this can be done manually during the review process.

---

### Research Cluster 3 — Evaluation & Ground Truth
**Core question: How do we know the model has learned the right thing, without a held-out test set?**

| Sub-question | Known (X) | Unknown (Y) |
|-------------|-----------|-------------|
| What does "a good email" mean, formally? | Noman's 22 rules exist | Whether those rules are sufficient as a formal specification or whether they miss important implicit criteria |
| Is reply rate a valid proxy for email quality? | It is the ultimate business signal | Heavily confounded; a great email to a cold lead may never get a reply; a mediocre email to a warm lead may get one |
| Can LLM-as-judge (Claude evaluating the fine-tuned model's output) measure what matters? | LLM-as-judge is an established technique | Whether Claude can judge "Diwas-ness" — his specific voice, offer, and positioning instinct |
| How many future sends constitute a statistically valid POC window? | We will collect $r_t$ and $q_t$ on future sends | The variance of $R_{\text{manual}}$ (Diwas's current reply rate), without which we cannot compute required $T$ |

**Research direction:** The evaluation problem here is a known open problem in generative AI — there is no perfect automatic metric for email quality. The closest validated approaches are: (1) human preference evaluation (blind A/B), (2) LLM-as-judge with a detailed rubric, and (3) downstream task metrics (reply rate). All three should be tracked.

---

### Research Cluster 4 — Generalization & OOD Robustness
**Core question: Does the model generalize to new leads, new ICPs, and new offers?**

| Sub-question | Known (X) | Unknown (Y) |
|-------------|-----------|-------------|
| Will the model generalize from marketing agencies to accounting firms? | Both are B2B service businesses | Whether the stylistic pattern transfers or whether ICP-specific vocabulary is load-bearing |
| What happens when Diwas's offer changes? | The offer is baked into the system prompt | Whether the model's weights encode the current offer in a way that resists system prompt override |
| Can the model handle leads with sparse context (no About section, no posts)? | Some leads in the dataset have minimal LinkedIn data | Model behavior on low-information $x_i$ — does it hallucinate specifics or appropriately hedge? |
| Is there a point of diminishing returns on context length in $x_i$? | Longer context = more signal, but also more noise | Optimal context window for lead features; whether summarizing $x_i$ before the model sees it would improve output quality |

**Research direction:** Domain adaptation in SFT — whether a model fine-tuned on a narrow ICP can be prompted (zero-shot) to a new ICP without retraining, or whether ICP-specific LoRA adapters are needed for each vertical Diwas targets.

---

## 5. Open Decisions (Not Yet Made)

These require Diwas's explicit decision before the pipeline is built:

- [ ] **What is Diwas's current manual reply rate baseline?** This is the denominator for the POC metric.
- [ ] **What percentage of Claude drafts should Diwas edit (minimum)?** Recommendation: at least 40%.
- [ ] **Is the accounting ICP dataset labeled by Claude or by Diwas first-pass?**
- [ ] **What is Diwas's service offer description in one paragraph?** (Needed as a fixed prior in every X.)

---

*This ADR is a living document. Update it as decisions are made and new failure modes are discovered.*

~