"""End-to-end tests for new V5 project, batch, feeding, notification and reporting flows."""
import os, tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'ranch_v5_guided_flows.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def check(r,code=200):
    assert r.status_code==code,(r.status_code,r.text)
    return r.json()

def test_guided_project_batch_animal_feed_reporting():
    with TestClient(main.app) as c:
        check(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner-guided@example.com','password':'strongPassword123'}))
        ids=[];keys=[]
        for n in (1,2):
            org=check(c.post('/api/v5/organizations/register',json={'name':f'Farm {n}','email':f'farm{n}@example.com','admin_name':'Farmer','admin_email':f'farmer{n}@example.com','admin_password':'strongPassword123'}),201)
            oid=org['organization']['id'];ids.append(oid)
            check(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
            keys.append(check(c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':45,'max_employees':25}))['key'])
        check(c.post('/api/auth/logout'))
        check(c.post('/api/auth/login',json={'email':'farmer1@example.com','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(ids[0])
        check(c.post('/api/v5/subscription/redeem',json={'key':keys[0]}))
        ranch_id=check(c.post('/api/v5/ranches',json={'name':'Main Ranch'}))['id']
        pr=check(c.post('/api/v5/projects',json={'ranch_id':ranch_id,'name':'Goat Fattening 2026','code':'GF-2026','start_date':'2026-10-23','end_date':'2026-12-25','objective':'Fatten goats'}),201)
        assert pr['name']=='Goat Fattening 2026'
        assert c.post('/api/v5/projects',json={'name':'Bad Date','start_date':'2026-10-23','end_date':'2026-10-22'}).status_code==422
        batch=check(c.post('/api/v5/batches',json={'name':'Starter goats','project_id':pr['id'],'capacity':2,'start_date':'2026-10-23','end_date':'2026-12-20'}))
        assert batch['capacity']==2 and batch['animal_count']==0
        assert check(c.get('/api/v5/ranches'))['items'][0]['name']=='Main Ranch'
        animal_data={'batch_id':batch['id'],'tag':'GOAT-01','species':'goat','sex':'female','age_months':10,'breed':'Boer','color':'Brown','origin':'Dodoma','supplier_name':'Supplier A','supplier_contact':'+255700000000','arrival_date':'2026-10-20','entry_weight_kg':21.5}
        animal=check(c.post('/api/v5/animals',json=animal_data),201)
        assert animal['breed']=='Boer' and animal['supplier_name']=='Supplier A'
        check(c.post('/api/v5/animals',json={**animal_data,'tag':'GOAT-02'}),201)
        full=c.post('/api/v5/animals',json={**animal_data,'tag':'GOAT-03'})
        assert full.status_code==409,full.text
        assert check(c.get('/api/v5/batches'))['items'][0]['available_capacity']==0
        assert c.patch(f"/api/v5/batches/{batch['id']}",json={'capacity':1}).status_code==409
        notification=check(c.get('/api/v5/notifications'))
        assert any(n['category']=='capacity' for n in notification['items'])
        other=check(c.post('/api/v5/batches',json={'name':'Finisher goats','project_id':pr['id'],'capacity':1}))
        check(c.post(f"/api/v5/animals/{animal['id']}/transfer",json={'batch_id':other['id']}))
        assert check(c.get('/api/v5/batches'))['items'][0]['available_capacity']==0 # latest batch has one animal
        feed1=check(c.post('/api/v5/stock/items',json={'name':'Maize bran','category':'feed','unit':'kg'}),201)['id']
        feed2=check(c.post('/api/v5/stock/items',json={'name':'Grass','category':'feed','unit':'kg'}),201)['id']
        check(c.post('/api/v5/stock/movements',json={'item_id':feed1,'direction':'in','quantity':100,'reference':'PURCHASE-001'}),201)
        check(c.post('/api/v5/stock/receive',json={'item_id':feed2,'quantity':20,'total_cost':0,'reference':'PURCHASE-002'}),201)
        created=check(c.post('/api/v5/rations',json={'name':'Starter mix','feed_type':'starter','ingredients':[{'item_id':feed1,'percent':30},{'item_id':feed2,'percent':70}]}),201)
        mix=created['id']
        check(c.post('/api/v5/mix-production',json={'ration_id':mix,'finished_item_id':created['finished_item_id'],'quantity_kg':10}),201)
        check(c.post('/api/v5/feed/assignments',json={'ration_id':mix,'batch_id':batch['id'],'start_date':'2026-10-23'}),201)
        check(c.post('/api/v5/feed/plans',json={'ration_id':mix,'batch_id':batch['id'],'kg_per_head_day':1.25,'shift':'Morning','start_date':'2026-10-23'}),201)
        rec=check(c.get(f"/api/v5/feed/recommendation?batch_id={batch['id']}&shift=Morning"))
        assert rec['ration_id']==mix and rec['feed_type']=='starter' and rec['kg_per_head_day']==1.25
        # V6.2: extra ingredients cannot be recorded alongside an assigned mix.
        rejected=c.post('/api/v5/feeding/record',json={'batch_id':batch['id'],'shift':'Morning',
            'ration_quantity_kg':2.5,'extras':[{'item_id':feed2,'quantity_kg':1}],
            'client_reference':'REJECTED-EXTRA-001'})
        assert rejected.status_code in (409,422)
        result=check(c.post('/api/v5/feeding/record',json={'batch_id':batch['id'],'shift':'Morning',
            'ration_quantity_kg':2.5,'client_reference':'RECORD-123456'}),201)
        assert result['quantity_kg']==2.5 and result['stock_deducted'] is True
        assert check(c.post('/api/v5/feeding/record',json={'batch_id':batch['id'],'shift':'Morning','ration_quantity_kg':2.5,'client_reference':'RECORD-123456'}),201)['id']==result['id']
        stock=check(c.get('/api/v5/stock/items'))['items']
        assert next(i['balance'] for i in stock if i['id']==feed1)==97
        check(c.post('/api/v5/finance',json={'batch_id':batch['id'],'kind':'cost','category':'Labour','amount':50000}),201)
        report=check(c.get('/api/v5/reports/summary'))
        assert report['active_animals']==2 and report['batch_capacity']==3 and report['feeding_kg_recorded']==2.5
        scoped=check(c.get(f"/api/v5/reports/summary?project_id={pr['id']}"))
        assert scoped['recorded_cost']==50000
        csv=c.get('/api/v5/reports/export?format=csv')
        assert csv.status_code==200 and b'Starter goats' in csv.content
        pdf=c.get('/api/v5/reports/export?format=pdf')
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
        check(c.post('/api/auth/logout'))
        check(c.post('/api/auth/login',json={'email':'farmer2@example.com','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(ids[1]);check(c.post('/api/v5/subscription/redeem',json={'key':keys[1]}))
        assert check(c.get('/api/v5/projects'))['items']==[]
        assert c.get(f"/api/v5/reports/summary?project_id={pr['id']}").status_code==404
        assert c.post('/api/v5/feed/assignments',json={'ration_id':mix,'batch_id':batch['id']}).status_code==404
        assert c.post('/api/v5/feeding/record',json={'batch_id':batch['id'],'shift':'Morning','extras':[{'item_id':feed1,'quantity_kg':1}],'client_reference':'CROSS-TEST-4567'}).status_code==404
