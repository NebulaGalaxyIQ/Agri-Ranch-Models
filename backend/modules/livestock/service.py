"""V6 general livestock activity/sales and crop sales. Operational events post finance once."""
from __future__ import annotations
from datetime import date,datetime
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import Integer,String,Text,Date,DateTime,Numeric,ForeignKey,UniqueConstraint,func
from sqlalchemy.orm import mapped_column,Mapped,Session
from database import Base,get_db,utcnow
from auth import audit
from modules.organizations.service import context
from modules.fattening.models import FinanceEntry
from modules.crops.models import CropCycle,CropRecord,LivestockGroup,GeneralAnimal,scope,linked,rowdata
# Canonical ORM classes are owned by their respective domains.
from modules.crops.models import CropSale
from modules.livestock.models import LivestockEvent, LivestockSale


router=APIRouter(prefix='/api/v6',tags=['V6-production-sales'])




class CropSaleIn(BaseModel):
    cycle_id:int;buyer:str=Field(min_length=2,max_length=180);buyer_contact:str|None=None
    quantity_kg:Decimal=Field(gt=0);price_per_kg:Decimal=Field(gt=0);currency:str='TZS'
    sale_date:date=Field(default_factory=date.today);invoice_ref:str|None=None;notes:str|None=None

class LivestockEventIn(BaseModel):
    group_id:int|None=None;animal_id:int|None=None;action:Literal['birth','mortality','egg_collection','milk_collection','wool_collection','meat_collection','chick_collection','byproduct_collection','vaccination','health_check','breeding','feeding','inspection','other']
    performed_on:date=Field(default_factory=date.today);quantity:Decimal|None=Field(default=None,gt=0)
    unit:str|None=None;reference:str=Field(min_length=6,max_length=120);cost:Decimal=Field(default=0,ge=0);currency:str='TZS';notes:str|None=None
    @model_validator(mode='after')
    def one_target(self):
        if (self.group_id is None)==(self.animal_id is None):raise ValueError('Select exactly one animal or herd/flock')
        if self.action in ('birth','mortality','egg_collection','milk_collection','wool_collection','meat_collection','chick_collection','byproduct_collection') and not self.quantity:raise ValueError('Quantity is required for production and population events')
        return self

class LivestockSaleIn(BaseModel):
    group_id:int|None=None;animal_id:int|None=None;buyer:str=Field(min_length=2,max_length=180);buyer_contact:str|None=None
    reason:str=Field(min_length=3);price_basis:Literal['per_head','per_kg'];price_per_unit:Decimal=Field(gt=0)
    quantity:int=Field(default=1,ge=1);weight_kg:Decimal|None=Field(default=None,gt=0)
    currency:str='TZS';sale_date:date=Field(default_factory=date.today)
    @model_validator(mode='after')
    def valid(self):
        if (self.group_id is None)==(self.animal_id is None):raise ValueError('Select animal OR herd/flock')
        if self.animal_id is not None and self.quantity!=1:raise ValueError('An individually identified animal is sold once')
        if self.price_basis=='per_kg' and not self.weight_kg:raise ValueError('Measured kg required for per-kg sales')
        if self.sale_date>date.today():raise ValueError('Sale date cannot be in the future')
        return self

def finance(db,actor,org,category,amount,currency,source,source_id,kind='cost'):
    if amount>0:db.add(FinanceEntry(organization_id=org.id,kind=kind,category=category,amount=amount,currency=currency,source_type=source,source_id=source_id,created_by=actor.id))


@router.get('/livestock/events')
def events(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'livestock');return {'items':[rowdata(x) for x in db.query(LivestockEvent).filter_by(organization_id=o.id).order_by(LivestockEvent.id.desc()).limit(500).all()]}
@router.post('/livestock/events',status_code=201)
def record_event(p:LivestockEventIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=scope(db,ctx,'livestock',True)
    group=linked(db,LivestockGroup,o,p.group_id,'Herd') if p.group_id else None
    animal=linked(db,GeneralAnimal,o,p.animal_id,'Animal') if p.animal_id else None
    if animal and animal.status!='active':raise HTTPException(409,'Animal not active')
    if db.query(LivestockEvent).filter_by(organization_id=o.id,reference=p.reference).first():raise HTTPException(409,'Event reference already used')
    if p.action in ('birth','mortality'):
        if not group:raise HTTPException(422,'Population adjustment requires a herd or flock')
        if p.quantity!=int(p.quantity):raise HTTPException(422,'Enter a whole-animal quantity')
        change=int(p.quantity)*(1 if p.action=='birth' else -1)
        if group.head_count+change<0:raise HTTPException(409,'The flock cannot become negative')
        group.head_count+=change
    ev=LivestockEvent(organization_id=o.id,recorded_by=actor.id,**p.model_dump())
    db.add(ev);db.flush()
    from modules.crops.service import post_livestock_product
    post_livestock_product(db,o,ev)
    finance(db,actor,o,'Livestock '+p.action,p.cost,p.currency,'v6_livestock_event',ev.id)
    audit(db,actor.id,'livestock_event','v6_livestock_event',ev.id,p.action);out=rowdata(ev);db.commit()
    return {'item':out,'message':'Animal activity recorded'}

@router.get('/livestock/sales')
def livestock_sales(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'livestock');return {'items':[rowdata(x) for x in db.query(LivestockSale).filter_by(organization_id=o.id).order_by(LivestockSale.id.desc()).limit(500).all()]}
@router.post('/livestock/sales',status_code=201)
def livestock_sale(p:LivestockSaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=scope(db,ctx,'livestock',True)
    if p.animal_id:
        animal=db.query(GeneralAnimal).filter_by(id=p.animal_id,organization_id=o.id).with_for_update().first()
        if not animal:raise HTTPException(404,'Animal not found')
        if animal.status!='active':raise HTTPException(409,'Animal already sold or inactive')
        if animal.group_id:
            parent=db.query(LivestockGroup).filter_by(id=animal.group_id,organization_id=o.id).with_for_update().first()
            if parent and parent.head_count>0:parent.head_count-=1
        animal.status='sold'
    if p.group_id:
        group=db.query(LivestockGroup).filter_by(id=p.group_id,organization_id=o.id).with_for_update().first()
        if not group:raise HTTPException(404,'Herd or flock not found')
        if p.quantity>group.head_count:raise HTTPException(409,'Cannot sell more animals than the group contains')
        group.head_count-=p.quantity
    gross=(p.price_per_unit*(p.weight_kg if p.price_basis=='per_kg' else Decimal(p.quantity))).quantize(Decimal('.01'))
    record=LivestockSale(organization_id=o.id,recorded_by=actor.id,gross=gross,**p.model_dump());db.add(record);db.flush()
    finance(db,actor,o,'General livestock sales',gross,p.currency,'v6_livestock_sale',record.id,'revenue')
    audit(db,actor.id,'livestock_sold','v6_livestock_sale',record.id,str(gross));data=rowdata(record);db.commit()
    return {'item':data,'message':'Sale recorded, animal count updated and Finance posted'}

# V8 reusable, domain-specific calculations. Report monetary totals by currency:
# no implicit exchange rates or fabricated shared expense allocations.
def livestock_money_by_currency(records, value_field):
    totals = {}
    for record in records:
        code = record.currency
        totals[code] = totals.get(code, Decimal('0')) + Decimal(getattr(record, value_field) or 0)
    return {code: float(amount) for code, amount in sorted(totals.items())}


def livestock_growth_rows(rows):
    """Annotate ascending weight history with actual per-target gain and ADG."""
    earlier = {}
    result = []
    for weight in sorted(rows, key=lambda x: (x.measured_on, x.id)):
        key = ('animal', weight.animal_id) if weight.animal_id else ('group', weight.group_id)
        previous = earlier.get(key)
        gain = Decimal(weight.weight_kg) - Decimal(previous.weight_kg) if previous else None
        days = (weight.measured_on - previous.measured_on).days if previous else 0
        info = rowdata(weight)
        info['gain_kg'] = float(gain) if gain is not None else None
        info['adg_kg_day'] = round(float(gain) / days, 3) if gain is not None and days > 0 else None
        result.append(info)
        earlier[key] = weight
    return sorted(result, key=lambda x: x['id'], reverse=True)
