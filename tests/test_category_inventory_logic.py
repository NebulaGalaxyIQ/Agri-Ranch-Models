"""V5.10: Inventory category contracts and retired organization Help Center."""
import os, tempfile
from pathlib import Path
path=Path(tempfile.gettempdir())/'gh_v510_inventory_test.sqlite'
if path.exists():path.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(path)
from fastapi.testclient import TestClient
import main

def ok(r, status=200):
 assert r.status_code==status,(r.status_code,r.text[:950]);return r.json()

def test_item_shapes_and_removed_help_center():
 with TestClient(main.app) as c:
  ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner510@company.org','password':'VerySecure#2026'}))
  r=ok(c.post('/api/v5/organizations/register',json={'name':'A Ranch Company','email':'office510@company.org','admin_name':'Admin','admin_email':'admin510@company.org','admin_password':'VerySecure#2026'}),201)
  org=r['organization']['id'];ok(c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
  key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':30,'max_employees':25}))['key']
  ok(c.post('/api/auth/logout'));ok(c.post('/api/auth/login',json={'email':'admin510@company.org','password':'VerySecure#2026'}))
  c.headers['X-Organization-ID']=str(org);ok(c.post('/api/v5/subscription/redeem',json={'key':key}))
  def make(name,cat,attrs,ref):
   return {'name':name,'category':cat,'unit':'pieces','valuation_currency':'TZS','attributes':attrs,
           'receipt':{'item_id':0,'quantity':2,'total_cost':100,'reference':ref,'currency':'TZS'}}
  equip=make('Tractor engine','equipment',{'manufacturer':'Machinery Inc','specification':'Model X'},'510-EQ-01')
  saved=ok(c.post('/api/v5/stock/receive/new-item',json=equip),201)
  assert saved['balance']==2
  equip['name']='Bad tractor';equip['receipt']['reference']='510-EQ-02';equip['attributes']['strength_or_concentration']='50 mg/ml'
  assert c.post('/api/v5/stock/receive/new-item',json=equip).status_code==422
  equip['attributes']={'size':'Size M'}
  assert c.post('/api/v5/stock/receive/new-item',json=equip).status_code==422
  assert c.patch(f'/api/v5/stock/items/{saved["id"]}/details',json={'reason':'Attempt irrelevant medical dosage','attributes':{'strength_or_concentration':'40%'}}).status_code==422
  boots=make('Safety boots','boots',{'size':'42','specification':'Steel toe'},'510-BT-01')
  ok(c.post('/api/v5/stock/receive/new-item',json=boots),201)
  boots['name']='Bad boots';boots['receipt']['reference']='510-BT-02';boots['attributes']['strength_or_concentration']='25%'
  assert c.post('/api/v5/stock/receive/new-item',json=boots).status_code==422
  herb=make('Herbicide','herbicide',{'strength_or_concentration':'25%', 'storage_instructions':'Locked cabinet'},'510-HB-01')
  ok(c.post('/api/v5/stock/receive/new-item',json=herb),201)
  med=make('Veterinary vaccine','medicine',{'strength_or_concentration':'50 IU/ml','specification':'10 ml vial'},'510-MD-01')
  assert c.post('/api/v5/stock/receive/new-item',json=med).status_code==422
  med['receipt']['expiry_date']='2027-12-31'
  ok(c.post('/api/v5/stock/receive/new-item',json=med),201)
  assert c.get('/api/v5/help/tickets').status_code==410
  assert c.post('/api/v5/help/tickets',json={'subject':'Not here','message':'Removed from organization portal'}).status_code==410
