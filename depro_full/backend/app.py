from __future__ import annotations

import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(title="Opsonic")

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


# =========================================================
# 1) GENERIC UPLOAD + ORCHESTRATION
# =========================================================
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    aws_access_key_id: str | None = Form(None),
    aws_secret_access_key: str | None = Form(None),
):
    try:
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

            vault_stored: bool | None = None

            # Auto-store to vault if frontend supplied fresh full credentials (independent of project type).
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
            if vault_stored is not None and isinstance(result, dict):
                result["vault_stored"] = vault_stored
            return result

        # JAR -> vault-aware credential resolution -> EC2 deploy
        if filename.endswith(".jar"):
            print("JAR detected -> direct EC2 deployment")

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
                    # Non-fatal: vault failure must not block deployment
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
            if vault_stored is not None and isinstance(result, dict):
                result["vault_stored"] = vault_stored
            return result

        # Unsupported
        return {
            "status": "uploaded",
            "file": filename,
            "message": "File stored. No deployment pipeline for this file type yet.",
        }

    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 2) STANDALONE REVIEW ENDPOINT
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
# 3) GITHUB UPLOAD
# =========================================================
@app.post("/upload/github")
async def upload_github_repo(
    repo_url: str = Form(...),
    github_token: str | None = Form(None),
    aws_access_key_id: str | None = Form(None),
    aws_secret_access_key: str | None = Form(None),
):
    try:
        repo_path = clone_github_repo(repo_url, github_token)
        print(f"GitHub repo cloned to: {repo_path}")

        review_output = review_project(repo_path)

        vault_stored: bool | None = None

        # Auto-store to vault if frontend supplied fresh full credentials (independent of project type).
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
        if vault_stored is not None and isinstance(result, dict):
            result["vault_stored"] = vault_stored
        return result
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
