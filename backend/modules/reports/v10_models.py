"""V10 additive reporting metadata. Operational records remain in their owning modules."""
from __future__ import annotations
from sqlalchemy import Integer, String, DateTime, ForeignKey, JSON, Index, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow

class SavedReport(Base):
    __tablename__ = 'v10_saved_reports'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(160))
    section_id: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    visibility: Mapped[str] = mapped_column(String(20), default='private')
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class ReportRun(Base):
    __tablename__ = 'v10_report_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    section_id: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(12))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='completed')
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)

class ReportSchedule(Base):
    __tablename__ = 'v10_report_schedules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    saved_report_id: Mapped[int] = mapped_column(ForeignKey('v10_saved_reports.id'), index=True)
    cadence: Mapped[str] = mapped_column(String(25))
    timezone: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    format: Mapped[str] = mapped_column(String(8), default='pdf')
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
