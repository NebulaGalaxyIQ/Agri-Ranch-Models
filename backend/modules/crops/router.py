"""Domain-owned operational endpoints.
Uses shared records and permissions without cross-tenant access.
"""
from __future__ import annotations
from datetime import date,datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import audit
from modules.organizations.service import context
from modules.crops.models import *
from modules.crops.models import scope,linked,ranch,result,rowdata,saved
from modules.livestock.models import *
from modules.gardening.models import *
from modules.machinery.models import *
basic_router=APIRouter(prefix='/api/v6',tags=['crops'])


@basic_router.get('/crops/fields')
def fields(db:Session=Depends(get_db),ctx=Depends(context)):_,org,_=scope(db,ctx,'crops');return result(db,CropField,org)


@basic_router.post('/crops/fields',status_code=201)
def create_field(p:FieldIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'crops',True);ranch(db,o,p.ranch_id);return saved(db,a,CropField,CropField(organization_id=o.id,**p.model_dump()),'field_created')


@basic_router.get('/crops/cycles')
def cycles(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'crops');return result(db,CropCycle,o)


@basic_router.post('/crops/cycles',status_code=201)
def create_cycle(p:CycleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'crops',True)
    f=linked(db,CropField,o,p.field_id,'Field')
    if p.planted_area_ha>f.area_ha:raise HTTPException(422,'Planted area cannot exceed field area')
    return saved(db,a,CropCycle,CropCycle(organization_id=o.id,**p.model_dump()),'crop_cycle_created')


@basic_router.get('/crops/records')
def crop_records(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'crops');return result(db,CropRecord,o)


@basic_router.post('/crops/records',status_code=201)
def add_crop_record(p:CropActivityIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'crops',True);cycle=linked(db,CropCycle,o,p.cycle_id,'Crop cycle')
    if cycle.status=='cancelled':raise HTTPException(409,'Cannot record activity for cancelled crop')
    if p.performed_on<cycle.planting_date:raise HTTPException(422,'Crop activity cannot precede its planting date')
    if p.performed_on>date.today():raise HTTPException(422,'Actual crop work must not be recorded in the future')
    if p.action=='harvest' and not p.quantity:raise HTTPException(422,'Harvest quantity is required')
    if p.action=='harvest':
        if p.unit and p.unit.lower()!='kg':raise HTTPException(422,'Harvest quantity is measured in kg. Convert other units before recording.')
        p=p.model_copy(update={'unit':'kg'})
        cycle.status='harvested'
    obj=CropRecord(organization_id=o.id,recorded_by=a.id,**p.model_dump())
    db.add(obj);db.flush()
    if p.cost>0:
        from modules.fattening.models import FinanceEntry
        db.add(FinanceEntry(organization_id=o.id,batch_id=None,kind='cost',category='Crop '+p.action,amount=p.cost,currency=p.currency,note=p.notes,source_type='v6_crop_record',source_id=obj.id,created_by=a.id))
    audit(db,a.id,'crop_record_created','v6_crop_records',obj.id);out=rowdata(obj);db.commit()
    return {'item':out,'message':'Crop activity and attributed cost recorded'}


# Domain-specific API endpoints and their shared transaction dependencies.

from modules.crops.service import *
from modules.livestock.service import *
from modules.crops.models import scope, linked, rowdata
from modules.crops.models import CropCycle, CropRecord
from modules.crops.models import CropInput

extra_router=APIRouter(prefix="/api/v6",tags=["crops"] )
@extra_router.get('/crops/inputs')
def crop_inputs(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'crops')
    return {'items':[rowdata(x) for x in db.query(CropInput).filter_by(organization_id=o.id).order_by(CropInput.id.desc()).limit(1000).all()]}


@extra_router.post('/crops/inputs',status_code=201)
def create_crop_input(p:CropInputIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'crops',True)
    cycle=linked(db,CropCycle,o,p.cycle_id,'Crop cycle')
    if p.performed_on>date.today():raise HTTPException(422,'Actual crop inputs cannot be recorded in the future')
    if cycle.status=='cancelled':raise HTTPException(409,'Cannot add inputs to a cancelled crop cycle')
    reference=p.reference or 'CIN-'+uuid4().hex[:16].upper()
    if db.query(CropInput).filter_by(organization_id=o.id,reference=reference).first():raise HTTPException(409,'This crop input was already recorded')
    amount=(p.quantity*p.unit_cost+p.labor_cost+p.transport_cost).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    obj=CropInput(organization_id=o.id,recorded_by=a.id,total_cost=amount,reference=reference,
                  **p.model_dump(exclude={'reference'}))
    db.add(obj);db.flush()
    finance(db,a,o,'Crop input: '+p.category,amount,p.currency,'v61_crop_input',obj.id)
    audit(db,a.id,'crop_input_recorded','v61_crop_inputs',obj.id,p.category)
    out=rowdata(obj);db.commit()
    return {'item':out,'message':'Crop input and related cost recorded once'}


@extra_router.get('/crops/profitability')
def crop_profitability(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'crops')
    cycles=db.query(CropCycle).filter_by(organization_id=o.id).all()
    result=[]
    for c in cycles:
        inputs=db.query(CropInput).filter_by(organization_id=o.id,cycle_id=c.id).all()
        records=db.query(CropRecord).filter_by(organization_id=o.id,cycle_id=c.id).all()
        sales=db.query(CropSale).filter_by(organization_id=o.id,cycle_id=c.id).all()
        currencies={x.currency for x in [*inputs,*records,*sales] if (getattr(x,'total_cost',None) or getattr(x,'cost',None) or getattr(x,'gross',None))}
        by_currency=[]
        for curr in sorted(currencies):
            inputs_sum=sum((Decimal(i.total_cost) for i in inputs if i.currency==curr),Decimal(0))
            other=sum((Decimal(r.cost) for r in records if r.currency==curr),Decimal(0))
            revenue=sum((Decimal(s.gross) for s in sales if s.currency==curr),Decimal(0))
            by_currency.append({'currency':curr,'recorded_inputs':float(inputs_sum),'activity_costs':float(other),
                'revenue':float(revenue),'contribution':float(revenue-inputs_sum-other)})
        harvested=sum((Decimal(r.quantity) for r in records if r.action=='harvest' and r.quantity),Decimal(0))
        sold=sum((Decimal(s.quantity_kg) for s in sales),Decimal(0))
        result.append({'cycle_id':c.id,'crop':c.crop,'variety':c.variety,'field_id':c.field_id,
                       'planted_area_ha':float(c.planted_area_ha),'harvested_kg':float(harvested),
                       'sold_kg':float(sold),'unsold_kg':float(max(Decimal(0),harvested-sold)),
                       'yield_kg_per_ha':float(harvested/c.planted_area_ha) if c.planted_area_ha else None,
                       'currencies':by_currency})
    return {'items':result,'note':'Recorded contribution excludes unallocated overhead, taxes, depreciation and unrecorded work. Currencies are never added together.'}


# Domain-specific API endpoints and their shared transaction dependencies.

from modules.crops.service import *
from modules.livestock.service import *
from modules.crops.models import scope, linked, rowdata
from modules.crops.models import CropCycle, CropRecord
from modules.crops.models import CropInput

sales_router=APIRouter(prefix="/api/v6",tags=["crops"] )
@extra_router.get('/crops/sales')
def crops_sales(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'crops');return {'items':[rowdata(x) for x in db.query(CropSale).filter_by(organization_id=o.id).order_by(CropSale.id.desc()).all()]}


@extra_router.post('/crops/sales',status_code=201)
def sell_crops(p:CropSaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=scope(db,ctx,'crops',True)
    c=db.query(CropCycle).filter_by(id=p.cycle_id,organization_id=o.id).with_for_update().first()
    if not c:raise HTTPException(404,'Crop cycle does not exist')
    if c.status=='cancelled':raise HTTPException(409,'Cancelled crop cycle')
    harvested=sum((Decimal(x.quantity or 0) for x in db.query(CropRecord).filter_by(organization_id=o.id,cycle_id=c.id,action='harvest')) ,Decimal(0))
    previously=sum((Decimal(x.quantity_kg) for x in db.query(CropSale).filter_by(organization_id=o.id,cycle_id=c.id)),Decimal(0))
    if p.quantity_kg>harvested-previously:raise HTTPException(409,f'Not enough harvested crop recorded; {harvested-previously} kg available')
    total=(p.quantity_kg*p.price_per_kg).quantize(Decimal('.01'))
    s=CropSale(organization_id=o.id,recorded_by=actor.id,gross=total,**p.model_dump())
    db.add(s);db.flush();finance(db,actor,o,'Crop sales',total,p.currency,'v6_crop_sale',s.id,'revenue')
    audit(db,actor.id,'crop_sold','v6_crop_sale',s.id,f'{p.quantity_kg} kg');out=rowdata(s);db.commit()
    return {'item':out,'message':'Crop sale recorded and Finance updated'}

# === GHR_CROPS_V9_ROUTES ===
from sqlalchemy import func as v9_func
from sqlalchemy.exc import IntegrityError
from modules.crops.schemas import (SECTIONS,GENERIC_SECTIONS,ProjectIn,UnitIn,VarietyIn,CycleInV9,
 RecordIn,BudgetIn,RoutineIn,CompletionIn,TrialIn,PlotIn,HarvestIn,SaleIn,StockIn,StatusIn)
from modules.crops.service import (v9_scope,v9_related,v9_project_cycle,v9_when,v9_check_data,
 v9_amount,v9_finance,v9_commit,v9_due,v9_project_analytics)
from modules.crops.models import (V9Project,V9Unit,V9Variety,V9Cycle,V9Record,V9Budget,V9Routine,V9Completion,
 V9Trial,V9Plot,V9Harvest,V9Stock,V9Sale)
from modules.crops.models import CropField
from modules.livestock.service import finance as legacy_finance

v9_router=APIRouter(prefix='/api/v9/crops',tags=['V9 global crop management'])

def v9_list(db,model,org,limit=750):
    return [rowdata(x) for x in db.query(model).filter_by(organization_id=org.id).order_by(model.id.desc()).limit(limit).all()]

def v9_new(db,actor,obj,action):
    try:return v9_commit(db,actor,obj,action)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Duplicate reference, name, or concurrent update')

@v9_router.get('/meta')
def v9_metadata(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=v9_scope(db,ctx)
    return {'version':'9.0.0','sections':SECTIONS,'organization_id':o.id,
            'units':['ha','acre','m2','kg','g','tonne','lb','L','m3','bags','pieces','hours','days','units'],
            'note':'Each project uses its own currency. Amounts with different currencies are not added together.'}

@v9_router.get('/workspace')
def v9_workspace(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=v9_scope(db,ctx)
    models={'projects':V9Project,'units':V9Unit,'varieties':V9Variety,'cycles':V9Cycle,'budgets':V9Budget,
            'routine':V9Routine,'completions':V9Completion,'trials':V9Trial,'plots':V9Plot,'harvest':V9Harvest,'sales':V9Sale,
            'stock':V9Stock}
    data={k:v9_list(db,m,o) for k,m in models.items()}
    data['fields']=v9_list(db,CropField,o)
    data['records']=v9_list(db,V9Record,o,2000)
    data['legacy']={'fields':len(data['fields']),
         'cycles':db.query(CropCycle).filter_by(organization_id=o.id).count(),
         'records':db.query(CropRecord).filter_by(organization_id=o.id).count(),
         'note':'Existing V6 crop records remain intact and available through the legacy V6 endpoints.'}
    data['analytics']=v9_project_analytics(db,o)
    return data

@v9_router.post('/projects',status_code=201)
def v9_create_project(p:ProjectIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True);ranch(db,o,p.ranch_id)
    return v9_new(db,actor,V9Project(organization_id=o.id,created_by=actor.id,**p.model_dump()),'v9_crop_project_created')

@v9_router.post('/units',status_code=201)
def v9_create_unit(p:UnitIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    field=v9_related(db,CropField,o,p.field_id,'Field')
    other=sum((Decimal(x.area_ha) for x in db.query(V9Unit).filter_by(organization_id=o.id,field_id=p.field_id).all()),Decimal(0))
    if other+p.area_ha>Decimal(field.area_ha):raise HTTPException(409,'Blocks exceed registered field area')
    if p.latitude is not None and not -90<=p.latitude<=90:raise HTTPException(422,'Invalid latitude')
    if p.longitude is not None and not -180<=p.longitude<=180:raise HTTPException(422,'Invalid longitude')
    return v9_new(db,actor,V9Unit(organization_id=o.id,**p.model_dump()),'v9_crop_unit_created')

@v9_router.post('/varieties',status_code=201)
def v9_create_variety(p:VarietyIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    return v9_new(db,actor,V9Variety(organization_id=o.id,**p.model_dump()),'v9_crop_variety_created')

@v9_router.post('/cycles',status_code=201)
def v9_create_cycle(p:CycleInV9,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    project,_,unit=v9_project_cycle(db,o,p.project_id,unit_id=p.unit_id)
    v9_related(db,V9Variety,o,p.variety_id,'Crop variety')
    if p.planted_area_ha>Decimal(unit.area_ha):raise HTTPException(422,'Area exceeds selected block')
    if p.planted_on<project.start_date:raise HTTPException(422,'Planting precedes project start')
    if project.end_date and p.planted_on>project.end_date:raise HTTPException(422,'Planting is outside project schedule')
    active=db.query(V9Cycle).filter_by(organization_id=o.id,unit_id=unit.id).filter(V9Cycle.status.notin_(['cancelled','completed','harvested'])).all()
    for c in active:
        # Treat overlapping occupancy conservatively. Explicit intercropping can be planned separately.
        overlapping=c.expected_harvest is None or p.expected_harvest is None or c.planted_on<=p.expected_harvest and p.planted_on<=c.expected_harvest
        if overlapping and Decimal(c.planted_area_ha)+p.planted_area_ha>Decimal(unit.area_ha):
            raise HTTPException(409,'Overlapping crop cycles exceed block capacity')
    return v9_new(db,actor,V9Cycle(organization_id=o.id,**p.model_dump()),'v9_crop_cycle_created')

@v9_router.post('/budgets',status_code=201)
def v9_create_budget(p:BudgetIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True);project,_,_=v9_project_cycle(db,o,p.project_id,p.cycle_id)
    if p.currency!=project.currency:raise HTTPException(422,'Budget currency must match project base currency')
    if p.status=='approved' and ctx[2].role not in ('org_admin','manager'):raise HTTPException(403,'Only managers approve budgets')
    amount=(p.quantity*p.unit_cost).quantize(Decimal('.01'))
    return v9_new(db,actor,V9Budget(organization_id=o.id,recorded_by=actor.id,amount=amount,**p.model_dump()),'v9_crop_budget_line_created')

@v9_router.post('/routines',status_code=201)
def v9_create_routine(p:RoutineIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True);v9_project_cycle(db,o,p.project_id,p.cycle_id,p.unit_id)
    if p.end_date and p.end_date<p.start_date:raise HTTPException(422,'End before start date')
    if any(i<0 or i>6 for i in p.weekdays):raise HTTPException(422,'Weekdays must be 0 to 6')
    if p.frequency not in ('daily','weekly','weekdays','monthly','once') and not (p.frequency.startswith('every_') and p.frequency[6:].isdigit() and int(p.frequency[6:])>0):
        raise HTTPException(422,'Invalid frequency')
    return v9_new(db,actor,V9Routine(organization_id=o.id,created_by=actor.id,**p.model_dump()),'v9_crop_routine_created')

@v9_router.get('/routines/due')
def v9_routines_due(day:date|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=v9_scope(db,ctx);day=day or date.today()
    routines=db.query(V9Routine).filter_by(organization_id=o.id,enabled=True).all()
    checks={c.routine_id:rowdata(c) for c in db.query(V9Completion).filter_by(organization_id=o.id,day=day).all()}
    return {'day':day.isoformat(),'items':[{**rowdata(r),'check':checks.get(r.id)} for r in routines if v9_due(r,day)]}

@v9_router.post('/routines/{routine_id}/complete',status_code=201)
def v9_complete_routine(routine_id:int,p:CompletionIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True);r=v9_related(db,V9Routine,o,routine_id,'Routine')
    v9_when(p.day,'Routine completion')
    if not v9_due(r,p.day):raise HTTPException(409,'Routine is not scheduled on this date')
    if p.status not in ('completed','skipped'):raise HTTPException(422,'Invalid completion state')
    exists=db.query(V9Completion).filter_by(organization_id=o.id,routine_id=r.id,day=p.day).first()
    if exists:raise HTTPException(409,'This routine has already been recorded for this date')
    project=v9_related(db,V9Project,o,r.project_id,'Project')
    if p.amount and p.currency!=project.currency:raise HTTPException(422,'Expense currency must match the project')
    obj=V9Completion(organization_id=o.id,routine_id=r.id,completed_by=actor.id,**p.model_dump())
    db.add(obj);db.flush()
    if p.status=='completed' and p.amount:v9_finance(db,actor,o,p.amount,p.currency,'v9_crop_routine_check',obj.id,'Crop routine')
    audit(db,actor.id,'v9_crop_routine_checked',obj.__tablename__,obj.id)
    output=rowdata(obj)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Duplicate routine completion')
    return {'item':output}

@v9_router.post('/trials',status_code=201)
def v9_create_trial(p:TrialIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True);v9_project_cycle(db,o,p.project_id,p.cycle_id)
    if p.end_date and p.end_date<p.start_date:raise HTTPException(422,'Trial end before start')
    return v9_new(db,actor,V9Trial(organization_id=o.id,created_by=actor.id,**p.model_dump()),'v9_crop_trial_created')

@v9_router.post('/plots',status_code=201)
def v9_create_plot(p:PlotIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True);t=v9_related(db,V9Trial,o,p.trial_id,'Trial')
    cycle=v9_related(db,V9Cycle,o,t.cycle_id,'Crop cycle')
    if p.unit_id!=cycle.unit_id:raise HTTPException(422,'Trial plot must belong to trial crop cycle block')
    if p.replicate>t.replications:raise HTTPException(422,'Replicate exceeds trial design')
    used=sum((Decimal(x.area_ha) for x in db.query(V9Plot).filter_by(organization_id=o.id,trial_id=t.id).all()),Decimal(0))
    if used+p.area_ha>Decimal(cycle.planted_area_ha):raise HTTPException(409,'Trial plot total area exceeds crop-cycle planted area')
    return v9_new(db,actor,V9Plot(organization_id=o.id,**p.model_dump()),'v9_crop_trial_plot_created')

@v9_router.get('/records/{section}')
def v9_section_records(section:str,project_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=v9_scope(db,ctx)
    if section not in GENERIC_SECTIONS:raise HTTPException(404,'Unknown data section')
    query=db.query(V9Record).filter_by(organization_id=o.id,section=section)
    if project_id:query=query.filter_by(project_id=project_id)
    return {'items':[rowdata(x) for x in query.order_by(V9Record.id.desc()).limit(1000).all()]}

@v9_router.post('/records/{section}',status_code=201)
def v9_record(section:str,p:RecordIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    if section not in GENERIC_SECTIONS:raise HTTPException(404,'Unknown data section')
    project,cycle,unit=v9_project_cycle(db,o,p.project_id,p.cycle_id,p.unit_id)
    v9_when(p.performed_on)
    if p.currency and p.currency!=project.currency:raise HTTPException(422,'Expense currency must match project currency')
    if cycle and p.performed_on<cycle.planted_on and section not in ('soil','planting','budgets'):
        raise HTTPException(422,'Crop observation predates crop planting')
    v9_check_data(section,p.data)
    if section in ('growth','nutrition','protection','irrigation','planting') and not cycle:raise HTTPException(422,'Choose a registered crop cycle')
    if section=='postharvest':
        lot=v9_related(db,V9Harvest,o,int(p.data.get('lot_id')),'Harvest lot')
        if lot.project_id!=project.id:raise HTTPException(422,'Postharvest lot belongs to a different project')
    if section=='outcomes' and p.data.get('trial_id'):
        trial=v9_related(db,V9Trial,o,int(p.data['trial_id']),'Trial')
        if trial.project_id!=project.id:raise HTTPException(422,'Trial belongs to a different project')
    if section=='trial_observations':
        trial=v9_related(db,V9Trial,o,int(p.data['trial_id']),'Trial')
        plot=v9_related(db,V9Plot,o,int(p.data['plot_id']),'Experimental plot')
        if plot.trial_id!=trial.id or trial.project_id!=project.id or trial.cycle_id!=p.cycle_id:
            raise HTTPException(422,'Observation must reference its own trial, project, crop cycle and plot')

    if p.data.get('plants_affected') is not None and p.data.get('plants_inspected') is not None and int(p.data['plants_affected'])>int(p.data['plants_inspected']):
        raise HTTPException(422,'Affected plants exceed plants inspected')
    ref=p.reference or None
    obj=V9Record(organization_id=o.id,recorded_by=actor.id,section=section,**p.model_dump(exclude={'reference','unit_id'}),unit_id=unit.id if unit else None,reference=ref)
    db.add(obj);db.flush()
    amount=v9_amount(p.quantity,p.unit_cost,p.other_cost)
    if amount>0 and section in ('inputs','nutrition') and p.data.get('stock_reference'):
        # Inventory is the cost/stock source of truth when a source issue exists.
        amount=Decimal(0)
    if amount>0:
        if not p.currency:raise HTTPException(422,'Currency required for attributed expense')
        v9_finance(db,actor,o,amount,p.currency,'v9_crop_record',obj.id,'Crop '+section)
    audit(db,actor.id,'v9_crop_record_created',obj.__tablename__,obj.id,section)
    output=rowdata(obj)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Duplicate source reference')
    return {'item':output}

@v9_router.post('/harvest',status_code=201)
def v9_create_harvest(p:HarvestIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    project,cycle,unit=v9_project_cycle(db,o,p.project_id,p.cycle_id,p.unit_id)
    v9_when(p.harvested_on,'Harvest')
    if p.harvested_on<cycle.planted_on:raise HTTPException(422,'Harvest date predates planting')
    marketable=p.gross_kg-p.tare_kg-p.rejected_kg
    if p.currency and p.currency!=project.currency:raise HTTPException(422,'Cost currency must match project currency')
    obj=V9Harvest(organization_id=o.id,recorded_by=actor.id,marketable_kg=marketable,available_kg=marketable,**p.model_dump())
    db.add(obj);db.flush()
    if p.cost:
        if not p.currency:raise HTTPException(422,'Currency required for harvest cost')
        v9_finance(db,actor,o,p.cost,p.currency,'v9_crop_harvest',obj.id,'Crop harvesting')
    audit(db,actor.id,'v9_crop_harvest_created',obj.__tablename__,obj.id)
    out=rowdata(obj)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Harvest batch reference already exists')
    return {'item':out}

@v9_router.post('/stock',status_code=201)
def v9_crop_stock(p:StockIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    if p.action not in ('loss','writeoff','internal_use'):raise HTTPException(422,'Unsupported stock movement; receipts arise only from harvest')
    lot=db.query(V9Harvest).filter_by(organization_id=o.id,id=p.lot_id).with_for_update().first()
    if not lot:raise HTTPException(404,'Harvest lot not found')
    if p.quantity_kg>lot.available_kg:raise HTTPException(409,'Cannot deduct more than available lot quantity')
    lot.available_kg-=p.quantity_kg
    return v9_new(db,actor,V9Stock(organization_id=o.id,recorded_by=actor.id,**p.model_dump()),'v9_crop_stock_movement')

@v9_router.post('/sales',status_code=201)
def v9_create_sale(p:SaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,_=v9_scope(db,ctx,True)
    lot=db.query(V9Harvest).filter_by(organization_id=o.id,id=p.lot_id).with_for_update().first()
    if not lot:raise HTTPException(404,'Harvest lot not found')
    project=v9_related(db,V9Project,o,lot.project_id,'Project')
    v9_when(p.sold_on,'Sale')
    if p.sold_on<lot.harvested_on:raise HTTPException(422,'Sale cannot precede harvest')
    if p.currency!=project.currency:raise HTTPException(422,'Sale currency must match project reporting currency; FX conversion is not automated')
    if p.quantity_kg>lot.available_kg:raise HTTPException(409,'Insufficient harvest lot stock')
    gross=(p.quantity_kg*p.price_per_kg).quantize(Decimal('.01'))
    lot.available_kg-=p.quantity_kg
    obj=V9Sale(organization_id=o.id,project_id=lot.project_id,recorded_by=actor.id,gross=gross,**p.model_dump())
    db.add(obj);db.flush()
    v9_finance(db,actor,o,gross,p.currency,'v9_crop_sale',obj.id,'Crop sale','revenue')
    if p.selling_cost:v9_finance(db,actor,o,p.selling_cost,p.currency,'v9_crop_sale_expense',obj.id,'Crop selling expense')
    audit(db,actor.id,'v9_crop_sale_created',obj.__tablename__,obj.id)
    out=rowdata(obj);db.commit();return {'item':out}

@v9_router.patch('/projects/{project_id}/status')
def v9_update_project(project_id:int,p:StatusIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,m=v9_scope(db,ctx,True)
    if m.role not in ('org_admin','manager'):raise HTTPException(403,'Manager approval is required')
    obj=v9_related(db,V9Project,o,project_id,'Project')
    allowed={'planned':{'active','cancelled'},'active':{'paused','completed','cancelled'},
             'paused':{'active','cancelled'},'completed':set(),'cancelled':set()}
    if p.status not in allowed.get(obj.status,set()):raise HTTPException(409,'Invalid project status transition')
    obj.status=p.status
    return v9_new(db,actor,obj,'v9_crop_project_status_changed')

@v9_router.patch('/cycles/{cycle_id}/status')
def v9_update_cycle(cycle_id:int,p:StatusIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,m=v9_scope(db,ctx,True)
    if m.role not in ('org_admin','manager'):raise HTTPException(403,'Manager approval is required')
    obj=v9_related(db,V9Cycle,o,cycle_id,'Crop cycle')
    allowed={'planned':{'growing','cancelled'},'growing':{'harvested','failed','cancelled'},
             'harvested':{'completed'},'completed':set(),'failed':set(),'cancelled':set()}
    if p.status not in allowed.get(obj.status,set()):raise HTTPException(409,'Invalid crop-cycle status transition')
    obj.status=p.status
    return v9_new(db,actor,obj,'v9_crop_cycle_status_changed')

@v9_router.patch('/trials/{trial_id}/status')
def v9_update_trial(trial_id:int,p:StatusIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,o,m=v9_scope(db,ctx,True)
    if m.role not in ('org_admin','manager'):raise HTTPException(403,'Manager approval is required')
    obj=v9_related(db,V9Trial,o,trial_id,'Trial')
    allowed={'planned':{'active','cancelled'},'active':{'completed','cancelled'},
             'completed':set(),'cancelled':set()}
    if p.status not in allowed.get(obj.status,set()):raise HTTPException(409,'Invalid trial status transition')
    obj.status=p.status
    return v9_new(db,actor,obj,'v9_crop_trial_status_changed')

@v9_router.get('/analytics')
def v9_analytics(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=v9_scope(db,ctx)
    return {'items':v9_project_analytics(db,o),
      'disclaimer':'Recorded contribution is not audited net profit, excludes unallocated overhead and cost of unsold stock. Forecasts are not actuals.'}
# === END_GHR_CROPS_V9_ROUTES ===
