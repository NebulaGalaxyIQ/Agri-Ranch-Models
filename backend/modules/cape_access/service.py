"""License-policy rules: no client-supplied expiry dates or auto-payments.
All time and key grants are calculated on the server.
"""
from datetime import timedelta
import secrets
from fastapi import HTTPException
from sqlalchemy.orm import Session
from auth import aware_utc, audit, hash_token
from database import utcnow
from modules.organizations.models import Organization
from modules.subscriptions.models import Subscription, LicenseKey
from .models import SubscriptionPolicy, TrialGrant, SubscriptionRequest


def policy(db:Session, lock=False)->SubscriptionPolicy:
    q=db.query(SubscriptionPolicy).filter_by(id=1)
    if lock:q=q.with_for_update()
    item=q.first()
    if not item:
        item=SubscriptionPolicy(id=1, trial_enabled=False,trial_days=30,minimum_paid_days=30,default_employee_seats=25)
        db.add(item);db.flush()
    return item


def active(db:Session,org_id:int)->bool:
    sub=db.get(Subscription,org_id)
    if not sub or sub.suspended or not sub.expires_at or aware_utc(sub.expires_at)<=utcnow():return False
    # Strong feature gate: every current entitlement must originate from a redeemed key.
    return db.query(LicenseKey.id).filter(LicenseKey.organization_id==org_id, LicenseKey.redeemed_at.isnot(None)).first() is not None


def grant_trial(db:Session,org:Organization,user):
    p=policy(db,lock=True)
    if not p.trial_enabled:raise HTTPException(409,'The free-trial promotion is currently unavailable')
    if org.status!='approved':raise HTTPException(403,'Organization approval is required before activation')
    # Organization lock serializes requests for the same trial.
    db.query(Organization).filter_by(id=org.id).with_for_update().one()
    if db.get(TrialGrant,org.id):raise HTTPException(409,'Free trial already claimed by this organization')
    if db.query(LicenseKey).filter(LicenseKey.organization_id==org.id, LicenseKey.redeemed_at.isnot(None)).count():
        raise HTTPException(409,'Free trial is only available before a previous subscription activation')
    sub=db.query(Subscription).filter_by(organization_id=org.id).with_for_update().first()
    if not sub:sub=Subscription(organization_id=org.id);db.add(sub);db.flush()
    if active(db,org.id):raise HTTPException(409,'Subscription already active')
    now=utcnow();end=now+timedelta(days=p.trial_days)
    key=LicenseKey(organization_id=org.id,key_hash=hash_token(secrets.token_urlsafe(48)), duration_days=p.trial_days,
                   max_employees=p.default_employee_seats,redeemed_at=now,created_at=now)
    db.add(key);db.flush()
    db.add(TrialGrant(organization_id=org.id,license_key_id=key.id,created_at=now,ends_at=end))
    sub.plan='trial';sub.expires_at=end;sub.max_employees=p.default_employee_seats;sub.suspended=False
    audit(db,user.id,'trial_activated','organization',org.id,f'{p.trial_days} days; license_id={key.id}')
    db.commit()
    return {'active':True,'plan':'trial','expires_at':end.isoformat(),'max_employees':sub.max_employees}


def issue_paid_key(db:Session,request:SubscriptionRequest,owner):
    org=db.get(Organization,request.organization_id)
    if not org or org.status!='approved':raise HTTPException(409,'Organization must be approved')
    if request.days<30:raise HTTPException(422,'Minimum subscription duration is 30 days')
    raw='CR-'+secrets.token_urlsafe(32)
    key=LicenseKey(organization_id=org.id,key_hash=hash_token(raw),duration_days=request.days,
                   max_employees=request.employee_seats,created_at=utcnow())
    db.add(key);db.flush()
    request.status='approved';request.reviewed_by=owner.id;request.reviewed_at=utcnow();request.license_key_id=key.id
    audit(db,owner.id,'subscription_request_approved','subscription_request',request.id,
          f'org={org.id}; key_id={key.id}; days={request.days}; seats={request.employee_seats}')
    db.commit()
    return {'request_id':request.id,'key':raw,'days':request.days,'employee_seats':request.employee_seats,
            'warning':'Copy this one-time product key securely. Plaintext is never stored.'}
