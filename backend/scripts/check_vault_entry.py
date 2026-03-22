# scripts/check_vault_entry.py
# Checks whether a given AWS Access Key ID has a box entry in the Algorand vault,
# and prints basic on-chain details (without printing secrets).
#
# Usage:
#   cd backend
#   python scripts/check_vault_entry.py AKIA...
#
# If no argument is provided, it uses AWS_ACCESS_KEY_ID from `.env` / environment.

from __future__ import annotations

import base64
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from algosdk.v2client import algod  # noqa: E402
from mcpServer.infraScripts.algorand_credential_store import _derive_box_key  # noqa: E402
from mcpServer.infraScripts.algorand_credential_store import _get_vault_app_id  # noqa: E402


def main() -> int:
    access_key_id = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("AWS_ACCESS_KEY_ID", "")).strip()
    if not access_key_id:
        print("ERROR: Provide an access key id arg or set AWS_ACCESS_KEY_ID in .env")
        return 1

    app_id = _get_vault_app_id()
    token = os.getenv("ALGOD_TOKEN", "")
    server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    client = algod.AlgodClient(token, server)

    box_key = _derive_box_key(access_key_id)
    safe_prefix = access_key_id[:8] + "****"

    print("OPSONIC VAULT ENTRY CHECK")
    print(f"Vault App ID: {app_id}")
    print(f"Access Key:   {safe_prefix}")
    print(f"Box key hex:  {box_key.hex()}")
    print(f"Explorer:     https://testnet.algoexplorer.io/application/{app_id}")

    try:
        box = client.application_box_by_name(app_id, box_key)
    except Exception as e:
        print(f"Result:       NOT FOUND ({e})")
        return 2

    value_bytes = base64.b64decode(box["value"])
    print("Result:       FOUND")
    print(f"Value bytes:  {len(value_bytes)} (encrypted blob)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

