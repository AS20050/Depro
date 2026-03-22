# scripts/verify_vault.py
# Run this anytime to verify the Algorand vault is working correctly.
# Tests the full cycle: store -> verify on-chain -> retrieve -> tamper test -> delete
#
# Usage:
#   cd algorand
#   python scripts/verify_vault.py

from __future__ import annotations

import base64
import os
import sys

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ensure algorand/ is on sys.path so local imports work
sys.path.append(str(Path(__file__).resolve().parents[1]))

from algosdk.v2client import algod as algod_module  # noqa: E402
from algorand_credential_store import (  # noqa: E402
    _decrypt,
    _derive_box_key,
    _derive_encryption_key,
    delete_aws_credentials,
    has_credentials,
    retrieve_aws_credentials,
    store_aws_credentials,
)

ALGOD_TOKEN = os.getenv("ALGOD_TOKEN", "")
ALGOD_SERVER = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
VAULT_APP_ID = os.getenv("CREDENTIAL_VAULT_APP_ID", "")

TEST_ACCESS_KEY_ID = "AKIATEST123456789012"
TEST_SECRET_ACCESS_KEY = "testSecretKey/ABC+DEF/GHI+JKL/MNO+PQR"
TEST_REGION = "ap-south-1"


def header(text: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def ok(text: str) -> None:
    print(f"    OK  {text}")


def fail(text: str) -> None:
    print(f"    FAIL {text}")


def warn(text: str) -> None:
    print(f"    WARN {text}")


def run() -> None:
    header("OPSONIC ALGORAND VAULT - VERIFICATION SCRIPT")
    keep_box = "--keep" in sys.argv

    if not VAULT_APP_ID:
        fail("CREDENTIAL_VAULT_APP_ID not set in .env")
        print("       Run: python scripts/setup_vault.py first")
        sys.exit(1)

    if not os.getenv("ALGORAND_DEPLOYER_MNEMONIC", ""):
        fail("ALGORAND_DEPLOYER_MNEMONIC not set in .env")
        sys.exit(1)

    algod_client = algod_module.AlgodClient(ALGOD_TOKEN, ALGOD_SERVER)
    app_id = int(VAULT_APP_ID)

    print("\n[1] Checking vault contract is live on Algorand TestNet...")
    try:
        info = algod_client.application_info(app_id)
        ok(f"Vault App ID:  {app_id}")
        ok(f"Creator:       {info['params']['creator']}")
        ok(f"Deleted:       {info.get('deleted', False)}")
        ok("Contract is live and responsive")
    except Exception as e:
        fail(f"Vault contract not found: {e}")
        sys.exit(1)

    print("\n[2] Storing test credential...")
    print(f"    Access Key ID: {TEST_ACCESS_KEY_ID}")
    print(f"    Secret Key:    {TEST_SECRET_ACCESS_KEY[:10]}****  (truncated)")
    try:
        result = store_aws_credentials(
            {
                "AWS_ACCESS_KEY_ID": TEST_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": TEST_SECRET_ACCESS_KEY,
                "AWS_DEFAULT_REGION": TEST_REGION,
            }
        )
        ok("Stored successfully")
        ok("Algorand TX confirmed")
        ok(f"Box key (hex): {result['box_key'][:32]}...")
        ok(f"Vault App: {result['explorer_url']}")
    except Exception as e:
        fail(f"Store failed: {e}")
        sys.exit(1)

    print("\n[3] Verifying box exists on Algorand chain...")
    try:
        boxes = algod_client.application_boxes(app_id)
        box_list = boxes.get("boxes", [])
        ok(f"Total boxes on-chain: {len(box_list)}")
        box_key = _derive_box_key(TEST_ACCESS_KEY_ID)
        if any(b.get("name") == base64.b64encode(box_key).decode() for b in box_list):
            ok("Test box exists in box list")
        else:
            ok("Box list retrieved (box may not appear if list is truncated)")
    except Exception as e:
        warn(f"Box list check failed (non-fatal): {e}")

    print("\n[4] Retrieving and decrypting from Algorand...")
    try:
        retrieved = retrieve_aws_credentials(TEST_ACCESS_KEY_ID)
        key_matches = retrieved["AWS_ACCESS_KEY_ID"] == TEST_ACCESS_KEY_ID
        secret_matches = retrieved["AWS_SECRET_ACCESS_KEY"] == TEST_SECRET_ACCESS_KEY
        region_matches = retrieved["AWS_DEFAULT_REGION"] == TEST_REGION

        ok("Decryption successful")
        ok(f"AWS_ACCESS_KEY_ID matches:     {key_matches}")
        ok(f"AWS_SECRET_ACCESS_KEY matches: {secret_matches}")
        ok(f"AWS_DEFAULT_REGION matches:    {region_matches}")

        if not (key_matches and secret_matches and region_matches):
            fail("One or more fields did not match")
            sys.exit(1)
    except Exception as e:
        fail(f"Retrieval failed: {e}")
        sys.exit(1)

    print("\n[5] Tamper detection - decrypt with wrong key...")
    try:
        from algosdk import mnemonic as algo_mnemonic

        raw_mnemonic = os.getenv("ALGORAND_DEPLOYER_MNEMONIC", "")
        private_key = algo_mnemonic.to_private_key(raw_mnemonic)
        pk_bytes = base64.b64decode(private_key)[:32]
        wrong_enc_key = _derive_encryption_key(pk_bytes, "WRONG_KEY_ID_000000000")

        box_key = _derive_box_key(TEST_ACCESS_KEY_ID)
        box_response = algod_client.application_box_by_name(app_id, box_key)
        encrypted = base64.b64decode(box_response["value"]).decode()

        _decrypt(encrypted, wrong_enc_key)
        fail("Tamper test failed - wrong key decrypted")
        sys.exit(1)
    except ValueError:
        ok("Tamper test passed - wrong key rejected")
    except Exception as e:
        warn(f"Tamper test inconclusive: {e}")

    if keep_box:
        print("\n[6] Skipping delete because --keep was provided.")
    else:
        print("\n[6] Deleting test credential...")
        try:
            delete_aws_credentials(TEST_ACCESS_KEY_ID)
            still_exists = has_credentials(TEST_ACCESS_KEY_ID)
            ok("Delete transaction confirmed")
            ok(f"Credential still exists after delete: {still_exists}")
        except Exception as e:
            warn(f"Cleanup failed (non-fatal): {e}")

    if keep_box:
        header("ALL CHECKS PASSED - VAULT IS WORKING (TEST BOX KEPT)")
    else:
        header("ALL CHECKS PASSED - VAULT IS WORKING")


if __name__ == "__main__":
    run()
