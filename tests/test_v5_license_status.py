"""Run separately: PYTHONPATH=backend python -m pytest -q tests/test_v5_license_status.py"""
import os
import tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'ranch_v5_license_status.sqlite'
if p.exists(): p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
import main

def test_license_status_and_custom_duration():
    with TestClient(main.app) as c:
        assert c.post('/api/auth/setup',json={'full_name':'Owner','email':'statusowner@example.com','password':'longPassword001!'}).status_code==200
        resp=c.post('/api/v5/organizations/register',json={'name':'Status Ranch','email':'ranch@example.com','admin_name':'Admin','admin_email':'statusadmin@example.com','admin_password':'longPassword001!'})
        assert resp.status_code==201,resp.text
        oid=resp.json()['organization']['id']
        def item():
            r=c.get('/api/v5/platform/organizations');assert r.status_code==200,r.text
            return next(x for x in r.json()['items'] if x['id']==oid)
        assert item()['status']=='pending'
        assert item()['latest_key_status']=='not_issued'
        assert c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':45,'max_employees':12}).status_code==409
        assert c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}).status_code==200
        assert item()['status']=='approved'
        key=c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':45,'max_employees':12})
        assert key.status_code==200,key.text
        assert key.json()['duration_days']==45
        assert item()['latest_key_status']=='issued'
        assert item()['pending_keys']==1
        history=c.get(f'/api/v5/platform/organizations/{oid}/license-keys').json()['items']
        assert history[0]['duration_days']==45 and history[0]['status']=='issued'
        c.post('/api/auth/logout')
        assert c.post('/api/auth/login',json={'email':'statusadmin@example.com','password':'longPassword001!'}).status_code==200
        c.headers['X-Organization-ID']=str(oid)
        redeem=c.post('/api/v5/subscription/redeem',json={'key':key.json()['key']})
        assert redeem.status_code==200,redeem.text
        assert redeem.json()['max_employees']==12
        c.post('/api/auth/logout')
        assert c.post('/api/auth/login',json={'email':'statusowner@example.com','password':'longPassword001!'}).status_code==200
        assert item()['latest_key_status']=='redeemed'
        assert item()['license_status']=='active'
        assert c.post('/api/v5/platform/license-keys/'+str(key.json()['id'])+'/revoke').status_code==409
        key2=c.post('/api/v5/platform/license-keys',json={'organization_id':oid,'duration_days':7,'max_employees':12}).json()
        assert item()['latest_key_status']=='issued'
        assert c.post('/api/v5/platform/license-keys/'+str(key2['id'])+'/revoke').status_code==200
        assert item()['latest_key_status']=='revoked'
