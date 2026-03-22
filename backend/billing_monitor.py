"""
billing_monitor.py
Place in: backend/billing_monitor.py

Reads AWS credentials directly from .env file.
Fetches live billing from AWS Cost Explorer.
Sends SMTP email alert when thresholds are crossed.
"""

import os
import sys
import json
import smtplib
import boto3
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Always load .env from backend root
load_dotenv(Path(__file__).parent / ".env")

THRESHOLDS_FILE = Path(__file__).parent / "billing_threshold.json"

DEFAULT_THRESHOLDS = {
    "TOTAL": 50.0,
    "Amazon EC2": 20.0,
    "AWS Amplify": 10.0,
    "Amazon S3": 5.0,
    "Amazon RDS": 15.0,
    "AWS Lambda": 5.0,
    "Amazon CloudFront": 5.0,
    "Amazon DynamoDB": 5.0,
    "AWS Data Transfer": 3.0,
    "Amazon CloudWatch": 3.0,
    "Amazon Route 53": 2.0,
}


# ── Credentials — reads directly from .env ────────────────────

def get_credentials() -> dict:
    """Read AWS credentials from .env file."""
    key    = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1").strip()

    if not key or not secret:
        raise Exception(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in backend/.env"
        )

    print(f"🔐 [CREDS] Using key: {key[:8]}...{key[-4:]} | region: {region}")
    return {"key": key, "secret": secret, "region": region}


def get_ce_client(creds: dict):
    """Cost Explorer is always us-east-1 regardless of your region."""
    return boto3.client(
        "ce",
        aws_access_key_id=creds["key"],
        aws_secret_access_key=creds["secret"],
        region_name="us-east-1"
    )


def get_sts_identity(creds: dict) -> dict:
    """Verify credentials and return account identity."""
    sts = boto3.client(
        "sts",
        aws_access_key_id=creds["key"],
        aws_secret_access_key=creds["secret"],
        region_name="us-east-1"
    )
    return sts.get_caller_identity()


# ── Threshold Config ──────────────────────────────────────────

def load_thresholds() -> dict:
    if THRESHOLDS_FILE.exists():
        with open(THRESHOLDS_FILE) as f:
            return json.load(f)
    return DEFAULT_THRESHOLDS.copy()


def save_thresholds(thresholds: dict):
    with open(THRESHOLDS_FILE, "w") as f:
        json.dump(thresholds, f, indent=2)
    print(f"💾 Thresholds saved to {THRESHOLDS_FILE}")


# ── Live Billing Fetch ────────────────────────────────────────

def fetch_billing_data(ce) -> dict:
    """Fetch live billing from AWS Cost Explorer for current month + last 7 days."""
    today = datetime.today()
    start = today.replace(day=1).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")

    if start == end:
        # first day of month — go back 1 day
        start = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"📅 Fetching billing: {start} → {end}")

    # Monthly total
    total_resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"]
    )
    total_cost = 0.0
    currency   = "USD"
    if total_resp["ResultsByTime"]:
        total_cost = float(total_resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
        currency   = total_resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Unit"]

    # By service
    svc_resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
    )
    services = {}
    if svc_resp["ResultsByTime"]:
        for group in svc_resp["ResultsByTime"][0]["Groups"]:
            name = group["Keys"][0]
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if cost > 0:
                services[name] = round(cost, 6)

    # Daily last 7 days
    daily_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    daily_resp  = ce.get_cost_and_usage(
        TimePeriod={"Start": daily_start, "End": end},
        Granularity="DAILY",
        Metrics=["UnblendedCost"]
    )
    daily = []
    for period in daily_resp["ResultsByTime"]:
        daily.append({
            "date": period["TimePeriod"]["Start"],
            "cost": round(float(period["Total"]["UnblendedCost"]["Amount"]), 6)
        })

    return {
        "total":      round(total_cost, 6),
        "currency":   currency,
        "services":   services,
        "daily":      daily,
        "period":     f"{start} to {end}",
        "checked_at": datetime.now().isoformat()
    }


# ── Threshold Checking ────────────────────────────────────────

def check_thresholds(billing_data: dict, thresholds: dict) -> list:
    breaches = []

    total_limit = thresholds.get("TOTAL")
    if total_limit and billing_data["total"] >= total_limit:
        breaches.append({
            "service":   "Total AWS Bill",
            "current":   billing_data["total"],
            "threshold": total_limit,
            "currency":  billing_data["currency"],
            "percent":   round((billing_data["total"] / total_limit) * 100, 1)
        })

    for service, cost in billing_data["services"].items():
        limit = thresholds.get(service)
        if limit and cost >= limit:
            breaches.append({
                "service":   service,
                "current":   cost,
                "threshold": limit,
                "currency":  billing_data["currency"],
                "percent":   round((cost / limit) * 100, 1)
            })

    return breaches


# ── Email Alert ───────────────────────────────────────────────

def build_email_html(billing: dict, breaches: list, thresholds: dict) -> str:
    breach_rows = ""
    for b in breaches:
        pct = min(b["percent"], 100)
        breach_rows += f"""
        <tr style="background:#fff3cd;">
          <td style="padding:10px;border:1px solid #ffc107;font-weight:600;">⚠️ {b['service']}</td>
          <td style="padding:10px;border:1px solid #ffc107;color:#dc3545;font-weight:700;">${b['current']:.4f}</td>
          <td style="padding:10px;border:1px solid #ffc107;">${b['threshold']:.2f}</td>
          <td style="padding:10px;border:1px solid #ffc107;">
            <div style="background:#e9ecef;border-radius:4px;height:14px;">
              <div style="background:#dc3545;border-radius:4px;height:14px;width:{pct}%;"></div>
            </div>
            <small>{b['percent']}%</small>
          </td>
        </tr>"""

    service_rows = ""
    for svc, cost in sorted(billing["services"].items(), key=lambda x: x[1], reverse=True):
        limit     = thresholds.get(svc)
        bar_pct   = min(cost / limit * 100, 100) if limit else 0
        bar_color = "#dc3545" if (limit and cost >= limit) else "#28a745"
        service_rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #dee2e6;font-size:12px;">{svc}</td>
          <td style="padding:8px;border:1px solid #dee2e6;font-size:12px;font-weight:600;">${cost:.6f}</td>
          <td style="padding:8px;border:1px solid #dee2e6;font-size:12px;">{f'${limit:.2f}' if limit else '—'}</td>
          <td style="padding:8px;border:1px solid #dee2e6;">
            {"<div style='background:#e9ecef;border-radius:3px;height:10px;'><div style='background:"+bar_color+";border-radius:3px;height:10px;width:"+str(round(bar_pct,1))+"%'></div></div><small style='font-size:10px;'>"+str(round(bar_pct,1))+"%</small>" if limit else "<small style='color:#aaa;font-size:10px;'>—</small>"}
          </td>
        </tr>"""

    total_limit = thresholds.get("TOTAL", 0)
    total_pct   = min(billing["total"] / total_limit * 100, 100) if total_limit else 0
    total_color = "#dc3545" if (total_limit and billing["total"] >= total_limit) else "#17a2b8"

    return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8f9fa;padding:20px;">
<div style="max-width:680px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.12);">
  <div style="background:#232f3e;padding:28px;color:#FF9900;">
    <h1 style="margin:0;font-size:22px;">⚠️ AWS Cost Alert</h1>
    <p style="margin:8px 0 0;color:#aaa;font-size:13px;">{len(breaches)} threshold(s) exceeded · {billing['period']}</p>
  </div>
  <div style="padding:20px;background:#f1f3f4;border-bottom:1px solid #dee2e6;">
    <div style="font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:1px;">Total This Month</div>
    <div style="font-size:38px;font-weight:700;color:{total_color};">${billing['total']:.4f} <span style="font-size:14px;color:#999;">{billing['currency']}</span></div>
    <div style="font-size:12px;color:#6c757d;">Limit: ${total_limit:.2f} · {round(total_pct,1)}% used</div>
    <div style="background:#dee2e6;border-radius:6px;height:10px;margin-top:8px;">
      <div style="background:{total_color};border-radius:6px;height:10px;width:{total_pct}%;"></div>
    </div>
  </div>
  <div style="padding:20px;">
    <h2 style="font-size:15px;color:#dc3545;margin-top:0;">🚨 Breaches</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="background:#343a40;color:#fff;">
        <th style="padding:10px;text-align:left;">Service</th>
        <th style="padding:10px;text-align:left;">Current</th>
        <th style="padding:10px;text-align:left;">Limit</th>
        <th style="padding:10px;text-align:left;">Usage</th>
      </tr></thead>
      <tbody>{breach_rows}</tbody>
    </table>
  </div>
  <div style="padding:20px;border-top:1px solid #dee2e6;">
    <h2 style="font-size:15px;margin-top:0;">📊 All Services</h2>
    <table style="width:100%;border-collapse:collapse;">
      <thead><tr style="background:#f8f9fa;">
        <th style="padding:8px;text-align:left;border:1px solid #dee2e6;font-size:12px;">Service</th>
        <th style="padding:8px;text-align:left;border:1px solid #dee2e6;font-size:12px;">Cost</th>
        <th style="padding:8px;text-align:left;border:1px solid #dee2e6;font-size:12px;">Limit</th>
        <th style="padding:8px;text-align:left;border:1px solid #dee2e6;font-size:12px;">Bar</th>
      </tr></thead>
      <tbody>{service_rows}</tbody>
    </table>
  </div>
  <div style="padding:14px 20px;background:#f8f9fa;border-top:1px solid #dee2e6;font-size:11px;color:#6c757d;">
    Checked: {billing['checked_at']} ·
    <a href="https://console.aws.amazon.com/cost-management/home" style="color:#FF9900;">Open AWS Cost Explorer →</a>
  </div>
</div></body></html>"""


def send_alert_email(billing: dict, breaches: list, thresholds: dict) -> bool:
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user).strip()
    alert_to  = os.getenv("ALERT_EMAIL", "").strip()

    if not smtp_user or not alert_to:
        print("⚠️  [EMAIL] Not configured — set SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL in .env")
        return False

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"⚠️ AWS Alert — {len(breaches)} breach(es) · ${billing['total']:.4f} this month"
    msg["From"]    = smtp_from
    msg["To"]      = alert_to

    plain = f"AWS COST ALERT\nTotal: ${billing['total']:.4f}\nPeriod: {billing['period']}\n\nBreaches:\n"
    for b in breaches:
        plain += f"  • {b['service']}: ${b['current']:.4f} / ${b['threshold']:.2f} ({b['percent']}%)\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_email_html(billing, breaches, thresholds), "html"))

    try:
        with smtplib.SMTP(
            os.getenv("SMTP_HOST", "smtp.gmail.com"),
            int(os.getenv("SMTP_PORT", "587"))
        ) as s:
            s.ehlo(); s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_from, alert_to, msg.as_string())
        print(f"✅ [EMAIL] Alert sent to {alert_to}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ [EMAIL] Auth failed — use Gmail App Password (not your login password)")
        return False
    except Exception as e:
        print(f"❌ [EMAIL] Failed: {e}")
        return False


def run_billing_check(custom_thresholds: dict = None) -> dict:
    thresholds   = custom_thresholds or load_thresholds()
    creds        = get_credentials()
    ce           = get_ce_client(creds)
    billing      = fetch_billing_data(ce)
    breaches     = check_thresholds(billing, thresholds)
    email_sent   = send_alert_email(billing, breaches, thresholds) if breaches else False
    return {
        "billing": billing, "breaches": breaches,
        "thresholds": thresholds, "email_sent": email_sent
    }


if __name__ == "__main__":
    result = run_billing_check()
    print(f"\nTotal: ${result['billing']['total']:.6f} | Breaches: {len(result['breaches'])}")