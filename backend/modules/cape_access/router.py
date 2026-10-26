"""Cape Ranch registration, subscription requests, owner policy, trial and self-service status."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db, User, utcnow
from auth import get_current_user, PH, audit, aware_utc
from modules.organizations.models import Organization, Membership
from modules.subscriptions.models import Subscription, LicenseKey
from modules.organizations.service import owner
from .models import OrganizationProfile, SubscriptionRequest, TrialGrant
from .schemas import OrganizationRegistration, PolicyUpdate, RequestSubscription, ApproveRequest
from .service import policy, active, grant_trial, issue_paid_key

router=APIRouter(prefix='/api/cape',tags=['Cape Ranch subscription & enrollment'])

# Unlike operational context, billing_context works for expired and pending customers.
def billing_context(request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if user.role=='platform_owner':raise HTTPException(403,'Select the platform administration area')
    org_id=request.headers.get('x-organization-id','')
    if not org_id.isdecimal():raise HTTPException(400,'Select an organization')
    org=db.get(Organization,int(org_id))
    member=db.query(Membership).filter_by(organization_id=int(org_id),user_id=user.id,active=True).first()
    if not org or not member:raise HTTPException(403,'No access to this organization')
    return user,org,member

@router.get('/public/enrollment-config')
def enrollment_config(db:Session=Depends(get_db)):
    p=policy(db)
    return {'free_trial_enabled':p.trial_enabled,'trial_days':p.trial_days,
            'minimum_paid_days':p.minimum_paid_days,'default_employee_seats':p.default_employee_seats}

@router.post('/public/organizations/register',status_code=201)
def register_org(payload:OrganizationRegistration,db:Session=Depends(get_db)):
    if not db.query(User.id).first():raise HTTPException(403,'Platform owner must complete initial setup first')
    email=str(payload.admin_email).lower()
    if db.query(User).filter_by(email=email).first():raise HTTPException(409,'Administrator email already in use')
    p=payload.model_dump()
    org=Organization(name=p['name'].strip(),trading_name=p.get('trading_name'),registration_number=p.get('registration_number'),
      tax_number=p.get('tax_number'),country=p['country'],region=p.get('region'),district=p.get('district'),
      address=p.get('address'),phone=p['phone'],email=str(p['email']),billing_email=str(p['billing_email']) if p.get('billing_email') else None,
      status='pending',livestock_types=p.get('production_focus'))
    db.add(org);db.flush()
    profile=OrganizationProfile(organization_id=org.id,legal_entity_type=p['legal_entity_type'],
      industry_sectors=p['industry_sectors'],operations_description=p['operations_description'],employee_count=p['employee_count'],
      expected_system_users=p['expected_system_users'],farms_count=p['farms_count'],
      total_land_hectares=str(p['total_land_hectares']) if p.get('total_land_hectares') is not None else None,
      city=p.get('city'),state_province=p.get('state_province'),postal_code=p.get('postal_code'),website=p.get('website'),
      incorporation_date=str(p['incorporation_date']) if p.get('incorporation_date') else None,
      contact_person=p['contact_person'],contact_position=p.get('contact_position'),contact_phone=p.get('contact_phone'),
      preferred_currency=p['preferred_currency'],timezone=p['timezone'],operational_countries=p.get('operational_countries'),
      production_focus=p.get('production_focus'))
    db.add(profile)
    user=User(full_name=p['admin_name'].strip(),email=email,password_hash=PH.hash(p['admin_password']),role='staff',is_active=True)
    db.add(user);db.flush()
    db.add(Membership(organization_id=org.id,user_id=user.id,role='org_admin'))
    db.add(Subscription(organization_id=org.id,plan='professional',max_employees=policy(db).default_employee_seats))
    audit(db,user.id,'organization_registration','organization',org.id,'Registration submitted; verification pending')
    db.commit()
    return {'organization_id':org.id,'status':'pending',
            'message':'Registration submitted. Organization verification is required before trial or paid activation.'}

@router.get('/subscription/status')
def status(db:Session=Depends(get_db),ctx=Depends(billing_context)):
    _,org,member=ctx;sub=db.get(Subscription,org.id);p=policy(db)
    trial=db.get(TrialGrant,org.id)
    valid=active(db,org.id) and org.status=='approved'
    return {'organization_id':org.id,'organization':org.name,'verification':org.status,
      'active':valid,'plan':sub.plan if sub else None,'suspended':sub.suspended if sub else False,
      'expires_at':sub.expires_at.isoformat() if sub and sub.expires_at else None,
      'days_remaining':max(0,(aware_utc(sub.expires_at)-utcnow()).days+1) if sub and sub.expires_at and valid else 0,
      'max_employees':sub.max_employees if sub else p.default_employee_seats,
      'trial_eligible':bool(org.status=='approved' and p.trial_enabled and not trial and not valid and
                    not db.query(LicenseKey).filter(LicenseKey.organization_id==org.id,LicenseKey.redeemed_at.isnot(None)).first()),
      'trial_enabled':p.trial_enabled,'trial_days':p.trial_days,'minimum_paid_days':p.minimum_paid_days,
      'can_manage':member.role=='org_admin'}

@router.post('/subscription/trial/start')
def start_trial(db:Session=Depends(get_db),ctx=Depends(billing_context)):
    user,org,m=ctx
    if m.role!='org_admin':raise HTTPException(403,'Organization administrator required')
    return grant_trial(db,org,user)

@router.post('/subscription/request',status_code=201)
def subscribe(p:RequestSubscription,db:Session=Depends(get_db),ctx=Depends(billing_context)):
    user,org,m=ctx
    if m.role!='org_admin':raise HTTPException(403,'Organization administrator required')
    if org.status!='approved':raise HTTPException(403,'Organization verification required before subscribing')
    if db.query(SubscriptionRequest).filter_by(organization_id=org.id,status='pending').first():
        raise HTTPException(409,'A subscription request is already under review')
    item=SubscriptionRequest(organization_id=org.id,requested_by=user.id,days=p.days,
                             employee_seats=p.employee_seats,notes=p.notes,status='pending')
    db.add(item);db.flush();audit(db,user.id,'subscription_requested','subscription_request',item.id,
      f'org={org.id}; days={p.days}; seats={p.employee_seats}')
    db.commit()
    return {'request_id':item.id,'status':item.status,
      'message':'Request submitted. Payment and eligibility are reviewed separately; no subscription has been activated.'}

@router.get('/subscription/requests')
def subscription_requests(db:Session=Depends(get_db),ctx=Depends(billing_context)):
    _,org,m=ctx
    if m.role!='org_admin':raise HTTPException(403,'Organization administrator required')
    rows=db.query(SubscriptionRequest).filter_by(organization_id=org.id).order_by(SubscriptionRequest.id.desc()).limit(100).all()
    return {'items':[{'id':x.id,'days':x.days,'employee_seats':x.employee_seats,
      'status':x.status,'created_at':x.created_at.isoformat()} for x in rows]}

@router.get('/organization/profile')
def profile(db:Session=Depends(get_db),ctx=Depends(billing_context)):
    _,org,_=ctx;obj=db.get(OrganizationProfile,org.id)
    return {'organization_id':org.id,'name':org.name,
       'profile':{c.name:getattr(obj,c.name) for c in OrganizationProfile.__table__.columns} if obj else {}}

@router.get('/platform/subscription-policy')
def owner_policy(db:Session=Depends(get_db),user:User=Depends(owner)):
    p=policy(db)
    return {'trial_enabled':p.trial_enabled,'trial_days':p.trial_days,
      'minimum_paid_days':p.minimum_paid_days,'default_employee_seats':p.default_employee_seats}

@router.put('/platform/subscription-policy')
def save_owner_policy(p:PolicyUpdate,db:Session=Depends(get_db),user:User=Depends(owner)):
    current=policy(db,lock=True)
    current.trial_enabled=p.trial_enabled;current.default_employee_seats=p.default_employee_seats
    audit(db,user.id,'subscription_policy_updated','subscription_policy',1,
          f'trial_enabled={p.trial_enabled}; seats={p.default_employee_seats}')
    db.commit()
    return owner_policy(db,user)

@router.get('/platform/subscription-requests')
def owner_requests(db:Session=Depends(get_db),user:User=Depends(owner)):
    rows=db.query(SubscriptionRequest).order_by(SubscriptionRequest.id.desc()).limit(300).all()
    return {'items':[{'id':r.id,'organization_id':r.organization_id,
      'organization':(db.get(Organization,r.organization_id).name if db.get(Organization,r.organization_id) else None),
      'days':r.days,'employee_seats':r.employee_seats,'notes':r.notes,
      'status':r.status,'created_at':r.created_at.isoformat()} for r in rows]}

@router.post('/platform/subscription-requests/{request_id}/review')
def review(request_id:int,p:ApproveRequest,db:Session=Depends(get_db),user:User=Depends(owner)):
    r=db.query(SubscriptionRequest).filter_by(id=request_id).with_for_update().first()
    if not r:raise HTTPException(404,'Subscription request not found')
    if r.status!='pending':raise HTTPException(409,'Request already reviewed')
    if p.decision=='approve':return issue_paid_key(db,r,user)
    r.status='rejected';r.reviewed_by=user.id;r.reviewed_at=utcnow()
    audit(db,user.id,'subscription_request_rejected','subscription_request',r.id,
          f'org={r.organization_id}')
    db.commit()
    return {'request_id':r.id,'status':'rejected'}

@router.get('/platform/organization-profile/{org_id}')
def owner_org_profile(org_id:int,db:Session=Depends(get_db),user:User=Depends(owner)):
    org=db.get(Organization,org_id)
    if not org:raise HTTPException(404,'Organization not found')
    row=db.get(OrganizationProfile,org_id)
    return {'name':org.name,'email':org.email,'country':org.country,'registration_number':org.registration_number,
      'phone':org.phone,'status':org.status,'profile':{c.name:getattr(row,c.name) for c in OrganizationProfile.__table__.columns} if row else {}}


@router.get('/platform/organization-subscriptions')
def owner_subscription_dashboard(db:Session=Depends(get_db), user:User=Depends(owner)):
    """Owner-only, source-backed trial versus paid license inventory.

    Registration is not a subscription; issued-but-unredeemed keys are not active.
    The canonical Subscription/LicenseKey rows remain untouched.
    """
    from datetime import timedelta
    from math import ceil
    from auth import aware_utc
    from modules.organizations.models import Membership
    now=utcnow()
    orgs=db.query(Organization).order_by(Organization.name.asc(),Organization.id.asc()).all()
    ids=[o.id for o in orgs]
    if not ids:
        return {'items':[], 'counts':{'all':0,'trial':0,'paid':0,'professional':0,'enterprise':0,'active':0,'expiring_soon':0,
                'expired':0,'suspended':0,'pending_verification':0,'pending_activation':0,'not_activated':0}}
    subs={s.organization_id:s for s in db.query(Subscription).filter(Subscription.organization_id.in_(ids)).all()}
    trials={t.organization_id:t for t in db.query(TrialGrant).filter(TrialGrant.organization_id.in_(ids)).all()}
    keys_by_org={}
    for k in db.query(LicenseKey).filter(LicenseKey.organization_id.in_(ids)).order_by(LicenseKey.id.desc()).all():
        keys_by_org.setdefault(k.organization_id,[]).append(k)
    requests={}
    for req in db.query(SubscriptionRequest).filter(SubscriptionRequest.organization_id.in_(ids), SubscriptionRequest.status=='pending').order_by(SubscriptionRequest.id.desc()).all():
        requests.setdefault(req.organization_id,req)
    seat_counts={i:0 for i in ids}
    for m in db.query(Membership).filter(Membership.organization_id.in_(ids),Membership.active.is_(True)).all():
        seat_counts[m.organization_id]+=1
    counts={'all':len(orgs),'trial':0,'paid':0,'professional':0,'enterprise':0,'active':0,'expiring_soon':0,'expired':0,
            'suspended':0,'pending_verification':0,'pending_activation':0,'not_activated':0}
    items=[]
    for org in orgs:
        sub=subs.get(org.id)
        trial=trials.get(org.id)
        valid_keys=[k for k in keys_by_org.get(org.id,[]) if k.redeemed_at and not k.revoked_at]
        trial_license_id=trial.license_key_id if trial else None
        paid_keys=[k for k in valid_keys if k.id!=trial_license_id]
        is_current_trial=bool(sub and sub.plan=='trial' and trial)
        # Unredeemed issued keys and default plan='professional' are NOT paid entitlements.
        mode='trial' if is_current_trial else ('paid' if paid_keys else 'none')
        if mode!='none':counts[mode]+=1
        if mode=='paid':
            counts['enterprise' if sub and sub.plan=='enterprise' else 'professional']+=1
        verified=org.status=='approved'
        end=aware_utc(sub.expires_at) if sub and sub.expires_at else None
        is_licensed=bool(verified and sub and not sub.suspended and end and end>now and valid_keys)
        remaining=max(0,ceil((end-now).total_seconds()/86400)) if is_licensed and end else 0
        if org.status!='approved':state='pending_verification'
        elif sub and sub.suspended:state='suspended'
        elif is_licensed:state='expiring_soon' if remaining<=7 else 'active'
        elif end and end<=now and valid_keys:state='expired'
        elif org.id in requests:state='pending_activation'
        else:state='not_activated'
        counts[state]+=1
        activated=(trial.created_at if is_current_trial else paid_keys[0].redeemed_at if paid_keys else None)
        items.append({'id':org.id,'organization_id':org.id,'name':org.name,'country':org.country,
           'verification':org.status,'mode':mode,
           'plan':sub.plan if mode!='none' and sub else None,
           'plan_label':('Free trial' if mode=='trial' else
               ('Enterprise' if sub and sub.plan=='enterprise' else 'Professional (paid)') if mode=='paid' else 'Not activated'),
           'access_status':state,'is_active':is_licensed,'trial_used':bool(trial),
           'trial_started_at':trial.created_at.isoformat() if trial else None,
           'trial_ends_at':trial.ends_at.isoformat() if trial else None,
           'activated_at':activated.isoformat() if activated else None,
           'expires_at':sub.expires_at.isoformat() if sub and sub.expires_at else None,
           'days_remaining':remaining,'max_employees':sub.max_employees if sub else None,
           'active_employees':seat_counts[org.id],
           'pending_request_id':requests[org.id].id if org.id in requests else None,
           'requested_days':requests[org.id].days if org.id in requests else None,
           'issued_unredeemed_keys':sum(1 for k in keys_by_org.get(org.id,[]) if not k.redeemed_at and not k.revoked_at)})
    return {'items':items,'counts':counts,'as_of':now.isoformat()}
