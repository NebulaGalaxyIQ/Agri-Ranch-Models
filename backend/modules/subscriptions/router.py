"""Platform-only offer administration; offers never modify licenses automatically."""
from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from database import get_db,User
from modules.organizations.service import owner
from . import service
from .schemas import OfferIn
router=APIRouter(prefix='/api/v6/platform/offers',tags=['Subscription offers'])
@router.get('')
def offers(db:Session=Depends(get_db),user:User=Depends(owner)):
    return service.list_offers(db)
@router.post('',status_code=201)
def add_offer(payload:OfferIn,db:Session=Depends(get_db),user:User=Depends(owner)):
    return service.create_offer(db,user,payload)
@router.patch('/{offer_id}')
def offer_status(offer_id:int,active:bool,db:Session=Depends(get_db),user:User=Depends(owner)):
    return service.change_offer(db,user,offer_id,active)
