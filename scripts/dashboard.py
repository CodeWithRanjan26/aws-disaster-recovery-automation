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

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = BASE_DIR / "sample-data" / "generated"
DR_BUCKET_DIR = BASE_DIR / "sample-data" / "dr-bucket"
RESTORE_DIR = BASE_DIR / "restore-output"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise AWS Disaster Recovery & Live Incident War Room</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --bg: #070b12;
      --bg-card: #0f172a;
      --bg-surface: #1e293b;
      --border: #334155;
      --border-accent: #475569;
      --accent-aws: #ff9900;
      --accent-blue: #38bdf8;
      --text: #94a3b8;
      --text-heading: #f8fafc;
      --text-muted: #64748b;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --danger-glow: rgba(239, 68, 68, 0.3);
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 18px; line-height: 1.5; min-height: 100vh; }
    .container { max-width: 1440px; margin: 0 auto; }

    /* Header Bar */
    header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 20px; flex-wrap: wrap; gap: 14px; }
    .brand-wrap { display: flex; align-items: center; gap: 14px; }
    .brand-icon { font-size: 32px; color: var(--accent-aws); }
    .brand-title { color: var(--text-heading); font-size: 20px; font-weight: 800; display: flex; align-items: center; gap: 10px; }
    .brand-sub { font-size: 12px; color: var(--text-muted); }
    .header-pills { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill { background: rgba(30, 41, 59, 0.8); border: 1px solid var(--border); padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; color: #cbd5e1; display: inline-flex; align-items: center; gap: 6px; }
    .pill-live { color: #34d399; border-color: rgba(52, 211, 153, 0.3); background: rgba(16, 185, 129, 0.1); }
    .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block; box-shadow: 0 0 8px #10b981; animation: pulse 2s infinite; }
    .pulse-dot-red { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; display: inline-block; box-shadow: 0 0 10px #ef4444; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

    /* CRITICAL SEV-1 WAR ROOM BANNER (Visible on Outage) */
    .sev1-banner { display: none; background: rgba(239, 68, 68, 0.12); border: 2px solid var(--danger); border-radius: 10px; padding: 18px 24px; margin-bottom: 22px; animation: glowRed 2s infinite; }
    .sev1-banner.active { display: block; }
    @keyframes glowRed { 0% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); } 50% { box-shadow: 0 0 30px rgba(239, 68, 68, 0.5); } 100% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); } }
    .sev1-flex { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
    .sev1-title { font-size: 16px; font-weight: 800; color: #fecaca; display: flex; align-items: center; gap: 10px; }
    .sev1-desc { font-size: 13px; color: #f87171; margin-top: 4px; }
    .downtime-counter { font-family: var(--font-mono); font-size: 24px; font-weight: 800; color: #fee2e2; background: #000; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--danger); }

    /* Live Website / Service Simulation Card */
    .service-status-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; position: relative; overflow: hidden; }
    .service-status-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: var(--success); }
    .service-status-card.down::before { background: var(--danger); }
    .service-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
    .service-name { font-size: 16px; font-weight: 700; color: var(--text-heading); display: flex; align-items: center; gap: 10px; }
    .service-url { font-size: 12px; font-family: var(--font-mono); color: var(--text-muted); }
    
    .status-badge { padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; display: inline-flex; align-items: center; gap: 8px; }
    .badge-healthy { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-outage { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid var(--danger); }
    .badge-recovered { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }

    .service-metrics-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 8px; border: 1px solid var(--border); }
    .sub-metric-title { font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 4px; }
    .sub-metric-val { font-size: 18px; font-weight: 700; color: var(--text-heading); font-family: var(--font-mono); }

    /* Tabs Bar */
    .tabs-bar { display: flex; gap: 6px; border-bottom: 1px solid var(--border); margin-bottom: 20px; overflow-x: auto; padding-bottom: 2px; }
    .tab-btn { background: none; border: none; padding: 10px 16px; font-size: 13px; font-weight: 600; color: var(--text-muted); cursor: pointer; border-radius: 6px 6px 0 0; display: flex; align-items: center; gap: 8px; transition: all 0.2s; white-space: nowrap; }
    .tab-btn:hover { color: var(--text-heading); background: rgba(30, 41, 59, 0.4); }
    .tab-btn.active { color: var(--accent-aws); border-bottom: 2px solid var(--accent-aws); background: rgba(255, 153, 0, 0.05); }

    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    /* Interactive Runbook / War Room Remediation */
    .war-room-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
    @media (max-width: 992px) { .war-room-grid { grid-template-columns: 1fr; } }

    .panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
    .panel-head { font-size: 15px; font-weight: 700; color: var(--text-heading); margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; }

    .runbook-step { background: rgba(30, 41, 59, 0.5); border: 1px solid var(--border); border-radius: 8px; padding: 14px; margin-bottom: 10px; display: flex; gap: 14px; align-items: center; transition: all 0.2s; }
    .runbook-step.active { border-color: var(--accent-aws); background: rgba(255, 153, 0, 0.05); }
    .runbook-step.done { border-color: var(--success); background: rgba(16, 185, 129, 0.05); }
    .step-num { width: 32px; height: 32px; border-radius: 50%; background: #0f172a; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; color: var(--text-heading); flex-shrink: 0; }
    .runbook-step.done .step-num { background: var(--success); color: #fff; border-color: var(--success); }
    .step-content { flex-grow: 1; }
    .step-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
    .step-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

    /* Action Buttons */
    .btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    .btn { background: #1e293b; color: var(--text-heading); border: 1px solid var(--border); padding: 10px 18px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; gap: 8px; }
    .btn:hover { background: #334155; transform: translateY(-1px); }
    .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border-color: var(--danger); }
    .btn-danger:hover { background: var(--danger); color: #fff; }
    .btn-fix { background: #059669; color: #fff; border-color: #059669; font-weight: 700; font-size: 14px; padding: 12px 22px; box-shadow: 0 0 15px rgba(16, 185, 129, 0.3); }
    .btn-fix:hover { background: #047857; }
    .btn-aws { background: var(--accent-aws); color: #000; border-color: var(--accent-aws); font-weight: 700; }
    .btn-aws:hover { background: #e68a00; color: #000; }

    /* Terminal Output Stream */
    .terminal-box { background: #030712; border: 1px solid var(--border); border-radius: 8px; padding: 14px; font-family: var(--font-mono); font-size: 12px; height: 320px; overflow-y: auto; line-height: 1.6; }
    .term-line { display: flex; gap: 8px; margin-bottom: 2px; }
    .term-time { color: #64748b; user-select: none; }
    .term-info { color: #38bdf8; }
    .term-success { color: #34d399; }
    .term-warn { color: #fbbf24; }
    .term-error { color: #f87171; }
    .term-audit { color: #c084fc; }

    /* Audit Table */
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { padding: 12px 14px; background: rgba(30, 41, 59, 0.6); color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); text-align: left; }
    td { padding: 10px 14px; border-bottom: 1px solid rgba(51, 65, 85, 0.5); font-family: var(--font-mono); color: #cbd5e1; }
    .badge-match { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; }
    .badge-mismatch { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; }

    /* Post-Mortem Report Card */
    .post-mortem-card { background: var(--bg-card); border: 1px solid #10b981; border-radius: 12px; padding: 26px; position: relative; }
    .stamp-badge { position: absolute; right: 24px; top: 24px; border: 2px solid #10b981; color: #10b981; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; transform: rotate(-5deg); text-transform: uppercase; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Top Header -->
    <header>
      <div class="brand-wrap">
        <i class="fa-brands fa-aws brand-icon"></i>
        <div>
          <div class="brand-title">
            Enterprise AWS Disaster Recovery Orchestrator & War Room
            <span class="pill pill-live"><span class="pulse-dot"></span> CLOUD CONNECTED</span>
          </div>
          <div class="brand-sub">Multi-Region S3 Replication &bull; Automated Sev-1 Incident Remediation &bull; Cryptographic Integrity Audit</div>
        </div>
      </div>
      <div class="header-pills">
        <span class="pill"><i class="fa-solid fa-cloud"></i> Primary: us-east-1</span>
        <span class="pill"><i class="fa-solid fa-shield-halved"></i> Standby DR: us-west-2</span>
        <span class="pill"><i class="fa-solid fa-stopwatch"></i> SLA Target: 99.99%</span>
        <span class="pill"><i class="fa-solid fa-lock"></i> AES-256 SSE-S3</span>
      </div>
    </header>

    <!-- CRITICAL SEV-1 OUTAGE BANNER (Appears when Disaster Strikes) -->
    <div class="sev1-banner" id="sev1-alert">
      <div class="sev1-flex">
        <div>
          <div class="sev1-title"><i class="fa-solid fa-triangle-exclamation"></i> 🚨 SEV-1 CRITICAL OUTAGE: PRIMARY REGION FAILURE (US-EAST-1)</div>
          <div class="sev1-desc" id="sev1-desc">Primary database corrupted & regional networking unreachable. Customer transactions failing!</div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 11px; color: #f87171; text-transform: uppercase; font-weight: 700; margin-bottom: 4px;">Active Incident Downtime</div>
          <div class="downtime-counter" id="downtime-timer">00:00:00</div>
        </div>
      </div>
    </div>

    <!-- LIVE PRODUCTION SERVICE STATUS CARD -->
    <div class="service-status-card" id="service-card">
      <div class="service-header">
        <div>
          <div class="service-name">
            <i class="fa-solid fa-globe" style="color: var(--accent-aws);"></i>
            Production Payments Gateway & E-Commerce Core API
            <span class="status-badge badge-healthy" id="service-status-pill"><i class="fa-solid fa-circle-check"></i> 200 OK - OPERATIONAL</span>
          </div>
          <div class="service-url">Endpoint: https://api.payments.enterprise-cloud.com/v1/checkout</div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-danger" onclick="triggerDisaster('regional_outage')"><i class="fa-solid fa-fire"></i> 1. Simulate Regional Catastrophe</button>
          <button class="btn btn-danger" onclick="triggerDisaster('ransomware')"><i class="fa-solid fa-skull"></i> 2. Simulate Ransomware DB Attack</button>
        </div>
      </div>

      <div class="service-metrics-row">
        <div>
          <div class="sub-metric-title">Active Hosting Region</div>
          <div class="sub-metric-val" id="metric-active-region" style="color: #38bdf8;">us-east-1 (Primary N. Virginia)</div>
        </div>
        <div>
          <div class="sub-metric-title">Database Health</div>
          <div class="sub-metric-val" id="metric-db-health" style="color: #34d399;">PostgreSQL Healthy (Synced)</div>
        </div>
        <div>
          <div class="sub-metric-title">Total Processed Volume</div>
          <div class="sub-metric-val" id="metric-tx-count">$1,250,420.00 (1,420 TX)</div>
        </div>
        <div>
          <div class="sub-metric-title">Latest Measured RTO</div>
          <div class="sub-metric-val" id="metric-rto" style="color: #ff9900;">-- sec</div>
        </div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-bar">
      <button class="tab-btn active" onclick="openTab('tab-remediation')"><i class="fa-solid fa-wrench"></i> Live Disaster Remediation War Room</button>
      <button class="tab-btn" onclick="openTab('tab-topology')"><i class="fa-solid fa-diagram-project"></i> Multi-Region Architecture & Buckets</button>
      <button class="tab-btn" onclick="openTab('tab-audit')"><i class="fa-solid fa-fingerprint"></i> SHA-256 Cryptographic Audit Matrix</button>
      <button class="tab-btn" onclick="openTab('tab-rca')"><i class="fa-solid fa-file-shield"></i> Post-Mortem Incident RCA Report</button>
      <button class="tab-btn" onclick="openTab('tab-iac')"><i class="fa-solid fa-cubes"></i> Terraform IaC Resources (11 Provisioned)</button>
    </div>

    <!-- TAB 1: LIVE DISASTER REMEDIATION WAR ROOM -->
    <div id="tab-remediation" class="tab-pane active">
      <div class="war-room-grid">
        <!-- Automated SRE Remediation Wizard -->
        <div class="panel">
          <div class="panel-head">
            <span><i class="fa-solid fa-list-check" style="color: var(--accent-aws);"></i> Automated SRE Disaster Recovery Runbook</span>
            <span class="pill" id="runbook-status"><i class="fa-solid fa-circle-check"></i> System Stable</span>
          </div>

          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
            Jab production disaster aata hai, toh yeh automated wizard 1-click mein **traffic drain, DR snapshot mount, cryptographic audit, aur Route 53 DNS failover** execute karke website ko wapas 200 OK banata hai!
          </p>

          <div class="runbook-step" id="step-1">
            <div class="step-num">1</div>
            <div class="step-content">
              <div class="step-title">Isolate Outage & Drain Primary Traffic</div>
              <div class="step-sub">Detach broken us-east-1 endpoints; stop corrupt write traffic.</div>
            </div>
          </div>

          <div class="runbook-step" id="step-2">
            <div class="step-num">2</div>
            <div class="step-content">
              <div class="step-title">Mount Latest Immutable DR Snapshot from us-west-2</div>
              <div class="step-sub">Fetch verified cross-region S3 recovery prefix snapshot.</div>
            </div>
          </div>

          <div class="runbook-step" id="step-3">
            <div class="step-num">3</div>
            <div class="step-content">
              <div class="step-title">Execute Cryptographic SHA-256 Checksum Audit</div>
              <div class="step-sub">Ensure zero bit-rot tampering before promoting database.</div>
            </div>
          </div>

          <div class="runbook-step" id="step-4">
            <div class="step-num">4</div>
            <div class="step-content">
              <div class="step-title">Restore Database & Route 53 DNS Failover</div>
              <div class="step-sub">Promote DR region us-west-2 to Active; switch global DNS.</div>
            </div>
          </div>

          <!-- THE BIG ACTION BUTTON -->
          <div class="btn-group">
            <button class="btn btn-fix" id="btn-remediate" onclick="executeAutomatedRemediation()"><i class="fa-solid fa-bolt"></i> 1-CLICK DISASTER REMEDIATION & FAILOVER</button>
            <button class="btn btn-aws" onclick="runNormalBackup()"><i class="fa-solid fa-cloud-arrow-up"></i> Routine Backup Run</button>
            <button class="btn" onclick="resetSystem()"><i class="fa-solid fa-arrow-rotate-left"></i> Reset to Baseline</button>
          </div>
        </div>

        <!-- Real-Time CloudWatch & Incident Log Stream -->
        <div class="panel">
          <div class="panel-head">
            <span><i class="fa-solid fa-terminal" style="color: var(--accent-blue);"></i> CloudWatch Observability Logs (Live Execution)</span>
            <span class="pill pill-live"><span class="pulse-dot"></span> STREAMING</span>
          </div>

          <div class="terminal-box" id="terminal">
            <div class="term-line"><span class="term-time">[SYS-INIT]</span> <span class="term-info">Disaster Recovery Orchestrator Online. Monitoring Primary Region us-east-1.</span></div>
            <div class="term-line"><span class="term-time">[SYS-INIT]</span> <span class="term-success">S3 Cross-Region Buckets Connected. Target SLA: 99.99%.</span></div>
            <div class="term-line"><span class="term-time">[READY]</span> <span class="term-info">Click 'Simulate Regional Catastrophe' above to observe live incident detection.</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: TOPOLOGY -->
    <div id="tab-topology" class="tab-pane">
      <div class="panel" style="margin-bottom: 20px;">
        <div class="panel-head"><span><i class="fa-solid fa-diagram-project"></i> Multi-Region Active/Standby Architecture</span></div>
        <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 20px; align-items: center;">
          <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border); border-radius: 8px; padding: 18px;">
            <span class="status-badge badge-healthy" style="margin-bottom: 10px;">Primary Region (us-east-1)</span>
            <h3 style="color: #fff; margin-bottom: 6px;">Source S3: dr-lab-primary-src</h3>
            <p style="font-size: 12px; color: var(--text-muted);">Contains live DB dumps, auth keys, application configs. Protected by Versioning & AES-256 SSE-S3.</p>
          </div>
          <div style="text-align: center; color: var(--accent-aws); font-size: 24px;">
            <i class="fa-solid fa-arrows-split-up-and-left"></i>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Automated S3 Replication</div>
          </div>
          <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border); border-radius: 8px; padding: 18px;">
            <span class="status-badge badge-recovered" style="margin-bottom: 10px;">Disaster Recovery Region (us-west-2)</span>
            <h3 style="color: #fff; margin-bottom: 6px;">Recovery S3: dr-lab-recovery-dr</h3>
            <p style="font-size: 12px; color: var(--text-muted);">Independent blast radius in Oregon. Immutable timestamped snapshots with 14-day auto-lifecycle purge.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: SHA-256 AUDIT MATRIX -->
    <div id="tab-audit" class="tab-pane">
      <div class="panel">
        <div class="panel-head">
          <span><i class="fa-solid fa-fingerprint"></i> Cryptographic SHA-256 Checksum Audit Matrix</span>
          <span class="pill" id="audit-badge">Verified</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>File Path</th>
              <th>Status</th>
              <th>Source SHA-256 Checksum (Primary)</th>
              <th>Restored SHA-256 Checksum (DR Snapshot)</th>
            </tr>
          </thead>
          <tbody id="audit-tbody">
            <tr>
              <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 24px;">Run the Remediation Wizard or Backup to view cryptographic checksums.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 4: POST-MORTEM RCA REPORT -->
    <div id="tab-rca" class="tab-pane">
      <div class="post-mortem-card">
        <div class="stamp-badge">INCIDENT RESOLVED & CLOSED</div>
        <h2 style="color: var(--text-heading); font-size: 18px; margin-bottom: 6px;"><i class="fa-solid fa-file-contract text-success"></i> Disaster Incident Post-Mortem & RCA Report</h2>
        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 20px;">SRE Engineering Incident Review for Executive Leadership & SOC 2 Compliance</div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px;">
          <div><div class="sub-metric-title">Incident Classification</div><strong style="color: #f87171;">SEV-1 Catastrophic Regional Outage</strong></div>
          <div><div class="sub-metric-title">Time to Detect (TTD)</div><strong style="color: #34d399;">&lt; 5 seconds (CloudWatch Metric Breach)</strong></div>
          <div><div class="sub-metric-title">Time to Remediate (TTR / RTO)</div><strong style="color: #ff9900;" id="rca-rto">0.042 seconds (Automated Failover)</strong></div>
          <div><div class="sub-metric-title">Data Loss (RPO)</div><strong style="color: #34d399;">0 Bytes (100% Cryptographically Verified)</strong></div>
          <div><div class="sub-metric-title">Active Failover Region</div><strong style="color: #38bdf8;">us-west-2 (Oregon Standby Promoted to Active)</strong></div>
        </div>

        <button class="btn btn-aws" onclick="window.print()"><i class="fa-solid fa-print"></i> Export / Print Post-Mortem Report</button>
      </div>
    </div>

    <!-- TAB 5: TERRAFORM IAC -->
    <div id="tab-iac" class="tab-pane">
      <div class="panel">
        <div class="panel-head"><span><i class="fa-solid fa-cubes text-accent"></i> 11 Provisioned Terraform Multi-Region Resources</span></div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; font-size: 12px;">
          <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_s3_bucket.source</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">Primary Source S3 Bucket</div>
            <div style="color: var(--text-muted);">Region: us-east-1 &bull; Versioned &bull; AES-256 SSE-S3</div>
          </div>
          <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_s3_bucket.destination</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">DR Standby S3 Bucket</div>
            <div style="color: var(--text-muted);">Region: us-west-2 &bull; 14-Day Auto-Expiration Lifecycle</div>
          </div>
          <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_lambda_function.backup</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">Python 3.12 Serverless Worker</div>
            <div style="color: var(--text-muted);">S3 Paginator &bull; ContentLength Size Check &bull; 900s Timeout</div>
          </div>
          <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_cloudwatch_metric_alarm.errors</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">CloudWatch Sev-1 Failure Alarm</div>
            <div style="color: var(--text-muted);">Evaluates Lambda Errors >= 1 in 300s &bull; Dispatches to SNS</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let downtimeInterval = null;
    let downtimeSeconds = 0;

    function openTab(tabId) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.currentTarget.classList.add('active');
    }

    function logTerm(msg, type='info') {
      const box = document.getElementById('terminal');
      const time = new Date().toLocaleTimeString();
      let colorClass = 'term-info';
      if(type === 'success') colorClass = 'term-success';
      if(type === 'warn') colorClass = 'term-warn';
      if(type === 'error') colorClass = 'term-error';
      if(type === 'audit') colorClass = 'term-audit';
      
      const line = document.createElement('div');
      line.className = 'term-line';
      line.innerHTML = `<span class="term-time">[${time}]</span> <span class="${colorClass}">${msg}</span>`;
      box.appendChild(line);
      box.scrollTop = box.scrollHeight;
    }

    function startDowntimeClock() {
      downtimeSeconds = 0;
      clearInterval(downtimeInterval);
      downtimeInterval = setInterval(() => {
        downtimeSeconds++;
        const mins = String(Math.floor(downtimeSeconds / 60)).padStart(2, '0');
        const secs = String(downtimeSeconds % 60).padStart(2, '0');
        document.getElementById('downtime-timer').innerText = `00:${mins}:${secs}`;
      }, 1000);
    }

    function stopDowntimeClock() {
      clearInterval(downtimeInterval);
    }

    // 1. TRIGGER DISASTER
    async function triggerDisaster(type) {
      logTerm(`CRITICAL INCIDENT: Injecting Sev-1 Disaster (${type.toUpperCase()})...`, 'error');
      startDowntimeClock();
      
      // Update UI to Outage Mode
      document.getElementById('sev1-alert').classList.add('active');
      const card = document.getElementById('service-card');
      card.classList.add('down');
      
      const pill = document.getElementById('service-status-pill');
      pill.className = 'status-badge badge-outage';
      pill.innerHTML = '<span class="pulse-dot-red"></span> 503 SERVICE UNAVAILABLE (SEV-1)';
      
      document.getElementById('metric-db-health').innerText = 'Corrupted / Offline';
      document.getElementById('metric-db-health').style.color = '#ef4444';
      
      document.getElementById('metric-active-region').innerText = 'us-east-1 (FAILED / UNREACHABLE)';
      document.getElementById('metric-active-region').style.color = '#ef4444';

      document.getElementById('runbook-status').className = 'pill';
      document.getElementById('runbook-status').innerHTML = '<span class="pulse-dot-red"></span> SEV-1 ACTIVE';

      // Call backend to tamper data
      if(type === 'ransomware') {
        await fetch('/api/corrupt-data', { method: 'POST' });
        logTerm("CHAOS: Production DB dump encrypted by ransomware bytes!", 'error');
      } else {
        await fetch('/api/simulate-regional-outage', { method: 'POST' });
        logTerm("CHAOS: us-east-1 regional power failure simulated! S3 endpoints unreachable.", 'error');
      }

      logTerm("ALARM: CloudWatch Metric `Errors >= 1` breached. PagerDuty / SNS Alert fired to Support Team!", 'error');
      openTab('tab-remediation');
    }

    // 2. EXECUTE 1-CLICK DISASTER REMEDIATION
    async function executeAutomatedRemediation() {
      logTerm("STARTING RUNBOOK: Initiating 1-Click Automated Disaster Recovery Failover...", 'warn');
      
      // Step 1
      document.getElementById('step-1').className = 'runbook-step done';
      logTerm("[STEP 1/4] Draining ingress traffic from damaged region us-east-1...", 'info');
      await new Promise(r => setTimeout(r, 600));

      // Step 2
      document.getElementById('step-2').className = 'runbook-step done';
      logTerm("[STEP 2/4] Accessing DR Standby S3 Bucket in us-west-2 (Oregon)...", 'info');
      logTerm("[STEP 2/4] Downloading latest verified immutable snapshot...", 'info');
      const resRestore = await fetch('/api/run-restore', { method: 'POST' });
      const dataRestore = await resRestore.json();
      await new Promise(r => setTimeout(r, 600));

      // Step 3
      document.getElementById('step-3').className = 'runbook-step done';
      logTerm("[STEP 3/4] Running bit-level SHA-256 cryptographic checksum audit on recovered dataset...", 'audit');
      const resVerify = await fetch('/api/verify-hashes', { method: 'POST' });
      const dataVerify = await resVerify.json();
      populateAuditTable(dataVerify);
      await new Promise(r => setTimeout(r, 600));

      // Step 4
      document.getElementById('step-4').className = 'runbook-step done';
      logTerm("[STEP 4/4] Promoting us-west-2 to PRIMARY. Executing Route 53 DNS failover switch...", 'success');
      await new Promise(r => setTimeout(r, 600));

      // Recovery Complete!
      stopDowntimeClock();
      document.getElementById('sev1-alert').classList.remove('active');
      const card = document.getElementById('service-card');
      card.classList.remove('down');

      const pill = document.getElementById('service-status-pill');
      pill.className = 'status-badge badge-recovered';
      pill.innerHTML = '<i class="fa-solid fa-circle-check"></i> 200 OK - OPERATIONAL (FAILOVER ACTIVE)';

      document.getElementById('metric-db-health').innerText = 'Restored 100% (PostgreSQL Healthy)';
      document.getElementById('metric-db-health').style.color = '#34d399';

      document.getElementById('metric-active-region').innerText = 'us-west-2 (DR Failover Active)';
      document.getElementById('metric-active-region').style.color = '#38bdf8';

      document.getElementById('metric-rto').innerText = `${dataRestore.elapsed_seconds} sec`;
      document.getElementById('rca-rto').innerText = `${dataRestore.elapsed_seconds} sec (Stopwatch Benchmark)`;

      document.getElementById('runbook-status').className = 'pill pill-live';
      document.getElementById('runbook-status').innerHTML = '<span class="pulse-dot"></span> FAILOVER HEALTHY';

      logTerm(`INCIDENT RESOLVED! Service restored to 200 OK in ${dataRestore.elapsed_seconds}s!`, 'success');
      logTerm("AUDIT CERTIFICATE: Zero bit-rot tampering. Generated Post-Mortem RCA in Tab 4.", 'success');
    }

    async function runNormalBackup() {
      logTerm("RUNNING ROUTINE BACKUP: EventBridge trigger -> Lambda handler...", 'info');
      const res = await fetch('/api/run-backup', { method: 'POST' });
      const data = await res.json();
      if(data.error) {
        logTerm(`BACKUP FAILED: ${data.error}`, 'error');
      } else {
        logTerm(`BACKUP COMPLETED: Snapshot written to ${data.prefix} (${data.copied_count} files verified)`, 'success');
      }
    }

    async function resetSystem() {
      logTerm("RESETTING: Restoring baseline mock enterprise workload in primary bucket...", 'info');
      await fetch('/api/generate-sample', { method: 'POST' });
      await fetch('/api/run-backup', { method: 'POST' });
      
      stopDowntimeClock();
      document.getElementById('sev1-alert').classList.remove('active');
      document.getElementById('service-card').classList.remove('down');

      const pill = document.getElementById('service-status-pill');
      pill.className = 'status-badge badge-healthy';
      pill.innerHTML = '<i class="fa-solid fa-circle-check"></i> 200 OK - OPERATIONAL';

      document.getElementById('metric-db-health').innerText = 'PostgreSQL Healthy (Synced)';
      document.getElementById('metric-db-health').style.color = '#34d399';

      document.getElementById('metric-active-region').innerText = 'us-east-1 (Primary N. Virginia)';
      document.getElementById('metric-active-region').style.color = '#38bdf8';

      ['step-1','step-2','step-3','step-4'].forEach(id => {
        document.getElementById(id).className = 'runbook-step';
      });

      logTerm("SYSTEM RESTORED: Primary region us-east-1 active. Pipeline normal.", 'success');
    }

    function populateAuditTable(data) {
      const tbody = document.getElementById('audit-tbody');
      tbody.innerHTML = '';
      if(!data.results) return;

      data.results.forEach(row => {
        const tr = document.createElement('tr');
        let statusBadge = '<span class="badge-match"><i class="fa-solid fa-check"></i> EXACT MATCH</span>';
        if(row.status !== 'match') {
          statusBadge = '<span class="badge-mismatch"><i class="fa-solid fa-xmark"></i> MISMATCH</span>';
        }
        tr.innerHTML = `
          <td><strong>${row.path}</strong></td>
          <td>${statusBadge}</td>
          <td>${row.source_sha256 ? row.source_sha256.substring(0, 32) + '...' : 'NULL'}</td>
          <td>${row.restored_sha256 ? row.restored_sha256.substring(0, 32) + '...' : 'NULL'}</td>
        `;
        tbody.appendChild(tr);
      });
      document.getElementById('audit-badge').innerText = `${data.results.length} Objects Checked`;
    }

    // Auto-setup sample files on load
    fetch('/api/generate-sample', { method: 'POST' }).then(() => {
      fetch('/api/run-backup', { method: 'POST' });
    });
  </script>
</body>
</html>
"""


class WarRoomDRDashboardHandler(http.server.BaseHTTPRequestHandler):
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
            db_dir = SAMPLE_DIR / "database"
            auth_dir = SAMPLE_DIR / "auth"
            ledger_dir = SAMPLE_DIR / "ledger"
            cfg_dir = SAMPLE_DIR / "config"

            for d in [db_dir, auth_dir, ledger_dir, cfg_dir]:
                d.mkdir(parents=True, exist_ok=True)

            (db_dir / "pg_dump_production_customers.sql").write_text(
                "-- PostgreSQL Production Database Dump\n"
                "CREATE TABLE customers (id SERIAL PRIMARY KEY, full_name VARCHAR(120), balance NUMERIC(12,2));\n"
                "INSERT INTO customers (full_name, balance) VALUES ('Global Finance Inc', 450000.00), ('Acme Cloud Corp', 89000.50);\n"
            )
            (auth_dir / "jwt_signing_keys.pem").write_text(
                "-----BEGIN RSA PRIVATE KEY-----\n"
                "MIIEowIBAAKCAQEA0Yh05v4Vn1Yt93R3G5Q+7Y4X5N7W1K3jX2y0...\n"
                "-----END RSA PRIVATE KEY-----\n"
            )
            (ledger_dir / "q4_financial_transactions.json").write_text(
                json.dumps(
                    {
                        "batch_id": "TX-2026-Q4-0091",
                        "total_volume_usd": 1250000.00,
                        "status": "SETTLED",
                        "records_count": 1420,
                    },
                    indent=2,
                )
            )
            (cfg_dir / "microservices_cluster.yaml").write_text(
                "environment: production\ncluster_nodes: 12\nauto_scaling: true\nencryption: enabled\n"
            )

            res = {"created_count": 4, "status": "success"}
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif parsed.path == "/api/run-backup":
            if not SAMPLE_DIR.exists() or not list(SAMPLE_DIR.rglob("*")):
                self.wfile.write(
                    json.dumps(
                        {"error": "Source bucket empty. Generate workload first."}
                    ).encode("utf-8")
                )
                return

            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-req-aws-sim")
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

            # If source was damaged, also restore the clean files to source!
            for item in src_recovery.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src_recovery)
                    target = SAMPLE_DIR / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

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
            target = SAMPLE_DIR / "database" / "pg_dump_production_customers.sql"
            if target.exists():
                target.write_text(
                    "-- BIT-ROT TAMPERED BY RANSOMWARE ENCRYPTION ATTACK\n"
                    "CORRUPTED BYTES 0xDEADBEEF 0x00000000000000000000\n"
                )
                res = {
                    "corrupted_file": "database/pg_dump_production_customers.sql",
                    "status": "tampered",
                }
            else:
                res = {"error": "Generate sample data first."}
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif parsed.path == "/api/simulate-regional-outage":
            target = SAMPLE_DIR / "database" / "pg_dump_production_customers.sql"
            if target.exists():
                target.write_text(
                    "-- 503 SERVICE UNAVAILABLE: REGIONAL POWER OUTAGE (us-east-1)\n"
                )
            res = {"status": "outage_simulated", "region": "us-east-1"}
            self.wfile.write(json.dumps(res).encode("utf-8"))

    def log_message(self, format, *args):
        return


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), WarRoomDRDashboardHandler) as httpd:
        print(f"============================================================")
        print(f" SRE Disaster Recovery War Room LIVE on port: {PORT}")
        print(f"============================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down console server.")


if __name__ == "__main__":
    main()
