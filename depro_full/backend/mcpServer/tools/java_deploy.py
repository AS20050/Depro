import os
from mcpServer.infraScripts.deploy_app import deploy_app_node_ex

def deploy_java_app_ec2(artifact_path: str = None): # pyright: ignore[reportArgumentType]
    """
    MCP Tool:
    Uploads and runs a Java JAR on the provisioned EC2 instance.
    Accepts specific artifact_path to deploy dynamically.
    """
    
    # DYNAMIC INJECTION:
    # If a specific file was uploaded, override the .env APP_FILE variable
    # so the underlying script deploys THIS file, not the hardcoded one.
    if artifact_path:
        # infraScripts/deploy_app.py expects just the filename in some places
        # or absolute path in others. Let's ensure env var is correct.
        
        # Update OS Environment for the script to pick up
        os.environ["APP_FILE"] = artifact_path 
        
        # Verify it exists before calling script
        if not os.path.exists(artifact_path):
             return {"status": "error", "message": f"Artifact not found at {artifact_path}"}

    try:
        deploy_app_node_ex()

        # Discover the public IP reliably (don't depend on env being set correctly).
        public_ip = os.getenv("EC2_PUBLIC_IP", "")
        if not public_ip:
            import boto3

            region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
            instance_name = "ubuntu-auto-ec2-v2"

            ec2 = boto3.client(
                "ec2",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=region,
            )

            res = ec2.describe_instances(
                Filters=[
                    {"Name": "tag:Name", "Values": [instance_name]},
                    {"Name": "instance-state-name", "Values": ["running"]},
                ]
            )
            if not res.get("Reservations"):
                return {"status": "error", "message": "No running EC2 instance found after deployment."}

            instance = res["Reservations"][0]["Instances"][0]
            public_ip = instance.get("PublicIpAddress", "")
            if public_ip:
                os.environ["EC2_PUBLIC_IP"] = public_ip

        port = os.getenv("APP_PORT", "8080")
        endpoint = f"http://{public_ip}:{port}" if public_ip else None

        if not endpoint:
            return {"status": "error", "message": "Deployment finished but no public IP was available to build an endpoint."}

        return {
            "status": "success",
            "deployment": "java_ec2",
            "public_ip": public_ip,
            "endpoint": endpoint,
            "message": "Java application deployed and running",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
