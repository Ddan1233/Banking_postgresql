from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from app.banking_models import CustomerProfileModel
from app.banking_orchestrator import RiskReportResult


class Base(DeclarativeBase):
    """Base class for banking persistence tables."""


class CustomerProfileRecord(Base):
    """Latest validated ETL profile for each Excel customer."""

    __tablename__ = "customer_profiles"

    customer_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    profile_data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    source_name: Mapped[str] = mapped_column(String(100), default="Data.xlsx")
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskReportRecord(Base):
    """Immutable audit entry for one execution of the risk workflow."""

    __tablename__ = "risk_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customer_profiles.customer_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    report_data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    is_valid: Mapped[bool] = mapped_column(Boolean)
    refinement_count: Mapped[int] = mapped_column(Integer)
    observability_data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    total_duration_ms: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(100))


class BankingStorage:
    """Persist workflow inputs, outputs, and stage timings in PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._sessions = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._initialized = False

    def initialize(self) -> None:
        """Create tables on first use; migrations can replace this in production."""

        if not self._initialized:
            Base.metadata.create_all(self._engine)
            self._initialized = True

    def save_customer_profile(self, profile: CustomerProfileModel) -> None:
        self.initialize()
        customer_id = str(profile.customer_id)
        now = datetime.now(timezone.utc)
        with self._sessions.begin() as session:
            record = session.get(CustomerProfileRecord, customer_id)
            if record is None:
                session.add(
                    CustomerProfileRecord(
                        customer_id=customer_id,
                        profile_data=profile.model_dump(mode="json"),
                        loaded_at=now,
                    )
                )
            else:
                record.profile_data = profile.model_dump(mode="json")
                record.loaded_at = now

    def save_risk_report(
        self,
        profile: CustomerProfileModel,
        result: RiskReportResult,
        observability: dict[str, Any],
        model_name: str,
    ) -> str:
        self.initialize()
        report_id = str(uuid4())
        with self._sessions.begin() as session:
            session.add(
                RiskReportRecord(
                    id=report_id,
                    customer_id=str(profile.customer_id),
                    created_at=datetime.now(timezone.utc),
                    risk_level=result.report.risk_level,
                    report_data=result.model_dump(mode="json"),
                    is_valid=result.validation.is_valid,
                    refinement_count=result.refinement_count,
                    observability_data=observability,
                    total_duration_ms=float(observability["total_duration_ms"]),
                    model_name=model_name,
                )
            )
        return report_id

    def update_report_observability(
        self, report_id: str, observability: dict[str, Any]
    ) -> None:
        with self._sessions.begin() as session:
            record = session.get(RiskReportRecord, report_id)
            if record is not None:
                record.observability_data = observability
                record.total_duration_ms = float(observability["total_duration_ms"])
