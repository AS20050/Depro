# mcpServer/infraScripts/algorand_deploy.py
#
# Algorand smart contract deployment:
# - Detect project structure (ABI spec / raw TEAL)
# - Compile if needed
# - Deploy to Algorand TestNet
# - Optionally deploy frontend to Amplify

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import boto3
import requests
from algosdk import account, encoding, mnemonic, transaction
from algosdk.v2client import algod


FRONTEND_DIR_HINTS = ["frontend", "client", "web", "ui", "app", "www"]


def _get_algod_client() -> algod.AlgodClient:
    token = os.getenv("ALGOD_TOKEN", "")
    server = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    return algod.AlgodClient(token, server)


def _get_deployer() -> tuple[str, str]:
    raw = os.getenv("ALGORAND_DEPLOYER_MNEMONIC", "").strip()
    if not raw:
        raise EnvironmentError("ALGORAND_DEPLOYER_MNEMONIC not set")
    private_key = mnemonic.to_private_key(raw)
    addr = account.address_from_private_key(private_key)
    return private_key, addr


def _app_address(app_id: int) -> str:
    return encoding.encode_address(encoding.checksum(b"appID" + app_id.to_bytes(8, "big")))


def _find_file(base: str, filename: str) -> Optional[str]:
    for root, _dirs, files in os.walk(base):
        if filename in files:
            return os.path.join(root, filename)
    return None


def _find_app_spec(base: str) -> Optional[str]:
    for name in ["application.json", "arc32.json"]:
        path = _find_file(base, name)
        if path:
            return path
    return None


def _find_teal_pair(base: str) -> tuple[Optional[str], Optional[str]]:
    approval = None
    clear = None
    for root, _dirs, files in os.walk(base):
        for f in files:
            lower = f.lower()
            if lower.endswith(".teal"):
                if "approval" in lower and approval is None:
                    approval = os.path.join(root, f)
                if "clear" in lower and clear is None:
                    clear = os.path.join(root, f)
        if approval and clear:
            return approval, clear
    return approval, clear


def _parse_state_schema(app_json: dict) -> tuple[int, int, int, int]:
    state = app_json.get("state") or app_json.get("schema") or {}
    global_state = state.get("global") or state.get("global_state") or {}
    local_state = state.get("local") or state.get("local_state") or {}

    if isinstance(global_state, dict) and "num_uints" in global_state:
        return (
            int(global_state.get("num_uints", 0)),
            int(global_state.get("num_byte_slices", 0)),
            int(local_state.get("num_uints", 0)),
            int(local_state.get("num_byte_slices", 0)),
        )

    def count_types(items: list) -> tuple[int, int]:
        uints = bytes_ = 0
        for item in items:
            t = str(item.get("type") or item.get("value_type") or "").lower()
            if "uint" in t:
                uints += 1
            elif "byte" in t:
                bytes_ += 1
        return uints, bytes_

    g_list = app_json.get("global-state") or app_json.get("global_state") or []
    l_list = app_json.get("local-state") or app_json.get("local_state") or []
    if isinstance(g_list, list) or isinstance(l_list, list):
        g_uints, g_bytes = count_types(g_list if isinstance(g_list, list) else [])
        l_uints, l_bytes = count_types(l_list if isinstance(l_list, list) else [])
        return g_uints, g_bytes, l_uints, l_bytes

    return 0, 0, 0, 0


def deploy_contract(project_path: str) -> dict[str, Any]:
    """Deploy an Algorand smart contract from project source."""
    algod_client = _get_algod_client()
    private_key, sender = _get_deployer()

    approval_teal, clear_teal = _find_teal_pair(project_path)
    app_spec_path = _find_app_spec(project_path)

    approval_bytes = None
    clear_bytes = None
    schema = (0, 0, 0, 0)

    # Try loading compiled programs from ABI spec
    if app_spec_path:
        data = json.loads(Path(app_spec_path).read_text(encoding="utf-8", errors="ignore"))
        schema = _parse_state_schema(data)
        a_b64 = data.get("approval_program")
        c_b64 = data.get("clear_program")
        if a_b64 and c_b64:
            approval_bytes = base64.b64decode(a_b64)
            clear_bytes = base64.b64decode(c_b64)

    # Fallback: compile raw TEAL
    if approval_bytes is None or clear_bytes is None:
        if not approval_teal or not clear_teal:
            raise FileNotFoundError("Could not find approval/clear TEAL or compiled programs")
        approval_result = algod_client.compile(Path(approval_teal).read_text(encoding="utf-8", errors="ignore"))
        clear_result = algod_client.compile(Path(clear_teal).read_text(encoding="utf-8", errors="ignore"))
        approval_bytes = base64.b64decode(approval_result["result"])
        clear_bytes = base64.b64decode(clear_result["result"])

    g_uints, g_bytes, l_uints, l_bytes = schema
    params = algod_client.suggested_params()
    txn = transaction.ApplicationCreateTxn(
        sender=sender,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_bytes,
        clear_program=clear_bytes,
        global_schema=transaction.StateSchema(num_uints=g_uints, num_byte_slices=g_bytes),
        local_schema=transaction.StateSchema(num_uints=l_uints, num_byte_slices=l_bytes),
    )

    signed = txn.sign(private_key)
    tx_id = algod_client.send_transaction(signed)
    transaction.wait_for_confirmation(algod_client, tx_id, 4)

    result = algod_client.pending_transaction_info(tx_id)
    app_id = int(result.get("application-index"))
    return {
        "app_id": app_id,
        "app_address": _app_address(app_id),
        "explorer_url": f"https://testnet.algoexplorer.io/application/{app_id}",
    }


def find_frontend_dir(project_path: str) -> Optional[str]:
    """Find frontend directory within a dApp project."""
    for hint in FRONTEND_DIR_HINTS:
        candidate = os.path.join(project_path, hint)
        if os.path.exists(os.path.join(candidate, "package.json")):
            return candidate
    for root, _dirs, files in os.walk(project_path):
        if "package.json" in files:
            return root
    return None


def _normalize_app_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9-]+", "-", name).strip("-")
    if len(name) < 3:
        name = f"depro-{int(time.time())}"
    return name[:64]


def deploy_frontend_to_amplify(source_path: str, app_name: str) -> dict[str, Any]:
    """Build and deploy a frontend to AWS Amplify."""
    region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    amplify = boto3.client("amplify", region_name=region)

    if not os.path.exists(os.path.join(source_path, "package.json")):
        raise FileNotFoundError("No package.json found for frontend")

    npm_path = shutil.which("npm")
    if npm_path:
        subprocess.run([npm_path, "install"], check=True, cwd=source_path)
        subprocess.run([npm_path, "run", "build"], check=True, cwd=source_path)
    else:
        build_js = os.path.join(source_path, "build.js")
        node_path = shutil.which("node")
        if node_path and os.path.exists(build_js):
            subprocess.run([node_path, build_js], check=True, cwd=source_path)
        else:
            raise RuntimeError("npm not found. Install Node.js.")

    build_dir = os.path.join(source_path, "dist")
    if not os.path.exists(build_dir):
        build_dir = os.path.join(source_path, "build")
    if not os.path.exists(build_dir):
        raise FileNotFoundError("Build failed. dist/build not found.")

    zip_dir = tempfile.mkdtemp(prefix="amplify_build_")
    zip_name = os.path.join(zip_dir, "amplify_build_artifact")
    zip_file = f"{zip_name}.zip"
    shutil.make_archive(zip_name, "zip", build_dir)

    app_name = _normalize_app_name(app_name)
    apps = amplify.list_apps()
    app_id = None
    for app in apps.get("apps", []):
        if app.get("name") == app_name:
            app_id = app["appId"]
            break
    if not app_id:
        res = amplify.create_app(name=app_name, platform="WEB")
        app_id = res["app"]["appId"]

    branch_name = "main"
    try:
        amplify.get_branch(appId=app_id, branchName=branch_name)
    except amplify.exceptions.NotFoundException:
        amplify.create_branch(appId=app_id, branchName=branch_name)

    deploy_config = amplify.create_deployment(appId=app_id, branchName=branch_name)
    job_id = deploy_config["jobId"]
    upload_url = deploy_config["zipUploadUrl"]

    with open(zip_file, "rb") as f:
        requests.put(upload_url, data=f, headers={"Content-Type": "application/zip"})

    amplify.start_deployment(appId=app_id, branchName=branch_name, jobId=job_id)

    deploy_url = f"https://{branch_name}.{app_id}.amplifyapp.com"
    try:
        for _ in range(30):
            job = amplify.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
            status = job["job"]["summary"]["status"]
            if status == "SUCCEED":
                return {"endpoint": deploy_url, "amplify_app_id": app_id}
            if status in ["FAILED", "CANCELLED"]:
                raise RuntimeError(f"Amplify deployment failed: {status}")
            time.sleep(5)
    finally:
        if os.path.exists(zip_file):
            os.remove(zip_file)
        if os.path.isdir(zip_dir):
            shutil.rmtree(zip_dir, ignore_errors=True)

    raise TimeoutError("Amplify deployment timed out.")


def deploy_algorand_dapp(project_path: str, app_name: str) -> dict[str, Any]:
    """
    Full Algorand dApp deployment pipeline:
    1. Deploy smart contract to TestNet
    2. If frontend/ exists, deploy to Amplify
    """
    print(f"[ALGORAND] Deploying contract from: {project_path}")
    contract = deploy_contract(project_path)

    response: dict[str, Any] = {
        "status": "success",
        "deployment": "algorand_dapp",
        "project_type": "algorand_dapp",
        "app_id": contract["app_id"],
        "app_address": contract["app_address"],
        "explorer_url": contract["explorer_url"],
    }

    frontend_dir = find_frontend_dir(project_path)
    if frontend_dir:
        print(f"[ALGORAND] Frontend found at: {frontend_dir}")
        try:
            frontend = deploy_frontend_to_amplify(frontend_dir, app_name)
            response["endpoint"] = frontend["endpoint"]
            response["amplify_app_id"] = frontend["amplify_app_id"]
        except Exception as e:
            print(f"[ALGORAND] Frontend deploy failed (contract still deployed): {e}")
            response["frontend_error"] = str(e)
    else:
        print("[ALGORAND] No frontend directory found. Contract-only deployment.")

    response["message"] = f"Algorand dApp deployed. App ID: {contract['app_id']}"
    return response
