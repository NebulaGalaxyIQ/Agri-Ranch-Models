"""V5.5 pen management, occurrence locking and audited correction endpoints.

One authoritative occurrence per relevant period prevents two workers from submitting
identical work. Changes to posted observations are amendments, never deletes.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Integer, String, ForeignKey, DateTime, Date, UniqueConstraint, Text, func
from sqlalchemy.orm import mapped_column, Mapped, Session
from sqlalchemy.exc import IntegrityError
from database import Base, get_db, utcnow
from modules.organizations.service import context, licensed, permitted, V5Batch, V5Routine
from modules.fattening.models import V5Animal, WeightObservation, Task
from auth import audit

# Canonical ORM classes are owned by their respective domains.
from modules.fattening.models import Pen, PeriodClaim


router=APIRouter(prefix='/api/v5',tags=['v5-pens-and-safe-routines'])



class PenIn(BaseModel):
    batch_id:int
    name:str=Field(min_length=1,max_length=120)
    description:str|None=None

class PenEdit(BaseModel):
    name:str|None=Field(default=None,min_length=1,max_length=120)
    description:str|None=None
    status:Literal['active','inactive']|None=None


def serialize_pen(p,b=None):
    return {'id':p.id,'organization_id':p.organization_id,'batch_id':p.batch_id,
            'batch_name':b.name if b else None,'name':p.name,'description':p.description,
            'status':p.status}

@router.get('/pens')
def get_pens(batch_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;licensed(db,org,False)
    if m.role not in ('org_admin','manager'):
        permitted(m,'routine.read')
    q=db.query(Pen).filter_by(organization_id=org.id)
    if batch_id is not None:q=q.filter(Pen.batch_id==batch_id)
    batches={b.id:b for b in db.query(V5Batch).filter_by(organization_id=org.id).all()}
    return {'items':[serialize_pen(p,batches.get(p.batch_id)) for p in q.order_by(Pen.batch_id,Pen.name).all()]}

@router.post('/pens',status_code=201)
def create_pen(p:PenIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    if m.role!='org_admin':permitted(m,'ranch.manage')
    batch=db.query(V5Batch).filter_by(id=p.batch_id,organization_id=org.id).first()
    if not batch:raise HTTPException(404,'Select an existing batch first')
    if not batch.project_id:raise HTTPException(409,'Connect this batch to a project before creating a pen')
    if db.query(Pen).filter(Pen.organization_id==org.id,Pen.batch_id==batch.id,func.lower(Pen.name)==p.name.strip().lower()).first():
        raise HTTPException(409,'A pen with this name already exists in the batch')
    obj=Pen(organization_id=org.id,batch_id=batch.id,name=p.name.strip(),description=p.description)
    db.add(obj);db.flush();audit(db,user.id,'pen_create','v5_pen',obj.id,obj.name);db.commit()
    return {**serialize_pen(obj,batch),'message':'Pen created successfully'}

@router.patch('/pens/{pen_id}')
def edit_pen(pen_id:int,p:PenEdit,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    if m.role!='org_admin':permitted(m,'ranch.manage')
    obj=db.query(Pen).filter_by(id=pen_id,organization_id=org.id).first()
    if not obj:raise HTTPException(404,'Pen not found')
    before=(obj.name,obj.status,obj.description)
    if p.name is not None:
        duplicate=db.query(Pen).filter(Pen.organization_id==org.id,Pen.batch_id==obj.batch_id,
                                       func.lower(Pen.name)==p.name.strip().lower(),Pen.id!=obj.id).first()
        if duplicate:raise HTTPException(409,'Another pen with this name already exists')
        obj.name=p.name.strip()
    if 'description' in p.model_fields_set:obj.description=p.description
    if p.status is not None:obj.status=p.status
    audit(db,user.id,'pen_update','v5_pen',obj.id,f'{before} -> {(obj.name,obj.status,obj.description)}')
    db.commit();return {**serialize_pen(obj),'message':'Pen updated successfully'}


def period_limits(freq:str,day:date):
    if freq=='weekly':
        start=day-timedelta(days=day.weekday());end=start+timedelta(days=7)
        return start,end,start.isoformat()+':week'
    if freq=='monthly':
        start=day.replace(day=1)
        end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
        return start,end,start.isoformat()+':month'
    if freq not in ('daily','once'):
        raise HTTPException(422,'Select daily, weekly or monthly frequency')
    return day,day+timedelta(days=1),day.isoformat()+':day'


def target_key(category,batch_id=None,animal_id=None,pen_id=None,medicine_id=None):
    if category=='cleaning':
        if not pen_id:raise HTTPException(422,'Select a registered pen to clean')
        return f'pen:{pen_id}'
    if category=='medication':
        if not animal_id or not medicine_id:raise HTTPException(422,'Select an animal and an existing medicine')
        return f'animal:{animal_id}:med:{medicine_id}'
    if category=='dipping' and animal_id is None and batch_id is not None:
        return f'batch:{batch_id}'
    if animal_id:return f'animal:{animal_id}'
    if batch_id:return f'batch:{batch_id}'
    raise HTTPException(422,'Select an existing target')


def has_period_record(db,org,category,target,frequency,day=None):
    """Existing V5 entries are also checked, including entries from before this upgrade."""
    day=day or date.today();start,end,_=period_limits(frequency,day)
    start_dt=datetime.combine(start,time.min);end_dt=datetime.combine(end,time.min)
    query=db.query(V5Routine).filter(V5Routine.organization_id==org.id,V5Routine.category==category,
                                     V5Routine.created_at>=start_dt,V5Routine.created_at<end_dt)
    if target.startswith('pen:'):
        query=query.filter(V5Routine.pen_id==int(target.split(':')[1]))
    elif target.startswith('animal:'):
        animal=db.query(V5Animal).filter_by(organization_id=org.id,id=int(target.split(':')[1])).first()
        if not animal:return None
        query=query.filter(V5Routine.animal_tag==animal.tag)
        if category=='medication' and ':med:' in target:
            from modules.fattening.models import StockItem
            med=db.query(StockItem).filter_by(organization_id=org.id,id=int(target.split(':med:')[1]),category='medicine').first()
            if not med:return None
            query=query.filter(V5Routine.product==med.name)
    else:
        query=query.filter(V5Routine.batch_id==int(target.split(':')[1]),V5Routine.animal_tag.is_(None))
        if category=='cleaning':return None
    return query.order_by(V5Routine.id.desc()).first()


def claim_period(db,org,user,category,target,frequency,entry_id=None):
    today=date.today();_,_,key=period_limits(frequency,today)
    previous=has_period_record(db,org,category,target,frequency,today)
    if previous:raise HTTPException(409,f'{category.capitalize()} already recorded for this {frequency} period. Edit record #{previous.id} instead.')
    entry=PeriodClaim(organization_id=org.id,category=category,target=target,period_key=key,
                      entry_id=entry_id,recorded_by=user.id)
    db.add(entry)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,f'{category.capitalize()} already recorded for this period. Edit the existing entry.')
    return entry

@router.get('/routine/record-status')
def routine_status(category:Literal['weighing','cleaning','dipping','medication','health','inspection','maintenance','other'],
                   batch_id:int|None=None,animal_id:int|None=None,pen_id:int|None=None,
                   frequency:Literal['daily','weekly','monthly']='daily',medicine_id:int|None=None,
                   db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;licensed(db,org,False)
    if m.role not in ('org_admin','manager'):permitted(m,'routine.'+category)
    if pen_id is not None:
        pen=db.query(Pen).filter_by(id=pen_id,organization_id=org.id,status='active').first()
        if not pen:raise HTTPException(404,'Pen not found or inactive')
        batch_id=pen.batch_id
    if animal_id is not None:
        animal=db.query(V5Animal).filter_by(id=animal_id,organization_id=org.id,status='active').first()
        if not animal:raise HTTPException(404,'Animal not found')
        batch_id=animal.batch_id
    elif batch_id is not None and not db.query(V5Batch).filter_by(id=batch_id,organization_id=org.id).first():
        raise HTTPException(404,'Batch not found')
    if category=='medication':
        from modules.fattening.models import StockItem
        if not medicine_id or not db.query(StockItem).filter_by(organization_id=org.id,id=medicine_id,category='medicine').first():
            raise HTTPException(422,'Select an existing medicine to check treatment status')
    target=target_key(category,batch_id,animal_id,pen_id,medicine_id)
    row=has_period_record(db,org,category,target,frequency)
    start,end,_=period_limits(frequency,date.today())
    if category=='weighing' and animal_id:
        from sqlalchemy import and_
        weigh=db.query(WeightObservation).filter(WeightObservation.organization_id==org.id,
            WeightObservation.animal_id==animal_id,WeightObservation.created_at>=datetime.combine(start,time.min),
            WeightObservation.created_at<datetime.combine(end,time.min)).order_by(WeightObservation.id.desc()).first()
        if weigh:return {'completed':True,'record_id':row.id if row else None,'weight_record_id':weigh.id,
                          'message':'Weight already recorded today. Use Edit weight to correct it.','next_date':end.isoformat()}
    return {'completed':bool(row),'record_id':row.id if row else None,'next_date':end.isoformat(),
        'message':f'Already recorded this {frequency} period. Edit the existing record.' if row else 'Ready to record'}

class RoutineEditIn(BaseModel):
    reason:str=Field(min_length=5,max_length=400)
    notes:str|None=None
    quantity:Decimal|None=Field(default=None,gt=0)

@router.patch('/routines/{entry_id}')
def edit_routine(entry_id:int,p:RoutineEditIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    row=db.query(V5Routine).filter_by(id=entry_id,organization_id=org.id).with_for_update().first()
    if not row:raise HTTPException(404,'Routine record not found')
    if m.role not in ('org_admin','manager'):
        if row.recorded_by!=user.id:raise HTTPException(403,'You can only correct records you entered')
        permitted(m,'routine.'+row.category)
        if row.created_at.date()!=date.today():raise HTTPException(403,'Ask your manager to correct an older record')
    if row.category=='feeding':raise HTTPException(409,'Feeding quantity and stock issue corrections must use the audited stock correction process')
    if row.category=='weighing':
        if p.quantity is None:raise HTTPException(422,'Enter corrected weight in kg')
        a=db.query(V5Animal).filter_by(organization_id=org.id,tag=row.animal_tag).first()
        if not a:raise HTTPException(409,'The animal linked to this record is missing')
        obs=db.query(WeightObservation).filter_by(organization_id=org.id,routine_id=row.id).first()
        if not obs:raise HTTPException(409,'Cannot locate linked weight observation; contact management')
        old=obs.weight_kg;obs.weight_kg=p.quantity;row.quantity=float(p.quantity)
        # Only change current weight if this remains the most recent observation.
        latest=db.query(WeightObservation).filter_by(organization_id=org.id,animal_id=a.id).order_by(WeightObservation.created_at.desc(),WeightObservation.id.desc()).first()
        if latest and latest.id==obs.id:a.current_weight_kg=p.quantity
        detail=f'weight {old} -> {p.quantity} kg; reason: {p.reason}'
    elif p.quantity is not None:
        raise HTTPException(422,'Only weight corrections may change quantity in this form')
    else:detail=f'notes {row.notes!r} -> {p.notes!r}; reason: {p.reason}'
    if 'notes' in p.model_fields_set:row.notes=p.notes
    audit(db,user.id,'routine_correct','v5_routine',row.id,detail)
    db.commit();return {'id':row.id,'message':'Record corrected. Original change preserved in audit history.'}

class WeightEditIn(BaseModel):
    weight_kg:Decimal=Field(gt=0)
    reason:str=Field(min_length=5,max_length=400)

@router.patch('/animals/{animal_id}/weight/{observation_id}')
def edit_weight(animal_id:int,observation_id:int,p:WeightEditIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    a=db.query(V5Animal).filter_by(organization_id=org.id,id=animal_id).first()
    obs=db.query(WeightObservation).filter_by(organization_id=org.id,id=observation_id,animal_id=animal_id).first()
    if not a or not obs:raise HTTPException(404,'Weight record not found')
    if m.role not in ('org_admin','manager'):
        if obs.recorded_by!=user.id or obs.created_at.date()!=date.today():
            raise HTTPException(403,'Only the recorder may correct a weight today; manager otherwise')
        permitted(m,'routine.weighing')
    before=obs.weight_kg;obs.weight_kg=p.weight_kg
    if obs.routine_id:
        routine=db.query(V5Routine).filter_by(organization_id=org.id,id=obs.routine_id).first()
        if routine:routine.quantity=float(p.weight_kg)
    latest=db.query(WeightObservation).filter_by(organization_id=org.id,animal_id=animal_id).order_by(WeightObservation.created_at.desc(),WeightObservation.id.desc()).first()
    if latest and latest.id==obs.id:a.current_weight_kg=p.weight_kg
    audit(db,user.id,'weight_correct','v5_weight_observation',obs.id,f'{before} -> {p.weight_kg} kg; {p.reason}')
    db.commit();return {'id':obs.id,'message':'Weight corrected with audit history','weight_kg':float(p.weight_kg)}


# Feed composition request validation is owned by Animal Fattening.
class MixLine(BaseModel):
    item_id: int
    quantity_kg: Decimal = Field(gt=0, max_digits=17, decimal_places=3)


class MixByQuantity(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    feed_type: Literal['starter','grower','finisher','maintenance','lactation','other']='starter'
    lines: list[MixLine] = Field(min_length=1, max_length=30)
    kg_per_head_day: Decimal|None = Field(default=None,gt=0)
    @model_validator(mode='after')
    def unique(self):
        if len({x.item_id for x in self.lines}) != len(self.lines):
            raise ValueError('Each feed ingredient can only be selected once')
        return self


# Read-only visualization selectors. No tables or migrations are introduced.
FatteningArea = Literal['ranches','projects','batches','pens','animals','weighing','feeding','mixes','sales']


# V7.6 - project planning is versioned independently of the existing project header.
from pydantic import model_validator as _model_validator
class FatteningBudgetLine(BaseModel):
    category:str=Field(min_length=2,max_length=100)
    amount_per_head:Decimal=Field(default=Decimal(0),ge=0)
    quantity_basis:Literal['per_head']='per_head'

class FatteningMilestoneIn(BaseModel):
    title:str=Field(min_length=2,max_length=140)
    target_date:date|None=None
    actual_date:date|None=None
    owner:str|None=Field(default=None,max_length=100)
    status:Literal['planned','in_progress','completed','delayed']='planned'
    notes:str|None=Field(default=None,max_length=400)

class FatteningRiskIn(BaseModel):
    title:str=Field(min_length=2,max_length=180)
    likelihood:Literal['low','medium','high']='medium'
    impact:Literal['low','medium','high']='medium'
    owner:str|None=Field(default=None,max_length=100)
    mitigation:str=Field(default='',max_length=1200)
    status:Literal['open','mitigating','closed']='open'
    review_date:date|None=None

class FatteningCashflowIn(BaseModel):
    period:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    description:str=Field(min_length=2,max_length=160)
    expected_inflow:Decimal=Field(default=Decimal(0),ge=0)
    expected_outflow:Decimal=Field(default=Decimal(0),ge=0)

class FatteningFeedPhaseIn(BaseModel):
    stage:Literal['starter','grower','finisher','maintenance','other']='starter'
    duration_days:int=Field(ge=1,le=1500)
    kg_per_head_day:Decimal=Field(ge=0)
    planned_mix:str|None=Field(default=None,max_length=140)
    notes:str|None=Field(default=None,max_length=400)


class FatteningScenarioIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    price_change_percent:Decimal=Field(default=Decimal(0),ge=-95,le=300)
    feed_cost_change_percent:Decimal=Field(default=Decimal(0),ge=-95,le=300)
    additional_days:int=Field(default=0,ge=0,le=500)
    additional_mortality_percent:Decimal=Field(default=Decimal(0),ge=0,le=90)
    assumptions:str|None=Field(default=None,max_length=600)

class FatteningProjectPlanIn(BaseModel):
    planned_animals:int=Field(ge=1,le=1000000)
    entry_weight_kg:Decimal|None=Field(default=None,gt=0)
    finishing_weight_kg:Decimal|None=Field(default=None,gt=0)
    target_adg_kg_day:Decimal|None=Field(default=None,gt=0)
    duration_days:int=Field(ge=1,le=1500)
    feed_kg_head_day:Decimal|None=Field(default=None,ge=0)
    water_liters_head_day:Decimal|None=Field(default=None,ge=0)
    staffing_required:int|None=Field(default=None,ge=0)
    pens_required:int|None=Field(default=None,ge=0)
    funding_source:str|None=Field(default=None,max_length=140)
    planned_feed_cost_kg:Decimal|None=Field(default=None,ge=0)
    expected_sale_price_kg:Decimal|None=Field(default=None,ge=0)
    expected_sale_price_head:Decimal|None=Field(default=None,ge=0)
    expected_mortality_percent:Decimal=Field(default=Decimal(0),ge=0,lt=100)
    selling_expense_per_head:Decimal=Field(default=Decimal(0),ge=0)
    contingency_per_head:Decimal=Field(default=Decimal(0),ge=0)
    budget_lines:list[FatteningBudgetLine]=Field(default_factory=list,max_length=40)
    milestones:list[FatteningMilestoneIn]=Field(default_factory=list,max_length=60)
    risk_notes:str|None=Field(default=None,max_length=4000)
    target_market:str|None=Field(default=None,max_length=160)
    customer_profile:str|None=Field(default=None,max_length=160)
    sourcing_strategy:str|None=Field(default=None,max_length=500)
    planned_breeds:str|None=Field(default=None,max_length=220)
    procurement_start:date|None=None
    procurement_end:date|None=None
    production_notes:str|None=Field(default=None,max_length=1500)
    feed_strategy:str|None=Field(default=None,max_length=1200)
    staffing_plan:str|None=Field(default=None,max_length=1000)
    equipment_plan:str|None=Field(default=None,max_length=1000)
    water_plan:str|None=Field(default=None,max_length=1000)
    expected_sale_window:str|None=Field(default=None,max_length=120)
    commercial_notes:str|None=Field(default=None,max_length=1200)
    feeding_phases:list[FatteningFeedPhaseIn]=Field(default_factory=list,max_length=12)
    cashflow_lines:list[FatteningCashflowIn]=Field(default_factory=list,max_length=100)
    risks:list[FatteningRiskIn]=Field(default_factory=list,max_length=100)
    scenarios:list[FatteningScenarioIn]=Field(default_factory=list,max_length=10)
    @_model_validator(mode='after')
    def check_plan(self):
        if self.finishing_weight_kg is not None and self.entry_weight_kg is not None and self.finishing_weight_kg<=self.entry_weight_kg:
            raise ValueError('Target finishing weight must exceed entry weight')
        if self.expected_sale_price_kg is not None and self.expected_sale_price_head is not None:
            raise ValueError('Choose either projected selling price per kg or per head')
        if self.procurement_start and self.procurement_end and self.procurement_end<self.procurement_start:
            raise ValueError('Procurement end date must not precede the start date')
        if sum(x.duration_days for x in self.feeding_phases)>self.duration_days:
            raise ValueError('Feed phases cannot exceed the planned fattening period')
        if len({(r.period,r.description.strip().lower()) for r in self.cashflow_lines})!=len(self.cashflow_lines):
            raise ValueError('Cashflow rows must have unique period and description')
        categories=[line.category.strip().lower() for line in self.budget_lines]
        if len(categories)!=len(set(categories)):raise ValueError('Each budget category must appear only once')
        return self


# Each Projects subsection has its own save contract. All changes are merged and
# validated against the full plan before committing; approved baselines are locked.
class FatteningProjectSectionUpdate(BaseModel):
    section:Literal['production','budget','resources','commercial','milestones','cashflow','risks','scenarios']
    data:dict[str,object]=Field(default_factory=dict)
    revision:str=Field(min_length=3,max_length=64)
