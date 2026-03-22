# scripts/fund_contract.py
# Funds the vault app address from the deployer wallet.
#
# Usage:
#   cd algorand
#   python scripts/fund_contract.py 0.2
#
# Amount is in ALGO (float). If omitted, defaults to 0.2 ALGO.

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from algosdk import account, encoding, mnemonic, transaction  # noqa: E402
from algosdk.v2client import algod  # noqa: E402


def _get_algod_client() -> algod.AlgodClient:
    token = os.getenv("ALGOD_TOKEN", "")
    server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    return algod.AlgodClient(token, server)


def _get_deployer() -> tuple[str, str]:
    raw_mnemonic = os.getenv("ALGORAND_DEPLOYER_MNEMONIC", "").strip()
    if not raw_mnemonic:
        raise EnvironmentError("ALGORAND_DEPLOYER_MNEMONIC not set")
    private_key = mnemonic.to_private_key(raw_mnemonic)
    addr = account.address_from_private_key(private_key)
    return private_key, addr


def _get_vault_app_id() -> int:
    app_id = os.getenv("CREDENTIAL_VAULT_APP_ID", "").strip()
    if not app_id:
        raise EnvironmentError("CREDENTIAL_VAULT_APP_ID not set. Run: python scripts/setup_vault.py")
    return int(app_id)


def _app_address(app_id: int) -> str:
    return encoding.encode_address(encoding.checksum(b"appID" + app_id.to_bytes(8, "big")))


def main() -> int:
    try:
        amount_algo = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
    except ValueError:
        print("ERROR: amount must be a number (ALGO)")
        return 1

    if amount_algo <= 0:
        print("ERROR: amount must be > 0")
        return 1

    client = _get_algod_client()
    private_key, sender = _get_deployer()
    app_id = _get_vault_app_id()
    receiver = _app_address(app_id)

    params = client.suggested_params()
    amount_microalgo = int(amount_algo * 1_000_000)

    # Compatible with older/newer SDKs
    payment_cls = getattr(transaction, "PaymentTransaction", None) or getattr(transaction, "PaymentTxn", None)
    if payment_cls is None:
        raise RuntimeError("algosdk transaction payment class not found")

    txn = payment_cls(
        sender=sender,
        sp=params,
        receiver=receiver,
        amt=amount_microalgo,
    )
    signed = txn.sign(private_key)
    tx_id = client.send_transaction(signed)

    print(f"TX submitted: {tx_id}")
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"Funded app {app_id} with {amount_algo} ALGO")
    print(f"App address: {receiver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

