import zipfile
from pathlib import Path

def extract_zip(zip_path: Path, extract_to: Path):
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Invalid ZIP file")

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
