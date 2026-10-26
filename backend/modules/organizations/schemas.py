"""Idempotent additive V5 columns for existing installations; always back up DB first.
Columns remain nullable to protect historical V5 records and do not touch legacy V4 tables.
"""
from sqlalchemy import inspect, text
from database import engine

COLUMNS = {
 'v5_routine_entries': {'pen_id':'INTEGER','frequency':"VARCHAR(20) DEFAULT 'daily'"},
 'v5_weight_observations': {'routine_id':'INTEGER'},

 'v5_batches': {
  'project_id':'INTEGER','capacity':'INTEGER','start_date':'DATE','end_date':'DATE',
  'description':'TEXT','status':"VARCHAR(30) DEFAULT 'active'",
 },
 'v5_animals': {'purchase_currency':"VARCHAR(10) DEFAULT 'TZS'",
  'breed':'VARCHAR(100)','color':'VARCHAR(100)','origin':'VARCHAR(180)','age_months':'INTEGER',
  'date_of_birth':'DATE','supplier_name':'VARCHAR(180)','supplier_contact':'VARCHAR(120)',
  'arrival_date':'DATE','notes':'TEXT',
 },
 'v5_rations': {'feed_type':"VARCHAR(40) DEFAULT 'maintenance'",'animal_id':'INTEGER'},
 'v5_stock_items': {'currency':"VARCHAR(10) DEFAULT 'TZS'",'reorder_level':'NUMERIC(16,3) DEFAULT 0'},
 'v5_stock_movements': {'transaction_date':'DATE','source_type':'VARCHAR(30)','batch_id':'INTEGER'},
 'v5_finance_entries': {'source_type':'VARCHAR(40)','source_id':'INTEGER','created_by':'INTEGER','animal_id':'INTEGER'},
 'v5_stock_receipts': {'exchange_rate':'NUMERIC(18,8) DEFAULT 1','base_currency':"VARCHAR(10) DEFAULT 'TZS'",'base_total_cost':'NUMERIC(18,2)'},
 'v5_tasks': {'pen_id':'INTEGER','due_date':'DATE','completed_by':'INTEGER','completed_at':'TIMESTAMP'},
 'v5_feed_plans': {'frequency':"VARCHAR(20) DEFAULT 'daily'"},
 'v5_projects': {'manager_id':'INTEGER','target_animals':'INTEGER','target_weight_kg':'NUMERIC(12,3)'},
}
def upgrade_v5_schema():
    inspector=inspect(engine)
    with engine.begin() as connection:
        for table, cols in COLUMNS.items():
            if not inspector.has_table(table):continue
            existing={col['name'] for col in inspector.get_columns(table)}
            for name,definition in cols.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))


def migrate_bootstrap_owner():
    """The original first/bootstrap administrator becomes the explicit owner principal.
    Organization administrators created subsequently remain staff members."""
    from database import SessionLocal, User
    with SessionLocal() as db:
        initial=db.get(User,1)
        if initial and initial.role=='admin':
            initial.role='platform_owner'
            db.commit()

from datetime import date,datetime
from typing import Literal
from pydantic import BaseModel,EmailStr,Field


class OrgIn(BaseModel):
    name: str = Field(min_length=2,max_length=180)
    trading_name: str | None = None
    registration_number: str | None = None
    tax_number: str | None = None
    country: str = 'Tanzania'
    region: str | None = None
    district: str | None = None
    address: str | None = None
    phone: str | None = None
    email: EmailStr
    billing_email: EmailStr | None = None
    livestock_types: str | None = None
    admin_name: str = Field(min_length=2)
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=128)


class OrgDecision(BaseModel):
    status: Literal['approved','rejected','suspended']


class KeyIn(BaseModel):
    organization_id: int
    duration_days: int = Field(default=30,ge=30,le=3650)
    max_employees: int = Field(default=25,ge=1,le=100000)


class RedeemIn(BaseModel):
    key: str = Field(min_length=20)


class MemberIn(BaseModel):
    name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=10)
    role: str = 'worker'


class MemberPatch(BaseModel):
    active: bool | None = None
    role: str | None = None


class RanchIn(BaseModel):
    name: str = Field(min_length=2)
    location: str | None = None


class BatchIn(BaseModel):
    name: str = Field(min_length=2,max_length=160)
    project_id: int | None = None
    ranch_id: int | None = None  # inferred from project or organization default
    capacity: int = Field(default=100,ge=1,le=1000000)
    start_date: __import__('datetime').date = Field(default_factory=__import__('datetime').date.today)
    end_date: __import__('datetime').date | None = None
    description: str | None = None
    status: Literal['planned','active','completed'] = 'active'
    animal_count: int = Field(default=0,ge=0)  # accepted for older integrations; ignored as actual count


class RoutineIn(BaseModel):
    category: str
    shift: str = 'Other'
    batch_id: int | None = None
    animal_tag: str | None = None  # backward compatibility, always resolved against the registry
    animal_id: int | None = None
    pen_id: int | None = None
    frequency: Literal['daily','weekly','monthly'] = 'daily'
    product: str | None = None
    quantity: float | None = Field(default=None,ge=0)
    unit: str | None = None
    notes: str | None = None
    client_reference: str = Field(min_length=8,max_length=100)
