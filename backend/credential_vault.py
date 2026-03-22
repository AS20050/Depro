"""
credential_vault.py — Intermediate layer between DePro APIs and Algorand Vault

FLOW:
  User uploads IAM creds via API
    → encrypt with AES-256-GCM
    → store encrypted blob in Algorand box storage
    → save only the access_key_id (hint) in user's DB record

  Any API needs AWS creds (billing, deploy, etc.)
    → read user's access_key_id from DB
    → retrieve + decrypt from Algorand vault
    → inject into os.environ for boto3
    → return as dict

  Plaintext credentials NEVER touch the database.
"""

import os
import sys
from pathlib import Path

# Add algorand folder to path so we can import the store
_ALGO_DIR = Path(__file__).parent / "algorand"
if str(_ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGO_DIR))

# Load algorand .env for vault config (mnemonic, app ID, algod server)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(_ALGO_DIR / ".env")

from algorand_credential_store import (
    store_aws_credentials as _algo_store,
    retrieve_aws_credentials as _algo_retrieve,
    delete_aws_credentials as _algo_delete,
    has_credentials as _algo_has,
)


def vault_store(access_key_id: str, secret_access_key: str, region: str = "ap-south-1") -> dict:
    """
    Encrypt and store AWS IAM credentials in Algorand vault.
    Returns metadata about the storage operation.
    """
    access_key_id = (access_key_id or "").strip()
    secret_access_key = (secret_access_key or "").strip()
    region = (region or "ap-south-1").strip()

    if not access_key_id or not secret_access_key:
        raise ValueError("Both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required")

    print(f"🔐 [VAULT] Storing creds for: {access_key_id[:8]}****")

    result = _algo_store({
        "AWS_ACCESS_KEY_ID": access_key_id,
        "AWS_SECRET_ACCESS_KEY": secret_access_key,
        "AWS_DEFAULT_REGION": region,
    })

    result["access_key_hint"] = access_key_id[:4] + "****" + access_key_id[-4:]
    return result


def vault_retrieve(access_key_id: str) -> dict:
    """
    Retrieve and decrypt AWS IAM credentials from Algorand vault.
    Returns: {"AWS_ACCESS_KEY_ID": ..., "AWS_SECRET_ACCESS_KEY": ..., "AWS_DEFAULT_REGION": ...}
    """
    access_key_id = (access_key_id or "").strip()
    if not access_key_id:
        raise ValueError("access_key_id is required for vault retrieval")

    print(f"🔓 [VAULT] Retrieving creds for: {access_key_id[:8]}****")
    return _algo_retrieve(access_key_id)


def vault_delete(access_key_id: str) -> dict:
    """Delete credentials from Algorand vault."""
    access_key_id = (access_key_id or "").strip()
    if not access_key_id:
        raise ValueError("access_key_id is required")

    print(f"🗑️ [VAULT] Deleting creds for: {access_key_id[:8]}****")
    return _algo_delete(access_key_id)


def vault_exists(access_key_id: str) -> bool:
    """Check if credentials exist in the vault."""
    return _algo_has((access_key_id or "").strip())


def vault_inject_to_env(access_key_id: str) -> dict:
    """
    Retrieve creds from vault and inject into os.environ for boto3.
    Returns the credentials dict.
    """
    creds = vault_retrieve(access_key_id)
    os.environ["AWS_ACCESS_KEY_ID"] = creds["AWS_ACCESS_KEY_ID"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = creds["AWS_SECRET_ACCESS_KEY"]
    os.environ["AWS_DEFAULT_REGION"] = creds.get("AWS_DEFAULT_REGION", "ap-south-1")
    print(f"✅ [VAULT] Credentials injected into environment")
    return creds


def get_credentials_for_user(access_key_id: str) -> dict:
    """
    Get AWS credentials for billing/deploy — retrieves from Algorand vault.
    Returns: {"key": ..., "secret": ..., "region": ...}
    Compatible with billing_monitor.get_credentials() format.
    """
    creds = vault_retrieve(access_key_id)
    return {
        "key":    creds["AWS_ACCESS_KEY_ID"],
        "secret": creds["AWS_SECRET_ACCESS_KEY"],
        "region": creds.get("AWS_DEFAULT_REGION", "ap-south-1"),
    }
