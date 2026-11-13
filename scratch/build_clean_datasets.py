"""
Complete dataset transformation, anonymization, and expansion script.
Produces:
- data/accounting.json (14 leads)
- data/marketing.json (88 leads)
- data/contact/contact.json (102 contacts)
- data/updated/accounting_update.json (14 candidate decompositions)
- data/updated/marketing_update.json (88 candidate decompositions)
- artifacts/decisions.json (102 records, 9 reviewed, 93 needs-review, partitioned)
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

SCRATCH_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRATCH_DIR))

from generate_54_leads import get_54_synthetic_leads
from mappings import ACCOUNTING_MAPPINGS, MARKETING_MAPPINGS

REPO_ROOT = Path(r"c:\Users\diwas\OneDrive\Documents\slm-2")
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

def canonical_hash(d: dict) -> str:
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def scrub_pii(text: str) -> str:
    if not isinstance(text, str):
        return text
    # RFC 2606 email scrub: any email not already ending with .example or example.com
    def replace_email(match):
        e = match.group(0)
        if e.endswith('.example') or e.endswith('example.com'):
            return e
        return 'contact@company.example'
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', replace_email, text)
    # Phone scrub to 555
    text = re.sub(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '+1-555-0199', text)
    # Specific reviewer credentials / emails
    text = re.sub(r'diwas\.devs@gmail\.com[^\.\n]*', 'verified system ingest', text, flags=re.IGNORECASE)
    text = re.sub(r'diwaspathak26[^\.\n]*', 'system_ingest', text, flags=re.IGNORECASE)
    text = re.sub(r'Prakriti Pathak', 'Synthetic Auditor', text, flags=re.IGNORECASE)
    return text

def main():
    print("Starting dataset transformation...")
    
    # 1. Load original accounting (base 14)
    with open(DATA_DIR / "accounting.json", "r", encoding="utf-8") as f:
        orig_acc = json.load(f)[:14]
    with open(DATA_DIR / "updated" / "accounting_update.json", "r", encoding="utf-8") as f:
        orig_acc_upd = json.load(f)

    # 2. Load original marketing (base 34)
    with open(DATA_DIR / "marketing.json", "r", encoding="utf-8") as f:
        orig_mkt = json.load(f)[:34]
    with open(DATA_DIR / "updated" / "marketing_update.json", "r", encoding="utf-8") as f:
        orig_mkt_upd = json.load(f)

    # Mappings loaded from mappings.py

    acc_map_by_name = {}
    for m in ACCOUNTING_MAPPINGS:
        acc_map_by_name[m["old_name"]] = m
        acc_map_by_name[m["new_name"]] = m

    mkt_map_by_name = {}
    for m in MARKETING_MAPPINGS:
        mkt_map_by_name[m["old_name"]] = m
        mkt_map_by_name[m["new_name"]] = m

    # Transform accounting leads
    clean_acc = []
    clean_acc_upd = {}
    clean_contacts = []

    for item in orig_acc:
        old_name = item.get("name")
        old_email = item.get("email")
        mapping = acc_map_by_name.get(old_name, {
            "new_name": "Jordan Vance",
            "new_email": "jordan.vance@accounting-firm.example",
            "new_company": "Vance Advisory LLP",
            "new_website": "https://vance-advisory.example",
            "new_linkedin": "https://www.linkedin.com/in/jordan-vance-cpa",
        })

        new_name = mapping["new_name"]
        new_email = mapping["new_email"]
        new_company = mapping["new_company"]
        new_website = mapping["new_website"]
        new_linkedin = mapping["new_linkedin"]

        lead = dict(item)
        lead["name"] = new_name
        lead["email"] = new_email
        lead["company"] = new_company
        lead["website"] = new_website
        lead["linkedin"] = new_linkedin

        if "email_source" in lead:
            lead["email_source"] = scrub_pii(lead["email_source"])
        
        # Scrub lead context
        ctx = dict(lead.get("lead_context", {}))
        for k, v in ctx.items():
            if isinstance(v, str):
                v_clean = scrub_pii(v)
                v_clean = v_clean.replace(old_name, new_name)
                v_clean = v_clean.replace(old_name.split()[0], new_name.split()[0])
                if item.get("company"):
                    v_clean = v_clean.replace(item["company"], new_company)
                ctx[k] = v_clean
            elif isinstance(v, dict):
                clean_sub = {}
                for sk, sv in v.items():
                    if isinstance(sv, str):
                        clean_sv = scrub_pii(sv)
                        clean_sv = clean_sv.replace(old_name, new_name)
                        clean_sv = clean_sv.replace(old_name.split()[0], new_name.split()[0])
                        clean_sub[sk] = clean_sv
                    else:
                        clean_sub[sk] = sv
                ctx[k] = clean_sub
        lead["lead_context"] = ctx

        # Scrub output_email
        out_mail = dict(lead.get("output_email", {}))
        if "body" in out_mail:
            body = scrub_pii(out_mail["body"])
            body = body.replace(f"Hi {old_name.split()[0]}", f"Hi {new_name.split()[0]}")
            body = body.replace(old_name, new_name)
            out_mail["body"] = body
        lead["output_email"] = out_mail
        clean_acc.append(lead)

        # Contact
        clean_contacts.append({
            "name": new_name,
            "company": new_company,
            "email": new_email,
            "linkedin": new_linkedin,
            "website": new_website,
        })

        # Candidate update
        if old_email in orig_acc_upd:
            cand = dict(orig_acc_upd[old_email])
            c_body = scrub_pii(cand.get("body", ""))
            c_body = c_body.replace(f"{old_name.split()[0]},", f"{new_name.split()[0]},")
            c_body = c_body.replace(old_name, new_name)
            c_subj = cand.get("subject", "").replace(old_name.split()[0], new_name.split()[0])
            cand["body"] = c_body
            cand["subject"] = c_subj
            clean_acc_upd[new_email] = cand

    print(f"Transformed {len(clean_acc)} accounting leads.")

    # Transform 34 marketing leads
    clean_mkt = []
    clean_mkt_upd = {}
    reviewed_status_map = {}

    for item in orig_mkt:
        old_name = item.get("name")
        old_email = item.get("email")
        mapping = mkt_map_by_name.get(old_name, {
            "new_name": "Taylor Morgan",
            "new_email": "t.morgan@marketing-agency.example",
            "new_company": "Morgan Digital Agency",
            "new_website": "https://morgan-digital.example",
            "new_linkedin": "https://www.linkedin.com/in/taylor-morgan-agency",
        })

        new_name = mapping["new_name"]
        new_email = mapping["new_email"]
        new_company = mapping["new_company"]
        new_website = mapping["new_website"]
        new_linkedin = mapping["new_linkedin"]

        lead = dict(item)
        lead["name"] = new_name
        lead["email"] = new_email
        lead["company"] = new_company
        lead["website"] = new_website
        lead["linkedin"] = new_linkedin

        if "email_source" in lead:
            lead["email_source"] = scrub_pii(lead["email_source"])
        
        # Scrub lead context
        ctx = dict(lead.get("lead_context", {}))
        for k, v in ctx.items():
            if isinstance(v, str):
                v_clean = scrub_pii(v)
                v_clean = v_clean.replace(old_name, new_name)
                v_clean = v_clean.replace(old_name.split()[0], new_name.split()[0])
                if item.get("company"):
                    v_clean = v_clean.replace(item["company"], new_company)
                ctx[k] = v_clean
        lead["lead_context"] = ctx

        # Scrub output_email
        out_mail = dict(lead.get("output_email", {}))
        if "body" in out_mail:
            body = scrub_pii(out_mail["body"])
            body = body.replace(f"Hi {old_name.split()[0]}", f"Hi {new_name.split()[0]}")
            body = body.replace(f"{old_name.split()[0]},", f"{new_name.split()[0]},")
            body = body.replace(old_name, new_name)
            out_mail["body"] = body
        lead["output_email"] = out_mail
        clean_mkt.append(lead)

        clean_contacts.append({
            "name": new_name,
            "company": new_company,
            "email": new_email,
            "linkedin": new_linkedin,
            "website": new_website,
        })

        # Candidate update
        if old_email in orig_mkt_upd:
            cand = dict(orig_mkt_upd[old_email])
            c_body = scrub_pii(cand.get("body", ""))
            c_body = c_body.replace(f"{old_name.split()[0]},", f"{new_name.split()[0]},")
            c_body = c_body.replace(old_name, new_name)
            c_subj = cand.get("subject", "").replace(old_name.split()[0], new_name.split()[0])
            cand["body"] = c_body
            cand["subject"] = c_subj
            clean_mkt_upd[new_email] = cand

        if "reviewed_state" in mapping:
            reviewed_status_map[new_email] = mapping["reviewed_state"]

    print(f"Transformed {len(clean_mkt)} original marketing leads. Reviewed count: {len(reviewed_status_map)}")

    # 3. Append 54 new synthetic marketing agencies
    new_54 = get_54_synthetic_leads()
    for item in new_54:
        name = item["name"]
        email = item["email"]
        company = item["company"]
        website = item["website"]
        linkedin = item["linkedin"]
        job_title = item["job_title"]
        niche = item["niche"]
        pain_point = item["pain_point"]
        personalization_angle = item["personalization_angle"]
        subject = item["subject"]
        body = item["body"]

        lead = {
            "name": name,
            "email": email,
            "company": company,
            "website": website,
            "linkedin": linkedin,
            "job_title": job_title,
            "lead_context": {
                "website_copy": f"{company} is a premier {niche} agency serving enterprise brands and high-growth venture-backed companies. Our focus: engineering predictable pipeline and removing technical delivery bottlenecks. {personalization_angle}",
                "website_source": f"Homepage ({website}) & Case Studies",
                "linkedin_headline": f"{job_title} at {company} | {niche}",
                "linkedin_about": f"Leading {company}. We partner with B2B executives to eliminate operational friction and scale customer acquisition systems.",
                "client_verticals": ["B2B SaaS", "Enterprise Software", "Growth Tech", "Direct-to-Consumer"],
            },
            "output_email": {
                "subject": subject,
                "body": body,
            }
        }
        clean_mkt.append(lead)

        clean_contacts.append({
            "name": name,
            "company": company,
            "email": email,
            "linkedin": linkedin,
            "website": website,
        })

        clean_mkt_upd[email] = {
            "pain_point": pain_point,
            "personalization_angle": personalization_angle,
            "subject": subject,
            "body": body,
        }

    print(f"Total marketing leads: {len(clean_mkt)} (34 original + 54 new). Total leads: {len(clean_acc) + len(clean_mkt)}")
    assert len(clean_acc) == 14
    assert len(clean_mkt) == 88
    assert len(clean_contacts) == 102
    assert len(clean_acc_upd) == 14
    assert len(clean_mkt_upd) == 88

    # Write out data files
    with open(DATA_DIR / "accounting.json", "w", encoding="utf-8") as f:
        json.dump(clean_acc, f, indent=2)
    with open(DATA_DIR / "marketing.json", "w", encoding="utf-8") as f:
        json.dump(clean_mkt, f, indent=2)
    with open(DATA_DIR / "contact" / "contact.json", "w", encoding="utf-8") as f:
        json.dump(clean_contacts, f, indent=2)
    with open(DATA_DIR / "updated" / "accounting_update.json", "w", encoding="utf-8") as f:
        json.dump(clean_acc_upd, f, indent=2)
    with open(DATA_DIR / "updated" / "marketing_update.json", "w", encoding="utf-8") as f:
        json.dump(clean_mkt_upd, f, indent=2)

    print("Wrote clean datasets and contact directory.")

    # 4. Generate decisions and partition train / val / test (80 / 10 / 10)
    # Accounting: 14 total -> 11 train, 2 val, 1 test
    # Marketing: 88 total -> 71 train, 8 val, 9 test
    # Total: 102 total -> 82 train, 10 val, 10 test
    
    # Compute deterministic record IDs
    acc_records = []
    for idx, item in enumerate(clean_acc):
        item_hash = canonical_hash(item)
        rec_id = f"REC-accounting-{item_hash[:12]}"
        acc_records.append({
            "rec_id": rec_id,
            "sector": "accounting",
            "email": item["email"],
            "hash": item_hash,
            "source_file": "data/accounting.json",
            "candidate": clean_acc_upd[item["email"]],
        })

    mkt_records = []
    for idx, item in enumerate(clean_mkt):
        item_hash = canonical_hash(item)
        rec_id = f"REC-marketing-{item_hash[:12]}"
        mkt_records.append({
            "rec_id": rec_id,
            "sector": "marketing",
            "email": item["email"],
            "hash": item_hash,
            "source_file": "data/marketing.json",
            "candidate": clean_mkt_upd[item["email"]],
        })

    # Partition assignment:
    # Reviewed leads MUST go to Train
    train_ids = set()
    val_ids = set()
    test_ids = set()

    # Accounting (14 leads):
    # 0..10 -> train (11), 11..12 -> val (2), 13 -> test (1)
    for idx, r in enumerate(acc_records):
        if idx < 11:
            train_ids.add(r["rec_id"])
        elif idx < 13:
            val_ids.add(r["rec_id"])
        else:
            test_ids.add(r["rec_id"])

    # Marketing (88 leads):
    # Put the 9 reviewed leads in train first
    reviewed_rec_ids = [r["rec_id"] for r in mkt_records if r["email"] in reviewed_status_map]
    for rid in reviewed_rec_ids:
        train_ids.add(rid)

    unassigned_mkt = [r for r in mkt_records if r["rec_id"] not in train_ids]
    # We need 71 train total in marketing (currently 9, need 62 more)
    # We need 8 val in marketing
    # We need 9 test in marketing
    # Total = 9 + 62 + 8 + 9 = 88.
    for idx, r in enumerate(unassigned_mkt):
        if idx < 62:
            train_ids.add(r["rec_id"])
        elif idx < 62 + 8:
            val_ids.add(r["rec_id"])
        else:
            test_ids.add(r["rec_id"])

    print(f"Partition counts: Train={len(train_ids)}, Val={len(val_ids)}, Test={len(test_ids)}")
    assert len(train_ids) == 82
    assert len(val_ids) == 10
    assert len(test_ids) == 10
    assert len(train_ids.intersection(val_ids)) == 0
    assert len(train_ids.intersection(test_ids)) == 0
    assert len(val_ids.intersection(test_ids)) == 0

    # Build decisions store
    decisions = {}
    history = []
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    all_records = acc_records + mkt_records
    for r in all_records:
        rec_id = r["rec_id"]
        email = r["email"]
        part = "train" if rec_id in train_ids else ("validation" if rec_id in val_ids else "test")
        
        if email in reviewed_status_map:
            st = reviewed_status_map[email]
            reviewer = "Diwas"
            notes = "Reviewed by Diwas (custom body & hook preserved)"
        else:
            st = "needs-review"
            reviewer = None
            notes = "Enqueued for Diwas review"

        decisions[rec_id] = {
            "source_id": rec_id,
            "source_file": r["source_file"],
            "source_hash": r["hash"],
            "state": st,
            "reviewer": reviewer,
            "reviewed_at": now_iso if reviewer else None,
            "notes": notes,
            "partition": part,
            "labels": {
                "pain_point": r["candidate"]["pain_point"],
                "personalization_angle": r["candidate"]["personalization_angle"],
                "subject": r["candidate"]["subject"],
                "body": r["candidate"]["body"],
            }
        }
        history.append({
            "source_id": rec_id,
            "from_state": "proposed",
            "to_state": st,
            "reviewer": reviewer or "system",
            "timestamp": now_iso,
            "notes": notes,
        })

    decisions_store = {
        "version": "1.1.0",
        "description": "ADR-001 verifiable human decision store (PII-free, 102 leads, 80/10/10 split)",
        "decisions": decisions,
        "history": history,
    }

    with open(ARTIFACTS_DIR / "decisions.json", "w", encoding="utf-8") as f:
        json.dump(decisions_store, f, indent=2)

    print("Successfully wrote artifacts/decisions.json.")
    print(f"Total decisions: {len(decisions)}.")
    rev_count = sum(1 for d in decisions.values() if d["state"] in ("revised", "accepted"))
    print(f"Reviewed count: {rev_count}, Pending count: {len(decisions) - rev_count}")

if __name__ == "__main__":
    main()
