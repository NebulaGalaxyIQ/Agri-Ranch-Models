"""V5.6 audited animal sales and finance reconciliation.

Every sale belongs to ONE registered animal and ONE organization. Sale recording,
animal removal from the active batch, revenue and selling costs commit together.
A void is an explicit reversed financial event; historical records are never deleted.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, get_db, utcnow, User
from modules.organizations.service import context, V5Batch
from modules.fattening.models import V5Animal, FinanceEntry, permission, animal_data
from auth import audit

# Canonical ORM classes are owned by their respective domains.
from modules.fattening.models import AnimalSale


router=APIRouter(prefix='/api/v5', tags=['v5-animal-sales'])


class SaleIn(BaseModel):
    buyer_name:str=Field(min_length=2,max_length=180)
    buyer_contact:str|None=Field(default=None,max_length=120)
    reason:str=Field(min_length=3,max_length=250)
    price_basis:Literal['per_kg','per_head']
    price_per_unit:Decimal=Field(gt=0)
    weight_kg:Decimal|None=Field(default=None,gt=0)
    sale_date:date=Field(default_factory=date.today)
    currency:Literal['TZS','USD','KES','EUR']='TZS'
    transport_cost:Decimal=Field(default=Decimal(0),ge=0)
    commission_cost:Decimal=Field(default=Decimal(0),ge=0)
    other_cost:Decimal=Field(default=Decimal(0),ge=0)
    invoice_ref:str|None=Field(default=None,max_length=120)
    notes:str|None=None
    preview_token:str|None=Field(default=None,min_length=64,max_length=64)
    @model_validator(mode='after')
    def validate_sale(self):
        if self.price_basis=='per_kg' and self.weight_kg is None:
            raise ValueError('Record the measured live sale weight in kg for a price-per-kg sale')
        if self.sale_date>date.today():
            raise ValueError('Sale date cannot be in the future')
        return self

class VoidIn(BaseModel):
    reason:str=Field(min_length=8,max_length=500)

CENT=Decimal('0.01')
def money(x):return Decimal(x).quantize(CENT,rounding=ROUND_HALF_UP)

def sale_dict(s,tag=None):
    return dict(id=s.id,animal_id=s.animal_id,animal_tag=tag,batch_id=s.batch_id,
        buyer_name=s.buyer_name,buyer_contact=s.buyer_contact,reason=s.reason,
        sale_date=s.sale_date.isoformat(),price_basis=s.price_basis,price_per_unit=float(s.price_per_unit),
        weight_kg=float(s.weight_kg) if s.weight_kg is not None else None,
        gross_amount=float(s.gross_amount),transport_cost=float(s.transport_cost),
        commission_cost=float(s.commission_cost),other_cost=float(s.other_cost),
        selling_expenses=float(s.transport_cost+s.commission_cost+s.other_cost),currency=s.currency,
        status=s.status,invoice_ref=s.invoice_ref,notes=s.notes,void_reason=s.void_reason,
        recorded_by=s.recorded_by,created_at=s.created_at.isoformat())

@router.post('/animals/{animal_id}/sale',status_code=201)
def sell_animal(animal_id:int,p:SaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=permission(ctx,db,'animals.manage',True)
    if m.role!='org_admin':
        from modules.organizations.service import permitted
        permitted(m,'finance.write')
    # Row lock serializes sales/status changes on PostgreSQL; partial unique index
    # independently protects against competing sales for the same animal.
    a=db.query(V5Animal).filter_by(id=animal_id,organization_id=org.id).with_for_update().first()
    if not a:raise HTTPException(404,'Animal is not registered in your organization')
    if a.arrival_date and p.sale_date<a.arrival_date:
        raise HTTPException(422,'Sale date cannot precede the animal arrival date')
    if a.status not in ('active','sold'):
        raise HTTPException(409,'Only active animals can be sold')
    if db.query(AnimalSale).filter_by(organization_id=org.id,animal_id=animal_id,status='completed').first():
        raise HTTPException(409,'This animal already has a completed sale. Open its sale record instead of recording another.')
    b=db.query(V5Batch).filter_by(organization_id=org.id,id=a.batch_id).first()
    if not b:raise HTTPException(409,'The animal must belong to a registered batch')
    if p.invoice_ref and db.query(AnimalSale).filter_by(organization_id=org.id,invoice_ref=p.invoice_ref,status='completed').first():
        raise HTTPException(409,'This invoice reference is already used by another completed sale')
    from modules.fattening.service import fattening_sale_preview
    from modules.fattening.models import FatteningSaleCostSnapshot
    import json
    preview=fattening_sale_preview(db,org.id,animal_id,p)
    if not preview['comparable']:raise HTTPException(409,'Sale cost currencies differ; convert and reconcile costs before confirming this sale')
    if p.preview_token is not None and p.preview_token != preview['preview_token']:
        raise HTTPException(409,'Animal cost or sale values have changed. Review the refreshed sale preview before confirming.')
    gross=money(p.price_per_unit*(p.weight_kg if p.price_basis=='per_kg' else Decimal(1)))
    expense=money(p.transport_cost+p.commission_cost+p.other_cost)
    obj=AnimalSale(organization_id=org.id,animal_id=a.id,batch_id=b.id,
        gross_amount=gross,recorded_by=user.id,**p.model_dump(exclude={'preview_token'}))
    db.add(obj);db.flush()
    db.add(FatteningSaleCostSnapshot(organization_id=org.id,sale_id=obj.id,project_id=preview['project_id'],
        currency=p.currency,cost_snapshot_json=json.dumps({k:v for k,v in preview.items() if k!='preview_token'})))
    db.add(FinanceEntry(organization_id=org.id,batch_id=b.id,animal_id=a.id,
        kind='revenue',category='Livestock sales',amount=gross,currency=p.currency,
        note=f'{a.tag} sold to {p.buyer_name}; {p.price_basis}; invoice {p.invoice_ref or "—"}',
        source_type='animal_sale',source_id=obj.id,created_by=user.id))
    if expense>0:
        db.add(FinanceEntry(organization_id=org.id,batch_id=b.id,animal_id=a.id,
            kind='cost',category='Selling expenses',amount=expense,currency=p.currency,
            note=f'Transport {p.transport_cost}; commission {p.commission_cost}; other {p.other_cost}',
            source_type='animal_sale_expense',source_id=obj.id,created_by=user.id))
    a.status='sold'
    audit(db,user.id,'animal_sold','v5_animal_sale',obj.id,
        f'{a.tag}; {p.price_basis}; {gross} {p.currency}; buyer {p.buyer_name}; batch {b.id}')
    try:db.commit()
    except __import__('sqlalchemy').exc.IntegrityError:
        db.rollback()
        raise HTTPException(409,'Animal already sold or sales reference is duplicated. Refresh the animal list.')
    return {**sale_dict(obj,a.tag),'financial_result':{k:v for k,v in preview.items() if k!='preview_token'},'message':'Animal sale saved; Finance updated and animal removed from active batch occupancy'}

@router.get('/sales')
def sales(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'finance.read')
    rows=db.query(AnimalSale).filter_by(organization_id=org.id).order_by(AnimalSale.id.desc()).limit(2000).all()
    animals={a.id:a.tag for a in db.query(V5Animal).filter_by(organization_id=org.id).all()}
    names={u.id:u.full_name for u in db.query(User).filter(User.id.in_([x for s in rows for x in (s.recorded_by,s.voided_by) if x] or [-1])).all()}
    return {'items':[{**sale_dict(s,animals.get(s.animal_id)),
             'recorded_by_name':names.get(s.recorded_by,'Unknown'),
             'voided_by_name':names.get(s.voided_by) if s.voided_by else None} for s in rows]}

@router.post('/sales/{sale_id}/void')
def void_sale(sale_id:int,p:VoidIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=permission(ctx,db,'finance.write',True)
    if m.role!='org_admin':
        from modules.organizations.service import permitted
        permitted(m,'animals.manage')
    s=db.query(AnimalSale).filter_by(id=sale_id,organization_id=org.id).with_for_update().first()
    if not s:raise HTTPException(404,'Sale not found')
    if s.status!='completed':raise HTTPException(409,'This sale was already cancelled')
    a=db.query(V5Animal).filter_by(id=s.animal_id,organization_id=org.id).with_for_update().first()
    b=db.query(V5Batch).filter_by(id=s.batch_id,organization_id=org.id).with_for_update().first()
    if not a or not b:raise HTTPException(409,'Historical animal or batch is missing; contact platform administrator')
    if a.status!='sold':raise HTTPException(409,'Animal status changed after sale; manual reconciliation required')
    active=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=b.id,status='active').count()
    if b.capacity is not None and active>=b.capacity:
        raise HTTPException(409,'Cannot restore sold animal: original batch is full. Move another animal first or contact management.')
    # Reverse the exact linked entries, not arbitrary manual revenue or unrelated costs.
    originals=db.query(FinanceEntry).filter_by(organization_id=org.id,source_id=s.id).filter(
        FinanceEntry.source_type.in_(['animal_sale','animal_sale_expense'])).all()
    if not any(e.source_type=='animal_sale' for e in originals):
        raise HTTPException(409,'Sale revenue is missing from Finance; cancellation requires reconciliation')
    for e in originals:
        db.add(FinanceEntry(organization_id=org.id,batch_id=e.batch_id,animal_id=e.animal_id,
            kind=e.kind,category=e.category,amount=-e.amount,currency=e.currency,
            note=f'REVERSAL of finance #{e.id}; sale #{s.id}; {p.reason}',
            source_type='animal_sale_reversal',source_id=s.id,created_by=user.id))
    s.status='voided';s.void_reason=p.reason;s.voided_by=user.id;s.voided_at=utcnow()
    a.status='active'
    audit(db,user.id,'animal_sale_void','v5_animal_sale',s.id,p.reason)
    db.commit()
    return {'id':s.id,'status':s.status,'message':'Sale cancelled, finance reversed and animal restored to batch'}

@router.get('/finance/animal-profitability')
def animal_profitability(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'finance.read')
    animals={a.id:a for a in db.query(V5Animal).filter_by(organization_id=org.id).all()}
    sales=db.query(AnimalSale).filter_by(organization_id=org.id,status='completed').order_by(AnimalSale.id.desc()).all()
    rows=db.query(FinanceEntry).filter_by(organization_id=org.id).all()
    entries={}
    for e in rows:
        if e.animal_id:entries.setdefault(e.animal_id,[]).append(e)
    result=[]
    for s in sales:
        a=animals.get(s.animal_id)
        if not a:continue
        purchase_currency=a.purchase_currency or 'TZS'
        same=purchase_currency==s.currency
        purchase=money(a.purchase_cost or 0)
        # Purchase appears in Finance once; don't sum procurement row and model purchase amount.
        direct_costs=sum((e.amount for e in entries.get(a.id,[]) if e.kind=='cost'
            and e.currency==s.currency and e.category!='Animal procurement'),Decimal(0))
        direct_revenue=sum((e.amount for e in entries.get(a.id,[]) if e.kind=='revenue'
            and e.currency==s.currency),Decimal(0))
        contribution=money(direct_revenue-direct_costs-purchase) if same else None
        result.append({'sale_id':s.id,'animal_id':a.id,'tag':a.tag,'batch_id':s.batch_id,
            'buyer':s.buyer_name,'sale_date':s.sale_date.isoformat(),'sale_currency':s.currency,
            'sale_revenue':float(direct_revenue),'procurement_cost':float(purchase),
            'procurement_currency':purchase_currency,'animal_direct_costs':float(direct_costs),
            'direct_contribution':float(contribution) if contribution is not None else None,
            'status':'Direct contribution — excludes unallocated batch overhead' if same else 'Currency mismatch — no conversion assumed'})
    unallocated={}
    for e in rows:
        if e.kind=='cost' and e.animal_id is None:
            key=(e.currency,e.category);unallocated[key]=unallocated.get(key,Decimal(0))+e.amount
    return {'items':result,'unallocated_costs':[{'currency':c,'category':cat,'amount':float(v)}
            for (c,cat),v in sorted(unallocated.items())],
            'note':'Direct contribution = recorded animal sale revenue − purchase cost − directly attributed animal costs. Batch feeding, labor, overhead and inventory acquisitions are NOT allocated to individual animals. Consequently direct contribution is NOT complete net profit. No currencies are silently converted.'}

@router.get('/sales/export')
def sales_export(db:Session=Depends(get_db),ctx=Depends(context)):
    data=sales(db,ctx)['items'];out=io.StringIO()
    keys=['animal_tag','sale_date','buyer_name','buyer_contact','reason','price_basis','price_per_unit',
          'weight_kg','gross_amount','currency','transport_cost','commission_cost','other_cost','status','invoice_ref']
    writer=csv.DictWriter(out,fieldnames=keys);writer.writeheader()
    for x in data:
        writer.writerow({k:("'"+str(x[k]) if isinstance(x.get(k),str) and x[k].startswith(('=','+','-','@')) else x.get(k)) for k in keys})
    return StreamingResponse(iter([out.getvalue().encode('utf-8-sig')]),media_type='text/csv',
        headers={'Content-Disposition':'attachment; filename="animal-sales.csv"'})

@router.get('/finance/profit-summary')
def profit_summary(db:Session=Depends(get_db),ctx=Depends(context)):
    """Recorded operating result by currency, not mixed-currency enterprise P&L.

    Animal procurement is capitalized until that animal is sold; stock purchases
    are inventory assets. Sold animals' acquisition costs become COGS. Batch-level
    costs remain in the period and are not misrepresented as measured per-head spend.
    """
    _,org,_=permission(ctx,db,'finance.read')
    ledger=db.query(FinanceEntry).filter_by(organization_id=org.id).all()
    completed=db.query(AnimalSale).filter_by(organization_id=org.id,status='completed').all()
    animals={a.id:a for a in db.query(V5Animal).filter_by(organization_id=org.id).all()}
    accounts={}
    def acc(currency):
        return accounts.setdefault(currency,dict(currency=currency,revenue=Decimal(0),
            operating_cost=Decimal(0),sold_livestock_cogs=Decimal(0),
            total_inventory_purchases=Decimal(0),total_livestock_acquisitions=Decimal(0),
            unknown_cross_currency_cogs=0))
    for e in ledger:
        row=acc(e.currency)
        if e.kind=='asset_purchase':
            if e.category=='Inventory purchased':row['total_inventory_purchases']+=e.amount
            continue
        if e.category=='Animal procurement':
            row['total_livestock_acquisitions']+=e.amount
            continue  # purchase is capital until recognized in sale COGS
        if e.kind=='cost':row['operating_cost']+=e.amount
        elif e.kind=='revenue':row['revenue']+=e.amount
    for s in completed:
        animal=animals.get(s.animal_id)
        if not animal:continue
        cur=animal.purchase_currency or 'TZS'
        row=acc(cur)
        # Keep cost in its original currency; incomplete conversion is explicit.
        row['sold_livestock_cogs']+=Decimal(animal.purchase_cost or 0)
        if cur!=s.currency:
            row['unknown_cross_currency_cogs']+=1
            acc(s.currency)['unknown_cross_currency_cogs']+=1
    result=[]
    for currency,r in sorted(accounts.items()):
        partial=any(s.currency!=animals[s.animal_id].purchase_currency for s in completed if s.animal_id in animals and (s.currency==currency or animals[s.animal_id].purchase_currency==currency))
        period=r['revenue']-r['operating_cost']-r['sold_livestock_cogs']
        result.append({**{k:(float(v) if isinstance(v,Decimal) else v) for k,v in r.items()},
          'recorded_period_result':None if partial else float(money(period)),
          'result_status':'Requires FX conversion or review' if partial else 'Recorded operating result, before unrecorded liabilities and depreciation'})
    return {'by_currency':result,'sale_count':len(completed),'note':
      'Procurement for unsold animals and inventory receipts are assets, not immediately expensed again. Sold livestock acquisition is recognized once as cost of goods sold. Recurring feed, labor and overhead are recorded expenses; when not tagged to an animal they remain batch/organization costs. The period result is not audited net profit, excludes missing depreciation/taxes and must not be combined across currencies.'}


# Native fattening animal performance, costs and pricing.
"""Tenant-scoped animal performance, feeding and financial interpretation.

Read-side aggregation only: never re-post expenses or feed stock movements.
Write-side remains the verified V5 transactional service through compatibility
routes while the full operational extraction is completed.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import V5Animal as Animal, WeightObservation, FinanceEntry, permission, V5Animal as _Animal
from .service import V5Project as Project, FeedAssignment, FeedingLine
from modules.organizations.service import V5Batch as Batch, V5Ranch as Ranch, V5Routine as RoutineEntry









from .service import animal_profile, profile_overview, animal_performance_list
from modules.fattening.models import permission
from modules.organizations.service import context
profile_router = APIRouter(prefix="/api/v6/fattening", tags=["Animal Fattening"] )

@profile_router.get("/overview")
def fattening_overview(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,"analytics.read")
    return profile_overview(db,org.id)

@profile_router.get("/animals/{animal_id}/profile")
def fattening_animal_profile(animal_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,"animals.read")
    return animal_profile(db,org.id,animal_id)

@profile_router.get("/animals/performance")
def fattening_animal_performance(batch_id:int|None=None,limit:int=100,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,"animals.read")
    return animal_performance_list(db,org.id,batch_id,max(1,min(limit,250)))

@profile_router.get("/animals/{animal_id}/break-even")
def fattening_animal_break_even(animal_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    """Automatically calculated from posted animal/batch cost records; read only."""
    _,org,_=permission(ctx,db,"animals.read")
    return animal_profile(db,org.id,animal_id)['break_even']

# Canonical Fattening public API backed by the module-owned handlers above and
# other actual module implementation files (no importing deprecated versions).
from modules.organizations.router import router as _organization_router
from modules.fattening.models import router as _animal_router
from modules.fattening.service import router as _feeding_router
from modules.fattening.schemas import router as _pen_router
from modules.inventory.service import router as _feed_stock_router
from modules.reports.service import router as _insights_router
native_router = APIRouter(prefix='/api/v6/fattening', tags=['Animal Fattening operations'])
_operational_paths = ('/ranches','/projects','/batches','/pens','/animals','/rations',
   '/feeding','/feed/assignments','/feed/plans','/feed/recommendation','/feed/catalog',
   '/feed/nutrients','/routine/options','/sales','/analytics/performance',
   '/finance/animal-profitability')
for _source in (_organization_router,_animal_router,_feeding_router,_pen_router,
                router,_feed_stock_router,_insights_router):
    for _route in _source.routes:
        _path = getattr(_route,'path','')
        if _path.startswith('/api/v5/'):
            _relative = _path[len('/api/v5'):]
            if any(_relative == s or _relative.startswith(s+'/') for s in _operational_paths):
                native_router.add_api_route(_relative,_route.endpoint,methods=list(_route.methods),
                    name='fattening_'+_route.name,include_in_schema=True,
                    status_code=_route.status_code,response_model=_route.response_model)

# Feed mix formulation endpoints owned by Animal Fattening.

from modules.fattening.schemas import MixByQuantity
from modules.fattening.models import MixReferenceAmount, Ingredient, add_ration, RationIn
mix_router=APIRouter(prefix="/api/v6",tags=["Feed formulation"])

@mix_router.post('/feed/mixes/by-quantity',status_code=201)
def mix_by_quantity(p:MixByQuantity, db:Session=Depends(get_db), ctx=Depends(context)):
    """Quantities specify the *recipe reference proportions*, NOT a manufacturing/stock movement."""
    total=sum((x.quantity_kg for x in p.lines),Decimal(0))
    parts=[];remaining=Decimal('100')
    for i,line in enumerate(p.lines):
        pct=remaining if i==len(p.lines)-1 else (line.quantity_kg*100/total)
        parts.append(Ingredient(item_id=line.item_id,percent=pct));remaining-=pct
    created=add_ration(RationIn(name=p.name,feed_type=p.feed_type,ingredients=parts,
                     kg_per_head_day=p.kg_per_head_day),db,ctx)
    _,org,_=ctx
    for line in p.lines:
        db.add(MixReferenceAmount(organization_id=org.id,ration_id=created['id'],item_id=line.item_id,quantity_kg=line.quantity_kg))
    db.commit()
    return {**created,'total_reference_kg':float(total),'composition':[{'item_id':x.item_id,'quantity_kg':float(x.quantity_kg),
            'percentage':float(parts[i].percent)} for i,x in enumerate(p.lines)],
            'message':'Feed mix saved; ingredients are not deducted until actual manufacturing'}


@mix_router.get('/feed/mixes/references')
def recipe_reference_amounts(db:Session=Depends(get_db),ctx=Depends(context)):
    from modules.fattening.models import permission
    _,o,_=permission(ctx,db,'rations.read')
    rows=db.query(MixReferenceAmount).filter_by(organization_id=o.id).all()
    grouped={}
    for x in rows:
        group=grouped.setdefault(x.ration_id,{'ration_id':x.ration_id,'total_reference_kg':0.0,'lines':[]})
        group['lines'].append({'item_id':x.item_id,'quantity_kg':float(x.quantity_kg)})
        group['total_reference_kg']+=float(x.quantity_kg)
    return {'items':list(grouped.values())}



# The application imports the public Fattening routers from this module only.
fattening_routers = (_animal_router, _feeding_router, _pen_router, router, profile_router, native_router, mix_router)

# V7.1: analytics are derived only from posted tenant-owned operations.
from .service import fattening_section_insights, fattening_mix_details
from .schemas import FatteningArea

@profile_router.get('/insights/{section}')
def section_insights(section:FatteningArea, currency:str|None=None,animal_id:int|None=None,
        db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    return fattening_section_insights(db,org.id,section,currency=currency,animal_id=animal_id)

@profile_router.get('/mixes/{mix_id}/details')
def mix_details(mix_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'rations.read')
    return fattening_mix_details(db,org.id,mix_id)


# V7.6 - owner-scoped project business plan and live project reconciliation endpoints.
from modules.fattening.models import FatteningProjectPlan,FatteningPlanHistory,FatteningSaleCostSnapshot,V5Project
from modules.fattening.schemas import FatteningProjectPlanIn,FatteningProjectSectionUpdate
from modules.fattening.service import fattening_project_dashboard, fattening_sale_preview
import json as _json
import hashlib as _hashlib

@profile_router.get('/projects/{project_id}/dashboard')
def project_dashboard(project_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'projects.read')
    return fattening_project_dashboard(db,org.id,project_id)

@profile_router.put('/projects/{project_id}/plan')
def save_project_plan(project_id:int,p:FatteningProjectPlanIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'projects.manage',True)
    project=db.query(V5Project).filter_by(id=project_id,organization_id=org.id).with_for_update().first()
    if not project:raise HTTPException(404,'Project not found')
    current=db.query(FatteningProjectPlan).filter_by(organization_id=org.id,project_id=project_id).with_for_update().first()
    if current and current.status=='approved':raise HTTPException(409,'Approved budget is locked. Start a revision first.')
    data=_json.dumps(p.model_dump(mode='json'),separators=(',',':'))
    if not current:
        current=FatteningProjectPlan(organization_id=org.id,project_id=project_id,prepared_by=user.id,
            status='draft',version=1,plan_json=data)
        db.add(current)
    else:current.plan_json=data;current.prepared_by=user.id
    audit(db,user.id,'fattening_project_plan_saved','v5_project',project_id,f'draft version {current.version}')
    db.commit()
    return fattening_project_dashboard(db,org.id,project_id)

# Field-level section ownership prevents unrelated fields from being clobbered.
FATTENING_PLAN_SECTIONS={
 'production':{'planned_animals','entry_weight_kg','finishing_weight_kg','target_adg_kg_day','duration_days','expected_mortality_percent','planned_breeds','sourcing_strategy','procurement_start','procurement_end','production_notes'},
 'budget':{'budget_lines','selling_expense_per_head','contingency_per_head'},
 'resources':{'feed_kg_head_day','planned_feed_cost_kg','water_liters_head_day','staffing_required','pens_required','funding_source','feed_strategy','staffing_plan','equipment_plan','water_plan','feeding_phases'},
 'commercial':{'expected_sale_price_kg','expected_sale_price_head','target_market','customer_profile','expected_sale_window','commercial_notes'},
 'milestones':{'milestones'},
 'cashflow':{'cashflow_lines'},
 'risks':{'risks','risk_notes'},
 'scenarios':{'scenarios'},
}

@profile_router.put('/projects/{project_id}/plan/section')
def save_project_plan_section(project_id:int,p:FatteningProjectSectionUpdate,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'projects.manage',True)
    project=db.query(V5Project).filter_by(id=project_id,organization_id=org.id).with_for_update().first()
    if not project:raise HTTPException(404,'Project not found')
    current=db.query(FatteningProjectPlan).filter_by(organization_id=org.id,project_id=project_id).with_for_update().first()
    if current and current.status=='approved':raise HTTPException(409,'This plan is approved. Start a revision before editing a section.')
    current_revision=(_hashlib.sha256(current.plan_json.encode('utf-8')).hexdigest() if current else 'new')
    if p.revision!=current_revision:raise HTTPException(409,'The project plan has been changed by another user. Refresh the project before saving.')
    allowed=FATTENING_PLAN_SECTIONS[p.section]
    unexpected=set(p.data)-allowed
    if unexpected:raise HTTPException(422,detail='Fields do not belong to '+p.section+': '+', '.join(sorted(unexpected)))
    if not p.data:raise HTTPException(422,'No fields submitted for this section')
    values=(_json.loads(current.plan_json) if current else
        {'planned_animals':max(1,int(project.target_animals or 1)),
         'duration_days':max(1,min(1500,((project.end_date-project.start_date).days if project.start_date and project.end_date else 90)))})
    values.update(p.data)
    # Validation covers cross-section dependencies such as duration and feeding phases.
    try:verified=FatteningProjectPlanIn.model_validate(values)
    except Exception as e:
        from pydantic import ValidationError
        if isinstance(e,ValidationError):raise HTTPException(422,e.errors(include_context=False,include_url=False))
        raise
    payload=_json.dumps(verified.model_dump(mode='json'),separators=(',',':'))
    if current is None:
        current=FatteningProjectPlan(organization_id=org.id,project_id=project_id,prepared_by=user.id,
            status='draft',version=1,plan_json=payload)
        db.add(current)
    else:current.plan_json=payload;current.prepared_by=user.id
    audit(db,user.id,'fattening_project_'+p.section+'_updated','v5_project',project_id,
          f'section={p.section}; draft version={current.version}')
    db.commit()
    return fattening_project_dashboard(db,org.id,project_id)

@profile_router.post('/projects/{project_id}/plan/approve')
def approve_project_plan(project_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=permission(ctx,db,'projects.manage',True)
    if m.role!='org_admin':
        from modules.organizations.service import permitted
        permitted(m,'finance.write')
    current=db.query(FatteningProjectPlan).filter_by(organization_id=org.id,project_id=project_id).with_for_update().first()
    if not current:raise HTTPException(404,'Prepare the project plan before approving it')
    if current.status=='approved':raise HTTPException(409,'Plan is already approved')
    # Publish the approved plan baseline back to the existing Projects listing.
    # Draft edits never silently change the approved operational budget.
    project=db.query(V5Project).filter_by(organization_id=org.id,id=project_id).with_for_update().first()
    if not project:raise HTTPException(404,'Project not found')
    values=_json.loads(current.plan_json)
    heads=int(values['planned_animals'])
    head_cost=sum((Decimal(str(line['amount_per_head'])) for line in values.get('budget_lines',[])),Decimal(0))
    if not any(line['category'].lower().strip()=='feed' and Decimal(str(line['amount_per_head']))>0 for line in values.get('budget_lines',[])):
        head_cost+=Decimal(str(values.get('feed_kg_head_day') or 0))*Decimal(str(values.get('planned_feed_cost_kg') or 0))*int(values.get('duration_days') or 0)
    head_cost+=Decimal(str(values.get('selling_expense_per_head') or 0))
    project.budget=(head_cost*heads).quantize(Decimal('0.01'))
    project.target_animals=heads
    if values.get('finishing_weight_kg') is not None:project.target_weight_kg=Decimal(str(values['finishing_weight_kg']))
    current.status='approved';current.approved_by=user.id;current.approved_at=utcnow()
    db.add(FatteningPlanHistory(organization_id=org.id,project_id=project_id,version=current.version,
        plan_json=current.plan_json,status='approved',recorded_by=user.id))
    audit(db,user.id,'fattening_project_plan_approved','v5_project',project_id,f'version {current.version}')
    db.commit()
    return fattening_project_dashboard(db,org.id,project_id)

@profile_router.post('/projects/{project_id}/plan/revise')
def revise_project_plan(project_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'projects.manage',True)
    current=db.query(FatteningProjectPlan).filter_by(organization_id=org.id,project_id=project_id).with_for_update().first()
    if not current:raise HTTPException(404,'Project plan not found')
    if current.status!='approved':raise HTTPException(409,'Only approved plans may be revised')
    current.version+=1;current.status='draft';current.prepared_by=user.id
    current.approved_at=None;current.approved_by=None
    audit(db,user.id,'fattening_project_plan_revised','v5_project',project_id,f'draft version {current.version}')
    db.commit()
    return fattening_project_dashboard(db,org.id,project_id)

@profile_router.post('/animals/{animal_id}/sale/preview')
def preview_animal_sale(animal_id:int,p:SaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'animals.manage')
    return fattening_sale_preview(db,org.id,animal_id,p)


class FatteningAnimalCostIn(BaseModel):
    category:str=Field(min_length=2,max_length=100)
    amount:Decimal=Field(gt=0)
    currency:Literal['TZS','USD','KES','EUR']='TZS'
    description:str|None=Field(default=None,max_length=600)

@profile_router.post('/animals/{animal_id}/costs',status_code=201)
def add_animal_operating_cost(animal_id:int,p:FatteningAnimalCostIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=permission(ctx,db,'finance.write',True)
    animal=db.query(V5Animal).filter_by(organization_id=org.id,id=animal_id).with_for_update().first()
    if not animal:raise HTTPException(404,'Animal not found')
    if animal.status!='active':raise HTTPException(409,'Add costs to an active animal only; use audited financial adjustments for sold animals')
    batch=db.query(V5Batch).filter_by(organization_id=org.id,id=animal.batch_id).first()
    if not batch or not batch.project_id:raise HTTPException(409,'Animal must have a project-linked batch')
    if p.category.strip().lower() in ('animal purchase','animal procurement','livestock sales','selling expenses','cogs','cost of sales'):
        raise HTTPException(422,'Use procurement/sales transactions for this category to prevent double posting')
    entry=FinanceEntry(organization_id=org.id,batch_id=batch.id,animal_id=animal.id,
       kind='cost',category=p.category.strip(),amount=p.amount,currency=p.currency,
       note=p.description,source_type='fattening_animal_operating_cost',created_by=user.id)
    db.add(entry);db.flush()
    audit(db,user.id,'fattening_animal_operating_cost','v5_finance_entry',entry.id,
          f'animal {animal.tag}; batch {batch.id}; project {batch.project_id}; {p.category}')
    db.commit()
    from modules.fattening.service import animal_profile
    return {'id':entry.id,'animal_id':animal.id,'batch_id':batch.id,'project_id':batch.project_id,
        'amount':float(entry.amount),'currency':entry.currency,
        'animal_break_even':animal_profile(db,org.id,animal.id)['break_even'],
        'message':'Cost posted once to Finance and reflected in animal, batch and project reports'}


@profile_router.post('/animals/{animal_id}/sale/confirm',status_code=201)
def confirm_reviewed_sale(animal_id:int,p:SaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    # New UI requires a reviewed server snapshot. V5 compatibility endpoint remains
    # in place for older integrations but cannot bypass currency validation.
    if not p.preview_token:
        raise HTTPException(422,'Review animal costs and break-even before confirming the sale')
    return sell_animal(animal_id,p,db,ctx)


@profile_router.get('/sales/accounting')
def sales_accounting_register(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'finance.read')
    sales=db.query(AnimalSale).filter_by(organization_id=org.id).order_by(AnimalSale.id.desc()).limit(2000).all()
    ids=[s.id for s in sales]; animal_ids=[s.animal_id for s in sales]
    snapshots=(db.query(FatteningSaleCostSnapshot).filter(FatteningSaleCostSnapshot.organization_id==org.id,
        FatteningSaleCostSnapshot.sale_id.in_(ids)).all() if ids else [])
    animals=(db.query(V5Animal).filter(V5Animal.organization_id==org.id,V5Animal.id.in_(animal_ids)).all() if animal_ids else [])
    bysale={snap.sale_id:_json.loads(snap.cost_snapshot_json) for snap in snapshots}
    byanimal={a.id:a for a in animals}
    out=[]
    for sale in sales:
        animal=byanimal.get(sale.animal_id);snapshot=bysale.get(sale.id)
        out.append({**sale_dict(sale,animal.tag if animal else None),
          'project_id':snapshot.get('project_id') if snapshot else None,
          'current_weight_kg':snapshot.get('latest_weight_kg') if snapshot else None,
          'purchase_cost':snapshot.get('purchase_cost') if snapshot else None,
          'direct_costs':snapshot.get('direct_costs') if snapshot else None,
          'allocated_batch_costs':snapshot.get('allocated_batch_costs') if snapshot else None,
          'animal_break_even':snapshot.get('animal_break_even') if snapshot else None,
          'total_break_even':snapshot.get('total_break_even') if snapshot else None,
          'profit_loss':snapshot.get('projected_profit_loss') if snapshot else None,
          'margin_percent':snapshot.get('margin_percent') if snapshot else None,
          'cost_snapshot_available':snapshot is not None})
    return {'items':out,'note':'Financial costs are immutable at the sale date for V7.6 sales. Earlier sales without snapshots show unavailable instead of invented historical costs.'}
