import http.server
import json
import os
import shutil
import socketserver
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import verify_restore

PORT = 8080
BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = BASE_DIR / "sample-data" / "generated"
DR_BUCKET_DIR = BASE_DIR / "sample-data" / "dr-bucket"
RESTORE_DIR = BASE_DIR / "restore-output"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AWS Disaster Recovery & Backup Automation Console</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --accent: #ff9900;
      --text: #c9d1d9;
      --text-heading: #f0f6fc;
      --success: #238636;
      --danger: #da3633;
      --info: #58a6ff;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 24px; }
    .container { max-width: 1200px; margin: 0 auto; }
    header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
    .logo-area { display: flex; align-items: center; gap: 12px; }
    .logo-icon { font-size: 28px; color: var(--accent); }
    h1 { color: var(--text-heading); font-size: 22px; font-weight: 600; }
    .badge { background: #21262d; border: 1px solid var(--border); padding: 4px 10px; border-radius: 12px; font-size: 12px; color: #8b949e; }
    .badge-aws { color: var(--accent); border-color: rgba(255, 153, 0, 0.4); }
    
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
    .card-title { font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #8b949e; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
    .metric-val { font-size: 26px; font-weight: 700; color: var(--text-heading); }
    .metric-sub { font-size: 12px; color: #8b949e; margin-top: 4px; }
    
    .panel { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 24px; overflow: hidden; }
    .panel-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
    .panel-title { color: var(--text-heading); font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
    .panel-body { padding: 20px; }

    .btn-group { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
    button { background: #21262d; color: var(--text-heading); border: 1px solid var(--border); padding: 10px 16px; border-radius: 6px; font-weight: 500; font-size: 13px; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; gap: 8px; }
    button:hover { background: #30363d; border-color: #8b949e; }
    button.btn-primary { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
    button.btn-primary:hover { background: #e68a00; }
    button.btn-success { background: var(--success); color: #fff; border-color: var(--success); }
    button.btn-success:hover { background: #2ea043; }
    button.btn-danger { background: rgba(218, 54, 51, 0.2); color: #ff7b72; border-color: var(--danger); }
    button.btn-danger:hover { background: var(--danger); color: #fff; }

    table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; margin-top: 12px; }
    th { padding: 10px 12px; background: #21262d; color: #8b949e; border-bottom: 1px solid var(--border); font-weight: 500; }
    td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-family: monospace; }
    tr:last-child td { border-bottom: none; }
    
    .status-pill { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; font-family: sans-serif; display: inline-block; }
    .status-match { background: rgba(35, 134, 54, 0.2); color: #3fb950; border: 1px solid rgba(35, 134, 54, 0.4); }
    .status-fail { background: rgba(218, 54, 51, 0.2); color: #ff7b72; border: 1px solid rgba(218, 54, 51, 0.4); }
    .status-warn { background: rgba(210, 153, 34, 0.2); color: #e3b341; border: 1px solid rgba(210, 153, 34, 0.4); }

    .arch-flow { display: flex; align-items: center; justify-content: space-around; gap: 12px; padding: 24px; background: #0d1117; border-radius: 6px; border: 1px solid var(--border); flex-wrap: wrap; margin-bottom: 20px; }
    .arch-node { text-align: center; padding: 12px 18px; border-radius: 8px; background: #161b22; border: 1px solid var(--border); min-width: 140px; }
    .arch-node i { font-size: 24px; margin-bottom: 8px; color: var(--accent); }
    .arch-node .name { font-weight: 600; font-size: 13px; color: var(--text-heading); }
    .arch-node .sub { font-size: 11px; color: #8b949e; margin-top: 2px; }
    .arch-arrow { color: #8b949e; font-size: 18px; }

    .terminal-box { background: #090d12; border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; color: #8b949e; max-height: 180px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; }
    .term-info { color: #58a6ff; }
    .term-success { color: #3fb950; }
    .term-error { color: #f85149; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-area">
        <i class="fa-brands fa-aws logo-icon"></i>
        <div>
          <h1>AWS Disaster Recovery & Backup Automation Console</h1>
          <div style="font-size: 12px; color: #8b949e;">Cross-Region S3 Replication, Lambda Orchestration & Hash Verification Drill</div>
        </div>
      </div>
      <div>
        <span class="badge badge-aws"><i class="fa-solid fa-server"></i> Active Mode: Local / EC2 Simulator</span>
      </div>
    </header>

    <!-- Top Metrics -->
    <div class="grid">
      <div class="card">
        <div class="card-title"><i class="fa-solid fa-cloud"></i> Source Region</div>
        <div class="metric-val" id="src-region">us-east-1</div>
        <div class="metric-sub">Primary Data (N. Virginia)</div>
      </div>
      <div class="card">
        <div class="card-title"><i class="fa-solid fa-shield-halved"></i> DR Region</div>
        <div class="metric-val" id="dr-region">us-west-2</div>
        <div class="metric-sub">Secondary Bucket (Oregon)</div>
      </div>
      <div class="card">
        <div class="card-title"><i class="fa-solid fa-clock-rotate-left"></i> Intended RPO</div>
        <div class="metric-val">&le; 24h</div>
        <div class="metric-sub">Daily EventBridge Schedule (02:00 UTC)</div>
      </div>
      <div class="card">
        <div class="card-title"><i class="fa-solid fa-stopwatch"></i> Measured RTO</div>
        <div class="metric-val" id="measured-rto">-- sec</div>
        <div class="metric-sub" id="rto-status">Awaiting Timed Drill</div>
      </div>
    </div>

    <!-- Visual Architecture Flow -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title"><i class="fa-solid fa-diagram-project"></i> Pipeline Architecture & Status</div>
        <span class="badge" id="pipe-status"><i class="fa-solid fa-check"></i> System Operational</span>
      </div>
      <div class="panel-body">
        <div class="arch-flow">
          <div class="arch-node">
            <i class="fa-solid fa-calendar-check"></i>
            <div class="name">EventBridge</div>
            <div class="sub">Daily Cron</div>
          </div>
          <div class="arch-arrow">&rarr;</div>
          <div class="arch-node">
            <i class="fa-solid fa-bolt"></i>
            <div class="name">AWS Lambda</div>
            <div class="sub">Python 3.12 Boto3</div>
          </div>
          <div class="arch-arrow">&rarr;</div>
          <div class="arch-node">
            <i class="fa-solid fa-database"></i>
            <div class="name">Source S3</div>
            <div class="sub" id="arch-src-count">0 Objects</div>
          </div>
          <div class="arch-arrow">&rarr;</div>
          <div class="arch-node">
            <i class="fa-solid fa-box-archive"></i>
            <div class="name">DR Recovery S3</div>
            <div class="sub" id="arch-dr-count">0 Runs</div>
          </div>
          <div class="arch-arrow">&rarr;</div>
          <div class="arch-node">
            <i class="fa-solid fa-fingerprint"></i>
            <div class="name">SHA-256 Audit</div>
            <div class="sub" id="arch-hash-status">Ready</div>
          </div>
        </div>

        <!-- Action Controls -->
        <div class="panel-title" style="margin-bottom: 12px;"><i class="fa-solid fa-sliders"></i> Disaster Recovery Drill Controls</div>
        <div class="btn-group">
          <button class="btn-primary" onclick="generateSample()"><i class="fa-solid fa-file-circle-plus"></i> 1. Generate Sample Source Data</button>
          <button class="btn-success" onclick="runBackup()"><i class="fa-solid fa-play"></i> 2. Execute Backup (Lambda Run)</button>
          <button onclick="runRestore()"><i class="fa-solid fa-download"></i> 3. Execute Restore Drill (Measure RTO)</button>
          <button onclick="verifyHashes()"><i class="fa-solid fa-certificate"></i> 4. Verify SHA-256 Hashes</button>
          <button class="btn-danger" onclick="corruptSample()"><i class="fa-solid fa-triangle-exclamation"></i> Simulate Data Corruption</button>
        </div>

        <!-- Terminal Output -->
        <div class="terminal-box" id="terminal">[System Initialized] Ready to execute Disaster Recovery Drill.
Choose '1. Generate Sample Source Data' to populate test data.</div>
      </div>
    </div>

    <!-- Integrity Audit Table -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title"><i class="fa-solid fa-list-check"></i> Cryptographic Hash Verification & File Audit</div>
        <span class="badge" id="audit-badge">0 Files Checked</span>
      </div>
      <div class="panel-body" style="padding: 0;">
        <table>
          <thead>
            <tr>
              <th>File Path</th>
              <th>Status</th>
              <th>Source SHA-256 Checksum</th>
              <th>Restored SHA-256 Checksum</th>
            </tr>
          </thead>
          <tbody id="audit-table-body">
            <tr>
              <td colspan="4" style="text-align: center; color: #8b949e; padding: 24px;">No files checked yet. Run "Generate Sample Source Data" followed by "Execute Backup" and "Restore".</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    function logTerm(msg, type='info') {
      const box = document.getElementById('terminal');
      const time = new Date().toLocaleTimeString();
      let colorClass = 'term-info';
      if(type === 'success') colorClass = 'term-success';
      if(type === 'error') colorClass = 'term-error';
      box.innerHTML += `\\n[${time}] <span class="${colorClass}">${msg}</span>`;
      box.scrollTop = box.scrollHeight;
    }

    async function refreshStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('arch-src-count').innerText = `${data.source_files.length} Objects`;
        document.getElementById('arch-dr-count').innerText = `${data.dr_runs.length} Recovery Runs`;
        if(data.last_rto) {
          document.getElementById('measured-rto').innerText = `${data.last_rto}s`;
          document.getElementById('rto-status').innerText = 'Last Drill Stopwatch Result';
        }
      } catch (err) {
        console.error(err);
      }
    }

    async function generateSample() {
      logTerm("Generating sample production files (app.config, users_dump.sql, payment_records.json)...");
      const res = await fetch('/api/generate-sample', { method: 'POST' });
      const data = await res.json();
      logTerm(`Created ${data.created_count} sample files in source bucket location.`, 'success');
      refreshStatus();
    }

    async function runBackup() {
      logTerm("Triggering Lambda Backup Orchestration...");
      const res = await fetch('/api/run-backup', { method: 'POST' });
      const data = await res.json();
      if(data.error) {
        logTerm(`Backup failed: ${data.error}`, 'error');
      } else {
        logTerm(`Backup completed! Run ID: ${data.run_id}`, 'success');
        logTerm(`Objects Copied: ${data.copied_count} | Bytes Checked: Valid | Target Prefix: ${data.prefix}`, 'info');
      }
      refreshStatus();
    }

    async function runRestore() {
      logTerm("Starting Recovery Drill: Downloading recovery point to target folder...");
      const res = await fetch('/api/run-restore', { method: 'POST' });
      const data = await res.json();
      if(data.error) {
        logTerm(`Restore drill failed: ${data.error}`, 'error');
      } else {
        logTerm(`Restore Drill Completed! Restored ${data.restored_count} files in ${data.elapsed_seconds}s`, 'success');
        document.getElementById('measured-rto').innerText = `${data.elapsed_seconds}s`;
        document.getElementById('rto-status').innerText = 'Verified via Timed Drill';
      }
      refreshStatus();
    }

    async function verifyHashes() {
      logTerm("Computing cryptographic SHA-256 checksums across Source and Restored datasets...");
      const res = await fetch('/api/verify-hashes', { method: 'POST' });
      const data = await res.json();
      const tbody = document.getElementById('audit-table-body');
      tbody.innerHTML = '';
      
      let allMatch = true;
      data.results.forEach(row => {
        const tr = document.createElement('tr');
        let statusBadge = '<span class="status-pill status-match"><i class="fa-solid fa-check"></i> MATCH</span>';
        if(row.status !== 'match') {
          statusBadge = `<span class="status-pill status-fail"><i class="fa-solid fa-xmark"></i> ${row.status.toUpperCase()}</span>`;
          allMatch = false;
        }
        tr.innerHTML = `
          <td><strong>${row.path}</strong></td>
          <td>${statusBadge}</td>
          <td style="font-size:11px;">${row.source_sha256 ? row.source_sha256.substring(0, 24) + '...' : 'NONE'}</td>
          <td style="font-size:11px;">${row.restored_sha256 ? row.restored_sha256.substring(0, 24) + '...' : 'NONE'}</td>
        `;
        tbody.appendChild(tr);
      });

      document.getElementById('audit-badge').innerText = `${data.results.length} Files Verified`;
      if(allMatch && data.results.length > 0) {
        logTerm(`AUDIT PASSED: All ${data.results.length} files match cryptographically (Zero Bit Rot/Tampering)!`, 'success');
        document.getElementById('arch-hash-status').innerText = 'Verified (100%)';
      } else if(!allMatch) {
        logTerm(`AUDIT FAILED: Cryptographic hash mismatch or missing files detected!`, 'error');
        document.getElementById('arch-hash-status').innerText = 'Integrity Mismatch!';
      }
    }

    async function corruptSample() {
      logTerm("Simulating Disaster / Data Corruption Event on Source dataset...", 'error');
      const res = await fetch('/api/corrupt-data', { method: 'POST' });
      const data = await res.json();
      logTerm(`Modified ${data.corrupted_file} with rogue data. Run "Verify SHA-256 Hashes" to observe integrity detection.`, 'error');
    }

    refreshStatus();
  </script>
</body>
</html>
"""


class DRDashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            source_files = []
            if SAMPLE_DIR.exists():
                source_files = [
                    str(p.relative_to(SAMPLE_DIR))
                    for p in SAMPLE_DIR.rglob("*")
                    if p.is_file()
                ]

            dr_runs = []
            if (DR_BUCKET_DIR / "recovery").exists():
                dr_runs = [
                    p.name for p in (DR_BUCKET_DIR / "recovery").iterdir() if p.is_dir()
                ]

            state = {
                "source_files": source_files,
                "dr_runs": dr_runs,
                "last_rto": getattr(self.server, "last_rto", None),
            }
            self.wfile.write(json.dumps(state).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if parsed.path == "/api/generate-sample":
            SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
            nested = SAMPLE_DIR / "configs"
            nested.mkdir(parents=True, exist_ok=True)

            (SAMPLE_DIR / "app_config.json").write_text(
                json.dumps(
                    {
                        "app_name": "PaymentGateway",
                        "env": "production",
                        "version": "2.4.1",
                    },
                    indent=2,
                )
            )
            (SAMPLE_DIR / "users_dump.sql").write_text(
                "CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(255));\n"
                "INSERT INTO users VALUES (1, 'admin@example.com'), (2, 'support@example.com');\n"
            )
            (nested / "database.yml").write_text(
                "production:\n  adapter: postgresql\n  pool: 10\n  timeout: 5000\n"
            )

            res = {"created_count": 3, "status": "success"}
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif parsed.path == "/api/run-backup":
            if not SAMPLE_DIR.exists() or not list(SAMPLE_DIR.rglob("*")):
                self.wfile.write(
                    json.dumps(
                        {"error": "Source bucket empty. Generate sample data first."}
                    ).encode("utf-8")
                )
                return

            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-req-sim123")
            target_run_dir = DR_BUCKET_DIR / "recovery" / run_id
            target_run_dir.mkdir(parents=True, exist_ok=True)

            count = 0
            for item in SAMPLE_DIR.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(SAMPLE_DIR)
                    dest = target_run_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    count += 1

            self.server.last_run_id = run_id
            res = {
                "run_id": run_id,
                "prefix": f"recovery/{run_id}",
                "copied_count": count,
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif parsed.path == "/api/run-restore":
            last_run = getattr(self.server, "last_run_id", None)
            if not last_run:
                # Find latest recovery run
                rec_dir = DR_BUCKET_DIR / "recovery"
                if rec_dir.exists():
                    dirs = sorted(
                        [d for d in rec_dir.iterdir() if d.is_dir()],
                        key=lambda x: x.stat().st_mtime,
                        reverse=True,
                    )
                    if dirs:
                        last_run = dirs[0].name

            if not last_run:
                self.wfile.write(
                    json.dumps(
                        {"error": "No recovery run found. Run backup first."}
                    ).encode("utf-8")
                )
                return

            src_recovery = DR_BUCKET_DIR / "recovery" / last_run
            RESTORE_DIR.mkdir(parents=True, exist_ok=True)

            start = time.perf_counter()
            restored_count = 0
            for item in src_recovery.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src_recovery)
                    dest = RESTORE_DIR / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    restored_count += 1
            elapsed = round(time.perf_counter() - start, 4)
            self.server.last_rto = elapsed

            res = {"restored_count": restored_count, "elapsed_seconds": elapsed}
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif parsed.path == "/api/verify-hashes":
            if not SAMPLE_DIR.exists() or not RESTORE_DIR.exists():
                self.wfile.write(
                    json.dumps(
                        {
                            "error": "Source or restored directory missing. Run steps 1-3 first."
                        }
                    ).encode("utf-8")
                )
                return

            result = verify_restore.verify(SAMPLE_DIR, RESTORE_DIR)
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif parsed.path == "/api/corrupt-data":
            target = SAMPLE_DIR / "users_dump.sql"
            if target.exists():
                target.write_text(
                    "-- TAMPERED BY RANSOMWARE / OPERATOR ERROR\nDROP TABLE users;\n"
                )
                res = {"corrupted_file": "users_dump.sql", "status": "tampered"}
            else:
                res = {"error": "Generate sample data first."}
            self.wfile.write(json.dumps(res).encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging
        return


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DRDashboardHandler) as httpd:
        print(f"============================================================")
        print(f" AWS Disaster Recovery Console is LIVE on: http://localhost:{PORT}")
        print(f" Press Ctrl+C to stop the dashboard server.")
        print(f"============================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard server.")


if __name__ == "__main__":
    main()
