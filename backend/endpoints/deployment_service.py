"""
Service to record deployments in the database.
Called from app.py after a successful/failed deployment.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Deployment
from db.database import async_session


async def record_deployment(
    user_id: str,
    source_type: str,           # "zip", "jar", "github"
    source_filename: str = None,
    repo_url: str = None,
    file_path: str = None,
    project_type: str = None,
    deployment_type: str = None,
    status: str = "pending",
    endpoint: str = None,
    app_id: str = None,
    aws_service: str = None,
    aws_region: str = "ap-south-1",
    error_message: str = None
) -> Deployment:
    """Insert a deployment record into the database."""
    async with async_session() as db:
        deployment = Deployment(
            user_id=user_id,
            source_type=source_type,
            source_filename=source_filename,
            repo_url=repo_url,
            file_path=file_path,
            project_type=project_type,
            deployment_type=deployment_type,
            status=status,
            endpoint=endpoint,
            app_id=app_id,
            aws_service=aws_service,
            aws_region=aws_region,
            error_message=error_message
        )
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)
        print(f"📝 [DB] Deployment recorded: {deployment.id} ({status})")
        return deployment
