"""V5.9 extensible stock catalog and one-step receive workflow.

Feed definitions originate in Feed Mixes & Rations. Other stock categories
can be created as part of receipt processing, with an immutable movement and
a linked inventory asset posted in the same database transaction.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, get_db
from modules.organizations.service import context
from modules.fattening.models import StockItem, permission
from modules.inventory.service import ReceiptIn, receive_stock
from auth import audit

# Canonical ORM classes are owned by their respective domains.
from modules.inventory.models import StockItemDetails


router=APIRouter(prefix='/api/v5',tags=['v5.9-general-inventory'])

STOCK_CATEGORIES={
    'feed':'Feeds & mixes','medicine':'Medicine & veterinary','herbicide':'Herbicides & crop care',
    'uniform':'Staff uniforms','boots':'Boots & protective wear','gardening_tool':'Gardening tools',
    'equipment':'Equipment & machinery','maintenance_part':'Maintenance parts',
    'seed':'Seeds & seedlings','fertilizer':'Fertilizers','fuel':'Fuel & lubricants',
    'cleaning_supply':'Cleaning supplies','other':'Other supplies',
}

# Only attributes meaningful for the item's category may be persisted.
# The same rules are used for new receipts and audited detail corrections.
CATEGORY_ATTRIBUTE_FIELDS = {
    'feed': frozenset(),
    'medicine': frozenset(('manufacturer', 'strength_or_concentration', 'specification', 'storage_instructions')),
    'herbicide': frozenset(('manufacturer', 'strength_or_concentration', 'specification', 'storage_instructions')),
    'uniform': frozenset(('size', 'specification', 'manufacturer')),
    'boots': frozenset(('size', 'specification', 'manufacturer')),
    'gardening_tool': frozenset(('specification', 'manufacturer')),
    'equipment': frozenset(('specification', 'manufacturer')),
    'maintenance_part': frozenset(('specification', 'manufacturer')),
    'seed': frozenset(('specification', 'manufacturer', 'storage_instructions')),
    'fertilizer': frozenset(('specification', 'strength_or_concentration', 'manufacturer', 'storage_instructions')),
    'fuel': frozenset(('specification', 'storage_instructions')),
    'cleaning_supply': frozenset(('specification', 'manufacturer', 'storage_instructions')),
    'other': frozenset(('specification', 'manufacturer')),
}

def allowed_attributes(category: str) -> frozenset[str]:
    # Unrecognized custom categories get a safe minimal description, not
    # veterinary dosage, clothing size, machinery models, etc. by default.
    return CATEGORY_ATTRIBUTE_FIELDS.get(category, CATEGORY_ATTRIBUTE_FIELDS['other'])

def check_attributes(category: str, attrs: 'StockAttributes') -> None:
    data = attrs.model_dump(exclude_none=True)
    invalid = sorted(k for k, v in data.items() if v and k not in allowed_attributes(category))
    if invalid:
        raise HTTPException(422, detail=f"Fields not applicable to {category.replace('_',' ')}: {', '.join(invalid)}")



def normalize_category(value:str)->str:
    value=value.strip().casefold().replace('-', '_').replace(' ', '_')
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,39}',value):
        raise ValueError('Category must be 2–40 letters, numbers or underscores')
    return value

class StockAttributes(BaseModel):
    specification:str|None=Field(default=None,max_length=300)
    manufacturer:str|None=Field(default=None,max_length=180)
    size:str|None=Field(default=None,max_length=80)
    strength_or_concentration:str|None=Field(default=None,max_length=120)
    storage_instructions:str|None=Field(default=None,max_length=500)

class NewStockReceipt(BaseModel):
    name:str=Field(min_length=2,max_length=180)
    category:str=Field(min_length=2,max_length=40)
    unit:str=Field(min_length=1,max_length=30)
    valuation_currency:str=Field(default='TZS',min_length=3,max_length=3)
    reorder_level:Decimal=Field(default=Decimal(0),ge=0)
    attributes:StockAttributes=Field(default_factory=StockAttributes)
    receipt:ReceiptIn

    @field_validator('category')
    @classmethod
    def category_is_valid(cls,v):return normalize_category(v)

    @field_validator('unit')
    @classmethod
    def valid_unit(cls,v):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9 /_-]{0,29}',v.strip()):
            raise ValueError('Select a valid measurement unit')
        return v.strip()

    @field_validator('valuation_currency')
    @classmethod
    def valid_currency(cls,v):
        if not v.isalpha():raise ValueError('Currency must contain three letters')
        return v.upper()

    @model_validator(mode='after')
    def guard_feed(self):
        if self.category=='feed' and (self.unit.lower()!='kg' or self.attributes.model_dump(exclude_none=True)):
            raise ValueError('Feed must be measured in kg; create a recipe separately under Feed Mixes & Rations')
        check_attributes(self.category, self.attributes)
        if self.receipt.item_id!=0:
            raise ValueError('New stock receipt must use item_id 0; existing items use the normal receipt endpoint')
        return self

@router.get('/stock/categories')
def categories(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'stock.read')
    existing={x[0] for x in db.query(StockItem.category).filter(StockItem.organization_id==org.id).distinct().all()}
    result={**STOCK_CATEGORIES,**{x:x.replace('_',' ').title() for x in existing if x not in STOCK_CATEGORIES}}
    return {'items':[{'id':k,'name':v,'allows_new':k!='feed'} for k,v in result.items()]}

@router.get('/stock/items/{item_id}/details')
def get_details(item_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'stock.read')
    item=db.query(StockItem).filter_by(id=item_id,organization_id=org.id).first()
    if not item:raise HTTPException(404,'Stock item not found')
    record=db.query(StockItemDetails).filter_by(item_id=item_id,organization_id=org.id).first()
    return {'id':item.id,'name':item.name,'category':item.category,'unit':item.unit,
            'currency':item.currency,'reorder_level':float(item.reorder_level or 0),
            'attributes':{k:v for k,v in (json.loads(record.attributes_json) if record else {}).items() if k in allowed_attributes(item.category)}}

class DetailsEdit(BaseModel):
    reason:str=Field(min_length=5,max_length=500)
    attributes:StockAttributes

@router.patch('/stock/items/{item_id}/details')
def edit_details(item_id:int,p:DetailsEdit,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    item=db.query(StockItem).filter_by(id=item_id,organization_id=org.id).first()
    if not item:raise HTTPException(404,'Stock item not found')
    record=db.query(StockItemDetails).filter_by(item_id=item_id,organization_id=org.id).first()
    check_attributes(item.category, p.attributes)
    old=record.attributes_json if record else '{}'
    if record is None:
        record=StockItemDetails(organization_id=org.id,item_id=item.id)
        db.add(record)
    record.attributes_json=p.attributes.model_dump_json(exclude_none=True)
    audit(db,user.id,'stock_item_details_correct','v5_stock_item',item.id,
          f'Reason: {p.reason}; previous: {old[:700]}; new: {record.attributes_json[:700]}')
    db.commit()
    return {'id':item.id,'message':'Item details saved with correction history'}

@router.post('/stock/receive/new-item',status_code=201)
def receive_new_item(p:NewStockReceipt,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    name=p.name.strip()
    if db.query(StockItem).filter(StockItem.organization_id==org.id,func.lower(StockItem.name)==name.lower()).first():
        raise HTTPException(409,'This item already exists. Select it from the saved item list to receive more stock.')
    item=StockItem(organization_id=org.id,name=name,category=p.category,unit=p.unit,
                   currency=p.valuation_currency,reorder_level=p.reorder_level,cost_per_unit=0)
    db.add(item)
    try:
        db.flush()
        db.add(StockItemDetails(item_id=item.id,organization_id=org.id,
                                attributes_json=p.attributes.model_dump_json(exclude_none=True)))
        receipt=p.receipt.model_copy(update={'item_id':item.id})
        posted=receive_stock(receipt,db,ctx)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'This item or reference was already recorded. Choose the saved stock item instead.')
    except Exception:
        db.rollback()
        raise
    return {'id':item.id,'item_name':item.name,**posted,'message':'New item registered, stock received and Finance updated'}

# Operational endpoints extracted from the shared V5-era operations handler.
# Their implementation now lives with the owning business module.
_original_router = globals().get('router')
from modules.fattening.models import *
if _original_router is not None: router = _original_router
operations_router=APIRouter(prefix='/api/v5',tags=['inventory operations'])


@operations_router.get('/stock/items')
def items(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'stock.read');return {'items':[dict(id=i.id,name=i.name,unit=i.unit,category=i.category,cost_per_unit=float(i.cost_per_unit),currency=i.currency or 'TZS',reorder_level=float(i.reorder_level or 0),balance=float(balance(db,org,i.id))) for i in db.query(StockItem).filter_by(organization_id=org.id).order_by(StockItem.name)]}


@operations_router.post('/stock/items',status_code=201)
def add_item(p:ItemIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    if db.query(StockItem).filter_by(organization_id=org.id,name=p.name).first():raise HTTPException(409,'Item already exists')
    if db.query(StockItem).filter(StockItem.organization_id==org.id,func.lower(StockItem.name)==p.name.strip().lower()).first():
        raise HTTPException(409,'Feed or stock item already exists. Select the existing item instead.')
    x=StockItem(organization_id=org.id,**{**p.model_dump(),'name':p.name.strip()});db.add(x);db.flush();audit(db,user.id,'stock_item_create','v5_stock_item',x.id,p.name);db.commit();return {'id':x.id}


@operations_router.get('/stock/movements')
def movements(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'stock.read');return {'items':[dict(id=x.id,item_id=x.item_id,direction=x.direction,quantity=float(x.quantity),unit_cost=float(x.unit_cost),reference=x.reference,created_at=x.created_at.isoformat(),transaction_date=x.transaction_date.isoformat() if x.transaction_date else None,source=x.source_type or 'manual') for x in db.query(StockMovement).filter_by(organization_id=org.id).order_by(StockMovement.id.desc()).limit(500)]}


@operations_router.post('/stock/movements',status_code=201)
def add_movement(p:MovementIn,db:Session=Depends(get_db),ctx=Depends(context)):
    """Compatibility wrapper: valuation and finance remain centralized."""
    if p.direction not in ('in','out'):
        raise HTTPException(422,'Use the audited inventory receipt or stock issue workflow for adjustments')
    from modules.inventory.service import ReceiptIn, IssueIn, receive_stock, issue_stock
    if p.direction=='in':
        return receive_stock(ReceiptIn(item_id=p.item_id,quantity=p.quantity,total_cost=p.unit_cost*p.quantity,
            reference=p.reference,note=p.note),db,ctx)
    return issue_stock(IssueIn(item_id=p.item_id,quantity=p.quantity,reference=p.reference,note=p.note),db,ctx)


@operations_router.post('/mix-production',status_code=201)
def manufacture(p:ProductionIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True)
    r=db.query(Ration).filter_by(id=p.ration_id,organization_id=org.id).first()
    if not r:raise HTTPException(404,'Ration not found')
    item_check(db,org,p.finished_item_id)
    from modules.inventory.service import FeedMixProduct,item_balance_and_cost
    link=db.query(FeedMixProduct).filter_by(organization_id=org.id,ration_id=r.id).first()
    if link and link.item_id!=p.finished_item_id:
        raise HTTPException(422,'Choose the finished feed item automatically registered for this mix')
    components=__import__('json').loads(r.ingredients)
    if p.finished_item_id in [i['item_id'] for i in components]:raise HTTPException(422,'Finished product cannot be its own ingredient')
    # Serialize concurrent production/issuance against ingredient stocks in deterministic order.
    ingredient_ids=sorted({int(c['item_id']) for c in components}|{int(p.finished_item_id)})
    finished_item=item_check(db,org,p.finished_item_id)
    currencies={item_check(db,org,i).currency for i in ingredient_ids}
    if len(currencies)>1:
        raise HTTPException(422,'Ingredients and finished mix require a common inventory valuation currency. Convert original purchase currencies at receiving; do not add unlike currencies.')
    db.query(StockItem).filter(StockItem.organization_id==org.id,StockItem.id.in_(ingredient_ids)).order_by(StockItem.id).with_for_update().all()
    for c in components:
        required=p.quantity_kg*Decimal(c['percent'])/100
        if balance(db,org,c['item_id'])<required:raise HTTPException(409,f'Insufficient ingredient stock for item {c["item_id"]}')
    run=Production(organization_id=org.id,ration_id=r.id,finished_item_id=p.finished_item_id,quantity_kg=p.quantity_kg);db.add(run);db.flush()
    total_value=Decimal('0')
    for c in components:
        qty=p.quantity_kg*Decimal(c['percent'])/100
        _,cost=item_balance_and_cost(db,org,c['item_id'])
        total_value+=qty*cost
        from modules.inventory.models import allocate_fefo
        available,_=item_balance_and_cost(db,org,c['item_id'])
        move=StockMovement(organization_id=org.id,item_id=c['item_id'],direction='out',quantity=qty,unit_cost=cost,
            reference=f'mix-{run.id}-use-{c["item_id"]}',recorded_by=user.id,transaction_date=date.today(),source_type='manufacture')
        db.add(move);db.flush()
        allocate_fefo(db,org,c['item_id'],move.id,qty,available,date.today())
    finished_cost=total_value/p.quantity_kg
    received=StockMovement(organization_id=org.id,item_id=p.finished_item_id,direction='in',quantity=p.quantity_kg,unit_cost=finished_cost,
        reference=f'mix-{run.id}-receive',recorded_by=user.id,transaction_date=date.today(),source_type='manufacture')
    db.add(received);db.flush()
    from modules.inventory.models import register_lot
    register_lot(db,org,received,None)
    audit(db,user.id,'mix_manufacture','v5_mix_production',run.id,str(p.quantity_kg));db.commit();return {'id':run.id,'quantity_kg':float(run.quantity_kg)}


@operations_router.get('/stock/items/{item_id}/nutrients')
def item_nutrients(item_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'rations.read')
    item=item_check(db,org,item_id)
    if item.category!='feed':raise HTTPException(422,'Only feed items have feed nutrient profiles')
    profile=db.query(FeedItemNutrients).filter_by(organization_id=org.id,item_id=item_id).first()
    return {'item_id':item_id,'nutrients':__import__('json').loads(profile.nutrients) if profile else {},'notes':profile.notes if profile else None}


@operations_router.put('/stock/items/{item_id}/nutrients')
def save_item_nutrients(item_id:int,p:NutritionIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True)
    item=item_check(db,org,item_id)
    if item.category!='feed':raise HTTPException(422,'Only feed items have feed nutrient profiles')
    if set(p.nutrients)-set(NUTRIENT_LABELS):raise HTTPException(422,'Select a supported feed nutrient')
    if any(v<0 or v>100 or not v.is_finite() for v in p.nutrients.values()):raise HTTPException(422,'Each nutrient percentage must be between 0 and 100')
    profile=db.query(FeedItemNutrients).filter_by(organization_id=org.id,item_id=item_id).first()
    if profile is None:
        profile=FeedItemNutrients(organization_id=org.id,item_id=item_id,nutrients='{}');db.add(profile)
    profile.nutrients=__import__('json').dumps({k:float(v) for k,v in p.nutrients.items()});profile.notes=p.notes
    audit(db,user.id,'feed_item_nutrition_update','v5_stock_item',item_id,'Feed nutrition manually entered')
    db.commit();return {'item_id':item_id,'nutrients':__import__('json').loads(profile.nutrients),'message':'Feed nutrient profile saved'}
