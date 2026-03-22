from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Optional

import boto3
import requests
from algosdk import account, encoding, mnemonic, transaction
from algosdk.v2client import algod


FRONTEND_DIR_HINTS = ["frontend", "client", "web", "ui", "app", "www"]
ALGOKIT_MARKERS = ["algokit.toml"]
ALGO_PY_IMPORTS = ["pyteal", "algopy", "algokit_utils", "beaker"]
ALGO_DEPENDENCY_KEYS = ["pyteal", "algopy", "algokit-utils", "beaker", "algosdk"]


def extract_zip(zip_path: str, extract_dir: str) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)


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


def _scan_python_for_algorand(base: str) -> bool:
    for root, _dirs, files in os.walk(base):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            try:
                content = Path(path).read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            for key in ALGO_PY_IMPORTS:
                if key in content:
                    return True
    return False


def _scan_dependencies_for_algorand(base: str) -> bool:
    req_path = _find_file(base, "requirements.txt")
    if req_path:
        content = Path(req_path).read_text(encoding="utf-8", errors="ignore").lower()
        if any(dep in content for dep in ALGO_DEPENDENCY_KEYS):
            return True

    pyproject = _find_file(base, "pyproject.toml")
    if pyproject:
        content = Path(pyproject).read_text(encoding="utf-8", errors="ignore").lower()
        if any(dep in content for dep in ALGO_DEPENDENCY_KEYS):
            return True

    return False


def detect_algorand_project(project_path: str) -> dict[str, Any]:
    signals: list[str] = []

    for marker in ALGOKIT_MARKERS:
        if _find_file(project_path, marker):
            signals.append(f"config:{marker}")

    app_spec_path = _find_app_spec(project_path)
    if app_spec_path:
        signals.append(f"app_spec:{Path(app_spec_path).name}")

    approval_teal, clear_teal = _find_teal_pair(project_path)
    if approval_teal and clear_teal:
        signals.append("teal_pair:approval+clear")

    if _scan_python_for_algorand(project_path):
        signals.append("python_imports:algorand")

    if _scan_dependencies_for_algorand(project_path):
        signals.append("deps:algorand")

    return {
        "is_algorand": len(signals) > 0,
        "signals": signals,
        "app_spec_path": app_spec_path,
        "approval_teal": approval_teal,
        "clear_teal": clear_teal,
    }


def _parse_state_schema(app_json: dict[str, Any]) -> tuple[int, int, int, int]:
    # Try a few common schema shapes.
    state = app_json.get("state") or app_json.get("schema") or {}
    global_state = state.get("global") or state.get("global_state") or {}
    local_state = state.get("local") or state.get("local_state") or {}

    if isinstance(global_state, dict) and "num_uints" in global_state:
        g_uints = int(global_state.get("num_uints", 0))
        g_bytes = int(global_state.get("num_byte_slices", 0))
        l_uints = int(local_state.get("num_uints", 0))
        l_bytes = int(local_state.get("num_byte_slices", 0))
        return g_uints, g_bytes, l_uints, l_bytes

    # ARC-32 may include global-state/local-state as arrays.
    def count_types(items: list) -> tuple[int, int]:
        uints = 0
        bytes_ = 0
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


def _load_compiled_programs(app_spec_path: str) -> tuple[Optional[bytes], Optional[bytes], tuple[int, int, int, int]]:
    data = json.loads(Path(app_spec_path).read_text(encoding="utf-8", errors="ignore"))
    schema = _parse_state_schema(data)

    approval_b64 = data.get("approval_program")
    clear_b64 = data.get("clear_program")
    if approval_b64 and clear_b64:
        return base64.b64decode(approval_b64), base64.b64decode(clear_b64), schema

    return None, None, schema


def deploy_algorand_contract(
    project_path: str,
    schema_override: Optional[tuple[int, int, int, int]] = None,
) -> dict[str, Any]:
    algod_client = _get_algod_client()
    private_key, sender = _get_deployer()

    approval_teal, clear_teal = _find_teal_pair(project_path)
    app_spec_path = _find_app_spec(project_path)

    approval_bytes = None
    clear_bytes = None
    schema = (0, 0, 0, 0)

    if app_spec_path:
        approval_bytes, clear_bytes, schema = _load_compiled_programs(app_spec_path)

    if approval_bytes is None or clear_bytes is None:
        if not approval_teal or not clear_teal:
            raise FileNotFoundError("Could not find approval/clear TEAL or compiled programs")
        approval_result = algod_client.compile(Path(approval_teal).read_text(encoding="utf-8", errors="ignore"))
        clear_result = algod_client.compile(Path(clear_teal).read_text(encoding="utf-8", errors="ignore"))
        approval_bytes = base64.b64decode(approval_result["result"])
        clear_bytes = base64.b64decode(clear_result["result"])

    if schema_override:
        schema = schema_override

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
    # Prefer known names
    for hint in FRONTEND_DIR_HINTS:
        candidate = os.path.join(project_path, hint)
        if os.path.exists(os.path.join(candidate, "package.json")):
            return candidate

    # Fallback: first directory with package.json
    for root, _dirs, files in os.walk(project_path):
        if "package.json" in files:
            return root
    return None


def _normalize_app_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9-]+", "-", name).strip("-")
    if len(name) < 3:
        name = f"opsonic-{int(time.time())}"
    return name[:64]


def deploy_frontend_to_amplify(
    source_path: str,
    app_name: str,
    aws_credentials: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    region = (aws_credentials or {}).get("aws_default_region") or os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

    if aws_credentials and aws_credentials.get("aws_access_key_id") and aws_credentials.get("aws_secret_access_key"):
        session = boto3.Session(
            aws_access_key_id=aws_credentials["aws_access_key_id"],
            aws_secret_access_key=aws_credentials["aws_secret_access_key"],
            region_name=region,
        )
    else:
        session = boto3.Session(region_name=region)

    amplify = session.client("amplify", region_name=region)

    if not os.path.exists(os.path.join(source_path, "package.json")):
        raise FileNotFoundError("No package.json found for frontend")

    def _run_cmd(cmd: list[str], cwd: str, label: str) -> None:
        try:
            subprocess.run(cmd, check=True, cwd=cwd)
        except FileNotFoundError as exc:
            raise RuntimeError(f"{label} not found. Command: {cmd} (cwd={cwd})") from exc

    npm_path = shutil.which("npm")
    if npm_path:
        _run_cmd([npm_path, "install"], source_path, "npm")
        _run_cmd([npm_path, "run", "build"], source_path, "npm")
    else:
        build_js = os.path.join(source_path, "build.js")
        node_path = shutil.which("node")
        if node_path and os.path.exists(build_js):
            _run_cmd([node_path, build_js], source_path, "node")
        else:
            raise RuntimeError("npm not found. Install Node.js (includes npm) or provide build.js with node available.")

    build_dir = os.path.join(source_path, "dist")
    if not os.path.exists(build_dir):
        build_dir = os.path.join(source_path, "build")
    if not os.path.exists(build_dir):
        raise FileNotFoundError("Build failed. dist/build not found.")

    zip_dir = tempfile.mkdtemp(prefix="amplify_build_")
    zip_name = os.path.join(zip_dir, "amplify_build_artifact")
    zip_file = f"{zip_name}.zip"
    shutil.make_archive(zip_name, "zip", build_dir)

    apps = amplify.list_apps()
    app_name = _normalize_app_name(app_name)
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
                return {"endpoint": deploy_url, "app_id": app_id}
            if status in ["FAILED", "CANCELLED"]:
                raise RuntimeError(f"Amplify deployment failed: {status}")
            time.sleep(5)
    finally:
        if os.path.exists(zip_file):
            os.remove(zip_file)
        if os.path.isdir(zip_dir):
            shutil.rmtree(zip_dir, ignore_errors=True)

    raise TimeoutError("Amplify deployment timed out.")


def clone_github_repo(repo_url: str, token: Optional[str]) -> str:
    tmp_dir = tempfile.mkdtemp(prefix="opsonic_repo_")
    clone_url = repo_url
    if token and "github.com" in repo_url:
        clone_url = repo_url.replace("https://", f"https://{token}@")
    subprocess.run(["git", "clone", clone_url, tmp_dir], check=True)
    return tmp_dir


def resolve_aws_credentials(
    aws_access_key_id: Optional[str],
    aws_secret_access_key: Optional[str],
    aws_default_region: Optional[str],
) -> dict[str, str]:
    access_key = (aws_access_key_id or "").strip()
    secret_key = (aws_secret_access_key or "").strip()
    region = (aws_default_region or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1").strip()

    if access_key and secret_key:
        return {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "aws_default_region": region,
        }

    env_access = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    env_secret = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    env_region = (os.getenv("AWS_DEFAULT_REGION") or region).strip()

    if env_access and env_secret:
        return {
            "aws_access_key_id": env_access,
            "aws_secret_access_key": env_secret,
            "aws_default_region": env_region,
        }

    if access_key:
        return {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": "",
            "aws_default_region": region,
        }

    return {}


def deploy_web3_project(
    project_path: str,
    app_name: str,
    aws_credentials: Optional[dict[str, str]] = None,
    schema_override: Optional[tuple[int, int, int, int]] = None,
) -> dict[str, Any]:
    detection = detect_algorand_project(project_path)
    if not detection["is_algorand"]:
        raise ValueError("Unknown project type. No Algorand signals detected.")

    contract = deploy_algorand_contract(project_path, schema_override=schema_override)
    response: dict[str, Any] = {
        "project_type": "algorand_dapp",
        "signals": detection["signals"],
        "app_id": contract["app_id"],
        "app_address": contract["app_address"],
        "explorer_url": contract["explorer_url"],
    }

    frontend_dir = find_frontend_dir(project_path)
    if frontend_dir:
        if not aws_credentials or not aws_credentials.get("aws_secret_access_key"):
            raise ValueError("AWS credentials are required to deploy the frontend to Amplify.")
        frontend = deploy_frontend_to_amplify(frontend_dir, app_name, aws_credentials)
        response["endpoint"] = frontend["endpoint"]
        response["amplify_app_id"] = frontend["app_id"]

    return response
