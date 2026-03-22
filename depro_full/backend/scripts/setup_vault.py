# scripts/setup_vault.py
# Run once to deploy the CredentialVault app on Algorand TestNet and persist
# CREDENTIAL_VAULT_APP_ID into `.env` (if present).
#
# Usage:
#   cd backend
#   python scripts/setup_vault.py
#
# NOTE: Keep all prints ASCII-only for Windows console compatibility.

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Hand-written TEAL so you don't need algokit installed to run setup.
# Logic: only creator can call store/delete, anyone can read boxes via algod API.

APPROVAL_TEAL = """#pragma version 9
// Allow on creation
txn ApplicationID
int 0
==
bz check_sender

b allow

// All other calls: only creator
check_sender:
txn Sender
global CreatorAddress
==
assert

// Route by first argument
txn NumAppArgs
int 1
>=
bz allow

txn ApplicationArgs 0
byte "store"
==
bz check_delete

// STORE: app_args[1]=box_key(32 bytes), app_args[2]=encrypted_blob
txn ApplicationArgs 1
txn ApplicationArgs 2
box_put
b allow

check_delete:
txn ApplicationArgs 0
byte "delete"
==
bz allow

// DELETE: app_args[1]=box_key(32 bytes)
txn ApplicationArgs 1
box_del
pop
b allow

allow:
int 1
return
"""

CLEAR_TEAL = """#pragma version 9
int 1
return
"""


def deploy_vault() -> int:
    from algosdk.v2client import algod
    from algosdk import account, mnemonic, transaction

    algod_token = os.getenv("ALGOD_TOKEN", "")
    algod_server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    deployer_mnemonic = os.getenv("ALGORAND_DEPLOYER_MNEMONIC", "")

    if not deployer_mnemonic:
        print("ERROR: ALGORAND_DEPLOYER_MNEMONIC not set in .env")
        sys.exit(1)

    existing = os.getenv("CREDENTIAL_VAULT_APP_ID", "")
    if existing:
        print(f"Vault already deployed. App ID: {existing}")
        print("To redeploy, remove CREDENTIAL_VAULT_APP_ID from .env")
        return int(existing)

    algod_client = algod.AlgodClient(algod_token, algod_server)
    private_key = mnemonic.to_private_key(deployer_mnemonic)
    address = account.address_from_private_key(private_key)

    print("Deploying CredentialVault to Algorand TestNet...")
    print(f"Deployer: {address}")

    # Best-effort balance check
    try:
        info = algod_client.account_info(address)
        balance = info.get("amount", 0) / 1_000_000
        print(f"Balance: {balance:.6f} ALGO")
        if balance < 0.5:
            print("WARNING: Low balance. Fund at https://bank.testnet.algorand.network")
    except Exception as e:
        print(f"WARNING: Could not check balance: {e}")

    print("Compiling TEAL...")
    approval_result = algod_client.compile(APPROVAL_TEAL)
    clear_result = algod_client.compile(CLEAR_TEAL)

    approval_bytes = base64.b64decode(approval_result["result"])
    clear_bytes = base64.b64decode(clear_result["result"])

    params = algod_client.suggested_params()
    txn = transaction.ApplicationCreateTxn(
        sender=address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_bytes,
        clear_program=clear_bytes,
        global_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
    )

    signed_txn = txn.sign(private_key)
    tx_id = algod_client.send_transaction(signed_txn)
    print(f"TX submitted: {tx_id}")
    print("Waiting for confirmation...")

    result = transaction.wait_for_confirmation(algod_client, tx_id, 4)
    app_id = result["application-index"]

    print("CredentialVault deployed successfully.")
    print(f"App ID: {app_id}")
    print(f"Explorer: https://testnet.algoexplorer.io/application/{app_id}")

    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8", errors="replace")
        if "CREDENTIAL_VAULT_APP_ID" in content:
            lines = [
                f'CREDENTIAL_VAULT_APP_ID="{app_id}"' if line.startswith("CREDENTIAL_VAULT_APP_ID") else line
                for line in content.splitlines()
            ]
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            with env_path.open("a", encoding="utf-8") as f:
                f.write(f'\nCREDENTIAL_VAULT_APP_ID="{app_id}"\n')
        print("CREDENTIAL_VAULT_APP_ID written to .env")
    else:
        print("WARNING: .env not found. Add this line manually:")
        print(f'CREDENTIAL_VAULT_APP_ID="{app_id}"')

    print("Setup complete. Vault is ready.")
    return int(app_id)


def verify_vault(app_id: int) -> None:
    from algosdk.v2client import algod

    algod_token = os.getenv("ALGOD_TOKEN", "")
    algod_server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    algod_client = algod.AlgodClient(algod_token, algod_server)

    try:
        info = algod_client.application_info(app_id)
        creator = info["params"]["creator"]
        deleted = info.get("deleted", False)
        print("Vault verification:")
        print(f"App ID: {app_id}")
        print(f"Creator: {creator}")
        print(f"Deleted: {deleted}")
        print("Vault contract is live and responsive.")
    except Exception as e:
        print(f"Vault verification failed: {e}")


if __name__ == "__main__":
    deployed_app_id = deploy_vault()
    verify_vault(deployed_app_id)

