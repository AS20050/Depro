import os
from mcpServer.infraScripts.provision_ec2 import provision_ec2_node_ex

def provision_ec2_instance():
    """
    MCP Tool:
    Provisions an Ubuntu EC2 instance suitable for backend workloads.
    """
    result = provision_ec2_node_ex()

    # Persist key deployment facts for downstream tools/scripts.
    if isinstance(result, dict):
        if result.get("public_ip"):
            os.environ["EC2_PUBLIC_IP"] = str(result["public_ip"])
        if result.get("instance_id"):
            os.environ["EC2_INSTANCE_ID"] = str(result["instance_id"])
        if result.get("key_path"):
            os.environ["EC2_KEY_PATH"] = str(result["key_path"])

        result.setdefault("resource", "ec2")
        result.setdefault("message", "EC2 instance provisioned successfully")
        return result

    return {"status": "error", "message": "EC2 provisioning did not return a result."}
