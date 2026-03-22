import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from algosdk.v2client import algod
from algosdk import account, mnemonic, transaction

ALGOD_TOKEN   = os.getenv("ALGOD_TOKEN", "")
ALGOD_SERVER  = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
MNEMONIC      = os.getenv("ALGORAND_DEPLOYER_MNEMONIC", "")
CONTRACT_ADDR = "KSSAXNRFJW3GZLOVXLQRDSXGBOPY2RZOTM3XAUJF3NVKXHEU6OQ3ODM7MY"

if not MNEMONIC:
    print("ERROR: ALGORAND_DEPLOYER_MNEMONIC not set in .env")
    sys.exit(1)

algod_client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_SERVER)
private_key  = mnemonic.to_private_key(MNEMONIC)
address      = account.address_from_private_key(private_key)

print(f"Sending 0.5 ALGO from {address[:20]}... to contract...")

params = algod_client.suggested_params()
txn    = transaction.PaymentTxn(
    sender=address,
    sp=params,
    receiver=CONTRACT_ADDR,
    amt=500000  # 0.5 ALGO in microALGO
)

signed = txn.sign(private_key)
tx_id  = algod_client.send_transaction(signed)
print(f"TX submitted: {tx_id}")

transaction.wait_for_confirmation(algod_client, tx_id, 4)
print("Done. Contract funded with 0.5 ALGO. Ready to store credentials.")