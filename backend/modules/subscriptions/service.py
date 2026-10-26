from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from auth import audit
from .models import Offer

def as_dict(o):
 return {'id':o.id,'name':o.name,'code':o.code,'description':o.description,'discount_pct':float(o.discount_pct),'bonus_days':o.bonus_days,'max_redemptions':o.max_redemptions,'starts_on':o.starts_on.isoformat(),'ends_on':o.ends_on.isoformat(),'active':o.active,'created_at':o.created_at.isoformat()}

def list_offers(db:Session):return {'items':[as_dict(x) for x in db.query(Offer).order_by(Offer.id.desc()).limit(300).all()]}
def create_offer(db:Session,user,request):
    obj=Offer(**{**request.model_dump(),'code':request.code.upper()},created_by=user.id)
    db.add(obj)
    try: db.flush();audit(db,user.id,'offer_create','platform_offer',obj.id,obj.code);db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Offer code already exists')
    db.refresh(obj);return as_dict(obj)
def change_offer(db:Session,user,offer_id:int,active:bool):
    obj=db.get(Offer,offer_id)
    if not obj:raise HTTPException(404,'Offer not found')
    obj.active=active;audit(db,user.id,'offer_status','platform_offer',obj.id,str(active));db.commit();return as_dict(obj)
