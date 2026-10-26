from __future__ import annotations

from datetime import date,datetime,timedelta,timezone
from typing import Literal
from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Integer, String, Text, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped,mapped_column
from database import Base,utcnow

# Canonical organization/subscription entities; existing PostgreSQL table names are unchanged.
class Organization(Base):
    __tablename__ = 'v5_organizations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(180))
    registration_number: Mapped[str | None] = mapped_column(String(100))
    tax_number: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(90), default='Tanzania')
    region: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(254))
    billing_email: Mapped[str | None] = mapped_column(String(254))
    livestock_types: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default='pending', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Membership(Base):
    __tablename__ = 'v5_memberships'
    __table_args__ = (UniqueConstraint('organization_id','user_id',name='uq_v5_member_org_user'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    role: Mapped[str] = mapped_column(String(40), default='worker')
    permissions: Mapped[str] = mapped_column(Text, default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class V5Ranch(Base):
    __tablename__ = 'v5_ranches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(180))
    location: Mapped[str | None] = mapped_column(String(240))


class V5Batch(Base):
    __tablename__ = 'v5_batches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    ranch_id: Mapped[int] = mapped_column(ForeignKey('v5_ranches.id'))
    name: Mapped[str] = mapped_column(String(160))
    animal_count: Mapped[int] = mapped_column(Integer, default=0)  # legacy planned count; occupancy is calculated from active animals
    project_id: Mapped[int | None] = mapped_column(ForeignKey('v5_projects.id'), index=True)
    capacity: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[__import__('datetime').date | None] = mapped_column(__import__('sqlalchemy').Date)
    end_date: Mapped[__import__('datetime').date | None] = mapped_column(__import__('sqlalchemy').Date)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='active')


class V5Routine(Base):
    __tablename__ = 'v5_routine_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey('v5_batches.id'))
    category: Mapped[str] = mapped_column(String(40))
    shift: Mapped[str] = mapped_column(String(35), default='Other')
    animal_tag: Mapped[str | None] = mapped_column(String(120))
    pen_id: Mapped[int | None] = mapped_column(ForeignKey('v5_pens.id'))
    frequency: Mapped[str | None] = mapped_column(String(20))
    product: Mapped[str | None] = mapped_column(String(180))
    quantity: Mapped[float | None] = mapped_column()
    unit: Mapped[str | None] = mapped_column(String(35))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    client_reference: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint('organization_id','client_reference',name='uq_v5_entry_dedupe'),)
