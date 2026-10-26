"""V5.3 tenant-scoped stocked feed, landed costs, linked issues and operational audit.

The feed catalog is StockItem; a recipe is Ration. Stock receipt is a separate
physical transaction. Consumption posts exactly one linked issue per item.
Receipts are stock assets (cash committed), while consumption is operating cost,
so inventory purchases are not counted twice in the profit statement.
"""
from __future__ import annotations
import csv, io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, get_db, utcnow, User
from modules.organizations.service import context, licensed, permitted, V5Routine, V5Batch
from modules.fattening.models import StockItem, StockMovement, Ration, FinanceEntry, Task, V5Animal, permission, balance
from auth import audit

# Canonical ORM classes are owned by their respective domains.
from modules.employees.models import TaskCompletion
from modules.inventory.models import StockReceipt, FeedMixProduct


router=APIRouter(prefix='/api/v5',tags=['v5-supply-chain-audit'])



def task_due(task,when:date):
    """Occurrence rule for an assigned task. Due dates determine when recurrence starts."""
    first=task.due_date or task.created_at.date()
    if when<first:return False
    if task.frequency=='once':return when==first
    days=(when-first).days
    if task.frequency=='daily':return True
    if task.frequency=='weekly':return days%7==0
    if task.frequency=='monthly':
        import calendar
        return when.day==min(first.day,calendar.monthrange(when.year,when.month)[1])
    return False



class ReceiptIn(BaseModel):
    item_id:int
    quantity:Decimal=Field(gt=0)
    total_cost:Decimal=Field(ge=0)
    transport_cost:Decimal=Field(default=Decimal(0),ge=0)
    other_cost:Decimal=Field(default=Decimal(0),ge=0)
    supplier_name:str|None=Field(default=None,max_length=180)
    supplier_contact:str|None=Field(default=None,max_length=120)
    origin:str|None=Field(default=None,max_length=180)
    invoice_number:str|None=Field(default=None,max_length=120)
    expiry_date:date|None=None
    transaction_date:date=Field(default_factory=date.today)
    reference:str=Field(default_factory=lambda:'STK-'+__import__('secrets').token_hex(8).upper(),min_length=5,max_length=100)
    currency:str='TZS'
    exchange_rate:Decimal|None=Field(default=None,gt=0,description='Stock valuation currency per 1 purchase currency unit')
    note:str|None=None
    @model_validator(mode='after')
    def validate(self):
        if len(self.currency)!=3 or not self.currency.isalpha():
            raise ValueError('Enter a valid three-letter currency code')
        if self.expiry_date and self.expiry_date<self.transaction_date:
            raise ValueError('Expiry must not precede receipt date')
        return self

class IssueIn(BaseModel):
    item_id:int
    quantity:Decimal=Field(gt=0)
    reference:str=Field(default_factory=lambda:'STK-'+__import__('secrets').token_hex(8).upper(),min_length=5,max_length=100)
    transaction_date:date=Field(default_factory=date.today)
    batch_id:int|None=None
    note:str|None=None

class ReorderIn(BaseModel):
    reorder_level:Decimal=Field(ge=0)

CENTS=Decimal('0.01')

def money(v):return Decimal(v).quantize(CENTS,rounding=ROUND_HALF_UP)

def item_balance_and_cost(db,org,item_id):
    """Perpetual moving-average value from posted movements, including landed freight.
    Historical movements with zero cost use their catalog fallback; no magic prices.
    """
    item=db.query(StockItem).filter_by(id=item_id,organization_id=org.id).first()
    if not item:raise HTTPException(404,'Stock item not found in this organization')
    movements=db.query(StockMovement).filter_by(organization_id=org.id,item_id=item_id).order_by(StockMovement.id).all()
    qty=Decimal(0);value=Decimal(0)
    for m in movements:
        amount=Decimal(m.quantity)
        if m.direction in ('in','adjustment_in'):
            cost=Decimal(m.unit_cost or 0) or Decimal(item.cost_per_unit or 0)
            qty+=amount;value+=amount*cost
        else:
            average=value/qty if qty>0 else Decimal(item.cost_per_unit or 0)
            assigned=Decimal(m.unit_cost or 0) or average
            qty-=amount;value-=amount*assigned
            if qty<=0:qty=Decimal(0);value=Decimal(0)
    average=value/qty if qty>0 else Decimal(item.cost_per_unit or 0)
    return qty,max(Decimal(0),average)

def commit_issue(db,org,user,item_id,qty,reference,when,batch_id=None,note=None,source='manual',animal_id=None):
    """Caller holds the selected StockItem row lock and commits the enclosing DB txn.
    Enforced atomicity: one issue per reference, stock cannot become negative.
    """
    item=db.query(StockItem).filter_by(id=item_id,organization_id=org.id).first()
    if not item:raise HTTPException(404,'Stock item not found')
    if db.query(StockMovement).filter_by(organization_id=org.id,reference=reference).first():
        raise HTTPException(409,'Stock reference already recorded')
    if batch_id is not None and not db.query(V5Batch).filter_by(id=batch_id,organization_id=org.id).first():
        raise HTTPException(404,'Batch not found')
    available,unit_cost=item_balance_and_cost(db,org,item_id)
    if available<qty:raise HTTPException(409,f'Insufficient {item.name} stock: {available} {item.unit} available, {qty} requested')
    cost=money(qty*unit_cost)
    movement=StockMovement(organization_id=org.id,item_id=item_id,direction='out',quantity=qty,
        unit_cost=unit_cost,reference=reference,note=note,recorded_by=user.id,
        transaction_date=when,source_type=source,batch_id=batch_id)
    db.add(movement);db.flush()
    from modules.inventory.models import allocate_fefo
    allocate_fefo(db,org,item_id,movement.id,qty,available,when)
    if cost>0:
        db.add(FinanceEntry(organization_id=org.id,batch_id=batch_id,animal_id=animal_id,kind='cost',category='Feed consumption' if source=='feeding' else 'Stock issue',
            amount=cost,currency=item.currency or 'TZS',note=f'Automated from stock movement {movement.id}: {item.name}; qty {qty} {item.unit}',
            source_type='stock_issue',source_id=movement.id,created_by=user.id))
    return movement,cost

@router.get('/feed/catalog')
def feed_catalog(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;licensed(db,org,False)
    if m.role not in ('org_admin','manager','nutritionist','storekeeper'):permitted(m,'rations.read')
    rows=db.query(StockItem).filter_by(organization_id=org.id,category='feed').order_by(StockItem.name).all()
    maps={x.item_id:x.ration_id for x in db.query(FeedMixProduct).filter_by(organization_id=org.id)}
    from modules.inventory.models import usable_qty
    return {'items':[dict(id=x.id,name=x.name,unit=x.unit,category=x.category,currency=x.currency,
        stock_kg=float(usable_qty(db,org,x.id,balance(db,org,x.id))),is_mix=x.id in maps,recipe_id=maps.get(x.id),
        reorder_level=float(x.reorder_level or 0)) for x in rows]}

@router.post('/feed/mixes/{ration_id}/register-product',status_code=201)
def register_mix(ration_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True)
    r=db.query(Ration).filter_by(id=ration_id,organization_id=org.id).first()
    if not r:raise HTTPException(404,'Mix not found')
    link=db.query(FeedMixProduct).filter_by(ration_id=r.id,organization_id=org.id).first()
    if link:return {'item_id':link.item_id,'message':'Mix product already registered'}
    name=f'Mix: {r.name}'
    item=db.query(StockItem).filter_by(organization_id=org.id,name=name).first()
    if not item:item=StockItem(organization_id=org.id,name=name,unit='kg',category='feed',cost_per_unit=0,currency='TZS',reorder_level=0);db.add(item);db.flush()
    db.add(FeedMixProduct(ration_id=r.id,organization_id=org.id,item_id=item.id))
    audit(db,user.id,'mix_product_register','v5_stock_item',item.id,name)
    db.commit()
    return {'item_id':item.id,'message':'Mix added to feed catalog. Manufacture or receive stock before feeding.'}

@router.post('/stock/receive',status_code=201)
def receive_stock(p:ReceiptIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    item=db.query(StockItem).filter_by(id=p.item_id,organization_id=org.id).with_for_update().first()
    if not item:raise HTTPException(404,'Select an item from the saved feed and stock catalog')
    if item.category=='medicine' and not p.expiry_date:
        raise HTTPException(422,'Medicine receipts require an expiry date')
    base_currency=(item.currency or 'TZS').upper()
    purchase_currency=p.currency.upper()
    if base_currency!=purchase_currency and p.exchange_rate is None:
        raise HTTPException(422,f'Enter the exchange rate: how many {base_currency} equal 1 {purchase_currency} on the receipt date')
    if base_currency==purchase_currency and p.exchange_rate not in (None,Decimal(1)):
        raise HTTPException(422,'Exchange rate must be 1 when purchase and valuation currencies match')
    rate=p.exchange_rate or Decimal(1)
    if db.query(StockMovement).filter_by(organization_id=org.id,reference=p.reference).first():raise HTTPException(409,'Receipt reference already recorded')
    unit_cost=(p.total_cost+p.transport_cost+p.other_cost)*rate/p.quantity
    m=StockMovement(organization_id=org.id,item_id=item.id,direction='in',quantity=p.quantity,
        unit_cost=unit_cost,reference=p.reference,note=p.note,recorded_by=user.id,transaction_date=p.transaction_date,source_type='purchase')
    db.add(m);db.flush()
    from modules.inventory.models import register_lot
    register_lot(db,org,m,p.expiry_date)
    db.add(StockReceipt(movement_id=m.id,organization_id=org.id,supplier_name=p.supplier_name,
        supplier_contact=p.supplier_contact,origin=p.origin,invoice_number=p.invoice_number,
        expiry_date=p.expiry_date,total_cost=p.total_cost,transport_cost=p.transport_cost,
        other_cost=p.other_cost,currency=purchase_currency,exchange_rate=rate,base_currency=base_currency,
        base_total_cost=money((p.total_cost+p.transport_cost+p.other_cost)*rate)))
    # Stock acquisition is a balance-sheet asset, not yet a feed-consumption expense.
    total=money((p.total_cost+p.transport_cost+p.other_cost)*rate)
    if total>0:db.add(FinanceEntry(organization_id=org.id,batch_id=None,kind='asset_purchase',category='Inventory purchased',
        amount=total,currency=base_currency,note=f'Supplier: {p.supplier_name or "Not recorded"}; invoice {p.invoice_number or p.reference}; original {(p.total_cost+p.transport_cost+p.other_cost)} {purchase_currency}; FX {rate}; transport {p.transport_cost}',
        source_type='stock_receipt',source_id=m.id,created_by=user.id))
    audit(db,user.id,'stock_receive','v5_stock_movement',m.id,p.reference)
    from modules.platform_admin.service import complete_recorded_staff_duties
    if p.transaction_date==date.today():complete_recorded_staff_duties(db,org,user,'stock_receive')
    db.commit();return {'id':m.id,'balance':float(balance(db,org,item.id)),
        'landed_cost_per_unit':float(unit_cost),'total_landed_cost':float(total),'base_currency':base_currency,'purchase_currency':purchase_currency,
        'exchange_rate':float(rate),'message':'Stock received and finance asset recorded'}

@router.post('/stock/issue',status_code=201)
def issue_stock(p:IssueIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    item=db.query(StockItem).filter_by(id=p.item_id,organization_id=org.id).with_for_update().first()
    if not item:raise HTTPException(404,'Store item not found')
    movement,cost=commit_issue(db,org,user,p.item_id,p.quantity,p.reference,p.transaction_date,p.batch_id,p.note)
    from modules.inventory.models import usable_qty
    remaining=usable_qty(db,org,item.id,balance(db,org,item.id))
    if Decimal(item.reorder_level or 0)>0 and remaining<=Decimal(item.reorder_level):
        from modules.fattening.service import alert
        alert(db,org,'reorder','Reorder stock',f'{item.name} has {remaining} {item.unit} remaining; threshold is {item.reorder_level}.')
    audit(db,user.id,'stock_issue','v5_stock_movement',movement.id,p.reference)
    from modules.platform_admin.service import complete_recorded_staff_duties
    if p.transaction_date==date.today():complete_recorded_staff_duties(db,org,user,'stock_out')
    db.commit();return {'id':movement.id,'cost':float(cost),'unit_cost':float(movement.unit_cost),'remaining':float(balance(db,org,item.id)),
                        'message':'Stock issued; valuation and finance updated'}

@router.put('/stock/items/{item_id}/reorder')
def set_reorder(item_id:int,p:ReorderIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'stock.write',True)
    item=db.query(StockItem).filter_by(id=item_id,organization_id=org.id).first()
    if not item:raise HTTPException(404,'Item not found')
    item.reorder_level=p.reorder_level
    audit(db,user.id,'stock_reorder_level','v5_stock_item',item.id,str(p.reorder_level))
    db.commit();return {'id':item.id,'reorder_level':float(item.reorder_level),'message':'Reorder threshold saved'}

@router.get('/stock/status')
def stock_status(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'stock.read')
    rows=db.query(StockItem).filter_by(organization_id=org.id).order_by(StockItem.name).all()
    receipts=db.query(StockReceipt).filter_by(organization_id=org.id).all()
    incoming={}
    for rec in receipts:
        m=db.get(StockMovement,rec.movement_id)
        if m and m.item_id in {i.id for i in rows}:incoming.setdefault(m.item_id,[]).append(rec)
    records=[]
    today=date.today()
    for i in rows:
        qty,unit_cost=item_balance_and_cost(db,org,i.id)
        exp=[r for r in incoming.get(i.id,[]) if r.expiry_date and r.expiry_date<=today+timedelta(days=30)]
        from modules.inventory.models import usable_qty
        usable=usable_qty(db,org,i.id,qty)
        records.append({'id':i.id,'name':i.name,'category':i.category,'unit':i.unit,
            'balance':float(qty),'usable_balance':float(usable),'expired_or_unusable':float(max(Decimal(0),qty-usable)),'reorder_level':float(i.reorder_level or 0),'reorder':bool(Decimal(i.reorder_level or 0)>0 and usable<=Decimal(i.reorder_level or 0)),
            'value':float(money(qty*unit_cost)),'unit_cost':float(unit_cost),'currency':i.currency or 'TZS',
            'expiry_warnings':[{'expiry_date':r.expiry_date.isoformat(),'movement_id':r.movement_id} for r in exp]})
    return {'items':records,'reorder_count':sum(r['reorder'] for r in records),
            'note':'Reorder thresholds are set by managers. Expiry alerts flag receipt dates; physical lot depletion cannot be proven without lot-tracking.'}

@router.get('/stock/ledger')
def stock_ledger(db:Session=Depends(get_db),ctx=Depends(context),limit:int=Query(500,ge=1,le=2000)):
    _,org,_=permission(ctx,db,'stock.read')
    rows=db.query(StockMovement).filter_by(organization_id=org.id).order_by(StockMovement.id.desc()).limit(limit).all()
    receipts={r.movement_id:r for r in db.query(StockReceipt).filter_by(organization_id=org.id)}
    items={i.id:i for i in db.query(StockItem).filter_by(organization_id=org.id)}
    ids={r.recorded_by for r in rows}
    users={u.id:u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}
    result=[]
    for r in rows:
        rec=receipts.get(r.id)
        result.append(dict(id=r.id,item_id=r.item_id,item=items[r.item_id].name if r.item_id in items else '',direction=r.direction,
          quantity=float(r.quantity),unit_cost=float(r.unit_cost or 0),total_value=float(money(r.quantity*Decimal(r.unit_cost or 0))),
          currency=items[r.item_id].currency if r.item_id in items else 'TZS',reference=r.reference,source=r.source_type or 'manual',
          transaction_date=(r.transaction_date or r.created_at.date()).isoformat(),recorded_by=users.get(r.recorded_by,'Unknown'),batch_id=r.batch_id,
          supplier=rec.supplier_name if rec else None,origin=rec.origin if rec else None,supplier_contact=rec.supplier_contact if rec else None,
          total_cost=float(rec.total_cost) if rec else None,
          transport_cost=float(rec.transport_cost) if rec else None,other_cost=float(rec.other_cost) if rec else None,
          note=r.note,
          purchase_currency=rec.currency if rec else None,exchange_rate=float(rec.exchange_rate or 1) if rec else None,
          purchase_total=float((rec.total_cost or 0)+(rec.transport_cost or 0)+(rec.other_cost or 0)) if rec else None,
          expiry_date=rec.expiry_date.isoformat() if rec and rec.expiry_date else None,invoice_number=rec.invoice_number if rec else None))
    return {'items':result}

@router.get('/audit/overview')
def audit_overview(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    tasks=db.query(Task).filter_by(organization_id=org.id).all()
    today=date.today()
    since=today-timedelta(days=30)
    completions=db.query(TaskCompletion).filter(TaskCompletion.organization_id==org.id,TaskCompletion.occurrence_date>=since).all()
    completed={(c.task_id,c.occurrence_date) for c in completions}
    missed=[]
    for t in tasks:
        first=t.due_date or t.created_at.date()
        if t.frequency=='once':
            if first<today and t.status!='completed' and (t.id,first) not in completed:
                missed.append((t,first))
            continue
        check_since=max(since,first,t.created_at.date())
        for delta in range(max(0,(today-check_since).days)):
            due=check_since+timedelta(days=delta)
            if task_due(t,due) and (t.id,due) not in completed:
                missed.append((t,due))
    submitted=db.query(V5Routine).filter_by(organization_id=org.id).all()
    by_action=Counter(x.category for x in submitted)
    by_staff=Counter(x.recorded_by for x in submitted)
    issued=db.query(StockMovement).filter_by(organization_id=org.id).all()
    from modules.fattening.service import FeedingLine
    feeding_lines=db.query(FeedingLine).filter_by(organization_id=org.id).all()
    links={x.ration_id:x.item_id for x in db.query(FeedMixProduct).filter_by(organization_id=org.id)}
    by_feed_recorded=defaultdict(lambda:Decimal('0'))
    for line in feeding_lines:
        item_id=links.get(line.ration_id) if line.ration_id else line.item_id
        if item_id:by_feed_recorded[item_id]+=Decimal(line.quantity_kg)
    by_stock_feeding=defaultdict(lambda:Decimal('0'))
    for move in issued:
        if move.direction=='out' and move.source_type=='feeding':by_stock_feeding[move.item_id]+=Decimal(move.quantity)
    all_ids=set(by_feed_recorded)|set(by_stock_feeding)
    name_map={i.id:i.name for i in db.query(StockItem).filter_by(organization_id=org.id)}
    comparisons=[{'item_id':i,'item':name_map.get(i,str(i)),'recorded_kg':float(by_feed_recorded[i]),
                  'stock_out_feeding_kg':float(by_stock_feeding[i]),
                  'variance_kg':float(by_stock_feeding[i]-by_feed_recorded[i])} for i in sorted(all_ids)]
    manual_issues=sum((Decimal(x.quantity) for x in issued if x.direction=='out' and x.source_type=='manual'),Decimal(0))
    manufacturing_issues=sum((Decimal(x.quantity) for x in issued if x.direction=='out' and x.source_type=='manufacture'),Decimal(0))
    feed_issued=sum(by_stock_feeding.values(),Decimal(0))
    fed=sum(by_feed_recorded.values(),Decimal(0))
    stock=stock_status(db,ctx)
    names={u.id:u.full_name for u in db.query(User).filter(User.id.in_(set(by_staff)|{t.assigned_to for t in tasks if t.assigned_to}))}
    staff=[{'user_id':uid,'name':names.get(uid,'Unknown'),'routine_submissions':count} for uid,count in by_staff.most_common()]
    pending=[{'id':t.id,'title':t.title,'category':t.category,'assigned_to':names.get(t.assigned_to,'Unassigned'),
              'due_date':due.isoformat(),'status':'overdue'} for t,due in missed]
    return {'routine_count':len(submitted),'routine_by_type':dict(by_action),'staff_activity':staff,
      'tasks_total':len(tasks),'tasks_completed':len(completed),'tasks_overdue':len(missed),
      'overdue_tasks':pending,'stock_out_kg_all_sources':float(feed_issued),'feeding_recorded_kg':float(fed),
      'feed_variance_kg':float(feed_issued-fed),'feed_reconciliation':comparisons,
      'manual_stock_out_kg':float(manual_issues),'manufacturing_ingredient_out_kg':float(manufacturing_issues),
      'reorder_items':[x for x in stock['items'] if x['reorder']],
      'explanation':'Feed-issued quantities reconcile per product. Manufacturing and manual stock outs are separate. Missed recurring tasks are assessed against their due dates for the most recent 30 days. Tasks without an assigned employee are not attributed to a specific worker.'}

@router.get('/audit/entries')
def audit_entries(section:str=Query('activity',pattern='^(activity|tasks|stock|finance|sales)$'),limit:int=Query(500,ge=1,le=2000),
                  db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    ids=set()
    if section=='activity':
        rows=db.query(V5Routine).filter_by(organization_id=org.id).order_by(V5Routine.id.desc()).limit(limit).all()
        ids={r.recorded_by for r in rows}
        users={u.id:u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}
        from modules.fattening.schemas import Pen
        pen_names={p.id:p.name for p in db.query(Pen).filter_by(organization_id=org.id).all()}
        return {'items':[{'id':r.id,'date':r.created_at.isoformat(),'employee':users.get(r.recorded_by,'Unknown'),
          'action':r.category,'shift':r.shift,'frequency':r.frequency,'batch_id':r.batch_id,
          'pen':pen_names.get(r.pen_id),'animal':r.animal_tag,'quantity':r.quantity,'unit':r.unit,'notes':r.notes} for r in rows]}
    if section=='stock':return stock_ledger(db,ctx,limit)
    if section=='sales':
        from modules.fattening.router import sales
        return {'items':sales(db,ctx)['items'][:limit]}
    if section=='tasks':
        rows=db.query(Task).filter_by(organization_id=org.id).order_by(Task.id.desc()).limit(limit).all()
        ids={i for r in rows for i in (r.assigned_to,r.completed_by) if i}
        users={u.id:u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}
        return {'items':[dict(id=r.id,title=r.title,activity=r.category,assigned_to=users.get(r.assigned_to,'Unassigned'),
          status=('completed today' if (r.id,date.today()) in {(c.task_id,c.occurrence_date) for c in db.query(TaskCompletion).filter_by(organization_id=org.id).all()} else 'overdue' if r.due_date and r.due_date<date.today() and r.status!='completed' else r.status),
          due_date=r.due_date.isoformat() if r.due_date else None,completed_by=users.get(r.completed_by,''),
          completed_at=r.completed_at.isoformat() if r.completed_at else None) for r in rows]}
    rows=db.query(FinanceEntry).filter_by(organization_id=org.id).order_by(FinanceEntry.id.desc()).limit(limit).all()
    ids={r.created_by for r in rows if r.created_by}
    users={u.id:u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}
    return {'items':[dict(id=r.id,date=r.created_at.isoformat(),kind=r.kind,category=r.category,amount=float(r.amount),
      currency=r.currency,batch_id=r.batch_id,animal_id=r.animal_id,recorded_by=users.get(r.created_by,'Historical entry'),source=r.source_type,
      transaction_id=r.source_id,note=r.note) for r in rows]}

@router.get('/audit/export')
def audit_export(section:str=Query('activity',pattern='^(activity|tasks|stock|finance|sales)$'),db:Session=Depends(get_db),ctx=Depends(context)):
    result=audit_entries(section,2000,db,ctx)['items']
    buffer=io.StringIO();keys=sorted({k for r in result for k in r.keys()})
    writer=csv.DictWriter(buffer,fieldnames=keys);writer.writeheader()
    for row in result:
        writer.writerow({key:("'"+str(value) if isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r')) else value)
                         for key,value in row.items()})
    return StreamingResponse(iter([buffer.getvalue().encode('utf-8-sig')]),media_type='text/csv',
      headers={'Content-Disposition':f'attachment; filename="ranch-audit-{section}.csv"'})
