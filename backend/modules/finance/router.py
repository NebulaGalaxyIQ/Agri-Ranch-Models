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
from modules.fattening.models import router

# Operational endpoints extracted from the shared V5-era operations handler.
# Their implementation now lives with the owning business module.
_original_router = globals().get('router')
from modules.fattening.models import *
if _original_router is not None: router = _original_router
operations_router=APIRouter(prefix='/api/v5',tags=['finance operations'])


@operations_router.get('/finance')
def finances(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'finance.read')
    rows=db.query(FinanceEntry).filter_by(organization_id=org.id).order_by(FinanceEntry.id.desc()).limit(1000).all()
    return {'items':[dict(id=x.id,kind=x.kind,category=x.category,amount=float(x.amount),currency=x.currency,batch_id=x.batch_id,animal_id=x.animal_id,note=x.note,source=x.source_type,source_id=x.source_id) for x in rows]}


@operations_router.post('/finance',status_code=201)
def add_finance(p:FinanceIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'finance.write',True);batch_check(db,org,p.batch_id)
    if p.category.strip().casefold() in {'livestock sales','animal sales','sale of animals','animal sale','animal procurement','inventory purchased','feed consumption','stock issue','selling expenses','sales cancellation'}:
        raise HTTPException(422,'Animal sales, procurement and inventory-related transactions are recorded automatically in their operational modules. Select the animal and use Animals → Sell animal.')
    x=FinanceEntry(organization_id=org.id,created_by=user.id,source_type='manual',**p.model_dump());db.add(x);db.flush();audit(db,user.id,'finance_create','v5_finance',x.id,p.kind)
    from modules.platform_admin.service import complete_recorded_staff_duties
    complete_recorded_staff_duties(db,org,user,'finance')
    db.commit();return {'id':x.id}
