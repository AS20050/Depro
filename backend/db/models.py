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

    # AWS vault reference — stores only the access key ID (lookup key for Algorand vault)
    # The actual secret is encrypted and stored in Algorand box storage, never in this DB
    aws_access_key_id = Column(String(50), nullable=True)
    aws_default_region = Column(String(30), default="ap-south-1")

    # Billing alert tracking — prevents duplicate emails
    billing_alerted_total = Column(Float, default=0.0)
    billing_alert_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    deployments = relationship("Deployment", back_populates="user", cascade="all, delete-orphan")
    aws_accounts = relationship("AWSAccount", back_populates="user", cascade="all, delete-orphan")
    billing_thresholds = relationship("BillingThreshold", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Source info
    source_type = Column(String(20), nullable=True)
    source_filename = Column(String(255), nullable=True)
    repo_url = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)

    # Deployment info
    project_type = Column(String(50), nullable=True)
    deployment_type = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")
    endpoint = Column(Text, nullable=True)
    app_id = Column(String(100), nullable=True)

    # AWS service used
    aws_service = Column(String(50), nullable=True)
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
    account_label = Column(String(100), nullable=True)
    access_key_hint = Column(String(10), nullable=True)
    region = Column(String(30), default="ap-south-1")
    monthly_bill = Column(Float, default=0.0)
    services_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="aws_accounts")

    def __repr__(self):
        return f"<AWSAccount {self.account_label}>"


class BillingThreshold(Base):
    __tablename__ = "billing_thresholds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    service_name = Column(String(200), nullable=False)   # "TOTAL", "Amazon EC2", etc.
    limit_value = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="billing_thresholds")

    def __repr__(self):
        return f"<BillingThreshold {self.service_name}={self.limit_value}>"
