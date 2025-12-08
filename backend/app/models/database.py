"""
Database Models for EDoS Security Dashboard
Professional SQLAlchemy models with proper relationships
"""

import uuid
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    Text,
    DECIMAL,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# Database-agnostic UUID type
class UUID(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36).
    """

    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid=False):
        self.as_uuid = as_uuid
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value) if not self.as_uuid else value
        else:
            if not isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if self.as_uuid and not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            elif not self.as_uuid:
                return str(value)
            return value


# Database-agnostic IP address type
class IPAddress(TypeDecorator):
    """Platform-independent IP address type.
    Uses PostgreSQL's INET type, otherwise uses VARCHAR(45).
    """

    impl = String(45)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import INET

            return dialect.type_descriptor(INET())
        else:
            return dialect.type_descriptor(String(45))


Base = declarative_base()

# =============================================
# USER MANAGEMENT MODELS
# =============================================


class UserProfile(Base):
    __tablename__ = "user_profiles"

    # Primary identification - matches Supabase auth.users.id
    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=True, index=True)

    # Profile information
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    role = Column(String(50), default="analyst")
    department = Column(String(100))

    # Account status
    is_active = Column(Boolean, default=True, index=True)
    email_verified = Column(Boolean, default=False)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(32))

    # Security tracking
    last_login = Column(DateTime(timezone=True))
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True), default=func.now())

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
    deleted_at = Column(DateTime(timezone=True))  # Soft delete

    # Relationships
    resources = relationship(
        "UserResource",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[UserResource.user_id]",
    )
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    alerts = relationship(
        "SecurityAlert",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[SecurityAlert.user_id]",
    )
    logs = relationship(
        "SystemLog",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[SystemLog.user_id]",
    )
    metrics = relationship(
        "SystemMetric",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[SystemMetric.user_id]",
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(IPAddress())
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    user = relationship("UserProfile", back_populates="sessions")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Security settings
    session_timeout = Column(Integer, default=30)  # minutes
    auto_logout = Column(Boolean, default=True)
    notification_email = Column(Boolean, default=True)
    notification_sms = Column(Boolean, default=False)

    # Dashboard preferences
    theme = Column(String(20), default="dark")
    timezone = Column(String(50), default="UTC")
    language = Column(String(10), default="en")
    refresh_interval = Column(Integer, default=30)  # seconds

    # Alert settings
    alert_threshold = Column(String(20), default="medium")
    alert_retention_days = Column(Integer, default=90)

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("UserProfile", back_populates="settings")


# =============================================
# CLOUD RESOURCES MODELS
# =============================================


class CloudProvider(Base):
    __tablename__ = "cloud_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)  # 'aws', 'azure', 'gcp'
    display_name = Column(String(100), nullable=False)
    api_endpoint = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    resource_types = relationship("ResourceType", back_populates="provider")


class ResourceType(Base):
    __tablename__ = "resource_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True), ForeignKey("cloud_providers.id"), nullable=False
    )
    name = Column(String(50), nullable=False)  # 'ec2', 'rds', 'vm'
    display_name = Column(String(100), nullable=False)
    icon = Column(String(50))
    category = Column(String(50))  # 'compute', 'storage', 'database'
    created_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    provider = relationship("CloudProvider", back_populates="resource_types")
    resources = relationship("UserResource", back_populates="resource_type")


class UserResource(Base):
    __tablename__ = "user_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type_id = Column(
        UUID(as_uuid=True), ForeignKey("resource_types.id"), nullable=False
    )

    # Resource identification
    resource_id = Column(String(255), nullable=False)  # External ID
    name = Column(String(255), nullable=False)
    sku = Column(String(100))

    # Location and configuration
    region = Column(String(50))
    availability_zone = Column(String(50))
    location = Column(JSON)  # {country, city, datacenter}

    # Resource specifications
    instance_type = Column(String(50))
    cpu_cores = Column(Integer)
    memory_gb = Column(DECIMAL(10, 2))
    storage_gb = Column(DECIMAL(10, 2))
    network_performance = Column(String(50))

    # Operating system
    os_type = Column(String(50))  # 'ubuntu', 'windows', 'centos'
    os_version = Column(String(50))
    kernel_version = Column(String(100))

    # Status and health
    status = Column(String(20), default="active", index=True)
    health_status = Column(String(20), default="healthy")
    last_health_check = Column(DateTime(timezone=True))

    # Cost tracking
    cost_per_hour = Column(DECIMAL(10, 4))
    monthly_cost_estimate = Column(DECIMAL(10, 2))

    # Network configuration
    private_ip = Column(IPAddress())
    public_ip = Column(IPAddress())
    vpc_id = Column(String(255))
    subnet_id = Column(String(255))
    security_groups = Column(JSON)  # Array of security group IDs

    # Metadata
    tags = Column(JSON, default={})
    resource_metadata = Column(JSON, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("UserProfile", back_populates="resources")
    resource_type = relationship("ResourceType", back_populates="resources")
    alerts = relationship("SecurityAlert", back_populates="resource")
    logs = relationship("SystemLog", back_populates="resource")
    metrics = relationship("SystemMetric", back_populates="resource")

    # Constraints
    __table_args__ = (UniqueConstraint("user_id", "resource_id", "resource_type_id"),)


# =============================================
# SECURITY ALERTS MODELS
# =============================================


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = Column(
        UUID(as_uuid=True), ForeignKey("user_resources.id", ondelete="CASCADE")
    )

    # Alert classification
    type = Column(String(50), nullable=False)  # 'malware', 'intrusion', 'ddos'
    category = Column(String(50), nullable=False)  # 'network', 'system', 'application'
    severity = Column(
        String(20), nullable=False, index=True
    )  # 'info', 'low', 'medium', 'high', 'critical'

    # Alert details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Source information
    source_ip = Column(IPAddress(), index=True)
    source_country = Column(String(2))
    source_city = Column(String(100))

    # Target information
    target_ip = Column(IPAddress())
    target_port = Column(Integer)
    target_service = Column(String(100))

    # Detection details
    detection_method = Column(String(100))
    confidence_score = Column(DECIMAL(5, 2))  # 0.00 to 100.00
    false_positive_probability = Column(DECIMAL(5, 2))

    # Attack details
    attack_vector = Column(String(100))
    payload_size = Column(Integer)
    attack_duration_seconds = Column(Integer)

    # Response and status
    status = Column(String(20), default="new", index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"))
    resolution_notes = Column(Text)

    # Metadata
    raw_data = Column(JSON)
    artifacts = Column(JSON)  # File hashes, URLs, etc.

    # Timestamps
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    user = relationship("UserProfile", back_populates="alerts", foreign_keys=[user_id])
    assigned_user = relationship("UserProfile", foreign_keys=[assigned_to])
    resource = relationship("UserResource", back_populates="alerts")

    # Constraints
    __table_args__ = (
        CheckConstraint(severity.in_(["info", "low", "medium", "high", "critical"])),
        CheckConstraint(
            status.in_(
                ["new", "investigating", "acknowledged", "resolved", "false_positive"]
            )
        ),
    )


# =============================================
# NETWORK TRAFFIC MODELS
# =============================================


class NetworkTraffic(Base):
    __tablename__ = "network_traffic"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = Column(
        UUID(as_uuid=True), ForeignKey("user_resources.id", ondelete="CASCADE")
    )

    # Traffic flow
    source_ip = Column(IPAddress(), nullable=False, index=True)
    source_port = Column(Integer)
    source_country = Column(String(2))
    source_city = Column(String(100))

    destination_ip = Column(IPAddress(), nullable=False)
    destination_port = Column(Integer)
    destination_country = Column(String(2))
    destination_city = Column(String(100))

    # Traffic details
    protocol = Column(String(10))  # 'TCP', 'UDP', 'ICMP'
    bytes_transferred = Column(Integer)
    packets_count = Column(Integer)
    duration_seconds = Column(DECIMAL(10, 3))

    # Threat classification
    is_malicious = Column(Boolean, default=False, index=True)
    threat_type = Column(String(50))
    threat_score = Column(DECIMAL(5, 2))  # 0.00 to 100.00

    # Detection
    detected_by = Column(String(100))
    blocked = Column(Boolean, default=False)

    # HTTP details
    user_agent = Column(Text)
    http_method = Column(String(10))
    url_path = Column(Text)

    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now())


# =============================================
# SYSTEM LOGS AND METRICS MODELS
# =============================================


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Log classification
    level = Column(
        String(20), nullable=False, index=True
    )  # 'debug', 'info', 'warn', 'error', 'critical'
    category = Column(String(50))  # 'system', 'application', 'security'
    source = Column(String(100), nullable=False)

    # Log content
    message = Column(Text, nullable=False)
    structured_data = Column(JSON)  # Parsed log fields

    # Context
    process_name = Column(String(255))
    process_id = Column(Integer)
    user_name = Column(String(100))

    # Timestamps
    log_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    user = relationship("UserProfile", back_populates="logs")
    resource = relationship("UserResource", back_populates="logs")


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_resources.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Resource utilization
    cpu_usage_percent = Column(DECIMAL(5, 2))
    memory_usage_percent = Column(DECIMAL(5, 2))
    memory_used_gb = Column(DECIMAL(10, 2))
    memory_total_gb = Column(DECIMAL(10, 2))

    # Storage metrics
    disk_usage_percent = Column(DECIMAL(5, 2))
    disk_used_gb = Column(DECIMAL(10, 2))
    disk_total_gb = Column(DECIMAL(10, 2))
    disk_iops = Column(Integer)

    # Network metrics
    network_in_mbps = Column(DECIMAL(10, 2))
    network_out_mbps = Column(DECIMAL(10, 2))
    network_packets_in = Column(Integer)
    network_packets_out = Column(Integer)

    # System metrics
    load_average = Column(DECIMAL(5, 2))
    processes_running = Column(Integer)
    processes_total = Column(Integer)
    uptime_seconds = Column(Integer)

    # Custom metrics
    custom_metrics = Column(JSON, default={})

    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    user = relationship("UserProfile", back_populates="metrics")
    resource = relationship("UserResource", back_populates="metrics")

    # Composite index for time-series queries
    __table_args__ = (
        Index("idx_metrics_user_resource_time", "user_id", "resource_id", "timestamp"),
    )


# =============================================
# PYDANTIC SCHEMAS FOR API
# =============================================


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class ResourceCreate(BaseModel):
    resource_id: str
    name: str
    resource_type_id: str
    region: Optional[str] = None
    instance_type: Optional[str] = None
    os_type: Optional[str] = None


class ResourceResponse(BaseModel):
    id: str
    name: str
    status: str
    health_status: str
    region: Optional[str]
    instance_type: Optional[str]
    os_type: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class AlertResponse(BaseModel):
    id: str
    type: str
    severity: str
    title: str
    description: str
    status: str
    source_ip: Optional[str]
    detected_at: datetime

    class Config:
        orm_mode = True
