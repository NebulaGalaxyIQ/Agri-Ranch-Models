from __future__ import annotations
from datetime import date,datetime
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from modules.organizations.service import context
from auth import audit
"""Single-use organization staff recovery codes. No password is ever returned to an administrator.
Delivery of the one-time code uses an administrator-verified channel (not email by default).
"""
from datetime import datetime,timedelta
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped,mapped_column,Session
from database import Base,User,UserSession,get_db,utcnow
from modules.organizations.service import Membership,context,licensed
from auth import PH,hash_token,audit,aware_utc

# Canonical ORM classes are owned by their respective domains.
from modules.employees.models import RecoveryCode


router=APIRouter(prefix='/api/v5',tags=['employee account recovery'])


class CompleteReset(BaseModel):
    code:str=Field(min_length=30,max_length=200)
    new_password:str=Field(min_length=10,max_length=128)

@router.post('/members/{membership_id}/password-reset',status_code=201)
def initiate_staff_reset(membership_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,m=ctx;licensed(db,org,False)
    if m.role!='org_admin':raise HTTPException(403,'Only the organization administrator may issue staff recovery codes')
    target=db.query(Membership).filter_by(id=membership_id,organization_id=org.id,active=True).first()
    if not target:raise HTTPException(404,'Active employee not found')
    if target.role=='org_admin':raise HTTPException(403,'Administrator recovery requires verified platform support')
    # Invalidate all older, unredeemed reset codes issued for this membership.
    db.query(RecoveryCode).filter_by(membership_id=target.id,used_at=None).update({'used_at':utcnow()})
    raw=secrets.token_urlsafe(36)
    ticket=RecoveryCode(organization_id=org.id,membership_id=target.id,user_id=target.user_id,
                        token_hash=hash_token(raw),expires_at=utcnow()+timedelta(minutes=30))
    db.add(ticket);db.flush()
    audit(db,actor.id,'staff_password_reset_issued','v5_membership',target.id,'Single-use recovery code issued')
    db.commit()
    return {'recovery_code':raw,'expires_in_minutes':30,'message':'Give this code to the employee through a verified private channel. It is displayed once only.'}

@router.post('/auth/password-reset/complete')
def complete_staff_reset(p:CompleteReset,db:Session=Depends(get_db)):
    token=db.query(RecoveryCode).filter_by(token_hash=hash_token(p.code.strip())).with_for_update().first()
    if not token or token.used_at or aware_utc(token.expires_at)<=utcnow():
        raise HTTPException(400,'Invalid or expired recovery code')
    member=db.query(Membership).filter_by(id=token.membership_id,user_id=token.user_id,organization_id=token.organization_id,active=True).first()
    user=db.get(User,token.user_id)
    if not member or not user or not user.is_active:raise HTTPException(403,'Account is unavailable')
    user.password_hash=PH.hash(p.new_password)
    user.failed_login_attempts=0;user.locked_until=None
    token.used_at=utcnow()
    db.query(UserSession).filter_by(user_id=user.id).delete(synchronize_session=False)
    audit(db,user.id,'staff_password_reset_completed','v5_membership',member.id,'Password changed using single-use code')
    db.commit()
    return {'message':'Password updated. Sign in with your new password.'}

# Operational endpoints extracted from the shared V5-era operations handler.
# Their implementation now lives with the owning business module.
_original_router = globals().get('router')
from modules.fattening.models import *
if _original_router is not None: router = _original_router
operations_router=APIRouter(prefix='/api/v5',tags=['employees operations'])


@operations_router.get('/tasks')
def tasks(db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False)
    query=db.query(Task).filter_by(organization_id=org.id)
    if m.role not in ('org_admin','manager'):query=query.filter(Task.assigned_to==user.id)
    from modules.inventory.service import TaskCompletion,task_due
    rows=query.order_by(Task.id.desc()).limit(500).all()
    today=date.today()
    records={(r.task_id,r.occurrence_date) for r in db.query(TaskCompletion).filter_by(organization_id=org.id,occurrence_date=today).all()}
    return {'items':[dict(id=x.id,title=x.title,category=x.category,shift=x.shift,frequency=x.frequency,
        status=('completed' if (x.id,today) in records else 'pending' if x.frequency!='once' and task_due(x,today) else x.status),
        assigned_to=x.assigned_to,batch_id=x.batch_id,pen_id=x.pen_id,due_date=x.due_date.isoformat() if x.due_date else None,
        completed_by=x.completed_by,completed_at=x.completed_at.isoformat() if x.completed_at else None) for x in rows]}


@operations_router.post('/tasks',status_code=201)
def add_task(p:TaskIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'tasks.manage',True);batch_check(db,org,p.batch_id)
    if p.category=='cleaning':
        from modules.fattening.schemas import Pen
        pen=db.query(Pen).filter_by(id=p.pen_id,organization_id=org.id,status='active').first()
        if not pen:raise HTTPException(422,'Cleaning tasks require a registered pen')
        if p.batch_id and p.batch_id!=pen.batch_id:raise HTTPException(422,'Pen does not belong to chosen batch')
        p.batch_id=pen.batch_id;p.shift='Other'
    elif p.pen_id is not None:raise HTTPException(422,'Only cleaning tasks use a pen')
    if p.category not in ('feeding','watering'):
        p.shift='Other'
    if p.assigned_to is not None:
        from modules.organizations.service import Membership
        member=db.query(Membership).filter_by(organization_id=org.id,user_id=p.assigned_to,active=True).first()
        if not member:raise HTTPException(404,'Assigned employee not found')
        from modules.organizations.service import permitted
        from modules.platform_admin.service import effective_role_permissions
        member._v57_permissions=effective_role_permissions(db,member)
        if p.category in ('stock_receive','stock_out','finance') and member.role not in ('org_admin','manager'):
            permitted(member,'stock.write' if p.category.startswith('stock_') else 'finance.write')
        if p.category in ('feeding','watering','cleaning','dipping','medication','weighing','health','movement','inspection','maintenance','other') and member.role not in ('org_admin','manager'):
            permitted(member,'routine.'+p.category)
    x=Task(organization_id=org.id,**p.model_dump());db.add(x);db.flush();audit(db,user.id,'task_create','v5_task',x.id,x.title)
    if p.assigned_to:
        from modules.fattening.service import alert
        alert(db,org,'task','New task assigned',x.title,p.assigned_to)
    db.commit();return {'id':x.id}


@operations_router.post('/tasks/{task_id}/complete')
def complete(task_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    x=db.query(Task).filter_by(id=task_id,organization_id=org.id).first()
    if not x:raise HTTPException(404,'Task not found')
    if m.role not in ('org_admin','manager') and x.assigned_to!=user.id:raise HTTPException(403,'Task not assigned to you')
    from modules.inventory.service import TaskCompletion,task_due
    today=date.today()
    if (x.frequency!='once' and not task_due(x,today)) or (x.frequency=='once' and x.due_date and today<x.due_date):
        raise HTTPException(409,'Task is not due yet')
    previous=db.query(TaskCompletion).filter_by(organization_id=org.id,task_id=x.id,occurrence_date=today).first()
    if previous:return {'id':x.id,'status':'completed','completion_id':previous.id,'message':'Already completed today'}
    if x.frequency=='once' and x.status=='completed':return {'id':x.id,'status':'completed','message':'Already completed'}
    if m.role not in ('org_admin','manager') and x.category in ('stock_receive','stock_out','finance'):
        from sqlalchemy import func as sqlfunc
        from datetime import datetime,time,timedelta
        start=datetime.combine(today,time.min);end=start+timedelta(days=1)
        if x.category=='finance':
            record=db.query(FinanceEntry).filter(FinanceEntry.organization_id==org.id,
               FinanceEntry.created_by==user.id,FinanceEntry.source_type=='manual',
               FinanceEntry.created_at>=start,FinanceEntry.created_at<end).first()
        else:
            record=db.query(StockMovement).filter(StockMovement.organization_id==org.id,
               StockMovement.recorded_by==user.id,StockMovement.direction==('in' if x.category=='stock_receive' else 'out'),
               StockMovement.created_at>=start,StockMovement.created_at<end).first()
        if not record:raise HTTPException(409,'Complete and save the assigned stock or finance record first')
    # Staff must actually record the work before completion can be claimed.
    # Manager approvals remain explicit administrative actions in the audit.
    if m.role not in ('org_admin','manager') and x.category in {
        'feeding','watering','cleaning','dipping','medication','weighing','health','movement','inspection','maintenance'}:
        from modules.employees.service import day_bounds
        start,end=day_bounds(today)
        q=db.query(V5Routine).filter(V5Routine.organization_id==org.id,
            V5Routine.recorded_by==user.id,V5Routine.category==x.category,
            V5Routine.created_at>=start,V5Routine.created_at<end)
        if x.category in ('feeding','watering'):q=q.filter(V5Routine.shift==x.shift)
        if x.category=='cleaning':q=q.filter(V5Routine.pen_id==x.pen_id)
        if x.batch_id:q=q.filter(V5Routine.batch_id==x.batch_id)
        if not q.first():raise HTTPException(409,'Record the assigned routine first; this task cannot be marked complete without a matching submission')
    if m.role not in ('org_admin','manager') and x.category in {'planting','harvest','crop','gardening','garden','machinery'}:
        # New modules must have an actual dated activity from the assigned worker.
        from modules.crops.models import CropRecord, GardenRecord, MachineRecord
        if x.category in {'planting','harvest','crop'}:
            query=db.query(CropRecord).filter_by(organization_id=org.id,recorded_by=user.id,performed_on=today)
            if x.category in {'planting','harvest'}:query=query.filter_by(action=x.category)
        elif x.category in {'gardening','garden'}:
            query=db.query(GardenRecord).filter_by(organization_id=org.id,recorded_by=user.id,performed_on=today)
        else:
            query=db.query(MachineRecord).filter_by(organization_id=org.id,recorded_by=user.id,performed_on=today)
        if not query.first():raise HTTPException(409,'Save the matching activity record first, then complete this task')
    record=TaskCompletion(organization_id=org.id,task_id=x.id,occurrence_date=today,completed_by=user.id)
    db.add(record);db.flush()
    if x.frequency=='once':x.status='completed'
    x.completed_by=user.id;x.completed_at=utcnow()
    audit(db,user.id,'task_completed','v5_task_completion',record.id,f'{x.title} ({today.isoformat()})')
    db.commit();return {'id':x.id,'status':'completed','completion_id':record.id,'message':'Task completed for today'}
