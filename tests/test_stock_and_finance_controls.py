"""V5.4 regression: financial links, stock editing, task board, shift safety, validation."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'gh_v54_smart_integration.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def ok(r, status=200):
    assert r.status_code==status,(r.status_code,r.text[:2500]);return r.json()

def test_smart_operational_flow():
    with TestClient(main.app) as c:
        ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner-v54@example.com','password':'UniquePassword123!'}))
        reg=ok(c.post('/api/v5/organizations/register',json={'name':'Example Farm','email':'v54@example.com',
           'admin_name':'Admin','admin_email':'admin-v54@example.com','admin_password':'UniquePassword123!'}),201)
        org=reg['organization']['id'];ok(c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
        key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':42,'max_employees':25}))['key']
        ok(c.post('/api/auth/logout'));ok(c.post('/api/auth/login',json={'email':'admin-v54@example.com','password':'UniquePassword123!'}));c.headers['X-Organization-ID']=str(org)
        ok(c.post('/api/v5/subscription/redeem',json={'key':key}))
        ranch=ok(c.post('/api/v5/ranches',json={'name':'Ranch One'}))['id']
        project=ok(c.post('/api/v5/projects',json={'name':'Fattening','ranch_id':ranch}),201)['id']
        batch=ok(c.post('/api/v5/batches',json={'name':'Batch A','project_id':project,'capacity':2}))['id']
        animal=ok(c.post('/api/v5/animals',json={'tag':'GH-54-1','batch_id':batch,'purchase_cost':85000,'supplier_name':'Supplier A'}),201)['id']
        finance=ok(c.get('/api/v5/finance'))['items']
        assert len([x for x in finance if x['source']=='animal_purchase' and x['amount']==85000])==1
        assert ('Animal procurement' in ok(c.get('/api/v5/finance/categories'))['cost_categories'])
        item=ok(c.post('/api/v5/stock/items',json={'name':'Starter ration','category':'feed','unit':'kg'}),201)['id']
        assert ok(c.get('/api/v5/routine/options'))['feeds']==[]
        assert c.post('/api/v5/stock/receive',json={'item_id':item,'quantity':0,'total_cost':1,'reference':'NO-ZERO-STOCK'}).status_code==422
        receipt=ok(c.post('/api/v5/stock/receive',json={'item_id':item,'quantity':20,'total_cost':30000,
           'transport_cost':5000,'supplier_name':'Feed supplier','reference':'RECEIPT-V54-01'}),201)
        receipt_id=receipt['id']
        edited=ok(c.patch(f'/api/v5/stock/receipts/{receipt_id}',json={'reason':'Wrong supplier name', 'supplier_name':'Correct supplier'}))
        assert 'corrected' in edited['message']
        financial_edit=ok(c.patch(f'/api/v5/stock/receipts/{receipt_id}',json={'reason':'Correct freight charge', 'transport_cost':7500}))
        assert financial_edit['financial_recalculated']
        assert any(x['amount']==37500 and x['source']=='stock_receipt' for x in ok(c.get('/api/v5/finance'))['items'])
        ok(c.post('/api/v5/members',json={'name':'Worker','email':'worker-v54@example.com','password':'UniquePassword123!','role':'worker'}),201)
        membership=next(x for x in ok(c.get('/api/v5/members'))['items'] if x['email']=='worker-v54@example.com')
        for cat in ('feeding','watering'):
            ok(c.post('/api/v5/tasks',json={'category':cat,'title':cat+' morning', 'assigned_to':membership['user_id'],
                                             'batch_id':batch,'shift':'Morning','frequency':'daily'}),201)
        ok(c.post('/api/auth/logout'));ok(c.post('/api/auth/login',json={'email':'worker-v54@example.com','password':'UniquePassword123!'}))
        c.headers['X-Organization-ID']=str(org)
        before=ok(c.get('/api/v5/tasks/my'))
        assert before['counts']['due']>=2
        assert ok(c.get('/api/v5/routine/shift-status',params={'category':'feeding','batch_id':batch}))['next_shift']=='Morning'
        assert c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','extras':[{'item_id':item,'quantity_kg':0}],
                        'client_reference':'FEED-WRONG-001'}).status_code==422
        feeding=ok(c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','extras':[{'item_id':item,'quantity_kg':5}],
                         'client_reference':'FEED-SHIFT-54-001'}),201)
        assert feeding['tasks_completed']==1
        assert c.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','extras':[{'item_id':item,'quantity_kg':1}],
                       'client_reference':'FEED-SHIFT-54-002'}).status_code==409
        shifts=ok(c.get('/api/v5/routine/shift-status',params={'category':'feeding','batch_id':batch}))
        assert 'Morning' in shifts['completed'] and shifts['next_shift']=='Afternoon'
        assert len(ok(c.get('/api/v5/routine/options'))['feeds'])==1
        water=ok(c.post('/api/v5/routines',json={'category':'watering','batch_id':batch,'shift':'Morning',
                                                'client_reference':'WATER-54-001'}),201)
        assert water['quantity'] is None
        assert c.post('/api/v5/routines',json={'category':'watering','batch_id':batch,'shift':'Morning',
                                           'client_reference':'WATER-54-002'}).status_code==409
        board=ok(c.get('/api/v5/tasks/my'))
        assert board['counts']['completed']>=2
        assert c.get('/api/v5/finance').status_code==403
        assert c.patch(f'/api/v5/stock/receipts/{receipt_id}',json={'reason':'Unauthorized staff edit','supplier_name':'Hacked'}).status_code==403
        ok(c.post('/api/auth/logout'));ok(c.post('/api/auth/login',json={'email':'admin-v54@example.com','password':'UniquePassword123!'}))
        c.headers['X-Organization-ID']=str(org)
        assert c.patch(f'/api/v5/stock/receipts/{receipt_id}',json={'reason':'Correct cost late', 'total_cost':33000}).status_code==409
        corrected=ok(c.post('/api/v5/stock/corrections',json={'item_id':item,'direction':'adjustment_out',
               'quantity':2,'reference':'ADJ-V54-001','reason':'Count identified two spoiled kilos'}),201)
        assert corrected['balance']==13
        assert any(x['source']=='correction' for x in ok(c.get('/api/v5/stock/ledger'))['items'])
        assert c.post('/api/v5/stock/corrections',json={'item_id':item,'direction':'adjustment_out',
               'quantity':100,'reference':'ADJ-V54-002','reason':'Impossible negative physical balance'}).status_code==409
        assert c.post('/api/v5/finance',json={'kind':'cost','category':'Labor and wages','amount':0}).status_code==422
        ok(c.post('/api/v5/finance',json={'kind':'cost','category':'Labor and wages','amount':25000,'currency':'TZS'}),201)
        summary=ok(c.get('/api/v5/finance/cost-summary'))
        assert any(x['category']=='Labor and wages' and x['amount']==25000 for x in summary['categories'])
        assert c.get('/api/v5/reports/summary').status_code==200
        assert c.get('/api/v5/analytics/performance').status_code==200
