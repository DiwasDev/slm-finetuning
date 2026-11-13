"""
Streamlit Review Dashboard for Diwas.
Run: streamlit run streamlit_app.py
(Requires: pip install streamlit)
"""

import json
import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import streamlit as st
    import streamlit.components.v1 as components
except ImportError:
    print("Streamlit is not installed in this environment.")
    print("To install: pip install streamlit")
    print("Or run the zero-dependency built-in dashboard: python app.py")
    sys.exit(1)

from decision import init_decision_store
from review_cli import get_all_review_items, apply_review_decision
from export import export_slm_dataset
from audit import audit_exported_dataset

st.set_page_config(
    page_title="EmailSLM Review Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ EmailSLM — Editorial Review Dashboard")
st.caption("ADR-001 Rubric Verification &bull; Reviewer: Diwas &bull; 102 leads · 80/10/10 split")

store = init_decision_store()
all_leads = get_all_review_items(store)
total = len(all_leads)
reviewed_leads = [l for l in all_leads if l["state"] in {"revised", "accepted", "rejected", "uncertain"}]
reviewed_count = len(reviewed_leads)
pct = int((reviewed_count / total) * 100) if total else 0

# Sidebar metrics
st.sidebar.header("Review Progress")
st.sidebar.metric(label="Reviewed Leads", value=f"{reviewed_count} / {total}", delta=f"{pct}% Complete")
st.sidebar.progress(pct / 100)

# Partition summary
dec_store = store.get("decisions", {})
part_counts: dict[str, dict[str, int]] = {}
for d in dec_store.values():
    p = d.get("partition", "unknown")
    s = d.get("state", "unknown")
    part_counts.setdefault(p, {})
    part_counts[p][s] = part_counts[p].get(s, 0) + 1

with st.sidebar.expander("📊 Partition Summary", expanded=False):
    for p in ("train", "validation", "test"):
        sc = part_counts.get(p, {})
        done = sc.get("revised", 0) + sc.get("accepted", 0)
        total_p = sum(sc.values())
        st.caption(f"**{p.upper()}** — {total_p} leads | {done} reviewed")

if "status_filter_key" not in st.session_state:
    st.session_state["status_filter_key"] = "All"

status_filter = st.sidebar.selectbox(
    "Filter by Status",
    ["All", "needs-review", "revised", "accepted", "rejected", "uncertain"],
    key="status_filter_key",
)

sector_filter = st.sidebar.selectbox(
    "Filter by Sector",
    ["All", "marketing", "accounting"],
)

partition_filter = st.sidebar.selectbox(
    "Filter by Partition",
    ["All", "train", "validation", "test"],
)

# Merge partition info into leads list
dec_map = store.get("decisions", {})
for lead in all_leads:
    sid = lead["source_id"]
    lead["partition"] = dec_map.get(sid, {}).get("partition", "train")

filtered_leads = [
    l for l in all_leads
    if (status_filter == "All" or l["state"] == status_filter)
    and (sector_filter == "All" or l["sector"] == sector_filter)
    and (partition_filter == "All" or l.get("partition") == partition_filter)
]

all_lead_ids = [l["source_id"] for l in all_leads]
filtered_ids = [l["source_id"] for l in filtered_leads]

if not filtered_leads:
    if reviewed_count == total and total > 0:
        st.balloons()
        st.success(f"🎉 **Review Complete! All {total} leads have been reviewed by Diwas.**")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Revised", sum(1 for l in all_leads if l["state"] == "revised"))
        col_s2.metric("Accepted", sum(1 for l in all_leads if l["state"] == "accepted"))
        col_s3.metric("Rejected", sum(1 for l in all_leads if l["state"] == "rejected"))
        col_s4.metric("Approved for Training", sum(1 for l in all_leads if l["state"] in {"revised", "accepted"}))
        st.info("To inspect any reviewed lead, change **Filter by Status** in the sidebar to **All** or **revised**.")
        if st.button("👁️ View All Reviewed Leads"):
            st.session_state["status_filter_key"] = "All"
            st.session_state["selected_id"] = all_lead_ids[0]
            st.rerun()
    else:
        st.info("No leads match the selected filters. Try changing or clearing the sidebar filters.")
        if st.button("🔄 Reset to All Leads"):
            st.session_state["status_filter_key"] = "All"
            st.session_state["selected_id"] = all_lead_ids[0]
            st.rerun()
    st.stop()

if "selected_id" not in st.session_state or st.session_state["selected_id"] not in all_lead_ids:
    pending_in_filtered = [l["source_id"] for l in filtered_leads if l["state"] == "needs-review"]
    st.session_state["selected_id"] = pending_in_filtered[0] if pending_in_filtered else filtered_ids[0]

if st.session_state["selected_id"] not in filtered_ids:
    st.session_state["selected_id"] = filtered_ids[0]

current_idx = filtered_ids.index(st.session_state["selected_id"])

# Navigation buttons
nav_col1, nav_col2, nav_col3 = st.sidebar.columns([1, 1, 1])
with nav_col1:
    if st.button("⬅ Prev", use_container_width=True, disabled=(current_idx == 0)):
        st.session_state["selected_id"] = filtered_ids[current_idx - 1]
        st.rerun()

with nav_col2:
    if st.button("Next ➡", use_container_width=True, disabled=(current_idx >= len(filtered_ids) - 1)):
        st.session_state["selected_id"] = filtered_ids[current_idx + 1]
        st.rerun()

with nav_col3:
    pending_leads = [l["source_id"] for l in filtered_leads if l["state"] == "needs-review"]
    if st.button("⏩ Pending", use_container_width=True, disabled=(not pending_leads)):
        st.session_state["selected_id"] = pending_leads[0]
        st.rerun()

lead_label_map = {
    l["source_id"]: f"[{l['state'].upper()}] {l['name']} ({l['company'] or l['sector']})"
    for l in filtered_leads
}

def on_select_lead():
    st.session_state["selected_id"] = st.session_state["lead_selector_key"]

st.sidebar.selectbox(
    "Select Prospect Lead",
    options=filtered_ids,
    format_func=lambda sid: lead_label_map.get(sid, sid),
    index=current_idx,
    key="lead_selector_key",
    on_change=on_select_lead,
)

lead = next(l for l in all_leads if l["source_id"] == st.session_state["selected_id"])

# ── Main workspace ──────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"{lead['name']} &bull; {lead['company'] or 'N/A'}")
    state_color = {
        "revised": "blue",
        "accepted": "green",
        "rejected": "red",
        "uncertain": "orange",
        "needs-review": "gray",
    }.get(lead["state"], "gray")
    part = lead.get("partition", "train")
    part_badge = {"train": "🟢 TRAIN", "validation": "🟡 VAL", "test": "🔴 TEST"}.get(part, part.upper())
    st.markdown(
        f"ID: `{lead['source_id']}` &bull; Sector: `{lead['sector'].upper()}` "
        f"&bull; Status: :{state_color}[**{lead['state'].upper()}**] "
        f"&bull; Partition: **{part_badge}**"
    )

with col2:
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if lead.get("linkedin") and lead["linkedin"] != "N/A":
            st.link_button("🔗 LinkedIn Profile", lead["linkedin"], use_container_width=True)
        else:
            st.button("🔗 No LinkedIn", disabled=True, use_container_width=True)
    with btn_col2:
        if lead.get("website") and lead["website"] != "N/A":
            url = lead["website"]
            if not url.startswith("http"):
                url = "https://" + url
            st.link_button("🌐 Company Website", url, use_container_width=True)
        else:
            st.button("🌐 No Website", disabled=True, use_container_width=True)

st.markdown("---")

labels = lead["labels"]

st.markdown("### 4-Field Label Taxonomy Editor")

new_pain = st.text_area(
    "1. Diagnostic Operational Pain Point",
    value=labels.get("pain_point", ""),
    key=f"pain_{lead['source_id']}",
    help="Must identify a real operational bottleneck or time/profit leak.",
)

new_angle = st.text_area(
    "2. Personalization Angle (Evidence Trace)",
    value=labels.get("personalization_angle", ""),
    key=f"angle_{lead['source_id']}",
    help="Specific verifiable citation from LinkedIn post or website copy.",
)

new_subject = st.text_input(
    "3. Pattern-Interrupt Hook Subject",
    value=labels.get("subject", ""),
    key=f"subject_{lead['source_id']}",
    help="Adhering strictly to Noman's 22 rules.",
)

new_body = st.text_area(
    "4. Email Message Body",
    value=labels.get("body", ""),
    height=200,
    key=f"body_{lead['source_id']}",
    help="Sign-off must be 'Regards,\\nDiwas'.",
)

notes = st.text_input("Review Notes", value=lead.get("notes", ""), key=f"notes_{lead['source_id']}")

# Formatted bundle text for clipboard copying
bundle_text = f"""PROSPECT: {lead['name']} ({lead['company'] or lead['sector']})
SECTOR: {lead['sector'].upper()}
WEBSITE: {lead.get('website', 'N/A')}
LINKEDIN: {lead.get('linkedin', 'N/A')}

1. OPERATIONAL PAIN POINT:
{new_pain.strip()}

2. PERSONALIZATION ANGLE:
{new_angle.strip()}

3. SUBJECT:
{new_subject.strip()}

4. EMAIL BODY:
{new_body.strip()}
""".strip()

# Interactive One-Click Copy Button via browser clipboard API
copy_btn_html = f"""
<div style="margin: 10px 0 16px 0;">
  <button id="copyBtn" onclick="copyAllFields()" style="
    width: 100%;
    background-color: #262730;
    color: #ffffff;
    border: 1px solid #4e5166;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s ease;
    outline: none;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  " onmouseover="this.style.borderColor='#ff4b4b'; this.style.color='#ff4b4b';" onmouseout="this.style.borderColor='#4e5166'; this.style.color='#ffffff';">
    <span id="copyIcon">📋</span> <span id="copyText">Copy All to Clipboard (Pain Point + Angle + Subject + Body)</span>
  </button>
</div>
<script>
function copyAllFields() {{
  const textToCopy = {json.dumps(bundle_text)};
  navigator.clipboard.writeText(textToCopy).then(function() {{
    const btn = document.getElementById('copyBtn');
    const icon = document.getElementById('copyIcon');
    const text = document.getElementById('copyText');
    btn.style.backgroundColor = '#21c354';
    btn.style.borderColor = '#21c354';
    btn.style.color = '#ffffff';
    icon.innerText = '✅';
    text.innerText = 'Copied All to Clipboard!';
    setTimeout(function() {{
      btn.style.backgroundColor = '#262730';
      btn.style.borderColor = '#4e5166';
      btn.style.color = '#ffffff';
      icon.innerText = '📋';
      text.innerText = 'Copy All to Clipboard (Pain Point + Angle + Subject + Body)';
    }}, 2500);
  }}).catch(function(err) {{
    // Fallback for restricted iframe contexts
    const ta = document.createElement('textarea');
    ta.value = textToCopy;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    const text = document.getElementById('copyText');
    text.innerText = 'Copied to Clipboard!';
    setTimeout(function() {{
      text.innerText = 'Copy All to Clipboard (Pain Point + Angle + Subject + Body)';
    }}, 2000);
  }});
}}
</script>
"""
components.html(copy_btn_html, height=52)

with st.expander("📄 View Plain Text Copy Bundle", expanded=False):
    st.code(bundle_text, language="text")

act_col1, act_col2, act_col3, act_col4 = st.columns(4)

with act_col1:
    if st.button("✓ Accept Verbatim", use_container_width=True):
        try:
            apply_review_decision(store, lead["source_id"], "accept", reviewer="Diwas", notes=notes)
            st.success(f"✓ Accepted {lead['name']}!")
            pending_remaining = [l["source_id"] for l in all_leads if l["state"] == "needs-review" and l["source_id"] != lead["source_id"]]
            if pending_remaining:
                st.session_state["selected_id"] = pending_remaining[0]
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

with act_col2:
    if st.button("✎ Save as Revised", type="primary", use_container_width=True):
        try:
            revised_labels = {
                "pain_point": new_pain.strip(),
                "personalization_angle": new_angle.strip(),
                "subject": new_subject.strip(),
                "body": new_body.strip(),
            }
            apply_review_decision(store, lead["source_id"], "revise", reviewer="Diwas", notes=notes or "Edited for voice/hook precision", revised_labels=revised_labels)
            st.success(f"✎ Saved revision for {lead['name']}!")
            pending_remaining = [l["source_id"] for l in all_leads if l["state"] == "needs-review" and l["source_id"] != lead["source_id"]]
            if pending_remaining:
                st.session_state["selected_id"] = pending_remaining[0]
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

with act_col3:
    if st.button("✕ Reject Lead", use_container_width=True):
        try:
            apply_review_decision(store, lead["source_id"], "reject", reviewer="Diwas", notes=notes or "Disqualified lead")
            st.warning(f"✕ Rejected {lead['name']}")
            pending_remaining = [l["source_id"] for l in all_leads if l["state"] == "needs-review" and l["source_id"] != lead["source_id"]]
            if pending_remaining:
                st.session_state["selected_id"] = pending_remaining[0]
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

with act_col4:
    if st.button("? Mark Uncertain", use_container_width=True):
        try:
            apply_review_decision(store, lead["source_id"], "uncertain", reviewer="Diwas", notes=notes or "Needs second pass")
            st.info(f"? Marked {lead['name']} as uncertain")
            pending_remaining = [l["source_id"] for l in all_leads if l["state"] == "needs-review" and l["source_id"] != lead["source_id"]]
            if pending_remaining:
                st.session_state["selected_id"] = pending_remaining[0]
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("Export Training Dataset")
if st.sidebar.button("📦 Export JSONL & Run Audit", use_container_width=True):
    try:
        receipt = export_slm_dataset()
        audit = audit_exported_dataset()
        st.sidebar.success(f"Exported {receipt['total_exported']} records total!")
        for split_name, split_info in receipt["partitions"].items():
            st.sidebar.caption(f"{split_name.upper()}: {split_info['count']} records")
        if audit["verified"]:
            st.sidebar.info(f"✅ Audit passed — zero leakage, zero overlap")
        else:
            st.sidebar.error(f"❌ Audit errors: {audit['errors'][:3]}")
    except Exception as e:
        st.sidebar.error(f"Export failed: {e}")
