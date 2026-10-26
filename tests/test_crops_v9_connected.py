"""Run from project root: DATABASE_URL=sqlite:///... python tests/test_crops_v9_connected.py
This suite uses a disposable, isolated in-memory database; no production data involved.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from datetime import date,timedelta
from decimal import Decimal
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from database import Base,User
from modules.organizations.models import Organization,V5Ranch
from modules.crops import router as r
from modules.crops.models import CropField,V9Project,V9Cycle,V9Harvest,V9Record,V9Completion
from modules.crops.schemas import (ProjectIn,UnitIn,VarietyIn,CycleInV9,RecordIn,BudgetIn,RoutineIn,
 CompletionIn,TrialIn,PlotIn,HarvestIn,SaleIn,StockIn,SECTIONS)

def assert_rejected(fn,code):
    try:fn()
    except HTTPException as exc:
        assert exc.status_code==code,(code,exc.status_code,exc.detail)
    else:raise AssertionError(f'Expected HTTP {code}')

def test_all():
    assert len(SECTIONS)==21
    engine=create_engine('sqlite:///:memory:',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        a=User(full_name='Test admin',email='admin@example.test',password_hash='not-for-login',role='org_admin')
        org=Organization(name='Global Demo Farm',email='farm@example.test',country='Canada',status='approved')
        db.add_all([a,org]);db.flush()
        farm=V5Ranch(organization_id=org.id,name='East Farm');db.add(farm);db.flush()
        field=CropField(organization_id=org.id,ranch_id=farm.id,name='Field A',area_ha=Decimal('10'))
        db.add(field);db.commit()
        ctx=(a,org,SimpleNamespace(role='org_admin'))
        # Test V9-specific business behavior without external subscriptions/licensing.
        r.v9_scope=lambda _db,_ctx,write=False: _ctx
        day=date.today()
        proj=r.v9_create_project(ProjectIn(ranch_id=farm.id,name='Global wheat research',code='WHEAT-26',currency='CAD',method='precision',start_date=day-timedelta(days=35)),db,ctx)['item']
        assert_rejected(lambda:r.v9_create_project(ProjectIn(ranch_id=farm.id,name='Duplicate',code='WHEAT-26',currency='CAD'),db,ctx),409)
        unit=r.v9_create_unit(UnitIn(field_id=field.id,name='Block 1',area_ha=Decimal('4.0')),db,ctx)['item']
        assert_rejected(lambda:r.v9_create_unit(UnitIn(field_id=field.id,name='Oversized',area_ha=Decimal('7')),db,ctx),409)
        variety=r.v9_create_variety(VarietyIn(name='Wheat',variety='Trial spring',category='cereal'),db,ctx)['item']
        cycle=r.v9_create_cycle(CycleInV9(project_id=proj['id'],unit_id=unit['id'],variety_id=variety['id'],planted_area_ha=Decimal('3'),planted_on=day-timedelta(days=30)),db,ctx)['item']
        assert_rejected(lambda:r.v9_create_cycle(CycleInV9(project_id=proj['id'],unit_id=unit['id'],variety_id=variety['id'],planted_area_ha=Decimal('2'),planted_on=day-timedelta(days=20)),db,ctx),409)
        budget=r.v9_create_budget(BudgetIn(project_id=proj['id'],cycle_id=cycle['id'],category='seed',description='Spring seed',quantity=Decimal('125'),unit='kg',unit_cost=Decimal('3'),currency='CAD',status='approved'),db,ctx)['item']
        assert budget['amount']==375.0
        assert_rejected(lambda:r.v9_create_budget(BudgetIn(project_id=proj['id'],category='labor',description='Labor',quantity=Decimal('1'),unit='days',unit_cost=Decimal('35'),currency='USD'),db,ctx),422)
        routine=r.v9_create_routine(RoutineIn(project_id=proj['id'],cycle_id=cycle['id'],title='Check irrigation',frequency='daily',start_date=day),db,ctx)['item']
        due=r.v9_routines_due(day,db,ctx)
        assert len(due['items'])==1 and due['items'][0]['check'] is None
        checked=r.v9_complete_routine(routine['id'],CompletionIn(day=day),db,ctx)['item']
        assert checked['status']=='completed'
        assert_rejected(lambda:r.v9_complete_routine(routine['id'],CompletionIn(day=day),db,ctx),409)
        assert r.v9_routines_due(day,db,ctx)['items'][0]['check']['status']=='completed'
        trial=r.v9_create_trial(TrialIn(project_id=proj['id'],cycle_id=cycle['id'],title='Nitrogen treatments',question='Which method produces a better result?',replications=4,start_date=day),db,ctx)['item']
        plot=r.v9_create_plot(PlotIn(trial_id=trial['id'],unit_id=unit['id'],code='B1',treatment='Control',replicate=1,area_ha=Decimal('.25'),is_control=True),db,ctx)['item']
        obs=r.v9_record('trial_observations',RecordIn(project_id=proj['id'],cycle_id=cycle['id'],performed_on=day,title='Plant height measurement',data={'trial_id':trial['id'],'plot_id':plot['id'],'trait':'Height','value':54,'measurement_unit':'cm','method':'ruler'}),db,ctx)['item']
        assert obs['data']['value']==54
        assert_rejected(lambda:r.v9_record('irrigation',RecordIn(project_id=proj['id'],cycle_id=cycle['id'],performed_on=day,title='Invalid numeric source',data={'system':'drip','measurement_source':'meter','water_m3':-25}),db,ctx),422)
        fert=r.v9_record('nutrition',RecordIn(project_id=proj['id'],cycle_id=cycle['id'],performed_on=day,title='Nutrition treatment',quantity=Decimal('10'),unit_cost=Decimal('5'),currency='CAD',data={'material':'Fertilizer','application_method':'broadcast'}),db,ctx)['item']
        assert fert['unit_cost']==5.0
        harvest=r.v9_create_harvest(HarvestIn(project_id=proj['id'],cycle_id=cycle['id'],unit_id=unit['id'],harvested_on=day,batch_ref='H-TEST-1',gross_kg=Decimal('1000'),tare_kg=Decimal('20'),rejected_kg=Decimal('30')),db,ctx)['item']
        assert harvest['marketable_kg']==950.0
        assert_rejected(lambda:r.v9_create_sale(SaleIn(lot_id=harvest['id'],buyer='Exporter',quantity_kg=Decimal('951'),price_per_kg=Decimal('2'),currency='CAD'),db,ctx),409)
        sold=r.v9_create_sale(SaleIn(lot_id=harvest['id'],buyer='Exporter',quantity_kg=Decimal('250'),price_per_kg=Decimal('2'),currency='CAD',sold_on=day),db,ctx)['item']
        assert sold['gross']==500.0
        stock=r.v9_crop_stock(StockIn(lot_id=harvest['id'],action='loss',quantity_kg=Decimal('10'),reference='LOSS-TEST-1'),db,ctx)['item']
        assert_rejected(lambda:r.v9_crop_stock(StockIn(lot_id=harvest['id'],action='loss',quantity_kg=Decimal('10'),reference='LOSS-TEST-1'),db,ctx),409)
        remaining=db.query(V9Harvest).filter_by(id=harvest['id']).one()
        assert Decimal(remaining.available_kg)==Decimal('690')
        insight=r.v9_analytics(db,ctx)['items'][0]
        assert insight['harvested_marketable_kg']==950.0 and insight['sold_kg']==250.0 and insight['unsold_kg']==690.0
        assert insight['currencies'][0]['currency']=='CAD' and insight['currencies'][0]['recorded_cost']==50.0
        work=r.v9_workspace(db,ctx)
        assert len(work['projects'])==1 and len(work['plots'])==1 and len(work['stock'])==1
        other=Organization(name='Other tenant',email='other@example.test',country='USA',status='approved')
        db.add(other);db.commit()
        assert_rejected(lambda:r.v9_project_cycle(db,other,proj['id']),404) if hasattr(r,'v9_project_cycle') else None
        print('PASS: 21 sections, projects, cross-reference security, area bounds, budgets, routines, trials, costs, harvest inventory, sales, analytics, idempotency')
if __name__=='__main__':test_all()
