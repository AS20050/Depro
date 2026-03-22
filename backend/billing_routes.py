"""
billing_routes.py — Per-user billing with DB-backed thresholds

All threshold endpoints are JWT-protected and scoped to the authenticated user.
Email alerts go to the user's registered email address.
"""

import os
import boto3
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv(Path(__file__).parent / ".env")

from db.database import get_db
from db.models import BillingThreshold, User
from auth.jwt_handler import get_current_user

from billing_monitor import (
    get_credentials, get_ce_client, get_sts_identity,
    fetch_billing_data, check_thresholds, send_alert_email,
)

router = APIRouter()

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


class ThresholdsUpdate(BaseModel):
    thresholds: Dict[str, float]


# ── Threshold helpers ────────────────────────────────────────────

async def _load_user_thresholds(user_id: str, db: AsyncSession) -> dict:
    """Load thresholds from DB for this user. Returns defaults if none exist."""
    result = await db.execute(
        select(BillingThreshold).where(BillingThreshold.user_id == user_id)
    )
    rows = result.scalars().all()
    if not rows:
        return DEFAULT_THRESHOLDS.copy()
    return {row.service_name: row.limit_value for row in rows}


async def _save_user_thresholds(user_id: str, thresholds: dict, db: AsyncSession):
    """Replace all thresholds for this user with new values."""
    # Delete existing
    await db.execute(
        delete(BillingThreshold).where(BillingThreshold.user_id == user_id)
    )
    # Insert new
    for service_name, limit_value in thresholds.items():
        if limit_value and limit_value > 0:
            db.add(BillingThreshold(
                user_id=user_id,
                service_name=service_name,
                limit_value=float(limit_value)
            ))
    await db.commit()
    print(f"💾 [DB] Thresholds saved for user {user_id}")


async def _get_user_email(user_id: str, db: AsyncSession) -> str | None:
    """Get the user's email address for alerts."""
    result = await db.execute(select(User.email).where(User.id == user_id))
    row = result.scalar_one_or_none()
    return row


# ── Billing helpers ──────────────────────────────────────────────

def _live_billing(user: User = None):
    """
    Get credentials and fetch live AWS billing.
    Priority: 1) User's vault creds  2) .env fallback
    """
    creds = None

    # 1. Try Algorand vault if user has stored access key
    if user and user.aws_access_key_id:
        try:
            from credential_vault import get_credentials_for_user
            creds = get_credentials_for_user(user.aws_access_key_id)
            print(f"🔐 [BILLING] Using vault creds for: {user.aws_access_key_id[:8]}****")
        except Exception as ve:
            print(f"⚠️ [BILLING] Vault retrieval failed, falling back to .env: {ve}")

    # 2. Fallback to .env
    if not creds:
        try:
            creds = get_credentials()
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"No AWS credentials available: {e}")

    try:
        ce      = get_ce_client(creds)
        billing = fetch_billing_data(ce)
        return billing, creds
    except Exception as e:
        err = str(e)
        if "OptInRequired" in err or "is not subscribed" in err:
            raise HTTPException(status_code=402,
                detail="Cost Explorer not enabled. AWS Console → Billing → Cost Explorer → Enable.")
        if "AccessDenied" in err:
            raise HTTPException(status_code=403,
                detail="IAM user lacks billing permission. Attach AWSBillingReadOnlyAccess or AdministratorAccess.")
        raise HTTPException(status_code=500, detail=f"AWS error: {err}")


# ── Routes ───────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Ping AWS with stored credentials to verify they work."""
    try:
        creds    = get_credentials()
        identity = get_sts_identity(creds)
        key      = creds["key"]
        return {
            "status":     "ok",
            "account_id": identity["Account"],
            "arn":        identity["Arn"],
            "region":     creds["region"],
            "key_masked": f"{key[:8]}...{key[-4:]}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/thresholds")
async def get_thresholds(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    thresholds = await _load_user_thresholds(str(user.id), db)
    return {"status": "success", "thresholds": thresholds}


@router.post("/thresholds")
async def update_thresholds(
    body: ThresholdsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _save_user_thresholds(str(user.id), body.thresholds, db)
    return {"status": "success", "thresholds": body.thresholds}


@router.post("/check")
async def run_check(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetch billing, compare user's thresholds, send email only if newly breached."""
    try:
        thresholds = await _load_user_thresholds(str(user.id), db)
        billing, _ = _live_billing(user)
        breaches   = check_thresholds(billing, thresholds)

        email_sent = False
        already_notified = False

        if breaches:
            current_total = billing["total"]
            last_alerted  = user.billing_alerted_total or 0.0

            # Only send if the total has increased beyond what we last alerted for
            if current_total > last_alerted:
                user_email = user.email
                if user_email:
                    email_sent = send_alert_email(billing, breaches, thresholds, recipient=user_email)
                    if email_sent:
                        # Record that we notified for this amount
                        user.billing_alerted_total = current_total
                        user.billing_alert_sent_at = datetime.now(timezone.utc)
                        await db.commit()
                        print(f"📧 [EMAIL] Alert sent to {user_email} for total ${current_total:.4f}")
                else:
                    print("⚠️  [EMAIL] User has no email address set")
            else:
                already_notified = True
                print(f"📧 [EMAIL] Already notified for ${last_alerted:.4f}, skipping (current: ${current_total:.4f})")

        return {
            "status":           "success",
            "billing":          billing,
            "breaches":         breaches,
            "email_sent":       email_sent,
            "already_notified": already_notified,
            "checked_at":       billing["checked_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Single endpoint for the dashboard.
    Returns live billing data + user's threshold status for every service.
    """
    try:
        thresholds = await _load_user_thresholds(str(user.id), db)
        billing, creds = _live_billing(user)
        identity   = get_sts_identity(creds)

        services_status = []
        for svc, cost in sorted(billing["services"].items(), key=lambda x: x[1], reverse=True):
            limit   = thresholds.get(svc)
            percent = round((cost / limit) * 100, 1) if limit else None
            services_status.append({
                "service":   svc,
                "cost":      cost,
                "threshold": limit,
                "percent":   percent,
                "breached":  bool(limit and cost >= limit),
            })

        total_limit    = thresholds.get("TOTAL")
        total_pct      = round((billing["total"] / total_limit) * 100, 1) if total_limit else None
        total_breached = bool(total_limit and billing["total"] >= total_limit)

        key = creds["key"]

        return {
            "status": "success",
            "summary": {
                "total":          billing["total"],
                "currency":       billing["currency"],
                "period":         billing["period"],
                "checked_at":     billing["checked_at"],
                "total_limit":    total_limit,
                "total_percent":  total_pct,
                "total_breached": total_breached,
                "services":       services_status,
                "daily":          billing["daily"],
                "thresholds":     thresholds,
                "account": {
                    "account_id":  identity["Account"],
                    "arn":         identity["Arn"],
                    "key_masked":  f"{key[:8]}...{key[-4:]}",
                    "region":      creds["region"],
                },
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))