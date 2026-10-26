"""Tenant-scoped operational V5 modules. No legacy V4 record is silently reclassified."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow

from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, ForeignKey, DateTime, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, get_db, utcnow
from modules.organizations.service import context, licensed, permitted, V5Batch, V5Ranch, V5Routine
from auth import audit

# Canonical ORM classes are owned by their respective domains.
from modules.inventory.models import StockItem, StockMovement, FeedItemNutrients
from modules.finance.models import FinanceEntry
from modules.employees.models import Task


router=APIRouter(prefix='/api/v5', tags=['v5-operations'])
class V5Animal(Base):
    __tablename__='v5_animals';__table_args__=(UniqueConstraint('organization_id','tag'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    batch_id:Mapped[int]=mapped_column(ForeignKey('v5_batches.id'),index=True)
    tag:Mapped[str]=mapped_column(String(100))
    species:Mapped[str]=mapped_column(String(50),default='cattle')
    sex:Mapped[str|None]=mapped_column(String(20))
    breed:Mapped[str|None]=mapped_column(String(100))
    color:Mapped[str|None]=mapped_column(String(100))
    origin:Mapped[str|None]=mapped_column(String(180))
    age_months:Mapped[int|None]=mapped_column(Integer)
    date_of_birth:Mapped[date|None]=mapped_column(__import__('sqlalchemy').Date)
    supplier_name:Mapped[str|None]=mapped_column(String(180))
    supplier_contact:Mapped[str|None]=mapped_column(String(120))
    arrival_date:Mapped[date|None]=mapped_column(__import__('sqlalchemy').Date)
    notes:Mapped[str|None]=mapped_column(Text)
    entry_weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(12,3))
    current_weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(12,3))
    purchase_cost:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0)
    purchase_currency:Mapped[str]=mapped_column(String(10),default='TZS')
    status:Mapped[str]=mapped_column(String(30),default='active')
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)
class Ration(Base):
    __tablename__='v5_rations'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    name:Mapped[str]=mapped_column(String(150))
    ingredients:Mapped[str]=mapped_column(Text) # serialized validated list
    kg_per_head_day:Mapped[Decimal|None]=mapped_column(Numeric(12,3))
    batch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_batches.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v5_animals.id'))
    feed_type:Mapped[str]=mapped_column(String(40),default='maintenance')
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)
class Production(Base):
    __tablename__='v5_mix_production'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ration_id:Mapped[int]=mapped_column(ForeignKey('v5_rations.id'))
    finished_item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'))
    quantity_kg:Mapped[Decimal]=mapped_column(Numeric(16,3))
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)

class AnimalIn(BaseModel):
    batch_id:int
    tag:str|None=Field(default=None,max_length=100)
    species:str=Field(default='cattle',min_length=2,max_length=50)
    sex:Literal['male','female','unknown']|None=None
    breed:str|None=None
    color:str|None=None
    origin:str|None=None
    age_months:int|None=Field(default=None,ge=0,le=600)
    date_of_birth:date|None=None
    supplier_name:str|None=None
    supplier_contact:str|None=None
    arrival_date:date|None=None
    notes:str|None=None
    entry_weight_kg:Decimal|None=Field(default=None,gt=0)
    purchase_cost:Decimal=Field(default=Decimal('0'),ge=0)
    purchase_currency:Literal['TZS','USD','KES','EUR']='TZS'

class WeightIn(BaseModel):
    weight_kg:Decimal=Field(gt=0)
    notes:str|None=None

class WeightObservation(Base):
    __tablename__='v5_weight_observations'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    animal_id:Mapped[int]=mapped_column(ForeignKey('v5_animals.id'),index=True,nullable=False)
    weight_kg:Mapped[Decimal]=mapped_column(Numeric(12,3),nullable=False)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    notes:Mapped[str|None]=mapped_column(Text)
    routine_id:Mapped[int|None]=mapped_column(ForeignKey('v5_routine_entries.id'))
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)

class ItemIn(BaseModel):
    name:str=Field(min_length=2,max_length=180);unit:str='kg';category:str='feed';cost_per_unit:Decimal=Field(default=Decimal('0'),ge=0)
    currency:str='TZS';reorder_level:Decimal=Field(default=Decimal('0'),ge=0)
class MovementIn(BaseModel):
    item_id:int;direction:Literal['in','out','adjustment_in','adjustment_out'];quantity:Decimal=Field(gt=0)
    unit_cost:Decimal=Field(default=Decimal("0"),ge=0);reference:str=Field(min_length=5,max_length=100);note:str|None=None
class Ingredient(BaseModel):
    item_id:int;percent:Decimal=Field(gt=0,le=100)
class RationIn(BaseModel):
    name:str=Field(min_length=2);ingredients:list[Ingredient]=Field(min_length=1)
    kg_per_head_day:Decimal|None=Field(default=None,gt=0);batch_id:int|None=None
    animal_id:int|None=None
    feed_type:Literal['starter','grower','finisher','maintenance','lactation','other']='starter'
class ProductionIn(BaseModel):
    ration_id:int;finished_item_id:int;quantity_kg:Decimal=Field(gt=0)
class FinanceIn(BaseModel):
    batch_id:int|None=None;kind:Literal['cost','revenue'];category:str=Field(min_length=2)
    amount:Decimal=Field(gt=0);currency:str='TZS';note:str|None=None
class TaskIn(BaseModel):
    category:Literal['feeding','watering','cleaning','dipping','medication','weighing','health','movement','inspection','maintenance','other','stock_receive','stock_out','finance','planting','harvest','crop','gardening','machinery']
    title:str=Field(min_length=2);assigned_to:int|None=None;batch_id:int|None=None;pen_id:int|None=None
    frequency:Literal['daily','weekly','monthly','once']='daily';shift:str='Morning';due_date:date=Field(default_factory=date.today)

def permission(ctx,db,perm,write=False):
    user,org,m=ctx;licensed(db,org,write)
    if m.role!='org_admin':permitted(m,perm)
    return user,org,m

def batch_check(db,org,bid):
    if bid is not None and not db.query(V5Batch).filter_by(id=bid,organization_id=org.id).first():raise HTTPException(404,'Batch not found')
def item_check(db,org,item_id):
    obj=db.query(StockItem).filter_by(id=item_id,organization_id=org.id).first()
    if not obj:raise HTTPException(404,'Store item not found')
    return obj

def balance(db,org,item_id):
    moves=db.query(StockMovement).filter_by(organization_id=org.id,item_id=item_id).all()
    return sum((x.quantity if x.direction in ('in','adjustment_in') else -x.quantity for x in moves),Decimal('0'))

def animal_data(a):
    return dict(id=a.id,batch_id=a.batch_id,tag=a.tag,species=a.species,sex=a.sex,breed=a.breed,color=a.color,
        origin=a.origin,age_months=a.age_months,date_of_birth=a.date_of_birth.isoformat() if a.date_of_birth else None,
        supplier_name=a.supplier_name,supplier_contact=a.supplier_contact,arrival_date=a.arrival_date.isoformat() if a.arrival_date else None,
        notes=a.notes,entry_weight_kg=float(a.entry_weight_kg) if a.entry_weight_kg is not None else None,
        current_weight_kg=float(a.current_weight_kg) if a.current_weight_kg is not None else None,
        purchase_cost=float(a.purchase_cost),purchase_currency=a.purchase_currency or 'TZS',status=a.status)

@router.get('/animals')
def animals(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'animals.read');return {'items':[animal_data(a) for a in db.query(V5Animal).filter_by(organization_id=org.id).order_by(V5Animal.id.desc()).limit(2000)]}
@router.post('/animals',status_code=201)
def add_animal(p:AnimalIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'animals.manage',True)
    if not p.tag or not p.tag.strip():
        import secrets
        p=p.model_copy(update={'tag':f'AN-{org.id}-{secrets.token_hex(5).upper()}'})
    if p.date_of_birth and p.age_months is not None: raise HTTPException(422,'Enter age or date of birth, not both')
    if p.date_of_birth and p.date_of_birth>date.today():raise HTTPException(422,'Date of birth cannot be in future')
    if p.arrival_date and p.arrival_date>date.today():raise HTTPException(422,'Arrival date cannot be in future')
    batch=db.query(V5Batch).filter_by(id=p.batch_id,organization_id=org.id).with_for_update().first()
    if not batch: raise HTTPException(404,'Batch not found')
    if batch.project_id is None:raise HTTPException(409,'Assign this older batch to a project before registering new animals')
    if batch.status=='completed':raise HTTPException(409,'Cannot add animals to completed batch')
    count=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=batch.id,status='active').count()
    if batch.capacity is not None and count>=batch.capacity:raise HTTPException(409,f'Batch is full ({count}/{batch.capacity}). Choose another batch.')
    if db.query(V5Animal).filter_by(organization_id=org.id,tag=p.tag).first():raise HTTPException(409,'Tag already exists')
    a=V5Animal(organization_id=org.id,**p.model_dump(),current_weight_kg=p.entry_weight_kg)
    db.add(a);db.flush();audit(db,user.id,'animal_create','v5_animal',a.id,p.tag)
    if p.purchase_cost>0:
        db.add(FinanceEntry(organization_id=org.id,batch_id=batch.id,animal_id=a.id,kind='cost',category='Animal procurement',
            amount=p.purchase_cost,currency=p.purchase_currency,created_by=user.id,source_type='animal_purchase',source_id=a.id,
            note=f'Animal {a.tag}; supplier {p.supplier_name or "not provided"}; origin {p.origin or "not provided"}'))
    if batch.capacity:
        from modules.fattening.service import alert
        if count<batch.capacity<=count+1:
            alert(db,org,'capacity','Batch is full',f'{batch.name}: {count+1}/{batch.capacity} spaces occupied')
        elif count / batch.capacity<0.9<=(count+1) / batch.capacity:
            alert(db,org,'capacity','Batch nearly full',f'{batch.name}: {count+1}/{batch.capacity} spaces occupied')
    db.commit();return animal_data(a)

@router.post('/animals/{animal_id}/weight')
def animal_weight(animal_id:int,p:WeightIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'animals.manage',True)
    a=db.query(V5Animal).filter_by(id=animal_id,organization_id=org.id).with_for_update().first()
    if not a:raise HTTPException(404,'V5Animal not found')
    if a.status!='active':raise HTTPException(409,'Weight can only be recorded for active animals')
    from modules.fattening.service import alert
    from modules.fattening.schemas import period_limits
    from datetime import datetime,time
    start,end,_=period_limits('daily',date.today())
    if db.query(WeightObservation).filter(WeightObservation.organization_id==org.id,WeightObservation.animal_id==a.id,WeightObservation.created_at>=datetime.combine(start,time.min),WeightObservation.created_at<datetime.combine(end,time.min)).first():
        raise HTTPException(409,'Weight already recorded for this animal today. Use Edit weight.')
    old_weight=a.current_weight_kg
    a.current_weight_kg=p.weight_kg
    if old_weight is not None and p.weight_kg<old_weight:
        alert(db,org,'weight','Weight decreased',f'{a.tag}: {old_weight} kg to {p.weight_kg} kg. Verify the measurement and review husbandry and health.')
    obs=WeightObservation(organization_id=org.id,animal_id=a.id,weight_kg=p.weight_kg,recorded_by=user.id,notes=p.notes)
    db.add(obs);db.flush()
    audit(db,user.id,'animal_weight','v5_weight_observation',obs.id,f'{a.tag}: {p.weight_kg} kg')
    db.commit();return {**animal_data(a),'weight_record_id':obs.id,'message':'Animal weight saved (kg)'}

@router.get('/rations')
def rations(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'rations.read');return {'items':[dict(id=x.id,name=x.name,feed_type=x.feed_type,ingredients=__import__('json').loads(x.ingredients),batch_id=x.batch_id,animal_id=x.animal_id,kg_per_head_day=float(x.kg_per_head_day) if x.kg_per_head_day else None) for x in db.query(Ration).filter_by(organization_id=org.id)]}
@router.post('/rations',status_code=201)
def add_ration(p:RationIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True);batch_check(db,org,p.batch_id)
    if p.animal_id is not None and not db.query(V5Animal).filter_by(id=p.animal_id,organization_id=org.id,status='active').first():raise HTTPException(404,'Animal not found')
    if abs(sum((x.percent for x in p.ingredients),Decimal(0))-Decimal(100))>Decimal('0.01'):raise HTTPException(422,'Ingredient percentages must total 100')
    if len({x.item_id for x in p.ingredients})!=len(p.ingredients):raise HTTPException(422,'Duplicate ingredient')
    if db.query(Ration).filter(Ration.organization_id==org.id,func.lower(Ration.name)==p.name.strip().lower()).first():
        raise HTTPException(409,'A feed mix with this name already exists. Use a different name.')
    for x in p.ingredients:
        item=item_check(db,org,x.item_id)
        if item.category.lower()!='feed' or item.unit.lower()!='kg':raise HTTPException(422,'Recipe ingredients must be feed items measured in kg')
    obj=Ration(organization_id=org.id,name=p.name,ingredients=__import__('json').dumps([{'item_id':x.item_id,'percent':str(x.percent)} for x in p.ingredients]),kg_per_head_day=p.kg_per_head_day,batch_id=p.batch_id,animal_id=p.animal_id,feed_type=p.feed_type)
    db.add(obj);db.flush()
    from modules.inventory.service import FeedMixProduct
    mix_name=f'Mix: {p.name}'
    product=db.query(StockItem).filter_by(organization_id=org.id,name=mix_name).first()
    if not product:
        product=StockItem(organization_id=org.id,name=mix_name,unit='kg',category='feed',cost_per_unit=0,currency='TZS',reorder_level=0)
        db.add(product);db.flush()
    db.add(FeedMixProduct(ration_id=obj.id,organization_id=org.id,item_id=product.id))
    audit(db,user.id,'ration_create','v5_ration',obj.id,p.name);db.commit()
    return {'id':obj.id,'finished_item_id':product.id,'message':'Feed mix recipe and catalog item saved. Produce or receive stock before feeding.'}

# These are operator-entered composition specifications; no unsupported laboratory inference.
NUTRIENT_LABELS = {'crude_protein':'Crude protein','calcium':'Calcium','phosphorus':'Phosphorus',
    'crude_fiber':'Crude fibre','crude_fat':'Crude fat','moisture':'Moisture','ash':'Ash',
    'sodium':'Sodium','magnesium':'Magnesium','potassium':'Potassium','salt':'Salt',
    'ndf':'Neutral detergent fibre','adf':'Acid detergent fibre'}

class FeedNutrition(Base):
    __tablename__='v5_feed_nutrition'
    __table_args__=(UniqueConstraint('organization_id','ration_id',name='uq_v5_nutrition_ration'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ration_id:Mapped[int]=mapped_column(ForeignKey('v5_rations.id'))
    nutrients:Mapped[str]=mapped_column(Text,nullable=False,default='{}')
    notes:Mapped[str|None]=mapped_column(Text)
    updated_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)

class NutritionIn(BaseModel):
    nutrients:dict[str,Decimal]=Field(min_length=1,max_length=25)
    notes:str|None=None

@router.get('/feed/nutrients/options')
def nutrient_options(db:Session=Depends(get_db),ctx=Depends(context)):
    permission(ctx,db,'rations.read')
    return {'items':[{'id':k,'name':v,'unit':'%'} for k,v in NUTRIENT_LABELS.items()]}

@router.get('/rations/{ration_id}/nutrients')
def view_nutrients(ration_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'rations.read')
    if not db.query(Ration).filter_by(id=ration_id,organization_id=org.id).first():raise HTTPException(404,'Mix not found')
    profile=db.query(FeedNutrition).filter_by(organization_id=org.id,ration_id=ration_id).first()
    return {'ration_id':ration_id,'nutrients':__import__('json').loads(profile.nutrients) if profile else {},'notes':profile.notes if profile else None}

@router.put('/rations/{ration_id}/nutrients')
def save_nutrients(ration_id:int,p:NutritionIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True)
    if not db.query(Ration).filter_by(id=ration_id,organization_id=org.id).first():raise HTTPException(404,'Mix not found')
    if set(p.nutrients)-set(NUTRIENT_LABELS):raise HTTPException(422,'Unknown nutrient; select from the supported list')
    if any(v<0 or v>100 or not v.is_finite() for v in p.nutrients.values()):raise HTTPException(422,'Composition values must be between 0% and 100%')
    profile=db.query(FeedNutrition).filter_by(organization_id=org.id,ration_id=ration_id).first()
    if profile is None:
        profile=FeedNutrition(organization_id=org.id,ration_id=ration_id,nutrients='{}');db.add(profile)
    profile.nutrients=__import__('json').dumps({k:float(v) for k,v in p.nutrients.items()})
    profile.notes=p.notes
    audit(db,user.id,'feed_nutrition_update','v5_ration',ration_id,'Nutrition values manually recorded')
    db.commit();return {'ration_id':ration_id,'nutrients':__import__('json').loads(profile.nutrients),'message':'Feed nutrient profile saved'}





# Break-even is derived from the purchase record and related posted expenses.
# No editable proposal or extra break-even database table is needed.
# Existing historical proposal tables, if present, are not dropped by this patch.

# Domain-owned database entities. Table names are preserved for existing installations.
class V5Project(Base):
    __tablename__='v5_projects'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    ranch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_ranches.id'))
    name:Mapped[str]=mapped_column(String(180),nullable=False)
    code:Mapped[str|None]=mapped_column(String(60))
    description:Mapped[str|None]=mapped_column(Text)
    objective:Mapped[str|None]=mapped_column(Text)
    livestock_type:Mapped[str|None]=mapped_column(String(70))
    start_date:Mapped[date]=mapped_column(Date,nullable=False)
    end_date:Mapped[date|None]=mapped_column(Date)
    budget:Mapped[Decimal|None]=mapped_column(Numeric(18,2))
    manager_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    target_animals:Mapped[int|None]=mapped_column(Integer)
    target_weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(12,3))
    currency:Mapped[str]=mapped_column(String(10),default='TZS')
    status:Mapped[str]=mapped_column(String(24),default='planned')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)


class FeedAssignment(Base):
    __tablename__='v5_feed_assignments'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ration_id:Mapped[int]=mapped_column(ForeignKey('v5_rations.id'))
    batch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_batches.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v5_animals.id'))
    start_date:Mapped[date]=mapped_column(Date,nullable=False)
    end_date:Mapped[date|None]=mapped_column(Date)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class FeedPlan(Base):
    __tablename__='v5_feed_plans'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ration_id:Mapped[int]=mapped_column(ForeignKey('v5_rations.id'))
    batch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_batches.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v5_animals.id'))
    kg_per_head_day:Mapped[Decimal]=mapped_column(Numeric(12,3))
    shift:Mapped[str]=mapped_column(String(30),default='Any')
    frequency:Mapped[str]=mapped_column(String(20),default='daily')
    start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date|None]=mapped_column(Date)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class FeedingLine(Base):
    __tablename__='v5_feeding_lines'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    routine_id:Mapped[int]=mapped_column(ForeignKey('v5_routine_entries.id'),index=True)
    item_id:Mapped[int|None]=mapped_column(ForeignKey('v5_stock_items.id'))
    ration_id:Mapped[int|None]=mapped_column(ForeignKey('v5_rations.id'))
    name:Mapped[str]=mapped_column(String(180))
    quantity_kg:Mapped[Decimal]=mapped_column(Numeric(14,3))


class Pen(Base):
    __tablename__='v5_pens'
    __table_args__=(UniqueConstraint('organization_id','batch_id','name',name='uq_v5_pen_batch_name'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    batch_id:Mapped[int]=mapped_column(ForeignKey('v5_batches.id'),index=True,nullable=False)
    name:Mapped[str]=mapped_column(String(120),nullable=False)
    description:Mapped[str|None]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='active',nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class PeriodClaim(Base):
    __tablename__='v5_routine_period_claims'
    __table_args__=(UniqueConstraint('organization_id','category','target','period_key',name='uq_v5_period_claim'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    category:Mapped[str]=mapped_column(String(40),nullable=False)
    target:Mapped[str]=mapped_column(String(90),nullable=False)
    period_key:Mapped[str]=mapped_column(String(40),nullable=False)
    entry_id:Mapped[int|None]=mapped_column(ForeignKey('v5_routine_entries.id'))
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class AnimalSale(Base):
    __tablename__='v5_animal_sales'
    __table_args__=(
        Index('uq_v5_animal_active_sale','organization_id','animal_id',unique=True,
              postgresql_where=text("status = 'completed'"),
              sqlite_where=text("status = 'completed'")),
    )
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    animal_id:Mapped[int]=mapped_column(ForeignKey('v5_animals.id'),index=True,nullable=False)
    batch_id:Mapped[int]=mapped_column(ForeignKey('v5_batches.id'),index=True,nullable=False)
    sale_date:Mapped[date]=mapped_column(Date,nullable=False)
    buyer_name:Mapped[str]=mapped_column(String(180),nullable=False)
    buyer_contact:Mapped[str|None]=mapped_column(String(120))
    reason:Mapped[str]=mapped_column(String(250),nullable=False)
    price_basis:Mapped[str]=mapped_column(String(20),nullable=False)
    price_per_unit:Mapped[Decimal]=mapped_column(Numeric(18,4),nullable=False)
    weight_kg:Mapped[Decimal|None]=mapped_column(Numeric(14,3))
    gross_amount:Mapped[Decimal]=mapped_column(Numeric(18,2),nullable=False)
    transport_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),nullable=False,default=0)
    commission_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),nullable=False,default=0)
    other_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),nullable=False,default=0)
    currency:Mapped[str]=mapped_column(String(10),nullable=False)
    invoice_ref:Mapped[str|None]=mapped_column(String(120))
    notes:Mapped[str|None]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='completed',nullable=False)
    void_reason:Mapped[str|None]=mapped_column(Text)
    voided_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    voided_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class MixReferenceAmount(Base):
    __tablename__='v61_mix_reference_amounts'
    __table_args__=(UniqueConstraint('organization_id','ration_id','item_id',name='uq_v61_mix_ingredient'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ration_id:Mapped[int]=mapped_column(ForeignKey('v5_rations.id'),index=True)
    item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'))
    quantity_kg:Mapped[Decimal]=mapped_column(Numeric(18,3))



# V7.6: domain-owned project business plans and immutable audit snapshots.
# These are additive tables, created by the existing Base.metadata.create_all on startup.
class FatteningProjectPlan(Base):
    __tablename__='fattening_project_plans'
    __table_args__=(UniqueConstraint('organization_id','project_id',name='uq_fattening_plan_tenant_project'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    project_id:Mapped[int]=mapped_column(ForeignKey('v5_projects.id'),index=True,nullable=False)
    version:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    status:Mapped[str]=mapped_column(String(20),default='draft',nullable=False)
    plan_json:Mapped[str]=mapped_column(Text,nullable=False,default='{}')
    prepared_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)

class FatteningPlanHistory(Base):
    __tablename__='fattening_project_plan_history'
    __table_args__=(UniqueConstraint('organization_id','project_id','version',name='uq_fattening_plan_history_version'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    project_id:Mapped[int]=mapped_column(ForeignKey('v5_projects.id'),index=True,nullable=False)
    version:Mapped[int]=mapped_column(Integer,nullable=False)
    status:Mapped[str]=mapped_column(String(20),nullable=False)
    plan_json:Mapped[str]=mapped_column(Text,nullable=False)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class FatteningSaleCostSnapshot(Base):
    __tablename__='fattening_sale_cost_snapshots'
    __table_args__=(UniqueConstraint('organization_id','sale_id',name='uq_fattening_sale_cost_snapshot'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    sale_id:Mapped[int]=mapped_column(ForeignKey('v5_animal_sales.id'),nullable=False,index=True)
    project_id:Mapped[int|None]=mapped_column(ForeignKey('v5_projects.id'))
    currency:Mapped[str]=mapped_column(String(10),nullable=False)
    cost_snapshot_json:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
