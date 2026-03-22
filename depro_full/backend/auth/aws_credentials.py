import getpass
import os

def ask_aws_credentials():
    """
    Terminal-based AWS credential intake.
    Later replace with frontend form or AssumeRole.
    """

    print("\n🔐 ENTER AWS IAM CREDENTIALS\n")

    access_key = input("AWS_ACCESS_KEY_ID: ").strip()
    secret_key = getpass.getpass("AWS_SECRET_ACCESS_KEY (hidden): ").strip()
    region = input("AWS_DEFAULT_REGION (e.g. ap-south-1): ").strip()

    if not access_key or not secret_key or not region:
        raise ValueError("All AWS credentials are required")

    return {
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
        "AWS_DEFAULT_REGION": region
    }

def inject_aws_creds(creds: dict):
    """
    Inject credentials into runtime environment (NOT stored).
    Existing boto3 code will work without modification.
    """
    os.environ["AWS_ACCESS_KEY_ID"] = creds["AWS_ACCESS_KEY_ID"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = creds["AWS_SECRET_ACCESS_KEY"]
    os.environ["AWS_DEFAULT_REGION"] = creds.get("AWS_DEFAULT_REGION", "ap-south-1")


def resolve_aws_credentials(
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    region: str = "ap-south-1",
    allow_terminal_prompt: bool = True,
) -> dict:
    """
    Credential resolution pipeline (priority order):
    1) Full credentials from frontend (both key + secret provided)
    2) Algorand vault lookup (access_key_id provided, secret missing)
    3) Environment variables (.env / OS env)
    4) Terminal prompt (last resort)
    """

    # 1) Full creds from frontend
    if access_key_id and secret_access_key:
        print("[AUTH] Using credentials provided by frontend.")
        creds = {
            "AWS_ACCESS_KEY_ID": access_key_id.strip(),
            "AWS_SECRET_ACCESS_KEY": secret_access_key.strip(),
            "AWS_DEFAULT_REGION": region or "ap-south-1",
        }
        inject_aws_creds(creds)
        return creds

    # 2) Vault lookup with Access Key ID only
    if access_key_id:
        safe_prefix = access_key_id[:8] + "****"
        print(f"[AUTH] Checking Algorand vault for: {safe_prefix}")
        try:
            from mcpServer.infraScripts.algorand_credential_store import has_credentials, retrieve_aws_credentials

            if has_credentials(access_key_id):
                print("[AUTH] Found vault entry. Retrieving and decrypting...")
                creds = retrieve_aws_credentials(access_key_id)
                inject_aws_creds(creds)
                return creds

            print("[AUTH] No vault entry found for this access key ID.")
        except EnvironmentError:
            print("[AUTH] Vault not configured (missing CREDENTIAL_VAULT_APP_ID). Skipping vault lookup.")
        except Exception as e:
            print(f"[AUTH] Vault lookup failed: {e}")

    # 3) Environment variables
    env_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    env_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    if env_key and env_secret:
        print("[AUTH] Using credentials from environment variables.")
        creds = {
            "AWS_ACCESS_KEY_ID": env_key,
            "AWS_SECRET_ACCESS_KEY": env_secret,
            "AWS_DEFAULT_REGION": (os.environ.get("AWS_DEFAULT_REGION", region) or "ap-south-1").strip()
            or "ap-south-1",
        }
        inject_aws_creds(creds)
        return creds

    # 3b) If only an access key is present in env, try vault lookup for it.
    # This enables zip/github flows where the server env holds only the Access Key ID.
    if env_key and not env_secret and not access_key_id:
        safe_prefix = env_key[:8] + "****"
        print(f"[AUTH] Env has Access Key ID only. Checking Algorand vault for: {safe_prefix}")
        try:
            from mcpServer.infraScripts.algorand_credential_store import has_credentials, retrieve_aws_credentials

            if has_credentials(env_key):
                print("[AUTH] Found vault entry. Retrieving and decrypting...")
                creds = retrieve_aws_credentials(env_key)
                inject_aws_creds(creds)
                return creds

            print("[AUTH] No vault entry found for this access key ID.")
        except EnvironmentError:
            print("[AUTH] Vault not configured (missing CREDENTIAL_VAULT_APP_ID). Skipping vault lookup.")
        except Exception as e:
            print(f"[AUTH] Vault lookup failed: {e}")

    # 4) Terminal prompt fallback
    if not allow_terminal_prompt:
        raise ValueError(
            "AWS credentials not available. Provide aws_access_key_id (vault) or set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY."
        )

    print("[AUTH] No credentials found. Falling back to terminal prompt.")
    creds = ask_aws_credentials()
    if "AWS_DEFAULT_REGION" not in creds or not creds["AWS_DEFAULT_REGION"]:
        creds["AWS_DEFAULT_REGION"] = region or "ap-south-1"
    inject_aws_creds(creds)
    return creds
