"""Integration checks for V5.2 existing-data workflows, tenant ownership and management insights."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'ranch_v52_smart_test.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main
from database import SessionLocal
from modules.fattening.models import WeightObservation

def ok(r,status=200):
    assert r.status_code==status,(r.status_code,r.text[:2000])
    return r.json()

def test_smart_chain_weight_nutrition_water_and_reports():
    with TestClient(main.app) as c:
        ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner-smart@example.org','password':'strongPassword123'}))
        orgs=[];keys=[]
        for n in (1,2):
            item=ok(c.post('/api/v5/organizations/register',json={
               'name':f'Smart Test Ranch Org {n}','email':f'smart-org{n}@example.org','admin_name':'Admin',
               'admin_email':f'smart-admin{n}@example.org','admin_password':'strongPassword123'}),201)
            oid=item['organization']['id'];orgs.append(oid)
            ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
            keys.append(ok(c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':66}))['key'])
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'smart-admin1@example.org','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(orgs[0]);ok(c.post('/api/v5/subscription/redeem',json={'key':keys[0]}))
        assert c.post('/api/v5/projects',json={'name':'Impossible without ranch'}).status_code==422
        assert c.post('/api/v5/batches',json={'name':'Impossible without project'}).status_code==422
        ranch=ok(c.post('/api/v5/ranches',json={'name':'Northern Ranch'}))['id']
        assert c.post('/api/v5/ranches',json={'name':'northern ranch'}).status_code==409
        pr=ok(c.post('/api/v5/projects',json={'name':'Fattening sheep','ranch_id':ranch,'target_weight_kg':45}),201)['id']
        assert c.post('/api/v5/projects',json={'name':'FATTENING SHEEP','ranch_id':ranch}).status_code==409
        bad=c.post('/api/v5/batches',json={'name':'Wrong','project_id':pr,'ranch_id':ranch+100})
        assert bad.status_code==422
        b=ok(c.post('/api/v5/batches',json={'name':'Starter','project_id':pr,'capacity':2}))['id']
        assert c.post('/api/v5/batches',json={'name':'starter','project_id':pr}).status_code==409
        sheep=ok(c.post('/api/v5/animals',json={'tag':'SHEEP-X1','batch_id':b,'species':'sheep',
          'age_months':9,'supplier_name':'Vendor A','origin':'Dodoma','entry_weight_kg':25,
          'arrival_date':'2026-10-01','purchase_cost':50000}),201)
        assert sheep['current_weight_kg']==25
        ok(c.post('/api/v5/animals',json={'tag':'SHEEP-X2','batch_id':b,'species':'sheep'}),201)
        assert c.post('/api/v5/animals',json={'tag':'SHEEP-X3','batch_id':b}).status_code==409
        # Moving between existing batches updates the animal and respects capacity.
        destination=ok(c.post('/api/v5/batches',json={'name':'Grower','project_id':pr,'capacity':1}))['id']
        moved=ok(c.post('/api/v5/routine/move',json={'animal_id':sheep['id'],'destination_batch_id':destination,
          'shift':'Afternoon','client_reference':'smart-move-001'}),201)
        assert moved['to_batch_id']==destination
        assert ok(c.post('/api/v5/routine/move',json={'animal_id':sheep['id'],
          'destination_batch_id':destination,'client_reference':'smart-move-001'}),201)['id']==moved['id']
        ok(c.post('/api/v5/animals',json={'tag':'SHEEP-X3','batch_id':b,'species':'sheep'}),201)
        assert c.post('/api/v5/routine/move',json={'animal_id':sheep['id'],'destination_batch_id':b,
            'client_reference':'smart-move-full-001'}).status_code==409

        item=ok(c.post('/api/v5/stock/items',json={'name':'Maize Bran','category':'feed'}),201)['id']
        assert c.post('/api/v5/stock/items',json={'name':'maize bran'}).status_code==409
        assert ok(c.put(f'/api/v5/stock/items/{item}/nutrients',json={'nutrients':{'crude_protein':18.5,'calcium':0.5,'phosphorus':0.23},'notes':'Lab sheet'}))['nutrients']['crude_protein']==18.5
        assert c.put(f'/api/v5/stock/items/{item}/nutrients',json={'nutrients':{'fake_nutrient':18}}).status_code==422
        mix=ok(c.post('/api/v5/rations',json={'name':'Starter mix','ingredients':[{'item_id':item,'percent':100}],'feed_type':'starter'}),201)['id']
        assert c.post('/api/v5/rations',json={'name':'Bad mix','ingredients':[{'item_id':item,'percent':50},{'item_id':item,'percent':50}]}).status_code==422
        ok(c.put(f'/api/v5/rations/{mix}/nutrients',json={'nutrients':{'crude_protein':16,'calcium':0.9}}))
        assert ok(c.get(f'/api/v5/rations/{mix}/nutrients'))['nutrients']['calcium']==0.9
        # A watering event uses an existing batch, shift and optional observation—no litres/quantity.
        rec=ok(c.post('/api/v5/routines',json={'category':'watering','batch_id':b,'shift':'Morning',
           'quantity':500,'unit':'litres','notes':'Clean water available','client_reference':'smart-water-001'}),201)
        assert rec['quantity'] is None and rec['unit'] is None
        assert ok(c.post('/api/v5/routines',json={'category':'watering','batch_id':b,
           'client_reference':'smart-water-001'}),201)['id']==rec['id']
        assert c.post('/api/v5/routines',json={'category':'weighing','batch_id':b,'quantity':32,
          'client_reference':'missing-animal-001'}).status_code==422
        wt=ok(c.post('/api/v5/routines',json={'category':'weighing','animal_id':sheep['id'],
            'quantity':35,'shift':'Morning','client_reference':'smart-weigh-001'}),201)
        assert wt['unit']=='kg' and wt['animal_tag']=='SHEEP-X1' and wt['batch_id']==destination
        with SessionLocal() as db:
            hist=db.query(WeightObservation).filter_by(organization_id=orgs[0],animal_id=sheep['id']).all()
            assert len(hist)==1 and float(hist[0].weight_kg)==35
        assert ok(c.get('/api/v5/animals'))['items'][1]['current_weight_kg']==35 or any(x['tag']=='SHEEP-X1' and x['current_weight_kg']==35 for x in ok(c.get('/api/v5/animals'))['items'])
        insights=ok(c.get('/api/v5/analytics/performance'))
        first=next(x for x in insights['animal_performance'] if x['tag']=='SHEEP-X1')
        assert first['current_kg']==35 and first['adg_kg_per_day'] is not None
        assert first['assessment'] in ('Growth recorded','Within batch range','Above batch peers')
        assert c.get('/api/v5/analytics/performance/export?format=csv').status_code==200
        pdf=c.get('/api/v5/analytics/performance/export?format=pdf')
        assert pdf.status_code==200,pdf.text[:400]
        assert pdf.content.startswith(b'%PDF')
        assert b'Feed' in c.get('/api/v5/analytics/performance/export?format=csv').content
        assert c.get('/api/v5/analytics/performance?project_id=123456').status_code==404
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'smart-admin2@example.org','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(orgs[1]);ok(c.post('/api/v5/subscription/redeem',json={'key':keys[1]}))
        assert c.get(f'/api/v5/rations/{mix}/nutrients').status_code==404
        assert c.get(f'/api/v5/stock/items/{item}/nutrients').status_code==404
        assert ok(c.get('/api/v5/analytics/performance'))['animal_performance']==[]
