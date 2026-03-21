import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=True)
    avatar_url = Column(Text, nullable=True)
    github_id = Column(String(100), unique=True, nullable=True, index=True)
    github_token = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    deployments = relationship("Deployment", back_populates="user", cascade="all, delete-orphan")
    aws_accounts = relationship("AWSAccount", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Source info
    source_type = Column(String(20), nullable=True)       # "zip", "jar", "github"
    source_filename = Column(String(255), nullable=True)   # original filename for zip/jar
    repo_url = Column(Text, nullable=True)                 # github URL
    file_path = Column(Text, nullable=True)                # local path to stored zip/jar

    # Deployment info
    project_type = Column(String(50), nullable=True)       # frontend, backend, fullstack
    deployment_type = Column(String(50), nullable=True)    # amplify_cicd, amplify_snapshot, ec2
    status = Column(String(20), default="pending")         # pending, running, success, failed, stopped
    endpoint = Column(Text, nullable=True)                 # live URL
    app_id = Column(String(100), nullable=True)            # AWS app ID

    # AWS service used
    aws_service = Column(String(50), nullable=True)        # amplify, ec2, s3
    aws_region = Column(String(30), default="ap-south-1")

    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="deployments")

    def __repr__(self):
        return f"<Deployment {self.id} - {self.status}>"


class AWSAccount(Base):
    __tablename__ = "aws_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_label = Column(String(100), nullable=True)     # "My AWS Account"
    access_key_hint = Column(String(10), nullable=True)    # Last 4 chars of access key
    region = Column(String(30), default="ap-south-1")
    monthly_bill = Column(Float, default=0.0)
    services_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="aws_accounts")

    def __repr__(self):
        return f"<AWSAccount {self.account_label}>"
