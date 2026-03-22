# mcpServer/tools/algorand_credentials.py

from __future__ import annotations

import traceback
from typing import Any

from mcpServer.infraScripts.algorand_credential_store import (
    delete_aws_credentials,
    has_credentials,
    retrieve_aws_credentials,
    store_aws_credentials,
)


def vault_store_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    print("[TOOL] vault_store_credentials")
    try:
        return store_aws_credentials(creds)
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}


def vault_retrieve_credentials(access_key_id: str) -> dict[str, Any]:
    safe_prefix = (access_key_id or "")[:8] + "****"
    print(f"[TOOL] vault_retrieve_credentials: {safe_prefix}")
    try:
        creds = retrieve_aws_credentials(access_key_id)
        return {"status": "success", "credentials": creds}
    except KeyError as exc:
        return {"status": "not_found", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}


def vault_delete_credentials(access_key_id: str) -> dict[str, Any]:
    safe_prefix = (access_key_id or "")[:8] + "****"
    print(f"[TOOL] vault_delete_credentials: {safe_prefix}")
    try:
        return delete_aws_credentials(access_key_id)
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}


def vault_check_credentials(access_key_id: str) -> dict[str, Any]:
    safe_prefix = (access_key_id or "")[:8] + "****"
    print(f"[TOOL] vault_check_credentials: {safe_prefix}")
    try:
        exists = has_credentials(access_key_id)
        return {
            "status": "success",
            "exists": exists,
            "message": "Credentials found in vault." if exists else "No credentials stored.",
        }
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}

