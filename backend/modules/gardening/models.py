from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, utcnow


# Domain-owned database entities. Table names are preserved for existing installations.
class GardenArea(Base):
    __tablename__='v6_garden_areas'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    name:Mapped[str]=mapped_column(String(160))
    area_m2:Mapped[Decimal|None]=mapped_column(Numeric(12,2))
    type:Mapped[str]=mapped_column(String(80),default='landscaping')
    notes:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class GardenRecord(Base):
    __tablename__='v6_garden_records'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    area_id:Mapped[int]=mapped_column(ForeignKey('v6_garden_areas.id'),index=True)
    action:Mapped[str]=mapped_column(String(40))
    performed_on:Mapped[date]=mapped_column(Date)
    observations:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


# Gardening V2 additive records. Historical v6 tables remain unchanged.
class GardenPlant(Base):
    __tablename__ = 'v11_garden_plants'
    __table_args__ = (Index('ix_v11_garden_plant_org_area', 'organization_id', 'area_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default='ornamental')
    variety: Mapped[str | None] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    planted_on: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(160))
    unit_purchase_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default='TZS', nullable=False)
    condition: Mapped[str] = mapped_column(String(32), default='healthy', nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GardenNurseryBatch(Base):
    __tablename__ = 'v11_garden_nursery_batches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    plant_name: Mapped[str] = mapped_column(String(160), nullable=False)
    method: Mapped[str] = mapped_column(String(30), default='seed', nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    seeds_started: Mapped[int] = mapped_column(Integer, nullable=False)
    germinated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    survived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='active')
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GardenSchedule(Base):
    __tablename__ = 'v11_garden_schedules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency: Mapped[str] = mapped_column(String(24), nullable=False, default='daily')
    shift: Mapped[str] = mapped_column(String(24), nullable=False, default='morning')
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GardenWork(Base):
    __tablename__ = 'v11_garden_work'
    __table_args__ = (UniqueConstraint('schedule_id', 'performed_on', name='uq_v11_garden_schedule_day'),
                      Index('ix_v11_garden_work_org_date', 'organization_id', 'performed_on'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey('v11_garden_schedules.id'))
    plant_id: Mapped[int | None] = mapped_column(ForeignKey('v11_garden_plants.id'))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    performed_on: Mapped[date] = mapped_column(Date, nullable=False)
    shift: Mapped[str] = mapped_column(String(24), nullable=False, default='unscheduled')
    water_litres: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    area_covered_m2: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    labor_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    direct_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default='TZS', nullable=False)
    observations: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GardenHealth(Base):
    __tablename__ = 'v11_garden_health'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    plant_id: Mapped[int | None] = mapped_column(ForeignKey('v11_garden_plants.id'))
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    issue: Mapped[str] = mapped_column(String(160), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False, default='low')
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    treatment: Mapped[str | None] = mapped_column(Text)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='open')
    expense: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default='TZS', nullable=False)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GardenExpense(Base):
    __tablename__ = 'v11_garden_expenses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    spent_on: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=1, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default='unit', nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    other_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default='TZS', nullable=False)
    inventory_item_id: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GardenInspection(Base):
    __tablename__ = 'v11_garden_inspections'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), nullable=False, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey('v6_garden_areas.id'), nullable=False)
    inspected_on: Mapped[date] = mapped_column(Date, nullable=False)
    cleanliness: Mapped[int] = mapped_column(Integer, nullable=False)
    plant_health: Mapped[int] = mapped_column(Integer, nullable=False)
    weed_control: Mapped[int] = mapped_column(Integer, nullable=False)
    irrigation: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    inspected_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
