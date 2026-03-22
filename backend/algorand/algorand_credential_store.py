# algorand_credential_store.py
#
# Algorand Credential Vault:
# - Encrypt AWS credentials with AES-256-GCM
# - Store encrypted blob in Algorand box storage keyed by sha256(access_key_id)
# - Derive per-user encryption key via HKDF-SHA256 using deployer private-key seed bytes
#
# NOTE: Keep all prints ASCII-only for Windows console compatibility.

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from dotenv import load_dotenv

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import algosdk.encoding as enc
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod

load_dotenv()

HKDF_INFO = b"depro-aws-creds-v1"
KEY_SIZE = 32  # AES-256
NONCE_SIZE = 12  # GCM standard nonce


def _get_algod_client() -> algod.AlgodClient:
    token = os.getenv("ALGOD_TOKEN", "")
    server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    return algod.AlgodClient(token, server)


def _get_deployer() -> tuple[bytes, str, str]:
    """
    Returns (private_key_seed_bytes, private_key_str, address).

    `private_key_seed_bytes` is derived from the first 32 bytes of the decoded
    Algorand private key string (which is base64-encoded in algosdk).
    """
    raw_mnemonic = os.getenv("ALGORAND_DEPLOYER_MNEMONIC", "").strip()
    if not raw_mnemonic:
        raise EnvironmentError("ALGORAND_DEPLOYER_MNEMONIC not set")

    private_key_str = mnemonic.to_private_key(raw_mnemonic)
    address = account.address_from_private_key(private_key_str)

    decoded = base64.b64decode(private_key_str)
    if len(decoded) < 32:
        raise ValueError("Unexpected deployer private key format (decoded < 32 bytes)")
    private_key_seed_bytes = decoded[:32]

    return private_key_seed_bytes, private_key_str, address


def _get_vault_app_id() -> int:
    app_id = os.getenv("CREDENTIAL_VAULT_APP_ID", "").strip()
    if not app_id:
        raise EnvironmentError("CREDENTIAL_VAULT_APP_ID not set. Run: python scripts/setup_vault.py")
    return int(app_id)


def _derive_box_key(access_key_id: str) -> bytes:
    """32-byte deterministic box name derived from access key ID."""
    return hashlib.sha256(access_key_id.encode("utf-8")).digest()


def _derive_encryption_key(private_key_seed_bytes: bytes, access_key_id: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=access_key_id.encode("utf-8"),
        info=HKDF_INFO,
    )
    return hkdf.derive(private_key_seed_bytes)


def _encrypt(data: dict[str, Any], encryption_key: bytes) -> str:
    """AES-256-GCM encrypt. Returns base64(nonce + ciphertext_with_tag)."""
    aesgcm = AESGCM(encryption_key)
    nonce = os.urandom(NONCE_SIZE)
    plaintext = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext_with_tag).decode("utf-8")


def _decrypt(encrypted_blob: str, encryption_key: bytes) -> dict[str, Any]:
    try:
        packed = base64.b64decode(encrypted_blob)
        nonce = packed[:NONCE_SIZE]
        ciphertext_with_tag = packed[NONCE_SIZE:]
        aesgcm = AESGCM(encryption_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Credential decryption failed (tamper or wrong key): {exc}") from exc


def _application_address(app_id: int) -> str:
    return enc.encode_address(enc.checksum(b"appID" + app_id.to_bytes(8, "big")))


def _required_box_mbr_microalgo(key_size: int, value_size: int) -> int:
    # MBR for box: 2500 + 400 * (key_size + value_size) microAlgos
    return 2500 + 400 * (key_size + value_size)


def _get_existing_box_value_size(algod_client: algod.AlgodClient, app_id: int, box_key: bytes) -> int | None:
    try:
        box_response = algod_client.application_box_by_name(app_id, box_key)
        value_bytes = base64.b64decode(box_response["value"])
        return len(value_bytes)
    except Exception:
        return None


def store_aws_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    access_key_id = (creds.get("AWS_ACCESS_KEY_ID") or "").strip()
    secret_access_key = (creds.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    region = (creds.get("AWS_DEFAULT_REGION") or "ap-south-1").strip() or "ap-south-1"

    if not access_key_id:
        raise ValueError("AWS_ACCESS_KEY_ID is required")
    if not secret_access_key:
        raise ValueError("AWS_SECRET_ACCESS_KEY is required")

    payload = {
        "AWS_ACCESS_KEY_ID": access_key_id,
        "AWS_SECRET_ACCESS_KEY": secret_access_key,
        "AWS_DEFAULT_REGION": region,
    }

    algod_client = _get_algod_client()
    private_key_seed_bytes, private_key_str, sender_addr = _get_deployer()
    vault_app_id = _get_vault_app_id()

    safe_prefix = access_key_id[:8] + "****"
    print(f"[VAULT] Storing credentials for: {safe_prefix}")

    box_key = _derive_box_key(access_key_id)
    encryption_key = _derive_encryption_key(private_key_seed_bytes, access_key_id)

    encrypted_blob = _encrypt(payload, encryption_key)
    blob_bytes = encrypted_blob.encode("utf-8")

    existing_value_size = _get_existing_box_value_size(algod_client, vault_app_id, box_key)
    required_new = _required_box_mbr_microalgo(len(box_key), len(blob_bytes))
    required_old = _required_box_mbr_microalgo(len(box_key), existing_value_size) if existing_value_size else 0
    mbr_delta = max(0, required_new - required_old)

    params = algod_client.suggested_params()

    app_call_txn = transaction.ApplicationCallTxn(
        sender=sender_addr,
        sp=params,
        index=vault_app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"store", box_key, blob_bytes],
        boxes=[(vault_app_id, box_key)],
    )

    if mbr_delta > 0:
        # Some algosdk versions use PaymentTxn instead of PaymentTransaction.
        payment_cls = getattr(transaction, "PaymentTransaction", None) or getattr(transaction, "PaymentTxn", None)
        if payment_cls is None:
            raise RuntimeError("algosdk transaction payment class not found")

        pay_txn = payment_cls(
            sender=sender_addr,
            sp=params,
            receiver=_application_address(vault_app_id),
            amt=mbr_delta,
        )
        gid = transaction.calculate_group_id([pay_txn, app_call_txn])
        pay_txn.group = gid
        app_call_txn.group = gid

        signed_pay = pay_txn.sign(private_key_str)
        signed_app = app_call_txn.sign(private_key_str)

        tx_id = algod_client.send_transactions([signed_pay, signed_app])
    else:
        signed_app = app_call_txn.sign(private_key_str)
        tx_id = algod_client.send_transaction(signed_app)

    transaction.wait_for_confirmation(algod_client, tx_id, 4)

    return {
        "status": "success",
        "box_key": box_key.hex(),
        "vault_app_id": vault_app_id,
        "mbr_paid_microalgo": mbr_delta,
        "explorer_url": f"https://testnet.algoexplorer.io/application/{vault_app_id}",
        "message": "AWS credentials encrypted and stored in Algorand box storage.",
    }


def retrieve_aws_credentials(access_key_id: str) -> dict[str, Any]:
    access_key_id = (access_key_id or "").strip()
    if not access_key_id:
        raise ValueError("access_key_id is required")

    algod_client = _get_algod_client()
    private_key_seed_bytes, _private_key_str, _sender_addr = _get_deployer()
    vault_app_id = _get_vault_app_id()

    safe_prefix = access_key_id[:8] + "****"
    print(f"[VAULT] Retrieving credentials for: {safe_prefix}")

    box_key = _derive_box_key(access_key_id)
    try:
        box_response = algod_client.application_box_by_name(vault_app_id, box_key)
    except Exception as exc:
        raise KeyError(f"No credentials found for access key ID: {safe_prefix}") from exc

    value_bytes = base64.b64decode(box_response["value"])
    encrypted_blob = value_bytes.decode("utf-8")

    encryption_key = _derive_encryption_key(private_key_seed_bytes, access_key_id)
    return _decrypt(encrypted_blob, encryption_key)


def delete_aws_credentials(access_key_id: str) -> dict[str, Any]:
    access_key_id = (access_key_id or "").strip()
    if not access_key_id:
        raise ValueError("access_key_id is required")

    algod_client = _get_algod_client()
    _private_key_seed_bytes, private_key_str, sender_addr = _get_deployer()
    vault_app_id = _get_vault_app_id()

    safe_prefix = access_key_id[:8] + "****"
    print(f"[VAULT] Deleting credentials for: {safe_prefix}")

    box_key = _derive_box_key(access_key_id)
    params = algod_client.suggested_params()

    txn = transaction.ApplicationCallTxn(
        sender=sender_addr,
        sp=params,
        index=vault_app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"delete", box_key],
        boxes=[(vault_app_id, box_key)],
    )

    signed = txn.sign(private_key_str)
    tx_id = algod_client.send_transaction(signed)
    transaction.wait_for_confirmation(algod_client, tx_id, 4)

    return {"status": "success", "message": "Credentials deleted from Algorand vault."}


def has_credentials(access_key_id: str) -> bool:
    access_key_id = (access_key_id or "").strip()
    if not access_key_id:
        return False

    algod_client = _get_algod_client()
    vault_app_id = _get_vault_app_id()
    box_key = _derive_box_key(access_key_id)
    try:
        algod_client.application_box_by_name(vault_app_id, box_key)
        return True
    except Exception:
        return False
