# mcpServer/infraScripts/x402_payment.py
#
# x402 protocol: verify on-chain ALGO payment before allowing deployments.

from __future__ import annotations

import os
from typing import Any

from algosdk.v2client import algod

TREASURY_ADDRESS = os.getenv(
    "DEPRO_TREASURY_ADDRESS",
    "7UCTS3PFI3ARHWEONK4SVTMW643WBANSLT6CPLATRAIRTUPCDIRZEOOK54",
)

# Fee table in microAlgos (1 ALGO = 1_000_000 microAlgos)
FEE_TABLE = {
    "frontend": 1_000_000,      # 1 ALGO
    "backend": 3_000_000,       # 3 ALGO
    "fullstack": 3_000_000,     # 3 ALGO
    "algorand_dapp": 2_000_000, # 2 ALGO
    "jar": 3_000_000,           # 3 ALGO
}

# In-memory replay prevention (fine for hackathon; resets on restart)
_used_tx_ids: set[str] = set()


def _get_algod_client() -> algod.AlgodClient:
    token = os.getenv("ALGOD_TOKEN", "")
    server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    return algod.AlgodClient(token, server)


def get_fee_table() -> dict[str, Any]:
    """Return human-readable fee table."""
    return {
        dtype: {"algo": amount / 1_000_000, "microalgo": amount}
        for dtype, amount in FEE_TABLE.items()
    }


def get_required_fee(deployment_type: str) -> int:
    """Return required fee in microAlgos for given deployment type."""
    return FEE_TABLE.get(deployment_type, 3_000_000)


def verify_payment(tx_id: str, deployment_type: str) -> dict[str, Any]:
    """
    Verify an Algorand payment transaction:
    1. TX exists on TestNet
    2. Receiver == treasury address
    3. Amount >= required fee
    4. TX not already used (replay prevention)
    """
    tx_id = (tx_id or "").strip()
    if not tx_id:
        raise ValueError("payment_tx_id is required.")

    if tx_id in _used_tx_ids:
        raise ValueError("This transaction ID has already been used.")

    required = get_required_fee(deployment_type)
    client = _get_algod_client()

    try:
        tx_info = client.pending_transaction_info(tx_id)
    except Exception:
        # Not in pending pool — check confirmed transactions via indexer-like lookup
        try:
            # algod doesn't have indexer search, but pending_transaction_info works
            # for recently confirmed txs too
            tx_info = client.pending_transaction_info(tx_id)
        except Exception as exc:
            raise ValueError(f"Transaction {tx_id} not found on TestNet: {exc}") from exc

    # Check it's a payment transaction
    tx_type = tx_info.get("txn", {}).get("txn", {}).get("type") or tx_info.get("tx-type", "")
    txn_data = tx_info.get("txn", {}).get("txn", {}) or tx_info.get("transaction", {})

    receiver = txn_data.get("rcv") or tx_info.get("payment-transaction", {}).get("receiver", "")
    amount = txn_data.get("amt", 0) or tx_info.get("payment-transaction", {}).get("amount", 0)

    if not receiver:
        raise ValueError("Transaction is not a payment transaction.")

    # Algorand addresses in raw txn are base32-encoded
    from algosdk import encoding
    try:
        receiver_addr = encoding.encode_address(encoding.decode_address(receiver)) if len(receiver) != 58 else receiver
    except Exception:
        receiver_addr = receiver

    if receiver_addr != TREASURY_ADDRESS:
        raise ValueError(
            f"Payment receiver mismatch. Expected: {TREASURY_ADDRESS[:12]}... Got: {receiver_addr[:12]}..."
        )

    if amount < required:
        raise ValueError(
            f"Insufficient payment. Required: {required / 1_000_000} ALGO, Got: {amount / 1_000_000} ALGO"
        )

    # Mark TX as used
    _used_tx_ids.add(tx_id)

    return {
        "status": "verified",
        "tx_id": tx_id,
        "amount_algo": amount / 1_000_000,
        "deployment_type": deployment_type,
        "message": "Payment verified successfully.",
    }
