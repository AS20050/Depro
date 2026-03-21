from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import User, AWSAccount
from db.schemas import AWSAccountResponse, AWSAccountCreate
from auth.jwt_handler import get_current_user

router = APIRouter(prefix="/api/aws-accounts", tags=["AWS Accounts"])


@router.get("", response_model=list[AWSAccountResponse])
async def list_aws_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all AWS accounts for the authenticated user."""

    result = await db.execute(
        select(AWSAccount)
        .where(AWSAccount.user_id == user.id)
        .order_by(AWSAccount.created_at.desc())
    )
    accounts = result.scalars().all()

    return [
        AWSAccountResponse(
            id=str(a.id),
            account_label=a.account_label,
            access_key_hint=a.access_key_hint,
            region=a.region,
            monthly_bill=a.monthly_bill,
            services_used=a.services_used,
            created_at=a.created_at
        )
        for a in accounts
    ]


@router.post("", response_model=AWSAccountResponse)
async def add_aws_account(
    data: AWSAccountCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register an AWS account. Only stores a hint of the access key for display."""

    # Store only last 4 chars of access key as hint
    hint = data.access_key_id[-4:] if len(data.access_key_id) >= 4 else data.access_key_id

    account = AWSAccount(
        user_id=user.id,
        account_label=data.account_label,
        access_key_hint=f"****{hint}",
        region=data.region,
        monthly_bill=0.0,
        services_used=0
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    return AWSAccountResponse(
        id=str(account.id),
        account_label=account.account_label,
        access_key_hint=account.access_key_hint,
        region=account.region,
        monthly_bill=account.monthly_bill,
        services_used=account.services_used,
        created_at=account.created_at
    )


@router.delete("/{account_id}")
async def delete_aws_account(
    account_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove an AWS account."""

    result = await db.execute(
        select(AWSAccount).where(
            AWSAccount.id == account_id,
            AWSAccount.user_id == user.id
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="AWS account not found")

    await db.delete(account)
    await db.commit()

    return {"status": "deleted", "account_id": account_id}
