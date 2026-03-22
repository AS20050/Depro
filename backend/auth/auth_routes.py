# auth/auth_routes.py
#
# FastAPI router for Lute wallet authentication endpoints.

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from auth.wallet_auth import (
    decode_token,
    generate_challenge,
    get_wallet_from_request,
    verify_signature,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class ChallengeRequest(BaseModel):
    wallet_address: str


class ChallengeResponse(BaseModel):
    challenge: str


class VerifyRequest(BaseModel):
    wallet_address: str
    signature: str  # base64-encoded


class VerifyResponse(BaseModel):
    token: str
    wallet: str


@router.post("/challenge", response_model=ChallengeResponse)
async def auth_challenge(req: ChallengeRequest):
    """Step 1: Get a challenge string for the wallet to sign."""
    challenge = generate_challenge(req.wallet_address)
    return {"challenge": challenge}


@router.post("/verify", response_model=VerifyResponse)
async def auth_verify(req: VerifyRequest):
    """Step 2: Submit signature to receive a session token."""
    try:
        token = verify_signature(req.wallet_address, req.signature)
        return {"token": token, "wallet": req.wallet_address}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
async def auth_me(authorization: str = Header(None)):
    """Check if session token is still valid."""
    try:
        wallet = get_wallet_from_request(authorization)
        return {"authenticated": True, "wallet": wallet}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def auth_logout():
    """Clear session (client-side token removal)."""
    return {"status": "success", "message": "Logged out. Remove token from localStorage."}
