from mcpServer.tools.ec2_provision import provision_ec2_instance
from mcpServer.tools.java_deploy import deploy_java_app_ec2
from mcpServer.tools.source_deploy import deploy_source_ec2
from mcpServer.tools.amplify_deploy import deploy_amplify_node_ex
from mcpServer.tools.amplify_cicd_tools import connect_amplify_cicd
from mcpServer.tools.algorand_credentials import (
    vault_check_credentials,
    vault_delete_credentials,
    vault_retrieve_credentials,
    vault_store_credentials,
)
from mcpServer.tools.algorand_deploy import deploy_algorand_dapp_tool

TOOLS = {
    "provision_ec2_instance": provision_ec2_instance,
    "deploy_java_app_ec2": deploy_java_app_ec2,
    "deploy_source_ec2": deploy_source_ec2,
    "deploy_to_amplify": deploy_amplify_node_ex,
    "connect_amplify_cicd": connect_amplify_cicd,
    "vault_store_credentials": vault_store_credentials,
    "vault_retrieve_credentials": vault_retrieve_credentials,
    "vault_delete_credentials": vault_delete_credentials,
    "vault_check_credentials": vault_check_credentials,
    "deploy_algorand_dapp": deploy_algorand_dapp_tool,
}

def call_tool(tool_name: str, args: dict):
    if tool_name not in TOOLS:
        raise ValueError("Unknown MCP tool")

    return TOOLS[tool_name](**args)
