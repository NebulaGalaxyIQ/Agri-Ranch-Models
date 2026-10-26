"""Organization enrollment, membership, ranch and subscription endpoints."""
from __future__ import annotations
from datetime import date,datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy.orm import Session
from database import get_db,User,utcnow
from auth import audit,PH,hash_token
from modules.organizations.models import *
from modules.subscriptions.models import Subscription,LicenseKey
from modules.organizations.schemas import OrgIn, OrgDecision, KeyIn, RedeemIn, MemberIn, MemberPatch, RanchIn, BatchIn, RoutineIn
from modules.organizations.service import *
router=APIRouter(prefix='/api/v5',tags=['Organization and licensing'])


@router.post('/organizations/register',status_code=201)
def register(payload: OrgIn,db:Session=Depends(get_db)):
    if not db.query(User).first():
        raise HTTPException(403,'Platform owner must complete initial setup before organization registration')
    email=str(payload.admin_email).lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409,'Administrator email already exists; contact support')
    org=Organization(**payload.model_dump(exclude={'admin_name','admin_email','admin_password'}))
    db.add(org); db.flush()
    user=User(full_name=payload.admin_name,email=email,password_hash=PH.hash(payload.admin_password),role='staff',is_active=True)
    db.add(user);db.flush()
    db.add(Membership(organization_id=org.id,user_id=user.id,role='org_admin'))
    db.add(Subscription(organization_id=org.id))
    db.commit()
    return {'organization':org_dict(org),'message':'Registration received; awaiting verification and license activation.'}


@router.get('/organizations')
def my_organizations(db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    memberships=db.query(Membership).filter_by(user_id=user.id,active=True).all()
    return {'items':[dict(**org_dict(db.get(Organization,m.organization_id)),role=m.role) for m in memberships]}


@router.get('/platform/organizations')
def owner_organizations(db:Session=Depends(get_db),_:User=Depends(owner)):
    now=utcnow()
    organizations=db.query(Organization).order_by(Organization.id.desc()).all()
    ids=[o.id for o in organizations]
    subs={x.organization_id:x for x in db.query(Subscription).filter(Subscription.organization_id.in_(ids)).all()} if ids else {}
    keys=db.query(LicenseKey).filter(LicenseKey.organization_id.in_(ids)).order_by(LicenseKey.created_at.desc(),LicenseKey.id.desc()).all() if ids else []
    grouped={}
    for key in keys:
        grouped.setdefault(key.organization_id,[]).append(key)
    items=[]
    for o in organizations:
        sub=subs.get(o.id)
        valid=bool(sub and sub.expires_at and aware_utc(sub.expires_at)>now and not sub.suspended)
        keys_for_org=grouped.get(o.id,[])
        pending=sum(k.redeemed_at is None and k.revoked_at is None for k in keys_for_org)
        latest=keys_for_org[0] if keys_for_org else None
        items.append({**org_dict(o), 'license_status':('active' if valid else 'suspended' if sub and sub.suspended else 'expired' if sub and sub.expires_at else 'not_activated'),
          'expires_at':sub.expires_at.isoformat() if sub and sub.expires_at else None,
          'max_employees':sub.max_employees if sub else 25,
          'issued_keys':len(keys_for_org), 'pending_keys':pending,
          'latest_key_status':('revoked' if latest.revoked_at else 'redeemed' if latest.redeemed_at else 'issued') if latest else 'not_issued',
          'latest_key_days':latest.duration_days if latest else None})
    return {'items':items}


@router.get('/platform/organizations/{org_id}/license-keys')
def owner_license_keys(org_id:int,db:Session=Depends(get_db),_:User=Depends(owner)):
    if not db.get(Organization,org_id): raise HTTPException(404,'Organization not found')
    keys=db.query(LicenseKey).filter_by(organization_id=org_id).order_by(LicenseKey.id.desc()).all()
    return {'items':[{'id':k.id,'duration_days':k.duration_days,'max_employees':k.max_employees,
       'status':'revoked' if k.revoked_at else 'redeemed' if k.redeemed_at else 'issued',
       'created_at':k.created_at.isoformat() if k.created_at else None,
       'redeemed_at':k.redeemed_at.isoformat() if k.redeemed_at else None} for k in keys]}


@router.post('/platform/license-keys/{key_id}/revoke')
def revoke_key(key_id:int,db:Session=Depends(get_db),user:User=Depends(owner)):
    k=db.get(LicenseKey,key_id)
    if not k: raise HTTPException(404,'License key not found')
    if k.redeemed_at: raise HTTPException(409,'Redeemed keys cannot be revoked retroactively; suspend the subscription instead')
    if k.revoked_at: raise HTTPException(409,'License key already revoked')
    k.revoked_at=utcnow()
    audit(db,user.id,'v5_revoke_key','license',k.id,f'org={k.organization_id}')
    db.commit()
    return {'id':k.id,'status':'revoked'}


@router.put('/platform/organizations/{org_id}/verification')
def verify(org_id:int,payload:OrgDecision,db:Session=Depends(get_db),user:User=Depends(owner)):
    org=db.get(Organization,org_id)
    if not org: raise HTTPException(404,'Organization not found')
    org.status=payload.status
    audit(db,user.id,'v5_verification','organization',org.id,payload.status);db.commit()
    return org_dict(org)


@router.post('/platform/license-keys')
def generate_key(payload:KeyIn,db:Session=Depends(get_db),user:User=Depends(owner)):
    org=db.get(Organization,payload.organization_id)
    if not org: raise HTTPException(404,'Organization not found')
    if org.status!='approved': raise HTTPException(409,'Approve organization before issuing a license key')
    raw='CR-'+secrets.token_urlsafe(32)
    obj=LicenseKey(organization_id=org.id,key_hash=hash_token(raw),duration_days=payload.duration_days,max_employees=payload.max_employees)
    db.add(obj);db.flush();audit(db,user.id,'v5_issue_key','license',obj.id, f'org={org.id},days={payload.duration_days},seats={payload.max_employees}');db.commit()
    return {'id':obj.id,'key':raw,'status':'issued','duration_days':obj.duration_days,'max_employees':obj.max_employees,'warning':'Copy now; the plaintext key is never stored or shown again'}


@router.post('/subscription/redeem')
def redeem(payload:RedeemIn,db:Session=Depends(get_db),ctx=Depends(billing_context)):
    user,org,member=ctx;permitted(member,'subscription.manage') if member.role!='org_admin' else None
    # PostgreSQL row lock ensures concurrent redemptions cannot both consume a key.
    key=db.query(LicenseKey).filter_by(key_hash=hash_token(payload.key.strip())).with_for_update().first()
    if not key or key.organization_id!=org.id or key.redeemed_at or key.revoked_at: raise HTTPException(400,'Invalid or already used key')
    existing_seats=db.query(Membership).filter_by(organization_id=org.id,active=True).count()
    if existing_seats>key.max_employees:raise HTTPException(409,'Product key seat limit is below existing active membership count')
    sub=db.query(Subscription).filter_by(organization_id=org.id).with_for_update().one()
    now=utcnow();start=max(now,aware_utc(sub.expires_at)) if sub.expires_at else now
    sub.expires_at=start+timedelta(days=key.duration_days);sub.max_employees=key.max_employees;sub.suspended=False;sub.plan='professional'
    key.redeemed_at=now
    audit(db,user.id,'v5_redeem','organization',org.id,f'key={key.id}; expires={sub.expires_at.isoformat()}');db.commit()
    return {'expires_at':sub.expires_at.isoformat(),'max_employees':sub.max_employees,'plan':sub.plan}


@router.get('/subscription')
def subscription(db:Session=Depends(get_db),ctx=Depends(billing_context)):
    _,org,_=ctx;sub=db.get(Subscription,org.id)
    return {'plan':sub.plan,'max_employees':sub.max_employees,'expires_at':sub.expires_at.isoformat() if sub.expires_at else None,'active':bool(sub.expires_at and aware_utc(sub.expires_at)>utcnow() and not sub.suspended),'suspended':sub.suspended}


@router.get('/members')
def members(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;permitted(m,'members.read')
    return {'items':[{'id':x.id,'user_id':x.user_id,'name':db.get(User,x.user_id).full_name,'email':db.get(User,x.user_id).email,'role':x.role,'active':x.active} for x in db.query(Membership).filter_by(organization_id=org.id).all()]}


@router.post('/members',status_code=201)
def add_member(payload:MemberIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,m=ctx;permitted(m,'members.manage') if m.role!='org_admin' else None
    if payload.role not in PERMS: raise HTTPException(400,'Unknown role')
    sub=db.query(Subscription).filter_by(organization_id=org.id).with_for_update().one();licensed(db,org)
    email=str(payload.email).lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409,'Existing account: invite workflow required')
    if db.query(Membership).filter_by(organization_id=org.id,active=True).count()>=sub.max_employees:raise HTTPException(409,'Employee seat limit reached')
    user=User(full_name=payload.name,email=email,password_hash=PH.hash(payload.password),role='staff',is_active=True)
    db.add(user);db.flush();member=Membership(organization_id=org.id,user_id=user.id,role=payload.role)
    db.add(member);audit(db,actor.id,'v5_add_employee','membership',user.id,f'org={org.id}; role={payload.role}');db.commit()
    return {'id':member.id,'user_id':user.id,'role':member.role}


@router.patch('/members/{member_id}')
def edit_member(member_id:int,payload:MemberPatch,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,m=ctx
    if m.role!='org_admin':raise HTTPException(403,'Organization administrator only')
    member=db.query(Membership).filter_by(id=member_id,organization_id=org.id).first()
    if not member:raise HTTPException(404,'Employee not found')
    if member.id==m.id and payload.active is False:raise HTTPException(400,'Cannot deactivate yourself')
    if payload.role is not None:
        if payload.role not in PERMS:raise HTTPException(400,'Invalid role')
        member.role=payload.role
    if payload.active is not None:
        sub=db.query(Subscription).filter_by(organization_id=org.id).with_for_update().one()
        if payload.active and not member.active and db.query(Membership).filter_by(organization_id=org.id,active=True).count()>=sub.max_employees:raise HTTPException(409,'Employee seat limit reached')
        member.active=payload.active
        if not payload.active:db.query(UserSession).filter_by(user_id=member.user_id).delete()
    audit(db,actor.id,'v5_update_employee','membership',member.id,f'org={org.id}');db.commit()
    return {'id':member.id,'active':member.active,'role':member.role}


@router.get('/ranches')
def ranches(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=ctx;licensed(db,org,False)
    return {'items':[{'id':r.id,'name':r.name,'location':r.location} for r in db.query(V5Ranch).filter_by(organization_id=org.id).all()]}


@router.post('/ranches')
def create_ranch(payload:RanchIn,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,m=ctx;licensed(db,org);permitted(m,'ranch.manage')
    if db.query(V5Ranch).filter(V5Ranch.organization_id==org.id,__import__('sqlalchemy').func.lower(V5Ranch.name)==payload.name.strip().lower()).first():raise HTTPException(409,'Ranch already exists. Select it from the list')
    r=V5Ranch(organization_id=org.id,**payload.model_dump());db.add(r);db.commit();return {'id':r.id}


@router.get('/batches')
def batches(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=ctx;licensed(db,org,False)
    return {'items':[batch_summary(db,b) for b in db.query(V5Batch).filter_by(organization_id=org.id).order_by(V5Batch.id.desc()).all()]}


@router.post('/batches')
def create_batch(payload:BatchIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org);permitted(m,'ranch.manage')
    if payload.end_date and payload.end_date<payload.start_date:raise HTTPException(422,'End date must be on or after start date')
    if payload.project_id is None:raise HTTPException(422,'Create and select a project before creating a batch')
    from modules.fattening.service import V5Project
    project=db.query(V5Project).filter_by(id=payload.project_id,organization_id=org.id).first()
    if not project:raise HTTPException(404,'Project not found')
    if project.ranch_id is None:raise HTTPException(409,'This older project has no ranch. Assign a ranch to the project first')
    ranch_id=project.ranch_id
    if db.query(V5Batch).filter(V5Batch.organization_id==org.id,V5Batch.project_id==project.id,__import__('sqlalchemy').func.lower(V5Batch.name)==payload.name.strip().lower()).first():raise HTTPException(409,'Batch name already exists in this project')
    if payload.start_date<project.start_date:raise HTTPException(422,'Batch start date cannot be before project start date')
    if project.end_date and payload.end_date and payload.end_date>project.end_date:raise HTTPException(422,'Batch end date cannot be after project end date')
    if payload.ranch_id is not None and payload.ranch_id!=ranch_id:raise HTTPException(422,'Batch must inherit the project ranch')
    b=V5Batch(organization_id=org.id,ranch_id=ranch_id,name=payload.name,project_id=payload.project_id,
              capacity=payload.capacity,start_date=payload.start_date,end_date=payload.end_date,
              description=payload.description,status=payload.status,animal_count=0)
    db.add(b);db.flush();audit(db,user.id,'v5_batch_create','v5_batch',b.id,b.name);db.commit()
    return batch_summary(db,b)


@router.get('/routines')
def list_routines(category:str|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False);permitted(m,'routine.read')
    query=db.query(V5Routine).filter_by(organization_id=org.id)
    if category:query=query.filter_by(category=category)
    if m.role not in {'org_admin','manager','viewer'}:query=query.filter_by(recorded_by=user.id)
    return {'items':[record_dict(r) for r in query.order_by(V5Routine.id.desc()).limit(200).all()]}


@router.post('/routines',status_code=201)
def create_routine(payload:RoutineIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    if payload.category not in CATEGORIES:raise HTTPException(400,'Unknown routine category')
    if m.role not in ('org_admin','manager'):permitted(m,'routine.'+payload.category)
    from modules.fattening.models import V5Animal, StockItem, WeightObservation
    from modules.fattening.schemas import Pen, target_key, claim_period, period_limits
    from modules.employees.service import completed_shifts, claim_shift, mark_matching_assignments
    from datetime import datetime, time
    from sqlalchemy import func
    existing=db.query(V5Routine).filter_by(organization_id=org.id,client_reference=payload.client_reference).first()
    if existing:return record_dict(existing)
    if payload.category=='cleaning':
        if payload.animal_id or payload.animal_tag or payload.batch_id:
            raise HTTPException(422,'Cleaning is pen-based. Select only the pen, not an animal or batch')
        pen=db.query(Pen).filter_by(id=payload.pen_id,organization_id=org.id,status='active').first()
        if not pen:raise HTTPException(422,'Choose an active registered pen')
        payload.batch_id=pen.batch_id;payload.shift='Other';payload.quantity=None;payload.unit=None
        payload.product=pen.name
    elif payload.pen_id is not None:
        raise HTTPException(422,'Pen selection applies only to cleaning')
    if payload.animal_id is not None:
        animal=db.query(V5Animal).filter_by(id=payload.animal_id,organization_id=org.id,status='active').first()
        if not animal:raise HTTPException(404,'Selected animal not found or inactive')
        if payload.batch_id is not None and payload.batch_id!=animal.batch_id:raise HTTPException(422,'Animal does not belong to that batch')
        payload.batch_id=animal.batch_id;payload.animal_tag=animal.tag
    elif payload.animal_tag:
        animal=db.query(V5Animal).filter_by(organization_id=org.id,tag=payload.animal_tag,status='active').first()
        if not animal:raise HTTPException(404,'Animal tag is not registered')
        if payload.batch_id is not None and payload.batch_id!=animal.batch_id:raise HTTPException(422,'Animal does not belong to that batch')
        payload.batch_id=animal.batch_id;payload.animal_id=animal.id;payload.animal_tag=animal.tag
    if not payload.batch_id:raise HTTPException(422,'Select a registered batch, animal or pen')
    batch=db.query(V5Batch).filter_by(id=payload.batch_id,organization_id=org.id).with_for_update().first()
    if not batch:raise HTTPException(404,'Batch not found')
    if payload.category=='watering':
        if payload.animal_id:raise HTTPException(422,'Watering is recorded for the batch')
        if payload.shift not in ('Morning','Afternoon','Evening'):raise HTTPException(422,'Choose Morning, Afternoon or Evening')
        payload.quantity=None;payload.unit=None;payload.product=None;payload.frequency='daily'
    if payload.category=='medication':
        item=db.query(StockItem).filter_by(organization_id=org.id,name=payload.product,category='medicine').first()
        if not item:raise HTTPException(422,'Select a registered medicine')
        if not payload.quantity or payload.quantity<=0 or not payload.unit:raise HTTPException(422,'Enter administered dose and unit')
        if not payload.animal_tag:raise HTTPException(422,'Select an animal for medication')
        payload.shift='Other'
    if payload.category=='dipping':
        if payload.animal_id and payload.animal_tag is None:raise HTTPException(422,'Select a registered animal')
        payload.shift='Other';payload.quantity=None;payload.unit=None
    if payload.category=='weighing':
        if not payload.animal_tag:raise HTTPException(422,'Select a registered animal')
        if payload.quantity is None or payload.quantity<=0:raise HTTPException(422,'Enter live weight in kg')
        payload.unit='kg';payload.frequency='daily';payload.shift='Other'
        start,end,_=period_limits('daily',date.today())
        if db.query(WeightObservation).filter(WeightObservation.organization_id==org.id,
              WeightObservation.animal_id==payload.animal_id,
              WeightObservation.created_at>=datetime.combine(start,time.min),
              WeightObservation.created_at<datetime.combine(end,time.min)).first():
            raise HTTPException(409,'Weight already recorded for this animal today. Use Edit weight.')
    if payload.category=='feeding':raise HTTPException(422,'Use Record feeding for measured quantities and automatic Stock Out')
    if payload.category in ('watering','cleaning','dipping','medication','weighing','health','inspection'):
        if payload.category=='watering':
            done=completed_shifts(db,org,'watering',payload.batch_id,None)
            if payload.shift in done:raise HTTPException(409,f'{payload.shift} watering already completed today')
            claim_shift(db,org,user,'watering',payload.batch_id,None,payload.shift)
        else:
            target=target_key(payload.category,payload.batch_id,payload.animal_id,payload.pen_id,
                              medicine_id=item.id if payload.category=='medication' else None)
            claim_period(db,org,user,payload.category,target,payload.frequency)
    row=V5Routine(organization_id=org.id,recorded_by=user.id,
                  **payload.model_dump(exclude={'animal_id'}))
    db.add(row);db.flush()
    if payload.category=='weighing':
        animal=db.query(V5Animal).filter_by(id=payload.animal_id,organization_id=org.id).with_for_update().first()
        previous=animal.current_weight_kg
        animal.current_weight_kg=__import__('decimal').Decimal(str(payload.quantity))
        if previous is not None and animal.current_weight_kg<previous:
            from modules.fattening.service import alert
            alert(db,org,'weight','Weight decreased',f'{animal.tag}: {previous} to {animal.current_weight_kg} kg. Verify measurement and animal health.')
        db.add(WeightObservation(organization_id=org.id,animal_id=animal.id,weight_kg=animal.current_weight_kg,
                                 recorded_by=user.id,notes=payload.notes,routine_id=row.id))
    mark_matching_assignments(db,org,user,payload.category,payload.batch_id,payload.shift,
                               individual=bool(payload.animal_tag),pen_id=payload.pen_id)
    audit(db,user.id,'routine_record','v5_routine',row.id,f'{payload.category}; batch={payload.batch_id}; pen={payload.pen_id}; frequency={payload.frequency}')
    db.commit();db.refresh(row);return {**record_dict(row),'message':'Record saved successfully'}
