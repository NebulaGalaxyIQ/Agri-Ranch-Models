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
class LivestockGroup(Base):
    __tablename__='v6_livestock_groups'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    name:Mapped[str]=mapped_column(String(160))
    species:Mapped[str]=mapped_column(String(80))
    purpose:Mapped[str]=mapped_column(String(60),default='general')
    head_count:Mapped[int]=mapped_column(Integer,default=0)
    location:Mapped[str|None]=mapped_column(String(180))
    notes:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class GeneralAnimal(Base):
    __tablename__='v6_general_animals'
    __table_args__=(UniqueConstraint('organization_id','tag',name='uq_v6_general_animal_tag'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    group_id:Mapped[int|None]=mapped_column(ForeignKey('v6_livestock_groups.id'))
    tag:Mapped[str]=mapped_column(String(100))
    species:Mapped[str]=mapped_column(String(80))
    breed:Mapped[str|None]=mapped_column(String(100))
    sex:Mapped[str|None]=mapped_column(String(20))
    birth_date:Mapped[date|None]=mapped_column(Date)
    origin:Mapped[str|None]=mapped_column(String(200))
    status:Mapped[str]=mapped_column(String(30),default='active')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class LivestockProject(Base):
    __tablename__='v61_livestock_projects'
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    name:Mapped[str]=mapped_column(String(160))
    purpose:Mapped[str]=mapped_column(String(100),default='general')
    start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date|None]=mapped_column(Date)
    currency:Mapped[str]=mapped_column(String(8),default='TZS')
    notes:Mapped[str|None]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class LivestockProjectGroup(Base):
    __tablename__='v61_livestock_project_groups'
    __table_args__=(UniqueConstraint('organization_id','project_id','group_id',name='uq_v61_project_group'), UniqueConstraint('organization_id','group_id',name='uq_v61_group_single_project'))
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v61_livestock_projects.id'),index=True)
    group_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_groups.id'),index=True)


class LivestockProjectCost(Base):
    __tablename__='v61_livestock_project_costs'
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v61_livestock_projects.id'),index=True)
    category:Mapped[str]=mapped_column(String(70))
    description:Mapped[str]=mapped_column(String(240))
    amount:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(8))
    performed_on:Mapped[date]=mapped_column(Date)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class ProductLot(Base):
    __tablename__='v61_livestock_product_lots'
    __table_args__=(UniqueConstraint('organization_id','event_id',name='uq_v61_product_lot_event'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    event_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_events.id'),index=True)
    group_id:Mapped[int|None]=mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v6_general_animals.id'))
    product:Mapped[str]=mapped_column(String(80))
    unit:Mapped[str]=mapped_column(String(30))
    quantity_received:Mapped[Decimal]=mapped_column(Numeric(15,3))
    quantity_sold:Mapped[Decimal]=mapped_column(Numeric(15,3),default=0)
    collected_on:Mapped[date]=mapped_column(Date)


class ProductSale(Base):
    __tablename__='v61_livestock_product_sales'
    __table_args__=(UniqueConstraint('organization_id','reference',name='uq_v61_product_sale_ref'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    lot_id:Mapped[int]=mapped_column(ForeignKey('v61_livestock_product_lots.id'),index=True)
    quantity:Mapped[Decimal]=mapped_column(Numeric(15,3))
    price_per_unit:Mapped[Decimal]=mapped_column(Numeric(18,2))
    gross:Mapped[Decimal]=mapped_column(Numeric(18,2))
    buyer:Mapped[str]=mapped_column(String(180))
    currency:Mapped[str]=mapped_column(String(8))
    sold_on:Mapped[date]=mapped_column(Date)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    reference:Mapped[str]=mapped_column(String(100))


class LivestockEvent(Base):
    __tablename__='v6_livestock_events'
    __table_args__=(UniqueConstraint('organization_id','reference',name='uq_v6_livestock_event_ref'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    group_id:Mapped[int|None]=mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v6_general_animals.id'))
    reference:Mapped[str]=mapped_column(String(120))
    action:Mapped[str]=mapped_column(String(40))
    performed_on:Mapped[date]=mapped_column(Date)
    quantity:Mapped[Decimal|None]=mapped_column(Numeric(14,3))
    unit:Mapped[str|None]=mapped_column(String(24))
    cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    currency:Mapped[str]=mapped_column(String(8),default='TZS')
    notes:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class LivestockSale(Base):
    __tablename__='v6_livestock_sales'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    group_id:Mapped[int|None]=mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v6_general_animals.id'))
    buyer:Mapped[str]=mapped_column(String(180))
    buyer_contact:Mapped[str|None]=mapped_column(String(120))
    reason:Mapped[str]=mapped_column(String(240))
    price_basis:Mapped[str]=mapped_column(String(20))
    price_per_unit:Mapped[Decimal]=mapped_column(Numeric(18,2))
    quantity:Mapped[int]=mapped_column(Integer)
    weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(14,3))
    gross:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(8))
    sale_date:Mapped[date]=mapped_column(Date)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


# V8 Livestock & Poultry additions. Existing production, herd, product and sales
# tables above retain their original identifiers and data.
class LivestockHouse(Base):
    __tablename__ = 'v8_livestock_houses'
    __table_args__ = (UniqueConstraint('organization_id', 'code', name='uq_v8_house_code'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    ranch_id: Mapped[int] = mapped_column(ForeignKey('v5_ranches.id'), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    house_type: Mapped[str] = mapped_column(String(60), default='barn')
    species: Mapped[str | None] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(180))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class LivestockPlacement(Base):
    __tablename__ = 'v8_livestock_placements'
    __table_args__ = (UniqueConstraint('organization_id', 'group_id', name='uq_v8_group_placement'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('v6_livestock_groups.id'), index=True)
    house_id: Mapped[int] = mapped_column(ForeignKey('v8_livestock_houses.id'), index=True)
    assigned_on: Mapped[date] = mapped_column(Date)
    assigned_by: Mapped[int] = mapped_column(ForeignKey('users.id'))

class LivestockHousingMovement(Base):
    __tablename__ = 'v8_livestock_housing_movements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('v6_livestock_groups.id'), index=True)
    from_house_id: Mapped[int | None] = mapped_column(ForeignKey('v8_livestock_houses.id'))
    to_house_id: Mapped[int] = mapped_column(ForeignKey('v8_livestock_houses.id'))
    moved_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))

class LivestockCareRecord(Base):
    __tablename__ = 'v8_livestock_care_records'
    __table_args__ = (UniqueConstraint('organization_id', 'reference', name='uq_v8_care_ref'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id: Mapped[int | None] = mapped_column(ForeignKey('v6_general_animals.id'))
    activity: Mapped[str] = mapped_column(String(45))
    shift: Mapped[str] = mapped_column(String(20))
    performed_on: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3))
    unit: Mapped[str | None] = mapped_column(String(30))
    expense: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default='TZS')
    reference: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class LivestockBreedingRecord(Base):
    __tablename__ = 'v8_livestock_breeding_records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id: Mapped[int | None] = mapped_column(ForeignKey('v6_general_animals.id'))
    method: Mapped[str] = mapped_column(String(45))
    sire_tag: Mapped[str | None] = mapped_column(String(100))
    service_date: Mapped[date] = mapped_column(Date)
    expected_date: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(35), default='planned')
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))

class LivestockHealthRecord(Base):
    __tablename__ = 'v8_livestock_health_records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id: Mapped[int | None] = mapped_column(ForeignKey('v6_general_animals.id'))
    action: Mapped[str] = mapped_column(String(45))
    condition: Mapped[str | None] = mapped_column(String(160))
    medication: Mapped[str | None] = mapped_column(String(160))
    dosage: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default='completed')
    performed_on: Mapped[date] = mapped_column(Date)
    next_due: Mapped[date | None] = mapped_column(Date)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default='TZS')
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))

class LivestockWeightRecord(Base):
    __tablename__ = 'v8_livestock_weight_records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('v6_livestock_groups.id'))
    animal_id: Mapped[int | None] = mapped_column(ForeignKey('v6_general_animals.id'))
    measured_on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    sample_size: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))

class LivestockIncubation(Base):
    __tablename__ = 'v8_livestock_incubations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('v6_livestock_groups.id'), index=True)
    batch_code: Mapped[str] = mapped_column(String(100))
    eggs_set: Mapped[int] = mapped_column(Integer)
    set_on: Mapped[date] = mapped_column(Date)
    expected_on: Mapped[date] = mapped_column(Date)
    hatched_on: Mapped[date | None] = mapped_column(Date)
    eggs_hatched: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(25), default='incubating')
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (UniqueConstraint('organization_id', 'batch_code', name='uq_v8_incubation_batch'),)

# V8.3 additive entities: no ALTER TABLE on V6/V8 records, and no Fattening changes.
class LivestockGroupProfile(Base):
    __tablename__='v83_livestock_group_profiles'
    __table_args__=(UniqueConstraint('organization_id','group_id',name='uq_v83_group_profile'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    group_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_groups.id'),index=True)
    breed:Mapped[str|None]=mapped_column(String(100))
    production_stage:Mapped[str|None]=mapped_column(String(60))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LivestockIndividualProfile(Base):
    __tablename__='v83_livestock_individual_profiles'
    __table_args__=(UniqueConstraint('organization_id','animal_id',name='uq_v83_individual_profile'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    animal_id:Mapped[int]=mapped_column(ForeignKey('v6_general_animals.id'),index=True)
    offspring_cohort_id:Mapped[int|None]=mapped_column(ForeignKey('v83_livestock_offspring_cohorts.id'),index=True)
    dam_id:Mapped[int|None]=mapped_column(ForeignKey('v6_general_animals.id'))
    sire_id:Mapped[int|None]=mapped_column(ForeignKey('v6_general_animals.id'))
    characteristics:Mapped[str|None]=mapped_column(Text)
    initial_weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(14,3))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LivestockHousingProfile(Base):
    __tablename__='v83_livestock_housing_profiles'
    __table_args__=(UniqueConstraint('organization_id','house_id',name='uq_v83_house_profile'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    house_id:Mapped[int]=mapped_column(ForeignKey('v8_livestock_houses.id'),index=True)
    purpose:Mapped[str]=mapped_column(String(60))
    source_group_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_groups.id'))

class LivestockRegistrationCost(Base):
    __tablename__='v83_livestock_registration_costs'
    __table_args__=(UniqueConstraint('organization_id','source_kind','source_id',name='uq_v83_registration_cost'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int|None]=mapped_column(ForeignKey('v61_livestock_projects.id'),index=True)
    source_kind:Mapped[str]=mapped_column(String(40))
    source_id:Mapped[int]=mapped_column(Integer)
    description:Mapped[str]=mapped_column(String(240))
    quantity:Mapped[Decimal]=mapped_column(Numeric(15,3))
    unit:Mapped[str]=mapped_column(String(40))
    unit_cost:Mapped[Decimal]=mapped_column(Numeric(18,2))
    total:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(8),default='TZS')
    recorded_on:Mapped[date]=mapped_column(Date,default=date.today)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))

class LivestockRoutineTemplate(Base):
    __tablename__='v83_livestock_routine_templates'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    group_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_groups.id'),index=True)
    name:Mapped[str]=mapped_column(String(160))
    activity:Mapped[str]=mapped_column(String(45))
    shift:Mapped[str]=mapped_column(String(20))
    reminder_time:Mapped[str|None]=mapped_column(String(5))
    days_of_week:Mapped[str]=mapped_column(String(20),default='0123456')
    default_quantity:Mapped[Decimal|None]=mapped_column(Numeric(15,3))
    unit:Mapped[str|None]=mapped_column(String(30))
    default_expense:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    currency:Mapped[str]=mapped_column(String(8),default='TZS')
    instructions:Mapped[str|None]=mapped_column(Text)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    starts_on:Mapped[date]=mapped_column(Date,default=date.today)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LivestockRoutineCompletion(Base):
    __tablename__='v83_livestock_routine_completions'
    __table_args__=(UniqueConstraint('organization_id','template_id','completed_on',name='uq_v83_routine_once_per_day'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    template_id:Mapped[int]=mapped_column(ForeignKey('v83_livestock_routine_templates.id'),index=True)
    completed_on:Mapped[date]=mapped_column(Date,index=True)
    quantity:Mapped[Decimal|None]=mapped_column(Numeric(15,3))
    expense:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    currency:Mapped[str]=mapped_column(String(8))
    notes:Mapped[str|None]=mapped_column(Text)
    completed_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LivestockBreedingTimeline(Base):
    __tablename__='v83_livestock_breeding_timeline'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    breeding_id:Mapped[int]=mapped_column(ForeignKey('v8_livestock_breeding_records.id'),index=True)
    event:Mapped[str]=mapped_column(String(40))
    event_on:Mapped[date]=mapped_column(Date)
    notes:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LivestockOffspringCohort(Base):
    __tablename__='v83_livestock_offspring_cohorts'
    __table_args__=(UniqueConstraint('organization_id','breeding_id',name='uq_v83_birth_breeding'),
                    UniqueConstraint('organization_id','incubation_id',name='uq_v83_birth_incubation'),
                    UniqueConstraint('organization_id','child_group_id',name='uq_v83_child_group'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    breeding_id:Mapped[int|None]=mapped_column(ForeignKey('v8_livestock_breeding_records.id'))
    incubation_id:Mapped[int|None]=mapped_column(ForeignKey('v8_livestock_incubations.id'))
    parent_group_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_groups.id'))
    child_group_id:Mapped[int]=mapped_column(ForeignKey('v6_livestock_groups.id'))
    dam_id:Mapped[int|None]=mapped_column(ForeignKey('v6_general_animals.id'))
    born_on:Mapped[date]=mapped_column(Date)
    total_born:Mapped[int]=mapped_column(Integer)
    live_count:Mapped[int]=mapped_column(Integer)
    male_count:Mapped[int|None]=mapped_column(Integer)
    female_count:Mapped[int|None]=mapped_column(Integer)
    initial_weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(14,3))
    breed:Mapped[str|None]=mapped_column(String(100))
    characteristics:Mapped[str|None]=mapped_column(Text)
    notes:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LivestockIncubationSource(Base):
    __tablename__='v83_livestock_incubation_sources'
    __table_args__=(UniqueConstraint('organization_id','incubation_id',name='uq_v83_incubation_source'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    incubation_id:Mapped[int]=mapped_column(ForeignKey('v8_livestock_incubations.id'),index=True)
    breeding_id:Mapped[int|None]=mapped_column(ForeignKey('v8_livestock_breeding_records.id'),index=True)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
