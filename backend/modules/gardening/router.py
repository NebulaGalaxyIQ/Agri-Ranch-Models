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
router=APIRouter(prefix='/api/v6',tags=['gardening'])


@router.get('/gardening/areas')
def garden_areas(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'gardening');return result(db,GardenArea,o)


@router.post('/gardening/areas',status_code=201)
def create_garden(p:GardenIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'gardening',True);ranch(db,o,p.ranch_id);return saved(db,a,GardenArea,GardenArea(organization_id=o.id,**p.model_dump()),'garden_area_created')


@router.get('/gardening/records')
def garden_records(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'gardening');return result(db,GardenRecord,o)


@router.post('/gardening/records',status_code=201)
def garden_log(p:GardenLogIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'gardening',True);linked(db,GardenArea,o,p.area_id,'Garden area')
    if db.query(GardenRecord).filter_by(organization_id=o.id,area_id=p.area_id,performed_on=p.performed_on,action=p.action).first():
        raise HTTPException(409,'Activity already recorded for this garden and date. Open the existing record to correct it.')
    return saved(db,a,GardenRecord,GardenRecord(organization_id=o.id,recorded_by=a.id,**p.model_dump()),'garden_activity_recorded')
