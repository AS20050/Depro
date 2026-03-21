from mcpServer.infraScripts.provision_ec2 import provision_ec2_node_ex

def provision_ec2_instance():
    """
    MCP Tool:
    Provisions an Ubuntu EC2 instance suitable for backend workloads.
    """
    provision_ec2_node_ex()

    return {
        "status": "success",
        "resource": "ec2",
        "message": "EC2 instance provisioned successfully"
    }