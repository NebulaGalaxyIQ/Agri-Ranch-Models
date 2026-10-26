"""Operational workflows and cross-tenant references."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'ranch_v5_ops_test.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def ok(r,expected=200):
    assert r.status_code==expected,(r.status_code,r.text)
    return r.json()

def test_ops():
    with TestClient(main.app) as c:
        ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'ownerops@tests.example','password':'ownerPassword123'}))
        orgs=[];keys=[]
        for n in (1,2):
            x=ok(c.post('/api/v5/organizations/register',json={'name':f'Org {n}','email':f'org{n}@tests.example','admin_name':'Admin','admin_email':f'adminops{n}@tests.example','admin_password':'strongPassword123'}),201)
            oid=x['organization']['id'];orgs.append(oid)
            ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
            keys.append(ok(c.post('/api/v5/platform/license-keys',json={'organization_id':oid}))['key'])
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'adminops1@tests.example','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(orgs[0]);ok(c.post('/api/v5/subscription/redeem',json={'key':keys[0]}))
        ranch=ok(c.post('/api/v5/ranches',json={'name':'Main'}))['id']
        project=ok(c.post('/api/v5/projects',json={'name':'Fattening Project','ranch_id':ranch}),201)['id']
        bid=ok(c.post('/api/v5/batches',json={'name':'Batch A','project_id':project,'capacity':5}))['id']
        ok(c.post('/api/v5/animals',json={'batch_id':bid,'tag':'GOAT-1','entry_weight_kg':30}),201)
        assert len(ok(c.get('/api/v5/animals'))['items'])==1
        feed=ok(c.post('/api/v5/stock/items',json={'name':'Maize','unit':'kg'}),201)['id']
        ok(c.post('/api/v5/stock/movements',json={'item_id':feed,'direction':'in','quantity':100,'reference':'purchase-0001'}),201)
        assert c.post('/api/v5/stock/movements',json={'item_id':feed,'direction':'out','quantity':1000,'reference':'bad-out'}).status_code==409
        created=ok(c.post('/api/v5/rations',json={'name':'Maize 100','ingredients':[{'item_id':feed,'percent':100}],'batch_id':bid,'kg_per_head_day':1.2}),201)
        ration=created['id'];finished=created['finished_item_id']
        ok(c.post('/api/v5/mix-production',json={'ration_id':ration,'finished_item_id':finished,'quantity_kg':25}),201)
        items=ok(c.get('/api/v5/stock/items'))['items'];balances={x['id']:x['balance'] for x in items}
        assert balances[feed]==75 and balances[finished]==25
        ok(c.post('/api/v5/finance',json={'kind':'cost','category':'Labour','amount':1000,'batch_id':bid}),201)
        assert ok(c.get('/api/v5/analytics/overview'))['recorded_profit']==-1000
        assert c.get('/api/v5/animals',headers={'X-Organization-ID':str(orgs[1])}).status_code==403
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'adminops2@tests.example','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(orgs[1]);ok(c.post('/api/v5/subscription/redeem',json={'key':keys[1]}))
        assert ok(c.get('/api/v5/animals'))['items']==[]
        assert c.post('/api/v5/animals',json={'batch_id':bid,'tag':'STOLEN'}).status_code==404
        assert c.post('/api/v5/stock/movements',json={'item_id':feed,'direction':'in','quantity':4,'reference':'another-ref'}).status_code==404
