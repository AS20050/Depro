from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

