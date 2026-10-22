"""v0.8 durable persistence model; tenant isolation enforced at database level."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass

class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (UniqueConstraint("tenant_id", "run_id"), {"schema":"agent_runtime"})
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trace_id: Mapped[str|None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class AgentCheckpointMetadata(Base):
    __tablename__ = "checkpoint_metadata"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "run_id"], ["agent_runtime.agent_runs.tenant_id", "agent_runtime.agent_runs.run_id"]), {"schema":"agent_runtime"})
    checkpoint_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class IntegrationReference(Base):
    __tablename__ = "external_references"
    __table_args__ = (UniqueConstraint("tenant_id", "source_system", "external_id"), {"schema":"integration"})
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)

class TraceLink(Base):
    __tablename__ = "trace_links"
    __table_args__ = ({"schema":"observability"},)
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    backend: Mapped[str] = mapped_column(String(32), nullable=False)
