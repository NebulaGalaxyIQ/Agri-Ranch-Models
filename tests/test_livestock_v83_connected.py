"""V8.3 species/project-linked workflow, checklists, lineage and finance regression.
Run isolated: PYTHONPATH=backend pytest -q tests/test_livestock_v83_connected.py
"""
import os,tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
path=Path(tempfile.gettempdir())/'gh_livestock_v83_connected.sqlite'
if path.exists():path.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(path)
from fastapi.testclient import TestClient
from main import app
BASE='/api/v6/livestock'

def ok(response,status=200):
    assert response.status_code==status,(response.status_code,response.text)
    return response.json()

def test_connected_livestock_v83():
    today=datetime.now(ZoneInfo('Africa/Dar_es_Salaam')).date().isoformat()
    with TestClient(app) as c:
        ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner_v83@example.org','password':'SecureOwnerPass123!'}))
        oid=ok(c.post('/api/v5/organizations/register',json={'name':'V83 Org','email':'v83@example.org','admin_name':'Admin','admin_email':'admin_v83@example.org','admin_password':'SecureAdminPass123!'}),201)['organization']['id']
        ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
        key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':30,'max_employees':25}))['key']
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'admin_v83@example.org','password':'SecureAdminPass123!'}))
        c.headers['X-Organization-ID']=str(oid)
        ok(c.post('/api/v5/subscription/redeem',json={'key':key}))
        ranch=ok(c.post('/api/v5/ranches',json={'name':'V8.3 Ranch'}))['id']
        project=ok(c.post(f'{BASE}/projects',json={'ranch_id':ranch,'name':'Connected Breeding','purpose':'general'}),201)['item']['id']
        group=ok(c.post(f'{BASE}/v83/groups',json={'project_id':project,'name':'Registered Cattle Breeders','species':'cattle','purpose':'breeding','breed':'Boran','head_count':3,'charge':{'quantity':3,'unit':'head','unit_cost':10000,'currency':'TZS'}}),201)['item']['id']
        chickens=ok(c.post(f'{BASE}/v83/groups',json={'project_id':project,'name':'Registered Layers','species':'chicken','purpose':'egg_production','breed':'ISA Brown','head_count':15}),201)['item']['id']
        eggbreeders=ok(c.post(f'{BASE}/v83/groups',json={'project_id':project,'name':'Hatching hens','species':'chicken','purpose':'breeding','head_count':5}),201)['item']['id']
        assert c.post(f'{BASE}/v83/groups',json={'project_id':project,'name':'Bad layers','species':'goat','purpose':'egg_production','head_count':10}).status_code==422
        person=ok(c.post(f'{BASE}/v83/individuals/animals',json={'group_id':group,'sex':'female','initial_weight_kg':200,'characteristics':'Brown white ear'}),201)['item']
        assert person['species']=='cattle' and person['breed']=='Boran' and person['ranch_id']==ranch
        assert c.post(f'{BASE}/v83/individuals/birds',json={'group_id':group,'sex':'female'}).status_code==422
        assert c.post(f'{BASE}/v83/individuals/animals',json={'group_id':chickens,'sex':'female'}).status_code==422
        chick=ok(c.post(f'{BASE}/v83/individuals/birds',json={'group_id':chickens,'sex':'female'}),201)['item']
        assert chick['species']=='chicken' and chick['breed']=='ISA Brown'
        assert c.post(f'{BASE}/v83/houses',json={'group_id':group,'code':'H1','name':'Wrong House','house_type':'layer_house','capacity':20}).status_code==422
        assert c.post(f'{BASE}/v83/houses',json={'group_id':chickens,'code':'H2','name':'Wrong barn','house_type':'barn','capacity':20}).status_code==422
        layer_house=ok(c.post(f'{BASE}/v83/houses',json={'group_id':chickens,'code':'LAY-1','name':'Layer House','house_type':'layer_house','capacity':16,'assign_now':True,'charge':{'quantity':2,'unit':'unit','unit_cost':10000}}),201)['item']
        assert layer_house['species']=='chicken'
        assert c.post(f'{BASE}/v8/placements',json={'group_id':group,'house_id':layer_house['id']}).status_code==422
        assert c.post(f'{BASE}/v8/placements',json={'group_id':eggbreeders,'house_id':layer_house['id']}).status_code in (409,422)
        context=ok(c.get(f'{BASE}/v83/context'))
        assert next(x for x in context['group_profiles'] if x['group_id']==group)['breed']=='Boran'
        assert next(x for x in context['group_projects'] if x['group_id']==group)['project_id']==project
        task=ok(c.post(f'{BASE}/v83/routines',json={'group_id':group,'name':'Morning feed cattle','activity':'feeding','shift':'morning','reminder_time':'07:30','default_quantity':8,'unit':'kg','default_expense':400,'starts_on':today,'days_of_week':'0123456'}),201)['item']['id']
        task_today=ok(c.get(f'{BASE}/v83/routines/today'))
        assert any(t['id']==task and t['scheduled_today'] for t in task_today['items'])
        ok(c.post(f'{BASE}/v83/routines/{task}/complete',json={'completed_on':today}),201)
        assert c.post(f'{BASE}/v83/routines/{task}/complete',json={'completed_on':today}).status_code==409
        assert next(t for t in ok(c.get(f'{BASE}/v83/routines/today'))['items'] if t['id']==task)['completed_today']
        assert c.post(f'{BASE}/v83/routines/{task}/complete',json={'completed_on':'2001-01-01'}).status_code==422
        ok(c.patch(f'{BASE}/v83/routines/{task}/active',json={'active':False}))
        assert next(t for t in ok(c.get(f'{BASE}/v83/routines/today'))['items'] if t['id']==task)['active']==False
        breeding=ok(c.post(f'{BASE}/v83/breeding',json={'group_id':group,'animal_id':person['id'],'service_date':'2026-01-01','method':'ai','sire_tag':'SIRE-1','outcome':'confirmed','charge':{'quantity':1,'unit_cost':2500}}),201)['item']
        assert breeding['expected_date'] is not None
        assert c.post(f'{BASE}/v83/breeding',json={'group_id':group,'animal_id':person['id'],'service_date':'2026-02-01'}).status_code==409
        assert c.post(f'{BASE}/v83/breeding',json={'group_id':chickens,'service_date':'2026-01-01'}).status_code==422
        assert c.post(f'{BASE}/v83/breeding',json={'group_id':eggbreeders,'service_date':'2026-01-01','expected_date':'2026-12-01'}).status_code==422
        child=ok(c.post(f'{BASE}/v83/breeding/{breeding["id"]}/offspring',json={'born_on':today,'total_born':2,'live_count':2,'cohort_name':'Boran calves 2026','male_count':1,'female_count':1,'initial_weight_kg':28,'charge':{'quantity':2,'unit_cost':1000}}),201)
        assert child['offspring_group']['head_count']==2
        assert c.post(f'{BASE}/v83/breeding/{breeding["id"]}/offspring',json={'born_on':today,'total_born':2,'live_count':2,'cohort_name':'Boran calves again'}).status_code==409
        baby_group=child['offspring_group']['id']
        baby=ok(c.post(f'{BASE}/v83/individuals/animals',json={'group_id':baby_group,'offspring_cohort_id':child['item']['id'],'sex':'female','initial_weight_kg':28}),201)['item']
        assert baby['birth_date']==today and baby['breed']=='Boran'
        ok(c.post(f'{BASE}/v8/weights',json={'animal_id':baby['id'],'measured_on':today,'weight_kg':30}),201)
        ok(c.post(f'{BASE}/v8/health',json={'animal_id':baby['id'],'action':'vaccination','performed_on':today}),201)
        lineage=ok(c.get(f'{BASE}/v83/lineage/{baby_group}'))
        assert lineage['offspring']['breeding_id']==breeding['id'] and len(lineage['weights'])==2
        assert len(lineage['health'])==1
        assert next(x for x in ok(c.get(f'{BASE}/v83/context'))['group_projects'] if x['group_id']==baby_group)['project_id']==project
        poultry_cycle=ok(c.post(f'{BASE}/v83/breeding',json={'group_id':eggbreeders,'method':'natural','service_date':'2026-10-01'}),201)['item']['id']
        incubation=ok(c.post(f'{BASE}/v83/incubations',json={'group_id':eggbreeders,'breeding_id':poultry_cycle,'batch_code':'FERTILE-001','eggs_set':10,'set_on':'2026-10-01','charge':{'quantity':10,'unit_cost':50}}),201)['item']['id']
        linked_source=ok(c.get(f'{BASE}/v83/context'))['incubation_sources']
        assert any(x['incubation_id']==incubation and x['breeding_id']==poultry_cycle for x in linked_source)
        assert c.post(f'{BASE}/v83/incubations',json={'group_id':chickens,'breeding_id':poultry_cycle,'batch_code':'INVALID-INCUB','eggs_set':10,'set_on':'2026-10-01'}).status_code==422
        chicks=ok(c.post(f'{BASE}/v83/incubations/{incubation}/offspring',json={'born_on':today,'total_born':8,'live_count':7,'cohort_name':'October day-old chicks'}),201)
        assert chicks['offspring_group']['head_count']==7
        assert ok(c.get(f'{BASE}/v83/lineage/{chicks["offspring_group"]["id"]}'))['source_breeding']['id']==poultry_cycle
        assert c.post(f'{BASE}/v83/incubations/{incubation}/offspring',json={'born_on':today,'total_born':8,'live_count':7,'cohort_name':'Duplicate chicks'}).status_code==409
        workspace=ok(c.get(f'{BASE}/v8/workspace'))
        assert workspace['dashboard']['population']==3+15+5+2+7
        figures={x['currency']:x for x in workspace['dashboard']['finance']}
        assert figures['TZS']['tracked_costs']>=30000+20000+400+2500+2000
        performance=ok(c.get(f'{BASE}/project-performance'))['items'][0]['currencies']
        assert any(x['registration_costs']>=55000 and x['routine_costs']==400 for x in performance)
        finance=ok(c.get('/api/v5/finance'))['items']
        assert len([x for x in finance if x['source']=='v83_livestock_routine_completion'])==1
        assert len([x for x in finance if x['source']=='v83_livestock_registration_cost'])==5
