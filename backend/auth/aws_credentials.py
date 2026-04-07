import getpass
import os
def ask_aws_credentials():
    """
    Terminal-based AWS credential intake.
    Later replace with frontend form or AssumeRole.
    """

    print("\nðŸ�?? ENTER AWS IAM CREDENTIALS\n")

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
    os.environ["AWS_DEFAULT_REGION"] = creds["AWS_DEFAULT_REGION"]
