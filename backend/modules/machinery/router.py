"""Domain-owned operational endpoints.
Uses shared records and permissions without cross-tenant access.
"""
from __future__ import annotations
from datetime import date,datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import audit
from modules.organizations.service import context
from modules.crops.models import *
from modules.crops.models import scope,linked,ranch,result,rowdata,saved
from modules.livestock.models import *
from modules.gardening.models import *
from modules.machinery.models import *
router=APIRouter(prefix='/api/v6',tags=['machinery'])


@router.get('/machinery/assets')
def machines(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'machinery');return result(db,Machine,o)


@router.post('/machinery/assets',status_code=201)
def create_machine(p:MachineIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'machinery',True);ranch(db,o,p.ranch_id)
    if db.query(Machine).filter_by(organization_id=o.id,asset_code=p.asset_code).first():raise HTTPException(409,'Asset code already exists')
    return saved(db,a,Machine,Machine(organization_id=o.id,**p.model_dump()),'machine_registered')


@router.get('/machinery/records')
def machine_records(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'machinery');return result(db,MachineRecord,o)


@router.post('/machinery/records',status_code=201)
def machine_log(p:MachineLogIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'machinery',True);linked(db,Machine,o,p.machine_id,'Machine')
    if p.action=='operation' and p.meter_hours is None:raise HTTPException(422,'Hours are required for equipment operation')
    obj=MachineRecord(organization_id=o.id,recorded_by=a.id,**p.model_dump())
    db.add(obj);db.flush()
    if p.expense>0:
        from modules.fattening.models import FinanceEntry
        db.add(FinanceEntry(organization_id=o.id,batch_id=None,kind='cost',category='Machinery '+p.action,amount=p.expense,currency=p.currency,note=p.notes,source_type='v6_machine_record',source_id=obj.id,created_by=a.id))
    audit(db,a.id,'machine_activity_recorded','v6_machine_records',obj.id);out=rowdata(obj);db.commit()
    return {'item':out,'message':'Equipment activity and attributed cost recorded'}
