"""
endpoints/vault.py — API endpoints for managing AWS credentials via Algorand Vault

Store/Retrieve/Delete user's IAM credentials.
The secret key is encrypted with AES-256-GCM and stored in Algorand box storage.
Only the access_key_id (non-secret) is saved in the user's DB record.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import User
from auth.jwt_handler import get_current_user

router = APIRouter(prefix="/api/vault", tags=["Credential Vault"])


class StoreCredsRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "ap-south-1"


@router.post("/store")
async def store_credentials(
    body: StoreCredsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Encrypt and store IAM credentials in Algorand vault.
    Saves only the access_key_id in the user's DB record.
    """
    try:
        from credential_vault import vault_store

        result = vault_store(
            access_key_id=body.aws_access_key_id,
            secret_access_key=body.aws_secret_access_key,
            region=body.aws_default_region,
        )

        # Save only the access key ID in user's DB record (not the secret)
        user.aws_access_key_id = body.aws_access_key_id
        user.aws_default_region = body.aws_default_region
        await db.commit()

        return {
            "status": "success",
            "message": "Credentials encrypted and stored in Algorand vault.",
            "access_key_hint": result.get("access_key_hint"),
            "vault_app_id": result.get("vault_app_id"),
            "explorer_url": result.get("explorer_url"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vault error: {e}")


@router.get("/status")
async def vault_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the user has credentials stored in the vault."""
    access_key = user.aws_access_key_id
    if not access_key:
        return {
            "status": "success",
            "has_credentials": False,
            "message": "No credentials stored yet.",
        }

    try:
        from credential_vault import vault_exists

        exists = vault_exists(access_key)
        return {
            "status": "success",
            "has_credentials": exists,
            "access_key_hint": f"{access_key[:4]}****{access_key[-4:]}",
            "region": user.aws_default_region or "ap-south-1",
        }
    except Exception as e:
        return {
            "status": "success",
            "has_credentials": False,
            "message": f"Vault check failed: {e}",
        }


@router.delete("/delete")
async def delete_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user's credentials from Algorand vault and clear DB reference."""
    access_key = user.aws_access_key_id
    if not access_key:
        raise HTTPException(status_code=404, detail="No credentials to delete")

    try:
        from credential_vault import vault_delete

        vault_delete(access_key)

        user.aws_access_key_id = None
        user.aws_default_region = "ap-south-1"
        await db.commit()

        return {"status": "success", "message": "Credentials deleted from vault."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vault delete failed: {e}")


@router.get("/retrieve")
async def retrieve_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve decrypted credentials from Algorand vault.
    Returns masked secret for display, full creds are used internally by APIs.
    """
    access_key = user.aws_access_key_id
    if not access_key:
        raise HTTPException(status_code=404, detail="No credentials stored in vault")

    try:
        from credential_vault import vault_retrieve

        creds = vault_retrieve(access_key)
        secret = creds.get("AWS_SECRET_ACCESS_KEY", "")

        return {
            "status": "success",
            "credentials": {
                "AWS_ACCESS_KEY_ID": creds["AWS_ACCESS_KEY_ID"],
                "AWS_SECRET_ACCESS_KEY_HINT": f"****{secret[-4:]}" if len(secret) >= 4 else "****",
                "AWS_DEFAULT_REGION": creds.get("AWS_DEFAULT_REGION", "ap-south-1"),
            },
            "message": "Credentials retrieved from Algorand vault (secret masked).",
        }
    except KeyError:
        # Vault entry doesn't exist anymore — clean up DB
        user.aws_access_key_id = None
        await db.commit()
        raise HTTPException(status_code=404, detail="Credentials not found in vault")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vault retrieval failed: {e}")
