"""Owner-controlled platform appearance and isolated organization logos.
Images are decoded, normalized and stored in the database; user uploads are NOT served
through the public static-files mount. Public endpoint only exposes the login backdrop.
"""
from __future__ import annotations
from io import BytesIO
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, Integer, String, LargeBinary, UniqueConstraint, Boolean
from sqlalchemy.orm import Session, Mapped, mapped_column
from database import Base, get_db
from modules.organizations.service import context, owner, Organization, licensed
from auth import audit
from modules.crops.models import ModuleSetting, MODULES

# Canonical ORM classes are owned by their respective domains.
from modules.platform_admin.models import BrandImage


router=APIRouter(prefix='/api/v6',tags=['v6-branding-subscriptions'])


async def image_data(upload:UploadFile):
    data=await upload.read(6*1024*1024+1)
    if len(data)>6*1024*1024:raise HTTPException(413,'Image must be under 6 MB')
    if len(data)<50:raise HTTPException(422,'Image is missing or empty')
    try:
        from PIL import Image, ImageOps
        img=Image.open(BytesIO(data));img.verify()
        img=Image.open(BytesIO(data))
        if img.format not in ('PNG','JPEG','WEBP'):raise ValueError('Unsupported image format')
        if img.width*img.height>16_000_000:raise ValueError('Image is too large in pixels')
        img=ImageOps.exif_transpose(img).convert('RGB')
        img.thumbnail((2400,1500))
        output=BytesIO();img.save(output,format='WEBP',quality=86,method=4)
        return output.getvalue(),'image/webp'
    except Exception as ex:
        raise HTTPException(422,'Upload a valid PNG, JPEG or WebP image') from ex

def put(db,scope,org_id,data,mime,user):
    image=db.query(BrandImage).filter_by(scope=scope,organization_id=org_id).first()
    if not image:
        image=BrandImage(scope=scope,organization_id=org_id,mime=mime,content=data);db.add(image)
    else:image.mime=mime;image.content=data
    db.flush();audit(db,user.id,'branding_updated',scope,org_id or 'platform')
    db.commit()
    return {'message':'Image saved successfully'}

@router.post('/platform/branding/background')
async def upload_platform_background(file:UploadFile=File(...),db:Session=Depends(get_db),actor=Depends(owner)):
    data,mime=await image_data(file);return put(db,'platform_background',None,data,mime,actor)

@router.get('/public/branding')
def public_branding(db:Session=Depends(get_db)):
    rec=db.query(BrandImage).filter_by(scope='platform_background',organization_id=None).first()
    return {'background_url':'/api/v6/public/branding/image' if rec else None}

@router.get('/public/branding/image')
def public_background(db:Session=Depends(get_db)):
    rec=db.query(BrandImage).filter_by(scope='platform_background',organization_id=None).first()
    if not rec:raise HTTPException(404,'No platform background image')
    return Response(rec.content,media_type=rec.mime,headers={'Cache-Control':'public,max-age=180'})

@router.delete('/platform/branding/background')
def clear_background(db:Session=Depends(get_db),actor=Depends(owner)):
    db.query(BrandImage).filter_by(scope='platform_background',organization_id=None).delete()
    audit(db,actor.id,'branding_cleared','platform_background','platform');db.commit();return {'message':'Background restored to default'}

@router.post('/organizations/me/logo')
async def organization_logo(file:UploadFile=File(...),db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,member=ctx;licensed(db,org,True)
    if member.role!='org_admin':raise HTTPException(403,'Organization administrator only')
    data,mime=await image_data(file)
    return put(db,'organization_logo',org.id,data,mime,actor)

@router.get('/organizations/me/logo')
def get_org_logo(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=ctx
    rec=db.query(BrandImage).filter_by(scope='organization_logo',organization_id=org.id).first()
    if not rec:raise HTTPException(404,'No organization logo')
    return Response(rec.content,media_type=rec.mime,headers={'Cache-Control':'private,max-age=120'})

@router.delete('/organizations/me/logo')
def clear_org_logo(db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,member=ctx;licensed(db,org,True)
    if member.role!='org_admin':raise HTTPException(403,'Organization administrator only')
    db.query(BrandImage).filter_by(scope='organization_logo',organization_id=org.id).delete()
    audit(db,actor.id,'branding_cleared','organization_logo',org.id);db.commit();return {'message':'Organization logo removed'}

class ModulePatch(BaseModel):
    enabled:bool

@router.put('/platform/organizations/{org_id}/modules/{module}')
def owner_set_module(org_id:int,module:str,p:ModulePatch,db:Session=Depends(get_db),actor=Depends(owner)):
    if module not in MODULES:raise HTTPException(404,'Unknown module')
    if not db.get(Organization,org_id):raise HTTPException(404,'Organization not found')
    item=db.query(ModuleSetting).filter_by(organization_id=org_id,module=module).first()
    if not item:
        item=ModuleSetting(organization_id=org_id,module=module,enabled=p.enabled);db.add(item)
    else:item.enabled=p.enabled
    audit(db,actor.id,'module_entitlement_updated','organization',org_id,f'{module}={p.enabled}')
    db.commit();return {'module':module,'enabled':p.enabled}

@router.get('/platform/organizations/{org_id}/modules')
def owner_get_modules(org_id:int,db:Session=Depends(get_db),actor=Depends(owner)):
    if not db.get(Organization,org_id):raise HTTPException(404,'Organization not found')
    overrides={r.module:r.enabled for r in db.query(ModuleSetting).filter_by(organization_id=org_id)}
    return {'items':[{'name':m,'enabled':overrides.get(m,True)} for m in MODULES]}
