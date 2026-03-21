from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct

from db.database import get_db
from db.models import User, Deployment, AWSAccount
from db.schemas import DashboardStats, DeploymentResponse
from auth.jwt_handler import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardStats)
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard overview stats for the authenticated user."""

    user_id = user.id

    # Total deployments
    total_q = await db.execute(
        select(func.count(Deployment.id)).where(Deployment.user_id == user_id)
    )
    total_deployments = total_q.scalar() or 0

    # Active (running/success) deployments
    active_q = await db.execute(
        select(func.count(Deployment.id)).where(
            Deployment.user_id == user_id,
            Deployment.status.in_(["running", "success"])
        )
    )
    active_deployments = active_q.scalar() or 0

    # Failed deployments
    failed_q = await db.execute(
        select(func.count(Deployment.id)).where(
            Deployment.user_id == user_id,
            Deployment.status == "failed"
        )
    )
    failed_deployments = failed_q.scalar() or 0

    # AWS accounts
    aws_q = await db.execute(
        select(func.count(AWSAccount.id)).where(AWSAccount.user_id == user_id)
    )
    aws_accounts = aws_q.scalar() or 0

    # Total AWS bill
    bill_q = await db.execute(
        select(func.coalesce(func.sum(AWSAccount.monthly_bill), 0.0)).where(
            AWSAccount.user_id == user_id
        )
    )
    total_aws_bill = float(bill_q.scalar() or 0.0)

    # Distinct AWS services used
    services_q = await db.execute(
        select(distinct(Deployment.aws_service)).where(
            Deployment.user_id == user_id,
            Deployment.aws_service.isnot(None)
        )
    )
    services_used = [row[0] for row in services_q.all()]

    # Recent 5 deployments
    recent_q = await db.execute(
        select(Deployment)
        .where(Deployment.user_id == user_id)
        .order_by(Deployment.created_at.desc())
        .limit(5)
    )
    recent = recent_q.scalars().all()

    recent_deployments = [
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
        for d in recent
    ]

    return DashboardStats(
        total_deployments=total_deployments,
        active_deployments=active_deployments,
        failed_deployments=failed_deployments,
        aws_accounts=aws_accounts,
        total_aws_bill=total_aws_bill,
        services_used=services_used,
        recent_deployments=recent_deployments
    )
