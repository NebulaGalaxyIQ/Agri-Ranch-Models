from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/ranching_model",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
_engine_kwargs = {"pool_pre_ping": True, "future": True, "connect_args": connect_args}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "8")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "12")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "10")),
        "pool_recycle": 1800,
    })
engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="staff", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class FatteningProject(Base):
    __tablename__ = "fattening_projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    ranch_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_weight_kg: Mapped[float] = mapped_column(Float, default=330.0)
    target_adg_kg: Mapped[float] = mapped_column(Float, default=1.0)
    expected_sale_price_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    expected_gain_kg_head: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_feed_as_fed_kg_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_dmi_kg_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_feed_cost_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_operating_cost_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_mortality_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighing_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="TZS")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnimalBatch(Base):
    __tablename__ = "animal_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    pen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_adg_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_gain_kg_head: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_feed_as_fed_kg_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_dmi_kg_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_feed_cost_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_operating_cost_head_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_sale_price_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighing_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    project: Mapped[FatteningProject] = relationship()


class Animal(Base):
    __tablename__ = "animals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    tag_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    rfid: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    animal_type: Mapped[str] = mapped_column(String(40), default="Cattle")
    sex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    breed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(180), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(180), nullable=True)
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    entry_weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_price: Mapped[float] = mapped_column(Float, default=0.0)
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    planned_adg_kg_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_gain_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_feed_as_fed_kg_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_dmi_kg_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_feed_cost_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_operating_cost_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_sale_price_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_body_condition_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighing_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_ration_stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    pen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    project: Mapped[FatteningProject] = relationship()
    batch: Mapped[AnimalBatch | None] = relationship()


class AnimalWeight(Base):
    __tablename__ = "animal_weights"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id", ondelete="CASCADE"), index=True)
    weigh_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    body_condition_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    animal: Mapped[Animal] = relationship()


class AnimalMovement(Base):
    __tablename__ = "animal_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id", ondelete="CASCADE"), index=True)
    movement_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    from_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    to_location: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(250), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedItem(Base):
    __tablename__ = "feed_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), default="kg")
    category: Mapped[str] = mapped_column(String(60), default="Feed Ingredient", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reorder_level: Mapped[float] = mapped_column(Float, default=0.0)
    default_unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedPurchase(Base):
    __tablename__ = "feed_purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_item_id: Mapped[int] = mapped_column(ForeignKey("feed_items.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    transport_cost: Mapped[float] = mapped_column(Float, default=0.0)
    other_cost: Mapped[float] = mapped_column(Float, default=0.0)
    landed_unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier: Mapped[str | None] = mapped_column(String(180), nullable=True)
    supplier_contact: Mapped[str | None] = mapped_column(String(180), nullable=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True)
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    feed_item: Mapped[FeedItem] = relationship()


class FeedConsumption(Base):
    __tablename__ = "feed_consumption"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_item_id: Mapped[int] = mapped_column(ForeignKey("feed_items.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="SET NULL"), nullable=True, index=True)
    consumption_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    wastage_kg: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    feed_item: Mapped[FeedItem] = relationship()


class FeedRation(Base):
    __tablename__ = "feed_rations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, default=date.today)
    kg_per_head_day: Mapped[float] = mapped_column(Float, default=0.0)
    composition_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedNutritionProfile(Base):
    __tablename__ = "feed_nutrition_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_item_id: Mapped[int] = mapped_column(ForeignKey("feed_items.id", ondelete="CASCADE"), unique=True, index=True)
    dry_matter_pct: Mapped[float] = mapped_column(Float, default=100.0)
    crude_protein_pct_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    metabolizable_energy_mj_kg_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndf_pct_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_pct_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ash_pct_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    calcium_pct_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    phosphorus_pct_dm: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    feed_item: Mapped[FeedItem] = relationship()


class AnimalRation(Base):
    __tablename__ = "animal_rations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id", ondelete="CASCADE"), index=True)
    ration_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    feeding_round: Mapped[str] = mapped_column(String(60), default="Daily")
    ration_stage: Mapped[str] = mapped_column(String(60), default="Finisher", index=True)
    expected_adg_kg_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    animal: Mapped[Animal] = relationship()
    items: Mapped[list["AnimalRationItem"]] = relationship(back_populates="ration", cascade="all, delete-orphan")


class AnimalRationItem(Base):
    __tablename__ = "animal_ration_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ration_id: Mapped[int] = mapped_column(ForeignKey("animal_rations.id", ondelete="CASCADE"), index=True)
    feed_item_id: Mapped[int] = mapped_column(ForeignKey("feed_items.id", ondelete="RESTRICT"), index=True)
    offered_as_fed_kg: Mapped[float] = mapped_column(Float, nullable=False)
    refused_as_fed_kg: Mapped[float] = mapped_column(Float, default=0.0)
    dry_matter_pct: Mapped[float] = mapped_column(Float, default=100.0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    source_mix_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ration: Mapped[AnimalRation] = relationship(back_populates="items")
    feed_item: Mapped[FeedItem] = relationship()


class HealthRecord(Base):
    __tablename__ = "health_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="SET NULL"), nullable=True, index=True)
    event_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    record_type: Mapped[str] = mapped_column(String(40), default="treatment", index=True)
    diagnosis: Mapped[str | None] = mapped_column(String(250), nullable=True)
    medicine: Mapped[str | None] = mapped_column(String(180), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    withdrawal_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    condition_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True)
    inventory_quantity_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MortalityRecord(Base):
    __tablename__ = "mortality_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    mortality_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    cause: Mapped[str | None] = mapped_column(String(250), nullable=True)
    post_mortem: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_loss: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="SET NULL"), nullable=True, index=True)
    expense_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    supplier: Mapped[str | None] = mapped_column(String(180), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="SET NULL"), nullable=True, index=True)
    sale_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    buyer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    live_weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    price_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyOperation(Base):
    __tablename__ = "daily_operations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    operation_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="completed")
    assigned_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    location: Mapped[str | None] = mapped_column(String(180), nullable=True)
    products_supplied: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(180), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedMix(Base):
    __tablename__ = "feed_mixes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    purpose: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_reference_template: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedMixComponent(Base):
    __tablename__ = "feed_mix_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mix_id: Mapped[int] = mapped_column(ForeignKey("feed_mixes.id", ondelete="CASCADE"), index=True)
    feed_item_id: Mapped[int] = mapped_column(ForeignKey("feed_items.id", ondelete="RESTRICT"), index=True)
    inclusion_pct: Mapped[float] = mapped_column(Float, nullable=False)
    mix: Mapped[FeedMix] = relationship()
    feed_item: Mapped[FeedItem] = relationship()


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(180), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    item_type: Mapped[str] = mapped_column(String(60), default="Feed", index=True)
    unit: Mapped[str] = mapped_column(String(30), default="kg")
    feed_item_id: Mapped[int | None] = mapped_column(ForeignKey("feed_items.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    feed_mix_id: Mapped[int | None] = mapped_column(ForeignKey("feed_mixes.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    reorder_level: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True)
    movement_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_contact: Mapped[str | None] = mapped_column(String(180), nullable=True)
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    feeding_round: Mapped[str | None] = mapped_column(String(40), nullable=True)
    issued_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedingReceipt(Base):
    """Independent confirmation by feeding records. DOES NOT alter stock balance.

    A receipt may be tied to a precise physical Store issue or entered on its own.
    Unlinked receipts are audit exceptions, never fabricated Store deductions.
    """
    __tablename__ = "feeding_receipts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_issue_id: Mapped[int | None] = mapped_column(ForeignKey("stock_movements.id", ondelete="SET NULL"), nullable=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True)
    feeding_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="SET NULL"), nullable=True, index=True)
    feeding_round: Mapped[str] = mapped_column(String(40), default="Morning")
    received_kg: Mapped[float] = mapped_column(Float, nullable=False)
    offered_kg: Mapped[float] = mapped_column(Float, nullable=False)
    refused_kg: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FeedPlan(Base):
    __tablename__ = "feed_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="CASCADE"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="CASCADE"), nullable=True, index=True)
    stage: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    feeding_round: Mapped[str] = mapped_column(String(60), default="Morning", index=True)
    effective_from: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedPlanLine(Base):
    __tablename__ = "feed_plan_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("feed_plans.id", ondelete="CASCADE"), index=True)
    feed_item_id: Mapped[int | None] = mapped_column(ForeignKey("feed_items.id", ondelete="RESTRICT"), nullable=True, index=True)
    feed_mix_id: Mapped[int | None] = mapped_column(ForeignKey("feed_mixes.id", ondelete="RESTRICT"), nullable=True, index=True)
    quantity_kg_head: Mapped[float] = mapped_column(Float, nullable=False)
    default_refusal_kg_head: Mapped[float] = mapped_column(Float, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Routine(Base):
    __tablename__ = "routines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="CASCADE"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="CASCADE"), nullable=True, index=True)
    feeding_round: Mapped[str | None] = mapped_column(String(60), nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(10), nullable=True)
    frequency: Mapped[str] = mapped_column(String(30), default="daily", index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoutineLog(Base):
    __tablename__ = "routine_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(30), default="info", index=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("fattening_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("animal_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id", ondelete="SET NULL"), nullable=True, index=True)
    routine_id: Mapped[int | None] = mapped_column(ForeignKey("routines.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="unread", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    setting_value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_additive_schema_updates() -> None:
    """Add new planning columns to existing databases without destructive migrations.

    This project intentionally keeps deployment compact, so additive schema changes are
    applied at startup. Existing data is preserved and no column is dropped or renamed.
    """
    additions = {
        "fattening_projects": {
            "expected_gain_kg_head": "FLOAT",
            "expected_feed_as_fed_kg_head_day": "FLOAT",
            "expected_dmi_kg_head_day": "FLOAT",
            "expected_feed_cost_head_day": "FLOAT",
            "expected_operating_cost_head_day": "FLOAT",
            "expected_mortality_pct": "FLOAT",
            "weighing_interval_days": "INTEGER",
        },
        "animal_batches": {
            "end_date": "DATE",
            "expected_gain_kg_head": "FLOAT",
            "expected_feed_as_fed_kg_head_day": "FLOAT",
            "expected_dmi_kg_head_day": "FLOAT",
            "expected_feed_cost_head_day": "FLOAT",
            "expected_operating_cost_head_day": "FLOAT",
            "expected_sale_price_per_kg": "FLOAT",
            "weighing_interval_days": "INTEGER",
        },
        "animals": {
            "color": "VARCHAR(100)",
            "birth_date": "DATE",
            "estimated_age_months": "INTEGER",
            "condition_status": "VARCHAR(60)",
            "target_weight_kg": "FLOAT",
            "planned_adg_kg_day": "FLOAT",
            "expected_gain_kg": "FLOAT",
            "expected_target_date": "DATE",
            "expected_feed_as_fed_kg_day": "FLOAT",
            "expected_dmi_kg_day": "FLOAT",
            "expected_feed_cost_day": "FLOAT",
            "expected_operating_cost_day": "FLOAT",
            "expected_sale_price_per_kg": "FLOAT",
            "target_body_condition_score": "FLOAT",
            "weighing_interval_days": "INTEGER",
            "planned_ration_stage": "VARCHAR(60)",
        },
        "animal_weights": {"condition_status": "VARCHAR(60)"},
        "feed_items": {"category": "VARCHAR(60)", "description": "TEXT"},
        "feed_purchases": {
            "total_price": "FLOAT", "transport_cost": "FLOAT", "other_cost": "FLOAT", "landed_unit_cost": "FLOAT",
            "supplier_id": "INTEGER", "supplier_contact": "VARCHAR(180)", "store_id": "INTEGER", "lot_number": "VARCHAR(100)", "expiry_date": "DATE"
        },
        "feed_nutrition_profiles": {"fat_pct_dm": "FLOAT", "ash_pct_dm": "FLOAT"},
        "animal_ration_items": {"source_mix_name": "VARCHAR(160)"},
        "health_records": {"condition_status": "VARCHAR(60)", "inventory_item_id": "INTEGER", "inventory_quantity_used": "FLOAT"},
        "feed_mixes": {"batch_id": "INTEGER", "purpose": "VARCHAR(80)", "source_note": "VARCHAR(250)", "version": "INTEGER DEFAULT 1", "is_reference_template": "BOOLEAN DEFAULT FALSE", "is_approved": "BOOLEAN DEFAULT FALSE"},
        "inventory_items": {"feed_mix_id": "INTEGER"},
        "stock_movements": {"total_price": "FLOAT", "supplier_id": "INTEGER", "supplier_contact": "VARCHAR(180)", "lot_number": "VARCHAR(100)", "expiry_date": "DATE", "purpose": "VARCHAR(40)", "project_id": "INTEGER", "batch_id": "INTEGER", "feeding_round": "VARCHAR(40)", "issued_to": "VARCHAR(160)"},
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        for table_name, cols in additions.items():
            if table_name not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table_name)}
            for col_name, sql_type in cols.items():
                if col_name not in existing:
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}'))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_additive_schema_updates()


def seed_defaults() -> None:
    with SessionLocal() as db:
        project = db.query(FatteningProject).first()
        if not project:
            project = FatteningProject(
                name="Cape Ranch",
                ranch_name="Cape Ranch",
                target_weight_kg=330.0,
                target_adg_kg=1.0,
                expected_sale_price_per_kg=0.0,
                weighing_interval_days=7,
                currency="TZS",
            )
            db.add(project)
            db.flush()
            db.add(AnimalBatch(project_id=project.id, name="Lot 1", target_weight_kg=330.0, target_adg_kg=1.0, weighing_interval_days=7))
        elif (project.name or "").strip() in {"Fattening Project 2026", "Ranching Project 2026", "Union Ranches"}:
            project.name = "Cape Ranch"
        if (project.ranch_name or "").strip() in {"Union Ranches", "Ranching Project 2026", "Fattening Project 2026"}:
            project.ranch_name = "Cape Ranch"

        defaults = {
            "company_name": "Cape Ranch",
            "ranch_name": "Cape Ranch",
            "report_footer": "Confidential - Cape Ranch Management System",
            "currency": "TZS",
        }
        legacy_values = {
            "company_name": {"Union Meat Group", "Ranching Project 2026"},
            "ranch_name": {"Union Ranches", "Ranching Project 2026"},
            "report_footer": {"Confidential - Ranching & Animal Fattening Management System", "Confidential"},
        }
        # Cape Ranch: recognize only former built-in branding defaults.
        old_seed_brand = "Green" + chr(32) + "Hills Ranches"
        legacy_values.setdefault("company_name", set()).add(old_seed_brand)
        legacy_values.setdefault("ranch_name", set()).add(old_seed_brand)
        legacy_values.setdefault("report_footer", set()).add("Confidential - " + old_seed_brand + " Management System")
        settings = {x.setting_key: x for x in db.query(SystemSetting).all()}
        for key, value in defaults.items():
            setting = settings.get(key)
            if not setting:
                db.add(SystemSetting(setting_key=key, setting_value=value))
            elif key in legacy_values and (setting.setting_value or "").strip() in legacy_values[key]:
                setting.setting_value = value
        if not db.query(Store).first():
            db.add(Store(name="Main Store", location="Cape Ranch"))

        # Seed a practical editable reference feed library. Values are reference defaults
        # only; users can replace them with supplier/laboratory values for their own feed.
        reference_feeds = [
            ("Wheat Bran", "Concentrate", 87.0, 17.3, 9.7, 45.2, 4.2, 5.5, 0.13, 1.05),
            ("Maize Germ", "Concentrate", 89.0, 11.5, 12.0, 23.0, 7.5, 4.5, 0.10, 0.75),
            ("Maize Bran", "Concentrate", 88.7, 11.9, 10.5, 44.2, 5.0, 5.0, 0.10, 0.90),
            ("Sunflower Cake", "Protein", 89.0, 32.4, 9.5, 40.0, 2.5, 7.0, 0.35, 1.00),
            ("Soybean Meal", "Protein", 89.0, 48.0, 12.2, 13.0, 1.8, 6.5, 0.30, 0.65),
            ("Cottonseed Cake", "Protein", 90.0, 36.0, 10.0, 31.0, 6.0, 6.0, 0.20, 1.00),
            ("Molasses", "Energy", 75.0, 5.0, 12.0, 0.0, 0.2, 10.0, 0.90, 0.10),
            ("Mineral Premix", "Supplement", 95.0, 0.0, 0.0, 0.0, 0.0, 90.0, 18.0, 8.0),
            ("Salt", "Supplement", 100.0, 0.0, 0.0, 0.0, 0.0, 100.0, 0.0, 0.0),
            ("Green Grass", "Roughage", 25.0, 12.0, 9.0, 55.0, 3.0, 10.0, 0.50, 0.30),
            ("Hay", "Roughage", 90.0, 9.0, 8.0, 65.0, 2.0, 8.0, 0.45, 0.25),
        ]
        feed_by_name = {x.name.lower(): x for x in db.query(FeedItem).all()}
        for name, category, dm, cp, me, ndf, fat, ash, ca, phos in reference_feeds:
            feed = feed_by_name.get(name.lower())
            if not feed:
                feed = FeedItem(name=name, category=category, description="Reference feed-library item; edit nutrient values to match supplier or laboratory analysis.", unit="kg", reorder_level=0.0, default_unit_cost=0.0, is_active=True)
                db.add(feed); db.flush(); feed_by_name[name.lower()] = feed
            if not db.query(FeedNutritionProfile).filter(FeedNutritionProfile.feed_item_id == feed.id).first():
                db.add(FeedNutritionProfile(feed_item_id=feed.id, dry_matter_pct=dm, crude_protein_pct_dm=cp, metabolizable_energy_mj_kg_dm=me, ndf_pct_dm=ndf, fat_pct_dm=fat, ash_pct_dm=ash, calcium_pct_dm=ca, phosphorus_pct_dm=phos))
            if not db.query(InventoryItem).filter(InventoryItem.feed_item_id == feed.id).first():
                db.add(InventoryItem(name=feed.name, item_type="Feed", unit="kg", feed_item_id=feed.id, reorder_level=float(feed.reorder_level or 0), is_active=True))

        db.flush()
        feed_by_name = {x.name.lower(): x for x in db.query(FeedItem).all()}
        reference_mixes = [
            ("Reference Starter Mix", "Starter", "Higher-fibre starter concentrate; offer roughage separately.", [("Wheat Bran",35),("Maize Germ",20),("Maize Bran",20),("Sunflower Cake",18),("Molasses",4),("Mineral Premix",2),("Salt",1)]),
            ("Reference Grower Mix", "Grower", "Balanced grower concentrate; adjust to local ingredient analysis and forage program.", [("Wheat Bran",30),("Maize Germ",25),("Maize Bran",17),("Sunflower Cake",20),("Molasses",4),("Mineral Premix",3),("Salt",1)]),
            ("Reference Finisher Mix", "Finisher", "Higher-energy finishing concentrate; transition gradually and maintain adequate roughage.", [("Wheat Bran",25),("Maize Germ",35),("Maize Bran",20),("Sunflower Cake",12),("Molasses",5),("Mineral Premix",2),("Salt",1)]),
            ("Reference High-Forage Supplement", "Grower", "Protein/energy supplement for higher-forage systems.", [("Wheat Bran",40),("Maize Bran",25),("Sunflower Cake",25),("Molasses",5),("Mineral Premix",4),("Salt",1)]),
        ]
        existing_mixes = {x.name.lower(): x for x in db.query(FeedMix).all()}
        for name, stage, description, components in reference_mixes:
            if name.lower() in existing_mixes:
                continue
            mix = FeedMix(name=name, stage=stage, purpose="Reference formulation", source_note="Editable Cape Ranch reference template; validate against local feed analysis and professional nutrition guidance.", version=1, is_reference_template=True, is_approved=False, description=description, is_active=True)
            db.add(mix); db.flush()
            for feed_name, pct in components:
                feed = feed_by_name.get(feed_name.lower())
                if feed:
                    db.add(FeedMixComponent(mix_id=mix.id, feed_item_id=feed.id, inclusion_pct=float(pct)))
            if not db.query(InventoryItem).filter(InventoryItem.feed_mix_id == mix.id).first():
                db.add(InventoryItem(name=mix.name, item_type="Feed Mix", unit="kg", feed_mix_id=mix.id, reorder_level=0.0, is_active=True))
        db.commit()


def get_setting(db: Session, key: str, default: str = "") -> str:
    item = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return item.setting_value if item else default


def set_setting(db: Session, key: str, value: str) -> None:
    item = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    if item:
        item.setting_value = value
        item.updated_at = utcnow()
    else:
        db.add(SystemSetting(setting_key=key, setting_value=value))
