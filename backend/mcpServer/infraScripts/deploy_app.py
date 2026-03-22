import os


def deploy_app_node_ex():
    import paramiko
    import boto3
    import time
    import os
    from dotenv import load_dotenv

    # ---------------- LOAD ENV ----------------
    load_dotenv()

    REGION = os.getenv("AWS_DEFAULT_REGION")
    KEY_NAME = os.getenv("KEY_NAME")
    APP_FILE = os.getenv("APP_FILE")
    APP_PORT = int(os.getenv("APP_PORT")) # pyright: ignore[reportArgumentType]

    INSTANCE_NAME = "ubuntu-auto-ec2-v2"
    KEY_PATH = f"{KEY_NAME}.pem"

    # ---------------- VALIDATION ----------------
    LOCAL_JAR_PATH = os.path.abspath(APP_FILE) # pyright: ignore[reportArgumentType, reportCallIssue]

    if not os.path.exists(LOCAL_JAR_PATH):
        raise FileNotFoundError(
            f"❌ JAR NOT FOUND locally:\n{LOCAL_JAR_PATH}\n"
            f"➡ Put the jar in the SAME folder as deploy_app.py"
        )

    print(f"📦 Local JAR found: {LOCAL_JAR_PATH}")

    # ---------------- AWS CLIENT ----------------
    ec2 = boto3.client(
        "ec2",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=REGION
    )

    # ---------------- FIND INSTANCE ----------------
    def get_instance():
        res = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": [INSTANCE_NAME]},
                {"Name": "instance-state-name", "Values": ["running"]}
            ]
        )
        if not res["Reservations"]:
            raise Exception("❌ No running EC2 found")
        return res["Reservations"][0]["Instances"][0]

    instance = get_instance()
    public_ip = instance["PublicIpAddress"]

    print(f"🔗 Connecting to {public_ip}")

    # ---------------- SSH CONNECT ----------------
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for attempt in range(20):
        try:
            print(f"⏳ SSH attempt {attempt+1}/20")
            ssh.connect(
                hostname=public_ip,
                username="ubuntu",
                key_filename=KEY_PATH,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10
            )
            print("✅ SSH connected")
            break
        except Exception as e:
            print("SSH not ready:", e)
            time.sleep(5)
    else:
        raise Exception("❌ SSH not reachable")

    # ---------------- UPLOAD APP ----------------
    remote_path = f"/home/ubuntu/{APP_FILE}"

    print(f"📤 Uploading JAR to {remote_path}")

    sftp = ssh.open_sftp()
    sftp.put(LOCAL_JAR_PATH, remote_path)
    sftp.close()

    print("✅ Upload complete")

    # ---------------- VERIFY UPLOAD ----------------
    verify_cmd = f"ls -lh {remote_path}"
    stdin, stdout, stderr = ssh.exec_command(verify_cmd)
    print(stdout.read().decode())
    print(stderr.read().decode())

    # ---------------- RUN APP ----------------
    commands = [
        "sudo apt update -y",
        "sudo apt install -y openjdk-17-jre",
        "java -version",
        "pkill -f 'mcp-calendar-.*.jar' || true",
        f"nohup java -jar {remote_path} > /home/ubuntu/app.log 2>&1 &",
        "sleep 8",
        "ss -tulnp | grep :8080 || echo '❌ Port 8080 not listening'",
        "tail -n 40 /home/ubuntu/app.log || true"
    ]

    for cmd in commands:
        print(f"\n▶ {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())

    ssh.close()

    print("\n✅ DEPLOY SCRIPT FINISHED")
    print(f"🌍 Endpoint: http://{public_ip}:{APP_PORT}")