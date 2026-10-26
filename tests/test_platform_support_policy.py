"""Current policy: ordinary organization members cannot create support tickets.
Platform owner retains historical support inbox and case-management endpoints.
"""
import os,tempfile
from pathlib import Path
_db=Path(tempfile.gettempdir())/'gh_modular_support_policy.sqlite'
if _db.exists():_db.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(_db)
from fastapi.testclient import TestClient
from main import app

def test_support_access_boundaries():
    with TestClient(app) as c:
        assert c.post('/api/auth/setup',json={'full_name':'Owner','email':'supportowner@test.example','password':'GoodPassword2026!'}).status_code==200
        resp=c.get('/api/v5/platform/help/tickets')
        assert resp.status_code==200 and resp.json()['items']==[]
        assert c.post('/api/v5/help/tickets',json={'subject':'Example','message':'Not offered here'}).status_code==410
        reg=c.post('/api/v5/organizations/register',json={'name':'Fattening Farm','email':'farm@test.example','admin_name':'Admin','admin_email':'admin@test.example','admin_password':'GoodPassword2026!'})
        assert reg.status_code==201
        org=reg.json()['organization']['id']
        assert c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}).status_code==200
        c.post('/api/auth/logout')
        c.post('/api/auth/login',json={'email':'admin@test.example','password':'GoodPassword2026!'})
        c.headers['X-Organization-ID']=str(org)
        assert c.post('/api/v5/help/tickets',json={'subject':'Example','message':'Disabled'}).status_code==410
        assert c.get('/api/v5/platform/help/tickets').status_code==403
