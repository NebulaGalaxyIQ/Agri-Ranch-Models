"""V5.4 audited receipt corrections, shifts, employee workboard and finance metadata.

Correct posted stock without silently erasing the original audit. Financial/quantity
edits to purchases are allowed only before downstream movements; later changes use
explicit stock adjustments so historical feeding costs remain immutable.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError
from database import Base
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from database import get_db, User
from modules.organizations.service import context, licensed, permitted, V5Routine, V5Batch
from modules.fattening.models import (permission, StockItem, StockMovement, FinanceEntry,
                                  Task, V5Animal, balance)
from modules.inventory.service import (StockReceipt, TaskCompletion, task_due, item_balance_and_cost, money)
from auth import audit

# Canonical ORM classes are owned by their respective domains.
from modules.employees.models import RoutineShiftClaim


router=APIRouter(prefix='/api/v5',tags=['v5-smart-controls'])
SHIFTS=('Morning','Afternoon','Evening')


def claim_shift(db,org,user,category,batch_id,animal_id,shift):
    if shift not in SHIFTS:return
    target=f'animal:{animal_id}' if animal_id else f'batch:{batch_id}'
    db.add(RoutineShiftClaim(organization_id=org.id,category=category,target=target,
             occurrence_date=date.today(),shift=shift,recorded_by=user.id))
    try:db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,f'{shift} {category} was already submitted for this target today')

COST_CATEGORIES=('Animal procurement','Labor and wages','Transport','Feed consumption',
                 'Veterinary and medication','Water and utilities','Ranch infrastructure',
                 'Equipment and maintenance','Accommodation and welfare','Fuel','Security',
                 'Insurance','Administration','Logistics','Inventory shrinkage','Selling expenses','Other operating costs')

def day_bounds(day):
    return datetime.combine(day,time.min),datetime.combine(day+timedelta(days=1),time.min)

def completed_shifts(db,org,category,batch_id,animal_tag):
    start,end=day_bounds(date.today())
    return {r.shift for r in db.query(V5Routine).filter(
        V5Routine.organization_id==org.id,V5Routine.batch_id==batch_id,
        V5Routine.category==category,V5Routine.animal_tag==animal_tag,
        V5Routine.created_at>=start,V5Routine.created_at<end).all()}

def mark_matching_assignments(db,org,user,category,batch_id,shift,individual=False,pen_id=None):
    """Only batch-level completion auto-marks a matching batch duty.
    Individual feeding must not falsely finish a whole-batch assignment.
    """
    if individual:return 0
    n=0;today=date.today()
    tasks=db.query(Task).filter_by(organization_id=org.id,assigned_to=user.id,
                                   category=category).all()
    for t in tasks:
        if t.batch_id!=batch_id or not task_due(t,today):continue
        if category=='cleaning' and t.pen_id!=pen_id:continue
        if category in ('feeding','watering') and t.shift!=shift:continue
        if db.query(TaskCompletion).filter_by(organization_id=org.id,task_id=t.id,
                                              occurrence_date=today).first():continue
        db.add(TaskCompletion(organization_id=org.id,task_id=t.id,occurrence_date=today,completed_by=user.id))
        t.completed_by=user.id
        from database import utcnow
        t.completed_at=utcnow()
        if t.frequency=='once':t.status='completed'
        n+=1
    return n

@router.get('/routine/shift-status')
def shift_status(category:Literal['feeding','watering'],batch_id:int|None=None,
                 animal_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False)
    if m.role not in ('org_admin','manager'):permitted(m,'routine.'+category)
    if (batch_id is None)==(animal_id is None):raise HTTPException(422,'Select one existing batch or animal')
    tag=None
    if animal_id:
        a=db.query(V5Animal).filter_by(organization_id=org.id,id=animal_id,status='active').first()
        if not a:raise HTTPException(404,'Animal not found')
        batch_id=a.batch_id;tag=a.tag
    elif not db.query(V5Batch).filter_by(organization_id=org.id,id=batch_id).first():
        raise HTTPException(404,'Batch not found')
    done=completed_shifts(db,org,category,batch_id,tag)
    # Do not jump backwards to Morning after Afternoon/Evening were already recorded.
    last=max((SHIFTS.index(s) for s in done if s in SHIFTS),default=-1)
    available=[s for i,s in enumerate(SHIFTS) if s not in done and i>last]
    missed=[s for i,s in enumerate(SHIFTS) if s not in done and i<=last]
    return {'category':category,'batch_id':batch_id,'animal_id':animal_id,
            'completed':[s for s in SHIFTS if s in done],'missed':missed,'available':available,'next_shift':available[0] if available else None,
            'all_done':not available,'date':date.today().isoformat(),
            'message':('All shifts recorded for today' if len(done)==len(SHIFTS) else 'No later shifts available today' if not available else 'Next available: '+available[0])}

@router.get('/tasks/my')
def my_tasks(db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=ctx;licensed(db,org,False)
    rows=db.query(Task).filter_by(organization_id=org.id,assigned_to=user.id).order_by(Task.id.desc()).all()
    today=date.today();first=today-timedelta(days=30)
    records=db.query(TaskCompletion).filter(TaskCompletion.organization_id==org.id,
                                            TaskCompletion.task_id.in_([x.id for x in rows] or [-1]),
                                            TaskCompletion.occurrence_date>=first).all()
    comp={(r.task_id,r.occurrence_date):r for r in records}
    output={'due':[],'completed':[],'overdue':[],'upcoming':[]}
    for t in rows:
        common={'id':t.id,'title':t.title,'category':t.category,'shift':t.shift,'batch_id':t.batch_id,
                'frequency':t.frequency,'pen_id':t.pen_id,'due_date':t.due_date.isoformat() if t.due_date else None}
        if task_due(t,today):
            if (t.id,today) in comp:
                output['completed'].append({**common,'occurrence_date':today.isoformat(),'status':'completed'})
            else:output['due'].append({**common,'occurrence_date':today.isoformat(),'status':'due'})
        elif t.frequency=='once' and t.status=='completed':
            output['completed'].append({**common,'status':'completed'})
        elif t.frequency=='once' and t.due_date and t.due_date>today:
            output['upcoming'].append({**common,'occurrence_date':t.due_date.isoformat(),'status':'upcoming'})
        elif t.frequency!='once':
            # Scheduled recurring task: next occurrence within 31 days.
            future=next((today+timedelta(days=i) for i in range(1,32) if task_due(t,today+timedelta(days=i))),None)
            if future:output['upcoming'].append({**common,'occurrence_date':future.isoformat(),'status':'upcoming'})
        d=max(first,t.due_date or t.created_at.date())
        for i in range(max((today-d).days,0)):
            x=d+timedelta(days=i)
            if task_due(t,x) and (t.id,x) not in comp and not (t.frequency=='once' and t.status=='completed'):
                output['overdue'].append({**common,'occurrence_date':x.isoformat(),'status':'overdue'})
        for k in range(1,31):
            past=today-timedelta(days=k)
            if (t.id,past) in comp:output['completed'].append({**common,'occurrence_date':past.isoformat(),'status':'completed'})
    return {'date':today.isoformat(),**output,'counts':{k:len(v) for k,v in output.items()}}

class ItemEditIn(BaseModel):
    reason:str=Field(min_length=5,max_length=500)
    name:str|None=Field(default=None,min_length=2,max_length=180)
    reorder_level:Decimal|None=Field(default=None,ge=0)
    cost_per_unit:Decimal|None=Field(default=None,ge=0)

@router.patch('/stock/items/{item_id}')
def update_item(item_id:int,p:ItemEditIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    item=db.query(StockItem).filter_by(organization_id=org.id,id=item_id).with_for_update().first()
    if not item:raise HTTPException(404,'Item not found')
    if not ({'name','reorder_level','cost_per_unit'} & p.model_fields_set):raise HTTPException(422,'Select an item detail to correct')
    old=(item.name,str(item.reorder_level),str(item.cost_per_unit))
    if p.name is not None:
        from sqlalchemy import func
        if db.query(StockItem).filter(StockItem.organization_id==org.id,func.lower(StockItem.name)==p.name.strip().lower(),StockItem.id!=item.id).first():
            raise HTTPException(409,'A stock item with that name already exists')
        item.name=p.name.strip()
    if p.reorder_level is not None:item.reorder_level=p.reorder_level
    if p.cost_per_unit is not None:
        if db.query(StockMovement).filter_by(organization_id=org.id,item_id=item.id).first():
            raise HTTPException(409,'Cannot rewrite the original unit cost after stock movements; correct a receipt or post an audited adjustment')
        item.cost_per_unit=p.cost_per_unit
    audit(db,user.id,'stock_item_edit','v5_stock_item',item.id,f'Reason: {p.reason}; {old} -> {(item.name,item.reorder_level,item.cost_per_unit)}')
    db.commit();return {'id':item.id,'message':'Stock item updated and change audited'}

class ReceiptEditIn(BaseModel):
    reason:str=Field(min_length=5,max_length=500)
    supplier_name:str|None=None
    supplier_contact:str|None=None
    origin:str|None=None
    invoice_number:str|None=None
    expiry_date:date|None=None
    note:str|None=None
    quantity:Decimal|None=Field(default=None,gt=0)
    total_cost:Decimal|None=Field(default=None,ge=0)
    transport_cost:Decimal|None=Field(default=None,ge=0)
    other_cost:Decimal|None=Field(default=None,ge=0)
    @model_validator(mode='after')
    def check(self):
        if self.model_fields_set=={'reason'}:raise ValueError('Select a field to correct')
        return self

@router.patch('/stock/receipts/{movement_id}')
def edit_receipt(movement_id:int,p:ReceiptEditIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    movement=db.query(StockMovement).filter_by(id=movement_id,organization_id=org.id,
                                                 direction='in',source_type='purchase').with_for_update().first()
    if not movement:raise HTTPException(404,'Purchase receipt not found')
    db.query(StockItem).filter_by(id=movement.item_id,organization_id=org.id).with_for_update().first()
    rec=db.query(StockReceipt).filter_by(movement_id=movement.id,organization_id=org.id).first()
    if not rec:raise HTTPException(404,'Purchase details not found')
    original={key:getattr(rec,key) for key in ('supplier_name','supplier_contact','origin','invoice_number','expiry_date','total_cost','transport_cost','other_cost')}
    original['quantity']=movement.quantity;original['note']=movement.note
    financial={'quantity','total_cost','transport_cost','other_cost'}&p.model_fields_set
    if financial:
        if db.query(StockMovement).filter(StockMovement.organization_id==org.id,StockMovement.item_id==movement.item_id,
                                          StockMovement.id>movement.id).first():
            raise HTTPException(409,'This stock has later movements. Supplier details can still be edited, but quantity/cost must be corrected with a new audited inventory adjustment.')
    for key in ('supplier_name','supplier_contact','origin','invoice_number','expiry_date','total_cost','transport_cost','other_cost'):
        if key in p.model_fields_set:setattr(rec,key,getattr(p,key))
    if 'note' in p.model_fields_set:movement.note=p.note
    if 'expiry_date' in p.model_fields_set:
        from modules.inventory.models import StockLot
        lot=db.query(StockLot).filter_by(organization_id=org.id,receipt_movement_id=movement.id).first()
        if lot:lot.expiry_date=rec.expiry_date
    if 'quantity' in p.model_fields_set:
        from modules.inventory.models import StockLot
        lot=db.query(StockLot).filter_by(organization_id=org.id,receipt_movement_id=movement.id).first()
        if lot:
            lot.received_quantity=p.quantity
            lot.remaining_quantity=p.quantity
        movement.quantity=p.quantity
    if rec.expiry_date and movement.transaction_date and rec.expiry_date<movement.transaction_date:
        raise HTTPException(422,'Expiry date must not precede receipt date')
    if financial:
        landed=money((rec.total_cost+rec.transport_cost+rec.other_cost)*Decimal(rec.exchange_rate or 1))
        movement.unit_cost=(rec.total_cost+rec.transport_cost+rec.other_cost)*Decimal(rec.exchange_rate or 1)/movement.quantity
        rec.base_total_cost=landed
        entry=db.query(FinanceEntry).filter_by(organization_id=org.id,source_type='stock_receipt',source_id=movement.id).first()
        if entry:entry.amount=landed;entry.note=f'Corrected receipt {movement.reference}; {p.reason}'
        elif landed>0:db.add(FinanceEntry(organization_id=org.id,kind='asset_purchase',category='Inventory purchased',amount=landed,
                                       currency=rec.base_currency or rec.currency,source_type='stock_receipt',source_id=movement.id,
                                       created_by=user.id,note=f'Corrected receipt {movement.reference}; {p.reason}'))
    modified={key:(str(original.get(key)),str(getattr(rec,key) if key not in ('quantity','note') else (movement.quantity if key=='quantity' else movement.note)))
              for key in p.model_fields_set if key!='reason'}
    audit(db,user.id,'stock_receipt_correct','v5_stock_movement',movement.id,f'Reason: {p.reason}; changes: {modified}')
    db.commit();return {'id':movement.id,'message':'Receipt corrected and audit history saved','financial_recalculated':bool(financial)}

class StockCorrectionIn(BaseModel):
    item_id:int
    direction:Literal['adjustment_in','adjustment_out']
    quantity:Decimal=Field(gt=0)
    reference:str=Field(min_length=5,max_length=100)
    reason:str=Field(min_length=10,max_length=1000)
    transaction_date:date=Field(default_factory=date.today)
    # Corrections do not rewrite past feeding costs or sales.

@router.post('/stock/corrections',status_code=201)
def correct_stock(p:StockCorrectionIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    item=db.query(StockItem).filter_by(id=p.item_id,organization_id=org.id).with_for_update().first()
    if not item:raise HTTPException(404,'Stock item not found')
    if db.query(StockMovement).filter_by(organization_id=org.id,reference=p.reference).first():
        raise HTTPException(409,'Reference already used')
    available,unit_cost=item_balance_and_cost(db,org,item.id)
    if p.direction=='adjustment_out' and p.quantity>available:
        raise HTTPException(409,'A correction cannot reduce available stock below zero')
    move=StockMovement(organization_id=org.id,item_id=item.id,direction=p.direction,
                       quantity=p.quantity,unit_cost=unit_cost,reference=p.reference,note=p.reason,
                       recorded_by=user.id,transaction_date=p.transaction_date,source_type='correction')
    db.add(move);db.flush()
    if p.direction=='adjustment_out':
        from modules.inventory.models import allocate_fefo
        allocate_fefo(db,org,item.id,move.id,p.quantity,available,p.transaction_date)
    # Spoilage, missing inventory or loss is an expense when recognized. An
    # increased count changes asset valuation but is not fictitious revenue.
    if p.direction=='adjustment_out' and unit_cost>0:
        db.add(FinanceEntry(organization_id=org.id,kind='cost',category='Inventory shrinkage',
            amount=money(p.quantity*unit_cost),currency=item.currency or 'TZS',
            source_type='stock_correction',source_id=move.id,created_by=user.id,
            note=f'{item.name}: {p.quantity} {item.unit}; {p.reason}'))
    audit(db,user.id,'stock_adjustment','v5_stock_movement',move.id,
          f'{p.direction} {p.quantity} {item.unit} at {unit_cost}; reason: {p.reason}')
    db.commit();return {'id':move.id,'balance':float(balance(db,org,item.id)),'message':'Inventory correction posted; original records remain visible'}

@router.get('/finance/categories')
def finance_categories(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'finance.read')
    return {'cost_categories':list(COST_CATEGORIES),
            'revenue_categories':['Manure/byproduct sales','Service fees','Other revenue'],
            'note':'Stock receipts are acquired inventory assets, feed issues operating costs. Animal purchases are recorded once on animal registration.'}

@router.get('/finance/cost-summary')
def cost_summary(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'finance.read')
    rows=db.query(FinanceEntry).filter_by(organization_id=org.id).all()
    groups=defaultdict(lambda:Decimal(0));totals=defaultdict(lambda:Decimal(0))
    for x in rows:
        groups[(x.currency or 'TZS',x.kind,x.category)]+=Decimal(x.amount)
        totals[(x.currency or 'TZS',x.kind)]+=Decimal(x.amount)
    return {'categories':[{'currency':a,'kind':b,'category':c,'amount':float(v)} for (a,b,c),v in sorted(groups.items())],
            'totals':[{'currency':a,'kind':b,'amount':float(v)} for (a,b),v in sorted(totals.items())],
            'note':'Asset purchases, expense consumption and revenue are separate. Do not combine currencies without exchange rates.'}
