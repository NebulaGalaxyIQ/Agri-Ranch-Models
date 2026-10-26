"""V5.7 role builder, customer support, platform oversight and feature adoption.
All organization-facing reads/writes are scoped by the authenticated membership.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, User, AuditLog, get_db, utcnow
from modules.organizations.service import Organization, Membership, Subscription, LicenseKey, V5Ranch, V5Batch, context, licensed, owner, PERMS, permitted
from auth import audit, aware_utc

# Canonical ORM classes are owned by their respective domains.
from modules.employees.models import OrgRole, MemberRole
from modules.help_center.models import SupportTicket, SupportMessage, SupportAttachment
from modules.platform_admin.models import FeatureUsage


router=APIRouter(prefix='/api/v5',tags=['V5.7 platform, roles and help'])






# A limited, auditable menu of grantable permissions. The wildcard cannot be delegated.
ASSIGNABLE={
 'routine.read','routine.feeding','routine.watering','routine.cleaning','routine.dipping',
 'routine.medication','routine.weighing','routine.health','routine.movement',
 'routine.inspection','routine.maintenance','routine.other','ranch.manage',
 'crops.read','crops.write','livestock.read','livestock.write','gardening.read','gardening.write','machinery.read','machinery.write',
 'projects.read','projects.manage','animals.read','animals.manage',
 'stock.read','stock.write','rations.read','rations.write',
 'finance.read','finance.write','tasks.manage','analytics.read','members.read'
}
ROLE_TEMPLATES={
 'veterinary':['routine.read','routine.medication','routine.dipping','routine.health'],
 'weighing':['routine.read','routine.weighing'],
 'feeding':['routine.read','routine.feeding'],
 'movement':['routine.read','routine.movement'],
 'storekeeper':['stock.read','stock.write'],
 'finance':['finance.read','finance.write','analytics.read'],
 'manager':['crops.read','crops.write','livestock.read','livestock.write','gardening.read','gardening.write','machinery.read','machinery.write','ranch.manage','projects.read','projects.manage','animals.read','animals.manage','stock.read','rations.read','finance.read','tasks.manage','analytics.read','routine.read'],
 'department_head':['tasks.manage','routine.read','analytics.read'],
 'cleaner':['routine.read','routine.cleaning'],
 'gardener':['routine.read','routine.maintenance','routine.other','gardening.read','gardening.write'],
 'crop_worker':['crops.read','crops.write'],
 'livestock_keeper':['livestock.read','livestock.write'],
 'mechanic':['machinery.read','machinery.write'],
 'other':['routine.read']}

class RoleIn(BaseModel):
 name:str=Field(min_length=2,max_length=90)
 permissions:list[str]=Field(default_factory=list,max_length=45)

class AssignRolesIn(BaseModel):
 role_ids:list[int]=Field(default_factory=list,max_length=30)

class TicketIn(BaseModel):
 subject:str=Field(min_length=5,max_length=200)
 message:str=Field(min_length=5,max_length=5000)
 category:Literal['technical','billing','training','data','feature_request','other']='technical'
 priority:Literal['low','normal','high','urgent']='normal'

class ReplyIn(BaseModel):
 message:str=Field(min_length=2,max_length=10000)
 internal:bool=False

class StatusIn(BaseModel):
 status:Literal['open','in_progress','waiting_customer','resolved','closed']
 assigned_to:int|None=None


def effective_role_permissions(db:Session,member:Membership):
    """Custom role permissions are resolved per request, never trusted from the client."""
    ids=[r.role_id for r in db.query(MemberRole).filter_by(membership_id=member.id)]
    rows=db.query(OrgRole).filter(OrgRole.id.in_(ids),OrgRole.organization_id==member.organization_id).all() if ids else []
    return set().union(*(set(filter(None,r.permissions.split(','))) for r in rows)) if rows else set()

@router.get('/roles')
def roles(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;licensed(db,org,False)
    # Only org management may see roles, because the directory lists authorization policies.
    if m.role!='org_admin':permitted(m,'members.read')
    custom=db.query(OrgRole).filter_by(organization_id=org.id).order_by(OrgRole.name).all()
    assignments=db.query(MemberRole).join(OrgRole,OrgRole.id==MemberRole.role_id).filter(OrgRole.organization_id==org.id).all()
    grouped={}
    for x in assignments:grouped.setdefault(x.membership_id,[]).append(x.role_id)
    return {'templates':ROLE_TEMPLATES,'allowed_permissions':sorted(ASSIGNABLE),'items':[
      {'id':r.id,'name':r.name,'permissions':list(filter(None,r.permissions.split(',')))} for r in custom],
      'assignments':grouped}

@router.post('/roles',status_code=201)
def create_role(p:RoleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org)
    if m.role!='org_admin':raise HTTPException(403,'Organization administrator required')
    permissions=set(p.permissions)
    if not permissions.issubset(ASSIGNABLE):raise HTTPException(422,'Unsupported permission selected')
    name=p.name.strip()
    if db.query(OrgRole).filter(func.lower(OrgRole.name)==name.lower(),OrgRole.organization_id==org.id).first():raise HTTPException(409,'Role already exists')
    r=OrgRole(organization_id=org.id,name=name,permissions=','.join(sorted(permissions)),created_by=user.id)
    db.add(r);db.flush();audit(db,user.id,'role_created','v57_org_role',r.id,name);db.commit()
    return {'id':r.id,'name':r.name,'permissions':sorted(permissions)}

@router.put('/members/{member_id}/roles')
def assign_roles(member_id:int,p:AssignRolesIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org)
    if m.role!='org_admin':raise HTTPException(403,'Organization administrator required')
    member=db.query(Membership).filter_by(id=member_id,organization_id=org.id).first()
    if not member:raise HTTPException(404,'Employee membership not found')
    ids=set(p.role_ids)
    matching=db.query(OrgRole).filter(OrgRole.organization_id==org.id,OrgRole.id.in_(ids)).count() if ids else 0
    if matching!=len(ids):raise HTTPException(422,'One or more roles belong to a different organization')
    db.query(MemberRole).filter_by(membership_id=member.id).delete(synchronize_session=False)
    for role_id in ids:db.add(MemberRole(membership_id=member.id,role_id=role_id))
    audit(db,user.id,'role_assignment','v5_membership',member.id,','.join(map(str,sorted(ids))))
    db.commit();return {'membership_id':member.id,'role_ids':sorted(ids),'message':'Employee roles updated'}














@router.get('/platform/organization-detail/{org_id}')
def organization_detail(org_id:int,db:Session=Depends(get_db),user:User=Depends(owner)):
 from modules.fattening.models import V5Animal
 from modules.fattening.service import V5Project
 org=db.get(Organization,org_id)
 if not org:raise HTTPException(404,'Organization not found')
 members=db.query(Membership).filter_by(organization_id=org.id).all()
 usage=db.query(FeatureUsage).filter_by(organization_id=org.id).order_by(FeatureUsage.actions.desc()).all()
 subscription=db.get(Subscription,org.id)
 tickets=db.query(SupportTicket).filter_by(organization_id=org.id).count()
 return {'organization':{k:getattr(org,k) for k in ('id','name','trading_name','country','email','phone','registration_number','tax_number','region','district','address','status')},
 'subscription':{'plan':subscription.plan,'expires_at':subscription.expires_at.isoformat() if subscription.expires_at else None,
  'max_employees':subscription.max_employees,'suspended':subscription.suspended} if subscription else None,
 'employees':[{'id':m.id,'name':db.get(User,m.user_id).full_name,'email':db.get(User,m.user_id).email,
  'role':m.role,'active':m.active,'last_login':db.get(User,m.user_id).last_login.isoformat() if db.get(User,m.user_id).last_login else None} for m in members],
 'counts':{'ranches':db.query(V5Ranch).filter_by(organization_id=org.id).count(),
 'projects':db.query(V5Project).filter_by(organization_id=org.id).count(),
 'batches':db.query(V5Batch).filter_by(organization_id=org.id).count(),
 'animals':db.query(V5Animal).filter_by(organization_id=org.id).count(),
 'support_tickets':tickets},
 'usage':[{'feature':r.feature,'actions':r.actions,'last_used_at':r.last_used_at.isoformat()} for r in usage],
 'unused_features':sorted(set(['routines','animals','inventory','feed','finance','sales','tasks','reports','projects','batches','crops','gardening','machinery','livestock'])-{x.feature for x in usage})}

@router.get('/platform/insights')
def owner_insights(db:Session=Depends(get_db),user:User=Depends(owner)):
 now=utcnow()
 orgs=db.query(Organization).all()
 subs=db.query(Subscription).all()
 expiring=[{'organization_id':s.organization_id,'name':next((o.name for o in orgs if o.id==s.organization_id),''),
 'expires_at':s.expires_at.isoformat(),'days_remaining':round((aware_utc(s.expires_at)-now).total_seconds()/86400,1)} for s in subs
 if s.expires_at and now<=aware_utc(s.expires_at)<=now+timedelta(days=30)]
 usage=db.query(FeatureUsage.feature,func.sum(FeatureUsage.actions)).group_by(FeatureUsage.feature).all()
 return {'organizations':len(orgs),'approved':sum(o.status=='approved' for o in orgs),
 'active_subscriptions':sum(bool(s.expires_at and aware_utc(s.expires_at)>now and not s.suspended) for s in subs),
 'open_tickets':db.query(SupportTicket).filter(SupportTicket.status.notin_(['resolved','closed'])).count(),
 'expiring':sorted(expiring,key=lambda x:x['expires_at']),
 'features':[{'feature':f,'actions':int(n)} for f,n in sorted(usage,key=lambda x:x[1],reverse=True)],
 'unused_features':sorted(set(['routines','animals','inventory','feed','finance','sales','tasks','reports','projects','batches','crops','gardening','machinery','livestock'])-{f for f,n in usage})}

@router.get('/access')
def my_access(db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,m=ctx
 permissions=PERMS.get(m.role,set()) | set(filter(None,(m.permissions or '').split(','))) | effective_role_permissions(db,m)
 if '*' in permissions:permissions=ASSIGNABLE|{'members.manage','subscription.manage'}
 return {'role':m.role,'permissions':sorted(permissions),'organization_id':org.id}

# Optional screenshots/documents: strict access checks; no public file URL.
from fastapi import File, UploadFile
from fastapi.responses import Response
from sqlalchemy import LargeBinary
import os










def complete_recorded_staff_duties(db,org,user,category):
 """Mark today's matching non-routine assignments after a successful operational write."""
 from datetime import date
 from modules.fattening.models import Task
 from modules.inventory.service import TaskCompletion,task_due
 today=date.today()
 rows=db.query(Task).filter_by(organization_id=org.id,assigned_to=user.id,category=category).all()
 completed=0
 for task in rows:
  if task_due(task,today) and not db.query(TaskCompletion).filter_by(organization_id=org.id,task_id=task.id,occurrence_date=today).first():
   db.add(TaskCompletion(organization_id=org.id,task_id=task.id,occurrence_date=today,completed_by=user.id))
   if task.frequency=='once':task.status='completed'
   task.completed_by=user.id;task.completed_at=utcnow()
   audit(db,user.id,'automatic_task_completion','v5_task',task.id,f'{category} recorded')
   completed+=1
 return completed

@router.get('/platform/audit/summary')
def owner_audit_summary(db:Session=Depends(get_db),user:User=Depends(owner)):
    """Platform-level audit browsing without exposing customer operational records."""
    rows=(db.query(AuditLog,User.full_name)
          .outerjoin(User,User.id==AuditLog.user_id)
          .order_by(AuditLog.id.desc()).limit(250).all())
    return {'items':[{'id':r.id,'created_at':r.created_at.isoformat() if r.created_at else None,
                      'actor':name or 'System','action':r.action,'entity_type':r.entity_type,
                      'entity_id':r.entity_id,'description':r.description} for r,name in rows]}
