from __future__ import annotations

import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Ensure local package imports work when running `python app.py`
sys.path.append(str(Path(__file__).parent))

# Best-effort: avoid UnicodeEncodeError on Windows consoles
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()

from fileUploadLayer.services.github_handler import clone_github_repo  # noqa: E402
from fileUploadLayer.services.zip_handler import extract_zip  # noqa: E402
from codeReviewLayer.reviewer import review_project  # noqa: E402
from aiLayer.decision_engine import decide_and_execute  # noqa: E402
from auth.aws_credentials import resolve_aws_credentials  # noqa: E402
from auth.auth_routes import router as auth_router  # noqa: E402
from auth.wallet_auth import get_wallet_from_request  # noqa: E402
from mcpServer.infraScripts.x402_payment import (  # noqa: E402
    get_fee_table,
    get_required_fee,
    verify_payment,
)

app = FastAPI(title="dePro")

# ------------------------------------------
# Auth Router
# ------------------------------------------
app.include_router(auth_router)

# ------------------------------------------
# CORS
# ------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------
# Storage
# ------------------------------------------
UPLOAD_DIR = Path("storage/uploads")
EXTRACT_DIR = Path("storage/extracted/zip")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_rmtree(path: Path) -> None:
    """Windows-safe directory delete (handles read-only files)."""
    if not path.exists():
        return

    import stat

    def remove_readonly(func, target_path, _excinfo):
        os.chmod(target_path, stat.S_IWRITE)
        func(target_path)

    shutil.rmtree(path, onerror=remove_readonly)


def _infer_deployment_type(review_output: dict, filename: str) -> str:
    """Infer deployment type from review output for fee calculation."""
    if filename.endswith(".jar"):
        return "jar"
    ai = review_output.get("ai_understanding", {}) or {}
    pt = str(ai.get("project_type", "")).lower()
    if pt == "algorand_dapp" or ai.get("is_algorand_dapp"):
        return "algorand_dapp"
    if pt == "frontend":
        return "frontend"
    if pt in ("backend", "fullstack"):
        return pt
    # Fallback from dependencies
    deps = review_output.get("dependencies", {}) or {}
    if deps.get("is_algorand_project"):
        return "algorand_dapp"
    return "backend"


def _build_payment_required_response(deployment_type: str) -> JSONResponse:
    """Return HTTP 402 with fee info for the frontend to show PaymentModal."""
    fee_micro = get_required_fee(deployment_type)
    treasury = os.getenv(
        "DEPRO_TREASURY_ADDRESS",
        "7UCTS3PFI3ARHWEONK4SVTMW643WBANSLT6CPLATRAIRTUPCDIRZEOOK54",
    )
    return JSONResponse(
        status_code=402,
        content={
            "status": "payment_required",
            "amount_algo": fee_micro / 1_000_000,
            "amount_microalgo": fee_micro,
            "receiver": treasury,
            "deployment_type": deployment_type,
            "message": "Payment required before deployment. Send ALGO to the treasury address and provide the TX ID.",
        },
    )


# =========================================================
# x402 PAYMENT ENDPOINTS
# =========================================================
@app.get("/x402/fees")
async def x402_fees():
    """Return fee table for all deployment types."""
    return {"status": "success", "fees": get_fee_table()}


class X402VerifyRequest(BaseModel):
    tx_id: str
    deployment_type: str = "backend"


@app.post("/x402/verify")
async def x402_verify(req: X402VerifyRequest):
    """Pre-verify a payment TX before upload."""
    try:
        result = verify_payment(req.tx_id, req.deployment_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================
# 1) GENERIC UPLOAD + ORCHESTRATION (auth + payment gated)
# =========================================================
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    aws_access_key_id: str | None = Form(None),
    aws_secret_access_key: str | None = Form(None),
    payment_tx_id: str | None = Form(None),
    authorization: Optional[str] = Header(None),
):
    try:
        # Auth check
        wallet_address = None
        if authorization:
            try:
                wallet_address = get_wallet_from_request(authorization)
            except ValueError:
                pass  # Auth optional for now

        original_name = file.filename or "unknown_file"
        clean_name = os.path.basename(original_name).strip() or f"upload_{int(time.time())}.bin"
        filename = clean_name
        upload_path = UPLOAD_DIR / filename

        # Save uploaded file
        print(f"Saving to: {upload_path}")
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        print(f"File uploaded: {upload_path}")

        # ZIP -> extract -> review -> AI decision
        if filename.endswith(".zip"):
            extract_path = EXTRACT_DIR
            _safe_rmtree(extract_path)
            extract_path.mkdir(parents=True, exist_ok=True)

            extract_zip(upload_path, extract_path)
            print(f"ZIP extracted to: {extract_path}")

            review_output = review_project(str(extract_path))

            # Determine deployment type for payment check
            deployment_type = _infer_deployment_type(review_output, filename)

            # Payment gate: if no payment_tx_id, return 402
            if not payment_tx_id:
                return _build_payment_required_response(deployment_type)

            # Verify payment
            try:
                payment_receipt = verify_payment(payment_tx_id, deployment_type)
            except ValueError as e:
                raise HTTPException(status_code=402, detail=str(e))

            vault_stored: bool | None = None

            # Auto-store to vault if frontend supplied fresh full credentials
            if aws_access_key_id and aws_secret_access_key:
                vault_stored = False
                try:
                    from mcpServer.infraScripts.algorand_credential_store import store_aws_credentials

                    store_aws_credentials(
                        {
                            "AWS_ACCESS_KEY_ID": aws_access_key_id,
                            "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
                            "AWS_DEFAULT_REGION": "ap-south-1",
                        }
                    )
                    vault_stored = True
                except Exception as e:
                    print(f"[VAULT] Auto-store failed (non-fatal): {e}")

            # Resolve AWS credentials for zip-based deploy paths (Amplify/EC2).
            try:
                resolve_aws_credentials(
                    access_key_id=aws_access_key_id,
                    secret_access_key=aws_secret_access_key,
                    region="ap-south-1",
                    allow_terminal_prompt=False,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            deployment_context = review_output.copy()
            deployment_context["project_path"] = str(extract_path)
            deployment_context["filename"] = filename
            deployment_context["repo_url"] = None
            deployment_context["github_token"] = None

            result = decide_and_execute(deployment_context)
            if isinstance(result, dict):
                if vault_stored is not None:
                    result["vault_stored"] = vault_stored
                if wallet_address:
                    result["deployed_by"] = wallet_address
                result["payment"] = payment_receipt
            return result

        # JAR -> vault-aware credential resolution -> EC2 deploy
        if filename.endswith(".jar"):
            print("JAR detected -> direct EC2 deployment")

            deployment_type = "jar"

            # Payment gate
            if not payment_tx_id:
                return _build_payment_required_response(deployment_type)

            try:
                payment_receipt = verify_payment(payment_tx_id, deployment_type)
            except ValueError as e:
                raise HTTPException(status_code=402, detail=str(e))

            vault_stored: bool | None = None
            try:
                creds = resolve_aws_credentials(
                    access_key_id=aws_access_key_id,
                    secret_access_key=aws_secret_access_key,
                    region="ap-south-1",
                    allow_terminal_prompt=False,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            # Auto-store to vault if frontend supplied fresh full credentials
            if aws_access_key_id and aws_secret_access_key:
                vault_stored = False
                try:
                    from mcpServer.infraScripts.algorand_credential_store import store_aws_credentials

                    store_aws_credentials(creds)
                    vault_stored = True
                except Exception as e:
                    print(f"[VAULT] Auto-store failed (non-fatal): {e}")

            # Env vars for deploy scripts
            os.environ["APP_FILE"] = filename
            os.environ["APP_PORT"] = "8080"
            os.environ["KEY_NAME"] = "ubuntu-auto-keypair-v2"

            # Copy JAR to project root (some deploy scripts assume CWD root)
            root_jar_path = Path(filename)
            if root_jar_path.exists():
                try:
                    os.remove(root_jar_path)
                except Exception:
                    pass
            shutil.copy(upload_path, root_jar_path)

            result = decide_and_execute({"artifact_type": "jar", "artifact_path": str(upload_path)})
            if isinstance(result, dict):
                if vault_stored is not None:
                    result["vault_stored"] = vault_stored
                if wallet_address:
                    result["deployed_by"] = wallet_address
                result["payment"] = payment_receipt
            return result

        # Unsupported
        return {
            "status": "uploaded",
            "file": filename,
            "message": "File stored. No deployment pipeline for this file type yet.",
        }

    except HTTPException:
        raise
    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 2) STANDALONE REVIEW ENDPOINT (no auth needed)
# =========================================================
class ReviewRequest(BaseModel):
    project_path: str


@app.post("/review")
async def review_repo(request: ReviewRequest):
    try:
        print(f"Starting review for: {request.project_path}")
        result = review_project(request.project_path)
        return {"status": "success", "review": result}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 3) GITHUB UPLOAD (auth + payment gated)
# =========================================================
@app.post("/upload/github")
async def upload_github_repo(
    repo_url: str = Form(...),
    github_token: str | None = Form(None),
    aws_access_key_id: str | None = Form(None),
    aws_secret_access_key: str | None = Form(None),
    payment_tx_id: str | None = Form(None),
    authorization: Optional[str] = Header(None),
):
    try:
        # Auth check
        wallet_address = None
        if authorization:
            try:
                wallet_address = get_wallet_from_request(authorization)
            except ValueError:
                pass

        repo_path = clone_github_repo(repo_url, github_token)
        print(f"GitHub repo cloned to: {repo_path}")

        review_output = review_project(repo_path)

        # Determine deployment type
        deployment_type = _infer_deployment_type(review_output, repo_url.split("/")[-1])

        # Payment gate
        if not payment_tx_id:
            return _build_payment_required_response(deployment_type)

        try:
            payment_receipt = verify_payment(payment_tx_id, deployment_type)
        except ValueError as e:
            raise HTTPException(status_code=402, detail=str(e))

        vault_stored: bool | None = None

        # Auto-store to vault if frontend supplied fresh full credentials
        if aws_access_key_id and aws_secret_access_key:
            vault_stored = False
            try:
                from mcpServer.infraScripts.algorand_credential_store import store_aws_credentials

                store_aws_credentials(
                    {
                        "AWS_ACCESS_KEY_ID": aws_access_key_id,
                        "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
                        "AWS_DEFAULT_REGION": "ap-south-1",
                    }
                )
                vault_stored = True
            except Exception as e:
                print(f"[VAULT] Auto-store failed (non-fatal): {e}")

        # Resolve AWS credentials for GitHub deploy paths (Amplify/EC2).
        try:
            resolve_aws_credentials(
                access_key_id=aws_access_key_id,
                secret_access_key=aws_secret_access_key,
                region="ap-south-1",
                allow_terminal_prompt=False,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        deployment_context = review_output.copy()
        deployment_context["project_path"] = repo_path
        deployment_context["filename"] = repo_url.split("/")[-1]
        deployment_context["repo_url"] = repo_url
        deployment_context["github_token"] = github_token

        result = decide_and_execute(deployment_context)
        if isinstance(result, dict):
            if vault_stored is not None:
                result["vault_stored"] = vault_stored
            if wallet_address:
                result["deployed_by"] = wallet_address
            result["payment"] = payment_receipt
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 4) VAULT - CHECK
# =========================================================
class VaultCheckRequest(BaseModel):
    access_key_id: str


@app.post("/vault/check")
async def vault_check(request: VaultCheckRequest):
    """Check if credentials exist in Algorand vault (read-only)."""
    try:
        from mcpServer.infraScripts.algorand_credential_store import has_credentials

        exists = has_credentials(request.access_key_id)
        return {
            "status": "success",
            "exists": exists,
            "message": "Credentials found in Algorand vault."
            if exists
            else "No credentials stored for this access key ID.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 5) VAULT - STORE
# =========================================================
class VaultStoreRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "ap-south-1"


@app.post("/vault/store")
async def vault_store(request: VaultStoreRequest):
    """Explicitly encrypt and store credentials in Algorand vault."""
    try:
        from mcpServer.infraScripts.algorand_credential_store import store_aws_credentials

        return store_aws_credentials(
            {
                "AWS_ACCESS_KEY_ID": request.aws_access_key_id,
                "AWS_SECRET_ACCESS_KEY": request.aws_secret_access_key,
                "AWS_DEFAULT_REGION": request.aws_default_region,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 6) VAULT - DELETE
# =========================================================
class VaultDeleteRequest(BaseModel):
    access_key_id: str


@app.post("/vault/delete")
async def vault_delete(request: VaultDeleteRequest):
    """Delete credentials from Algorand vault (box deletion)."""
    try:
        from mcpServer.infraScripts.algorand_credential_store import delete_aws_credentials

        return delete_aws_credentials(request.access_key_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
