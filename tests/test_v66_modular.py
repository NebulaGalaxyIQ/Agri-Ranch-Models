"""V6.6 module integration; run separately from legacy SQLite bootstrap suites."""
import os,tempfile
from pathlib import Path
file=Path(tempfile.gettempdir())/'green_hills_v66_test.sqlite'
if file.exists():file.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(file)
from fastapi.testclient import TestClient
from main import app

def checked(r,code=200):
 assert r.status_code==code,(r.status_code,r.text[:1500]);return r.json()

def test_module_owner_offers_and_organization_animal_profile():
 with TestClient(app) as client:
  checked(client.post('/api/auth/setup',json={'full_name':'Owner','email':'owner66@example.org','password':'StrongPassword2026!'}))
  checked(client.post('/api/v6/platform/offers',json={'name':'Welcome promotion','code':'WELCOME_66','discount_pct':15,'bonus_days':7,'starts_on':'2026-10-01','ends_on':'2027-03-01'}),201)
  assert checked(client.get('/api/v6/platform/offers'))['items'][0]['code']=='WELCOME_66'
  org=checked(client.post('/api/v5/organizations/register',json={'name':'V66 Fattening Ranch','email':'ranch66@example.org','admin_name':'Administrator','admin_email':'admin66@example.org','admin_password':'StrongPassword2026!'}),201)['organization']['id']
  checked(client.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
  key=checked(client.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':45,'max_employees':25}))['key']
  checked(client.post('/api/auth/logout'))
  checked(client.post('/api/auth/login',json={'email':'admin66@example.org','password':'StrongPassword2026!'}))
  client.headers['X-Organization-ID']=str(org)
  checked(client.post('/api/v5/subscription/redeem',json={'key':key}))
  assert client.get('/api/v6/platform/offers').status_code==403
  ranch=checked(client.post('/api/v6/fattening/ranches',json={'name':'Main Site'}))['id']
  project=checked(client.post('/api/v6/fattening/projects',json={'name':'Beef Project','ranch_id':ranch}),201)['id']
  batch=checked(client.post('/api/v6/fattening/batches',json={'name':'Finishing Batch','project_id':project,'capacity':10}))['id']
  animal=checked(client.post('/api/v6/fattening/animals',json={'batch_id':batch,'tag':'FAT-100','entry_weight_kg':220,'arrival_date':'2026-10-10','purchase_cost':450000,'purchase_currency':'TZS'}),201)['id']
  profile=checked(client.get(f'/api/v6/fattening/animals/{animal}/profile'))
  assert profile['tag']=='FAT-100' and profile['entry_weight_kg']==220
  assert profile['feed_consumed_kg'] is None and profile['purchase_price']==450000
  updated=checked(client.put(f'/api/v6/fattening/animals/{animal}/proposed-price',json={'price_basis':'per_kg','amount':3000,'currency':'TZS'}))
  assert updated['proposed_sale']['estimated_value']==660000
  assert updated['proposed_sale']['partial'] is True
  assert len(checked(client.get('/api/v6/fattening/animals'))['items'])==1
  checked(client.post('/api/auth/logout'))
  checked(client.post('/api/auth/login',json={'email':'owner66@example.org','password':'StrongPassword2026!'}))
  assert checked(client.get('/api/v6/platform/offers'))['items'][0]['discount_pct']==15
  assert client.get(f'/api/v6/fattening/animals/{animal}/profile').status_code in (400,403)
