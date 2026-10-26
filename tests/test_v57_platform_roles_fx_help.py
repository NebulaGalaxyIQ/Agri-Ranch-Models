"""Run separately: creates an isolated SQLite DB and validates V5.7 key flows."""
import os, tempfile
from pathlib import Path
DB=Path(tempfile.gettempdir())/'gh_v57_platform_roles_fx_help.sqlite'
if DB.exists():DB.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(DB)
from fastapi.testclient import TestClient
import main

def good(r,status=200):
    assert r.status_code==status,(r.status_code,r.text[:700]);return r.json()

def test_owner_roles_stock_fx_help():
    with TestClient(main.app) as c:
        good(c.post('/api/auth/setup',json={'full_name':'Platform Owner','email':'owner-v57@example.org','password':'VeryUniquePassword123!'}))
        assert good(c.get('/api/auth/me'))['user']['role']=='platform_owner'
        assert good(c.get('/api/v5/platform/insights'))['organizations']==0
        assert c.get('/api/v5/help/tickets').status_code==403
        reg=good(c.post('/api/v5/organizations/register',json={'name':'Farm V57','email':'contact-v57@example.org','admin_name':'Farm Admin','admin_email':'admin-v57@example.org','admin_password':'VeryUniquePassword123!'}),201)
        org=reg['organization']['id']
        good(c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
        key=good(c.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':46,'max_employees':25}))['key']
        assert good(c.get('/api/v5/platform/insights'))['organizations']==1
        good(c.post('/api/auth/logout'))
        good(c.post('/api/auth/login',json={'email':'admin-v57@example.org','password':'VeryUniquePassword123!'}))
        c.headers['X-Organization-ID']=str(org)
        good(c.post('/api/v5/subscription/redeem',json={'key':key}))
        defs=good(c.get('/api/v5/roles'))
        assert 'movement' in defs['templates']
        role=good(c.post('/api/v5/roles',json={'name':'Pen Cleaner','permissions':['routine.read','routine.cleaning']}),201)
        assert c.post('/api/v5/roles',json={'name':'Super Admin','permissions':['*']}).status_code==422
        created=good(c.post('/api/v5/members',json={'name':'Cleaner','email':'cleaner-v57@example.org','password':'VeryUniquePassword123!','role':'cleaner'}),201)
        membership=next(m for m in good(c.get('/api/v5/members'))['items'] if m['email']=='cleaner-v57@example.org')
        good(c.put(f'/api/v5/members/{membership["id"]}/roles',json={'role_ids':[role['id']]}))
        assert role['id'] in good(c.get('/api/v5/roles'))['assignments'][str(membership['id'])]
        code=good(c.post(f'/api/v5/members/{membership["id"]}/password-reset'),201)['recovery_code']
        good(c.post('/api/v5/auth/password-reset/complete',json={'code':code,'new_password':'DifferentUniquePassword123!'}))
        assert c.post('/api/v5/auth/password-reset/complete',json={'code':code,'new_password':'CannotReusePassword123!'}).status_code==400
        t=good(c.post('/api/v5/help/tickets',json={'subject':'Help with feeding','message':'How do I correct a feeding record?'}),201)
        assert good(c.get('/api/v5/help/tickets'))['items'][0]['id']==t['id']
        attach=good(c.post(f'/api/v5/help/tickets/{t["id"]}/attachments',files={'file':('photo.png',b'\x89PNG\r\n\x1a\n'+b'example-data','image/png')}),201)
        assert good(c.get(f'/api/v5/help/tickets/{t["id"]}'))['attachments'][0]['id']==attach['id']
        assert c.get(f'/api/v5/help/tickets/{t["id"]}/attachments/{attach["id"]}').status_code==200
        assert c.post(f'/api/v5/help/tickets/{t["id"]}/attachments',files={'file':('bad.txt',b'script','text/plain')}).status_code==422
        assert c.post(f'/api/v5/help/tickets/{t["id"]}/reply',json={'message':'Hidden','internal':True}).status_code==403
        item=good(c.post('/api/v5/stock/items',json={'name':'Sunflower cake','category':'feed','unit':'kg','currency':'TZS'}),201)['id']
        assert c.post('/api/v5/stock/receive',json={'item_id':item,'quantity':100,'total_cost':100,'currency':'USD','reference':'RFX-INVALID'}).status_code==422
        first=good(c.post('/api/v5/stock/receive',json={'item_id':item,'quantity':100,'total_cost':100,
            'currency':'USD','exchange_rate':2500,'reference':'V57-USD-001'}),201)
        assert first['total_landed_cost']==250000 and first['base_currency']=='TZS'
        second=good(c.post('/api/v5/stock/receive',json={'item_id':item,'quantity':50,'total_cost':100000,
            'currency':'TZS','reference':'V57-TZS-001'}),201)
        assert second['landed_cost_per_unit']==2000
        balance=good(c.get('/api/v5/stock/status'))['items'][0]
        assert round(balance['unit_cost'],2)==round(350000/150,2)
        assert good(c.get('/api/v5/stock/ledger'))['items'][1]['purchase_currency']=='USD'
        # Physical expiry date is tracked independently of moving-average valuation.
        good(c.post('/api/v5/stock/receive',json={'item_id':item,'quantity':10,'total_cost':10000,
            'currency':'TZS','transaction_date':'2020-01-01','expiry_date':'2020-12-31',
            'reference':'V57-EXPIRED-001'}),201)
        after=good(c.get('/api/v5/stock/status'))['items'][0]
        assert after['balance']==160 and after['usable_balance']==150
        options=good(c.get('/api/v5/routine/options'))
        assert next(x for x in options['feeds'] if x['id']==item)['available_kg']==150
        good(c.post('/api/v5/stock/issue',json={'item_id':item,'quantity':150,
            'reference':'V57-USE-150','transaction_date':'2026-10-23'}),201)
        assert c.post('/api/v5/stock/issue',json={'item_id':item,'quantity':1,
            'reference':'V57-BLOCK-EXPIRED'}).status_code==409
        finance=good(c.get('/api/v5/finance'))['items']
        assert sum(r['amount'] for r in finance if r['source']=='stock_receipt')==360000
        good(c.post('/api/auth/logout'))
        good(c.post('/api/auth/login',json={'email':'cleaner-v57@example.org','password':'DifferentUniquePassword123!'}))
        assert 'routine.cleaning' in good(c.get('/api/v5/access'))['permissions']
        assert c.get('/api/v5/finance').status_code==403
        assert c.get('/api/v5/stock/status').status_code==403
        good(c.post('/api/auth/logout'))
        good(c.post('/api/auth/login',json={'email':'owner-v57@example.org','password':'VeryUniquePassword123!'}))
        c.headers.pop('X-Organization-ID',None)
        assert good(c.get('/api/v5/platform/help/tickets'))['items'][0]['id']==t['id']
        good(c.post(f'/api/v5/platform/help/tickets/{t["id"]}/reply',json={'message':'Select My Submissions and edit.'}),201)
        assert good(c.get(f'/api/v5/platform/organization-detail/{org}'))['counts']['support_tickets']==1
        assert good(c.get('/api/v5/platform/insights'))['features']
