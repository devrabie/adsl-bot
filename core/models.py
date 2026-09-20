import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Line(Base):
    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Subscriber info
    subscriber_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    package_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_uid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    session_cookies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scraped cache fields
    total_gb: Mapped[float] = mapped_column(Float, default=0.0)
    used_gb: Mapped[float] = mapped_column(Float, default=0.0)
    remaining_gb: Mapped[float] = mapped_column(Float, default=0.0)
    expiry_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    days_left: Mapped[int] = mapped_column(Integer, default=0)
    last_scraped_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Custom Alert Threshold Settings per line
    gb_threshold_warning: Mapped[float] = mapped_column(Float, default=50.0) # 50 GB
    gb_threshold_critical: Mapped[float] = mapped_column(Float, default=10.0) # 10 GB
    days_threshold_warning: Mapped[int] = mapped_column(Integer, default=10)   # 10 Days
    days_threshold_critical: Mapped[int] = mapped_column(Integer, default=5)   # 5 Days

    # Alert Sent Flags to avoid repeating alerts
    alert_50gb_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_10gb_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_10days_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_5days_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    snapshots: Mapped[List["Snapshot"]] = relationship("Snapshot", back_populates="line", cascade="all, delete-orphan")

class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(Integer, ForeignKey("lines.id", ondelete="CASCADE"), nullable=False)

    total_gb: Mapped[float] = mapped_column(Float, default=0.0)
    used_gb: Mapped[float] = mapped_column(Float, default=0.0)
    remaining_gb: Mapped[float] = mapped_column(Float, default=0.0)
    days_left: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    line: Mapped["Line"] = relationship("Line", back_populates="snapshots")
