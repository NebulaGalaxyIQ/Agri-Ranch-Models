"""Run isolated: PYTHONPATH=backend pytest -q tests/test_v61_contextual_agriculture.py"""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'ghv61_contextual.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
from main import app

def data(r,code=200):
 assert r.status_code==code,(r.status_code,r.text)
 return r.json()

def test_contextual_mixes_stock_crop_and_livestock_production():
 with TestClient(app) as c:
  data(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner61@example.org','password':'VerySecurePass123!'}))
  org=data(c.post('/api/v5/organizations/register',json={'name':'Mixed Farm 61','email':'farm61@example.org','admin_name':'Admin','admin_email':'admin61@example.org','admin_password':'AdminPassword123!'}),201)['organization']['id']
  data(c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
  key=data(c.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':50,'max_employees':25}))['key']
  data(c.post('/api/auth/logout'))
  data(c.post('/api/auth/login',json={'email':'admin61@example.org','password':'AdminPassword123!'}));c.headers['X-Organization-ID']=str(org)
  data(c.post('/api/v5/subscription/redeem',json={'key':key}))
  ranch=data(c.post('/api/v5/ranches',json={'name':'Ranch V61'}))['id']
  pr=data(c.post('/api/v5/projects',json={'ranch_id':ranch,'name':'Finishing 61','start_date':'2026-10-23'}),201)
  batch=data(c.post('/api/v5/batches',json={'project_id':pr['id'],'name':'Batch 61','capacity':5,'start_date':'2026-10-23'}))
  animal=data(c.post('/api/v5/animals',json={'batch_id':batch['id'],'species':'cattle','entry_weight_kg':260}),201)
  assert animal['tag'].startswith('AN-')
  f1=data(c.post('/api/v5/stock/items',json={'name':'Maize 61','unit':'kg','category':'feed'}),201)['id']
  f2=data(c.post('/api/v5/stock/items',json={'name':'Bran 61','unit':'kg','category':'feed'}),201)['id']
  assert c.post('/api/v6/feed/mixes/by-quantity',json={'name':'Bad Repeat','feed_type':'starter','lines':[{'item_id':f1,'quantity_kg':6},{'item_id':f1,'quantity_kg':1}]}).status_code==422
  mix=data(c.post('/api/v6/feed/mixes/by-quantity',json={'name':'Starter 61','feed_type':'starter','lines':[{'item_id':f1,'quantity_kg':80},{'item_id':f2,'quantity_kg':20}]}),201)
  assert mix['total_reference_kg']==100
  assert [x['percentage'] for x in mix['composition']]==[80,20]
  assert data(c.get('/api/v6/feed/mixes/references'))['items'][0]['total_reference_kg']==100
  data(c.post('/api/v5/feed/assignments',json={'ration_id':mix['id'],'batch_id':batch['id']}),201)
  recommendation=data(c.get(f'/api/v5/feed/recommendation?animal_id={animal["id"]}'))
  assert recommendation['ration_id']==mix['id']
  # One-step new-item Stock In and automatic reference generation.
  boots=data(c.post('/api/v5/stock/receive/new-item',json={'name':'Worker Boots 61','category':'boots','unit':'pairs','valuation_currency':'TZS','attributes':{'size':'43'},'receipt':{'item_id':0,'quantity':10,'total_cost':100000,'currency':'TZS'}}),201)
  assert boots['id']>0
  assert c.post('/api/v5/stock/receive/new-item',json={'name':'Wrong Feed Size','category':'feed','unit':'kg','attributes':{'size':'43'},'receipt':{'item_id':0,'quantity':100,'total_cost':20000,'currency':'TZS'}}).status_code==422
  field=data(c.post('/api/v6/crops/fields',json={'ranch_id':ranch,'name':'Field 61','area_ha':4}),201)['item']
  cycle=data(c.post('/api/v6/crops/cycles',json={'field_id':field['id'],'crop':'Tomatoes','planted_area_ha':2,'planting_date':'2026-10-23'}),201)['item']
  inp=data(c.post('/api/v6/crops/inputs',json={'cycle_id':cycle['id'],'category':'seed','description':'Seed bags','quantity':4,'unit':'bags','unit_cost':5000,'labor_cost':2000,'transport_cost':1000,'currency':'TZS'}),201)['item']
  assert inp['total_cost']==23000
  data(c.post('/api/v6/crops/records',json={'cycle_id':cycle['id'],'action':'harvest','quantity':100,'unit':'kg'}),201)
  data(c.post('/api/v6/crops/sales',json={'cycle_id':cycle['id'],'buyer':'Buyer 61','quantity_kg':50,'price_per_kg':1000,'currency':'TZS'}),201)
  report=data(c.get('/api/v6/crops/profitability'))['items'][0]
  assert report['unsold_kg']==50
  assert report['currencies'][0]['contribution']==27000
  project=data(c.post('/api/v6/livestock/projects',json={'ranch_id':ranch,'name':'Egg Operation 61'}),201)['item']
  flock=data(c.post('/api/v6/livestock/groups',json={'ranch_id':ranch,'name':'Flock 61','species':'chicken','head_count':20}),201)['item']
  data(c.post(f'/api/v6/livestock/projects/{project["id"]}/groups',json={'group_id':flock['id']}),201)
  data(c.post(f'/api/v6/livestock/projects/{project["id"]}/costs',json={'category':'labor','description':'Collect eggs','amount':2500}),201)
  data(c.post('/api/v6/livestock/events',json={'group_id':flock['id'],'action':'egg_collection','quantity':60,'unit':'pieces','reference':'EGG-RECEIPT-61'}),201)
  lots=data(c.get('/api/v6/livestock/products'))['items']
  assert lots[0]['available']==60
  data(c.post('/api/v6/livestock/products/sales',json={'lot_id':lots[0]['id'],'quantity':40,'price_per_unit':300,'buyer':'Egg Buyer 61','currency':'TZS'}),201)
  assert c.post('/api/v6/livestock/products/sales',json={'lot_id':lots[0]['id'],'quantity':21,'price_per_unit':300,'buyer':'Egg Buyer 61'}).status_code==409
  assert data(c.get('/api/v6/livestock/products'))['items'][0]['available']==20
  perf=data(c.get('/api/v6/livestock/project-performance'))['items'][0]
  assert perf['currencies'][0]['product_revenue']==12000
  finance=data(c.get('/api/v5/finance'))['items']
  assert any(x['source']=='v61_crop_input' for x in finance)
  assert any(x['source']=='v61_livestock_product_sale' for x in finance)
