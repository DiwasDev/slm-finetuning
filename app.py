"""
Streamlit-style Review Dashboard for Diwas.
Built with Python standard library (http.server).
Zero external dependencies. Launches on http://localhost:8501
"""

import json
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent / "src"))

from decision import init_decision_store, DEFAULT_STORE_PATH
from review_cli import prepare_review_queue, apply_review_decision, get_all_review_items
from export import export_slm_dataset, DEFAULT_EXPORT_PATH
from audit import audit_exported_dataset

PORT = 8501

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EmailSLM Review Dashboard &bull; Streamlit UI</title>
  <style>
    :root {
      --bg: #0e1117;
      --sidebar-bg: #262730;
      --card-bg: #1e2130;
      --border: #31333f;
      --text: #fafafa;
      --muted: #808495;
      --primary: #ff4b4b;
      --accent: #0068c9;
      --success: #29b5e8;
      --green: #21c354;
      --warning: #ffbd45;
      --danger: #ff4b4b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }
    
    /* Sidebar */
    #sidebar { width: 340px; background: var(--sidebar-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
    .sidebar-header { padding: 1.25rem; border-bottom: 1px solid var(--border); }
    .sidebar-header h1 { font-size: 1.15rem; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 0.5rem; }
    .sidebar-header p { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }
    .stats-card { background: rgba(0,0,0,0.2); border-radius: 6px; padding: 0.75rem; margin-top: 0.75rem; font-size: 0.8rem; }
    .progress-bar-bg { background: #31333f; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 0.5rem; }
    .progress-bar-fill { background: var(--primary); height: 100%; width: 0%; transition: width 0.3s; }
    
    .filter-box { padding: 0.75rem 1.25rem; border-bottom: 1px solid var(--border); display: flex; gap: 0.5rem; }
    .filter-select { background: #0e1117; color: var(--text); border: 1px solid var(--border); border-radius: 4px; padding: 0.35rem 0.5rem; font-size: 0.8rem; flex: 1; }
    
    .lead-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
    .lead-item { padding: 0.65rem 0.75rem; border-radius: 6px; margin-bottom: 0.35rem; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; font-size: 0.85rem; }
    .lead-item:hover { background: #31333f; }
    .lead-item.active { background: #31333f; border-color: var(--primary); }
    .lead-item-header { display: flex; justify-content: space-between; align-items: center; }
    .lead-item-title { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 190px; }
    .lead-item-sub { font-size: 0.75rem; color: var(--muted); margin-top: 0.15rem; }
    
    .badge { padding: 0.15rem 0.45rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }
    .badge-revised { background: rgba(0, 104, 201, 0.25); color: #70b4ff; border: 1px solid #0068c9; }
    .badge-accepted { background: rgba(33, 195, 84, 0.25); color: #5ee48a; border: 1px solid #21c354; }
    .badge-rejected { background: rgba(255, 75, 75, 0.25); color: #ff8585; border: 1px solid #ff4b4b; }
    .badge-uncertain { background: rgba(255, 189, 69, 0.25); color: #ffd685; border: 1px solid #ffbd45; }
    .badge-needs-review { background: #31333f; color: var(--muted); border: 1px solid #4a4d5e; }

    /* Main Content */
    #main { flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 2rem; }
    .header-bar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; }
    .header-title h2 { font-size: 1.75rem; font-weight: 700; color: var(--text); }
    .header-title p { color: var(--muted); font-size: 0.9rem; margin-top: 0.25rem; }
    
    .top-actions { display: flex; gap: 0.75rem; }
    .btn { background: #262730; color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 1rem; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.15s; display: inline-flex; align-items: center; gap: 0.4rem; text-decoration: none; }
    .btn:hover { background: #31333f; border-color: var(--muted); }
    .btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
    .btn-primary:hover { background: #e03a3a; }
    .btn-green { background: #198754; border-color: #198754; color: #fff; }
    .btn-green:hover { background: #157347; }
    .btn-link { background: rgba(0, 104, 201, 0.15); border-color: #0068c9; color: #70b4ff; }
    .btn-link:hover { background: rgba(0, 104, 201, 0.3); }

    /* Review Card */
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card-section-title { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; }
    
    .prospect-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
    .prospect-stat label { display: block; font-size: 0.75rem; color: var(--muted); }
    .prospect-stat span { font-weight: 600; font-size: 0.95rem; }
    
    .link-row { display: flex; gap: 0.75rem; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.05); }

    /* Form Editors */
    .field-group { margin-bottom: 1.25rem; }
    .field-group label { display: block; font-size: 0.85rem; font-weight: 600; color: var(--text); margin-bottom: 0.4rem; }
    .field-desc { font-size: 0.75rem; color: var(--muted); margin-bottom: 0.35rem; }
    .input-text, .textarea { width: 100%; background: #0e1117; border: 1px solid var(--border); border-radius: 6px; padding: 0.65rem; color: var(--text); font-size: 0.9rem; font-family: inherit; }
    .input-text:focus, .textarea:focus { outline: none; border-color: var(--primary); }
    .textarea { resize: vertical; min-height: 80px; }
    .textarea-body { min-height: 140px; font-family: monospace; font-size: 0.85rem; }

    /* Decision Bar */
    .decision-bar { display: flex; justify-content: space-between; align-items: center; background: #1e2130; border-top: 1px solid var(--border); padding: 1rem 0 0 0; margin-top: 1.5rem; }
    .decision-buttons { display: flex; gap: 0.75rem; }
    .status-msg { font-size: 0.85rem; font-weight: 600; }
  </style>
</head>
<body>
  <!-- Sidebar -->
  <div id="sidebar">
    <div class="sidebar-header">
      <h1><span>⚡</span> EmailSLM Review</h1>
      <p>Diwas Editorial Decision System</p>
      <div class="stats-card">
        <div style="display: flex; justify-content: space-between;">
          <span id="reviewed-count">Reviewed: 1 / 48</span>
          <span id="progress-pct" style="font-weight: 700; color: var(--primary);">2%</span>
        </div>
        <div class="progress-bar-bg">
          <div id="progress-fill" class="progress-bar-fill" style="width: 2%;"></div>
        </div>
      </div>
    </div>

    <div class="filter-box">
      <select id="filter-status" class="filter-select" onchange="renderList()">
        <option value="all">All States</option>
        <option value="needs-review">Pending (Needs Review)</option>
        <option value="revised">Revised</option>
        <option value="accepted">Accepted</option>
        <option value="rejected">Rejected</option>
        <option value="uncertain">Uncertain</option>
      </select>
      <select id="filter-sector" class="filter-select" onchange="renderList()">
        <option value="all">All Sectors</option>
        <option value="marketing">Marketing (34)</option>
        <option value="accounting">Accounting (14)</option>
      </select>
    </div>

    <div id="lead-list" class="lead-list"></div>
  </div>

  <!-- Main View -->
  <div id="main">
    <div class="header-bar">
      <div class="header-title">
        <h2 id="lead-title">Select a Lead</h2>
        <p id="lead-subtitle">ADR-001 Editorial Review Rubric</p>
      </div>
      <div class="top-actions">
        <button class="btn btn-green" onclick="exportDataset()"><span>📦</span> Export SLM JSONL & Audit</button>
      </div>
    </div>

    <div id="workspace">
      <!-- Prospect Info -->
      <div class="card">
        <div class="card-section-title">
          <span>Prospect Profile & Verified Links</span>
          <span id="lead-badge" class="badge badge-needs-review">needs-review</span>
        </div>
        <div class="prospect-grid">
          <div class="prospect-stat"><label>Prospect Name</label><span id="prospect-name">—</span></div>
          <div class="prospect-stat"><label>Company</label><span id="prospect-company">—</span></div>
          <div class="prospect-stat"><label>Sector</label><span id="prospect-sector">—</span></div>
          <div class="prospect-stat"><label>Email</label><span id="prospect-email">—</span></div>
        </div>

        <div class="link-row">
          <a id="btn-linkedin" href="#" target="_blank" class="btn btn-link"><span>🔗</span> Open LinkedIn Profile</a>
          <a id="btn-website" href="#" target="_blank" class="btn btn-link"><span>🌐</span> Visit Company Website</a>
        </div>
      </div>

      <!-- 4-Field Taxonomy Editor -->
      <div class="card">
        <div class="card-section-title">
          <span>4-Field Taxonomy (Claude Candidate vs Editorial Rewrite)</span>
          <span style="font-size: 0.75rem; color: var(--muted);">Target &ge;30% Diwas Edits</span>
        </div>

        <div class="field-group">
          <label>1. Diagnostic Pain Point</label>
          <div class="field-desc">Must identify a real operational time or profit leak at their firm.</div>
          <textarea id="field-pain" class="textarea"></textarea>
        </div>

        <div class="field-group">
          <label>2. Personalization Angle (Evidence Trace)</label>
          <div class="field-desc">Specific verifiable citation from their website or recent LinkedIn posts.</div>
          <textarea id="field-angle" class="textarea"></textarea>
        </div>

        <div class="field-group">
          <label>3. Subject Hook</label>
          <div class="field-desc">Pattern-interrupt hook adhering strictly to Noman's 22 rules.</div>
          <input type="text" id="field-subject" class="input-text">
        </div>

        <div class="field-group">
          <label>4. Email Message Body</label>
          <div class="field-desc">Tailored cold outreach signed off with 'Regards,\nDiwas'.</div>
          <textarea id="field-body" class="textarea textarea-body"></textarea>
        </div>

        <div class="field-group">
          <label>Review Notes (Optional)</label>
          <input type="text" id="field-notes" class="input-text" placeholder="e.g. Tightened the hook / authentic Diwas voice">
        </div>

        <div class="decision-bar">
          <div id="status-msg" class="status-msg"></div>
          <div class="decision-buttons">
            <button class="btn" style="border-color: #4e5166; background: #262730; color: #fff;" onclick="copyLeadBundle()"><span id="copy-icon">📋</span> <span id="copy-btn-text">Copy All to Clipboard</span></button>
            <button class="btn btn-green" onclick="submitDecision('accept')"><span>✓</span> Accept Verbatim</button>
            <button class="btn btn-primary" onclick="submitDecision('revise')"><span>✎</span> Save as Revised</button>
            <button class="btn btn-danger" style="color: #ff8585; border-color: #ff4b4b;" onclick="submitDecision('reject')"><span>✕</span> Reject</button>
            <button class="btn" onclick="submitDecision('uncertain')"><span>?</span> Mark Uncertain</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let leadsData = [];
    let currentLead = null;

    function copyLeadBundle() {
      if (!currentLead) return;
      const pain = (document.getElementById('field-pain').value || '').trim();
      const angle = (document.getElementById('field-angle').value || '').trim();
      const subject = (document.getElementById('field-subject').value || '').trim();
      const body = (document.getElementById('field-body').value || '').trim();
      
      const text = `PROSPECT: ${currentLead.name} (${currentLead.company || currentLead.sector})\nSECTOR: ${currentLead.sector.toUpperCase()}\nWEBSITE: ${currentLead.website || 'N/A'}\nLINKEDIN: ${currentLead.linkedin || 'N/A'}\n\n1. OPERATIONAL PAIN POINT:\n${pain}\n\n2. PERSONALIZATION ANGLE:\n${angle}\n\n3. SUBJECT:\n${subject}\n\n4. EMAIL BODY:\n${body}`;
      
      const btn = document.getElementById('copy-btn-text');
      const icon = document.getElementById('copy-icon');

      navigator.clipboard.writeText(text).then(() => {
        btn.innerText = 'Copied to Clipboard!';
        icon.innerText = '✅';
        setTimeout(() => {
          btn.innerText = 'Copy All to Clipboard';
          icon.innerText = '📋';
        }, 2500);
      }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btn.innerText = 'Copied!';
        icon.innerText = '✅';
        setTimeout(() => {
          btn.innerText = 'Copy All to Clipboard';
          icon.innerText = '📋';
        }, 2000);
      });
    }

    async function loadData() {
      const res = await fetch('/api/leads');
      leadsData = await res.json();
      renderList();
      updateStats();

      // Default select first pending lead or Waleed
      if (!currentLead && leadsData.length > 0) {
        selectLead(leadsData[0].source_id);
      }
    }

    function updateStats() {
      const total = leadsData.length;
      const reviewed = leadsData.filter(l => l.state !== 'needs-review' && l.state !== 'proposed').length;
      const pct = Math.round((reviewed / total) * 100);

      document.getElementById('reviewed-count').innerText = `Reviewed: ${reviewed} / ${total}`;
      document.getElementById('progress-pct').innerText = `${pct}%`;
      document.getElementById('progress-fill').style.width = `${pct}%`;
    }

    function renderList() {
      const filterStatus = document.getElementById('filter-status').value;
      const filterSector = document.getElementById('filter-sector').value;
      const listEl = document.getElementById('lead-list');
      listEl.innerHTML = '';

      leadsData.forEach(lead => {
        if (filterStatus !== 'all' && lead.state !== filterStatus) return;
        if (filterSector !== 'all' && lead.sector !== filterSector) return;

        const item = document.createElement('div');
        item.className = 'lead-item' + (currentLead && currentLead.source_id === lead.source_id ? ' active' : '');
        item.onclick = () => selectLead(lead.source_id);

        item.innerHTML = `
          <div class="lead-item-header">
            <div class="lead-item-title">${lead.name || 'Unnamed'}</div>
            <span class="badge badge-${lead.state}">${lead.state}</span>
          </div>
          <div class="lead-item-sub">${lead.company || ''} &bull; ${lead.sector}</div>
        `;
        listEl.appendChild(item);
      });
    }

    function selectLead(sourceId) {
      currentLead = leadsData.find(l => l.source_id === sourceId);
      if (!currentLead) return;

      renderList();

      document.getElementById('lead-title').innerText = `${currentLead.name} (${currentLead.company || 'N/A'})`;
      document.getElementById('lead-subtitle').innerText = `${currentLead.source_id} &bull; Sector: ${currentLead.sector.toUpperCase()}`;

      document.getElementById('prospect-name').innerText = currentLead.name || 'N/A';
      document.getElementById('prospect-company').innerText = currentLead.company || 'N/A';
      document.getElementById('prospect-sector').innerText = currentLead.sector.toUpperCase();
      document.getElementById('prospect-email').innerText = currentLead.email || 'N/A';

      const badge = document.getElementById('lead-badge');
      badge.className = `badge badge-${currentLead.state}`;
      badge.innerText = currentLead.state;

      // Contact Links
      const linkedinBtn = document.getElementById('btn-linkedin');
      if (currentLead.linkedin && currentLead.linkedin !== 'N/A') {
        linkedinBtn.href = currentLead.linkedin;
        linkedinBtn.style.display = 'inline-flex';
      } else {
        linkedinBtn.style.display = 'none';
      }

      const websiteBtn = document.getElementById('btn-website');
      if (currentLead.website && currentLead.website !== 'N/A') {
        let url = currentLead.website;
        if (!url.startsWith('http://') && !url.startsWith('https://')) url = 'https://' + url;
        websiteBtn.href = url;
        websiteBtn.style.display = 'inline-flex';
      } else {
        websiteBtn.style.display = 'none';
      }

      // Fields
      const labels = currentLead.labels || {};
      document.getElementById('field-pain').value = labels.pain_point || '';
      document.getElementById('field-angle').value = labels.personalization_angle || '';
      document.getElementById('field-subject').value = labels.subject || '';
      document.getElementById('field-body').value = labels.body || '';
      document.getElementById('field-notes').value = currentLead.notes || '';
      document.getElementById('status-msg').innerText = '';
    }

    async function submitDecision(action) {
      if (!currentLead) return;

      const labels = {
        pain_point: document.getElementById('field-pain').value.trim(),
        personalization_angle: document.getElementById('field-angle').value.trim(),
        subject: document.getElementById('field-subject').value.trim(),
        body: document.getElementById('field-body').value.trim()
      };
      const notes = document.getElementById('field-notes').value.trim();

      const res = await fetch('/api/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: currentLead.source_id,
          action: action,
          labels: labels,
          notes: notes
        })
      });

      const result = await res.json();
      if (result.ok) {
        document.getElementById('status-msg').innerText = `Saved as ${action.toUpperCase()}!`;
        document.getElementById('status-msg').style.color = '#5ee48a';
        currentLead.state = result.record.state;
        currentLead.labels = result.record.labels;
        currentLead.notes = result.record.notes;
        updateStats();
        renderList();
      } else {
        document.getElementById('status-msg').innerText = `Error: ${result.error}`;
        document.getElementById('status-msg').style.color = '#ff8585';
      }
    }

    async function exportDataset() {
      const res = await fetch('/api/export', { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        alert(`Dataset Exported Successfully!\\nTotal Examples: ${data.receipt.total_exported}\\nAudit Verified: ${data.audit.verified}\\nFile: ${data.receipt.output_file}`);
      } else {
        alert(`Export failed: ${data.error}`);
      }
    }

    window.onload = loadData;
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif url.path == "/api/leads":
            store = init_decision_store()
            leads_list = get_all_review_items(store)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(leads_list).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        if url.path == "/api/decision":
            try:
                data = json.loads(body.decode("utf-8"))
                sid = data["source_id"]
                action = data["action"]
                notes = data.get("notes", "")
                labels = data.get("labels")

                store = init_decision_store()
                rec = apply_review_decision(
                    store,
                    source_id=sid,
                    action=action,
                    reviewer="Diwas",
                    notes=notes,
                    revised_labels=labels if action == "revise" else None,
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "record": rec}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))

        elif url.path == "/api/export":
            try:
                receipt = export_slm_dataset()
                audit = audit_exported_dataset()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "receipt": receipt, "audit": audit}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server():
    server = HTTPServer(("localhost", PORT), DashboardHandler)
    url = f"http://localhost:{PORT}"
    print(f"\n=======================================================")
    print(f"  EMAIL-SLM STREAMLIT-STYLE REVIEW DASHBOARD")
    print(f"  Running at: {url}")
    print(f"  Press Ctrl+C to stop the server.")
    print(f"=======================================================\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    run_server()
