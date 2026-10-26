"""V5 tenant-safe API. Legacy V4 APIs are deliberately owner-only until migrated.

The V5 tables are strictly tenant scoped and never accept a tenant id from a request body.
"""
from __future__ import annotations
import hashlib
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, User, UserSession, get_db, utcnow
from auth import PH, get_current_user, hash_token, aware_utc, audit

from modules.organizations.models import Organization, Membership, V5Ranch, V5Batch, V5Routine
from modules.subscriptions.models import Subscription, LicenseKey










PERMS={
 'org_admin': {'*'}, 'manager': {'crops.read','crops.write','livestock.read','livestock.write','gardening.read','gardening.write','machinery.read','machinery.write','routine.read','routine.write','ranch.manage','projects.read','projects.manage','members.read','animals.read','animals.manage','stock.read','stock.write','rations.read','rations.write','finance.read','finance.write','tasks.manage','analytics.read'},
 'feeding_recorder': {'routine.feeding','routine.read'}, 'weighing_recorder': {'routine.weighing','routine.read'}, 'movement_recorder': {'routine.movement','routine.read'},
 'storekeeper': {'routine.read','stock.read','stock.write'}, 'veterinary': {'routine.medication','routine.health','routine.dipping','routine.read'},
 'worker': {'routine.feeding','routine.watering','routine.cleaning','routine.dipping','routine.read'},
 'cleaner': {'routine.cleaning','routine.read'}, 'gardener': {'routine.maintenance','routine.other','routine.read','gardening.read','gardening.write'},
 'crop_worker': {'crops.read','crops.write'}, 'livestock_keeper': {'livestock.read','livestock.write'}, 'mechanic': {'machinery.read','machinery.write'},
 'department_head': {'tasks.manage','routine.read','analytics.read'},
 'finance': {'finance.read','finance.write','analytics.read'},
 'nutritionist': {'rations.read','rations.write','routine.read','stock.read'},
 'viewer': {'routine.read','projects.read','animals.read','stock.read','rations.read','finance.read','analytics.read'},
}
CATEGORIES={'feeding','watering','cleaning','dipping','medication','weighing','health','movement','inspection','maintenance','other'}










from modules.organizations.schemas import OrgIn, OrgDecision, KeyIn, RedeemIn, MemberIn, MemberPatch, RanchIn, BatchIn, RoutineIn

def owner(user: User=Depends(get_current_user)) -> User:
    # Owner is exclusively the original bootstrap administrator; role changes cannot confer ownership.
    if user.role != 'platform_owner':
        raise HTTPException(403,'Platform owner only')
    return user

def org_dict(o):
    return {k:getattr(o,k) for k in ['id','name','email','country','phone','status','registration_number','tax_number','region','district','address','billing_email','livestock_types']}

def context(request: Request, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role=='platform_owner':raise HTTPException(403,'Platform administrators use the owner portal, not organization operations')
    org_id=request.headers.get('x-organization-id')
    if not org_id or not org_id.isdecimal():
        raise HTTPException(400,'Select an organization (X-Organization-ID header)')
    member=db.query(Membership).filter_by(organization_id=int(org_id),user_id=user.id,active=True).first()
    if not member: raise HTTPException(403,'Not a member of this organization')
    org=db.get(Organization,int(org_id))
    if not org or org.status!='approved': raise HTTPException(403,'Organization is not approved')
    from modules.platform_admin.service import effective_role_permissions
    member._v57_permissions=effective_role_permissions(db,member)
    from modules.cape_access.service import active
    if not active(db,org.id):
        raise HTTPException(402,'Subscription inactive. Open Subscription & Licensing to activate a valid product key or eligible trial.')
    return user,org,member

def billing_context(request: Request, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    """Allowed for subscription status/activation when entitlement has expired."""
    if user.role=='platform_owner':raise HTTPException(403,'Platform administrators use the owner portal')
    org_id=request.headers.get('x-organization-id','')
    if not org_id.isdecimal():raise HTTPException(400,'Select an organization')
    member=db.query(Membership).filter_by(organization_id=int(org_id),user_id=user.id,active=True).first()
    if not member:raise HTTPException(403,'Not a member of this organization')
    org=db.get(Organization,int(org_id))
    if not org:raise HTTPException(404,'Organization not found')
    return user,org,member

def permitted(member,action):
    allowed=PERMS.get(member.role,set()) | set(filter(None,(member.permissions or '').split(','))) | getattr(member,'_v57_permissions',set())
    if '*' not in allowed and action not in allowed:
        raise HTTPException(403,'Insufficient organization permission')

def licensed(db,org,write=True):
    sub=db.get(Subscription,org.id)
    if not sub or sub.suspended or not sub.expires_at or aware_utc(sub.expires_at)<=utcnow():
        if write: raise HTTPException(402,'Subscription inactive or expired; renew access')
    return sub

def record_dict(r):
    return dict(id=r.id,category=r.category,shift=r.shift,batch_id=r.batch_id,pen_id=r.pen_id,frequency=r.frequency,animal_tag=r.animal_tag,product=r.product,quantity=r.quantity,unit=r.unit,notes=r.notes,recorded_by=r.recorded_by,created_at=r.created_at.isoformat())















def batch_summary(db: Session, batch: V5Batch) -> dict:
    from modules.fattening.models import V5Animal
    active=db.query(V5Animal).filter_by(organization_id=batch.organization_id,batch_id=batch.id,status='active').count()
    return dict(id=batch.id,name=batch.name,ranch_id=batch.ranch_id,project_id=batch.project_id,
                capacity=batch.capacity,animal_count=active,available_capacity=max(0,batch.capacity-active) if batch.capacity else None,
                start_date=batch.start_date.isoformat() if batch.start_date else None,
                end_date=batch.end_date.isoformat() if batch.end_date else None,
                description=batch.description,status=batch.status)
