"""Dedicated V6 API tests (run individually; old suite modules use different temp databases)."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'green_hills_v6_integration.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
from main import app

def ok(response,code=200):
 assert response.status_code==code,(response.status_code,response.text)
 return response.json()

def test_v6_domains_branding_permissions_and_tenant_separation():
 with TestClient(app) as c:
  ok(c.post('/api/auth/setup',json={'full_name':'Platform Owner','email':'v6owner@example.org','password':'OwnerPassword123!'}))
  orgs=[];keys=[]
  for n in [1,2]:
   created=ok(c.post('/api/v5/organizations/register',json={'name':f'V6 Company {n}','email':f'v6org{n}@example.org','admin_name':'Admin','admin_email':f'admin{n}@example.org','admin_password':'AdminPassword123!'}),201)
   oid=created['organization']['id'];orgs.append(oid)
   ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
   key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':60,'max_employees':25}));keys.append(key['key'])
  assert ok(c.get('/api/v6/public/branding'))['background_url'] is None
  # These routes cannot be used by organization members.
  assert c.put(f'/api/v6/platform/organizations/{orgs[0]}/modules/crops',json={'enabled':False}).status_code==200
  assert c.put(f'/api/v6/platform/organizations/{orgs[0]}/modules/crops',json={'enabled':True}).status_code==200
  assert c.get('/api/v6/crops/fields',headers={'X-Organization-ID':str(orgs[0])}).status_code==403
  ok(c.post('/api/auth/logout'))
  ok(c.post('/api/auth/login',json={'email':'admin1@example.org','password':'AdminPassword123!'}))
  h={'X-Organization-ID':str(orgs[0])};c.headers.update(h)
  ok(c.post('/api/v5/subscription/redeem',json={'key':keys[0]}))
  ranch=ok(c.post('/api/v5/ranches',json={'name':'Kijani Ranch'}))
  rid=ranch['id'];fields=ok(c.post('/api/v6/crops/fields',json={'ranch_id':rid,'name':'Field A','area_ha':5.0}),201)
  fid=fields['item']['id']
  assert c.post('/api/v6/crops/cycles',json={'field_id':fid,'crop':'Maize','planted_area_ha':6,'planting_date':'2026-10-23'}).status_code==422
  cycle=ok(c.post('/api/v6/crops/cycles',json={'field_id':fid,'crop':'Maize','planted_area_ha':3.5,'planting_date':'2026-10-23'}),201)['item']
  ok(c.post('/api/v6/crops/records',json={'cycle_id':cycle['id'],'action':'irrigation','performed_on':'2026-10-23','cost':23000,'currency':'TZS'}),201)
  ok(c.post('/api/v6/crops/records',json={'cycle_id':cycle['id'],'action':'harvest','performed_on':'2026-10-23','quantity':1000,'unit':'kg'}),201)
  assert c.post('/api/v6/crops/sales',json={'cycle_id':cycle['id'],'buyer':'Maize Buyer','quantity_kg':1200,'price_per_kg':700}).status_code==409
  ok(c.post('/api/v6/crops/sales',json={'cycle_id':cycle['id'],'buyer':'Maize Buyer','quantity_kg':300,'price_per_kg':700}),201)
  herd=ok(c.post('/api/v6/livestock/groups',json={'ranch_id':rid,'name':'Free-range ducks','species':'duck','head_count':30}),201)['item']
  assert herd['head_count']==30
  ok(c.post('/api/v6/livestock/events',json={'group_id':herd['id'],'action':'egg_collection','quantity':28,'unit':'eggs','reference':'EGGS-00001'}),201)
  ok(c.post('/api/v6/livestock/sales',json={'group_id':herd['id'],'buyer':'Bird Buyer','reason':'Commercial sale','price_basis':'per_head','price_per_unit':8000,'quantity':5}),201)
  animal=ok(c.post('/api/v6/livestock/animals',json={'ranch_id':rid,'group_id':herd['id'],'tag':'DUCK-001','species':'duck'}),201)
  assert c.post('/api/v6/livestock/animals',json={'ranch_id':rid,'group_id':herd['id'],'tag':'DUCK-001','species':'duck'}).status_code==409
  area=ok(c.post('/api/v6/gardening/areas',json={'ranch_id':rid,'name':'Office flowers','area_m2':400}),201)['item']
  ok(c.post('/api/v6/gardening/records',json={'area_id':area['id'],'action':'watering'}),201)
  assert c.post('/api/v6/gardening/records',json={'area_id':area['id'],'action':'watering'}).status_code==409
  machine=ok(c.post('/api/v6/machinery/assets',json={'ranch_id':rid,'asset_code':'TRACTOR-001','name':'John Deere tractor'}),201)['item']
  assert c.post('/api/v6/machinery/records',json={'machine_id':machine['id'],'action':'operation'}).status_code==422
  ok(c.post('/api/v6/machinery/records',json={'machine_id':machine['id'],'action':'maintenance','expense':3000,'currency':'TZS'}),201)
  finance=ok(c.get('/api/v5/finance'))['items'];assert any(r['source']=='v6_crop_record' for r in finance)
  assert any(r['source']=='v6_machine_record' for r in finance)
  assert any(r['source']=='v6_crop_sale' for r in finance)
  assert any(r['source']=='v6_livestock_sale' for r in finance)
  assert len(ok(c.get('/api/v6/crops/fields'))['items'])==1
  assert c.post('/api/v6/crops/fields',json={'ranch_id':99999,'name':'Foreign','area_ha':1}).status_code==404
  from PIL import Image
  from io import BytesIO
  im=Image.new('RGB',(60,45),(22,111,45));b=BytesIO();im.save(b,format='PNG')
  ok(c.post('/api/v6/organizations/me/logo',files={'file':('logo.png',b.getvalue(),'image/png')}))
  assert c.get('/api/v6/organizations/me/logo').status_code==200
  ok(c.post('/api/auth/logout'))
  ok(c.post('/api/auth/login',json={'email':'admin2@example.org','password':'AdminPassword123!'}))
  c.headers['X-Organization-ID']=str(orgs[1]);ok(c.post('/api/v5/subscription/redeem',json={'key':keys[1]}))
  assert ok(c.get('/api/v6/crops/fields'))['items']==[]
  assert c.post('/api/v6/crops/cycles',json={'field_id':fid,'crop':'Sunflower','planted_area_ha':1,'planting_date':'2026-10-23'}).status_code==404
  assert c.post('/api/v6/livestock/animals',json={'ranch_id':rid,'tag':'CROSS','species':'cow'}).status_code==404
  assert c.get('/api/v6/organizations/me/logo').status_code==404
