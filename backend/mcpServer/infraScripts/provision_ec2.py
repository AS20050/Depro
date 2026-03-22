import boto3
import time
import os
import platform
import subprocess
import stat
from dotenv import load_dotenv

load_dotenv()

def provision_ec2_node_ex():
    """
    Provisions an EC2 instance.
    CRITICAL: Aggressively cleans up old local key files to prevent PermissionErrors.
    """
    REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    KEY_NAME = os.getenv("KEY_NAME", "ubuntu-auto-keypair-v2")
    SG_NAME = "ubuntu-auto-sg-v2"
    
    # Ubuntu 24.04 LTS (ap-south-1)
    AMI_ID = "ami-0ff91eb5c6fe7cc86" 

    ec2 = boto3.client("ec2", region_name=REGION)
    ec2_resource = boto3.resource("ec2", region_name=REGION)

    print(f"\n🚀 [SCRIPT] Provisioning EC2 Resource in {REGION}...")

    # ==========================================
    # 1. KEY PAIR (FORCE CLEANUP & RECREATE)
    # ==========================================
    print(f"🔑 [SCRIPT] Managing Key Pair: {KEY_NAME}")
    
    pem_file = f"{KEY_NAME}.pem"

    # --- CRITICAL FIX: Aggressive Windows Unlock ---
    if os.path.exists(pem_file):
        print(f"   ♻️  Found old local key: {pem_file}")
        try:
            # 1. Windows-specific: Force reset permissions so we can delete it
            if platform.system() == "Windows":
                # Reset ACLs to default (removes the strict read-only we set previously)
                subprocess.run(f"icacls {pem_file} /reset", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Grant full control to current user just in case
                subprocess.run(f"icacls {pem_file} /grant:r \"{os.environ.get('USERNAME')}:F\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. Standard Python chmod (for Read-Only attribute)
            os.chmod(pem_file, stat.S_IWRITE)
            
            # 3. Delete
            os.remove(pem_file)
            print("   🗑️  Deleted old local key file.")
        except Exception as e:
            print(f"   ⚠️  Warning: Could not delete local key. You might need to manually delete '{pem_file}': {e}")

    # --- Delete from AWS ---
    try:
        ec2.delete_key_pair(KeyName=KEY_NAME)
        print("   ☁️  Deleted old key pair from AWS Console.")
    except Exception:
        pass

    # --- Create New ---
    key_pair = ec2.create_key_pair(KeyName=KEY_NAME)

    # --- Save New ---
    with open(pem_file, "w") as f:
        f.write(key_pair["KeyMaterial"])
    print(f"   ⬇️  Downloaded fresh private key to: {os.path.abspath(pem_file)}")

    # --- Secure Permissions (Re-apply security) ---
    if platform.system() == "Windows":
        # Remove inheritance, grant current user read access
        subprocess.run(f"icacls {pem_file} /reset", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(f"icacls {pem_file} /inheritance:r", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(f"icacls {pem_file} /grant:r \"{os.environ.get('USERNAME')}:R\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.chmod(pem_file, 0o400)
    print("   🔒  Key permissions secured.")

    # ==========================================
    # 2. SECURITY GROUP
    # ==========================================
    try:
        ec2.create_security_group(GroupName=SG_NAME, Description="Opsonic Auto SG")
        print(f"🛡️  Created Security Group: {SG_NAME}")
        # Allow SSH (22) and Web (80, 8080)
        ec2.authorize_security_group_ingress(
            GroupName=SG_NAME,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
    except Exception as e:
        if "InvalidGroup.Duplicate" in str(e):
            print(f"🛡️  Security Group {SG_NAME} exists (Reusing)")
        else:
            print(f"⚠️  SG Error: {e}")

    # ==========================================
    # 3. LAUNCH INSTANCE
    # ==========================================
    print("🚀 [SCRIPT] Launching EC2 Instance...")
    instances = ec2_resource.create_instances( # pyright: ignore[reportAttributeAccessIssue]
        ImageId=AMI_ID,
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        KeyName=KEY_NAME,
        SecurityGroups=[SG_NAME],
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'ubuntu-auto-ec2-v2'}]
        }]
    )
    
    instance = instances[0]
    print(f"   🆕 Instance ID: {instance.id}")
    print("   ⏳ Waiting for 'Running' state...")
    
    instance.wait_until_running()
    instance.reload()
    
    print(f"✅ [SCRIPT] Instance Ready. Public IP: {instance.public_ip_address}")
    
    return {
        "status": "success",
        "instance_id": instance.id,
        "public_ip": instance.public_ip_address,
        "key_path": os.path.abspath(pem_file)
    }