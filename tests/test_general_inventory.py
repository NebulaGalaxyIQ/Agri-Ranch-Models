"""Independent SQLite acceptance test for generalized inventory and corrections."""
import os, tempfile
from pathlib import Path
path=Path(tempfile.gettempdir())/'gh_v59_inventory_test.sqlite'
if path.exists():path.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(path)
from fastapi.testclient import TestClient
import main

def ok(resp,code=200):
    assert resp.status_code==code,(resp.status_code,resp.text[:1100])
    return resp.json()

def test_general_inventory_and_tenant_isolation():
    with TestClient(main.app) as client:
        ok(client.post('/api/auth/setup',json={'full_name':'Platform Admin','email':'owner-v59@test.org','password':'StrongPassword1!'}))
        orgs=[]
        for i in range(2):
            email=f'admin-v59-{i}@test.org'
            created=ok(client.post('/api/v5/organizations/register',json={'name':f'Ranch Organization {i}','email':f'ranch-v59-{i}@test.org','admin_name':'Organization Admin','admin_email':email,'admin_password':'StrongPassword1!'}),201)
            oid=created['organization']['id']
            ok(client.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
            key=ok(client.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':30,'max_employees':25}))['key']
            orgs.append((oid,key,email))
        ok(client.post('/api/auth/logout'))
        oid,key,email=orgs[0]
        ok(client.post('/api/auth/login',json={'email':email,'password':'StrongPassword1!'}))
        client.headers['X-Organization-ID']=str(oid)
        ok(client.post('/api/v5/subscription/redeem',json={'key':key}))
        categories=ok(client.get('/api/v5/stock/categories'))['items']
        assert {c['id'] for c in categories}>={'feed','medicine','herbicide','uniform','boots','gardening_tool','other'}
        payload={'name':'Worker Safety Boots','category':'boots','unit':'pairs','valuation_currency':'TZS','reorder_level':3,
                 'attributes':{'size':'Mixed sizes','manufacturer':'Brand A'},
                 'receipt':{'item_id':0,'quantity':10,'total_cost':200000,'transport_cost':10000,'currency':'TZS','reference':'V59-BOOTS-001','supplier_name':'Local Supplier'}}
        row=ok(client.post('/api/v5/stock/receive/new-item',json=payload),201)
        item=row['id']
        assert row['balance']==10
        details=ok(client.get(f'/api/v5/stock/items/{item}/details'))
        assert details['category']=='boots' and details['attributes']['size']=='Mixed sizes'
        assert len([f for f in ok(client.get('/api/v5/finance'))['items'] if f['source']=='stock_receipt'])==1
        assert client.post('/api/v5/stock/receive/new-item',json=payload).status_code==409
        payload['name']='Hidden feed';payload['category']='feed';payload['receipt']['reference']='V59-FEED-BLOCK'
        assert client.post('/api/v5/stock/receive/new-item',json=payload).status_code==422
        assert client.patch(f'/api/v5/stock/items/{item}',json={'name':'Safety Boots Updated'}).status_code==422
        ok(client.patch(f'/api/v5/stock/items/{item}',json={'name':'Safety Boots Updated','reason':'Correction to full inventory name'}))
        assert client.patch(f'/api/v5/stock/items/{item}/details',json={'attributes':{'size':'42'}}).status_code==422
        ok(client.patch(f'/api/v5/stock/items/{item}/details',json={'reason':'Update the recorded sizes','attributes':{'size':'42'}}))
        rec=ok(client.get('/api/v5/stock/ledger'))['items'][0]
        ok(client.patch(f'/api/v5/stock/receipts/{rec["id"]}',json={'reason':'Supplier name correction','supplier_name':'Revised Supplier'}))
        # An agriculture category shares the same stock and FX pipeline.
        fertilizer={'name':'NPK fertilizer','category':'fertilizer','unit':'bags','valuation_currency':'TZS','reorder_level':1,
                    'attributes':{'strength_or_concentration':'20-10-10','storage_instructions':'Keep dry'},
                    'receipt':{'item_id':0,'quantity':2,'total_cost':40,'transport_cost':5,'reference':'V59-FERT-USD',
                               'currency':'USD','exchange_rate':2500}}
        fert=ok(client.post('/api/v5/stock/receive/new-item',json=fertilizer),201)
        assert fert['total_landed_cost']==112500
        assert ok(client.get(f'/api/v5/stock/items/{fert["id"]}/details'))['attributes']['strength_or_concentration']=='20-10-10'
        assert 'fertilizer' in {x['id'] for x in ok(client.get('/api/v5/stock/categories'))['items']}
        feed=ok(client.post('/api/v5/stock/items',json={'name':'Sunflower','category':'feed','unit':'kg','currency':'TZS'}),201)['id']
        ok(client.post('/api/v5/stock/receive',json={'item_id':feed,'quantity':10,'total_cost':100000,'reference':'V59-FEED-01'}),201)
        assert {x['id'] for x in ok(client.get('/api/v5/stock/status'))['items']}=={item,feed,fert['id']}
        ok(client.post('/api/v5/stock/issue',json={'item_id':item,'quantity':3,'reference':'V59-OUT-BOOTS','note':'Issued safety boots to staff'}),201)
        assert ok(client.get(f'/api/v5/stock/items/{item}/details'))['name']=='Safety Boots Updated'
        ok(client.post('/api/auth/logout'))
        oid2,key2,email2=orgs[1]
        ok(client.post('/api/auth/login',json={'email':email2,'password':'StrongPassword1!'}))
        client.headers['X-Organization-ID']=str(oid2)
        ok(client.post('/api/v5/subscription/redeem',json={'key':key2}))
        assert ok(client.get('/api/v5/stock/items'))['items']==[]
        assert client.get(f'/api/v5/stock/items/{item}/details').status_code==404
        assert client.patch(f'/api/v5/stock/items/{item}/details',json={'reason':'Not my organization','attributes':{'size':'44'}}).status_code==404
        assert client.post('/api/v5/stock/receive',json={'item_id':item,'quantity':2,'total_cost':100,'reference':'CROSS-STOCK-01'}).status_code==404
