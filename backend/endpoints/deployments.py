from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pathlib import Path

from db.database import get_db
from db.models import User, Deployment
from db.schemas import DeploymentResponse, DeploymentListResponse
from auth.jwt_handler import get_current_user

router = APIRouter(prefix="/api/deployments", tags=["Deployments"])


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all deployments for the authenticated user, with optional status filter."""

    query = select(Deployment).where(Deployment.user_id == user.id)

    if status:
        query = query.where(Deployment.status == status)

    query = query.order_by(Deployment.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    deployments = result.scalars().all()

    # Total count
    count_q = select(func.count(Deployment.id)).where(Deployment.user_id == user.id)
    if status:
        count_q = count_q.where(Deployment.status == status)
    total = (await db.execute(count_q)).scalar() or 0

    return DeploymentListResponse(
        total=total,
        deployments=[
            DeploymentResponse(
                id=str(d.id),
                source_type=d.source_type,
                source_filename=d.source_filename,
                repo_url=d.repo_url,
                file_path=d.file_path,
                project_type=d.project_type,
                deployment_type=d.deployment_type,
                status=d.status,
                endpoint=d.endpoint,
                app_id=d.app_id,
                aws_service=d.aws_service,
                aws_region=d.aws_region,
                error_message=d.error_message,
                created_at=d.created_at,
                updated_at=d.updated_at
            )
            for d in deployments
        ]
    )


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single deployment by ID."""

    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.user_id == user.id
        )
    )
    d = result.scalar_one_or_none()

    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return DeploymentResponse(
        id=str(d.id),
        source_type=d.source_type,
        source_filename=d.source_filename,
        repo_url=d.repo_url,
        file_path=d.file_path,
        project_type=d.project_type,
        deployment_type=d.deployment_type,
        status=d.status,
        endpoint=d.endpoint,
        app_id=d.app_id,
        aws_service=d.aws_service,
        aws_region=d.aws_region,
        error_message=d.error_message,
        created_at=d.created_at,
        updated_at=d.updated_at
    )


@router.get("/{deployment_id}/download")
async def download_source(
    deployment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download the source archive (zip/jar) for a deployment."""

    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.user_id == user.id
        )
    )
    d = result.scalar_one_or_none()

    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if d.source_type == "github":
        raise HTTPException(
            status_code=400,
            detail="GitHub deployments have no downloadable file. Use the repo URL instead."
        )

    if not d.file_path:
        raise HTTPException(status_code=404, detail="Source file not available")

    file_path = Path(d.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Source file no longer exists on disk")

    return FileResponse(
        path=str(file_path),
        filename=d.source_filename or file_path.name,
        media_type="application/octet-stream"
    )


@router.patch("/{deployment_id}/status")
async def update_deployment_status(
    deployment_id: str,
    new_status: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually update a deployment's status (running, stopped, etc.)."""

    valid_statuses = ["pending", "running", "success", "failed", "stopped"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.user_id == user.id
        )
    )
    d = result.scalar_one_or_none()

    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")

    d.status = new_status
    await db.commit()

    return {"status": "updated", "deployment_id": str(d.id), "new_status": new_status}
