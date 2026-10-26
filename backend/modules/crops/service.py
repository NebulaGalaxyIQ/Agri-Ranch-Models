"""V6.1 contextual nutrition, crop input costing and sellable animal products.

All writes are scoped to a subscribing organization. Financial postings occur in
one DB transaction and are identified by their source; no duplicate sales entry.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, get_db, utcnow
from modules.organizations.service import context
from auth import audit
from modules.fattening.models import FinanceEntry, ItemIn, RationIn, Ingredient, add_ration, StockItem
from modules.crops.models import (CropCycle, CropRecord, LivestockGroup, GeneralAnimal,
                        scope, linked, rowdata)
from modules.livestock.service import CropSale, LivestockEvent, LivestockSale, finance

# Canonical ORM classes are owned by their respective domains.
from modules.fattening.models import MixReferenceAmount
from modules.crops.models import CropInput
from modules.livestock.models import LivestockProject, LivestockProjectGroup, LivestockProjectCost, ProductLot, ProductSale


router = APIRouter(prefix='/api/v6', tags=['V6.1-contextual-operations'])





class CropInputIn(BaseModel):
    cycle_id:int
    category:Literal['seed','seedling','fertilizer','pesticide','herbicide','irrigation','labor','machinery','fuel','transport','land','other']
    description:str=Field(min_length=2,max_length=180)
    quantity:Decimal=Field(gt=0)
    unit:str=Field(min_length=1,max_length=30)
    unit_cost:Decimal=Field(ge=0)
    labor_cost:Decimal=Field(default=0,ge=0)
    transport_cost:Decimal=Field(default=0,ge=0)
    currency:str=Field(default='TZS',min_length=3,max_length=3)
    performed_on:date=Field(default_factory=date.today)
    note:str|None=None
    reference:str|None=None







class LivestockProjectIn(BaseModel):
    ranch_id:int;name:str=Field(min_length=2,max_length=160);purpose:str='general'
    start_date:date=Field(default_factory=date.today);end_date:date|None=None;currency:str='TZS';notes:str|None=None

class ProjectGroupIn(BaseModel):
    group_id:int

class ProjectCostIn(BaseModel):
    category:str=Field(min_length=2,max_length=70)
    description:str=Field(min_length=2,max_length=240)
    amount:Decimal=Field(gt=0);currency:str='TZS';performed_on:date=Field(default_factory=date.today)







PRODUCT_ACTIONS={'egg_collection':('eggs','pieces'),'milk_collection':('milk','litres'),
                 'wool_collection':('wool','kg'),'meat_collection':('meat','kg'),
                 'chick_collection':('chicks','birds'),'byproduct_collection':('byproduct','units')}

def post_livestock_product(db,org,event:LivestockEvent):
    """Called within the livestock event transaction; no second item registration."""
    if event.action not in PRODUCT_ACTIONS:return
    product,unit=PRODUCT_ACTIONS[event.action]
    if not event.quantity or event.quantity<=0:raise HTTPException(422,'Positive product quantity is required')
    # Physical unit follows recorded event unit when supplied.
    lot=ProductLot(organization_id=org.id,event_id=event.id,group_id=event.group_id,animal_id=event.animal_id,
                   product=product,unit=event.unit or unit,quantity_received=event.quantity,quantity_sold=0,
                   collected_on=event.performed_on)
    db.add(lot)

class ProductSaleIn(BaseModel):
    lot_id:int;quantity:Decimal=Field(gt=0);price_per_unit:Decimal=Field(gt=0)
    buyer:str=Field(min_length=2,max_length=180);currency:str='TZS';sold_on:date=Field(default_factory=date.today)
    reference:str|None=None

# === GHR_CROPS_V9_HELPERS ===
from datetime import timedelta
from sqlalchemy import func as sa_func
from modules.crops.models import (V9Project,V9Unit,V9Variety,V9Cycle,V9Record,V9Budget,V9Routine,V9Completion,
                                  V9Trial,V9Plot,V9Harvest,V9Stock,V9Sale,CropField)
from modules.crops.schemas import GENERIC_SECTIONS,SECTION_BY_ID

def v9_scope(db,ctx,write=False):
    return scope(db,ctx,'crops',write)

def v9_related(db,model,org,identifier,caption=None):
    if identifier is None:return None
    row=db.query(model).filter_by(id=identifier,organization_id=org.id).first()
    if row is None:raise HTTPException(404,f'{caption or model.__name__} does not belong to the organization')
    return row

def v9_project_cycle(db,org,project_id,cycle_id=None,unit_id=None):
    project=v9_related(db,V9Project,org,project_id,'Crop project')
    cycle=v9_related(db,V9Cycle,org,cycle_id,'Crop cycle')
    unit=v9_related(db,V9Unit,org,unit_id,'Field/block')
    if cycle and cycle.project_id!=project.id:raise HTTPException(422,'Crop cycle belongs to another project')
    if cycle and unit and cycle.unit_id!=unit.id:raise HTTPException(422,'Crop cycle belongs to another field/block')
    if unit:
        field=v9_related(db,CropField,org,unit.field_id,'Field')
        if field.ranch_id!=project.ranch_id:raise HTTPException(422,'Field belongs to a different ranch')
    if cycle and not unit:unit=v9_related(db,V9Unit,org,cycle.unit_id,'Field/block')
    if project.status in ('cancelled','completed'):raise HTTPException(409,'The project is closed for new operational records')
    return project,cycle,unit

def v9_when(day,action='Actual work'):
    if day>date.today():raise HTTPException(422,f'{action} cannot be recorded in the future')

def v9_check_data(section,data):
    fields={x['key']:x for x in SECTION_BY_ID[section]['fields']}
    unknown=set(data)-set(fields)
    if unknown:raise HTTPException(422,'Unrecognized fields: '+', '.join(sorted(unknown)))
    for key,field in fields.items():
        value=data.get(key)
        if field['required'] and (value is None or value==''):raise HTTPException(422,f"{field['label']} is required")
        if value is None or value=='':continue
        kind=field['kind']
        if kind=='choice' and value not in field['options']:raise HTTPException(422,f"Invalid value for {field['label']}")
        if kind in ('number','integer'):
            try: num=Decimal(str(value))
            except Exception:raise HTTPException(422,f"{field['label']} must be a number")
            if not num.is_finite():raise HTTPException(422,f"{field['label']} must be finite")
            if kind=='integer' and num!=int(num):raise HTTPException(422,f"{field['label']} must be a whole number")
            if any(k in key for k in ('pct','percentage')) and not (0<=num<=100):raise HTTPException(422,f"{field['label']} must be 0-100")
            if key not in ('air_temp_c','soil_ph','water_ph','ndvi') and num<0:raise HTTPException(422,f"{field['label']} cannot be negative")
        if kind=='date':
            try:date.fromisoformat(str(value))
            except Exception:raise HTTPException(422,f"{field['label']} requires YYYY-MM-DD")
        if kind=='boolean' and not isinstance(value,bool):raise HTTPException(422,f"{field['label']} must be checked or unchecked")
        if kind=='text' and (not isinstance(value,str) or len(value)>2000):raise HTTPException(422,f"Invalid {field['label']}")

def v9_amount(quantity,unit_cost,other_cost):
    base=Decimal(str(quantity or 0))*Decimal(str(unit_cost or 0))+Decimal(str(other_cost or 0))
    return base.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)

def v9_finance(db,actor,org,amount,currency,source_type,source_id,category,kind='cost'):
    if amount<=0:return
    db.add(FinanceEntry(organization_id=org.id,batch_id=None,kind=kind,category=category,amount=amount,
                        currency=currency,source_type=source_type,source_id=source_id,created_by=actor.id))

def v9_commit(db,actor,obj,action):
    db.add(obj);db.flush();audit(db,actor.id,action,obj.__tablename__,obj.id)
    value=rowdata(obj);db.commit();return {'item':value}

def v9_due(r,day):
    if not r.enabled or day<r.start_date or (r.end_date and day>r.end_date):return False
    delta=(day-r.start_date).days
    if r.frequency=='daily':return True
    if r.frequency=='weekly':return day.weekday() in (r.weekdays or [r.start_date.weekday()])
    if r.frequency=='weekdays':return day.weekday() in (r.weekdays or [0,1,2,3,4])
    if r.frequency=='monthly':return day.day==r.start_date.day
    if r.frequency=='once':return day==r.start_date
    if r.frequency.startswith('every_'):
        try:n=int(r.frequency.split('_')[1]);return n>0 and delta%n==0
        except Exception:return False
    return False

def v9_project_analytics(db,org):
    projects=db.query(V9Project).filter_by(organization_id=org.id).all()
    out=[]
    for p in projects:
        budgets=db.query(V9Budget).filter_by(organization_id=org.id,project_id=p.id,status='approved').all()
        budgets_latest={}
        for b in budgets:
            key=(b.category,b.description,b.currency,b.cycle_id)
            if key not in budgets_latest or b.version>budgets_latest[key].version:budgets_latest[key]=b
        budgets_by={}
        for b in budgets_latest.values():budgets_by[b.currency]=budgets_by.get(b.currency,Decimal(0))+Decimal(b.amount)
        costs={};revenues={};harvest=Decimal(0);sold=Decimal(0)
        records=db.query(V9Record).filter_by(organization_id=org.id,project_id=p.id).all()
        for r in records:
            # External Inventory issues must not post a duplicate cost.
            if r.data and r.data.get('stock_reference'):continue
            amount=v9_amount(r.quantity,r.unit_cost,r.other_cost)
            if amount>0 and r.currency:costs[r.currency]=costs.get(r.currency,Decimal(0))+amount
        lots=db.query(V9Harvest).filter_by(organization_id=org.id,project_id=p.id).all()
        available=Decimal(0)
        for l in lots:
            available+=Decimal(l.available_kg)
            harvest+=Decimal(l.marketable_kg)
            if l.cost is not None and l.currency:costs[l.currency]=costs.get(l.currency,Decimal(0))+Decimal(l.cost)
        sales=db.query(V9Sale).filter_by(organization_id=org.id,project_id=p.id).all()
        for s in sales:
            sold+=Decimal(s.quantity_kg)
            revenues[s.currency]=revenues.get(s.currency,Decimal(0))+Decimal(s.gross)
            if s.selling_cost is not None:costs[s.currency]=costs.get(s.currency,Decimal(0))+Decimal(s.selling_cost)
        for c in db.query(V9Completion).join(V9Routine,V9Routine.id==V9Completion.routine_id).filter(
            V9Completion.organization_id==org.id,V9Routine.project_id==p.id).all():
            if c.amount and c.currency:costs[c.currency]=costs.get(c.currency,Decimal(0))+Decimal(c.amount)
        by_currency=[]
        for currency in sorted(set(budgets_by)|set(costs)|set(revenues)):
            b=budgets_by.get(currency,Decimal(0));c=costs.get(currency,Decimal(0));r=revenues.get(currency,Decimal(0))
            by_currency.append({'currency':currency,'approved_budget':float(b),'recorded_cost':float(c),
                                'sales_revenue':float(r),'recorded_contribution':float(r-c),
                                'budget_variance':float(c-b)})
        out.append({'project_id':p.id,'project':p.name,'status':p.status,'harvested_marketable_kg':float(harvest),
                    'sold_kg':float(sold),'unsold_kg':float(available),'currencies':by_currency,
                    'cycles':db.query(V9Cycle).filter_by(organization_id=org.id,project_id=p.id).count()})
    return out
# === END_GHR_CROPS_V9_HELPERS ===
