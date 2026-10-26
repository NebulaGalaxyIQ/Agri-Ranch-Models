"""Smoke and isolation tests. Run: cd backend && pytest ../tests/test_v5.py -q"""
import os
import tempfile
from pathlib import Path

path=Path(tempfile.gettempdir())/'ranch_v5_isolation_test.sqlite'
if path.exists():path.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(path)
from fastapi.testclient import TestClient
import main

def assert_ok(r,code=200):
    assert r.status_code==code,(r.status_code,r.text)
    return r.json()

def test_full_workflow():
    with TestClient(main.app) as c:
        assert_ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner@tests.example','password':'ownerPassword123'}))
        orgs=[];keys=[]
        for i in (1,2):
            org=assert_ok(c.post('/api/v5/organizations/register',json={'name':f'Ranch {i}','email':f'ranch{i}@tests.example','admin_name':'Manager','admin_email':f'admin{i}@tests.example','admin_password':'strongPassword123'}),201)['organization'];orgs.append(org['id'])
            assert_ok(c.put(f'/api/v5/platform/organizations/{org["id"]}/verification',json={'status':'approved'}))
            keys.append(assert_ok(c.post('/api/v5/platform/license-keys',json={'organization_id':org['id'],'duration_days':30,'max_employees':25}))['key'])
        assert_ok(c.post('/api/auth/logout'))
        assert_ok(c.post('/api/auth/login',json={'email':'admin1@tests.example','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(orgs[0])
        assert_ok(c.post('/api/v5/subscription/redeem',json={'key':keys[0]}))
        assert_ok(c.post('/api/v5/ranches',json={'name':'First Ranch'}))
        assert c.get('/api/animals').status_code==403
        assert c.get('/api/v5/ranches',headers={'X-Organization-ID':str(orgs[1])}).status_code==403
        assert c.post('/api/v5/subscription/redeem',json={'key':keys[0]}).status_code==400
        assert c.post('/api/v5/subscription/redeem',json={'key':keys[1]}).status_code==400
        assert_ok(c.post('/api/auth/logout'))
        assert_ok(c.post('/api/auth/login',json={'email':'admin2@tests.example','password':'strongPassword123'}))
        c.headers['X-Organization-ID']=str(orgs[1])
        assert_ok(c.post('/api/v5/subscription/redeem',json={'key':keys[1]}))
        assert_ok(c.post('/api/v5/ranches',json={'name':'Second Ranch'}))
        assert assert_ok(c.get('/api/v5/ranches'))['items'][0]['name']=='Second Ranch'
        assert c.get('/api/v5/ranches',headers={'X-Organization-ID':str(orgs[0])}).status_code==403
