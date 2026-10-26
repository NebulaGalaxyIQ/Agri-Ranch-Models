"""Gardening V2 validated contracts; V6 GardenIn/GardenLogIn remain supported."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Currency = Literal['TZS', 'USD', 'KES', 'EUR']
Shift = Literal['morning', 'afternoon', 'evening', 'unscheduled']
Action = Literal['planting', 'watering', 'weeding', 'pruning', 'landscaping', 'cleaning', 'mowing', 'mulching', 'fertilizing', 'inspection', 'other']

class PlantIn(BaseModel):
    area_id: int
    name: str = Field(min_length=2, max_length=160)
    category: Literal['ornamental', 'flower', 'tree', 'hedge', 'vegetable', 'lawn', 'herb', 'other'] = 'ornamental'
    variety: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=1, le=1000000)
    planted_on: date | None = None
    source: str | None = Field(default=None, max_length=160)
    unit_purchase_cost: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    condition: Literal['healthy', 'stressed', 'diseased', 'damaged', 'dead', 'replaced'] = 'healthy'
    notes: str | None = Field(default=None, max_length=4000)

class NurseryIn(BaseModel):
    area_id: int
    plant_name: str = Field(min_length=2, max_length=160)
    method: Literal['seed', 'cutting', 'transplant', 'grafting', 'other'] = 'seed'
    started_on: date = Field(default_factory=date.today)
    seeds_started: int = Field(ge=1)
    germinated: int = Field(default=0, ge=0)
    survived: int = Field(default=0, ge=0)
    status: Literal['active', 'transplanted', 'completed', 'cancelled'] = 'active'
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode='after')
    def check_counts(self):
        if not 0 <= self.survived <= self.germinated <= self.seeds_started:
            raise ValueError('Survived must be ≤ germinated, and germinated ≤ started')
        return self

class ScheduleIn(BaseModel):
    area_id: int
    title: str = Field(min_length=2, max_length=160)
    action: Action
    frequency: Literal['once', 'daily', 'weekly', 'monthly'] = 'daily'
    shift: Shift = 'morning'
    assigned_to: int | None = None
    starts_on: date = Field(default_factory=date.today)
    ends_on: date | None = None
    instructions: str | None = Field(default=None, max_length=4000)

    @model_validator(mode='after')
    def dates(self):
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValueError('End date cannot precede the start date')
        return self

class WorkIn(BaseModel):
    area_id: int
    plant_id: int | None = None
    action: Action
    performed_on: date = Field(default_factory=date.today)
    shift: Shift = 'unscheduled'
    water_litres: Decimal = Field(default=Decimal('0'), ge=0)
    area_covered_m2: Decimal = Field(default=Decimal('0'), ge=0)
    labor_hours: Decimal = Field(default=Decimal('0'), ge=0)
    direct_cost: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    observations: str | None = Field(default=None, max_length=4000)

class CompleteIn(BaseModel):
    performed_on: date = Field(default_factory=date.today)
    water_litres: Decimal = Field(default=Decimal('0'), ge=0)
    area_covered_m2: Decimal = Field(default=Decimal('0'), ge=0)
    labor_hours: Decimal = Field(default=Decimal('0'), ge=0)
    direct_cost: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    observations: str | None = Field(default=None, max_length=4000)

class HealthIn(BaseModel):
    area_id: int
    plant_id: int | None = None
    observed_on: date = Field(default_factory=date.today)
    issue: str = Field(min_length=2, max_length=160)
    severity: Literal['low', 'moderate', 'high', 'critical'] = 'low'
    affected_count: int = Field(default=0, ge=0)
    treatment: str | None = Field(default=None, max_length=4000)
    follow_up_on: date | None = None
    status: Literal['open', 'treating', 'recovered', 'closed'] = 'open'
    expense: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'

class ExpenseIn(BaseModel):
    area_id: int
    spent_on: date = Field(default_factory=date.today)
    category: Literal['seed', 'seedling', 'fertilizer', 'compost', 'treatment', 'tools', 'water', 'labor', 'machinery', 'transport', 'other']
    description: str = Field(min_length=2, max_length=200)
    quantity: Decimal = Field(default=Decimal('1'), gt=0)
    unit: str = Field(default='unit', min_length=1, max_length=32)
    unit_cost: Decimal = Field(default=Decimal('0'), ge=0)
    other_cost: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    inventory_item_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)

class InspectionIn(BaseModel):
    area_id: int
    inspected_on: date = Field(default_factory=date.today)
    cleanliness: int = Field(ge=1, le=5)
    plant_health: int = Field(ge=1, le=5)
    weed_control: int = Field(ge=1, le=5)
    irrigation: int = Field(ge=1, le=5)
    corrective_action: str | None = Field(default=None, max_length=4000)
    follow_up_on: date | None = None

class AreaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    type: str | None = Field(default=None, min_length=2, max_length=80)
    area_m2: Decimal | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=4000)

class PlantUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=1000000)
    condition: Literal['healthy', 'stressed', 'diseased', 'damaged', 'dead', 'replaced'] | None = None
    notes: str | None = Field(default=None, max_length=4000)

class NurseryUpdate(BaseModel):
    germinated: int | None = Field(default=None, ge=0)
    survived: int | None = Field(default=None, ge=0)
    status: Literal['active','transplanted','completed','cancelled'] | None = None
    notes: str | None = Field(default=None, max_length=4000)

class HealthUpdate(BaseModel):
    treatment: str | None = Field(default=None, max_length=4000)
    status: Literal['open','treating','recovered','closed'] | None = None
    follow_up_on: date | None = None

class ScheduleUpdate(BaseModel):
    is_active: bool
