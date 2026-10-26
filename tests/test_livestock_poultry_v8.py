"""Isolated V8 smoke/regression: PYTHONPATH=backend pytest -q tests/test_livestock_poultry_v8.py"""
import os
import tempfile
from pathlib import Path

path = Path(tempfile.gettempdir()) / 'gh_livestock_v8_isolated.sqlite'
if path.exists(): path.unlink()
os.environ['DATABASE_URL'] = 'sqlite:///' + str(path)

from fastapi.testclient import TestClient
from main import app


def response(res, status=200):
    assert res.status_code == status, (res.status_code, res.text)
    return res.json()


def test_livestock_poultry_v8_end_to_end():
    base = '/api/v6/livestock'
    with TestClient(app) as c:
        response(c.post('/api/auth/setup', json={'full_name':'Owner','email':'owner_v8@example.org','password':'SecureOwnerPass123!'}))
        org = response(c.post('/api/v5/organizations/register', json={'name':'V8 Ranch','email':'ranch_v8@example.org','admin_name':'Manager','admin_email':'admin_v8@example.org','admin_password':'SecureAdminPass123!'}), 201)['organization']['id']
        response(c.put(f'/api/v5/platform/organizations/{org}/verification', json={'status':'approved'}))
        other_org = response(c.post('/api/v5/organizations/register', json={'name':'Other Company','email':'other_v8@example.org','admin_name':'Another','admin_email':'otheradmin_v8@example.org','admin_password':'OtherAdminPass123!'}), 201)['organization']['id']
        response(c.put(f'/api/v5/platform/organizations/{other_org}/verification', json={'status':'approved'}))
        key = response(c.post('/api/v5/platform/license-keys', json={'organization_id':org,'duration_days':60,'max_employees':25}))['key']
        response(c.post('/api/auth/logout'))
        response(c.post('/api/auth/login', json={'email':'admin_v8@example.org','password':'SecureAdminPass123!'}))
        c.headers['X-Organization-ID']=str(other_org)
        assert c.get(f'{base}/v8/workspace').status_code==403
        c.headers['X-Organization-ID']=str(org)
        response(c.post('/api/v5/subscription/redeem', json={'key':key}))
        ranch=response(c.post('/api/v5/ranches',json={'name':'V8 Ranch One'}))['id']
        ranch_other=response(c.post('/api/v5/ranches',json={'name':'Ranch Two'}))['id']
        flock=response(c.post(f'{base}/groups',json={'ranch_id':ranch,'name':'Layers','species':'chicken','head_count':20}),201)['item']['id']
        cattle=response(c.post(f'{base}/groups',json={'ranch_id':ranch,'name':'Dairy Herd','species':'cattle','head_count':5}),201)['item']['id']
        animal=response(c.post(f'{base}/animals',json={'ranch_id':ranch,'group_id':cattle,'species':'cattle','sex':'female'}),201)['item']['id']
        house=response(c.post(f'{base}/v8/houses',json={'ranch_id':ranch,'code':'COOP-1','name':'Main coop','house_type':'coop','species':'chicken','capacity':25}),201)['item']['id']
        assert c.post(f'{base}/v8/houses',json={'ranch_id':ranch,'code':'COOP-1','name':'Duplicate','capacity':50}).status_code==409
        small=response(c.post(f'{base}/v8/houses',json={'ranch_id':ranch,'code':'COOP-2','name':'Small coop','capacity':10}),201)['item']['id']
        wrong=response(c.post(f'{base}/v8/houses',json={'ranch_id':ranch_other,'code':'COOP-3','name':'Other ranch house','capacity':25}),201)['item']['id']
        assert c.post(f'{base}/v8/placements',json={'group_id':flock,'house_id':small}).status_code==409
        assert c.post(f'{base}/v8/placements',json={'group_id':flock,'house_id':wrong}).status_code==422
        response(c.post(f'{base}/v8/placements',json={'group_id':flock,'house_id':house}),201)
        assert c.post(f'{base}/v8/placements',json={'group_id':flock,'house_id':house}).status_code==409
        health=response(c.post(f'{base}/v8/health',json={'animal_id':animal,'action':'vaccination','status':'planned','performed_on':'2026-10-23','next_due':'2026-10-24'}),201)['item']['id']
        assert c.post(f'{base}/v8/health',json={'animal_id':animal,'action':'vaccination','status':'planned','cost':200}).status_code==422
        response(c.patch(f'{base}/v8/health/{health}/complete',json={'performed_on':'2026-10-24','cost':200,'currency':'TZS'}))
        assert c.patch(f'{base}/v8/health/{health}/complete',json={'performed_on':'2026-10-24','cost':200}).status_code==409
        response(c.post(f'{base}/v8/care',json={'group_id':flock,'activity':'feeding','shift':'morning','performed_on':'2026-10-24','quantity':12,'unit':'kg','expense':500,'currency':'TZS','reference':'CARE-001-X'}),201)
        assert c.post(f'{base}/v8/care',json={'group_id':flock,'activity':'feeding','shift':'morning','reference':'CARE-001-X'}).status_code==409
        breeding=response(c.post(f'{base}/v8/breeding',json={'animal_id':animal,'method':'ai','service_date':'2026-10-01','expected_date':'2027-07-01'}),201)['item']['id']
        response(c.patch(f'{base}/v8/breeding/{breeding}/outcome',json={'outcome':'confirmed'}))
        response(c.post(f'{base}/v8/weights',json={'animal_id':animal,'measured_on':'2026-10-01','weight_kg':300}),201)
        response(c.post(f'{base}/v8/weights',json={'animal_id':animal,'measured_on':'2026-10-11','weight_kg':315}),201)
        weights=response(c.get(f'{base}/v8/records/weights'))['items']
        assert weights[0]['gain_kg']==15 and weights[0]['adg_kg_day']==1.5
        incubation=response(c.post(f'{base}/v8/incubations',json={'group_id':flock,'batch_code':'OCT-SET-01','eggs_set':100,'set_on':'2026-10-01','expected_on':'2026-10-21'}),201)['item']['id']
        assert c.patch(f'{base}/v8/incubations/{incubation}/hatch',json={'hatched_on':'2026-10-23','eggs_hatched':101}).status_code==422
        hatch=response(c.patch(f'{base}/v8/incubations/{incubation}/hatch',json={'hatched_on':'2026-10-23','eggs_hatched':75}))
        assert hatch['hatch_rate_pct']==75
        assert c.patch(f'{base}/v8/incubations/{incubation}/hatch',json={'hatched_on':'2026-10-23','eggs_hatched':75}).status_code==409
        overview=response(c.get(f'{base}/v8/workspace'))
        assert overview['dashboard']['population']==25
        assert next(x for x in overview['houses'] if x['id']==house)['occupancy']==20
        assert overview['dashboard']['active_incubations']==0
        # Hatch record itself does not double-count flock. Only the birth event does.
        response(c.post(f'{base}/events',json={'group_id':flock,'action':'birth','quantity':75,'unit':'head','reference':'BIRTH-V8-001'}),201)
        response(c.post(f'{base}/events',json={'group_id':flock,'action':'egg_collection','quantity':40,'unit':'pieces','reference':'EGGS-V8-001'}),201)
        overview=response(c.get(f'{base}/v8/workspace'))
        assert overview['dashboard']['population']==100
        assert overview['dashboard']['over_capacity']==1
        lot=response(c.get(f'{base}/v8/records/products'))['items'][0]
        assert lot['available']==40
        response(c.post(f'{base}/products/sales',json={'lot_id':lot['id'],'quantity':10,'price_per_unit':300,'buyer':'Egg Purchaser','currency':'TZS'}),201)
        assert response(c.get(f'{base}/v8/records/products'))['items'][0]['available']==30
        finance=response(c.get('/api/v5/finance'))['items']
        assert len([x for x in finance if x['source']=='v8_livestock_health'])==1
        assert len([x for x in finance if x['source']=='v8_livestock_care'])==1
        assert response(c.get(f'{base}/v8/records/health'))['items'][0]['status']=='completed'
        assert c.get(f'{base}/v8/records/nonexistent').status_code==404
