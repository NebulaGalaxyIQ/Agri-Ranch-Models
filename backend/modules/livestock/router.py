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
basic_router=APIRouter(prefix='/api/v6',tags=['livestock'])


@basic_router.get('/livestock/groups')
def groups(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'livestock');return result(db,LivestockGroup,o)


@basic_router.post('/livestock/groups',status_code=201)
def add_group(p:GroupIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'livestock',True);ranch(db,o,p.ranch_id);return saved(db,a,LivestockGroup,LivestockGroup(organization_id=o.id,**p.model_dump()),'livestock_group_created')


@basic_router.get('/livestock/animals')
def general_animals(db:Session=Depends(get_db),ctx=Depends(context)):_,o,_=scope(db,ctx,'livestock');return result(db,GeneralAnimal,o)


@basic_router.post('/livestock/animals',status_code=201)
def create_general_animal(p:GeneralAnimalIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'livestock',True);ranch(db,o,p.ranch_id)
    if not p.tag or not p.tag.strip():
        import secrets
        p=p.model_copy(update={'tag':f'LV-{o.id}-{secrets.token_hex(5).upper()}'})
    if p.group_id:
        group=linked(db,LivestockGroup,o,p.group_id,'Herd / flock')
        if group.ranch_id!=p.ranch_id:raise HTTPException(422,'Animal and group must belong to the same ranch')
    if db.query(GeneralAnimal).filter_by(organization_id=o.id,tag=p.tag).first():raise HTTPException(409,'Animal tag already registered')
    return saved(db,a,GeneralAnimal,GeneralAnimal(organization_id=o.id,**p.model_dump()),'livestock_animal_created')


# Domain-specific API endpoints and their shared transaction dependencies.

from modules.crops.service import *
from modules.livestock.service import *

extra_router=APIRouter(prefix="/api/v6",tags=["livestock"] )
@extra_router.get('/livestock/projects')
def livestock_projects(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'livestock')
    return {'items':[rowdata(x) for x in db.query(LivestockProject).filter_by(organization_id=o.id).order_by(LivestockProject.id.desc()).all()]}


@extra_router.post('/livestock/projects',status_code=201)
def livestock_project(p:LivestockProjectIn,db:Session=Depends(get_db),ctx=Depends(context)):
    from modules.organizations.service import V5Ranch
    a,o,_=scope(db,ctx,'livestock',True)
    linked(db,V5Ranch,o,p.ranch_id,'Ranch')
    obj=LivestockProject(organization_id=o.id,created_by=a.id,**p.model_dump())
    db.add(obj);db.flush();audit(db,a.id,'livestock_project_created','v61_livestock_projects',obj.id)
    out=rowdata(obj);db.commit();return {'item':out,'message':'Livestock project created'}


@extra_router.post('/livestock/projects/{project_id}/groups',status_code=201)
def assign_livestock_group(project_id:int,p:ProjectGroupIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'livestock',True)
    pr=linked(db,LivestockProject,o,project_id,'Project');group=linked(db,LivestockGroup,o,p.group_id,'Group')
    if pr.ranch_id!=group.ranch_id:raise HTTPException(422,'Project and group must belong to the same ranch')
    if db.query(LivestockProjectGroup).filter_by(organization_id=o.id,group_id=p.group_id).first():
        raise HTTPException(409,'Group already belongs to a livestock project; moving it requires a controlled reassignment')
    obj=LivestockProjectGroup(organization_id=o.id,project_id=project_id,group_id=p.group_id)
    db.add(obj);db.flush();audit(db,a.id,'livestock_group_assigned','v61_livestock_project_groups',obj.id)
    db.commit();return {'id':obj.id,'message':'Group linked to livestock project'}


@extra_router.post('/livestock/projects/{project_id}/costs',status_code=201)
def livestock_project_cost(project_id:int,p:ProjectCostIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'livestock',True);linked(db,LivestockProject,o,project_id,'Project')
    obj=LivestockProjectCost(organization_id=o.id,project_id=project_id,recorded_by=a.id,**p.model_dump())
    db.add(obj);db.flush();finance(db,a,o,'Livestock project: '+p.category,p.amount,p.currency,'v61_livestock_project_cost',obj.id)
    audit(db,a.id,'livestock_project_cost','v61_livestock_project_costs',obj.id)
    out=rowdata(obj);db.commit();return {'item':out,'message':'Livestock project cost saved and Finance updated'}


@extra_router.get('/livestock/products')
def livestock_products(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'livestock')
    return {'items':[{**rowdata(x),'available':float(x.quantity_received-x.quantity_sold)} for x in
      db.query(ProductLot).filter_by(organization_id=o.id).order_by(ProductLot.id.desc()).limit(1000).all()]}


@extra_router.get('/livestock/products/sales')
def livestock_product_sales(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'livestock')
    return {'items':[rowdata(x) for x in db.query(ProductSale).filter_by(organization_id=o.id).order_by(ProductSale.id.desc()).limit(1000).all()]}


@extra_router.post('/livestock/products/sales',status_code=201)
def sell_product(p:ProductSaleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    a,o,_=scope(db,ctx,'livestock',True)
    lot=db.query(ProductLot).filter_by(id=p.lot_id,organization_id=o.id).with_for_update().first()
    if not lot:raise HTTPException(404,'Product stock lot not found')
    if p.quantity>lot.quantity_received-lot.quantity_sold:raise HTTPException(409,'Insufficient collected product stock')
    reference=p.reference or 'LPS-'+uuid4().hex[:16].upper()
    if db.query(ProductSale).filter_by(organization_id=o.id,reference=reference).first():raise HTTPException(409,'Sale reference already used')
    gross=(p.quantity*p.price_per_unit).quantize(Decimal('0.01'))
    obj=ProductSale(organization_id=o.id,recorded_by=a.id,reference=reference,gross=gross,**p.model_dump(exclude={'reference'}))
    lot.quantity_sold+=p.quantity;db.add(obj);db.flush()
    finance(db,a,o,lot.product.capitalize()+' sales',gross,p.currency,'v61_livestock_product_sale',obj.id,'revenue')
    audit(db,a.id,'livestock_product_sold','v61_livestock_product_sales',obj.id)
    out=rowdata(obj);db.commit();return {'item':out,'message':'Product sale saved, stock reduced, Finance updated'}


@extra_router.get('/livestock/project-performance')
def livestock_project_performance(db:Session=Depends(get_db),ctx=Depends(context)):
    _,o,_=scope(db,ctx,'livestock')
    projects=db.query(LivestockProject).filter_by(organization_id=o.id).all()
    output=[]
    for p in projects:
        links=db.query(LivestockProjectGroup).filter_by(organization_id=o.id,project_id=p.id).all()
        ids=[l.group_id for l in links]
        costs=db.query(LivestockProjectCost).filter_by(organization_id=o.id,project_id=p.id).all()
        products=db.query(ProductSale).join(ProductLot,ProductSale.lot_id==ProductLot.id).filter(
            ProductSale.organization_id==o.id,ProductLot.group_id.in_(ids)).all() if ids else []
        group_sales=db.query(LivestockSale).filter(LivestockSale.organization_id==o.id,LivestockSale.group_id.in_(ids)).all() if ids else []
        tagged_ids=[a.id for a in db.query(GeneralAnimal).filter(GeneralAnimal.organization_id==o.id,GeneralAnimal.group_id.in_(ids)).all()] if ids else []
        individual_sales=db.query(LivestockSale).filter(LivestockSale.organization_id==o.id,LivestockSale.animal_id.in_(tagged_ids)).all() if tagged_ids else []
        activity=db.query(LivestockEvent).filter(LivestockEvent.organization_id==o.id,LivestockEvent.group_id.in_(ids)).all() if ids else []
        # Include newly logged daily care and veterinary costs attributable to
        # the project's groups or their individually identified animals.
        target_care=db.query(LivestockCareRecord).filter(LivestockCareRecord.organization_id==o.id).filter(
            (LivestockCareRecord.group_id.in_(ids) if ids else False) |
            (LivestockCareRecord.animal_id.in_(tagged_ids) if tagged_ids else False)).all() if ids else []
        target_health=db.query(LivestockHealthRecord).filter(LivestockHealthRecord.organization_id==o.id,
            LivestockHealthRecord.status=='completed').filter(
            (LivestockHealthRecord.group_id.in_(ids) if ids else False) |
            (LivestockHealthRecord.animal_id.in_(tagged_ids) if tagged_ids else False)).all() if ids else []
        # Additional V8.3 costs are posted once to Finance, and attributed to
        # exactly one project (no currency conversion or duplication).
        new_costs=db.query(LivestockRegistrationCost).filter_by(organization_id=o.id,project_id=p.id).all()
        routine_ids=[x.id for x in db.query(LivestockRoutineTemplate).filter(
            LivestockRoutineTemplate.organization_id==o.id,LivestockRoutineTemplate.group_id.in_(ids)).all()] if ids else []
        task_costs=db.query(LivestockRoutineCompletion).filter(
            LivestockRoutineCompletion.organization_id==o.id,
            LivestockRoutineCompletion.template_id.in_(routine_ids)).all() if routine_ids else []
        currencies=set([c.currency for c in costs]+[s.currency for s in products+group_sales+individual_sales]+[e.currency for e in activity]+[c.currency for c in target_care]+[h.currency for h in target_health]+[c.currency for c in new_costs]+[c.currency for c in task_costs])
        currency_results=[]
        for currency in sorted(currencies):
            direct=sum((Decimal(x.amount) for x in costs if x.currency==currency),Decimal(0))
            activities=sum((Decimal(x.cost) for x in activity if x.currency==currency),Decimal(0))
            product_revenue=sum((Decimal(x.gross) for x in products if x.currency==currency),Decimal(0))
            animal_revenue=sum((Decimal(x.gross) for x in group_sales+individual_sales if x.currency==currency),Decimal(0))
            care_costs=sum((Decimal(x.expense) for x in target_care if x.currency==currency),Decimal(0))
            veterinary_costs=sum((Decimal(x.cost) for x in target_health if x.currency==currency),Decimal(0))
            registrations=sum((Decimal(x.total) for x in new_costs if x.currency==currency),Decimal(0))
            routine=sum((Decimal(x.expense) for x in task_costs if x.currency==currency),Decimal(0))
            currency_results.append({'currency':currency,'registration_costs':float(registrations),'routine_costs':float(routine),'direct_costs':float(direct),'activity_costs':float(activities),
                'care_costs':float(care_costs),'veterinary_costs':float(veterinary_costs),
                'product_revenue':float(product_revenue),'animal_sales':float(animal_revenue),
                'recorded_contribution':float(product_revenue+animal_revenue-direct-activities-care_costs-veterinary_costs-registrations-routine)})
        output.append({'project_id':p.id,'name':p.name,'groups':len(ids),'currencies':currency_results})
    return {'items':output,'note':'Only linked groups, identifiable project costs, and production/sales events are included. Full net profit requires shared expenses, stock costs, depreciation and any unallocated procurement to be reconciled.'}


# V8 additive endpoints; registered through the existing livestock extra_router.
# No changes to the application's router wiring or historical API contracts.
from collections import Counter, defaultdict
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import func
from pydantic import BaseModel
from modules.organizations.service import V5Ranch
from modules.livestock.schemas import (
    HouseIn, PlaceGroupIn, CareIn, BreedingIn, BreedingOutcomeIn,
    HealthIn, CompleteHealthIn, WeightIn, IncubationIn, HatchIn,
)
from modules.livestock.service import livestock_money_by_currency, livestock_growth_rows

POULTRY_SPECIES = {'chicken', 'duck', 'turkey', 'quail', 'goose', 'guinea_fowl'}
V8_SECTIONS = {
    'houses': LivestockHouse, 'placements': LivestockPlacement, 'movements': LivestockHousingMovement,
    'care': LivestockCareRecord, 'breeding': LivestockBreedingRecord,
    'health': LivestockHealthRecord, 'weights': LivestockWeightRecord,
    'incubations': LivestockIncubation, 'production': LivestockEvent,
    'products': ProductLot, 'costs': LivestockProjectCost, 'sales': LivestockSale,
    'product_sales': ProductSale, 'projects': LivestockProject, 'groups': LivestockGroup,
    'animals': GeneralAnimal,
}

def _v8_target(db, org, payload):
    group = linked(db, LivestockGroup, org, payload.group_id, 'Herd/flock') if payload.group_id else None
    animal = linked(db, GeneralAnimal, org, payload.animal_id, 'Animal/bird') if payload.animal_id else None
    if animal and animal.status != 'active':
        raise HTTPException(409, 'Only active animals may receive new records')
    if animal and animal.group_id:
        actual=linked(db,LivestockGroup,org,animal.group_id,'Herd/flock')
        if animal.species.strip().lower()!=actual.species.strip().lower():
            raise HTTPException(422,'Animal species does not match its registered herd/flock')
    if animal and group and animal.group_id != group.id:
        raise HTTPException(422, 'Animal does not belong to that group')
    return group, animal


def _v8_store(db, actor, model, obj, action):
    db.add(obj); db.flush()
    audit(db, actor.id, action, model.__tablename__, obj.id)
    value = rowdata(obj)
    db.commit()
    return {'item': value, 'message': 'Record saved'}

@extra_router.get('/livestock/v8/workspace')
def livestock_v8_workspace(db: Session = Depends(get_db), ctx = Depends(context)):
    _, org, _ = scope(db, ctx, 'livestock')
    oid = org.id
    def allrows(model, max_rows=1500):
        return [rowdata(x) for x in db.query(model).filter_by(organization_id=oid).order_by(model.id.desc()).limit(max_rows).all()]
    groups = db.query(LivestockGroup).filter_by(organization_id=oid).all()
    houses = db.query(LivestockHouse).filter_by(organization_id=oid).all()
    placements = db.query(LivestockPlacement).filter_by(organization_id=oid).all()
    by_house = defaultdict(int)
    for placement in placements:
        group = next((g for g in groups if g.id == placement.group_id), None)
        if group: by_house[placement.house_id] += group.head_count
    housed = [{**rowdata(h), 'occupancy': by_house[h.id], 'available': h.capacity - by_house[h.id]}
             for h in houses]
    health_due = db.query(LivestockHealthRecord).filter(
        LivestockHealthRecord.organization_id == oid,
        LivestockHealthRecord.next_due != None,
        LivestockHealthRecord.next_due <= date.today(),
    ).count()
    animal_count = db.query(GeneralAnimal).filter_by(organization_id=oid, status='active').count()
    ungrouped = db.query(GeneralAnimal).filter_by(organization_id=oid, group_id=None, status='active').count()
    events = db.query(LivestockEvent).filter_by(organization_id=oid).order_by(LivestockEvent.id.desc()).limit(5).all()
    recent_year_events = db.query(LivestockEvent).filter(LivestockEvent.organization_id==oid, LivestockEvent.performed_on >= date.today()-timedelta(days=365)).all()
    event_costs = db.query(LivestockEvent.currency,func.sum(LivestockEvent.cost)).filter_by(organization_id=oid).group_by(LivestockEvent.currency).all()
    group_species = Counter()
    for group in groups: group_species[group.species.strip().lower()] += group.head_count
    species_counts = [{'species': name, 'head_count': count} for name, count in sorted(group_species.items(), key=lambda x: -x[1])]
    months = defaultdict(lambda: {'eggs': 0.0, 'milk_litres': 0.0, 'births': 0, 'mortality': 0})
    for event in recent_year_events:
        month = event.performed_on.strftime('%Y-%m')
        n = float(event.quantity or 0)
        if event.action == 'egg_collection' and event.unit in ('pieces', 'eggs', None): months[month]['eggs'] += n
        if event.action == 'milk_collection' and event.unit in ('litres', 'liters', None): months[month]['milk_litres'] += n
        if event.action == 'birth': months[month]['births'] += int(n)
        if event.action == 'mortality': months[month]['mortality'] += int(n)
    sales = db.query(LivestockSale).filter_by(organization_id=oid).all()
    products_sold = db.query(ProductSale).filter_by(organization_id=oid).all()
    project_costs = db.query(LivestockProjectCost).filter_by(organization_id=oid).all()
    care = db.query(LivestockCareRecord).filter_by(organization_id=oid).all()
    health = db.query(LivestockHealthRecord).filter_by(organization_id=oid, status='completed').all()
    registration_costs=db.query(LivestockRegistrationCost).filter_by(organization_id=oid).all()
    routine_costs=db.query(LivestockRoutineCompletion).filter_by(organization_id=oid).all()
    revenue = defaultdict(Decimal)
    cost = defaultdict(Decimal)
    for record in sales + products_sold: revenue[record.currency] += Decimal(record.gross)
    for currency, total in event_costs: cost[currency] += Decimal(total or 0)
    for record, attr in [(v, 'amount') for v in project_costs] + [(v,'expense') for v in care] + [(v,'cost') for v in health] + [(v,'total') for v in registration_costs] + [(v,'expense') for v in routine_costs]:
        cost[record.currency] += Decimal(getattr(record, attr) or 0)
    figures = [{'currency': cur, 'revenue': float(revenue[cur]), 'tracked_costs': float(cost[cur]),
                'recorded_contribution': float(revenue[cur] - cost[cur])}
               for cur in sorted(set(revenue) | set(cost))]
    return {'ranches': allrows(V5Ranch), 'groups': allrows(LivestockGroup),
        'animals': allrows(GeneralAnimal), 'projects': allrows(LivestockProject),
        'houses': housed, 'placements': allrows(LivestockPlacement),
        'lots': [{**rowdata(x), 'available': float(x.quantity_received - x.quantity_sold)}
                 for x in db.query(ProductLot).filter_by(organization_id=oid).order_by(ProductLot.id.desc()).limit(1500).all()],
        'dashboard': {
            'herds': len(groups), 'population': sum(g.head_count for g in groups) + ungrouped,
            'registered_animals': animal_count, 'houses': len(houses),
            'over_capacity': sum(1 for h in houses if by_house[h.id] > h.capacity),
            'health_due': health_due, 'active_incubations': db.query(LivestockIncubation).filter_by(organization_id=oid, status='incubating').count(),
            'product_lots': db.query(ProductLot).filter_by(organization_id=oid).count(),
            'species': species_counts, 'months': [{'month': m, **v} for m,v in sorted(months.items())][-12:],
            'finance': figures, 'recent_production': [rowdata(e) for e in events[:5]],
            'recent_sales': [rowdata(x) for x in sorted(sales, key=lambda v: v.id, reverse=True)[:5]],
            'note': 'Grouped animal tags are already part of their herd/flock count. Tracked costs exclude unallocated feed stocks, purchases, shared overheads and depreciation. Currencies are never mixed.'}}

@extra_router.get('/livestock/v8/records/{area}')
def livestock_v8_records(area: str, db: Session = Depends(get_db), ctx = Depends(context)):
    _, org, _ = scope(db, ctx, 'livestock')
    model = V8_SECTIONS.get(area)
    if not model: raise HTTPException(404, 'Unknown livestock record area')
    q = db.query(model).filter_by(organization_id=org.id)
    records = q.order_by(model.id.desc()).limit(500).all()
    if area == 'weights':
        rows = livestock_growth_rows(records)
    else:
        rows = [rowdata(x) for x in records]
    if area == 'incubations':
        for item in rows:
            item['hatch_rate_pct'] = round(item['eggs_hatched'] * 100 / item['eggs_set'], 1) if item['eggs_hatched'] is not None and item['eggs_set'] else None
    if area == 'products':
        for item in rows: item['available'] = round(item['quantity_received'] - item['quantity_sold'], 3)
    if area == 'costs':
        project_names = {p.id:p.name for p in db.query(LivestockProject).filter_by(organization_id=org.id).all()}
        for item in rows: item['project_name'] = project_names.get(item['project_id'], 'Unknown')
    if area == 'houses':
        placements = db.query(LivestockPlacement).filter_by(organization_id=org.id).all()
        groups = {g.id:g for g in db.query(LivestockGroup).filter_by(organization_id=org.id).all()}
        occupancy = defaultdict(int)
        for p in placements:
            if p.group_id in groups: occupancy[p.house_id] += groups[p.group_id].head_count
        for item in rows:
            item['occupancy'] = occupancy[item['id']]
            item['available'] = item['capacity'] - item['occupancy']
    return {'items': rows, 'limit': 500, 'note':'Most recent 500 records. Totals on dashboard use full population.'}

@extra_router.post('/livestock/v8/houses', status_code=201)
def v8_house(p: HouseIn, db: Session = Depends(get_db), ctx = Depends(context)):
    actor, org, _ = scope(db, ctx, 'livestock', True)
    ranch(db, org, p.ranch_id)
    if db.query(LivestockHouse).filter_by(organization_id=org.id, code=p.code).first():
        raise HTTPException(409, 'House code already exists')
    return _v8_store(db, actor, LivestockHouse, LivestockHouse(organization_id=org.id, **p.model_dump()), 'livestock_house_added')

@extra_router.post('/livestock/v8/placements', status_code=201)
def v8_place(p: PlaceGroupIn, db: Session = Depends(get_db), ctx = Depends(context)):
    actor, org, _ = scope(db, ctx, 'livestock', True)
    # Serialize assignments per destination house to avoid admission races.
    house = db.query(LivestockHouse).filter_by(id=p.house_id, organization_id=org.id).with_for_update().first()
    group = db.query(LivestockGroup).filter_by(id=p.group_id, organization_id=org.id).with_for_update().first()
    if not house or not group: raise HTTPException(404, 'House or group not found')
    if not house.active: raise HTTPException(409, 'Housing is not active')
    if house.ranch_id != group.ranch_id: raise HTTPException(422, 'Group and house must be in the same ranch')
    if house.species and house.species.strip().lower() != group.species.strip().lower():
        raise HTTPException(422, 'Housing reserved for another species')
    current = db.query(LivestockPlacement).filter_by(organization_id=org.id, group_id=group.id).with_for_update().first()
    if current and current.house_id == house.id: raise HTTPException(409, 'Group already assigned to this house')
    placements = db.query(LivestockPlacement).filter_by(organization_id=org.id, house_id=house.id).all()
    others = [x.group_id for x in placements if x.group_id != group.id]
    occupied = sum(x.head_count for x in db.query(LivestockGroup).filter(
        LivestockGroup.organization_id == org.id, LivestockGroup.id.in_(others)).all()) if others else 0
    if occupied + group.head_count > house.capacity:
        raise HTTPException(409, f'House capacity exceeded: {house.capacity - occupied} places available')
    _v83_valid_house(group, house.house_type)
    policy=db.query(LivestockHousingProfile).filter_by(organization_id=org.id,house_id=house.id).first()
    if policy and policy.purpose not in ('general','other',group.purpose,'rearing'):
        raise HTTPException(422, 'Housing purpose is incompatible with this herd/flock')
    old_id = current.house_id if current else None
    if current:
        current.house_id = house.id; current.assigned_on = p.moved_on; current.assigned_by = actor.id
    else:
        db.add(LivestockPlacement(organization_id=org.id, group_id=group.id, house_id=house.id,
                                 assigned_on=p.moved_on, assigned_by=actor.id))
    history = LivestockHousingMovement(organization_id=org.id, group_id=group.id,
        from_house_id=old_id, to_house_id=house.id, moved_on=p.moved_on, notes=p.notes, recorded_by=actor.id)
    return _v8_store(db, actor, LivestockHousingMovement, history, 'livestock_housing_transfer')

@extra_router.post('/livestock/v8/care', status_code=201)
def v8_care(p: CareIn, db: Session = Depends(get_db), ctx = Depends(context)):
    actor, org, _ = scope(db, ctx, 'livestock', True)
    _v8_target(db, org, p)
    if p.performed_on > date.today(): raise HTTPException(422, 'Future routine work cannot be marked as completed')
    if db.query(LivestockCareRecord).filter_by(organization_id=org.id, reference=p.reference).first():
        raise HTTPException(409, 'Routine record reference already used')
    row = LivestockCareRecord(organization_id=org.id, recorded_by=actor.id, **p.model_dump())
    db.add(row); db.flush()
    finance(db,actor,org,'Livestock daily care: '+p.activity,p.expense,p.currency,'v8_livestock_care',row.id)
    audit(db,actor.id,'livestock_care_completed',row.__tablename__,row.id)
    result = rowdata(row); db.commit(); return {'item':result,'message':'Routine saved and cost posted to Finance'}

@extra_router.post('/livestock/v8/breeding', status_code=201)
def v8_breeding(p: BreedingIn, db: Session = Depends(get_db), ctx = Depends(context)):
    actor, org, _ = scope(db, ctx, 'livestock', True)
    _, animal = _v8_target(db, org, p)
    if animal and animal.sex == 'male': raise HTTPException(422, 'Breeding outcome must target a female animal or breeding group')
    return _v8_store(db, actor, LivestockBreedingRecord,
        LivestockBreedingRecord(organization_id=org.id, recorded_by=actor.id, **p.model_dump()), 'livestock_breeding_recorded')

@extra_router.patch('/livestock/v8/breeding/{record_id}/outcome')
def v8_breeding_outcome(record_id:int, p:BreedingOutcomeIn, db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    row=db.query(LivestockBreedingRecord).filter_by(organization_id=org.id,id=record_id).with_for_update().first()
    if not row:raise HTTPException(404,'Breeding record not found')
    if p.outcome=='delivered':raise HTTPException(422,'Register actual birth and offspring with the V8.3 delivery form')
    if row.outcome in ('delivered','failed'):raise HTTPException(409,'Breeding cycle already closed')
    row.outcome=p.outcome
    if p.notes is not None:row.notes=p.notes
    audit(db,actor.id,'livestock_breeding_outcome',row.__tablename__,row.id,p.outcome)
    result=rowdata(row);db.commit();return {'item':result, 'message':'Breeding outcome updated; register births separately'}

@extra_router.post('/livestock/v8/health',status_code=201)
def v8_health(p:HealthIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    _v8_target(db,org,p)
    if p.status=='completed' and p.performed_on>date.today():raise HTTPException(422,'Completed treatment cannot have a future date')
    row=LivestockHealthRecord(organization_id=org.id,recorded_by=actor.id,**p.model_dump())
    db.add(row);db.flush()
    if p.status=='completed':finance(db,actor,org,'Livestock health: '+p.action,p.cost,p.currency,'v8_livestock_health',row.id)
    audit(db,actor.id,'livestock_health_recorded',row.__tablename__,row.id)
    result=rowdata(row);db.commit();return {'item':result,'message':'Health record saved'}

@extra_router.patch('/livestock/v8/health/{record_id}/complete')
def v8_health_complete(record_id:int,p:CompleteHealthIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    row=db.query(LivestockHealthRecord).filter_by(organization_id=org.id,id=record_id).with_for_update().first()
    if not row:raise HTTPException(404,'Health record not found')
    if row.status!='planned':raise HTTPException(409,'Treatment already completed')
    if p.performed_on>date.today():raise HTTPException(422,'Treatment date is in the future')
    row.status='completed';row.performed_on=p.performed_on;row.cost=p.cost;row.currency=p.currency
    if p.notes is not None:row.notes=p.notes
    db.flush();finance(db,actor,org,'Livestock health: '+row.action,p.cost,p.currency,'v8_livestock_health',row.id)
    audit(db,actor.id,'livestock_health_completed',row.__tablename__,row.id)
    result=rowdata(row);db.commit();return {'item':result,'message':'Health treatment completed'}

@extra_router.post('/livestock/v8/weights',status_code=201)
def v8_weight(p:WeightIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    _v8_target(db,org,p)
    if p.measured_on>date.today():raise HTTPException(422,'Weighing date cannot be in the future')
    return _v8_store(db,actor,LivestockWeightRecord,
       LivestockWeightRecord(organization_id=org.id,recorded_by=actor.id,**p.model_dump()),'livestock_weight_recorded')

@extra_router.post('/livestock/v8/incubations',status_code=201)
def v8_incubation(p:IncubationIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    group=linked(db,LivestockGroup,org,p.group_id,'Flock')
    if group.species.strip().lower() not in POULTRY_SPECIES:raise HTTPException(422,'Incubation requires a poultry flock')
    if db.query(LivestockIncubation).filter_by(organization_id=org.id,batch_code=p.batch_code).first():raise HTTPException(409,'Batch code already used')
    return _v8_store(db,actor,LivestockIncubation,
      LivestockIncubation(organization_id=org.id,recorded_by=actor.id,**p.model_dump()),'livestock_incubation_started')

@extra_router.patch('/livestock/v8/incubations/{record_id}/hatch')
def v8_hatch(record_id:int,p:HatchIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    row=db.query(LivestockIncubation).filter_by(organization_id=org.id,id=record_id).with_for_update().first()
    if not row:raise HTTPException(404,'Incubation not found')
    if row.status!='incubating':raise HTTPException(409,'Hatch already completed')
    if p.eggs_hatched>row.eggs_set:raise HTTPException(422,'Hatched eggs cannot exceed eggs set')
    if p.hatched_on<row.set_on or p.hatched_on>date.today():raise HTTPException(422,'Invalid hatch completion date')
    row.status='completed';row.hatched_on=p.hatched_on;row.eggs_hatched=p.eggs_hatched
    if p.notes is not None:row.notes=p.notes
    audit(db,actor.id,'livestock_hatch_completed',row.__tablename__,row.id)
    result=rowdata(row);db.commit()
    return {'item':result,'hatch_rate_pct':round(p.eggs_hatched/row.eggs_set*100,1),
            'message':'Hatch recorded. Add surviving chicks to population separately using a birth event.'}

# -----------------------------------------------------------------------------
# V8.3 — linked species-aware registration, daily checklists, parental lineage.
# No existing API paths or historical table structures are replaced.
# -----------------------------------------------------------------------------
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError
from modules.livestock.schemas import (
    ConnectedGroupIn,ConnectedIndividualIn,ConnectedHouseIn,RoutineTemplateIn,
    RoutineCompleteIn,RoutineToggleIn,ConnectedBreedingIn,BreedingProgressIn,OffspringIn,
)

V83_POULTRY = POULTRY_SPECIES
V83_POULTRY_HOUSES = {'coop','brooder','layer_house','broiler_house','free_range'}
V83_LIVESTOCK_HOUSES = {'barn','paddock','shed','stable','free_range'}
# Planning estimates only: breed, genetics and husbandry change gestation.
V83_GESTATION_ESTIMATES = {'cattle':283,'goat':150,'sheep':147,'pig':114,'horse':340,'rabbit':31}

def _v83_today():
    return datetime.now(ZoneInfo('Africa/Dar_es_Salaam')).date()

def _v83_is_poultry(species):
    return str(species or '').strip().lower() in V83_POULTRY

def _v83_project(db,org,group_id):
    link=db.query(LivestockProjectGroup).filter_by(organization_id=org.id,group_id=group_id).first()
    return linked(db,LivestockProject,org,link.project_id,'Project') if link else None

def _v83_profile(db,org,group_id):
    return db.query(LivestockGroupProfile).filter_by(organization_id=org.id,group_id=group_id).first()

def _v83_charge(db,actor,org,charge,kind,source_id,project_id,default_quantity,description):
    if not charge or charge.unit_cost is None:return
    quantity=charge.quantity if charge.quantity is not None else Decimal(default_quantity)
    amount=(quantity*charge.unit_cost).quantize(Decimal('0.01'))
    item=LivestockRegistrationCost(organization_id=org.id,project_id=project_id,source_kind=kind,
        source_id=source_id,description=charge.description or description,quantity=quantity,unit=charge.unit,
        unit_cost=charge.unit_cost,total=amount,currency=charge.currency,recorded_on=_v83_today(),recorded_by=actor.id)
    db.add(item);db.flush()
    if amount>0:finance(db,actor,org,description,amount,charge.currency,'v83_livestock_registration_cost',item.id)
    audit(db,actor.id,'livestock_registration_cost',item.__tablename__,item.id)

def _v83_valid_house(group,house_type):
    is_bird=_v83_is_poultry(group.species)
    if is_bird and house_type not in V83_POULTRY_HOUSES:
        raise HTTPException(422,'This house type is for livestock, not poultry')
    if not is_bird and house_type not in V83_LIVESTOCK_HOUSES:
        raise HTTPException(422,'Poultry housing cannot accommodate livestock')
    if house_type=='layer_house' and not (group.species.lower()=='chicken' and group.purpose=='egg_production'):
        raise HTTPException(422,'A layer house requires a chicken flock registered for egg production')
    if house_type=='broiler_house' and group.purpose!='meat':
        raise HTTPException(422,'A broiler house requires poultry registered for meat production')
    if house_type=='brooder' and group.purpose not in ('rearing','breeding','general'):
        raise HTTPException(422,'A brooder requires a flock intended for rearing or breeding')

def _v83_new_cohort(db,actor,org,group,born_on,total,live,name,breed,source_id,kind,
                    dam_id=None,males=None,females=None,weight=None,characteristics=None,notes=None):
    if db.query(LivestockGroup).filter_by(organization_id=org.id,ranch_id=group.ranch_id,name=name).first():
        raise HTTPException(409,'A herd/flock with that cohort name already exists in the ranch')
    baby=LivestockGroup(organization_id=org.id,ranch_id=group.ranch_id,name=name,species=group.species,
                       purpose='rearing',head_count=live,location=group.location,
                       notes=f'Offspring of {group.name}; {kind} #{source_id}')
    db.add(baby);db.flush()
    db.add(LivestockGroupProfile(organization_id=org.id,group_id=baby.id,breed=breed,production_stage='newborn' if kind=='breeding' else 'hatched'))
    project=_v83_project(db,org,group.id)
    if project:db.add(LivestockProjectGroup(organization_id=org.id,project_id=project.id,group_id=baby.id))
    cohort=LivestockOffspringCohort(organization_id=org.id,breeding_id=source_id if kind=='breeding' else None,
        incubation_id=source_id if kind=='incubation' else None,parent_group_id=group.id,child_group_id=baby.id,
        dam_id=dam_id,born_on=born_on,total_born=total,live_count=live,male_count=males,female_count=females,
        initial_weight_kg=weight,breed=breed,characteristics=characteristics,notes=notes,recorded_by=actor.id)
    db.add(cohort);db.flush()
    # Birth event is an audit/analytics record only. Population is already
    # present on the NEW offspring group; do not invoke /livestock/events,
    # which increments an existing herd, or count births twice.
    if live>0:
        db.add(LivestockEvent(organization_id=org.id,group_id=baby.id,animal_id=None,
            reference=f'V83-{kind.upper()}-{source_id}',action='birth',performed_on=born_on,
            quantity=Decimal(live),unit='head',cost=Decimal('0'),currency='TZS',
            notes=f'Traceable offspring cohort #{cohort.id}',recorded_by=actor.id))
    audit(db,actor.id,'livestock_offspring_cohort_created',cohort.__tablename__,cohort.id)
    return cohort,baby

@extra_router.post('/livestock/v83/groups',status_code=201)
def v83_register_group(p:ConnectedGroupIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    project=linked(db,LivestockProject,org,p.project_id,'Project')
    if _v83_is_poultry(p.species) and p.purpose in ('dairy','wool'):
        raise HTTPException(422,'Poultry cannot be registered for dairy or wool production')
    if not _v83_is_poultry(p.species) and p.purpose=='egg_production':
        raise HTTPException(422,'Egg production requires a registered poultry species')
    if project.purpose not in ('general','other',p.purpose) and p.purpose not in ('general','rearing'):
        raise HTTPException(422,'The herd/flock purpose must be compatible with its project')
    if db.query(LivestockGroup).filter_by(organization_id=org.id,ranch_id=project.ranch_id,name=p.name).first():
        raise HTTPException(409,'A herd or flock with this name already exists in the ranch')
    group=LivestockGroup(organization_id=org.id,ranch_id=project.ranch_id,name=p.name,
        species=p.species.strip().lower(),purpose=p.purpose,head_count=p.head_count,location=p.location,notes=p.notes)
    db.add(group);db.flush()
    db.add(LivestockGroupProfile(organization_id=org.id,group_id=group.id,breed=p.breed,production_stage=p.production_stage))
    db.add(LivestockProjectGroup(organization_id=org.id,project_id=project.id,group_id=group.id))
    _v83_charge(db,actor,org,p.charge,'group',group.id,project.id,p.head_count or 1,'Livestock group registration')
    audit(db,actor.id,'livestock_group_registered',group.__tablename__,group.id)
    result=rowdata(group);db.commit();return {'item':result,'message':'Herd/flock registered and linked to project'}

@extra_router.post('/livestock/v83/individuals/{kind}',status_code=201)
def v83_register_individual(kind:str,p:ConnectedIndividualIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    if kind not in ('animals','birds'):raise HTTPException(404,'Unknown registration type')
    group=linked(db,LivestockGroup,org,p.group_id,'Herd/flock')
    if _v83_is_poultry(group.species)!=(kind=='birds'):
        raise HTTPException(422,f'{kind.title()} registration requires a matching herd/flock')
    cohort=None
    if p.offspring_cohort_id:
        cohort=linked(db,LivestockOffspringCohort,org,p.offspring_cohort_id,'Offspring cohort')
        if cohort.child_group_id!=group.id:raise HTTPException(422,'Selected offspring cohort belongs to a different group')
    for identifier,label in ((p.dam_id,'Dam'),(p.sire_id,'Sire')):
        if identifier:
            parent=linked(db,GeneralAnimal,org,identifier,label)
            if parent.species.lower()!=group.species.lower():raise HTTPException(422,f'{label} species does not match group')
            if label=='Dam' and parent.sex=='male':raise HTTPException(422,'Dam cannot be male')
            if label=='Sire' and parent.sex=='female':raise HTTPException(422,'Sire cannot be female')
    import secrets
    tag=(p.tag or '').strip() or f'{"BRD" if kind=="birds" else "LV"}-{org.id}-{secrets.token_hex(5).upper()}'
    if db.query(GeneralAnimal).filter_by(organization_id=org.id,tag=tag).first():
        raise HTTPException(409,'Tag already registered')
    prior=db.query(GeneralAnimal).filter_by(organization_id=org.id,group_id=group.id,status='active').count()
    if prior>=group.head_count:raise HTTPException(409,'All animals in this group are already individually registered. Increase its population through traceable birth or stock adjustment before adding more.')
    profile=_v83_profile(db,org,group.id)
    breeding_source=(linked(db,LivestockBreedingRecord,org,cohort.breeding_id,'Breeding') if cohort and cohort.breeding_id else None)
    if cohort and cohort.incubation_id:
        incubation_link=db.query(LivestockIncubationSource).filter_by(organization_id=org.id,incubation_id=cohort.incubation_id).first()
        if incubation_link and incubation_link.breeding_id:
            breeding_source=linked(db,LivestockBreedingRecord,org,incubation_link.breeding_id,'Poultry breeding')
    inherited_sire=None
    if breeding_source and breeding_source.sire_tag:
        inherited_sire=db.query(GeneralAnimal).filter_by(organization_id=org.id,tag=breeding_source.sire_tag).first()
        if inherited_sire and (inherited_sire.species!=group.species or inherited_sire.sex=='female'):
            inherited_sire=None
    animal=GeneralAnimal(organization_id=org.id,ranch_id=group.ranch_id,group_id=group.id,
        tag=tag,species=group.species,breed=cohort.breed if cohort and cohort.breed else (profile.breed if profile else None),
        sex=p.sex,birth_date=p.birth_date or (cohort.born_on if cohort else None),origin=p.origin,
        status='active')
    db.add(animal);db.flush()
    db.add(LivestockIndividualProfile(organization_id=org.id,animal_id=animal.id,offspring_cohort_id=p.offspring_cohort_id,
        dam_id=p.dam_id or (cohort.dam_id if cohort else None),sire_id=p.sire_id or (inherited_sire.id if inherited_sire else None),
        characteristics=p.characteristics,initial_weight_kg=p.initial_weight_kg))
    project=_v83_project(db,org,group.id)
    _v83_charge(db,actor,org,p.charge,kind,animal.id,project.id if project else None,1,'Livestock individual registration')
    if p.initial_weight_kg:
        db.add(LivestockWeightRecord(organization_id=org.id,group_id=None,animal_id=animal.id,
            measured_on=p.birth_date or (cohort.born_on if cohort else _v83_today()),
            weight_kg=p.initial_weight_kg,sample_size=1,notes='Registration weight',recorded_by=actor.id))
    audit(db,actor.id,'livestock_individual_registered',animal.__tablename__,animal.id)
    result=rowdata(animal);db.commit();return {'item':result,'message':'Identity registered using linked herd/flock information'}

@extra_router.post('/livestock/v83/houses',status_code=201)
def v83_register_house(p:ConnectedHouseIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    group=linked(db,LivestockGroup,org,p.group_id,'Herd/flock')
    _v83_valid_house(group,p.house_type)
    if p.assign_now and group.head_count>p.capacity:raise HTTPException(409,'Housing capacity is less than current herd/flock population')
    if p.assign_now and db.query(LivestockPlacement).filter_by(organization_id=org.id,group_id=group.id).first():
        raise HTTPException(409,'Group already housed. Use the transfer action instead')
    if db.query(LivestockHouse).filter_by(organization_id=org.id,code=p.code).first():
        raise HTTPException(409,'House code already exists')
    house=LivestockHouse(organization_id=org.id,ranch_id=group.ranch_id,code=p.code,name=p.name,
        house_type=p.house_type,species=group.species,capacity=p.capacity,location=p.location,active=True)
    db.add(house);db.flush()
    db.add(LivestockHousingProfile(organization_id=org.id,house_id=house.id,purpose=group.purpose,source_group_id=group.id))
    if p.assign_now:
        db.add(LivestockPlacement(organization_id=org.id,group_id=group.id,house_id=house.id,
            assigned_on=_v83_today(),assigned_by=actor.id))
        db.add(LivestockHousingMovement(organization_id=org.id,group_id=group.id,to_house_id=house.id,
            from_house_id=None,moved_on=_v83_today(),recorded_by=actor.id))
    project=_v83_project(db,org,group.id)
    _v83_charge(db,actor,org,p.charge,'house',house.id,project.id if project else None,1,'Livestock housing registration')
    audit(db,actor.id,'livestock_housing_registered',house.__tablename__,house.id)
    result=rowdata(house);db.commit();return {'item':result,'message':'Housing registered for matching species and purpose'}

@extra_router.post('/livestock/v83/routines',status_code=201)
def v83_routine_template(p:RoutineTemplateIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    group=linked(db,LivestockGroup,org,p.group_id,'Herd/flock')
    if p.activity=='milking' and (_v83_is_poultry(group.species) or group.purpose!='dairy'):
        raise HTTPException(422,'Milking routine requires dairy livestock')
    if p.activity=='egg_collection_check' and not _v83_is_poultry(group.species):
        raise HTTPException(422,'Egg-collection routine requires poultry')
    if db.query(LivestockRoutineTemplate).filter_by(organization_id=org.id,group_id=group.id,name=p.name,active=True).first():
        raise HTTPException(409,'An active routine with this name already exists for the group')
    task=LivestockRoutineTemplate(organization_id=org.id,created_by=actor.id,**p.model_dump())
    return _v8_store(db,actor,LivestockRoutineTemplate,task,'livestock_routine_created')

@extra_router.patch('/livestock/v83/routines/{task_id}/active')
def v83_routine_active(task_id:int,p:RoutineToggleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    task=linked(db,LivestockRoutineTemplate,org,task_id,'Routine')
    task.active=p.active;audit(db,actor.id,'livestock_routine_toggled',task.__tablename__,task.id)
    result=rowdata(task);db.commit();return {'item':result}

@extra_router.post('/livestock/v83/routines/{task_id}/complete',status_code=201)
def v83_routine_complete(task_id:int,p:RoutineCompleteIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    task=db.query(LivestockRoutineTemplate).filter_by(organization_id=org.id,id=task_id).with_for_update().first()
    if not task:raise HTTPException(404,'Routine not found')
    if not task.active:raise HTTPException(409,'Routine has been paused')
    if p.completed_on!=_v83_today():raise HTTPException(422,'Routine checklists can only be completed for the current local day')
    if p.completed_on<task.starts_on or str(p.completed_on.weekday()) not in task.days_of_week:
        raise HTTPException(422,'Routine is not scheduled today')
    if db.query(LivestockRoutineCompletion).filter_by(organization_id=org.id,template_id=task.id,completed_on=p.completed_on).first():
        raise HTTPException(409,'Routine already completed today')
    quantity=p.quantity if p.quantity is not None else task.default_quantity
    expense=p.expense if p.expense is not None else task.default_expense
    row=LivestockRoutineCompletion(organization_id=org.id,template_id=task.id,completed_on=p.completed_on,
        quantity=quantity,expense=expense,currency=task.currency,notes=p.notes,completed_by=actor.id)
    db.add(row);db.flush()
    if expense>0:finance(db,actor,org,'Livestock routine: '+task.activity,expense,task.currency,'v83_livestock_routine_completion',row.id)
    audit(db,actor.id,'livestock_routine_completed',row.__tablename__,row.id)
    result=rowdata(row);db.commit();return {'item':result,'message':'Task completed once today; tomorrow a fresh unchecked task appears'}

@extra_router.get('/livestock/v83/routines/today')
def v83_routine_today(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=scope(db,ctx,'livestock');today=_v83_today()
    tasks=db.query(LivestockRoutineTemplate).filter_by(organization_id=org.id).order_by(LivestockRoutineTemplate.shift,LivestockRoutineTemplate.id).all()
    completions=db.query(LivestockRoutineCompletion).filter_by(organization_id=org.id,completed_on=today).all()
    done={row.template_id for row in completions}
    groups={x.id:x for x in db.query(LivestockGroup).filter_by(organization_id=org.id).all()}
    items=[]
    for task in tasks:
        record=rowdata(task)
        record['group_name']=groups.get(task.group_id).name if task.group_id in groups else 'Unknown'
        record['completed_today']=task.id in done
        record['scheduled_today']=bool(task.active and today>=task.starts_on and str(today.weekday()) in task.days_of_week)
        items.append(record)
    return {'today':today.isoformat(),'items':items,'due':sum(x['scheduled_today'] and not x['completed_today'] for x in items),
            'completed':sum(x['scheduled_today'] and x['completed_today'] for x in items),
            'note':'In-app reminders are shown when the module is open; browser push/SMS scheduling is not enabled.'}

@extra_router.post('/livestock/v83/breeding',status_code=201)
def v83_breeding(p:ConnectedBreedingIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    group=linked(db,LivestockGroup,org,p.group_id,'Herd/flock')
    if group.purpose!='breeding':raise HTTPException(422,'Choose a herd/flock registered for breeding')
    if _v83_is_poultry(group.species) and p.expected_date:
        raise HTTPException(422,'Birds do not have pregnancy/delivery dates. Track hatching through Incubation.')
    if p.animal_id:
        animal=linked(db,GeneralAnimal,org,p.animal_id,'Dam/hen')
        if animal.group_id!=group.id or animal.status!='active' or animal.sex!='female':
            raise HTTPException(422,'Breeding requires an active female in the chosen breeding group')
        if db.query(LivestockBreedingRecord).filter(LivestockBreedingRecord.organization_id==org.id,
            LivestockBreedingRecord.animal_id==animal.id,LivestockBreedingRecord.outcome.in_(['planned','served','confirmed'])).first():
            raise HTTPException(409,'This female has an open breeding cycle. Update its outcome first.')
    if p.outcome!='planned' and p.service_date>_v83_today():
        raise HTTPException(422,'Future service date must be marked planned')
    expected=p.expected_date
    if not expected and group.species.lower() in V83_GESTATION_ESTIMATES:
        expected=p.service_date+timedelta(days=V83_GESTATION_ESTIMATES[group.species.lower()])
    record=LivestockBreedingRecord(organization_id=org.id,group_id=group.id,animal_id=p.animal_id,
        method=p.method,sire_tag=p.sire_tag,service_date=p.service_date,expected_date=expected,
        outcome=p.outcome,notes=p.notes,recorded_by=actor.id)
    db.add(record);db.flush()
    project=_v83_project(db,org,group.id)
    _v83_charge(db,actor,org,p.charge,'breeding',record.id,project.id if project else None,1,'Livestock breeding / insemination cost')
    db.add(LivestockBreedingTimeline(organization_id=org.id,breeding_id=record.id,event=p.outcome,
        event_on=p.service_date,notes=p.notes,recorded_by=actor.id))
    audit(db,actor.id,'livestock_breeding_registered',record.__tablename__,record.id)
    result=rowdata(record);db.commit();return {'item':result,'message':'Breeding registered with linked herd and offspring tracking'}

@extra_router.patch('/livestock/v83/breeding/{record_id}/progress')
def v83_breeding_progress(record_id:int,p:BreedingProgressIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    record=db.query(LivestockBreedingRecord).filter_by(organization_id=org.id,id=record_id).with_for_update().first()
    if not record:raise HTTPException(404,'Breeding not found')
    if record.outcome in ('delivered','failed','cancelled'):raise HTTPException(409,'Breeding cycle already closed')
    if p.event_on<record.service_date or p.event_on>_v83_today():raise HTTPException(422,'Invalid progress date')
    record.outcome=p.outcome
    db.add(LivestockBreedingTimeline(organization_id=org.id,breeding_id=record.id,event=p.outcome,
        event_on=p.event_on,notes=p.notes,recorded_by=actor.id))
    audit(db,actor.id,'livestock_breeding_progress',record.__tablename__,record.id)
    result=rowdata(record);db.commit();return {'item':result}

@extra_router.post('/livestock/v83/breeding/{record_id}/offspring',status_code=201)
def v83_birth(record_id:int,p:OffspringIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    record=db.query(LivestockBreedingRecord).filter_by(organization_id=org.id,id=record_id).with_for_update().first()
    if not record:raise HTTPException(404,'Breeding not found')
    if record.outcome in ('delivered','failed','cancelled'):raise HTTPException(409,'Breeding cycle already closed')
    group=linked(db,LivestockGroup,org,record.group_id or linked(db,GeneralAnimal,org,record.animal_id,'Animal').group_id,'Herd')
    if _v83_is_poultry(group.species):raise HTTPException(422,'Use Incubation to register hatched birds')
    if p.born_on<record.service_date or p.born_on>_v83_today():raise HTTPException(422,'Invalid delivery date')
    profile=_v83_profile(db,org,group.id)
    cohort,baby=_v83_new_cohort(db,actor,org,group,p.born_on,p.total_born,p.live_count,p.cohort_name,
        profile.breed if profile else None,record.id,'breeding',dam_id=record.animal_id,males=p.male_count,
        females=p.female_count,weight=p.initial_weight_kg,characteristics=p.characteristics,notes=p.notes)
    project=_v83_project(db,org,baby.id)
    _v83_charge(db,actor,org,p.charge,'birth',cohort.id,project.id if project else None,p.live_count or 1,'Livestock birth and offspring registration')
    record.outcome='delivered'
    db.add(LivestockBreedingTimeline(organization_id=org.id,breeding_id=record.id,event='delivered',
        event_on=p.born_on,notes=p.notes,recorded_by=actor.id))
    db.commit();return {'item':rowdata(cohort),'offspring_group':rowdata(baby),'message':'Delivery and traceable offspring cohort registered; population counted once'}

@extra_router.post('/livestock/v83/incubations/{record_id}/offspring',status_code=201)
def v83_hatched_offspring(record_id:int,p:OffspringIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    record=db.query(LivestockIncubation).filter_by(organization_id=org.id,id=record_id).with_for_update().first()
    if not record:raise HTTPException(404,'Incubation not found')
    if db.query(LivestockOffspringCohort).filter_by(organization_id=org.id,incubation_id=record_id).first():
        raise HTTPException(409,'Offspring from this incubation batch have already been registered')
    if p.born_on<record.set_on or p.born_on>_v83_today():raise HTTPException(422,'Invalid hatch date')
    if p.total_born>record.eggs_set:raise HTTPException(422,'Hatched birds exceed eggs set')
    if record.status=='completed' and record.eggs_hatched!=p.total_born:
        raise HTTPException(422,'Hatched count must match the recorded hatch result')
    group=linked(db,LivestockGroup,org,record.group_id,'Flock')
    profile=_v83_profile(db,org,group.id)
    cohort,baby=_v83_new_cohort(db,actor,org,group,p.born_on,p.total_born,p.live_count,p.cohort_name,
        profile.breed if profile else None,record.id,'incubation',males=p.male_count,females=p.female_count,
        weight=p.initial_weight_kg,characteristics=p.characteristics,notes=p.notes)
    project=_v83_project(db,org,baby.id)
    _v83_charge(db,actor,org,p.charge,'hatch',cohort.id,project.id if project else None,p.live_count or 1,'Poultry hatch and offspring registration')
    if record.status=='incubating':record.status='completed';record.hatched_on=p.born_on;record.eggs_hatched=p.total_born
    db.commit();return {'item':rowdata(cohort),'offspring_group':rowdata(baby),'message':'Hatch results and offspring flock registered; population counted once'}

@extra_router.get('/livestock/v83/lineage/{group_id}')
def v83_group_lineage(group_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=scope(db,ctx,'livestock');group=linked(db,LivestockGroup,org,group_id,'Herd/flock')
    cohort=db.query(LivestockOffspringCohort).filter_by(organization_id=org.id,child_group_id=group.id).first()
    tag_ids=[a.id for a in db.query(GeneralAnimal).filter_by(organization_id=org.id,group_id=group.id).all()]
    def fetch(model,key):return [rowdata(x) for x in db.query(model).filter(model.organization_id==org.id, ((getattr(model,'group_id')==group.id) | (getattr(model,'animal_id').in_(tag_ids) if tag_ids else False))).order_by(model.id.desc()).limit(500).all()]
    linked_incubation=(db.query(LivestockIncubationSource).filter_by(organization_id=org.id,incubation_id=cohort.incubation_id).first() if cohort and cohort.incubation_id else None)
    source_breeding_id=cohort.breeding_id if cohort and cohort.breeding_id else (linked_incubation.breeding_id if linked_incubation else None)
    return {'group':rowdata(group),'offspring':rowdata(cohort) if cohort else None,
        'source_breeding':rowdata(linked(db,LivestockBreedingRecord,org,source_breeding_id,'Breeding cycle')) if source_breeding_id else None,
        'individuals':[rowdata(x) for x in db.query(GeneralAnimal).filter_by(organization_id=org.id,group_id=group.id).all()],
        'weights':fetch(LivestockWeightRecord,'weights'),'health':fetch(LivestockHealthRecord,'health'),
        'care':fetch(LivestockCareRecord,'care'),
        'routine_completions':[rowdata(x) for x in db.query(LivestockRoutineCompletion).join(LivestockRoutineTemplate,LivestockRoutineTemplate.id==LivestockRoutineCompletion.template_id).filter(LivestockRoutineCompletion.organization_id==org.id,LivestockRoutineTemplate.organization_id==org.id,LivestockRoutineTemplate.group_id==group.id).order_by(LivestockRoutineCompletion.id.desc()).limit(500).all()]}

V8_SECTIONS.update({'offspring':LivestockOffspringCohort,'routine_templates':LivestockRoutineTemplate,
    'routine_completions':LivestockRoutineCompletion,'registration_costs':LivestockRegistrationCost,
    'breeding_timeline':LivestockBreedingTimeline,'individual_profiles':LivestockIndividualProfile})

@extra_router.get('/livestock/v83/context')
def v83_context(db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=scope(db,ctx,'livestock')
    links=db.query(LivestockProjectGroup).filter_by(organization_id=org.id).all()
    profiles=db.query(LivestockGroupProfile).filter_by(organization_id=org.id).all()
    houses=db.query(LivestockHousingProfile).filter_by(organization_id=org.id).all()
    offspring=db.query(LivestockOffspringCohort).filter_by(organization_id=org.id).order_by(LivestockOffspringCohort.id.desc()).limit(500).all()
    individuals=db.query(LivestockIndividualProfile).filter_by(organization_id=org.id).all()
    breeding=db.query(LivestockBreedingRecord).filter_by(organization_id=org.id).all()
    timeline=db.query(LivestockBreedingTimeline).filter_by(organization_id=org.id).all()
    today=_v83_today()
    b_rows=[]
    for b in breeding:
        record=rowdata(b)
        record['days_until_delivery']=(b.expected_date-today).days if b.expected_date and b.outcome not in ('delivered','failed','cancelled') else None
        record['alert']=('Overdue' if record['days_until_delivery'] is not None and record['days_until_delivery']<0 else
                         'Due soon' if record['days_until_delivery'] is not None and record['days_until_delivery']<=14 else 'Monitoring')
        b_rows.append(record)
    return {'group_profiles':[rowdata(x) for x in profiles],
            'group_projects':[rowdata(x) for x in links],
            'house_profiles':[rowdata(x) for x in houses],
            'individual_profiles':[rowdata(x) for x in individuals],
            'offspring':[rowdata(x) for x in offspring],
            'incubation_sources':[rowdata(x) for x in db.query(LivestockIncubationSource).filter_by(organization_id=org.id).all()],
            'breeding':b_rows,'breeding_timeline':[rowdata(x) for x in timeline],
            'today':today.isoformat(), 'gestation_estimates':V83_GESTATION_ESTIMATES,
            'incubation_estimates':V83_INCUBATION_ESTIMATES,
            'alerts':{'hatches_due_14_days':db.query(LivestockIncubation).filter(
                LivestockIncubation.organization_id==org.id,LivestockIncubation.status=='incubating',
                LivestockIncubation.expected_on>=today,LivestockIncubation.expected_on<=today+timedelta(days=14)).count(),
                      'births_overdue':sum(x['days_until_delivery'] is not None and x['days_until_delivery']<0 for x in b_rows),
                      'births_due_14_days':sum(x['days_until_delivery'] is not None and 0<=x['days_until_delivery']<=14 for x in b_rows)}}

# Poultry parentage: connect fertilization/mating with the egg incubation batch.
from modules.livestock.schemas import ConnectedIncubationIn
V83_INCUBATION_ESTIMATES={'chicken':21,'duck':28,'turkey':28,'quail':17,'goose':30,'guinea_fowl':28}

@extra_router.post('/livestock/v83/incubations',status_code=201)
def v83_start_incubation(p:ConnectedIncubationIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=scope(db,ctx,'livestock',True)
    group=linked(db,LivestockGroup,org,p.group_id,'Source flock')
    if not _v83_is_poultry(group.species):raise HTTPException(422,'Hatchery incubation requires a registered poultry flock')
    if db.query(LivestockIncubation).filter_by(organization_id=org.id,batch_code=p.batch_code).first():
        raise HTTPException(409,'Incubation batch reference already exists')
    source=None
    if p.breeding_id:
        source=linked(db,LivestockBreedingRecord,org,p.breeding_id,'Poultry breeding cycle')
        if source.group_id!=group.id:raise HTTPException(422,'Incubated eggs and breeding cycle must belong to the same flock')
    expected=p.expected_on or (p.set_on+timedelta(days=V83_INCUBATION_ESTIMATES[group.species.lower()]))
    incub=LivestockIncubation(organization_id=org.id,group_id=group.id,batch_code=p.batch_code,
        eggs_set=p.eggs_set,set_on=p.set_on,expected_on=expected,status='incubating',
        notes=p.notes,recorded_by=actor.id)
    db.add(incub);db.flush()
    db.add(LivestockIncubationSource(organization_id=org.id,incubation_id=incub.id,breeding_id=p.breeding_id,recorded_by=actor.id))
    project=_v83_project(db,org,group.id)
    _v83_charge(db,actor,org,p.charge,'incubation',incub.id,project.id if project else None,p.eggs_set,'Poultry incubation batch cost')
    audit(db,actor.id,'livestock_incubation_started',incub.__tablename__,incub.id)
    result=rowdata(incub);db.commit();return {'item':result,'message':'Incubation batch saved with a linked source flock and breeding cycle'}
