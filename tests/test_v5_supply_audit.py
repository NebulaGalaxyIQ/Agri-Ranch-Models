"""V5.3 stocked feed, landed cost, finance, audit and organization boundary checks."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'gh_v53_supply_integration.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def ok(resp,code=200):
    assert resp.status_code==code,(resp.status_code,resp.text[:2200])
    return resp.json()

def test_feed_inventory_costs_and_staff_audit():
    with TestClient(main.app) as c:
        ok(c.post('/api/auth/setup',json={'full_name':'Platform Owner','email':'owner-supply@example.com','password':'SecurePassword123!'}))
        data=[]
        for n in (1,2):
            registered=ok(c.post('/api/v5/organizations/register',json={'name':f'Supply Test Org {n}',
                'email':f'supply{n}@example.com','admin_name':'Admin','admin_email':f'admin-supply{n}@example.com',
                'admin_password':'StrongPassword123!'}),201)
            oid=registered['organization']['id']
            ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
            key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':45,'max_employees':25}))['key']
            data.append((oid,key))
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'admin-supply1@example.com','password':'StrongPassword123!'}))
        c.headers['X-Organization-ID']=str(data[0][0])
        ok(c.post('/api/v5/subscription/redeem',json={'key':data[0][1]}))
        ranch=ok(c.post('/api/v5/ranches',json={'name':'Main ranch'}))['id']
        proj=ok(c.post('/api/v5/projects',json={'name':'Feedlot','ranch_id':ranch}),201)['id']
        batch=ok(c.post('/api/v5/batches',json={'name':'Batch Alpha','project_id':proj,'capacity':10}))['id']
        animal=ok(c.post('/api/v5/animals',json={'tag':'K-001','batch_id':batch}),201)['id']
        maize=ok(c.post('/api/v5/stock/items',json={'name':'Maize bran','unit':'kg','category':'feed','reorder_level':20}),201)['id']
        grass=ok(c.post('/api/v5/stock/items',json={'name':'Grass','unit':'kg','category':'feed','reorder_level':10}),201)['id']
        assert ok(c.get('/api/v5/routine/options'))['feeds']==[]
        recipe=ok(c.post('/api/v5/rations',json={'name':'Starter 60/40','feed_type':'starter',
           'ingredients':[{'item_id':maize,'percent':60},{'item_id':grass,'percent':40}]}),201)
        mix=recipe['id'];finished=recipe['finished_item_id']
        assert finished!=maize
        catalog=ok(c.get('/api/v5/feed/catalog'))['items']
        assert any(x['is_mix'] and x['id']==finished for x in catalog)
        assert not any(x['name']=='Mix: Starter 60/40' for x in ok(c.get('/api/v5/routine/options'))['feeds'])
        rec1=ok(c.post('/api/v5/stock/receive',json={'item_id':maize,'quantity':100,'total_cost':120000,
            'transport_cost':20000,'other_cost':10000,'supplier_name':'Tanga Feed Co','supplier_contact':'+255700000000',
            'origin':'Tanga','invoice_number':'INV-AB-1','reference':'RCV-MAIZE-01','expiry_date':'2026-12-30','currency':'TZS'}),201)
        assert rec1['total_landed_cost']==150000 and rec1['landed_cost_per_unit']==1500
        ok(c.post('/api/v5/stock/receive',json={'item_id':grass,'quantity':100,'total_cost':30000,
           'reference':'RCV-GRASS-01'}),201)
        assert c.post('/api/v5/stock/receive',json={'item_id':grass,'quantity':1,'total_cost':1,'reference':'RCV-GRASS-01'}).status_code==409
        opts=ok(c.get('/api/v5/routine/options'))
        assert {f['id'] for f in opts['feeds']}=={maize,grass}
        ok(c.post('/api/v5/feed/assignments',json={'ration_id':mix,'batch_id':batch}),201)
        recommendation=ok(c.get('/api/v5/feed/recommendation',params={'batch_id':batch}))
        assert recommendation['ration_id']==mix and recommendation['stocked'] is False
        assert c.post('/api/v5/feeding/record',json={'batch_id':batch,'ration_quantity_kg':10,
                'client_reference':'UNSTOCKED-MIX-001'}).status_code==409
        ok(c.post('/api/v5/mix-production',json={'ration_id':mix,'finished_item_id':finished,'quantity_kg':40}),201)
        assert ok(c.get('/api/v5/feed/recommendation',params={'batch_id':batch}))['stocked'] is True
        opts=ok(c.get('/api/v5/routine/options'))
        assert opts['mixes'][0]['id']==mix and opts['mixes'][0]['available_kg']==40
        # V6.2: once the batch has a mix, additional feed items are not allowed.
        blocked=c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning',
            'ration_quantity_kg':10,'extras':[{'item_id':maize,'quantity_kg':4}],
            'client_reference':'FORBIDDEN-EXTRA-001'})
        assert blocked.status_code in (409,422)
        feeding=ok(c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning',
            'ration_quantity_kg':10,'client_reference':'FEEDING-LINKED-001'}),201)
        assert feeding['stock_deducted'] is True and feeding['quantity_kg']==10
        assert feeding['calculated_feed_cost']>0
        again=ok(c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning',
            'ration_quantity_kg':10,'client_reference':'FEEDING-LINKED-001'}),201)
        assert again['id']==feeding['id']
        assert c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning',
            'ration_quantity_kg':1000,'client_reference':'OVER-STOCK-001'}).status_code==409
        led=ok(c.get('/api/v5/stock/ledger'))['items']
        assert any(x['source']=='feeding' and x['reference'].startswith('feed-') and x['recorded_by']=='Admin' for x in led)
        maize_balance=next(x['balance'] for x in ok(c.get('/api/v5/stock/status'))['items'] if x['id']==maize)
        assert maize_balance==76
        financial=ok(c.get('/api/v5/finance'))['items']
        assert any(x['kind']=='asset_purchase' and x['source']=='stock_receipt' for x in financial)
        assert any(x['kind']=='cost' and x['source']=='stock_issue' for x in financial)
        details=ok(c.get('/api/v5/audit/entries?section=stock'))['items']
        assert any(x['supplier']=='Tanga Feed Co' and x['transport_cost']==20000 for x in details)
        pen=ok(c.post('/api/v5/pens',json={'batch_id':batch,'name':'Cleaning Pen A'}),201)['id']
        tasks=ok(c.post('/api/v5/tasks',json={'title':'Yesterday cleaning',
            'category':'cleaning','frequency':'once','due_date':'2026-01-01','batch_id':batch,'pen_id':pen}),201)
        overview=ok(c.get('/api/v5/audit/overview'))
        assert overview['tasks_overdue']>=1 and overview['feeding_recorded_kg']==10
        assert c.get('/api/v5/audit/export?section=finance').status_code==200
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'admin-supply2@example.com','password':'StrongPassword123!'}))
        c.headers['X-Organization-ID']=str(data[1][0])
        ok(c.post('/api/v5/subscription/redeem',json={'key':data[1][1]}))
        assert ok(c.get('/api/v5/stock/status'))['items']==[]
        assert ok(c.get('/api/v5/audit/entries?section=finance'))['items']==[]
        assert c.post('/api/v5/stock/issue',json={'item_id':maize,'quantity':1,'reference':'CROSS-ORG-ISSUE-1'}).status_code==404
