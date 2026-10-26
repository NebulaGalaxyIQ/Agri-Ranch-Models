"""V5 project/batch control, feed planning, reporting and notifications.

All queries are organization scoped and protected on the backend. Recorded feeding
posts linked physical feed stock issues and costs; no values are inferred as measured.
"""
from __future__ import annotations
import csv
import io
import json
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, get_db, utcnow
from auth import audit
from modules.organizations.service import (context, licensed, permitted, V5Batch, V5Ranch, V5Routine,
                     Subscription, batch_summary)
from modules.fattening.models import (V5Animal, Ration, StockItem, StockMovement, FinanceEntry,
                                  Task, animal_data, permission)

# Canonical ORM classes are owned by their respective domains.
from modules.fattening.models import V5Project, FeedAssignment, FeedPlan, FeedingLine
from modules.employees.models import Notification


router = APIRouter(prefix='/api/v5', tags=['v5-projects-feeding-notifications-reports'])






class ProjectIn(BaseModel):
    name:str=Field(min_length=2,max_length=180)
    code:str|None=None
    description:str|None=None
    objective:str|None=None
    livestock_type:str|None=None
    ranch_id:int|None=None
    start_date:date=Field(default_factory=date.today)
    end_date:date|None=None
    budget:Decimal|None=Field(default=None,ge=0)
    manager_id:int|None=None
    target_animals:int|None=Field(default=None,ge=1)
    target_weight_kg:Decimal|None=Field(default=None,gt=0)
    currency:str='TZS'
    status:Literal['planned','active','paused','completed','cancelled']='planned'
    @model_validator(mode='after')
    def check_dates(self):
        if self.end_date and self.end_date < self.start_date:raise ValueError('Project end date must not precede start date')
        return self

class BatchUpdate(BaseModel):
    project_id:int|None=None  # one-time upgrade for older orphan batches only
    name:str|None=Field(default=None,min_length=2,max_length=160)
    capacity:int|None=Field(default=None,ge=1,le=1000000)
    end_date:date|None=None
    status:Literal['planned','active','completed']|None=None
    description:str|None=None

class AnimalMove(BaseModel):
    batch_id:int

class AnimalStatus(BaseModel):
    status:Literal['active','sold','deceased','removed']

class FeedTarget(BaseModel):
    ration_id:int
    batch_id:int|None=None
    animal_id:int|None=None
    start_date:date=Field(default_factory=date.today)
    end_date:date|None=None
    @model_validator(mode='after')
    def target(self):
        if (self.batch_id is None)==(self.animal_id is None):raise ValueError('Select exactly one batch or animal')
        if self.end_date and self.end_date<self.start_date:raise ValueError('End date precedes start date')
        return self

class FeedPlanIn(FeedTarget):
    kg_per_head_day:Decimal=Field(gt=0)
    shift:Literal['Morning','Afternoon','Evening','Any']='Any'
    frequency:Literal['daily','weekly','monthly']='daily'

class FeedingLineIn(BaseModel):
    item_id:int|None=None
    ration_id:int|None=None
    quantity_kg:Decimal=Field(gt=0)
    @model_validator(mode='after')
    def source(self):
        if (self.item_id is None)==(self.ration_id is None):raise ValueError('Choose one feed or mix per line')
        return self

class FeedingRecordIn(BaseModel):
    batch_id:int|None=None
    animal_id:int|None=None
    shift:Literal['Morning','Afternoon','Evening','Other']='Morning'
    ration_id:int|None=None
    ration_quantity_kg:Decimal|None=Field(default=None,gt=0)
    extras:list[FeedingLineIn]=Field(default_factory=list,max_length=30)
    notes:str|None=None
    client_reference:str=Field(min_length=8,max_length=100)
    @model_validator(mode='after')
    def valid(self):
        if (self.batch_id is None)==(self.animal_id is None):raise ValueError('Select exactly one batch or animal')
        if self.ration_quantity_kg is None and not self.extras:raise ValueError('Enter mix quantity or at least one feed item')
        return self

def project_dict(db,org,p):
    bs=db.query(V5Batch).filter_by(organization_id=org.id,project_id=p.id).all()
    total=sum(db.query(V5Animal).filter_by(organization_id=org.id,batch_id=b.id,status='active').count() for b in bs)
    return dict(id=p.id,name=p.name,code=p.code,description=p.description,objective=p.objective,
                livestock_type=p.livestock_type,ranch_id=p.ranch_id,manager_id=p.manager_id,target_animals=p.target_animals,
                target_weight_kg=float(p.target_weight_kg) if p.target_weight_kg is not None else None,start_date=p.start_date.isoformat(),
                end_date=p.end_date.isoformat() if p.end_date else None,budget=float(p.budget) if p.budget is not None else None,
                currency=p.currency,status=p.status,batches=len(bs),animals=total)

def verify_batch(db,org,bid,lock=False):
    q=db.query(V5Batch).filter_by(id=bid,organization_id=org.id)
    b=(q.with_for_update() if lock else q).first()
    if not b:raise HTTPException(404,'Batch not found')
    return b

def verify_animal(db,org,aid,lock=False):
    q=db.query(V5Animal).filter_by(id=aid,organization_id=org.id)
    a=(q.with_for_update() if lock else q).first()
    if not a:raise HTTPException(404,'Animal not found')
    return a

def verify_ration(db,org,rid):
    r=db.query(Ration).filter_by(id=rid,organization_id=org.id).first()
    if not r:raise HTTPException(404,'Feed mix not found')
    return r

def verify_item(db,org,iid):
    i=db.query(StockItem).filter_by(id=iid,organization_id=org.id).first()
    if not i:raise HTTPException(404,'Feed item not found')
    return i

def alert(db,org,category,title,message,user_id=None):
    db.add(Notification(organization_id=org.id,category=category,title=title,message=message,user_id=user_id))

@router.get('/projects')
def projects(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'projects.read')
    return {'items':[project_dict(db,org,x) for x in db.query(V5Project).filter_by(organization_id=org.id).order_by(V5Project.id.desc())]}

@router.post('/projects',status_code=201)
def create_project(p:ProjectIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'projects.manage',True)
    if not p.code: p=p.model_copy(update={'code':f'PRJ-{org.id}-{secrets.token_hex(5).upper()}'})
    if p.ranch_id is None:raise HTTPException(422,'Create and select a ranch before creating a project')
    if not db.query(V5Ranch).filter_by(id=p.ranch_id,organization_id=org.id).first():raise HTTPException(404,'Ranch not found')
    if p.code and db.query(V5Project).filter_by(organization_id=org.id,code=p.code).first():raise HTTPException(409,'Project code already exists')
    if db.query(V5Project).filter(V5Project.organization_id==org.id,V5Project.ranch_id==p.ranch_id,func.lower(V5Project.name)==p.name.strip().lower()).first():raise HTTPException(409,'Project with this name already exists in the ranch')
    if p.manager_id is not None:
        from modules.organizations.service import Membership
        if not db.query(Membership).filter_by(organization_id=org.id,user_id=p.manager_id,active=True).first():raise HTTPException(404,'Project manager must be an active organization employee')
    obj=V5Project(organization_id=org.id,created_by=user.id,**p.model_dump());db.add(obj);db.flush()
    audit(db,user.id,'project_create','v5_project',obj.id,obj.name)
    alert(db,org,'project','Project created',f'{obj.name} has been created. Add batches to start.',user.id)
    db.commit()
    return project_dict(db,org,obj)

@router.patch('/projects/{project_id}')
def update_project(project_id:int,p:ProjectIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'projects.manage',True)
    obj=db.query(V5Project).filter_by(id=project_id,organization_id=org.id).first()
    if not obj:raise HTTPException(404,'Project not found')
    if p.ranch_id is None:raise HTTPException(422,'Project must belong to a ranch')
    if not db.query(V5Ranch).filter_by(id=p.ranch_id,organization_id=org.id).first():raise HTTPException(404,'Ranch not found')
    if p.ranch_id!=obj.ranch_id and db.query(V5Batch).filter_by(organization_id=org.id,project_id=obj.id).count():raise HTTPException(409,'Cannot change ranch after batches have been created')
    if p.manager_id is not None:
        from modules.organizations.service import Membership
        if not db.query(Membership).filter_by(organization_id=org.id,user_id=p.manager_id,active=True).first():raise HTTPException(404,'Project manager must be an active organization employee')
    for k,v in p.model_dump().items():setattr(obj,k,v)
    audit(db,user.id,'project_update','v5_project',obj.id,obj.name);db.commit();return project_dict(db,org,obj)

@router.patch('/batches/{batch_id}')
def update_batch(batch_id:int,p:BatchUpdate,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'ranch.manage',True)
    b=verify_batch(db,org,batch_id,lock=True)
    count=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=b.id,status='active').count()
    if p.capacity is not None and p.capacity<count:raise HTTPException(409,f'Capacity cannot be lower than {count} active animals')
    changes=p.model_dump(exclude_unset=True)
    if 'project_id' in changes:
        if b.project_id is not None and changes['project_id']!=b.project_id:raise HTTPException(409,'Batch is already assigned to a project; changing ownership requires supervised migration')
        project=db.query(V5Project).filter_by(id=changes['project_id'],organization_id=org.id).first() if changes['project_id'] else None
        if not project or not project.ranch_id:raise HTTPException(422,'Select a project already assigned to a ranch')
        if project.ranch_id!=b.ranch_id:raise HTTPException(409,'Existing batch and project must belong to same ranch')
    for k,v in changes.items():setattr(b,k,v)
    if b.end_date and b.start_date and b.end_date<b.start_date:raise HTTPException(422,'End date before start date')
    audit(db,user.id,'batch_update','v5_batch',b.id,b.name);db.commit();return batch_summary(db,b)

@router.post('/animals/{animal_id}/transfer')
def transfer_animal(animal_id:int,p:AnimalMove,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'animals.manage',True)
    a=verify_animal(db,org,animal_id,lock=True)
    if a.status!='active':raise HTTPException(409,'Only active animals may be transferred')
    b=verify_batch(db,org,p.batch_id,lock=True)
    if b.id==a.batch_id:return animal_data(a)
    if b.status=='completed':raise HTTPException(409,'Target batch is completed')
    count=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=b.id,status='active').count()
    if b.capacity is not None and count>=b.capacity:raise HTTPException(409,'Target batch is at capacity')
    old=a.batch_id;a.batch_id=b.id
    audit(db,user.id,'animal_transfer','v5_animal',a.id,f'{old}->{b.id}');db.commit();return animal_data(a)

@router.patch('/animals/{animal_id}/status')
def animal_status(animal_id:int,p:AnimalStatus,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'animals.manage',True)
    a=verify_animal(db,org,animal_id,lock=True)
    if p.status=='sold' or a.status=='sold':
        raise HTTPException(409,'Animal sales require a sales record. Use Animals → Sell animal. To cancel a sale, use the audited sales cancellation workflow.')
    if p.status=='active' and a.status!='active':
        b=verify_batch(db,org,a.batch_id,lock=True)
        count=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=b.id,status='active').count()
        if b.capacity is not None and count>=b.capacity:raise HTTPException(409,'Batch is full; cannot reactivate animal')
    a.status=p.status;audit(db,user.id,'animal_status','v5_animal',a.id,p.status);db.commit();return animal_data(a)

def resolve_mix(db,org,batch_id,animal_id,when=None,shift='Any'):
    """One effective mix per target. A batch assignment applies to every animal
    in the batch. A dated replacement assignment takes precedence over old plans.
    """
    when=when or date.today()
    assignments=(db.query(FeedAssignment)
        .filter_by(organization_id=org.id,active=True)
        .filter(FeedAssignment.start_date<=when)
        .filter((FeedAssignment.end_date==None)|(FeedAssignment.end_date>=when))
        .order_by(FeedAssignment.id.desc()).all())
    # Preserve the daily target stored in an older feed plan IF it uses the
    # same assigned mix. Plans never unlock an alternative feed selection.
    def matching_plan_metadata(assignment):
        plans=(db.query(FeedPlan).filter_by(organization_id=org.id,active=True,ration_id=assignment.ration_id)
            .filter(FeedPlan.start_date<=when)
            .filter((FeedPlan.end_date==None)|(FeedPlan.end_date>=when))
            .filter(FeedPlan.shift.in_(['Any',shift]))
            .order_by(FeedPlan.id.desc()).all())
        for p in plans:
            if p.batch_id!=assignment.batch_id or p.animal_id!=assignment.animal_id:continue
            if p.frequency=='weekly' and (when-p.start_date).days%7:continue
            if p.frequency=='monthly' and when.day!=min(p.start_date.day,__import__('calendar').monthrange(when.year,when.month)[1]):continue
            return p.kg_per_head_day,p.id
        return None,None
    # A batch assignment locks all animals in that batch to one mix.
    for assignment in assignments:
        if assignment.batch_id==batch_id and assignment.animal_id is None:
            kg,plan_id=matching_plan_metadata(assignment)
            return assignment.ration_id,kg,plan_id
    for assignment in assignments:
        if animal_id and assignment.animal_id==animal_id:
            kg,plan_id=matching_plan_metadata(assignment)
            return assignment.ration_id,kg,plan_id
    q=(db.query(FeedPlan).filter_by(organization_id=org.id,active=True)
       .filter(FeedPlan.start_date<=when)
       .filter((FeedPlan.end_date==None)|(FeedPlan.end_date>=when))
       .filter(FeedPlan.shift.in_(['Any',shift])))
    plans=q.order_by(FeedPlan.id.desc()).all()
    def scheduled(plan):
        if plan.frequency=='weekly':return (when-plan.start_date).days % 7==0
        if plan.frequency=='monthly':return when.day==min(plan.start_date.day,__import__('calendar').monthrange(when.year,when.month)[1])
        return True
    for plan in plans:
        if scheduled(plan) and plan.batch_id==batch_id and plan.animal_id is None:
            return plan.ration_id,plan.kg_per_head_day,plan.id
    for plan in plans:
        if scheduled(plan) and animal_id and plan.animal_id==animal_id:
            return plan.ration_id,plan.kg_per_head_day,plan.id
    # Backwards compatibility for historical embedded recipe assignments.
    for r in db.query(Ration).filter_by(organization_id=org.id,batch_id=batch_id).order_by(Ration.id.desc()):
        return r.id,r.kg_per_head_day,None
    if animal_id:
        for r in db.query(Ration).filter_by(organization_id=org.id,animal_id=animal_id).order_by(Ration.id.desc()):
            return r.id,r.kg_per_head_day,None
    return None,None,None


@router.get('/feed/assignments')
def assignments(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'rations.read')
    rows=db.query(FeedAssignment).filter_by(organization_id=org.id).order_by(FeedAssignment.id.desc()).limit(300)
    return {'items':[dict(id=a.id,ration_id=a.ration_id,batch_id=a.batch_id,animal_id=a.animal_id,active=a.active,start_date=a.start_date.isoformat(),end_date=a.end_date.isoformat() if a.end_date else None) for a in rows]}

@router.post('/feed/assignments',status_code=201)
def assign_feed(p:FeedTarget,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True)
    verify_ration(db,org,p.ration_id)
    if p.batch_id:verify_batch(db,org,p.batch_id,lock=True)
    if p.animal_id:
        animal=verify_animal(db,org,p.animal_id)
        verify_batch(db,org,animal.batch_id,lock=True)
    # Replace the prior active assignment for this target. Keeping historic
    # rows permits audit while preventing ambiguous simultaneous selections.
    target=db.query(FeedAssignment).filter_by(organization_id=org.id,active=True,
                                            batch_id=p.batch_id,animal_id=p.animal_id).with_for_update().all()
    for previous in target:previous.active=False
    obj=FeedAssignment(organization_id=org.id,created_by=user.id,**p.model_dump())
    db.add(obj);db.flush();audit(db,user.id,'feed_assignment','v5_feed_assignment',obj.id,
                                 f'mix {obj.ration_id}; replaced {len(target)} older assignment(s)')
    db.commit();return {'id':obj.id,'message':'Mix assigned. This is the only available mix for the batch and its animals while active.'}

@router.get('/feed/plans')
def plans(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'rations.read')
    rows=db.query(FeedPlan).filter_by(organization_id=org.id).order_by(FeedPlan.id.desc()).limit(300)
    return {'items':[dict(id=a.id,ration_id=a.ration_id,batch_id=a.batch_id,animal_id=a.animal_id,kg_per_head_day=float(a.kg_per_head_day),shift=a.shift,frequency=a.frequency,active=a.active,start_date=a.start_date.isoformat(),end_date=a.end_date.isoformat() if a.end_date else None) for a in rows]}

@router.post('/feed/plans',status_code=201)
def plan_feed(p:FeedPlanIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,_=permission(ctx,db,'rations.write',True)
    verify_ration(db,org,p.ration_id)
    if p.batch_id:verify_batch(db,org,p.batch_id)
    if p.animal_id:verify_animal(db,org,p.animal_id)
    obj=FeedPlan(organization_id=org.id,created_by=user.id,**p.model_dump())
    db.add(obj);db.flush();audit(db,user.id,'feed_plan','v5_feed_plan',obj.id,str(obj.ration_id));db.commit();return {'id':obj.id,'message':'Feeding plan saved'}

@router.get('/routine/options')
def routine_options(db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False)
    permitted(m,'routine.read')
    batches=db.query(V5Batch).filter_by(organization_id=org.id).order_by(V5Batch.name).all()
    animal_rows=db.query(V5Animal).filter_by(organization_id=org.id,status='active').order_by(V5Animal.tag).limit(2000).all()
    from modules.inventory.service import FeedMixProduct
    from modules.fattening.models import balance
    item_rows=db.query(StockItem).filter_by(organization_id=org.id,category='feed',unit='kg').order_by(StockItem.name).all()
    from modules.inventory.models import usable_qty
    available={i.id:usable_qty(db,org,i.id,balance(db,org,i.id)) for i in item_rows}
    mix_links={m.ration_id:m.item_id for m in db.query(FeedMixProduct).filter_by(organization_id=org.id)}
    recipe_rows=db.query(Ration).filter_by(organization_id=org.id).order_by(Ration.name).all()
    medicine_rows=db.query(StockItem).filter_by(organization_id=org.id,category='medicine').order_by(StockItem.name).all()
    return {'batches':[dict(id=b.id,name=b.name,capacity=b.capacity,
               animal_count=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=b.id,status='active').count()) for b in batches],
            'animals':[dict(id=a.id,tag=a.tag,name=a.tag,batch_id=a.batch_id,species=a.species) for a in animal_rows],
            'feeds':[dict(id=i.id,name=i.name,category=i.category,unit=i.unit,available_kg=float(available[i.id]))
                 for i in item_rows if available[i.id]>0 and i.id not in set(mix_links.values())],
            'mixes':[dict(id=r.id,name=r.name,feed_type=r.feed_type,item_id=mix_links.get(r.id),
                  available_kg=float(available.get(mix_links.get(r.id),Decimal(0))))
                  for r in recipe_rows if available.get(mix_links.get(r.id),Decimal(0))>0],
            'medicines':[dict(id=x.id,name=x.name,unit=x.unit) for x in medicine_rows],
            'message':'Only feeds and finished mixes with positive posted stock are available for feeding.'}

@router.get('/feed/recommendation')
def recommendation(batch_id:int|None=None,animal_id:int|None=None,shift:str='Morning',db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False)
    if m.role!='org_admin' and m.role!='manager':permitted(m,'routine.feeding')
    if animal_id:
        a=verify_animal(db,org,animal_id);batch_id=a.batch_id
    if not batch_id:raise HTTPException(422,'Select a batch or animal')
    verify_batch(db,org,batch_id)
    rid,kg,plan_id=resolve_mix(db,org,batch_id,animal_id,shift=shift)
    from modules.inventory.service import FeedMixProduct
    from modules.fattening.models import balance
    ration=verify_ration(db,org,rid) if rid else None
    link=db.query(FeedMixProduct).filter_by(organization_id=org.id,ration_id=rid).first() if rid else None
    from modules.inventory.models import usable_qty
    available=usable_qty(db,org,link.item_id,balance(db,org,link.item_id)) if link else Decimal('0')
    return dict(batch_id=batch_id,animal_id=animal_id,ration_id=rid,feed_type=ration.feed_type if ration else None,
                ration_name=ration.name if ration else None,assigned_item_id=link.item_id if link else None,
                restrict_to_assigned_mix=bool(rid),kg_per_head_day=float(kg) if kg else None,
                plan_id=plan_id,ingredients=json.loads(ration.ingredients) if ration else [],
                available_mix_kg=float(available),stocked=available>0,
                message=('Only the assigned mix may be recorded for this batch or animal.' if available>0 and ration
                    else 'Assigned mix is out of stock. Receive or manufacture that mix before feeding.' if ration
                    else 'No mix assigned. Choose a stocked feed.'))

@router.post('/feeding/record',status_code=201)
def record_feeding(p:FeedingRecordIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    if m.role not in {'org_admin','manager'}:permitted(m,'routine.feeding')
    prior=db.query(V5Routine).filter_by(organization_id=org.id,client_reference=p.client_reference).first()
    if prior:
        if prior.category!='feeding':raise HTTPException(409,'Reference already belongs to another routine')
        return {'id':prior.id,'message':'Previously recorded; duplicate avoided'}
    if p.animal_id:
        a=verify_animal(db,org,p.animal_id)
        if a.status!='active':raise HTTPException(409,'Animal is not active')
        if p.batch_id and p.batch_id!=a.batch_id:raise HTTPException(422,'Animal does not belong to selected batch')
        b=verify_batch(db,org,a.batch_id)
    else:b=verify_batch(db,org,p.batch_id)
    # Serialize entries for one batch, including multiple staff submitting concurrently.
    b=verify_batch(db,org,b.id,lock=True)
    if p.shift in ('Morning','Afternoon','Evening'):
        from modules.employees.service import completed_shifts
        done=completed_shifts(db,org,'feeding',b.id,a.tag if p.animal_id else None)
        if p.shift in done:raise HTTPException(409,f'{p.shift} feeding was already recorded for this target today. Choose the next shift.')
    assigned_rid,_,_=resolve_mix(db,org,b.id,p.animal_id,shift=p.shift)
    rid=assigned_rid or p.ration_id
    if assigned_rid and p.ration_id and p.ration_id!=assigned_rid:
        raise HTTPException(409,'This batch has an assigned mix. Only that mix may be fed.')
    if p.ration_quantity_kg and not rid:
        raise HTTPException(422,'Choose a stocked feed or assign a mix first')
    if rid:verify_ration(db,org,rid)
    from modules.inventory.service import FeedMixProduct,commit_issue
    # The server is the authority: hiding other feeds in the browser is not enough.
    assigned_item_id=None
    if assigned_rid:
        linked=db.query(FeedMixProduct).filter_by(organization_id=org.id,ration_id=assigned_rid).first()
        if not linked:
            raise HTTPException(409,'Assigned mix has no finished stock. Receive or manufacture it before recording feeding.')
        assigned_item_id=linked.item_id
        if p.ration_quantity_kg and p.extras:
            raise HTTPException(422,'Record the assigned mix quantity only once')
        if any((line.item_id!=assigned_item_id if line.item_id is not None else line.ration_id!=assigned_rid) for line in p.extras):
            raise HTTPException(409,'Only the assigned mix is permitted for this batch and its animals.')
    from collections import defaultdict
    lines=[]
    if p.ration_quantity_kg:
        r=verify_ration(db,org,rid)
        link=db.query(FeedMixProduct).filter_by(ration_id=r.id,organization_id=org.id).first()
        if not link:raise HTTPException(409,'Mix has no registered finished stock item. Register the mix product first.')
        lines.append(dict(ration_id=r.id,item_id=link.item_id,name=r.name,quantity_kg=p.ration_quantity_kg))
    for l in p.extras:
        if l.item_id is not None:
            item=verify_item(db,org,l.item_id)
            if item.category.lower()!='feed' or item.unit.lower()!='kg':raise HTTPException(422,f'{item.name} must be a feed item measured in kg')
            lines.append(dict(item_id=item.id,ration_id=None,name=item.name,quantity_kg=l.quantity_kg))
        else:
            r=verify_ration(db,org,l.ration_id)
            link=db.query(FeedMixProduct).filter_by(ration_id=r.id,organization_id=org.id).first()
            if not link:raise HTTPException(409,f'{r.name} must be registered as a finished stock item')
            lines.append(dict(item_id=link.item_id,ration_id=r.id,name=r.name,quantity_kg=l.quantity_kg))
    requested=defaultdict(lambda:Decimal('0'))
    for line in lines:requested[line['item_id']]+=Decimal(line['quantity_kg'])
    # All matching stock item rows are locked before checking balances to serialize
    # simultaneous receipts, manual issues, and animal/batch feeding.
    db.query(StockItem).filter(StockItem.organization_id==org.id,StockItem.id.in_(sorted(requested))).order_by(StockItem.id).with_for_update().all()
    from modules.inventory.service import item_balance_and_cost
    for item_id,quantity in requested.items():
        available,_=item_balance_and_cost(db,org,item_id)
        if quantity>available:
            item=verify_item(db,org,item_id)
            raise HTTPException(409,f'{item.name}: only {available} kg in stock, requested {quantity} kg. Receive stock before feeding.')
    from modules.employees.service import claim_shift
    claim_shift(db,org,user,'feeding',b.id,p.animal_id,p.shift)
    qty=sum((line['quantity_kg'] for line in lines),Decimal(0))
    entry=V5Routine(organization_id=org.id,recorded_by=user.id,batch_id=b.id,
        category='feeding',shift=p.shift,animal_tag=a.tag if p.animal_id else None,
        product=', '.join(line['name'] for line in lines)[:180],quantity=float(qty),unit='kg',
        notes=p.notes,client_reference=p.client_reference)
    db.add(entry);db.flush()
    for line in lines:db.add(FeedingLine(organization_id=org.id,routine_id=entry.id,**line))
    cost_total=Decimal(0)
    for item_id,quantity in sorted(requested.items()):
        movement,cost=commit_issue(db,org,user,item_id,quantity,f'feed-{entry.id}-stock-{item_id}',date.today(),
            batch_id=b.id,note=f'Automatic issue for feeding #{entry.id}',source='feeding',animal_id=p.animal_id)
        cost_total+=cost
        stock_item=verify_item(db,org,item_id)
        from modules.fattening.models import balance
        from modules.inventory.models import usable_qty
        remaining=usable_qty(db,org,item_id,balance(db,org,item_id))
        if Decimal(stock_item.reorder_level or 0)>0 and remaining<=Decimal(stock_item.reorder_level):
            alert(db,org,'reorder','Feed stock needs reordering',f'{stock_item.name}: {remaining} kg remaining; reorder at {stock_item.reorder_level} kg.')
    from modules.employees.service import mark_matching_assignments
    tasks_completed=mark_matching_assignments(db,org,user,'feeding',b.id,p.shift,individual=bool(p.animal_id))
    audit(db,user.id,'feeding_record','v5_routine',entry.id,f'{qty} kg batch {b.id}; stock issues automatic')
    db.commit();return {'id':entry.id,'quantity_kg':float(qty),'stock_deducted':True,
                        'stock_issue_count':len(requested),'calculated_feed_cost':float(cost_total),'tasks_completed':tasks_completed,
                        'message':'Feeding recorded, stock deducted and feed cost posted to Finance'}

@router.get('/notifications')
def notifications(db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False)
    q=db.query(Notification).filter_by(organization_id=org.id)
    if m.role not in ('org_admin','manager'):q=q.filter(Notification.user_id==user.id)
    rows=q.order_by(Notification.id.desc()).limit(100).all()
    dynamic=[]
    sub=db.get(Subscription,org.id)
    if sub and sub.expires_at:
        expires=sub.expires_at.date()
        days=(expires-date.today()).days
        if days<=7:dynamic.append(dict(id=None,category='subscription',title='License expires soon' if days>=0 else 'License expired',message=f'{max(0,days)} days remaining' if days>=0 else 'Renew subscription to restore operations',is_read=False,created_at=None))
    if m.role in ('org_admin','manager'):
        for pr in db.query(V5Project).filter_by(organization_id=org.id,status='active').all():
            if pr.end_date and 0<=(pr.end_date-date.today()).days<=7:
                dynamic.append(dict(id=None,category='project',title='Project nearing end date',message=f'{pr.name} ends {pr.end_date.isoformat()}',is_read=False,created_at=None))
    return {'items':dynamic+[dict(id=n.id,category=n.category,title=n.title,message=n.message,is_read=n.is_read,created_at=n.created_at.isoformat()) for n in rows],
            'unread':len(dynamic)+sum(not n.is_read for n in rows)}

@router.post('/notifications/{notification_id}/read')
def mark_read(notification_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,False)
    n=db.query(Notification).filter_by(id=notification_id,organization_id=org.id).first()
    if not n:raise HTTPException(404,'Notification not found')
    if m.role not in ('org_admin','manager') and n.user_id!=user.id:raise HTTPException(403,'Not your notification')
    n.is_read=True;db.commit();return {'id':n.id,'is_read':True}

@router.get('/reports/summary')
def report_summary(project_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    if project_id is not None and not db.query(V5Project).filter_by(id=project_id,organization_id=org.id).first():raise HTTPException(404,'Project not found')
    bs=db.query(V5Batch).filter_by(organization_id=org.id)
    if project_id is not None:bs=bs.filter_by(project_id=project_id)
    batches=bs.all();ids=[b.id for b in batches]
    animals=db.query(V5Animal).filter(V5Animal.organization_id==org.id,V5Animal.batch_id.in_(ids)).all() if ids else []
    entries=db.query(V5Routine).filter(V5Routine.organization_id==org.id,V5Routine.batch_id.in_(ids)).all() if ids else []
    cash=db.query(FinanceEntry).filter(FinanceEntry.organization_id==org.id)
    if project_id is not None:cash=cash.filter(FinanceEntry.batch_id.in_(ids))
    money=cash.all()
    totals={}
    for x in money:
        if x.kind not in ('cost','revenue'):continue
        v=totals.setdefault(x.currency,{'cost':Decimal(0),'revenue':Decimal(0)})
        v[x.kind]+=x.amount
    expenses=sum((x.amount for x in money if x.kind=='cost'),Decimal(0))
    revenue=sum((x.amount for x in money if x.kind=='revenue'),Decimal(0))
    mixed=len(totals)>1
    counts={}
    for entry in entries:counts[entry.category]=counts.get(entry.category,0)+1
    kg=sum((Decimal(str(e.quantity)) for e in entries if e.category=='feeding' and e.unit=='kg' and e.quantity is not None),Decimal(0))
    occupied=sum(a.status=='active' for a in animals)
    feed_items=db.query(StockItem).filter_by(organization_id=org.id).all() if project_id is None else []
    stock=[]
    for item in feed_items:
        moves=db.query(StockMovement).filter_by(organization_id=org.id,item_id=item.id).all()
        bal=sum((m.quantity if m.direction in ('in','adjustment_in') else -m.quantity for m in moves),Decimal(0))
        stock.append(dict(name=item.name,unit=item.unit,balance=float(bal)))
    return dict(organization=org.name,project_id=project_id,generated_at=utcnow().isoformat(),
       project_count=db.query(V5Project).filter_by(organization_id=org.id).count() if project_id is None else 1,
       batch_count=len(batches),animal_count=len(animals),active_animals=occupied,
       batch_capacity=sum(b.capacity or 0 for b in batches),feeding_kg_recorded=float(kg),
       routine_counts=counts,recorded_cost=float(expenses) if not mixed else None,recorded_revenue=float(revenue) if not mixed else None,
       recorded_net=float(revenue-expenses) if not mixed else None,currency_totals={cur:{'cost':float(t['cost']),'revenue':float(t['revenue']),'net':float(t['revenue']-t['cost'])} for cur,t in totals.items()},stock_balances=stock,
       batches=[dict(name=b.name,project_id=b.project_id,active_animals=sum(a.batch_id==b.id and a.status=='active' for a in animals),capacity=b.capacity,status=b.status) for b in batches],
       note='Recorded net equals revenue less recorded operating costs, not fully allocated per-animal profit. Records are tenant-scoped; batch feeding is not measured individual intake. Feeding deducts stock and posts feed-consumption cost. Stock purchase is an inventory asset, not an immediate expense. Amounts are recorded transactions, not full accrual profitability. Project-level finance excludes unallocated costs. Different currencies are not summed together.')

@router.get('/reports/export')
def export_report(format:Literal['csv','pdf']='csv',project_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    data=report_summary(project_id=project_id,db=db,ctx=ctx)
    metrics=[('Organization',data['organization']),('Projects',data['project_count']),('Batches',data['batch_count']),
       ('Animals',data['animal_count']),('Active animals',data['active_animals']),('Total capacity',data['batch_capacity']),
       ('Feeding kg recorded',data['feeding_kg_recorded']),('Recorded costs',data['recorded_cost']),
       ('Recorded revenue',data['recorded_revenue']),('Net recorded',data['recorded_net'])]
    if format=='csv':
        out=io.StringIO();w=csv.writer(out);w.writerow(['Metric','Value']);w.writerows(metrics)
        w.writerow([]);w.writerow(['Batch','Project ID','Active animals','Capacity','Status'])
        for b in data['batches']:w.writerow([b['name'],b['project_id'],b['active_animals'],b['capacity'],b['status']])
        w.writerow([]);w.writerow(['Routine','Number recorded'])
        w.writerows(data['routine_counts'].items())
        w.writerow([]);w.writerow(['Feed stock','Unit','Balance'])
        for x in data['stock_balances']:w.writerow([x['name'],x['unit'],x['balance']])
        w.writerow([]);w.writerow([data['note']]);out.seek(0)
        return StreamingResponse(iter([out.getvalue().encode('utf-8-sig')]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="ranch-report.csv"'})
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from xml.sax.saxutils import escape as xml_escape
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,title='Ranch management report',leftMargin=42,rightMargin=42)
    styles=getSampleStyleSheet();story=[Paragraph('Ranch Management Report',styles['Title']),Paragraph(xml_escape(data['organization']),styles['Heading2']),Spacer(1,14)]
    table=Table([['Metric','Value']]+[[str(k),str(v)] for k,v in metrics],colWidths=[310,170])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7efe8')),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#cddbd0')),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.extend([table,Spacer(1,16),Paragraph('Batch occupancy',styles['Heading2'])])
    for b in data['batches']:story.append(Paragraph(xml_escape(f"{b['name']} — {b['active_animals']}/{b['capacity'] or 'unlimited'} active animals"),styles['Normal']))
    story.extend([Spacer(1,14),Paragraph(data['note'],styles['Normal'])]);doc.build(story);out.seek(0)
    return StreamingResponse(out,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="ranch-report.pdf"'})

ReportSection=Literal['animals','batches','pens','feeding','routines','inventory','finance','sales','projects']

@router.get('/reports/details')
def report_details(section:ReportSection='animals',project_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    if project_id is not None and not db.query(V5Project).filter_by(id=project_id,organization_id=org.id).first():raise HTTPException(404,'Project not found')
    ids=[b.id for b in db.query(V5Batch).filter_by(organization_id=org.id).filter(V5Batch.project_id==project_id).all()] if project_id else None
    rows=[]
    if section=='animals':
        query=db.query(V5Animal).filter_by(organization_id=org.id)
        if ids is not None:query=query.filter(V5Animal.batch_id.in_(ids))
        rows=[dict(tag=a.tag,batch_id=a.batch_id,species=a.species,breed=a.breed,sex=a.sex,age_months=a.age_months,
            origin=a.origin,supplier=a.supplier_name,entry_kg=float(a.entry_weight_kg) if a.entry_weight_kg is not None else None,
            current_kg=float(a.current_weight_kg) if a.current_weight_kg is not None else None,
            gain_kg=round(float(a.current_weight_kg-a.entry_weight_kg),3) if a.current_weight_kg is not None and a.entry_weight_kg is not None else None,
            status=a.status) for a in query.order_by(V5Animal.id.desc()).limit(1000)]
    elif section=='batches':
        query=db.query(V5Batch).filter_by(organization_id=org.id)
        if ids is not None:query=query.filter(V5Batch.id.in_(ids))
        rows=[batch_summary(db,b) for b in query.order_by(V5Batch.id.desc()).limit(1000)]
    elif section=='pens':
        from modules.fattening.schemas import Pen
        q=db.query(Pen).filter_by(organization_id=org.id)
        if ids is not None:q=q.filter(Pen.batch_id.in_(ids))
        rows=[dict(id=p.id,pen=p.name,batch_id=p.batch_id,description=p.description,status=p.status)
              for p in q.order_by(Pen.batch_id,Pen.name).limit(1000).all()]
    elif section in ('feeding','routines'):
        query=db.query(V5Routine).filter_by(organization_id=org.id)
        if ids is not None:query=query.filter(V5Routine.batch_id.in_(ids))
        if section=='feeding':query=query.filter_by(category='feeding')
        from database import User
        from modules.fattening.schemas import Pen
        recs=query.order_by(V5Routine.id.desc()).limit(1000).all()
        user_names={u.id:u.full_name for u in db.query(User).filter(User.id.in_([r.recorded_by for r in recs] or [-1])).all()}
        pen_names={p.id:p.name for p in db.query(Pen).filter(Pen.organization_id==org.id).all()}
        rows=[dict(id=r.id,category=r.category,batch_id=r.batch_id,pen=pen_names.get(r.pen_id),animal_tag=r.animal_tag,shift=r.shift,frequency=r.frequency,
            product=r.product,quantity=r.quantity,unit=r.unit,recorded_by=user_names.get(r.recorded_by,'Unknown'),created_at=r.created_at.isoformat())
            for r in recs]
    elif section=='inventory':
        # Inventory belongs to the organization; no project-level attribution is invented.
        if project_id is None:
            for item in db.query(StockItem).filter_by(organization_id=org.id).order_by(StockItem.name).limit(1000):
                moves=db.query(StockMovement).filter_by(organization_id=org.id,item_id=item.id).all()
                bal=sum((m.quantity if m.direction in ('in','adjustment_in') else -m.quantity for m in moves),Decimal(0))
                rows.append(dict(item=item.name,category=item.category,unit=item.unit,balance=float(bal),unit_cost=float(item.cost_per_unit)))
    elif section=='sales':
        from modules.fattening.router import AnimalSale,sale_dict
        q=db.query(AnimalSale).filter_by(organization_id=org.id)
        if ids is not None:q=q.filter(AnimalSale.batch_id.in_(ids))
        tags={a.id:a.tag for a in db.query(V5Animal).filter_by(organization_id=org.id).all()}
        rows=[sale_dict(record,tags.get(record.animal_id)) for record in q.order_by(AnimalSale.id.desc()).limit(1000).all()]
    elif section=='finance':
        query=db.query(FinanceEntry).filter_by(organization_id=org.id)
        if ids is not None:query=query.filter(FinanceEntry.batch_id.in_(ids))
        rows=[dict(id=x.id,batch_id=x.batch_id,animal_id=x.animal_id,type=x.kind,category=x.category,amount=float(x.amount),currency=x.currency,note=x.note,
            created_at=x.created_at.isoformat()) for x in query.order_by(FinanceEntry.id.desc()).limit(1000)]
    else:
        query=db.query(V5Project).filter_by(organization_id=org.id)
        if project_id is not None:query=query.filter_by(id=project_id)
        rows=[project_dict(db,org,p) for p in query.order_by(V5Project.id.desc()).limit(1000)]
    return dict(section=section,project_id=project_id,organization=org.name,items=rows,
        note='Reports show explicitly recorded organization-owned data (up to 1,000 recent records). Project-scoped inventory is omitted because items are not allocated to projects.')

@router.get('/reports/export-detail')
def export_report_detail(section:ReportSection='animals',format:Literal['csv','pdf']='csv',project_id:int|None=None,
                         db:Session=Depends(get_db),ctx=Depends(context)):
    report=report_details(section=section,project_id=project_id,db=db,ctx=ctx)
    keys=list(dict.fromkeys(k for row in report['items'] for k in row))
    if format=='csv':
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow([report['organization']+' — '+section]);writer.writerow(keys)
        def safe(v):
            v='' if v is None else str(v)
            return "'"+v if v.startswith(('=','+','-','@','\t','\r')) else v
        for row in report['items']:writer.writerow([safe(row.get(k)) for k in keys])
        writer.writerow([]);writer.writerow([report['note']]);output.seek(0)
        return StreamingResponse(iter([output.getvalue().encode('utf-8-sig')]),media_type='text/csv',
            headers={'Content-Disposition':f'attachment; filename="ranch-{section}.csv"'})
    from xml.sax.saxutils import escape as xml_escape
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, LongTable
    from reportlab.lib.styles import getSampleStyleSheet
    output=io.BytesIO();styles=getSampleStyleSheet();page=landscape(A4)
    story=[Paragraph(xml_escape(report['organization']),styles['Title']),Paragraph(section.title()+' Report',styles['Heading2']),Spacer(1,12)]
    if keys:
        width=(page[0]-80)/len(keys)
        data=[[Paragraph(xml_escape(str(k)),styles['BodyText']) for k in keys]]
        for row in report['items'][:500]:
            data.append([Paragraph(xml_escape(str(row.get(k) if row.get(k) is not None else ''))[:120],styles['BodyText']) for k in keys])
        table=LongTable(data,colWidths=[width]*len(keys),repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7efe8')),
            ('GRID',(0,0),(-1,-1),0.2,colors.HexColor('#c9d7cb')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),7)]))
        story.append(table)
    else:story.append(Paragraph('No records found.',styles['Normal']))
    story.extend([Spacer(1,15),Paragraph(xml_escape(report['note']),styles['Normal'])])
    doc=SimpleDocTemplate(output,pagesize=page,leftMargin=40,rightMargin=40,topMargin=38,bottomMargin=38)
    doc.build(story);output.seek(0)
    return StreamingResponse(output,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="ranch-{section}.pdf"'})

class RoutineMoveIn(BaseModel):
    animal_id:int
    destination_batch_id:int
    shift:Literal['Morning','Afternoon','Evening','Other']='Other'
    notes:str|None=None
    client_reference:str=Field(min_length=8,max_length=100)

@router.post('/routine/move',status_code=201)
def routine_move(p:RoutineMoveIn,db:Session=Depends(get_db),ctx=Depends(context)):
    user,org,m=ctx;licensed(db,org,True)
    if m.role not in ('org_admin','manager'):permitted(m,'routine.movement')
    previous=db.query(V5Routine).filter_by(organization_id=org.id,client_reference=p.client_reference).first()
    if previous:
        if previous.category!='movement':raise HTTPException(409,'Request reference already used')
        return {'id':previous.id,'message':'Movement was already recorded; duplicate avoided'}
    animal=verify_animal(db,org,p.animal_id,lock=True)
    if animal.status!='active':raise HTTPException(409,'Only active animals may move')
    old=verify_batch(db,org,animal.batch_id,lock=True)
    dest=verify_batch(db,org,p.destination_batch_id,lock=True)
    if dest.id==old.id:raise HTTPException(422,'Choose a different destination batch')
    if dest.project_id is None:raise HTTPException(409,'Destination batch must belong to a project')
    if dest.status=='completed':raise HTTPException(409,'Destination batch is completed')
    occupied=db.query(V5Animal).filter_by(organization_id=org.id,batch_id=dest.id,status='active').count()
    if dest.capacity is not None and occupied>=dest.capacity:raise HTTPException(409,'Destination batch is at maximum capacity')
    animal.batch_id=dest.id
    entry=V5Routine(organization_id=org.id,recorded_by=user.id,batch_id=dest.id,
        animal_tag=animal.tag,category='movement',shift=p.shift,product=(old.name+' → '+dest.name)[:180],
        quantity=None,unit=None,notes=p.notes,client_reference=p.client_reference)
    db.add(entry);db.flush()
    audit(db,user.id,'routine_move','v5_animal',animal.id,f'{old.id}->{dest.id}')
    alert(db,org,'movement','Animal transferred',f'{animal.tag}: {old.name} to {dest.name}')
    db.commit()
    return {'id':entry.id,'animal_id':animal.id,'from_batch_id':old.id,'to_batch_id':dest.id,'message':'Animal moved and movement recorded'}

# Fattening animal-level metrics, provenance and proposed selling prices.
from collections import defaultdict
from datetime import date
from modules.organizations.models import V5Batch as Batch, V5Ranch as Ranch, V5Routine as RoutineEntry
from modules.fattening.models import V5Animal as Animal, WeightObservation, FinanceEntry, AnimalSale
Project = V5Project

def _d(x): return Decimal(str(x or 0))


def _n(x): return round(float(x),3) if x is not None else None


def _fattening_cost_excluded(entry):
    """Exclude acquisition/cost of sales already represented by the purchase price.

    Reversals of sale COGS do not represent new animal production costs.
    """
    return entry.source_type in {
        'animal_procurement', 'animal_purchase', 'animal_cogs', 'cogs',
        'animal_sale_reversal',
    }


def _batch_shared_cost_allocations(db:Session,org_id:int,animal):
    """Transparent *estimated* equal-head split of posted batch-only operating costs.

    Each cost is split among animals currently associated with this batch that had
    entered fattening by its posting date, and which had not been sold beforehand.
    Actual feed *intake* is never imputed from the resulting financial allocation.
    Historical batch transfers / unrecorded costs can make this incomplete.
    """
    entries=(db.query(FinanceEntry)
             .filter(FinanceEntry.organization_id==org_id,
                     FinanceEntry.batch_id==animal.batch_id,
                     FinanceEntry.animal_id.is_(None),FinanceEntry.kind=='cost')
             .order_by(FinanceEntry.created_at,FinanceEntry.id).all())
    if not entries:
        return [], False
    members=db.query(Animal).filter_by(organization_id=org_id,batch_id=animal.batch_id).all()
    ids=[member.id for member in members]
    sales=(db.query(AnimalSale).filter(AnimalSale.organization_id==org_id,
                    AnimalSale.animal_id.in_(ids),AnimalSale.status=='completed').all()
           if ids else [])
    exit_dates={sale.animal_id:sale.sale_date for sale in sales}
    def present(member,entry):
        when=entry.created_at.date() if entry.created_at else date.today()
        entered=member.arrival_date or (member.created_at.date() if member.created_at else None)
        if entered and entered>when:return False
        # Same-day registration after posting is not evidence of prior
        # membership. Dated backfill on an earlier day is still eligible.
        if (entered==when and member.created_at and entry.created_at and
                member.created_at.replace(tzinfo=None)>entry.created_at.replace(tzinfo=None)):
            return False
        sold=exit_dates.get(member.id)
        return not (sold and sold<when)
    allocated=[]
    for entry in entries:
        if _fattening_cost_excluded(entry):continue
        if not entry.amount or entry.amount<=0:continue
        when=entry.created_at.date() if entry.created_at else date.today()
        eligible=[member for member in members if present(member,entry)]
        if not any(member.id==animal.id for member in eligible):continue
        if not eligible:continue
        allocated.append({
            'category':entry.category or 'Other batch operating costs',
            'currency':entry.currency or 'TZS',
            'amount':_d(entry.amount)/Decimal(len(eligible)),
            'source_id':entry.id, 'eligible_headcount':len(eligible),
            'method':'equal eligible headcount at expense date',
        })
    return allocated, bool(entries)


def animal_profile(db:Session,org_id:int,animal_id:int):
    animal=db.query(Animal).filter_by(id=animal_id,organization_id=org_id).first()
    if not animal:raise HTTPException(404,'Animal not found in your organization')
    batch=db.query(Batch).filter_by(id=animal.batch_id,organization_id=org_id).first()
    project=db.query(Project).filter_by(id=batch.project_id,organization_id=org_id).first() if batch and batch.project_id else None
    ranch=db.query(Ranch).filter_by(id=batch.ranch_id,organization_id=org_id).first() if batch else None
    entry_date=animal.arrival_date or (animal.created_at.date() if animal.created_at else None)
    now=date.today()
    days=(now-entry_date).days if entry_date and entry_date<=now else None
    weights=db.query(WeightObservation).filter_by(organization_id=org_id,animal_id=animal_id).order_by(WeightObservation.created_at,WeightObservation.id).all()
    curve=[]
    if entry_date and animal.entry_weight_kg is not None:curve.append({'date':entry_date.isoformat(),'kg':_n(animal.entry_weight_kg),'source':'entry'})
    curve.extend({'date':w.created_at.date().isoformat(),'kg':_n(w.weight_kg),'source':'weighing'} for w in weights)
    daily={point['date']:point for point in curve}
    latest_weight=animal.current_weight_kg
    gain=_d(latest_weight)-_d(animal.entry_weight_kg) if latest_weight is not None and animal.entry_weight_kg is not None else None
    first,last=next(iter(sorted(daily.items())),(None,None)),next(iter(sorted(daily.items(),reverse=True)),(None,None))
    elapsed=(date.fromisoformat(last[0])-date.fromisoformat(first[0])).days if first[0] and last[0] else 0
    adg=(_d(last[1]['kg'])-_d(first[1]['kg']))/Decimal(elapsed) if elapsed>0 else None
    routines=db.query(RoutineEntry).filter_by(organization_id=org_id,category='feeding',batch_id=animal.batch_id).order_by(RoutineEntry.created_at).all()
    individual=[r for r in routines if r.animal_tag==animal.tag]
    batch_events=[r for r in routines if not r.animal_tag]
    individual_ids=[r.id for r in individual]
    lines=(db.query(FeedingLine).filter(FeedingLine.organization_id==org_id,FeedingLine.routine_id.in_(individual_ids)).all() if individual_ids else [])
    measured_feed=sum((_d(x.quantity_kg) for x in lines),Decimal(0))
    if individual and not lines:
        measured_feed=sum((_d(r.quantity) for r in individual if r.unit=='kg'),Decimal(0))
    unmeasured_batch_feed=sum((_d(r.quantity) for r in batch_events if r.unit=='kg'),Decimal(0))

    currency=animal.purchase_currency or 'TZS'
    financial=defaultdict(lambda:defaultdict(lambda:Decimal(0)))
    cost_categories=defaultdict(lambda:defaultdict(lambda:Decimal(0)))
    direct=db.query(FinanceEntry).filter_by(organization_id=org_id,animal_id=animal_id).all()
    for entry in direct:
        cur=entry.currency or currency
        if entry.kind=='cost' and not _fattening_cost_excluded(entry):
            financial[cur]['direct_fattening_costs']+=_d(entry.amount)
            cost_categories[cur][entry.category or 'Other direct operating costs']+=_d(entry.amount)
        elif entry.kind=='revenue':
            financial[cur]['revenue']+=_d(entry.amount)
    shared,has_batch_costs=_batch_shared_cost_allocations(db,org_id,animal)
    for entry in shared:
        cur=entry['currency']
        financial[cur]['allocated_batch_costs']+=entry['amount']
        cost_categories[cur][f"{entry['category']} (batch allocation)"]+=entry['amount']
    sale=db.query(AnimalSale).filter_by(organization_id=org_id,animal_id=animal_id,status='completed').first()
    if sale:
        financial[sale.currency]['recorded_sale_value']=_d(sale.gross_amount)
        if entry_date and sale.sale_date>=entry_date:days=(sale.sale_date-entry_date).days
    currencies={currency}
    for cur,amounts in financial.items():
        if any(_d(amounts[name])!=0 for name in ('direct_fattening_costs','allocated_batch_costs')):
            currencies.add(cur)
    comparable=(len(currencies)==1)
    accounts=[]
    for cur in sorted(set(financial)|{currency}):
        direct_cost=financial[cur]['direct_fattening_costs']
        allocated_cost=financial[cur]['allocated_batch_costs']
        fattening=direct_cost+allocated_cost
        acquisition=_d(animal.purchase_cost) if cur==currency else Decimal(0)
        total=acquisition+fattening
        accounts.append({
            'currency':cur,'acquisition':_n(acquisition),
            'direct_fattening_costs':_n(direct_cost),'allocated_batch_costs':_n(allocated_cost),
            'fattening_costs':_n(fattening),
            'total_recorded_cost':_n(total) if comparable else None,
            'revenue':_n(financial[cur]['revenue']),
            'partial':bool(shared or not comparable),
            'note':('Multiple cost currencies; record approved FX conversion before consolidating.'
                    if not comparable else 'Recorded direct expenses plus estimated batch-cost allocation. Unposted or unknown costs are excluded.'),
        })
    acquisition=_d(animal.purchase_cost)
    fattening_total=(sum((financial[cur]['direct_fattening_costs']+financial[cur]['allocated_batch_costs'] for cur in currencies),Decimal(0))
                     if comparable else None)
    break_even_total=acquisition+fattening_total if comparable else None
    break_even_per_kg=(break_even_total/_d(latest_weight) if break_even_total is not None and
                       latest_weight is not None and _d(latest_weight)>0 else None)
    be_note=('Costs are recorded in different currencies. Record an approved currency conversion to calculate one break-even amount.'
             if not comparable else
             'Purchase price + recorded animal operating costs + estimated equal-head share of posted batch costs. '
             'Not a guaranteed final cost: unposted project overhead, historical transfers, missing costs and future expenses are not included.')
    break_even={
        'currency':currency,'purchase_cost':_n(acquisition),
        'direct_fattening_costs':_n(financial[currency]['direct_fattening_costs']) if comparable else None,
        'allocated_batch_costs':_n(financial[currency]['allocated_batch_costs']) if comparable else None,
        'fattening_costs':_n(fattening_total),'amount':_n(break_even_total),
        'per_kg':_n(break_even_per_kg),'weight_basis_kg':_n(latest_weight) if latest_weight is not None else None,
        'comparable':comparable,'provisional':True,
        'allocation_method':'Equal eligible animal headcount at each posted batch expense date' if shared else 'Direct posted animal costs only',
        'has_batch_allocations':bool(shared),'has_batch_costs':has_batch_costs,
        'note':be_note,
    }
    cost_breakdown=([{'category':'Animal purchase','currency':currency,'amount':_n(animal.purchase_cost),'allocation':'direct'}]
          + [{'category':category,'currency':cur,'amount':_n(value),'allocation':'estimated batch allocation' if category.endswith('(batch allocation)') else 'direct'}
             for cur,cats in cost_categories.items() for category,value in cats.items()])
    insights=_insights(days,adg,gain,individual,batch_events,sale)
    if shared:
        insights.append('Batch expenses are allocated by eligible headcount for costing, not treated as measured individual feed intake.')
    if not comparable:
        insights.append('Break-even requires valid currency conversion because linked expenses use different currencies.')
    return {'id':animal.id,'tag':animal.tag,'species':animal.species,'breed':animal.breed,'sex':animal.sex,
        'status':animal.status,'age_months_at_entry':animal.age_months,'entry_date':entry_date.isoformat() if entry_date else None,
        'days_spent':days,'supplier':animal.supplier_name,'origin':animal.origin,
        'batch_id':animal.batch_id,'batch':batch.name if batch else None,'project':project.name if project else None,
        'ranch':ranch.name if ranch else None,'entry_weight_kg':_n(animal.entry_weight_kg),
        'current_weight_kg':_n(latest_weight),'gain_kg':_n(gain),'adg_kg_day':_n(adg),
        'weight_series':[daily[d] for d in sorted(daily)],
        'feed_consumed_kg':_n(measured_feed) if individual else None,
        'feed_basis':'individually recorded feed' if individual else 'not measured individually',
        'batch_feed_recorded_kg':_n(unmeasured_batch_feed),
        'feeding_events':len(individual),'batch_feeding_events':len(batch_events),
        'feeding_series':[{'date':(r.created_at.date().isoformat() if r.created_at else None),
                           'kg':_n(sum((_d(line.quantity_kg) for line in lines if line.routine_id==r.id),Decimal(0))) if lines else _n(r.quantity) if r.unit=='kg' else None}
                           for r in individual],
        'cost_breakdown':cost_breakdown,'currency':currency,'purchase_price':_n(animal.purchase_cost),
        'accounts':accounts,'break_even':break_even,
        'sale':{'gross':_n(sale.gross_amount),'currency':sale.currency,'date':sale.sale_date.isoformat()} if sale else None,
        'insights':insights}


def _insights(days,adg,gain,individual,batch_events,sale):
    result=[]
    if sale:result.append('This animal has a completed sale. View its final sale record for actual proceeds.')
    if adg is None:result.append('More dated weight observations are needed to determine average daily gain.')
    elif adg<=0:result.append('Growth is not positive. Verify measurements and review nutrition and health with a qualified specialist.')
    if not individual and batch_events:result.append('Batch feeding exists, but individual feed intake is not measured. No individual FCR is inferred.')
    if not individual and not batch_events:result.append('No linked feeding activity has been recorded for this animal or its batch.')
    return result


def profile_overview(db,org_id:int):
    from modules.reports.service import report
    from modules.organizations.service import Organization
    org=db.get(Organization,org_id)
    if not org:raise HTTPException(404,'Organization not found')
    return report(db,org)


def animal_performance_list(db:Session,org_id:int,batch_id:int|None=None,limit:int=100):
    """Tenant-scoped animal register with automatic and provenance-labelled break-even."""
    q=db.query(Animal).filter_by(organization_id=org_id)
    if batch_id is not None:q=q.filter(Animal.batch_id==batch_id)
    animals=q.order_by(Animal.id.desc()).limit(limit).all()
    summaries=[]
    for animal in animals:
        profile=animal_profile(db,org_id,animal.id)
        account=next((a for a in profile['accounts'] if a['currency']==profile['currency']),None)
        be=profile['break_even']
        summaries.append({
            'id':profile['id'],'tag':profile['tag'],'batch':profile['batch'],'batch_id':profile['batch_id'],
            'breed':profile['breed'],'status':profile['status'],'entry_date':profile['entry_date'],
            'age_months_at_entry':profile['age_months_at_entry'],'days_spent':profile['days_spent'],
            'entry_weight_kg':profile['entry_weight_kg'],'current_weight_kg':profile['current_weight_kg'],
            'weight_gain_kg':profile['gain_kg'],'adg_kg_day':profile['adg_kg_day'],
            'individual_feed_kg':profile['feed_consumed_kg'],'feed_basis':profile['feed_basis'],
            'purchase_price':profile['purchase_price'],
            'direct_fattening_costs':account['direct_fattening_costs'] if account else None,
            'allocated_batch_costs':account['allocated_batch_costs'] if account else None,
            'fattening_costs':be['fattening_costs'],
            'total_attributable_cost':be['amount'],'break_even_point':be['amount'],
            'break_even_per_kg':be['per_kg'],'currency':be['currency'],
            'break_even_provisional':be['provisional'],
        })
    return {'items':summaries,'count':len(summaries),'limit':limit,
            'note':'Break-even = recorded acquisition + direct animal expenses + estimated eligible-headcount share of posted batch costs. Multi-currency costs require conversion. Unposted expenses are excluded.'}


# V7.1 - organization-scoped, read-only submodule intelligence.
# Keep operational posting in the existing service transactions; reporting must
# never mutate the ledger or invent individual allocations of batch feeding.
def fattening_section_insights(db:Session, org_id:int, section:str, *, currency:str|None=None, animal_id:int|None=None):
    """Tenant-safe evidence-backed figures for the nine Animal Fattening screens.

    Missing readings stay missing; different currencies are never summed.
    Raw ORM objects and serialized ingredient JSON never reach the UI.
    """
    from collections import Counter, defaultdict
    from modules.fattening.models import Pen, FeedAssignment, MixReferenceAmount
    from modules.inventory.models import StockItem
    from modules.organizations.models import V5Ranch, V5Routine
    from database import User

    known=('ranches','projects','batches','pens','animals','weighing','feeding','mixes','sales')
    if section not in known:
        raise HTTPException(404,'Unknown fattening area')
    ranches=db.query(Ranch).filter_by(organization_id=org_id).all()
    projects=db.query(Project).filter_by(organization_id=org_id).all()
    batches=db.query(Batch).filter_by(organization_id=org_id).all()
    animals=db.query(Animal).filter_by(organization_id=org_id).all()
    pens=db.query(Pen).filter_by(organization_id=org_id).all()
    weights=db.query(WeightObservation).filter_by(organization_id=org_id).order_by(WeightObservation.created_at).limit(6000).all()
    feeding=db.query(V5Routine).filter_by(organization_id=org_id,category='feeding').order_by(V5Routine.created_at.desc()).limit(5000).all()
    feeding_ids=[r.id for r in feeding]
    lines=(db.query(FeedingLine).filter(FeedingLine.organization_id==org_id,FeedingLine.routine_id.in_(feeding_ids)).all()
           if feeding_ids else [])
    mixes=db.query(Ration).filter_by(organization_id=org_id).all()
    assignments=db.query(FeedAssignment).filter_by(organization_id=org_id).all()
    refs=db.query(MixReferenceAmount).filter_by(organization_id=org_id).all()
    sales=db.query(AnimalSale).filter_by(organization_id=org_id,status='completed').all()
    costs=db.query(FinanceEntry).filter_by(organization_id=org_id).all()
    feed_ids={l.item_id for l in lines if l.item_id}
    feed_ids.update(x.item_id for x in refs)
    items=(db.query(StockItem).filter(StockItem.organization_id==org_id,StockItem.id.in_(feed_ids)).all()
           if feed_ids else [])
    names={x.id:x.name for x in items}
    ranchname={r.id:r.name for r in ranches}
    projectname={p.id:p.name for p in projects}
    batchname={b.id:b.name for b in batches}
    animal_by_id={a.id:a for a in animals}
    animal_tag={a.tag:a for a in animals}
    batch_by_id={b.id:b for b in batches}
    ration_by_id={r.id:r for r in mixes}
    refs_by_mix=defaultdict(list)
    for ref in refs: refs_by_mix[ref.ration_id].append(ref)
    line_by_routine=defaultdict(list)
    for line in lines: line_by_routine[line.routine_id].append(line)
    active=[a for a in animals if a.status=='active']
    pop=Counter(a.batch_id for a in active)
    to_float=lambda v:round(float(v),3) if v is not None else None
    total=lambda xs:round(sum(float(v or 0) for v in xs),3)
    kpis=[];charts=[];rows=[];columns=[];insights=[]
    def k(label,value,note=None):kpis.append({'label':label,'value':value if value is not None else '—','note':note})
    def ch(title,kind,points,unit='',note=None):
        vals=[{'label':str(x['label']),'value':round(float(x['value']),3)} for x in points if x.get('value') is not None]
        charts.append({'title':title,'kind':kind,'points':vals[-24:],'unit':unit,'note':note})
    def ct(x):return x.created_at.date().isoformat() if x.created_at else None
    def amount(cost):return float(cost.amount or 0)
    # Costs are grouped by currency; purchases of inventory and acquisition
    # do not represent consumed fattening overhead at receipt time.
    def expense(e):
        return e.kind=='cost' and e.source_type not in {
            'inventory_purchase','stock_receipt','animal_procurement','animal_purchase','animal_cogs','cogs',
            'animal_sale_reversal','inventory_acquisition'}
    currencies=sorted(set(e.currency or 'TZS' for e in costs))
    currency=currency if currency in currencies else (currencies[0] if len(currencies)==1 else None)
    def financial(bid=None,pid=None):
        out=defaultdict(lambda:defaultdict(float))
        project_batch_ids={b.id for b in batches if b.project_id==pid} if pid else None
        for e in costs:
            if bid is not None and e.batch_id!=bid:continue
            if pid is not None and e.batch_id not in project_batch_ids:continue
            if expense(e):out[e.currency]['operating']+=amount(e)
            if e.kind=='revenue' and e.source_type!='animal_sale_reversal':out[e.currency]['revenue']+=amount(e)
        return out
    def costs_chart(title,records):
        bycur=defaultdict(lambda:defaultdict(float))
        for e in records:
            if expense(e):bycur[e.currency][e.category or 'Other']+=amount(e)
        for cur,cats in sorted(bycur.items()):
            ch(f'{title} · {cur}','bar',[{'label':cat,'value':v} for cat,v in sorted(cats.items(),key=lambda x:-x[1])[:8]],cur,
               'Posted operating costs only; unused feed and unallocated overhead are not inferred.')
    if section=='ranches':
        k('Registered ranches',len(ranches));k('Fattening projects',len(projects));k('Active animals',len(active))
        k('Batches',len(batches))
        by_ranch={r.id:sum(pop.get(b.id,0) for b in batches if b.ranch_id==r.id) for r in ranches}
        ch('Active animals by ranch','bar',[{'label':r.name,'value':by_ranch[r.id]} for r in ranches],'animals')
        ch('Project distribution','bar',[{'label':r.name,'value':sum(1 for p in projects if p.ranch_id==r.id)} for r in ranches],'projects')
        columns=[('name','Ranch'),('location','Location'),('projects','Projects'),('animals','Active animals'),('batch_capacity','Recorded batch capacity')]
        rows=[{'id':r.id,'name':r.name,'location':r.location or '—',
               'projects':sum(p.ranch_id==r.id for p in projects),'animals':by_ranch[r.id],
               'batch_capacity':sum((b.capacity or 0) for b in batches if b.ranch_id==r.id)} for r in ranches]
        insights.append('Ranch capacity is a sum of registered batch limits, not an independently verified physical ranch limit.')
    elif section=='projects':
        k('Fattening projects',len(projects));k('Active projects',sum(p.status=='active' for p in projects))
        k('Enrolled animals',len(animals));k('Batches',len(batches))
        ch('Animals per project','bar',[{'label':p.name,'value':sum(pop.get(b.id,0) for b in batches if b.project_id==p.id)} for p in projects],'animals')
        columns=[('name','Project'),('ranch','Ranch'),('status','Status'),('batches','Batches'),('animals','Active animals'),('budget','Budget'),('operating_costs','Posted operating costs'),('realized_revenue','Realized revenue'),('currency','Currency')]
        rows=[]
        for p in projects:
            project_finances=financial(pid=p.id)
            own=project_finances.get(p.currency,{})
            other_currencies=[c for c,amounts in project_finances.items() if c!=p.currency and any(amounts.values())]
            rows.append({'id':p.id,'name':p.name,'ranch':ranchname.get(p.ranch_id,'—'),'status':p.status,
                'batches':sum(b.project_id==p.id for b in batches),
                'animals':sum(pop.get(b.id,0) for b in batches if b.project_id==p.id),
                'budget':to_float(p.budget),'operating_costs':round(own.get('operating',0),2),
                'realized_revenue':round(own.get('revenue',0),2),'currency':p.currency,
                'unconverted_currencies':other_currencies})
        for cur in sorted({p.currency for p in projects}):
            ch(f'Posted project operating costs · {cur}','bar',[
               {'label':p.name,'value':next((r['operating_costs'] for r in rows if r['id']==p.id),0)}
               for p in projects if p.currency==cur],cur,
               'Shared project allocations are not inferred; different transaction currencies remain separate.')
        for cur in sorted({p.currency for p in projects if p.budget is not None}):
            ch(f'Planned project budgets · {cur}','bar',[{'label':p.name,'value':float(p.budget)} for p in projects if p.currency==cur and p.budget is not None],cur)
        costs_chart('Project operating expense categories',costs)
        insights.append('Project operating cost records may include shared expenses and cannot automatically be equated with fully allocated project profit.')
    elif section=='batches':
        k('Total batches',len(batches));k('Active animals',len(active));k('Maximum recorded spaces',sum(b.capacity or 0 for b in batches))
        cap=sum(b.capacity or 0 for b in batches)
        k('Occupancy',f'{round(100*len(active)/cap,1)}%' if cap else None)
        ch('Animal occupancy by batch','bar',[{'label':b.name,'value':pop.get(b.id,0)} for b in batches],'animals')
        ch('Recorded batch capacity','bar',[{'label':b.name,'value':b.capacity or 0} for b in batches],'animals')
        columns=[('name','Batch'),('project','Project'),('active_animals','Active animals'),('capacity','Maximum capacity'),('occupancy','Occupancy'),('status','Status')]
        rows=[{'id':b.id,'name':b.name,'project':projectname.get(b.project_id,'—'),
               'active_animals':pop.get(b.id,0),'capacity':b.capacity,'occupancy':f'{round(pop.get(b.id,0)*100/b.capacity,1)}%' if b.capacity else '—',
               'status':b.status} for b in batches]
        if any(b.capacity and pop.get(b.id,0)/b.capacity>=.9 for b in batches):insights.append('One or more batches exceed 90% of recorded capacity. Review space before moving animals.')
        else:insights.append('Occupancy is based on active animal registration, not a manually typed batch count.')
    elif section=='pens':
        cleaning=db.query(V5Routine).filter_by(organization_id=org_id,category='cleaning').order_by(V5Routine.created_at.desc()).limit(3000).all()
        done=Counter(x.pen_id for x in cleaning if x.pen_id)
        k('Registered pens',len(pens));k('Cleaning entries',len(cleaning));k('Pens cleaned',sum(done[p.id]>0 for p in pens))
        ch('Recorded cleaning by pen','bar',[{'label':p.name,'value':done[p.id]} for p in pens],'records')
        ch('Cleaning records by date','line',[{'label':d,'value':n} for d,n in sorted(Counter(ct(x) for x in cleaning if ct(x)).items())],'records')
        columns=[('name','Pen'),('batch','Batch'),('status','Status'),('cleanings','Cleaning records')]
        rows=[{'id':p.id,'name':p.name,'batch':batchname.get(p.batch_id,'—'),'status':p.status,'cleanings':done[p.id]} for p in pens]
        insights.append('Pen capacity and individual occupancy cannot be calculated accurately until explicit pen-allocation records exist.')
    elif section=='animals':
        k('Active animals',len(active));k('All registered animals',len(animals));k('Animals sold',sum(a.status=='sold' for a in animals))
        k('With current weight',sum(a.current_weight_kg is not None for a in active))
        ch('Current weight by animal','bar',[{'label':a.tag,'value':float(a.current_weight_kg)} for a in active if a.current_weight_kg is not None][:15],'kg')
        ch('Animal population by batch','bar',[{'label':batchname.get(b.id,'Batch'),'value':pop.get(b.id,0)} for b in batches],'animals')
        columns=[('tag','Animal'),('batch','Batch'),('entry_date','Entry date'),('age_months','Age (months)'),('days_spent','Days in fattening'),('entry_weight_kg','Entry weight kg'),('current_weight_kg','Current weight kg'),('gain_kg','Gain kg'),('purchase_price','Purchase cost'),('currency','Currency'),('status','Status')]
        rows=[]
        for a in animals:
            entry=a.arrival_date or (a.created_at.date() if a.created_at else None)
            exit_sale=next((s for s in sales if s.animal_id==a.id),None)
            endpoint=exit_sale.sale_date if exit_sale else date.today()
            gain=float(a.current_weight_kg-a.entry_weight_kg) if a.entry_weight_kg is not None and a.current_weight_kg is not None else None
            rows.append({'id':a.id,'tag':a.tag,'batch':batchname.get(a.batch_id,'—'),
                'entry_date':entry.isoformat() if entry else None,'age_months':a.age_months,
                'days_spent':(endpoint-entry).days if entry and endpoint>=entry else None,
                'entry_weight_kg':to_float(a.entry_weight_kg),'current_weight_kg':to_float(a.current_weight_kg),
                'gain_kg':round(gain,3) if gain is not None else None,'purchase_price':to_float(a.purchase_cost),
                'currency':a.purchase_currency,'status':a.status})
        insights.append('Individual FCR cannot be inferred from batch-level feed quantities. Open an animal profile for measured consumption and attributable costs.')
    elif section=='weighing':
        # A weight observation belongs exclusively to one animal. Never average
        # readings from different animals into a purported growth trend.
        if animal_id is not None and animal_id not in animal_by_id:
            raise HTTPException(404,'Animal not found for this organization')
        selected = (animal_by_id.get(animal_id) if animal_id is not None else
                    next((a for a in active if any(w.animal_id == a.id for w in weights)),None) or
                    (active[0] if active else (animals[0] if animals else None)))
        selected_weights = sorted((w for w in weights if selected and w.animal_id == selected.id),
                                   key=lambda w:(w.created_at or datetime.min,w.id))
        k('Selected animal',selected.tag if selected else '—')
        k('Recorded weighings',len(selected_weights))
        k('Current live weight',f'{to_float(selected.current_weight_kg):,} kg' if selected and selected.current_weight_kg is not None else 'Not recorded')
        gain=(float(selected.current_weight_kg)-float(selected.entry_weight_kg)
              if selected and selected.current_weight_kg is not None and selected.entry_weight_kg is not None else None)
        k('Gain since entry',f'{gain:,.2f} kg' if gain is not None else 'Insufficient data')
        # Build one chronological series for the selected animal only. Use its
        # recorded arrival weight when dated, and then actual dated readings.
        entry=(selected.arrival_date or (selected.created_at.date() if selected.created_at else None)) if selected else None
        readings={}
        if selected and entry and selected.entry_weight_kg is not None:
            readings[entry.isoformat()]=float(selected.entry_weight_kg)
        for w in selected_weights:
            if ct(w):readings[ct(w)]=float(w.weight_kg)
        points=[{'label':day,'value':val} for day,val in sorted(readings.items())]
        ch(f'{selected.tag} · Live weight progression' if selected else 'Individual weight progression',
           'line',points,'kg','Measurements are recorded against this animal only, not a batch.')
        if selected and selected.entry_weight_kg is not None:
            ch(f'{selected.tag} · Gain since entry','line',[
                {'label':p['label'],'value':round(p['value']-float(selected.entry_weight_kg),3)} for p in points
            ],'kg','Gain compared with this animal’s recorded entry weight.')
        columns=[('tag','Animal'),('date','Weighing date'),('weight_kg','Live weight (kg)'),('notes','Observation')]
        rows=[{'id':w.animal_id,'tag':selected.tag,'date':ct(w),'weight_kg':to_float(w.weight_kg),
               'notes':w.notes or '—'} for w in selected_weights[::-1]] if selected else []
        insights.append('Each weight is associated with a single animal; changes between animals are never averaged into the selected animal’s growth chart.')
        if not selected_weights:insights.append('No follow-up weighing has been recorded for this animal yet.')
    elif section=='feeding':
        totals=defaultdict(float);shifts=defaultdict(float);by_date=defaultdict(float);by_batch=defaultdict(float)
        for r in feeding:
            linked=line_by_routine[r.id]
            qty=sum(float(x.quantity_kg) for x in linked) if linked else float(r.quantity or 0) if r.unit=='kg' else 0
            totals[r.id]=qty;shifts[r.shift]+=qty
            if ct(r):by_date[ct(r)]+=qty
            by_batch[r.batch_id]+=qty
        k('Feeding events',len(feeding));k('Recorded feed issued',f'{round(sum(totals.values()),1):,} kg');k('Batches fed',len({r.batch_id for r in feeding if r.batch_id}))
        ch('Feed issued by day','line',[{'label':d,'value':v} for d,v in sorted(by_date.items())],'kg')
        ch('Feed by shift','bar',[{'label':shift,'value':qty} for shift,qty in shifts.items()],'kg')
        ch('Feed issued by batch','bar',[{'label':batchname.get(bid,'—'),'value':qty} for bid,qty in by_batch.items()],'kg')
        columns=[('date','Date'),('batch','Batch'),('animal','Animal'),('shift','Shift'),('feed','Feed / Mix'),('quantity_kg','Quantity kg'),('recorder','Recorded by')]
        userids={x.recorded_by for x in feeding}
        staff={u.id:u.full_name for u in db.query(User).filter(User.id.in_(userids or [-1])).all()}
        rows=[]
        for r in feeding[:350]:
            linked=line_by_routine[r.id]
            rows.append({'id':r.id,'date':ct(r),'batch':batchname.get(r.batch_id,'—'),
                 'animal':r.animal_tag or 'Whole batch','shift':r.shift,
                 'feed':', '.join(x.name for x in linked) or r.product or '—',
                 'quantity_kg':round(totals[r.id],3),'recorder':staff.get(r.recorded_by,'—')})
        insights.append('Batch feeding quantity represents the group total. It must never be labelled as measured intake of each animal.')
    elif section=='mixes':
        k('Feed mix recipes',len(mixes));k('Active assignments',sum(a.active and a.start_date<=date.today() and (a.end_date is None or a.end_date>=date.today()) for a in assignments))
        stages=Counter(m.feed_type for m in mixes)
        ch('Mixes by feeding stage','bar',[{'label':stage.title(),'value':n} for stage,n in stages.items()],'mixes')
        mix_usage=Counter(a.ration_id for a in assignments if a.active)
        ch('Assignments by mix','bar',[{'label':m.name,'value':mix_usage[m.id]} for m in mixes],'assignments')
        columns=[('name','Feed Mix'),('stage','Stage'),('ingredients','Ingredients'),('total_kg','Reference quantity kg'),('assignments','Active assignments')]
        rows=[]
        for m in mixes:
            composition=_mix_composition(m,refs_by_mix[m.id],names)
            rows.append({'id':m.id,'name':m.name,'stage':m.feed_type,'ingredients':len(composition),
                'total_kg':round(sum(x.get('quantity_kg') or 0 for x in composition),3) if any(x.get('quantity_kg') is not None for x in composition) else None,
                'assignments':mix_usage[m.id]})
        insights.append('A recipe defines feed proportions, not stock. Ingredients are deducted only when a finished mix is manufactured.')
    else: # sales
        k('Completed animal sales',len(sales));k('Animals sold',len({s.animal_id for s in sales}));k('Buyers',len({s.buyer_name for s in sales}))
        currencies_in_sales=sorted({s.currency for s in sales})
        for cur in currencies_in_sales:
            daily=defaultdict(float)
            for s in sales:
                if s.currency==cur:daily[s.sale_date.isoformat()]+=float(s.gross_amount)
            ch(f'Sales revenue over time · {cur}','line',[{'label':d,'value':v} for d,v in sorted(daily.items())],cur)
        buyers=Counter(s.buyer_name for s in sales)
        ch('Sales count by buyer','bar',[{'label':n,'value':v} for n,v in buyers.most_common(10)],'sales')
        sold_by_day=Counter(s.sale_date.isoformat() for s in sales)
        ch('Number of animals sold by date','line',[{'label':d,'value':v} for d,v in sorted(sold_by_day.items())],'animals')
        columns=[('date','Sale date'),('animal','Animal'),('buyer','Buyer'),('basis','Sale basis'),('weight_kg','Sale weight kg'),('gross','Revenue'),('currency','Currency')]
        rows=[{'id':s.id,'date':s.sale_date.isoformat(),'animal':animal_by_id[s.animal_id].tag if s.animal_id in animal_by_id else '—',
            'buyer':s.buyer_name,'basis':s.price_basis,'weight_kg':to_float(s.weight_kg),
            'gross':to_float(s.gross_amount),'currency':s.currency} for s in sorted(sales,key=lambda x:x.sale_date,reverse=True)]
        insights.append('Sales revenue is not net profit. Acquisition, realized COGS, attributed operating costs and selling expenses must be reconciled by currency.')
    return {'section':section,'kpis':kpis,'charts':charts,'columns':[{'key':c[0],'label':c[1]} for c in columns],
            'rows':rows[:500],'insights':insights,'currency_options':currencies,
            'note':'Live organization records; missing values stay unavailable. Charts never use placeholder sample figures.'}


def _mix_composition(mix,reference_lines,item_names):
    """Return name / kg / % tables, never serialized objects or IDs."""
    import json
    if reference_lines:
        total=sum(float(x.quantity_kg) for x in reference_lines)
        return [{'name':item_names.get(x.item_id,f'Feed #{x.item_id}'),
                 'quantity_kg':round(float(x.quantity_kg),3),
                 'percentage':round(float(x.quantity_kg)*100/total,2) if total else 0}
                for x in reference_lines]
    try: raw=json.loads(mix.ingredients or '[]')
    except (ValueError,TypeError):raw=[]
    result=[]
    for line in raw if isinstance(raw,list) else []:
        if not isinstance(line,dict):continue
        iid=line.get('item_id')
        result.append({'name':item_names.get(iid,f'Feed #{iid}' if iid else 'Unidentified feed'),
                       'quantity_kg':None,'percentage':round(float(line.get('percent') or 0),2)})
    return result


def fattening_mix_details(db:Session,org_id:int,mix_id:int):
    from modules.fattening.models import MixReferenceAmount, FeedAssignment
    from modules.inventory.models import StockItem
    mix=db.query(Ration).filter_by(organization_id=org_id,id=mix_id).first()
    if not mix:raise HTTPException(404,'Feed mix not found in this organization')
    refs=db.query(MixReferenceAmount).filter_by(organization_id=org_id,ration_id=mix_id).all()
    try:ids={x.item_id for x in refs}
    except Exception:ids=set()
    import json
    try:legacy=json.loads(mix.ingredients or '[]')
    except (ValueError,TypeError):legacy=[]
    for row in legacy if isinstance(legacy,list) else []:
        if isinstance(row,dict) and row.get('item_id'):ids.add(int(row['item_id']))
    names={x.id:x.name for x in db.query(StockItem).filter(StockItem.organization_id==org_id,StockItem.id.in_(ids or [-1])).all()}
    composition=_mix_composition(mix,refs,names)
    targets=db.query(FeedAssignment).filter_by(organization_id=org_id,ration_id=mix_id).order_by(FeedAssignment.start_date.desc()).all()
    batches={x.id:x.name for x in db.query(Batch).filter_by(organization_id=org_id).all()}
    animals={x.id:x.tag for x in db.query(Animal).filter_by(organization_id=org_id).all()}
    assignments=[{'target':('Batch: '+batches.get(a.batch_id,'Unknown batch')) if a.batch_id else ('Animal: '+animals.get(a.animal_id,'Unknown animal')),
                  'start_date':a.start_date.isoformat(),'end_date':a.end_date.isoformat() if a.end_date else None,
                  'status':'Active' if a.active and a.start_date<=date.today() and (not a.end_date or a.end_date>=date.today()) else 'Historical'} for a in targets]
    return {'id':mix.id,'name':mix.name,'stage':mix.feed_type,'ingredients':composition,'assignments':assignments,
            'total_reference_kg':round(sum(x['quantity_kg'] or 0 for x in composition),3) if any(x['quantity_kg'] is not None for x in composition) else None,
            'note':'Recipe values do not represent physical manufactured stock. Historical percentage-only recipes may not have reference kilogram quantities.'}


# V7.6: project operations, animal registrations, posted inventory/finance and sales
# are joined by current batch -> project. Report reads do NOT post another ledger entry.
def fattening_project_dashboard(db:Session,org_id:int,project_id:int):
    from .models import FatteningProjectPlan, FatteningPlanHistory
    from modules.organizations.models import V5Routine
    from collections import defaultdict
    project=db.query(V5Project).filter_by(id=project_id,organization_id=org_id).first()
    if not project:raise HTTPException(404,'Project does not belong to your organization')
    batches=db.query(Batch).filter_by(organization_id=org_id,project_id=project_id).all()
    batch_ids={b.id for b in batches}
    animals=(db.query(Animal).filter(Animal.organization_id==org_id,Animal.batch_id.in_(batch_ids)).all() if batch_ids else [])
    animal_ids={a.id for a in animals}
    finance=(db.query(FinanceEntry).filter(FinanceEntry.organization_id==org_id,
       (FinanceEntry.batch_id.in_(batch_ids)) | (FinanceEntry.animal_id.in_(animal_ids))).order_by(FinanceEntry.created_at).all()
       if batch_ids or animal_ids else [])
    sales=(db.query(AnimalSale).filter(AnimalSale.organization_id==org_id,
       AnimalSale.animal_id.in_(animal_ids),AnimalSale.status=='completed').all() if animal_ids else [])
    routines=(db.query(V5Routine).filter(V5Routine.organization_id==org_id,
       V5Routine.batch_id.in_(batch_ids),V5Routine.category=='feeding').all() if batch_ids else [])
    plan=db.query(FatteningProjectPlan).filter_by(organization_id=org_id,project_id=project_id).first()
    plan_data=json.loads(plan.plan_json) if plan else None
    plan_status=plan.status if plan else 'not_planned'
    per_currency=defaultdict(lambda:{'animal_purchases':Decimal(0),'operating_costs':Decimal(0),'sale_revenue':Decimal(0),'selling_expenses':Decimal(0)})
    costs_by_category=defaultdict(lambda:defaultdict(lambda:Decimal(0)))
    for animal in animals:per_currency[animal.purchase_currency or project.currency]['animal_purchases']+=_d(animal.purchase_cost)
    seen_ids=set()
    for e in finance:
        if e.id in seen_ids:continue
        seen_ids.add(e.id)
        cur=e.currency or project.currency
        if e.kind!='cost' or _fattening_cost_excluded(e):continue
        # Posted sales selling expenses are kept separate for clarity.
        if e.source_type=='animal_sale_expense':per_currency[cur]['selling_expenses']+=_d(e.amount)
        else:per_currency[cur]['operating_costs']+=_d(e.amount)
        costs_by_category[cur][e.category or 'Other']+=_d(e.amount)
    for sale in sales:per_currency[sale.currency]['sale_revenue']+=_d(sale.gross_amount)
    currencies=[{'currency':cur,**{k:_n(v) for k,v in amt.items()},
       'recorded_costs_including_purchases':_n(amt['animal_purchases']+amt['operating_costs']+amt['selling_expenses']),
       'revenue_less_all_recorded_costs':_n(amt['sale_revenue']-amt['animal_purchases']-amt['operating_costs']-amt['selling_expenses'])}
       for cur,amt in sorted(per_currency.items())]
    active=[a for a in animals if a.status=='active']
    weights=[_d(a.current_weight_kg) for a in active if a.current_weight_kg is not None]
    planned=int(plan_data['planned_animals']) if plan_data else (project.target_animals or 0)
    budget_rows=[];planned_cost_head=Decimal(0);expected_revenue=None;forecast=None
    if plan_data:
        for line in plan_data.get('budget_lines',[]):
            unit=_d(line['amount_per_head']);planned_cost_head+=unit
            budget_rows.append({'category':line['category'],'amount_per_head':_n(unit),'project_amount':_n(unit*planned)})
        # If feed costs have been entered as a formula, don't add another feed budget line.
        if not any(x['category'].strip().lower()=='feed' and _d(x.get('amount_per_head'))>0 for x in plan_data.get('budget_lines',[])):
            feed=_d(plan_data.get('feed_kg_head_day'))*_d(plan_data.get('planned_feed_cost_kg'))*int(plan_data.get('duration_days') or 0)
            if feed:
                planned_cost_head+=feed
                budget_rows.append({'category':'Feed (calculated)','amount_per_head':_n(feed),'project_amount':_n(feed*planned)})
        expense=_d(plan_data.get('selling_expense_per_head'))
        planned_cost_head+=expense
        if expense:budget_rows.append({'category':'Selling expenses','amount_per_head':_n(expense),'project_amount':_n(expense*planned)})
        mortality=_d(plan_data.get('expected_mortality_percent'))
        expected_sold=Decimal(planned)*(Decimal(1)-mortality/Decimal(100))
        if plan_data.get('expected_sale_price_kg') is not None and plan_data.get('finishing_weight_kg') is not None:
            expected_revenue=expected_sold*_d(plan_data['expected_sale_price_kg'])*_d(plan_data['finishing_weight_kg'])
        elif plan_data.get('expected_sale_price_head') is not None:
            expected_revenue=expected_sold*_d(plan_data['expected_sale_price_head'])
        if expected_revenue is not None:forecast=expected_revenue-(planned_cost_head*planned)
    reserve=_d(plan_data.get('contingency_per_head')) if plan_data else Decimal(0)
    expected_budget=planned_cost_head*planned
    # Complete operating costs may not be posted yet; this is a cash/cost
    # position, NOT realized profit while unsold animals remain in inventory.
    own=per_currency.get(project.currency,{})
    recorded=sum((own.get(key,Decimal(0)) for key in ('animal_purchases','operating_costs','selling_expenses')),Decimal(0))
    consumption=Decimal(0)
    for r in routines:
        if r.unit=='kg':consumption+=_d(r.quantity)
    import hashlib
    plan_revision=hashlib.sha256(plan.plan_json.encode('utf-8')).hexdigest() if plan else 'new'
    section_completed={
      'production':bool(plan_data and plan_data.get('entry_weight_kg') and plan_data.get('finishing_weight_kg')),
      'budget':bool(plan_data and any(_d(x.get('amount_per_head'))>0 for x in plan_data.get('budget_lines',[]))),
      'resources':bool(plan_data and (plan_data.get('feed_kg_head_day') or plan_data.get('feeding_phases'))),
      'commercial':bool(plan_data and (plan_data.get('expected_sale_price_kg') is not None or plan_data.get('expected_sale_price_head') is not None)),
      'milestones':bool(plan_data and plan_data.get('milestones')),
      'cashflow':bool(plan_data and plan_data.get('cashflow_lines')),
      'risks':bool(plan_data and (plan_data.get('risks') or plan_data.get('risk_notes'))),
      'scenarios':bool(plan_data and plan_data.get('scenarios')),
    }
    # Scenario projections are read-only what-if estimates, not Finance postings.
    scenario_rows=[]
    for scenario in (plan_data.get('scenarios',[]) if plan_data else []):
        adjusted_mortality=min(Decimal('99.99'),_d(plan_data.get('expected_mortality_percent'))+_d(scenario.get('additional_mortality_percent')))
        sell_heads=Decimal(planned)*(Decimal(100)-adjusted_mortality)/Decimal(100)
        sale_head_price=(_d(plan_data.get('expected_sale_price_head')) if plan_data.get('expected_sale_price_head') is not None else
                         _d(plan_data.get('finishing_weight_kg'))*_d(plan_data.get('expected_sale_price_kg'))) if expected_revenue is not None else None
        gross=(sell_heads*sale_head_price*(Decimal(1)+_d(scenario.get('price_change_percent'))/Decimal(100))) if sale_head_price is not None else None
        explicit_feed=next((_d(x.get('amount_per_head')) for x in plan_data.get('budget_lines',[]) if x.get('category','').strip().lower()=='feed'),Decimal(0))
        base_feed=explicit_feed if explicit_feed else _d(plan_data.get('feed_kg_head_day'))*_d(plan_data.get('planned_feed_cost_kg'))*int(plan_data.get('duration_days') or 0)
        delta_feed=base_feed*_d(scenario.get('feed_cost_change_percent'))/Decimal(100)
        added_days=_d(plan_data.get('feed_kg_head_day'))*_d(plan_data.get('planned_feed_cost_kg'))*int(scenario.get('additional_days') or 0)
        revised_cost=(planned_cost_head+delta_feed+added_days)*planned
        scenario_rows.append({'name':scenario.get('name'),'expected_sales_headcount':_n(sell_heads),
            'forecast_cost':_n(revised_cost),'forecast_revenue':_n(gross),'forecast_contribution':_n(gross-revised_cost) if gross is not None else None,
            'additional_days':scenario.get('additional_days'),'assumptions':scenario.get('assumptions')})
    approvals=db.query(FatteningPlanHistory).filter_by(organization_id=org_id,project_id=project_id).order_by(FatteningPlanHistory.version.desc()).limit(30).all()
    version_history=[{'version':x.version,'status':x.status,'recorded_at':x.recorded_at.isoformat() if x.recorded_at else None} for x in approvals]
    return {'project':project_dict(db,type('OrgRef',(),{'id':org_id})(),project),
      'plan':{'version':plan.version,'status':plan_status,'approved_at':plan.approved_at.isoformat() if plan and plan.approved_at else None,
              'data':plan_data} if plan else None,
      'plan_revision':plan_revision,'section_completed':section_completed,
      'kpis':{'planned_animals':planned,'enrolled_animals':len(animals),'active_animals':len(active),
        'sold_animals':len(sales),'batches':len(batches),'average_active_weight_kg':_n(sum(weights)/len(weights)) if weights else None,
        'recorded_batch_feeding_kg':_n(consumption),'budget_per_animal':_n(planned_cost_head) if plan_data else None,
        'planned_project_cost':_n(expected_budget) if plan_data else None,
        'funding_including_contingency':_n((planned_cost_head+reserve)*planned) if plan_data else None,
        'recorded_costs_base_currency':_n(recorded),
        'planned_revenue':_n(expected_revenue),'forecast_contribution':_n(forecast)},
      'budget_lines':budget_rows,'currency_breakdown':currencies,
      'actual_cost_categories':[{'category':category,'currency':cur,'amount':_n(value)}
            for cur,groups in sorted(costs_by_category.items()) for category,value in sorted(groups.items())],
      'animal_rows':[{'id':a.id,'tag':a.tag,'status':a.status,'batch':next((b.name for b in batches if b.id==a.batch_id),None),
              'entry_weight_kg':_n(a.entry_weight_kg),'current_weight_kg':_n(a.current_weight_kg),
              'purchase_price':_n(a.purchase_cost),'currency':a.purchase_currency} for a in animals],
      'batch_rows':[{'id':b.id,'name':b.name,'capacity':b.capacity,'animals':sum(a.batch_id==b.id for a in animals)} for b in batches],
      'milestones':plan_data.get('milestones',[]) if plan_data else [],
      'risks':plan_data.get('risks',[]) if plan_data else [],
      'scenarios':plan_data.get('scenarios',[]) if plan_data else [],
      'scenario_rows':scenario_rows,'version_history':version_history,
      'feeding_phases':plan_data.get('feeding_phases',[]) if plan_data else [],
      'cashflow_lines':plan_data.get('cashflow_lines',[]) if plan_data else [],
      'notes':['Purchases come from animal registrations; feed/other operational costs come from posted Finance entries; sales come from completed sales. No duplicate posting.',
               'The current position includes costs of unsold animals: it is not realized accounting profit.',
               'Costs in different currencies are reported separately without invented FX.',
               'Animals transferred between projects are attributed by current batch; historical cross-project allocations require a dated movement ledger.']}


def fattening_sale_preview(db:Session,org_id:int,animal_id:int,sale):
    import hashlib
    a=db.query(Animal).filter_by(id=animal_id,organization_id=org_id).first()
    if not a:raise HTTPException(404,'Animal not found')
    if a.status!='active':raise HTTPException(409,'Only active animals can be sold')
    profile=animal_profile(db,org_id,animal_id)
    be=profile['break_even']
    gross=_d(sale.price_per_unit)*(_d(sale.weight_kg) if sale.price_basis=='per_kg' else Decimal(1))
    extra=_d(sale.transport_cost)+_d(sale.commission_cost)+_d(sale.other_cost)
    comparable=be['comparable'] and be['currency']==sale.currency
    total=_d(be['amount'])+extra if comparable else None
    result=gross-total if total is not None else None
    project=db.query(Batch).filter_by(id=a.batch_id,organization_id=org_id).first()
    digest=hashlib.sha256(('::'.join(str(x) for x in (a.id,a.status,be['amount'],be['currency'],
       be['direct_fattening_costs'],be['allocated_batch_costs'],sale.currency,sale.price_basis,sale.price_per_unit,
       sale.weight_kg,extra,project.project_id if project else None))).encode()).hexdigest()
    return {'animal_id':a.id,'tag':a.tag,'project_id':project.project_id if project else None,
      'latest_weight_kg':profile['current_weight_kg'],'sale_weight_kg':_n(sale.weight_kg) if sale.weight_kg else None,
      'price_basis':sale.price_basis,'price_per_unit':_n(sale.price_per_unit),'currency':sale.currency,
      'purchase_cost':be['purchase_cost'],'direct_costs':be['direct_fattening_costs'],
      'allocated_batch_costs':be['allocated_batch_costs'],'fattening_costs':be['fattening_costs'],
      'animal_break_even':be['amount'],'selling_expenses':_n(extra),'total_break_even':_n(total),
      'gross_revenue':_n(gross),'projected_profit_loss':_n(result),
      'margin_percent':_n(result/gross*100) if result is not None and gross>0 else None,
      'break_even_per_kg':_n(total/_d(sale.weight_kg)) if total is not None and sale.weight_kg and _d(sale.weight_kg)>0 else None,
      'comparable':comparable,'costs_are_provisional':True,'preview_token':digest,
      'warnings':([] if comparable else ['Purchase/cost and selling currency are not compatible; enter an approved FX conversion before committing the sale.'])
         + (['The selected animal has no recent recorded weight. Verify the sale weight.'] if profile['current_weight_kg'] is None else [])}
