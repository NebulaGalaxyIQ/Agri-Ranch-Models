from __future__ import annotations
from datetime import date,datetime
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from modules.organizations.service import context
from auth import audit
"""Established router remains active; avoid duplicate mounting."""
from modules.reports.service import router

# Domain-specific API endpoints and their shared transaction dependencies.

from modules.crops.service import *
from modules.crops.models import scope,rowdata
from modules.crops.router import crop_profitability, crop_inputs
from modules.livestock.router import livestock_products,livestock_product_sales,livestock_project_performance

extra_router=APIRouter(prefix="/api/v6",tags=["reports"] )
@extra_router.get('/reports/operations.csv')
def operations_report(section:Literal['crop_profitability','crop_inputs','livestock_products','livestock_product_sales','livestock_project_performance'],
                      db:Session=Depends(get_db),ctx=Depends(context)):
    """Single permission-checked export for production details; currency rows stay separate."""
    import csv,io
    from fastapi.responses import StreamingResponse
    scope(db,ctx,'crops' if section.startswith('crop') else 'livestock')
    if section=='crop_profitability':
        original=crop_profitability(db,ctx)['items']
        rows=[{'crop':x['crop'],'cycle_id':x['cycle_id'],'field_id':x['field_id'],
               'harvested_kg':x['harvested_kg'],'sold_kg':x['sold_kg'],'unsold_kg':x['unsold_kg'],
               **c} for x in original for c in (x['currencies'] or [{'currency':'','recorded_inputs':0,'activity_costs':0,'revenue':0,'contribution':0}])]
    elif section=='crop_inputs':rows=crop_inputs(db,ctx)['items']
    elif section=='livestock_products':rows=livestock_products(db,ctx)['items']
    elif section=='livestock_product_sales':rows=livestock_product_sales(db,ctx)['items']
    else:
        original=livestock_project_performance(db,ctx)['items']
        rows=[{'project':x['name'],'project_id':x['project_id'],'groups':x['groups'],**c} for x in original for c in (x['currencies'] or [{'currency':'','direct_costs':0,'activity_costs':0,'product_revenue':0,'animal_sales':0,'recorded_contribution':0}])]
    cols=list(dict.fromkeys(k for row in rows for k in row)) or ['no_records']
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    return StreamingResponse(iter([out.getvalue().encode('utf-8-sig')]),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{section}.csv"','Cache-Control':'no-store'})


# Operational endpoints extracted from the shared V5-era operations handler.
# Their implementation now lives with the owning business module.
_original_router = globals().get('router')
from modules.fattening.models import *
if _original_router is not None: router = _original_router
operations_router=APIRouter(prefix='/api/v5',tags=['reports operations'])


@operations_router.get('/analytics/overview')
def overview(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    entries=db.query(FinanceEntry).filter_by(organization_id=org.id).all()
    c=sum((x.amount for x in entries if x.kind=='cost'),Decimal(0));r=sum((x.amount for x in entries if x.kind=='revenue'),Decimal(0))
    return {'ranches':db.query(V5Ranch).filter_by(organization_id=org.id).count(),'batches':db.query(V5Batch).filter_by(organization_id=org.id).count(),'animals':db.query(V5Animal).filter_by(organization_id=org.id,status='active').count(),'routines':db.query(V5Routine).filter_by(organization_id=org.id).count(),'tasks_pending':db.query(Task).filter_by(organization_id=org.id,status='pending').count(),'recorded_costs':float(c),'recorded_revenue':float(r),'recorded_profit':float(r-c),'note':'Summary reflects explicitly recorded V5 transactions; it does not infer unrecorded expenses, sales, or consumption.'}
