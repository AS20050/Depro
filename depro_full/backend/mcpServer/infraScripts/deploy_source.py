import paramiko
import boto3
import time
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

def find_project_root(start_path, language):
    """
    Traverses down to find the actual project root containing requirements.txt or package.json.
    This effectively "flattens" the folder structure for deployment.
    """
    marker = "requirements.txt" if language == "python" else "package.json"
    
    # 1. Check current dir
    if os.path.exists(os.path.join(start_path, marker)):
        return start_path
    
    # 2. Check immediate subdirectories (1 level deep)
    # This handles the common case where zipping a folder creates a root folder inside the zip
    for item in os.listdir(start_path):
        sub_path = os.path.join(start_path, item)
        if os.path.isdir(sub_path) and os.path.exists(os.path.join(sub_path, marker)):
            print(f"🔍 [SCRIPT] Flattening: Found real project root at: {item}/")
            return sub_path
            
    return start_path

def deploy_source_node_ex(source_path, language="python", entry_point="main.py"):
    """
    Deploys source code to EC2, auto-flattens directory structure, 
    installs runtime, and starts app using PM2 on port 8080.
    """
    REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    KEY_NAME = os.getenv("KEY_NAME", "ubuntu-auto-keypair-v2")
    INSTANCE_NAME = "ubuntu-auto-ec2-v2"
    KEY_PATH = f"{KEY_NAME}.pem"

    if not source_path:
        raise ValueError("❌ source_path is None! (Did you fix app.py?)")

    print(f"\n🚀 [SCRIPT] Starting {language.upper()} Deployment...")

    # ---------------- 1. SMART ZIP (FLATTEN STRUCTURE) ----------------
    real_source_path = find_project_root(source_path, language)
    
    zip_base = "deploy_package"
    shutil.make_archive(zip_base, 'zip', real_source_path)
    local_zip = f"{zip_base}.zip"
    print(f"📦 [SCRIPT] Zipped source from: {real_source_path}")

    # ---------------- 2. FIND INSTANCE ----------------
    ec2 = boto3.client("ec2", region_name=REGION)
    res = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [INSTANCE_NAME]},
        {"Name": "instance-state-name", "Values": ["running"]}
    ])
    if not res["Reservations"]:
        raise Exception("❌ No running EC2 found. Did provision fail?")
    
    public_ip = res["Reservations"][0]["Instances"][0]["PublicIpAddress"]
    print(f"🔗 [SCRIPT] Target IP: {public_ip}")

    # ---------------- 3. ROBUST SSH CONNECTION ----------------
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print("⏳ [SCRIPT] Establishing SSH Connection...")
    ssh_ready = False
    
    for i in range(30):
        try:
            ssh.connect(
                public_ip, 
                username="ubuntu", 
                key_filename=KEY_PATH, 
                timeout=10, 
                banner_timeout=30
            )
            ssh_ready = True
            print("✅ [SCRIPT] TCP/SSH Handshake Complete")
            break
        except Exception as e:
            print(f"   Waiting for SSH ({i+1}/30)...")
            time.sleep(10)
    
    if not ssh_ready:
        raise Exception("❌ SSH Connection Timed Out")

    print("⏳ [SCRIPT] Stabilizing SFTP Subsystem...")
    time.sleep(5)
    
    sftp = None
    for attempt in range(5):
        try:
            sftp = ssh.open_sftp()
            print("✅ [SCRIPT] SFTP Channel Open")
            break
        except Exception as e:
            print(f"⚠️ SFTP Open Failed ({attempt+1}/5): {e}")
            time.sleep(5)
    
    if not sftp:
        raise Exception("❌ Failed to open SFTP session")

    # ---------------- 4. UPLOAD ----------------
    remote_dir = "/home/ubuntu/app_source"
    remote_zip = "/home/ubuntu/pkg.zip"
    
    print(f"📤 [SCRIPT] Uploading code...")
    sftp.put(local_zip, remote_zip)
    sftp.close()

    # ---------------- 5. PREPARE COMMANDS ----------------
    setup_cmds = [
        "sudo apt update -y",
        "sudo apt install -y unzip",
        # Install Node/PM2 globally
        "curl -sL https://deb.nodesource.com/setup_18.x | sudo -E bash -",
        "sudo apt install -y nodejs",
        "sudo npm install -g pm2",
        # Clean and Unzip
        f"rm -rf {remote_dir} && mkdir -p {remote_dir}",
        f"unzip -o {remote_zip} -d {remote_dir}",
        f"ls -la {remote_dir}" 
    ]

    run_cmds = []

    # --- PYTHON LOGIC ---
    if language == "python":
        print("🐍 [SCRIPT] Configuring Python Environment...")
        setup_cmds.extend([
            "sudo apt install -y python3-pip python3-venv",
        ])
        
        # Smart Module Detection
        filename = os.path.basename(entry_point) # "main.py"
        module_name = filename.replace(".py", "") # "main"
        
        run_cmds = [
            f"cd {remote_dir} && python3 -m venv venv",
            f"cd {remote_dir} && ./venv/bin/pip install -r requirements.txt",
            f"pm2 delete backend || true",
            # Assuming 'main:app' structure inside the flattened root
            f"cd {remote_dir} && pm2 start \"./venv/bin/python3 -m uvicorn {module_name}:app --host 0.0.0.0 --port 8080\" --name backend"
        ]

    # --- NODE.JS LOGIC ---
    elif language == "node":
        print("🟩 [SCRIPT] Configuring Node.js Environment...")
        start_cmd = entry_point
        if "npm" not in start_cmd and not start_cmd.startswith("node"):
             start_cmd = f"pm2 start {os.path.basename(start_cmd)} --name backend"
        
        run_cmds = [
            f"cd {remote_dir} && npm install",
            f"pm2 delete backend || true",
            f"cd {remote_dir} && PORT=8080 {start_cmd}"
        ]

    # ---------------- 6. EXECUTE COMMANDS ----------------
    all_cmds = setup_cmds + run_cmds
    
    print("▶ [SCRIPT] Executing Remote Commands...")
    for cmd in all_cmds:
        print(f"   EXEC: {cmd[:60]}...")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err_log = stderr.read().decode().strip()
            if "pm2 delete" in cmd or "already exists" in err_log:
                continue
            print(f"   ⚠️ CMD Warning/Error (Code {exit_status}): {err_log}")

    # 7. SAVE PM2 LIST
    ssh.exec_command("pm2 save")
    ssh.close()
    
    if os.path.exists(local_zip):
        os.remove(local_zip)

    return {
        "public_ip": public_ip,
        "endpoint": f"http://{public_ip}:8080",
        "message": f"Deployed {language} app using PM2."
    }