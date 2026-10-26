"""V6 operational modules. Every query is organization-scoped and permission-checked.

These modules intentionally coexist with V5's fattening, sales and accounting records.
The organization (rather than a fattening batch) owns fields, poultry, gardens and machines.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import String, Text, Integer, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Session, Mapped, mapped_column
from database import Base, get_db, utcnow
from auth import audit
from modules.organizations.service import context, V5Ranch, licensed, permitted

# Canonical ORM classes are owned by their respective domains.
from modules.platform_admin.models import ModuleSetting
from modules.livestock.models import LivestockGroup, GeneralAnimal
from modules.gardening.models import GardenArea, GardenRecord
from modules.machinery.models import Machine, MachineRecord


router=APIRouter(prefix='/api/v6',tags=['V6 agriculture, livestock, gardens and machinery'])


class CropField(Base):
    __tablename__='v6_crop_fields'
    __table_args__=(UniqueConstraint('organization_id','ranch_id','name',name='uq_v6_field_org_ranch_name'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    name:Mapped[str]=mapped_column(String(150))
    area_ha:Mapped[Decimal]=mapped_column(Numeric(14,3))
    soil_type:Mapped[str|None]=mapped_column(String(120))
    irrigation:Mapped[str|None]=mapped_column(String(120))
    location:Mapped[str|None]=mapped_column(String(220))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class CropCycle(Base):
    __tablename__='v6_crop_cycles'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    field_id:Mapped[int]=mapped_column(ForeignKey('v6_crop_fields.id'),index=True)
    crop:Mapped[str]=mapped_column(String(140))
    variety:Mapped[str|None]=mapped_column(String(140))
    planted_area_ha:Mapped[Decimal]=mapped_column(Numeric(12,3))
    planting_date:Mapped[date]=mapped_column(Date)
    expected_harvest_date:Mapped[date|None]=mapped_column(Date)
    status:Mapped[str]=mapped_column(String(24),default='planned')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class CropRecord(Base):
    __tablename__='v6_crop_records'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    cycle_id:Mapped[int]=mapped_column(ForeignKey('v6_crop_cycles.id'),index=True)
    action:Mapped[str]=mapped_column(String(30))
    performed_on:Mapped[date]=mapped_column(Date)
    quantity:Mapped[Decimal|None]=mapped_column(Numeric(15,3))
    unit:Mapped[str|None]=mapped_column(String(35))
    notes:Mapped[str|None]=mapped_column(Text)
    cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    currency:Mapped[str]=mapped_column(String(8),default='TZS')
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)







MODULES=['fattening','livestock','crops','gardening','machinery','inventory','finance']
PERMISSION={'livestock':'livestock','crops':'crops','gardening':'gardening','machinery':'machinery'}

def scope(db,ctx,module,write=False):
    actor,org,m=ctx;licensed(db,org,write)
    module_rule=db.query(ModuleSetting).filter_by(organization_id=org.id,module=module).first()
    if module_rule and not module_rule.enabled:raise HTTPException(403,f'{module.title()} is not enabled in your subscription')
    if m.role not in ('org_admin','manager'):
        permitted(m,f'{module}.{"write" if write else "read"}')
    return actor,org,m

def linked(db,model,org,obj_id,message='Record'):
    row=db.query(model).filter_by(id=obj_id,organization_id=org.id).first()
    if not row:raise HTTPException(404,f'{message} not found in this organization')
    return row

def ranch(db,org,ranch_id):return linked(db,V5Ranch,org,ranch_id,'Ranch')

def rowdata(obj):
    out={}
    for c in obj.__table__.columns:
        v=getattr(obj,c.key)
        out[c.key]=v.isoformat() if isinstance(v,(date,datetime)) else float(v) if isinstance(v,Decimal) else v
    return out

def result(db,model,org):
    return {'items':[rowdata(r) for r in db.query(model).filter_by(organization_id=org.id).order_by(model.id.desc()).limit(500).all()]}

def saved(db,actor,model,obj,action):
    db.add(obj);db.flush();audit(db,actor.id,action,model.__tablename__,obj.id)
    out=rowdata(obj);db.commit();return {'item':out,'message':'Saved successfully'}

class FieldIn(BaseModel):
    ranch_id:int;name:str=Field(min_length=2,max_length=150);area_ha:Decimal=Field(gt=0)
    soil_type:str|None=None;irrigation:str|None=None;location:str|None=None
class CycleIn(BaseModel):
    field_id:int;crop:str=Field(min_length=2,max_length=140);variety:str|None=None
    planted_area_ha:Decimal=Field(gt=0);planting_date:date;expected_harvest_date:date|None=None
    status:Literal['planned','growing','harvested','cancelled']='planned'
    @model_validator(mode='after')
    def dates(self):
        if self.expected_harvest_date and self.expected_harvest_date<self.planting_date:raise ValueError('Harvest cannot precede planting')
        return self
class CropActivityIn(BaseModel):
    cycle_id:int;action:Literal['planting','irrigation','fertilizer','spraying','weeding','inspection','harvest']
    performed_on:date=Field(default_factory=date.today);quantity:Decimal|None=Field(default=None,gt=0)
    unit:str|None=None;notes:str|None=None;cost:Decimal=Field(default=0,ge=0);currency:str='TZS'
class GroupIn(BaseModel):
    ranch_id:int;name:str=Field(min_length=2,max_length=160);species:str=Field(min_length=2,max_length=80)
    purpose:str='general';head_count:int=Field(ge=0);location:str|None=None;notes:str|None=None
class GeneralAnimalIn(BaseModel):
    ranch_id:int;group_id:int|None=None;tag:str|None=Field(default=None,max_length=100);species:str=Field(min_length=2,max_length=80)
    breed:str|None=None;sex:Literal['male','female','unknown']|None=None;birth_date:date|None=None;origin:str|None=None
class GardenIn(BaseModel):
    ranch_id:int;name:str=Field(min_length=2,max_length=160);type:str='landscaping';area_m2:Decimal|None=Field(default=None,gt=0);notes:str|None=None
class GardenLogIn(BaseModel):
    area_id:int;action:Literal['watering','weeding','pruning','planting','landscaping','cleaning','inspection','other']
    performed_on:date=Field(default_factory=date.today);observations:str|None=None
class MachineIn(BaseModel):
    ranch_id:int;asset_code:str=Field(min_length=2,max_length=100);name:str=Field(min_length=2,max_length=180)
    category:str='machinery';model:str|None=None;serial_number:str|None=None;acquired_on:date|None=None
class MachineLogIn(BaseModel):
    machine_id:int;action:Literal['operation','maintenance','breakdown','fuel','repair','inspection']
    performed_on:date=Field(default_factory=date.today);meter_hours:Decimal|None=Field(default=None,ge=0)
    expense:Decimal=Field(default=0,ge=0);currency:str='TZS';notes:str|None=None

@router.get('/modules')
def modules(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;licensed(db,org,False)
    rules={r.module:r.enabled for r in db.query(ModuleSetting).filter_by(organization_id=org.id)}
    return {'items':[{'name':m,'enabled':rules.get(m,True)} for m in MODULES]}





@router.get('/overview')
def overview(db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=ctx;licensed(db,o,False)
    return {'organization':o.name,'fields':db.query(CropField).filter_by(organization_id=o.id).count(),
      'crop_cycles':db.query(CropCycle).filter_by(organization_id=o.id).count(),
      'livestock_groups':db.query(LivestockGroup).filter_by(organization_id=o.id).count(),
      'general_animals':db.query(GeneralAnimal).filter_by(organization_id=o.id).count(),
      'gardens':db.query(GardenArea).filter_by(organization_id=o.id).count(),
      'machinery':db.query(Machine).filter_by(organization_id=o.id).count()}


# Domain-owned database entities. Table names are preserved for existing installations.
class CropInput(Base):
    __tablename__='v61_crop_inputs'
    __table_args__=(UniqueConstraint('organization_id','reference',name='uq_v61_crop_input_ref'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    cycle_id:Mapped[int]=mapped_column(ForeignKey('v6_crop_cycles.id'),index=True)
    category:Mapped[str]=mapped_column(String(60))
    description:Mapped[str]=mapped_column(String(180))
    quantity:Mapped[Decimal]=mapped_column(Numeric(16,3))
    unit:Mapped[str]=mapped_column(String(30))
    unit_cost:Mapped[Decimal]=mapped_column(Numeric(18,4))
    labor_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    transport_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    total_cost:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(8))
    reference:Mapped[str]=mapped_column(String(100))
    performed_on:Mapped[date]=mapped_column(Date)
    note:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class CropSale(Base):
    __tablename__='v6_crop_sales'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    cycle_id:Mapped[int]=mapped_column(ForeignKey('v6_crop_cycles.id'),index=True)
    buyer:Mapped[str]=mapped_column(String(180))
    buyer_contact:Mapped[str|None]=mapped_column(String(120))
    quantity_kg:Mapped[Decimal]=mapped_column(Numeric(16,3))
    price_per_kg:Mapped[Decimal]=mapped_column(Numeric(18,2))
    gross:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(8))
    sale_date:Mapped[date]=mapped_column(Date)
    invoice_ref:Mapped[str|None]=mapped_column(String(120))
    notes:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

# === GHR_CROPS_V9_MODELS ===
# Additive tables: original V6 crop data remain untouched.
from sqlalchemy import JSON, CheckConstraint

class V9Project(Base):
    __tablename__='v9_crop_projects'
    __table_args__=(UniqueConstraint('organization_id','code',name='uq_v9_crop_project_code'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    name:Mapped[str]=mapped_column(String(160));code:Mapped[str]=mapped_column(String(64))
    category:Mapped[str]=mapped_column(String(60),default='commercial');objective:Mapped[str|None]=mapped_column(Text)
    method:Mapped[str]=mapped_column(String(60),default='open_field');season:Mapped[str|None]=mapped_column(String(80))
    start_date:Mapped[date]=mapped_column(Date);end_date:Mapped[date|None]=mapped_column(Date)
    manager_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    currency:Mapped[str]=mapped_column(String(3),default='USD');planned_budget:Mapped[Decimal|None]=mapped_column(Numeric(18,2))
    target_yield_kg:Mapped[Decimal|None]=mapped_column(Numeric(18,3));expected_price:Mapped[Decimal|None]=mapped_column(Numeric(18,4))
    status:Mapped[str]=mapped_column(String(24),default='planned');notes:Mapped[str|None]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Unit(Base):
    __tablename__='v9_crop_units'
    __table_args__=(UniqueConstraint('organization_id','field_id','name',name='uq_v9_crop_unit'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    field_id:Mapped[int]=mapped_column(ForeignKey('v6_crop_fields.id'),index=True)
    name:Mapped[str]=mapped_column(String(120));kind:Mapped[str]=mapped_column(String(60),default='block')
    area_ha:Mapped[Decimal]=mapped_column(Numeric(14,4));capacity:Mapped[int|None]=mapped_column(Integer)
    latitude:Mapped[Decimal|None]=mapped_column(Numeric(10,6));longitude:Mapped[Decimal|None]=mapped_column(Numeric(10,6))
    irrigation_system:Mapped[str|None]=mapped_column(String(100));status:Mapped[str]=mapped_column(String(24),default='available')
    notes:Mapped[str|None]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Variety(Base):
    __tablename__='v9_crop_varieties'
    __table_args__=(UniqueConstraint('organization_id','name','variety',name='uq_v9_crop_variety'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    name:Mapped[str]=mapped_column(String(150));scientific_name:Mapped[str|None]=mapped_column(String(180))
    family:Mapped[str|None]=mapped_column(String(120));category:Mapped[str]=mapped_column(String(70))
    variety:Mapped[str]=mapped_column(String(150));life_cycle:Mapped[str]=mapped_column(String(30))
    days_to_maturity:Mapped[int|None]=mapped_column(Integer);growing_method:Mapped[str|None]=mapped_column(String(120))
    source:Mapped[str|None]=mapped_column(String(180));seed_certification:Mapped[str|None]=mapped_column(String(160))
    notes:Mapped[str|None]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Cycle(Base):
    __tablename__='v9_crop_cycles'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    unit_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_units.id'),index=True)
    variety_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_varieties.id'),index=True)
    planted_area_ha:Mapped[Decimal]=mapped_column(Numeric(14,4));planted_on:Mapped[date]=mapped_column(Date)
    expected_harvest:Mapped[date|None]=mapped_column(Date);method:Mapped[str]=mapped_column(String(60),default='direct_seed')
    status:Mapped[str]=mapped_column(String(30),default='planned');target_yield_kg:Mapped[Decimal|None]=mapped_column(Numeric(18,3))
    notes:Mapped[str|None]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Record(Base):
    __tablename__='v9_crop_records'
    __table_args__=(UniqueConstraint('organization_id','section','reference',name='uq_v9_crop_record_reference'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    cycle_id:Mapped[int|None]=mapped_column(ForeignKey('v9_crop_cycles.id'),index=True)
    unit_id:Mapped[int|None]=mapped_column(ForeignKey('v9_crop_units.id'),index=True)
    section:Mapped[str]=mapped_column(String(40),index=True)
    performed_on:Mapped[date]=mapped_column(Date,index=True)
    title:Mapped[str]=mapped_column(String(160));quantity:Mapped[Decimal|None]=mapped_column(Numeric(18,4))
    unit:Mapped[str|None]=mapped_column(String(30));unit_cost:Mapped[Decimal|None]=mapped_column(Numeric(18,4))
    other_cost:Mapped[Decimal|None]=mapped_column(Numeric(18,2));currency:Mapped[str|None]=mapped_column(String(3))
    reference:Mapped[str|None]=mapped_column(String(100));notes:Mapped[str|None]=mapped_column(Text)
    data:Mapped[dict]=mapped_column(JSON,default=dict);recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Budget(Base):
    __tablename__='v9_crop_budgets'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    cycle_id:Mapped[int|None]=mapped_column(ForeignKey('v9_crop_cycles.id'))
    category:Mapped[str]=mapped_column(String(80));description:Mapped[str]=mapped_column(String(220))
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,4));unit:Mapped[str]=mapped_column(String(30))
    unit_cost:Mapped[Decimal]=mapped_column(Numeric(18,4));amount:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(3));version:Mapped[int]=mapped_column(Integer,default=1)
    status:Mapped[str]=mapped_column(String(24),default='draft');planned_on:Mapped[date|None]=mapped_column(Date)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Routine(Base):
    __tablename__='v9_crop_routines'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    cycle_id:Mapped[int|None]=mapped_column(ForeignKey('v9_crop_cycles.id'))
    unit_id:Mapped[int|None]=mapped_column(ForeignKey('v9_crop_units.id'))
    title:Mapped[str]=mapped_column(String(180));instructions:Mapped[str|None]=mapped_column(Text)
    frequency:Mapped[str]=mapped_column(String(30),default='daily');weekdays:Mapped[list]=mapped_column(JSON,default=list)
    shift:Mapped[str]=mapped_column(String(30),default='morning');start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date|None]=mapped_column(Date);assigned_to:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    planned_quantity:Mapped[Decimal|None]=mapped_column(Numeric(18,3));unit:Mapped[str|None]=mapped_column(String(40))
    estimated_minutes:Mapped[int|None]=mapped_column(Integer);enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Completion(Base):
    __tablename__='v9_crop_completions'
    __table_args__=(UniqueConstraint('organization_id','routine_id','day',name='uq_v9_crop_daily_check'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    routine_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_routines.id'),index=True)
    day:Mapped[date]=mapped_column(Date);status:Mapped[str]=mapped_column(String(25))
    notes:Mapped[str|None]=mapped_column(Text);actual_quantity:Mapped[Decimal|None]=mapped_column(Numeric(18,3))
    amount:Mapped[Decimal|None]=mapped_column(Numeric(18,2));currency:Mapped[str|None]=mapped_column(String(3))
    completed_by:Mapped[int]=mapped_column(ForeignKey('users.id'));completed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Trial(Base):
    __tablename__='v9_crop_trials'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    cycle_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_cycles.id'))
    title:Mapped[str]=mapped_column(String(180));question:Mapped[str]=mapped_column(Text)
    hypothesis:Mapped[str|None]=mapped_column(Text);design:Mapped[str]=mapped_column(String(40))
    replications:Mapped[int]=mapped_column(Integer);start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date|None]=mapped_column(Date);status:Mapped[str]=mapped_column(String(24))
    notes:Mapped[str|None]=mapped_column(Text);created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Plot(Base):
    __tablename__='v9_crop_trial_plots'
    __table_args__=(UniqueConstraint('trial_id','code',name='uq_v9_plot_code'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    trial_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_trials.id'),index=True)
    unit_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_units.id'))
    code:Mapped[str]=mapped_column(String(60));treatment:Mapped[str]=mapped_column(String(150))
    replicate:Mapped[int]=mapped_column(Integer);area_ha:Mapped[Decimal]=mapped_column(Numeric(14,4))
    randomization_order:Mapped[int|None]=mapped_column(Integer);is_control:Mapped[bool]=mapped_column(Boolean,default=False)

class V9Harvest(Base):
    __tablename__='v9_crop_harvest_lots'
    __table_args__=(UniqueConstraint('organization_id','batch_ref',name='uq_v9_harvest_batch'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    cycle_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_cycles.id'))
    unit_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_units.id'))
    harvested_on:Mapped[date]=mapped_column(Date);pass_number:Mapped[int]=mapped_column(Integer,default=1)
    gross_kg:Mapped[Decimal]=mapped_column(Numeric(18,3));tare_kg:Mapped[Decimal]=mapped_column(Numeric(18,3))
    rejected_kg:Mapped[Decimal]=mapped_column(Numeric(18,3));grade:Mapped[str]=mapped_column(String(80))
    marketable_kg:Mapped[Decimal]=mapped_column(Numeric(18,3));available_kg:Mapped[Decimal]=mapped_column(Numeric(18,3))
    quality:Mapped[dict]=mapped_column(JSON,default=dict);batch_ref:Mapped[str]=mapped_column(String(100))
    cost:Mapped[Decimal|None]=mapped_column(Numeric(18,2));currency:Mapped[str|None]=mapped_column(String(3))
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Stock(Base):
    __tablename__='v9_crop_stock_movements'
    __table_args__=(UniqueConstraint('organization_id','reference',name='uq_v9_crop_stock_ref'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    lot_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_harvest_lots.id'),index=True)
    action:Mapped[str]=mapped_column(String(30));quantity_kg:Mapped[Decimal]=mapped_column(Numeric(18,3))
    reference:Mapped[str]=mapped_column(String(100));notes:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class V9Sale(Base):
    __tablename__='v9_crop_sales'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_projects.id'),index=True)
    lot_id:Mapped[int]=mapped_column(ForeignKey('v9_crop_harvest_lots.id'),index=True)
    buyer:Mapped[str]=mapped_column(String(180));quantity_kg:Mapped[Decimal]=mapped_column(Numeric(18,3))
    price_per_kg:Mapped[Decimal]=mapped_column(Numeric(18,4));gross:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(3));sold_on:Mapped[date]=mapped_column(Date)
    delivery_ref:Mapped[str|None]=mapped_column(String(120));selling_cost:Mapped[Decimal|None]=mapped_column(Numeric(18,2))
    notes:Mapped[str|None]=mapped_column(Text);recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
# === END_GHR_CROPS_V9_MODELS ===
