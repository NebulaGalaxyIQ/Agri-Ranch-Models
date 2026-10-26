import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'ranch_v5_staff_reports.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def ok(r,code=200):
    assert r.status_code==code,(r.status_code,r.text)
    return r.json()

def test_staff_portal_and_detail_reports():
    with TestClient(main.app) as c:
        ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner-staff@example.com','password':'strongPassword123'}))
        org=ok(c.post('/api/v5/organizations/register',json={'name':'Sample Ranch','email':'sampleranch@example.com','admin_name':'Org Admin','admin_email':'org-staff@example.com','admin_password':'strongPassword123'}),201)['organization']
        oid=org['id'];ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
        key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':oid}))['key']
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'org-staff@example.com','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(oid)
        ok(c.post('/api/v5/subscription/redeem',json={'key':key}))
        ranch=ok(c.post('/api/v5/ranches',json={'name':'Staff Ranch'}))['id']
        project=ok(c.post('/api/v5/projects',json={'name':'Staff Project','ranch_id':ranch}),201)['id']
        b=ok(c.post('/api/v5/batches',json={'name':'Staff Batch','project_id':project,'capacity':3}))['id']
        ok(c.post('/api/v5/animals',json={'tag':'SHEEP1','batch_id':b,'species':'sheep'}),201)
        feed=ok(c.post('/api/v5/stock/items',json={'name':'Feed example','unit':'kg','category':'feed'}),201)['id']
        ok(c.post('/api/v5/stock/receive',json={'item_id':feed,'quantity':20,'total_cost':0,'reference':'RECEIPT-STAFF-01'}),201)
        ok(c.post('/api/v5/members',json={'name':'Staff Worker','email':'worker-staff@example.com','password':'strongPassword123','role':'feeding_recorder'}),201)
        for section in ['animals','batches','feeding','routines','inventory','finance','projects']:
            d=ok(c.get('/api/v5/reports/details?section='+section))
            assert d['section']==section
            assert c.get(f'/api/v5/reports/export-detail?section={section}&format=csv').status_code==200
        pdf=c.get('/api/v5/reports/export-detail?section=animals&format=pdf')
        assert pdf.status_code==200,(pdf.status_code,pdf.text[:200]);assert pdf.content.startswith(b'%PDF')
        ok(c.post('/api/auth/logout'))
        ok(c.post('/api/auth/login',json={'email':'worker-staff@example.com','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(oid)
        opts=ok(c.get('/api/v5/routine/options'))
        assert opts['feeds'][0]['name']=='Feed example'
        assert opts['animals'][0]['tag']=='SHEEP1'
        assert c.get('/api/v5/animals').status_code==403
        assert c.get('/api/v5/stock/items').status_code==403
        assert c.get('/api/v5/reports/summary').status_code==403
        assert c.get('/api/v5/projects').status_code==403
        result=ok(c.post('/api/v5/feeding/record',json={'batch_id':b,'shift':'Morning','extras':[{'item_id':feed,'quantity_kg':2}],'client_reference':'STAFF-RECORD-0001'}),201)
        assert result['quantity_kg']==2
        assert len(ok(c.get('/api/v5/routines'))['items'])==1
        assert c.post('/api/v5/feeding/record',json={'batch_id':b,'shift':'Morning','extras':[{'item_id':feed,'quantity_kg':2}],'client_reference':'STAFF-RECORD-0001'}).status_code==201
        assert c.post('/api/v5/animals',json={'batch_id':b,'tag':'ILLEGAL'}).status_code==403
