from __future__ import annotations

import os
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DEMO_DIR = ROOT / "demo_dapp"
ZIP_PATH = ROOT / "demo_dapp.zip"


def make_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in DEMO_DIR.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(DEMO_DIR))


def main() -> None:
    make_zip()
    api_url = os.getenv("OPSONIC_API_URL", "http://localhost:8000")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_default_region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

    with open(ZIP_PATH, "rb") as f:
        files = {"file": ("demo_dapp.zip", f, "application/zip")}
        data = {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_default_region": aws_default_region,
            "app_name": "opsonic-demo-dapp",
        }
        response = requests.post(f"{api_url}/upload", files=files, data=data, timeout=300)

    print("Status:", response.status_code)
    print(response.json())


if __name__ == "__main__":
    main()
