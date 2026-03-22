"""
billing_routes.py — Drop in backend/ folder

Add to app.py:
    from billing_routes import router as billing_router
    app.include_router(billing_router, prefix="/billing", tags=["Billing"])
"""

import os
import boto3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from billing_monitor import (
    get_credentials, get_ce_client, get_sts_identity,
    fetch_billing_data, check_thresholds, send_alert_email,
    load_thresholds, save_thresholds,
)

router = APIRouter()


class ThresholdsUpdate(BaseModel):
    thresholds: Dict[str, float]


def _live_billing():
    """Get credentials from .env and fetch live AWS billing."""
    try:
        creds = get_credentials()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Missing AWS credentials in .env: {e}")

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


@router.get("/health")
async def health():
    """Ping AWS with stored credentials to verify they work."""
    try:
        creds    = get_credentials()
        identity = get_sts_identity(creds)
        key      = creds["key"]
        return {
            "status":          "ok",
            "account_id":      identity["Account"],
            "arn":             identity["Arn"],
            "region":          creds["region"],
            "key_masked":      f"{key[:8]}...{key[-4:]}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/thresholds")
async def get_thresholds():
    return {"status": "success", "thresholds": load_thresholds()}


@router.post("/thresholds")
async def update_thresholds(body: ThresholdsUpdate):
    save_thresholds(body.thresholds)
    return {"status": "success", "thresholds": body.thresholds}


@router.post("/check")
async def run_check():
    """Fetch billing, compare thresholds, send email if breached."""
    try:
        thresholds = load_thresholds()
        billing, _ = _live_billing()
        breaches   = check_thresholds(billing, thresholds)
        email_sent = send_alert_email(billing, breaches, thresholds) if breaches else False
        return {
            "status":     "success",
            "billing":    billing,
            "breaches":   breaches,
            "email_sent": email_sent,
            "checked_at": billing["checked_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def summary():
    """
    Single endpoint for the dashboard.
    Returns live billing data + threshold status for every service.
    """
    try:
        creds      = get_credentials()
        thresholds = load_thresholds()
        billing, _ = _live_billing()
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
                # Live billing totals
                "total":          billing["total"],
                "currency":       billing["currency"],
                "period":         billing["period"],
                "checked_at":     billing["checked_at"],

                # Threshold status
                "total_limit":    total_limit,
                "total_percent":  total_pct,
                "total_breached": total_breached,

                # Per-service with threshold bars
                "services":       services_status,

                # Daily trend chart data
                "daily":          billing["daily"],

                # Current thresholds (for editor)
                "thresholds":     thresholds,

                # Account identity from .env credentials
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