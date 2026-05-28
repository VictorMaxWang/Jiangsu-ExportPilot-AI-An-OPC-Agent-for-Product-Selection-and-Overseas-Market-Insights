from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DataSourceCache(TimestampMixin, Base):
    __tablename__ = "data_source_caches"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "endpoint",
            "query",
            "country",
            name="uq_data_source_caches_provider_endpoint_query_country",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
