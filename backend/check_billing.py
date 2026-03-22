"""
check_billing.py
Run from backend folder: python check_billing.py
Tests whether AWS Cost Explorer is accessible with current credentials.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# ── Load .env from backend root ──
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# ── Add backend to path ──
sys.path.insert(0, str(Path(__file__).parent))

import boto3
from botocore.exceptions import ClientError


def get_credentials() -> dict:
    """Pull credentials from Elasticsearch first, then .env fallback."""
    try:
        from db import get_store
        store = get_store()
        key    = store.get("aws_access_key_id")
        secret = store.get("aws_secret_access_key")
        region = store.get("aws_region") or os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        if key and secret:
            print("🔐 [CREDS] Loaded from Elasticsearch")
            return {"key": key, "secret": secret, "region": region}
    except Exception as e:
        print(f"⚠️  [CREDS] ES unavailable: {e}")

    key    = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

    if key and secret:
        print("🔐 [CREDS] Loaded from .env")
        return {"key": key, "secret": secret, "region": region}

    raise Exception("❌ No credentials found. Set AWS keys in .env or connect via webapp.")


def check_identity(creds: dict):
    """Step 1: Verify credentials are valid via STS."""
    print("\n" + "="*50)
    print("STEP 1 — Verifying AWS Identity")
    print("="*50)
    sts = boto3.client("sts",
        aws_access_key_id=creds["key"],
        aws_secret_access_key=creds["secret"],
        region_name="us-east-1"
    )
    identity = sts.get_caller_identity()
    print(f"✅ Account ID : {identity['Account']}")
    print(f"✅ ARN        : {identity['Arn']}")
    print(f"✅ User ID    : {identity['UserId']}")
    return identity


def check_cost_explorer_enabled(creds: dict):
    """Step 2: Check if Cost Explorer is enabled."""
    print("\n" + "="*50)
    print("STEP 2 — Checking Cost Explorer Access")
    print("="*50)

    ce = boto3.client("ce",
        aws_access_key_id=creds["key"],
        aws_secret_access_key=creds["secret"],
        region_name="us-east-1"  # Cost Explorer is ALWAYS us-east-1
    )

    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        response = ce.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"]
        )
        print("✅ Cost Explorer is ENABLED and accessible")
        return ce
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "OptInRequired" or "Enable" in str(e):
            print("❌ Cost Explorer is NOT enabled on this account.")
            print("   Go to: AWS Console → Billing → Cost Explorer → Enable")
            raise Exception("Cost Explorer not enabled. Enable it in AWS Console first.")
        elif code == "AccessDeniedException":
            print("❌ IAM user does not have permission to access Cost Explorer.")
            print("   Add policy: AWSBillingReadOnlyAccess or AdministratorAccess")
            raise Exception(f"Access denied: {e}")
        else:
            raise e


def get_total_cost(ce, days: int = 30):
    """Step 3: Fetch total cost for last N days."""
    print("\n" + "="*50)
    print(f"STEP 3 — Total Cost (Last {days} days)")
    print("="*50)

    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost", "BlendedCost"]
    )

    for period in response["ResultsByTime"]:
        unblended = float(period["Total"]["UnblendedCost"]["Amount"])
        blended   = float(period["Total"]["BlendedCost"]["Amount"])
        currency  = period["Total"]["UnblendedCost"]["Unit"]
        print(f"📅 Period     : {period['TimePeriod']['Start']} → {period['TimePeriod']['End']}")
        print(f"💰 Total Cost : {unblended:.4f} {currency}")
        print(f"💰 Blended    : {blended:.4f} {currency}")

    return response


def get_cost_by_service(ce, days: int = 30):
    """Step 4: Fetch cost broken down by AWS service."""
    print("\n" + "="*50)
    print(f"STEP 4 — Cost by Service (Last {days} days)")
    print("="*50)

    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
    )

    services = []
    for period in response["ResultsByTime"]:
        for group in period["Groups"]:
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if cost > 0:
                services.append({
                    "service":  group["Keys"][0],
                    "cost":     round(cost, 6),
                    "currency": group["Metrics"]["UnblendedCost"]["Unit"]
                })

    services_sorted = sorted(services, key=lambda x: x["cost"], reverse=True)

    if not services_sorted:
        print("💡 No costs found for this period (account might be in free tier)")
    else:
        print(f"{'Service':<45} {'Cost':>12} {'Currency'}")
        print("-" * 65)
        for s in services_sorted:
            print(f"{s['service']:<45} {s['cost']:>12.6f} {s['currency']}")

    return services_sorted


def get_daily_costs(ce, days: int = 7):
    """Step 5: Fetch daily cost breakdown for last N days."""
    print("\n" + "="*50)
    print(f"STEP 5 — Daily Costs (Last {days} days)")
    print("="*50)

    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="DAILY",
        Metrics=["UnblendedCost"]
    )

    print(f"{'Date':<15} {'Cost':>12} {'Currency'}")
    print("-" * 35)
    for period in response["ResultsByTime"]:
        cost     = float(period["Total"]["UnblendedCost"]["Amount"])
        currency = period["Total"]["UnblendedCost"]["Unit"]
        date     = period["TimePeriod"]["Start"]
        print(f"{date:<15} {cost:>12.6f} {currency}")

    return response


def get_cost_forecast(ce):
    """Step 6: Fetch cost forecast for next 30 days."""
    print("\n" + "="*50)
    print("STEP 6 — Cost Forecast (Next 30 days)")
    print("="*50)

    start = datetime.today().strftime("%Y-%m-%d")
    end   = (datetime.today() + timedelta(days=30)).strftime("%Y-%m-%d")

    try:
        response = ce.get_cost_forecast(
            TimePeriod={"Start": start, "End": end},
            Metric="UNBLENDED_COST",
            Granularity="MONTHLY"
        )
        total    = float(response["Total"]["Amount"])
        currency = response["Total"]["Unit"]
        print(f"📈 Forecasted Cost : {total:.4f} {currency}")
        print(f"📅 Period          : {start} → {end}")
        return response
    except ClientError as e:
        if "DataUnavailableException" in str(e):
            print("⚠️  Forecast unavailable — need at least 14 days of billing history")
        else:
            print(f"⚠️  Forecast error: {e}")


def main():
    print("\n" + "="*50)
    print("  AWS BILLING CHECK")
    print("="*50)

    try:
        # Load credentials
        creds = get_credentials()
        print(f"\n   Key ID  : {creds['key'][:8]}...{creds['key'][-4:]}")
        print(f"   Region  : {creds['region']}")
        print(f"   Key len : {len(creds['key'])} chars")
        print(f"   Sec len : {len(creds['secret'])} chars")

        # Run checks
        check_identity(creds)
        ce = check_cost_explorer_enabled(creds)
        get_total_cost(ce, days=30)
        get_cost_by_service(ce, days=30)
        get_daily_costs(ce, days=7)
        get_cost_forecast(ce)

        print("\n" + "="*50)
        print("✅ ALL BILLING CHECKS PASSED")
        print("="*50)

    except Exception as e:
        print(f"\n❌ BILLING CHECK FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()