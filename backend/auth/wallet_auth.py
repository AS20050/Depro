# auth/wallet_auth.py
#
# Lute wallet authentication: challenge-response + JWT session tokens.

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Optional

import jwt
from algosdk import encoding
from algosdk.util import verify_bytes

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 86400  # 24 hours

# In-memory challenge store  {wallet_address: (challenge_str, created_at)}
_challenges: dict[str, tuple[str, float]] = {}
CHALLENGE_TTL = 300  # 5 minutes


def generate_challenge(wallet_address: str) -> str:
    """Create a random challenge string for the wallet to sign."""
    nonce = secrets.token_hex(16)
    ts = int(time.time())
    challenge = f"dePro-login-{nonce}-{ts}"
    _challenges[wallet_address] = (challenge, time.time())
    return challenge


def verify_signature(wallet_address: str, signature_b64: str) -> str:
    """
    Verify the Algorand signature and return a JWT session token.
    Raises ValueError on failure.
    """
    entry = _challenges.pop(wallet_address, None)
    if entry is None:
        raise ValueError("No pending challenge for this wallet address.")

    challenge_str, created_at = entry
    if time.time() - created_at > CHALLENGE_TTL:
        raise ValueError("Challenge expired. Request a new one.")

    challenge_bytes = challenge_str.encode("utf-8")
    signature_bytes = base64.b64decode(signature_b64)

    # algosdk verify_bytes uses "MX" prefix internally
    try:
        valid = verify_bytes(challenge_bytes, signature_bytes, wallet_address)
    except Exception as exc:
        raise ValueError(f"Signature verification failed: {exc}") from exc

    if not valid:
        raise ValueError("Invalid signature.")

    # Issue JWT
    payload = {
        "wallet": wallet_address,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Returns payload dict. Raises on invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Session expired. Please reconnect wallet.")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid session token: {exc}") from exc


def get_wallet_from_request(authorization: Optional[str]) -> str:
    """
    Extract wallet address from Authorization header.
    Expects: 'Bearer <token>'
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    return payload["wallet"]
