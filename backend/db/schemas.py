from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== AUTH ====================

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    username: str = Field(..., min_length=3, max_length=50)
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    github_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==================== DEPLOYMENTS ====================

class DeploymentResponse(BaseModel):
    id: str
    source_type: Optional[str] = None
    source_filename: Optional[str] = None
    repo_url: Optional[str] = None
    file_path: Optional[str] = None
    project_type: Optional[str] = None
    deployment_type: Optional[str] = None
    status: str
    endpoint: Optional[str] = None
    app_id: Optional[str] = None
    aws_service: Optional[str] = None
    aws_region: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeploymentListResponse(BaseModel):
    total: int
    deployments: List[DeploymentResponse]


# ==================== AWS ACCOUNT ====================

class AWSAccountResponse(BaseModel):
    id: str
    account_label: Optional[str] = None
    access_key_hint: Optional[str] = None
    region: Optional[str] = None
    monthly_bill: float = 0.0
    services_used: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class AWSAccountCreate(BaseModel):
    account_label: Optional[str] = "My AWS Account"
    access_key_id: str
    secret_access_key: str
    region: str = "ap-south-1"


# ==================== DASHBOARD ====================

class DashboardStats(BaseModel):
    total_deployments: int
    active_deployments: int
    failed_deployments: int
    aws_accounts: int
    total_aws_bill: float
    services_used: List[str]
    recent_deployments: List[DeploymentResponse]
