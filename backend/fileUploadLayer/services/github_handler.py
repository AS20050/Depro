import uuid
from pathlib import Path
from git import Repo

BASE_GITHUB_DIR = Path("storage/extracted")
BASE_GITHUB_DIR.mkdir(parents=True, exist_ok=True)

def clone_github_repo(repo_url: str, github_token: str | None = None) -> str:
    repo_id = str(uuid.uuid4())
    repo_path = BASE_GITHUB_DIR / repo_id

    if github_token:
        # Inject token for private repo access
        repo_url = repo_url.replace(
            "https://",
            f"https://{github_token}@"
        )

    Repo.clone_from(repo_url, repo_path)
    return str(repo_path)
