"""V6.2: one assigned batch mix, staff safe selection, submodule layout.
Run alone: PYTHONPATH=backend pytest -q tests/test_v62_module_feeding_policy.py
"""
import os,tempfile
from pathlib import Path
DATABASE=Path(tempfile.gettempdir())/'ranch_v62_batch_mix_policy.sqlite'
if DATABASE.exists():DATABASE.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(DATABASE)
from fastapi.testclient import TestClient
from main import app


def response(r,expected=200):
    assert r.status_code==expected,(r.status_code,r.text[:2000])
    return r.json()


def test_only_assigned_mix_is_selectable_and_accepted_for_batch_and_animals():
 with TestClient(app) as client:
  response(client.post('/api/auth/setup',json={'full_name':'Owner','email':'v62-owner@example.org','password':'StrongPassword2026!'}))
  org=response(client.post('/api/v5/organizations/register',json={'name':'V62 Test Ranch','email':'v62-ranch@example.org',
     'admin_name':'Ranch Manager','admin_email':'v62-admin@example.org','admin_password':'StrongPassword2026!'}),201)['organization']['id']
  response(client.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
  key=response(client.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':50,'max_employees':25}))['key']
  response(client.post('/api/auth/logout'))
  response(client.post('/api/auth/login',json={'email':'v62-admin@example.org','password':'StrongPassword2026!'}))
  client.headers['X-Organization-ID']=str(org)
  response(client.post('/api/v5/subscription/redeem',json={'key':key}))
  ranch=response(client.post('/api/v5/ranches',json={'name':'V62 Main Ranch'}))['id']
  project=response(client.post('/api/v5/projects',json={'name':'Finishing Project','ranch_id':ranch}),201)['id']
  batch=response(client.post('/api/v5/batches',json={'name':'Starter Batch','project_id':project,'capacity':10}))['id']
  animal=response(client.post('/api/v5/animals',json={'batch_id':batch,'tag':'ANIMAL-V62'}),201)['id']
  maize=response(client.post('/api/v5/stock/items',json={'name':'Maize V62','category':'feed','unit':'kg'}),201)['id']
  bran=response(client.post('/api/v5/stock/items',json={'name':'Bran V62','category':'feed','unit':'kg'}),201)['id']
  response(client.post('/api/v5/stock/receive',json={'item_id':maize,'quantity':100,'total_cost':10000,'reference':'V62-MAIZE'}),201)
  response(client.post('/api/v5/stock/receive',json={'item_id':bran,'quantity':100,'total_cost':10000,'reference':'V62-BRAN'}),201)
  starter=response(client.post('/api/v6/feed/mixes/by-quantity',json={'name':'Starter Mix V62','feed_type':'starter','lines':[
   {'item_id':maize,'quantity_kg':80},{'item_id':bran,'quantity_kg':20}]}),201)
  finisher=response(client.post('/api/v6/feed/mixes/by-quantity',json={'name':'Finisher Mix V62','feed_type':'finisher','lines':[
   {'item_id':maize,'quantity_kg':25},{'item_id':bran,'quantity_kg':75}]}),201)
  # Obtain each finished-product stock item, then physically receive the mixes.
  stock1=starter['finished_item_id'];stock2=finisher['finished_item_id']
  response(client.post('/api/v5/stock/receive',json={'item_id':stock1,'quantity':80,'total_cost':30000,'reference':'V62-STARTER'}),201)
  response(client.post('/api/v5/stock/receive',json={'item_id':stock2,'quantity':50,'total_cost':40000,'reference':'V62-FINISHER'}),201)
  response(client.post('/api/v5/feed/assignments',json={'ration_id':starter['id'],'batch_id':batch}),201)
  rec=response(client.get('/api/v5/feed/recommendation',params={'animal_id':animal,'shift':'Afternoon'}))
  assert rec['ration_id']==starter['id'] and rec['assigned_item_id']==stock1
  assert rec['restrict_to_assigned_mix'] is True
  bad=client.post('/api/v5/feeding/record',json={'animal_id':animal,'shift':'Afternoon','extras':[{'item_id':maize,'quantity_kg':1}], 'client_reference':'V62-BAD-FEED-001'})
  assert bad.status_code==409,bad.text
  wrong_mix=client.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','extras':[{'item_id':stock2,'quantity_kg':1}], 'client_reference':'V62-WRONG-MIX-001'})
  assert wrong_mix.status_code==409,wrong_mix.text
  forbidden_combination=client.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','ration_quantity_kg':1,'extras':[{'item_id':stock1,'quantity_kg':1}], 'client_reference':'V62-DOUBLE-001'})
  assert forbidden_combination.status_code==422
  recorded=response(client.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','extras':[{'item_id':stock1,'quantity_kg':5}], 'client_reference':'V62-OK-BATCH-001'}),201)
  assert recorded['stock_deducted'] and recorded['quantity_kg']==5
  recorded_animal=response(client.post('/api/v5/feeding/record',json={'animal_id':animal,'shift':'Afternoon','extras':[{'item_id':stock1,'quantity_kg':2}], 'client_reference':'V62-OK-ANIMAL-001'}),201)
  assert recorded_animal['quantity_kg']==2
  assert client.post('/api/v5/feeding/record',json={'batch_id':batch,'shift':'Morning','extras':[{'item_id':stock1,'quantity_kg':1}],'client_reference':'V62-DUP-SHIFT-001'}).status_code==409
  response(client.post('/api/v5/feed/assignments',json={'ration_id':finisher['id'],'batch_id':batch}),201)
  assignments=response(client.get('/api/v5/feed/assignments'))['items']
  assert len([x for x in assignments if x['active'] and x['batch_id']==batch])==1
  rec2=response(client.get('/api/v5/feed/recommendation',params={'animal_id':animal}))
  assert rec2['ration_id']==finisher['id'] and rec2['assigned_item_id']==stock2
  assert client.post('/api/v5/feeding/record',json={'animal_id':animal,'shift':'Evening','extras':[{'item_id':stock1,'quantity_kg':1}],'client_reference':'V62-OLD-MIX-001'}).status_code==409


def test_submodule_pages_replace_horizontal_tab_navigation():
 front=Path(__file__).resolve().parents[1]/'frontend'
 for name in ['fattening','crops','livestock','gardening','machinery','inventory']:
  source=(front/'pages'/name/'index.js').read_text()
  assert 'submoduleDirectory(' in source and 'submoduleWorkspace(' in source,name
  assert '<div class="tabs"' not in source and 'fattening-tabs' not in source,name
 assert "title:'Animal Fattening'" in (front/'shared'/'app.js').read_text()
 assert (front/'shared'/'styles'/'submodules.css').exists()
