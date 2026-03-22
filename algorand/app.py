from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure local imports work when running `python app.py`
sys.path.append(str(Path(__file__).parent))

load_dotenv()

from algorand_credential_store import (  # noqa: E402
    delete_aws_credentials,
    has_credentials,
    retrieve_aws_credentials,
    store_aws_credentials,
)
from deploy_web3 import (  # noqa: E402
    clone_github_repo,
    deploy_web3_project,
    extract_zip,
    resolve_aws_credentials,
)

app = FastAPI(title="Algorand Credential Vault")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VaultCheckRequest(BaseModel):
    access_key_id: str


class VaultStoreRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "ap-south-1"


class VaultDeleteRequest(BaseModel):
    access_key_id: str


class VaultRetrieveRequest(BaseModel):
    access_key_id: str


class GitHubDeployRequest(BaseModel):
    repo_url: str
    github_token: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_default_region: str = "ap-south-1"
    app_name: Optional[str] = None
    global_uints: Optional[int] = None
    global_bytes: Optional[int] = None
    local_uints: Optional[int] = None
    local_bytes: Optional[int] = None


def _schema_override_from(
    global_uints: Optional[int],
    global_bytes: Optional[int],
    local_uints: Optional[int],
    local_bytes: Optional[int],
) -> Optional[tuple[int, int, int, int]]:
    if any(v is not None for v in [global_uints, global_bytes, local_uints, local_bytes]):
        return (
            int(global_uints or 0),
            int(global_bytes or 0),
            int(local_uints or 0),
            int(local_bytes or 0),
        )
    return None


def _resolve_aws_for_deploy(
    aws_access_key_id: Optional[str],
    aws_secret_access_key: Optional[str],
    aws_default_region: Optional[str],
) -> dict[str, str]:
    creds = resolve_aws_credentials(aws_access_key_id, aws_secret_access_key, aws_default_region)
    if creds.get("aws_access_key_id") and not creds.get("aws_secret_access_key"):
        try:
            vault_creds = retrieve_aws_credentials(creds["aws_access_key_id"])
            return {
                "aws_access_key_id": vault_creds.get("AWS_ACCESS_KEY_ID", ""),
                "aws_secret_access_key": vault_creds.get("AWS_SECRET_ACCESS_KEY", ""),
                "aws_default_region": vault_creds.get("AWS_DEFAULT_REGION", creds.get("aws_default_region", "")),
            }
        except Exception:
            return creds
    return creds


@app.post("/vault/check")
async def vault_check(request: VaultCheckRequest):
    try:
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


@app.post("/vault/store")
async def vault_store(request: VaultStoreRequest):
    try:
        return store_aws_credentials(
            {
                "AWS_ACCESS_KEY_ID": request.aws_access_key_id,
                "AWS_SECRET_ACCESS_KEY": request.aws_secret_access_key,
                "AWS_DEFAULT_REGION": request.aws_default_region,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vault/delete")
async def vault_delete(request: VaultDeleteRequest):
    try:
        return delete_aws_credentials(request.access_key_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vault/retrieve")
async def vault_retrieve(request: VaultRetrieveRequest):
    try:
        creds = retrieve_aws_credentials(request.access_key_id)
        return {"status": "success", "credentials": creds}
    except KeyError as e:
        return {"status": "not_found", "message": str(e)}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_zip(
    file: UploadFile = File(...),
    aws_access_key_id: Optional[str] = Form(None),
    aws_secret_access_key: Optional[str] = Form(None),
    aws_default_region: Optional[str] = Form("ap-south-1"),
    app_name: Optional[str] = Form(None),
    global_uints: Optional[int] = Form(None),
    global_bytes: Optional[int] = Form(None),
    local_uints: Optional[int] = Form(None),
    local_bytes: Optional[int] = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP uploads are supported for Algorand dApp deploys.")

    temp_dir = tempfile.mkdtemp(prefix="opsonic_upload_")
    zip_path = os.path.join(temp_dir, file.filename)
    extract_dir = os.path.join(temp_dir, "extracted")

    try:
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        extract_zip(zip_path, extract_dir)
        resolved_app_name = app_name or Path(file.filename).stem
        aws_creds = _resolve_aws_for_deploy(aws_access_key_id, aws_secret_access_key, aws_default_region)
        schema_override = _schema_override_from(global_uints, global_bytes, local_uints, local_bytes)
        result = deploy_web3_project(
            extract_dir,
            resolved_app_name,
            aws_credentials=aws_creds,
            schema_override=schema_override,
        )
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            if os.path.isdir(temp_dir):
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(temp_dir)
        except Exception:
            pass


@app.post("/upload/github")
async def upload_github(request: GitHubDeployRequest):
    repo_dir = None
    try:
        repo_dir = clone_github_repo(request.repo_url, request.github_token)
        app_name = request.app_name or Path(request.repo_url.rstrip("/")).stem
        aws_creds = _resolve_aws_for_deploy(
            request.aws_access_key_id,
            request.aws_secret_access_key,
            request.aws_default_region,
        )
        schema_override = _schema_override_from(
            request.global_uints,
            request.global_bytes,
            request.local_uints,
            request.local_bytes,
        )
        result = deploy_web3_project(
            repo_dir,
            app_name,
            aws_credentials=aws_creds,
            schema_override=schema_override,
        )
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if repo_dir and os.path.isdir(repo_dir):
            try:
                for root, dirs, files in os.walk(repo_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(repo_dir)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
