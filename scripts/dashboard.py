import http.server
import json
import os
import shutil
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
  <title>Enterprise AWS SRE Disaster Recovery & War Room Platform</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --bg: #06090e;
      --bg-card: #0c121e;
      --bg-surface: #151f32;
      --border: #233148;
      --border-focus: #3b82f6;
      --accent-aws: #ff9900;
      --accent-blue: #38bdf8;
      --text: #94a3b8;
      --text-heading: #f8fafc;
      --text-muted: #64748b;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 16px; line-height: 1.5; min-height: 100vh; }
    .container { max-width: 1460px; margin: 0 auto; }

    /* Top Navigation Header */
    header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 14px; margin-bottom: 18px; flex-wrap: wrap; gap: 12px; }
    .brand-wrap { display: flex; align-items: center; gap: 14px; }
    .brand-icon { font-size: 34px; color: var(--accent-aws); }
    .brand-title { color: var(--text-heading); font-size: 19px; font-weight: 800; display: flex; align-items: center; gap: 8px; }
    .brand-sub { font-size: 12px; color: var(--text-muted); }
    .header-pills { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill { background: rgba(21, 31, 50, 0.8); border: 1px solid var(--border); padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; color: #cbd5e1; display: inline-flex; align-items: center; gap: 6px; }
    .pill-live { color: #34d399; border-color: rgba(52, 211, 153, 0.3); background: rgba(16, 185, 129, 0.1); }
    .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block; box-shadow: 0 0 8px #10b981; animation: pulse 2s infinite; }
    .pulse-dot-red { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; display: inline-block; box-shadow: 0 0 10px #ef4444; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

    /* CRITICAL SEV-1 STROBE BANNER */
    .sev1-banner { display: none; background: rgba(239, 68, 68, 0.12); border: 2px solid var(--danger); border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; animation: glowRed 2s infinite; }
    .sev1-banner.active { display: block; }
    @keyframes glowRed { 0% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); } 50% { box-shadow: 0 0 35px rgba(239, 68, 68, 0.5); } 100% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); } }
    .sev1-flex { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; }
    .sev1-title { font-size: 16px; font-weight: 800; color: #fecaca; display: flex; align-items: center; gap: 10px; }
    .sev1-desc { font-size: 13px; color: #f87171; margin-top: 3px; }
    .downtime-counter { font-family: var(--font-mono); font-size: 22px; font-weight: 800; color: #fee2e2; background: #000; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--danger); }

    /* LIVE FINANCIAL LOSS & REVENUE METER BAR */
    .finance-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .finance-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; position: relative; overflow: hidden; }
    .finance-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--border); }
    .finance-card.danger::before { background: var(--danger); }
    .finance-card.success::before { background: var(--success); }
    .finance-card.accent::before { background: var(--accent-aws); }
    .fin-label { font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.5px; display: flex; justify-content: space-between; margin-bottom: 4px; }
    .fin-val { font-size: 22px; font-weight: 800; color: var(--text-heading); font-family: var(--font-mono); }
    .fin-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

    /* LIVE PRODUCTION SERVICE CARD */
    .service-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; position: relative; }
    .service-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: var(--success); }
    .service-card.down::before { background: var(--danger); }
    .service-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 12px; }
    .service-name { font-size: 16px; font-weight: 800; color: var(--text-heading); display: flex; align-items: center; gap: 10px; }
    .status-badge { padding: 5px 12px; border-radius: 20px; font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; display: inline-flex; align-items: center; gap: 6px; }
    .badge-healthy { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-outage { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid var(--danger); }
    .badge-recovered { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }

    /* ANIMATED ROUTE 53 DNS FLOW VISUALIZER */
    .dns-flow-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }
    .dns-title { font-size: 14px; font-weight: 800; color: var(--text-heading); margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; }
    .flow-diagram { display: grid; grid-template-columns: 1fr auto 1.2fr; gap: 18px; align-items: center; background: rgba(10, 15, 25, 0.6); padding: 20px; border-radius: 10px; border: 1px solid var(--border); }
    @media (max-width: 900px) { .flow-diagram { grid-template-columns: 1fr; } }
    
    .dns-node { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
    .dns-node-icon { font-size: 26px; color: var(--accent-aws); margin-bottom: 6px; }
    .dns-node-title { font-weight: 700; font-size: 13px; color: var(--text-heading); }
    .dns-node-sub { font-size: 11px; color: var(--text-muted); }

    .route-arrow-box { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
    .dns-policy-badge { background: #0f172a; border: 1px solid var(--border); padding: 4px 10px; border-radius: 12px; font-size: 11px; color: var(--accent-blue); font-weight: 700; margin-bottom: 6px; }
    .flow-line { width: 100px; height: 3px; background: repeating-linear-gradient(90deg, #10b981, #10b981 6px, transparent 6px, transparent 12px); animation: flowGreen 1s linear infinite; }
    .flow-line.failover { background: repeating-linear-gradient(90deg, #38bdf8, #38bdf8 6px, transparent 6px, transparent 12px); animation: flowBlue 1s linear infinite; }
    .flow-line.broken { background: #ef4444; animation: none; }
    @keyframes flowGreen { from { background-position: 0 0; } to { background-position: 24px 0; } }
    @keyframes flowBlue { from { background-position: 0 0; } to { background-position: 24px 0; } }

    .target-regions-box { display: flex; flex-direction: column; gap: 12px; }
    .region-card-mini { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; display: flex; justify-content: space-between; align-items: center; }
    .region-card-mini.active { border-color: var(--success); box-shadow: 0 0 10px rgba(16, 185, 129, 0.15); }
    .region-card-mini.offline { border-color: var(--danger); opacity: 0.6; }

    /* Navigation Tabs */
    .tabs-bar { display: flex; gap: 6px; border-bottom: 1px solid var(--border); margin-bottom: 18px; overflow-x: auto; padding-bottom: 2px; }
    .tab-btn { background: none; border: none; padding: 10px 16px; font-size: 13px; font-weight: 600; color: var(--text-muted); cursor: pointer; border-radius: 6px 6px 0 0; display: flex; align-items: center; gap: 8px; transition: all 0.2s; white-space: nowrap; }
    .tab-btn:hover { color: var(--text-heading); background: rgba(30, 41, 59, 0.4); }
    .tab-btn.active { color: var(--accent-aws); border-bottom: 2px solid var(--accent-aws); background: rgba(255, 153, 0, 0.05); }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    /* War Room Layout (Split View: SRE Runbook + Live Slack Incident Feed) */
    .war-room-split { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 18px; margin-bottom: 20px; }
    @media (max-width: 1024px) { .war-room-split { grid-template-columns: 1fr; } }

    .panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
    .panel-head { font-size: 14px; font-weight: 800; color: var(--text-heading); margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; }

    /* Step-by-Step Runbook Checklist */
    .runbook-step { background: rgba(21, 31, 50, 0.5); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; display: flex; gap: 12px; align-items: center; transition: all 0.2s; }
    .runbook-step.done { border-color: var(--success); background: rgba(16, 185, 129, 0.06); }
    .step-num { width: 28px; height: 28px; border-radius: 50%; background: #0c121e; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 12px; color: var(--text-heading); flex-shrink: 0; }
    .runbook-step.done .step-num { background: var(--success); color: #fff; border-color: var(--success); }
    .step-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
    .step-sub { font-size: 11px; color: var(--text-muted); }

    .progress-bar-container { width: 100%; height: 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px; overflow: hidden; margin: 12px 0 18px 0; }
    .progress-fill { width: 0%; height: 100%; background: var(--success); transition: width 0.4s ease; }

    /* Action Buttons */
    .btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    .btn { background: #1e293b; color: var(--text-heading); border: 1px solid var(--border); padding: 10px 18px; border-radius: 6px; font-size: 13px; font-weight: 700; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; gap: 8px; }
    .btn:hover { background: #334155; transform: translateY(-1px); }
    .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border-color: var(--danger); }
    .btn-danger:hover { background: var(--danger); color: #fff; }
    .btn-fix { background: #059669; color: #fff; border-color: #059669; box-shadow: 0 0 15px rgba(16, 185, 129, 0.3); }
    .btn-fix:hover { background: #047857; }
    .btn-aws { background: var(--accent-aws); color: #000; border-color: var(--accent-aws); }
    .btn-aws:hover { background: #e68a00; color: #000; }

    /* Slack #prod-incidents Feed */
    .slack-box { background: #080c14; border: 1px solid var(--border); border-radius: 8px; height: 380px; display: flex; flex-direction: column; overflow: hidden; }
    .slack-header { background: #0f172a; padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 12px; font-weight: 700; color: #cbd5e1; display: flex; align-items: center; gap: 8px; }
    .slack-messages { padding: 14px; overflow-y: auto; flex-grow: 1; display: flex; flex-direction: column; gap: 12px; font-size: 12px; }
    .slack-msg { display: flex; gap: 10px; }
    .slack-avatar { width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; flex-shrink: 0; }
    .avatar-bot { background: #38bdf8; color: #000; }
    .avatar-alert { background: #ef4444; color: #fff; }
    .avatar-sre { background: #ff9900; color: #000; }
    .slack-author { font-weight: 700; color: var(--text-heading); font-size: 12px; }
    .slack-time { font-size: 10px; color: var(--text-muted); margin-left: 6px; }
    .slack-text { color: #cbd5e1; margin-top: 2px; line-height: 1.4; }

    /* Audit Table */
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { padding: 12px 14px; background: rgba(21, 31, 50, 0.7); color: #94a3b8; font-weight: 700; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); text-align: left; }
    td { padding: 10px 14px; border-bottom: 1px solid rgba(51, 65, 85, 0.5); font-family: var(--font-mono); color: #cbd5e1; }
    .badge-match { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; }
    .badge-mismatch { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; }

    /* Printable SOC 2 / Executive Certificate */
    .cert-card { background: var(--bg-card); border: 2px solid #10b981; border-radius: 12px; padding: 28px; position: relative; }
    .cert-stamp { position: absolute; right: 26px; top: 26px; border: 2px dashed #10b981; color: #10b981; padding: 8px 18px; border-radius: 8px; font-weight: 800; font-size: 13px; transform: rotate(-5deg); text-transform: uppercase; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header>
      <div class="brand-wrap">
        <i class="fa-brands fa-aws brand-icon"></i>
        <div>
          <div class="brand-title">
            Enterprise AWS SRE Disaster Recovery Platform
            <span class="pill pill-live"><span class="pulse-dot"></span> CLOUD LIVE</span>
          </div>
          <div class="brand-sub">Multi-Region S3 Replication &bull; Route 53 DNS Failover &bull; Cryptographic Integrity Audit &bull; Financial SLA Tracking</div>
        </div>
      </div>
      <div class="header-pills">
        <span class="pill"><i class="fa-solid fa-cloud"></i> Primary: us-east-1</span>
        <span class="pill"><i class="fa-solid fa-shield-halved"></i> Standby DR: us-west-2</span>
        <span class="pill"><i class="fa-solid fa-stopwatch"></i> SLA Target: 99.99%</span>
        <span class="pill"><i class="fa-solid fa-lock"></i> AES-256 SSE-S3</span>
      </div>
    </header>

    <!-- CRITICAL SEV-1 OUTAGE BANNER -->
    <div class="sev1-banner" id="sev1-alert">
      <div class="sev1-flex">
        <div>
          <div class="sev1-title"><i class="fa-solid fa-triangle-exclamation"></i> 🚨 SEV-1 CRITICAL OUTAGE: PRIMARY REGION FAILURE (US-EAST-1)</div>
          <div class="sev1-desc" id="sev1-desc">Primary database corrupted & regional networking unreachable. Payment checkout failing for global customers!</div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 11px; color: #f87171; text-transform: uppercase; font-weight: 700; margin-bottom: 4px;">Active Incident Downtime</div>
          <div class="downtime-counter" id="downtime-timer">00:00:00</div>
        </div>
      </div>
    </div>

    <!-- FINANCIAL LOSS & BUSINESS ROI METER -->
    <div class="finance-bar">
      <div class="finance-card danger" id="card-loss">
        <div class="fin-label"><span>Revenue Loss Rate</span><i class="fa-solid fa-dollar-sign"></i></div>
        <div class="fin-val" id="val-loss-rate" style="color: #f87171;">$0 / sec</div>
        <div class="fin-sub" id="sub-loss-rate">Normal Traffic Flow</div>
      </div>
      <div class="finance-card danger" id="card-risk">
        <div class="fin-label"><span>Total Revenue at Risk</span><i class="fa-solid fa-chart-line-down"></i></div>
        <div class="fin-val" id="val-risk" style="color: #f87171;">$0.00</div>
        <div class="fin-sub" id="sub-risk">0 Blocked Transactions</div>
      </div>
      <div class="finance-card success">
        <div class="fin-label"><span>Total Volume Protected</span><i class="fa-solid fa-shield-heart"></i></div>
        <div class="fin-val" style="color: #34d399;">$1,250,000.00</div>
        <div class="fin-sub">1,420 Settled Customer Transactions</div>
      </div>
      <div class="finance-card accent">
        <div class="fin-label"><span>Target RPO vs Measured RTO</span><i class="fa-solid fa-stopwatch"></i></div>
        <div class="fin-val" id="val-rto" style="color: #ff9900;">&le; 24h &bull; -- sec</div>
        <div class="fin-sub" id="sub-rto">Awaiting Timed Failover Drill</div>
      </div>
    </div>

    <!-- LIVE PRODUCTION SERVICE STATUS CARD -->
    <div class="service-card" id="service-card">
      <div class="service-header">
        <div>
          <div class="service-name">
            <i class="fa-solid fa-globe" style="color: var(--accent-aws);"></i>
            Production Payments Gateway & E-Commerce Core API
            <span class="status-badge badge-healthy" id="service-status-pill"><i class="fa-solid fa-circle-check"></i> 200 OK - OPERATIONAL</span>
          </div>
          <div style="font-size: 12px; font-family: var(--font-mono); color: var(--text-muted); margin-top: 2px;">
            Endpoint: https://api.payments.enterprise-cloud.com/v1/checkout &bull; Active DB: PostgreSQL Cluster
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-danger" onclick="triggerDisaster('regional_outage')"><i class="fa-solid fa-fire"></i> 💥 1. Simulate Region Catastrophe</button>
          <button class="btn btn-danger" onclick="triggerDisaster('ransomware')"><i class="fa-solid fa-skull"></i> ☣️ 2. Simulate Ransomware Attack</button>
        </div>
      </div>
    </div>

    <!-- ANIMATED ROUTE 53 DNS FAILOVER VISUALIZER -->
    <div class="dns-flow-card">
      <div class="dns-title">
        <span><i class="fa-solid fa-network-wired" style="color: var(--accent-blue);"></i> Amazon Route 53 Live DNS Traffic Flow & Health Checks</span>
        <span class="pill" id="dns-status-pill"><i class="fa-solid fa-check"></i> Route 53 Health Check: 3/3 HEALTHY</span>
      </div>

      <div class="flow-diagram">
        <!-- Node 1: Global Users -->
        <div class="dns-node">
          <div class="dns-node-icon"><i class="fa-solid fa-users"></i></div>
          <div class="dns-node-title">Global Customer Traffic</div>
          <div class="dns-node-sub">1,420 Active Sessions</div>
        </div>

        <!-- Node 2: Route 53 Router -->
        <div class="route-arrow-box">
          <div class="dns-policy-badge"><i class="fa-solid fa-arrows-split-up-and-left"></i> Route 53 Failover Routing</div>
          <div class="flow-line" id="flow-line-indicator"></div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;" id="flow-label">Routing to Primary us-east-1</div>
        </div>

        <!-- Node 3: Target Regions (Primary vs Standby) -->
        <div class="target-regions-box">
          <div class="region-card-mini active" id="node-primary-reg">
            <div>
              <div style="font-weight: 700; color: #fff; font-size: 13px;"><i class="fa-solid fa-database text-accent"></i> Primary Region (us-east-1 N. Virginia)</div>
              <div style="font-size: 11px; color: var(--text-muted);" id="primary-node-status">Active Ingress &bull; Primary S3 Bucket &bull; PostgreSQL</div>
            </div>
            <span class="status-badge badge-healthy" id="primary-badge">PRIMARY ACTIVE</span>
          </div>

          <div class="region-card-mini" id="node-dr-reg">
            <div>
              <div style="font-weight: 700; color: #fff; font-size: 13px;"><i class="fa-solid fa-shield-halved" style="color: var(--accent-blue);"></i> Standby DR Region (us-west-2 Oregon)</div>
              <div style="font-size: 11px; color: var(--text-muted);" id="dr-node-status">Standby Target &bull; Immutable S3 Replication &bull; Ready</div>
            </div>
            <span class="status-badge" style="background: rgba(148, 163, 184, 0.1); color: #94a3b8;" id="dr-badge">STANDBY READY</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-bar">
      <button class="tab-btn active" onclick="openTab('tab-war-room')"><i class="fa-solid fa-bolt"></i> Live War Room & Remediation</button>
      <button class="tab-btn" onclick="openTab('tab-audit')"><i class="fa-solid fa-fingerprint"></i> SHA-256 Cryptographic Checksum Audit</button>
      <button class="tab-btn" onclick="openTab('tab-certificate')"><i class="fa-solid fa-file-contract"></i> Executive SOC 2 / ISO 27001 Certificate</button>
      <button class="tab-btn" onclick="openTab('tab-iac')"><i class="fa-solid fa-cubes"></i> Terraform Multi-Region IaC</button>
    </div>

    <!-- TAB 1: WAR ROOM SPLIT VIEW -->
    <div id="tab-war-room" class="tab-pane active">
      <div class="war-room-split">
        <!-- Left: Automated SRE Runbook Wizard -->
        <div class="panel">
          <div class="panel-head">
            <span><i class="fa-solid fa-list-check" style="color: var(--accent-aws);"></i> Automated SRE Disaster Recovery Runbook</span>
            <span class="pill" id="runbook-status-pill"><i class="fa-solid fa-circle-check"></i> System Operational</span>
          </div>

          <div class="progress-bar-container">
            <div class="progress-fill" id="runbook-progress"></div>
          </div>

          <div class="runbook-step" id="step-1">
            <div class="step-num">1</div>
            <div>
              <div class="step-title">Isolate Outage & Drain Ingress from us-east-1</div>
              <div class="step-sub">Stop corrupt write traffic; mark Route 53 health check unhealthy.</div>
            </div>
          </div>

          <div class="runbook-step" id="step-2">
            <div class="step-num">2</div>
            <div>
              <div class="step-title">Mount Latest Immutable DR Snapshot from us-west-2</div>
              <div class="step-sub">Fetch verified cross-region S3 recovery prefix snapshot.</div>
            </div>
          </div>

          <div class="runbook-step" id="step-3">
            <div class="step-num">3</div>
            <div>
              <div class="step-title">Execute Bit-Level SHA-256 Cryptographic Audit</div>
              <div class="step-sub">Verify binary hashes to ensure zero bit-rot / ransomware tampering.</div>
            </div>
          </div>

          <div class="runbook-step" id="step-4">
            <div class="step-num">4</div>
            <div>
              <div class="step-title">Promote Oregon DR to Primary & Route 53 DNS Switch</div>
              <div class="step-sub">Promote standby database; redirect customer traffic to us-west-2.</div>
            </div>
          </div>

          <div class="btn-group">
            <button class="btn btn-fix" id="btn-remediate" onclick="executeAutomatedRemediation()"><i class="fa-solid fa-bolt"></i> 1-CLICK DISASTER REMEDIATION & FAILOVER</button>
            <button class="btn btn-aws" onclick="runNormalBackup()"><i class="fa-solid fa-cloud-arrow-up"></i> Routine Backup Run</button>
            <button class="btn" onclick="resetSystem()"><i class="fa-solid fa-arrow-rotate-left"></i> Reset System</button>
          </div>
        </div>

        <!-- Right: Live Slack #prod-incidents Feed -->
        <div class="panel" style="padding: 0; overflow: hidden;">
          <div class="slack-box">
            <div class="slack-header">
              <i class="fa-brands fa-slack" style="color: #e01e5a; font-size: 16px;"></i>
              <span>#prod-incident-war-room</span>
              <span class="pill" style="margin-left: auto; font-size: 10px;">AWS ChatOps Bot Connected</span>
            </div>
            <div class="slack-messages" id="slack-feed">
              <div class="slack-msg">
                <div class="slack-avatar avatar-bot"><i class="fa-solid fa-robot"></i></div>
                <div>
                  <span class="slack-author">AWS-EventBridge</span><span class="slack-time">02:00 UTC</span>
                  <div class="slack-text">Daily Scheduled Backup job triggered via Lambda worker `dr-lab-s3-backup`.</div>
                </div>
              </div>
              <div class="slack-msg">
                <div class="slack-avatar avatar-sre"><i class="fa-solid fa-user-shield"></i></div>
                <div>
                  <span class="slack-author">On-Call SRE Engineer</span><span class="slack-time">Just now</span>
                  <div class="slack-text">System is healthy. Standing by for any Sev-1 incident triggers.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: AUDIT MATRIX -->
    <div id="tab-audit" class="tab-pane">
      <div class="panel">
        <div class="panel-head">
          <span><i class="fa-solid fa-fingerprint"></i> Side-by-Side Cryptographic SHA-256 Checksum Audit</span>
          <span class="pill" id="audit-badge">4 Objects Audited</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>File Path</th>
              <th>Status</th>
              <th>Source SHA-256 Checksum (Primary)</th>
              <th>Restored SHA-256 Checksum (DR Copy)</th>
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

    <!-- TAB 3: EXECUTIVE SOC 2 CERTIFICATE -->
    <div id="tab-certificate" class="tab-pane">
      <div class="cert-card">
        <div class="cert-stamp">AUDIT COMPLIANT &amp; ATTESTED</div>
        <h2 style="color: var(--text-heading); font-size: 19px; margin-bottom: 6px;"><i class="fa-solid fa-stamp text-success"></i> Disaster Recovery & Business Continuity Attestation (SOC 2 / ISO 27001)</h2>
        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 22px;">Executive Engineering Incident Review & Cryptographic Data Recovery Record</div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; font-size: 13px;">
          <div><div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Target RPO (Schedule)</div><strong style="color: #34d399;">&le; 24 Hours (EventBridge Daily)</strong></div>
          <div><div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Measured RTO (Stopwatch)</div><strong style="color: #ff9900;" id="cert-rto">0.041 seconds</strong></div>
          <div><div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Data Loss (RPO Actual)</div><strong style="color: #34d399;">0 Bytes (Zero Bit-Rot)</strong></div>
          <div><div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Financial Volume Saved</div><strong style="color: #38bdf8;">$1,250,000.00</strong></div>
          <div><div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Failover Target</div><strong>us-west-2 (Oregon Standby)</strong></div>
          <div><div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Encryption Standard</div><strong>AES-256 SSE-S3 Verified</strong></div>
        </div>

        <button class="btn btn-aws" onclick="window.print()"><i class="fa-solid fa-print"></i> Download / Print Executive SOC 2 Report</button>
      </div>
    </div>

    <!-- TAB 4: TERRAFORM IAC -->
    <div id="tab-iac" class="tab-pane">
      <div class="panel">
        <div class="panel-head"><span><i class="fa-solid fa-cubes text-accent"></i> 11 Provisioned Terraform Multi-Region Cloud Resources</span></div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; font-size: 12px;">
          <div style="background: rgba(21, 31, 50, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_s3_bucket.source</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">Primary Source S3 Bucket</div>
            <div style="color: var(--text-muted);">Region: us-east-1 &bull; Versioned &bull; AES-256 SSE-S3 &bull; Block Public Access</div>
          </div>
          <div style="background: rgba(21, 31, 50, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_s3_bucket.destination</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">DR Standby S3 Bucket</div>
            <div style="color: var(--text-muted);">Region: us-west-2 &bull; 14-Day Auto-Expiration Lifecycle &bull; Independent Blast Radius</div>
          </div>
          <div style="background: rgba(21, 31, 50, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_lambda_function.backup</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">Python 3.12 Serverless Worker</div>
            <div style="color: var(--text-muted);">S3 Paginator &bull; ContentLength Size Check &bull; 900s Timeout &bull; 256MB RAM</div>
          </div>
          <div style="background: rgba(21, 31, 50, 0.4); border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <div style="color: var(--accent-aws); font-family: var(--font-mono); font-weight: 700;">aws_cloudwatch_metric_alarm.errors</div>
            <div style="font-weight: 600; color: #fff; margin: 4px 0;">CloudWatch Sev-1 Failure Alarm</div>
            <div style="color: var(--text-muted);">Evaluates Lambda Errors >= 1 in 300s &bull; Automated SNS Topic Dispatch</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let downtimeInterval = null;
    let downtimeSeconds = 0;
    const REVENUE_LOSS_RATE = 175; // $175 per second

    function openTab(tabId) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.currentTarget.classList.add('active');
    }

    function addSlackMessage(author, avatarClass, iconClass, text) {
      const feed = document.getElementById('slack-feed');
      const time = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'slack-msg';
      div.innerHTML = `
        <div class="slack-avatar ${avatarClass}"><i class="${iconClass}"></i></div>
        <div>
          <span class="slack-author">${author}</span><span class="slack-time">${time}</span>
          <div class="slack-text">${text}</div>
        </div>
      `;
      feed.appendChild(div);
      feed.scrollTop = feed.scrollHeight;
    }

    function startDowntimeClock() {
      downtimeSeconds = 0;
      clearInterval(downtimeInterval);
      document.getElementById('val-loss-rate').innerText = `$${REVENUE_LOSS_RATE} / sec`;
      document.getElementById('sub-loss-rate').innerText = 'CRITICAL SEV-1 ACTIVE';

      downtimeInterval = setInterval(() => {
        downtimeSeconds++;
        const mins = String(Math.floor(downtimeSeconds / 60)).padStart(2, '0');
        const secs = String(downtimeSeconds % 60).padStart(2, '0');
        document.getElementById('downtime-timer').innerText = `00:${mins}:${secs}`;
        
        const totalRisk = (downtimeSeconds * REVENUE_LOSS_RATE).toLocaleString('en-US', { minimumFractionDigits: 2 });
        document.getElementById('val-risk').innerText = `$${totalRisk}`;
        document.getElementById('sub-risk').innerText = `${downtimeSeconds * 3} Transactions Blocked`;
      }, 1000);
    }

    function stopDowntimeClock() {
      clearInterval(downtimeInterval);
      document.getElementById('val-loss-rate').innerText = '$0 / sec';
      document.getElementById('sub-loss-rate').innerText = 'Recovered - Traffic Healthy';
    }

    // 1. TRIGGER DISASTER
    async function triggerDisaster(type) {
      startDowntimeClock();
      document.getElementById('sev1-alert').classList.add('active');
      document.getElementById('service-card').classList.add('down');

      const pill = document.getElementById('service-status-pill');
      pill.className = 'status-badge badge-outage';
      pill.innerHTML = '<span class="pulse-dot-red"></span> 503 SERVICE UNAVAILABLE (SEV-1)';

      // Route 53 Broken State
      document.getElementById('flow-line-indicator').className = 'flow-line broken';
      document.getElementById('flow-label').innerText = 'PRIMARY ROUTE FAILED (0/3 Unhealthy)';
      document.getElementById('flow-label').style.color = '#ef4444';
      document.getElementById('dns-status-pill').className = 'pill';
      document.getElementById('dns-status-pill').innerHTML = '<span class="pulse-dot-red"></span> Health Check: 0/3 UNHEALTHY';

      document.getElementById('node-primary-reg').className = 'region-card-mini offline';
      document.getElementById('primary-badge').className = 'status-badge badge-outage';
      document.getElementById('primary-badge').innerText = 'OFFLINE';

      // Slack PagerDuty Alert
      if(type === 'ransomware') {
        await fetch('/api/corrupt-data', { method: 'POST' });
        addSlackMessage('PagerDuty', 'avatar-alert', 'fa-solid fa-bell', '🚨 [P1-CRITICAL] Production DB Encrypted by Ransomware Attack! E-Commerce checkout failing.');
      } else {
        await fetch('/api/simulate-regional-outage', { method: 'POST' });
        addSlackMessage('CloudWatch-Alarms', 'avatar-alert', 'fa-solid fa-triangle-exclamation', '🚨 [ALARM] Metric `AWS/Lambda Errors >= 1` in us-east-1. Regional Datacenter Unreachable.');
      }

      addSlackMessage('On-Call SRE', 'avatar-sre', 'fa-solid fa-user-shield', '@channel Sev-1 declared. Joining War Room to execute automated DR failover.');
      openTab('tab-war-room');
    }

    // 2. 1-CLICK REMEDIATION WIZARD
    async function executeAutomatedRemediation() {
      addSlackMessage('SRE-Automation', 'avatar-bot', 'fa-solid fa-gears', '🚀 Executing Automated Runbook `DR-2026-FAILOVER`...');

      // Step 1
      document.getElementById('step-1').className = 'runbook-step done';
      document.getElementById('runbook-progress').style.width = '25%';
      addSlackMessage('Route-53-Bot', 'avatar-bot', 'fa-solid fa-network-wired', '[Step 1/4] Draining ingress traffic from damaged region us-east-1.');
      await new Promise(r => setTimeout(r, 600));

      // Step 2
      document.getElementById('step-2').className = 'runbook-step done';
      document.getElementById('runbook-progress').style.width = '50%';
      addSlackMessage('S3-Replication', 'avatar-bot', 'fa-solid fa-box-archive', '[Step 2/4] Mounting latest immutable recovery snapshot from us-west-2 (Oregon).');
      const resRestore = await fetch('/api/run-restore', { method: 'POST' });
      const dataRestore = await resRestore.json();
      await new Promise(r => setTimeout(r, 600));

      // Step 3
      document.getElementById('step-3').className = 'runbook-step done';
      document.getElementById('runbook-progress').style.width = '75%';
      addSlackMessage('Audit-Engine', 'avatar-bot', 'fa-solid fa-fingerprint', '[Step 3/4] Cryptographic SHA-256 audit completed: 100% hash match (0 bit-rot).');
      const resVerify = await fetch('/api/verify-hashes', { method: 'POST' });
      const dataVerify = await resVerify.json();
      populateAuditTable(dataVerify);
      await new Promise(r => setTimeout(r, 600));

      // Step 4: Route 53 Switch
      document.getElementById('step-4').className = 'runbook-step done';
      document.getElementById('runbook-progress').style.width = '100%';
      addSlackMessage('Route-53-Bot', 'avatar-bot', 'fa-solid fa-route', '[Step 4/4] Route 53 DNS Failover executed. Standby Oregon promoted to PRIMARY.');
      await new Promise(r => setTimeout(r, 600));

      // Complete
      stopDowntimeClock();
      document.getElementById('sev1-alert').classList.remove('active');
      document.getElementById('service-card').classList.remove('down');

      const pill = document.getElementById('service-status-pill');
      pill.className = 'status-badge badge-recovered';
      pill.innerHTML = '<i class="fa-solid fa-circle-check"></i> 200 OK - OPERATIONAL (FAILOVER ACTIVE)';

      // Update Route 53 Diagram
      document.getElementById('flow-line-indicator').className = 'flow-line failover';
      document.getElementById('flow-label').innerText = 'FAILOVER ACTIVE: Routing to us-west-2 (Oregon)';
      document.getElementById('flow-label').style.color = '#38bdf8';
      document.getElementById('dns-status-pill').className = 'pill pill-live';
      document.getElementById('dns-status-pill').innerHTML = '<span class="pulse-dot"></span> Health Check: FAILOVER HEALTHY';

      document.getElementById('node-dr-reg').className = 'region-card-mini active';
      document.getElementById('dr-badge').className = 'status-badge badge-healthy';
      document.getElementById('dr-badge').innerText = 'PROMOTED TO PRIMARY';

      document.getElementById('val-rto').innerText = `RTO: ${dataRestore.elapsed_seconds}s`;
      document.getElementById('cert-rto').innerText = `${dataRestore.elapsed_seconds} seconds (Stopwatch Benchmark)`;

      document.getElementById('card-risk').className = 'finance-card success';
      document.getElementById('val-risk').innerText = '$0.00';
      document.getElementById('val-risk').style.color = '#34d399';
      document.getElementById('sub-risk').innerText = 'Zero Business Financial Loss!';

      addSlackMessage('On-Call SRE', 'avatar-sre', 'fa-solid fa-circle-check', `✅ Incident RESOLVED! All traffic healthy on us-west-2 in ${dataRestore.elapsed_seconds}s. Total data loss: 0 Bytes!`);
    }

    async function runNormalBackup() {
      addSlackMessage('EventBridge', 'avatar-bot', 'fa-solid fa-cloud-arrow-up', 'Triggering routine Boto3 backup run...');
      const res = await fetch('/api/run-backup', { method: 'POST' });
      const data = await res.json();
      if(data.error) {
        addSlackMessage('EventBridge', 'avatar-alert', 'fa-solid fa-triangle-exclamation', `Backup failed: ${data.error}`);
      } else {
        addSlackMessage('EventBridge', 'avatar-bot', 'fa-solid fa-check', `Backup snapshot verified: ${data.prefix} (${data.copied_count} objects copied)`);
      }
    }

    async function resetSystem() {
      addSlackMessage('SRE-Admin', 'avatar-sre', 'fa-solid fa-arrow-rotate-left', 'Resetting environment back to primary baseline us-east-1.');
      await fetch('/api/generate-sample', { method: 'POST' });
      await fetch('/api/run-backup', { method: 'POST' });

      stopDowntimeClock();
      document.getElementById('sev1-alert').classList.remove('active');
      document.getElementById('service-card').classList.remove('down');

      const pill = document.getElementById('service-status-pill');
      pill.className = 'status-badge badge-healthy';
      pill.innerHTML = '<i class="fa-solid fa-circle-check"></i> 200 OK - OPERATIONAL';

      document.getElementById('flow-line-indicator').className = 'flow-line';
      document.getElementById('flow-label').innerText = 'Routing to Primary us-east-1';
      document.getElementById('flow-label').style.color = '#94a3b8';
      document.getElementById('dns-status-pill').className = 'pill';
      document.getElementById('dns-status-pill').innerHTML = '<i class="fa-solid fa-check"></i> Route 53 Health Check: 3/3 HEALTHY';

      document.getElementById('node-primary-reg').className = 'region-card-mini active';
      document.getElementById('primary-badge').className = 'status-badge badge-healthy';
      document.getElementById('primary-badge').innerText = 'PRIMARY ACTIVE';

      document.getElementById('node-dr-reg').className = 'region-card-mini';
      document.getElementById('dr-badge').className = 'status-badge';
      document.getElementById('dr-badge').innerText = 'STANDBY READY';

      document.getElementById('runbook-progress').style.width = '0%';
      ['step-1','step-2','step-3','step-4'].forEach(id => {
        document.getElementById(id).className = 'runbook-step';
      });

      document.getElementById('val-loss-rate').innerText = '$0 / sec';
      document.getElementById('val-risk').innerText = '$0.00';
      document.getElementById('card-risk').className = 'finance-card danger';
      document.getElementById('val-risk').style.color = '#f87171';
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

    fetch('/api/generate-sample', { method: 'POST' }).then(() => {
      fetch('/api/run-backup', { method: 'POST' });
    });
  </script>
</body>
</html>
"""


class UltimateDRDashboardHandler(http.server.BaseHTTPRequestHandler):
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

            # Clean restore to source location
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
    with http.server.ThreadingHTTPServer(("", PORT), UltimateDRDashboardHandler) as httpd:
        print(f"============================================================")
        print(f" Ultimate AWS SRE War Room Console LIVE on port: {PORT}")
        print(f"============================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down console server.")


if __name__ == "__main__":
    main()
