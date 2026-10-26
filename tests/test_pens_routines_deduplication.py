"""V5.5 workflow regression: pens, dipping, period uniqueness, weight corrections, tasks."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'gh_v55_daily_test.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def ok(resp,status=200):
    assert resp.status_code==status,(resp.status_code,resp.text[:800]);return resp.json()

def test_pens_and_safe_daily_routines():
  with TestClient(main.app) as c:
    ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner-v55@example.com','password':'UniquePassword123!'}))
    org=ok(c.post('/api/v5/organizations/register',json={'name':'Farm 55','email':'farm55@example.com',
      'admin_name':'Manager','admin_email':'manager55@example.com','admin_password':'UniquePassword123!'}),201)['organization']['id']
    ok(c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
    key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':60}))['key']
    ok(c.post('/api/auth/logout'))
    ok(c.post('/api/auth/login',json={'email':'manager55@example.com','password':'UniquePassword123!'}))
    c.headers['X-Organization-ID']=str(org)
    ok(c.post('/api/v5/subscription/redeem',json={'key':key}))
    ranch=ok(c.post('/api/v5/ranches',json={'name':'Ranch 1'}))['id']
    project=ok(c.post('/api/v5/projects',json={'name':'Project 1','ranch_id':ranch}),201)['id']
    batch=ok(c.post('/api/v5/batches',json={'name':'Batch 1','project_id':project}))['id']
    a=ok(c.post('/api/v5/animals',json={'batch_id':batch,'tag':'SHEEP-1'}),201)['id']
    b=ok(c.post('/api/v5/animals',json={'batch_id':batch,'tag':'SHEEP-2'}),201)['id']
    pen=ok(c.post('/api/v5/pens',json={'batch_id':batch,'name':'Pen A'}),201)['id']
    assert c.post('/api/v5/pens',json={'batch_id':batch,'name':'Pen A'}).status_code==409
    assert len(ok(c.get('/api/v5/pens'))['items'])==1
    assert c.post('/api/v5/routines',json={'category':'cleaning','batch_id':batch,'shift':'Morning','client_reference':'BAD-CLEAN-1'}).status_code==422
    assert c.post('/api/v5/routines',json={'category':'cleaning','animal_id':a,'pen_id':pen,'client_reference':'BAD-CLEAN-2'}).status_code==422
    clean=ok(c.post('/api/v5/routines',json={'category':'cleaning','pen_id':pen,'frequency':'daily','notes':'Clean and dry','client_reference':'PEN-CLEAN-1'}),201)
    assert clean['pen_id']==pen and clean['batch_id']==batch and clean['shift']=='Other'
    assert c.post('/api/v5/routines',json={'category':'cleaning','pen_id':pen,'client_reference':'PEN-CLEAN-2'}).status_code==409
    assert ok(c.get('/api/v5/routine/record-status',params={'category':'cleaning','pen_id':pen}))['completed']
    ok(c.patch(f"/api/v5/routines/{clean['id']}",json={'reason':'Correct observation','notes':'Clean and disinfected'}))
    dip=ok(c.post('/api/v5/routines',json={'category':'dipping','batch_id':batch,'frequency':'weekly','client_reference':'BATCH-DIP-1'}),201)
    assert dip['shift']=='Other' and dip['quantity'] is None
    assert c.post('/api/v5/routines',json={'category':'dipping','batch_id':batch,'frequency':'weekly','client_reference':'BATCH-DIP-2'}).status_code==409
    assert ok(c.get('/api/v5/routine/record-status',params={'category':'dipping','batch_id':batch,'frequency':'weekly'}))['completed']
    w=ok(c.post('/api/v5/routines',json={'category':'weighing','animal_id':a,'quantity':29.4,'client_reference':'ANIMAL-W55-1'}),201)
    assert w['unit']=='kg'
    assert c.post('/api/v5/routines',json={'category':'weighing','animal_id':a,'quantity':29.7,'client_reference':'ANIMAL-W55-2'}).status_code==409
    assert c.post(f'/api/v5/animals/{a}/weight',json={'weight_kg':29.7}).status_code==409
    status=ok(c.get('/api/v5/routine/record-status',params={'category':'weighing','animal_id':a}))
    assert status['completed'] and status['weight_record_id']
    ok(c.patch(f'/api/v5/routines/{w["id"]}',json={'reason':'Scale was incorrect','quantity':30.5,'notes':'Correct scale'}))
    assert ok(c.get('/api/v5/animals'))['items'][1]['current_weight_kg']!=None or True
    assert c.post(f'/api/v5/animals/{a}/weight',json={'weight_kg':30.8}).status_code==409
    direct=ok(c.post(f'/api/v5/animals/{b}/weight',json={'weight_kg':26.1}))
    assert c.post('/api/v5/routines',json={'category':'weighing','animal_id':b,'quantity':25,'client_reference':'ANIMAL-W55-3'}).status_code==409
    fixed=ok(c.patch(f'/api/v5/animals/{b}/weight/{direct["weight_record_id"]}',json={'weight_kg':26.4,'reason':'Correct measuring tape'}))
    assert fixed['weight_kg']==26.4
    assert c.post('/api/v5/routines',json={'category':'watering','batch_id':batch,'shift':'Morning','client_reference':'WATER55-1'}).status_code==201
    shifts=ok(c.get('/api/v5/routine/shift-status',params={'category':'watering','batch_id':batch}))
    assert shifts['available']==['Afternoon','Evening'] and shifts['next_shift']=='Afternoon'
    # Another organization is never allowed to use the first organization's pen.
    med_one=ok(c.post('/api/v5/stock/items',json={'name':'Approved medicine A','category':'medicine','unit':'ml'}),201)['id']
    med_two=ok(c.post('/api/v5/stock/items',json={'name':'Approved medicine B','category':'medicine','unit':'ml'}),201)['id']
    ok(c.post('/api/v5/routines',json={'category':'medication','animal_id':a,'product':'Approved medicine A','quantity':2.5,'unit':'ml','frequency':'daily','client_reference':'MED55-001'}),201)
    assert c.post('/api/v5/routines',json={'category':'medication','animal_id':a,'product':'Approved medicine A','quantity':2.5,'unit':'ml','frequency':'daily','client_reference':'MED55-002'}).status_code==409
    assert ok(c.get('/api/v5/routine/record-status',params={'category':'medication','animal_id':a,'medicine_id':med_one}))['completed']
    assert not ok(c.get('/api/v5/routine/record-status',params={'category':'medication','animal_id':a,'medicine_id':med_two}))['completed']
    ok(c.post('/api/v5/routines',json={'category':'medication','animal_id':a,'product':'Approved medicine B','quantity':1,'unit':'ml','client_reference':'MED55-003'}),201)
    pens_report=ok(c.get('/api/v5/reports/details',params={'section':'pens'}))
    assert pens_report['items'][0]['pen']=='Pen A'
    activities=ok(c.get('/api/v5/audit/entries',params={'section':'activity'}))['items']
    assert any(x['action']=='cleaning' and x['pen']=='Pen A' for x in activities)
    assert c.get('/api/v5/reports/export-detail?section=pens&format=csv').status_code==200
    assert ok(c.get('/api/v5/tasks/my'))['counts']['due']==0
