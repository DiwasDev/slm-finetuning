"""
Claude teacher candidate label generation interface and trace preservation.
Conditions decomposition on Noman's 22-rule framework and lead context.
Uses standard library only (Ponytail: stdlib first).
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent))
from schema import validate_label_taxonomy, validate_provenance

DEFAULT_TEACHER_MODEL = "claude-sonnet-4-6"

NOMAN_FRAMEWORK_POLICY = """
Noman's 22-Rule Framework Summary:
1. One pain point only.
2. Low-friction direct question.
3. No fake pleasantries ('Hope you are doing well').
4. Evidence-backed personalization angle directly cited from prospect context.
5. Short, conversational, low-context American B2B register.
6. Pain point is diagnostic of a manual/repetitive leak in operations.
7. Clear distinction between diagnostic pain, evidence angle, hook subject, and message body.
"""

DIWAS_SERVICE_OFFER = (
    "GTM AI Engineer building AI agent workflows and automation for agencies and "
    "service firms to eliminate repetitive manual operations, saving time and recoverable profits."
)


def build_teacher_prompt(lead: dict[str, Any]) -> str:
    """Build the conditioned teacher prompt for Claude Sonnet decomposition pass."""
    context = lead.get("lead_context", {})
    posts = context.get("linkedin_posts", {})
    post_text = " ".join(
        p.get("text", "") for p in posts.values() if isinstance(p, dict)
    )[:1000]

    prompt = f"""You are Claude Sonnet acting as the Teacher Model for an SLM Cold-Outreach fine-tuning pipeline.
Sender Positioning: {DIWAS_SERVICE_OFFER}
Style Policy: {NOMAN_FRAMEWORK_POLICY}

Prospect Context:
- Name: {lead.get('name', 'Prospect')}
- Company: {lead.get('company', 'Unknown')}
- Sector: {lead.get('sector', 'B2B')}
- Website Summary: {str(context.get('website_copy', ''))[:800]}
- LinkedIn Headline: {context.get('linkedin_headline', '')}
- LinkedIn About: {str(context.get('linkedin_about', ''))[:500]}
- Recent Posts: {post_text}

Task: Decompose and formulate a cold outreach email candidate strictly into this 4-field JSON format:
{{
  "pain_point": "<Single diagnostic operational pain / time-profit leak>",
  "personalization_angle": "<Specific verifiable hook from their website or LinkedIn>",
  "subject": "<Low-friction, pattern-interrupt subject line without cheesy emojis>",
  "body": "<Body copy strictly following Noman's rules, signed off with 'Regards,\\nDiwas'>"
}}
Output strictly valid JSON and nothing else.
"""
    return prompt.strip()


def extract_candidate_from_teacher_output(raw_text: str) -> dict[str, str]:
    """Parse JSON payload from raw teacher output."""
    raw_text = raw_text.strip()
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        raise ValueError("No JSON object found in teacher response")
    
    parsed = json.loads(match.group(0))
    ok, err = validate_label_taxonomy(parsed)
    if not ok:
        raise ValueError(f"Teacher output failed taxonomy validation: {err}")
    return parsed


def generate_candidate_record(
    lead: dict[str, Any],
    teacher_output: str | dict[str, str] | None = None,
    teacher_model: str = DEFAULT_TEACHER_MODEL,
) -> dict[str, Any]:
    """
    Generate a verifiable teacher candidate record binding raw lead context,
    teacher traces, and validated 4-field labels in 'proposed' state.
    """
    prov_ok, prov_err = validate_provenance(lead)
    if not prov_ok:
        raise ValueError(f"Invalid lead provenance: {prov_err}")

    prompt = build_teacher_prompt(lead)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    if teacher_output is None:
        # Heuristic teacher fallback using raw email if already present in dataset
        raw_email = lead.get("raw_output_email", {})
        raw_subject = raw_email.get("subject", "Quick question")
        raw_body = raw_email.get("body", "")
        
        # Decompose from raw body and headline context
        company = lead.get("company", "your firm")
        labels = {
            "pain_point": f"Manual repetitive processes leaking time and profits at {company}",
            "personalization_angle": (
                lead.get("lead_context", {}).get("linkedin_headline")
                or f"Operations at {company}"
            ),
            "subject": raw_subject,
            "body": raw_body or f"Hey {lead.get('name', '')},\n\nNoticed {company} handles extensive client work...",
        }
        raw_response_text = json.dumps(labels, indent=2)
    elif isinstance(teacher_output, dict):
        ok, err = validate_label_taxonomy(teacher_output)
        if not ok:
            raise ValueError(f"Teacher output dictionary failed schema: {err}")
        labels = teacher_output
        raw_response_text = json.dumps(labels, indent=2)
    else:
        labels = extract_candidate_from_teacher_output(teacher_output)
        raw_response_text = str(teacher_output)

    candidate_record = {
        "candidate_id": f"CAND-{lead['source_id'].replace('REC-', '')}",
        "source_id": lead["source_id"],
        "source_file": lead["source_file"],
        "source_hash": lead["source_hash"],
        "state": "proposed",
        "labels": labels,
        "teacher_trace": {
            "model": teacher_model,
            "prompt_hash": prompt_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "raw_response": raw_response_text,
        },
    }

    return candidate_record

