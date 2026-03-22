# mcpServer/tools/algorand_deploy.py

from __future__ import annotations

import traceback
from typing import Any

from mcpServer.infraScripts.algorand_deploy import deploy_algorand_dapp


def deploy_algorand_dapp_tool(project_path: str, app_name: str = "depro-dapp") -> dict[str, Any]:
    """MCP tool wrapper: deploy Algorand smart contract + optional frontend."""
    print(f"[TOOL] deploy_algorand_dapp: {project_path}")
    try:
        return deploy_algorand_dapp(project_path, app_name)
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}
