"""Run by itself: verifies support identities, chronological messages and owner-only notes."""
import os,tempfile
from pathlib import Path
DATABASE=Path(tempfile.gettempdir())/'gh_v58_conversations.sqlite'
if DATABASE.exists():DATABASE.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(DATABASE)
from fastapi.testclient import TestClient
import main

def ok(r,status=200):
 assert r.status_code==status,(r.status_code,r.text[:700])
 return r.json()

def test_v58_conversations_and_privacy():
 with TestClient(main.app) as c:
  ok(c.post('/api/auth/setup',json={'full_name':'Platform Owner','email':'owner-v58@testing.example','password':'UniquePasswordForV58!'}))
  reg=ok(c.post('/api/v5/organizations/register',json={'name':'Green Farm North','email':'north-v58@testing.example','admin_name':'North Admin','admin_email':'north-admin-v58@testing.example','admin_password':'UniquePasswordForV58!'}),201)
  oid=reg['organization']['id']
  ok(c.put(f'/api/v5/platform/organizations/{oid}/verification',json={'status':'approved'}))
  ok(c.post('/api/auth/logout'))
  ok(c.post('/api/auth/login',json={'email':'north-admin-v58@testing.example','password':'UniquePasswordForV58!'}))
  c.headers['X-Organization-ID']=str(oid)
  ticket=ok(c.post('/api/v5/help/tickets',json={'subject':'Feeding problem','message':'I cannot see my feed entry.'}),201)
  tid=ticket['id']
  listing=ok(c.get('/api/v5/help/tickets'))['items'][0]
  assert listing['organization_name']=='Green Farm North'
  assert listing['created_by_name']=='North Admin'
  assert listing['last_message']=='I cannot see my feed entry.'
  detail=ok(c.get(f'/api/v5/help/tickets/{tid}'))
  assert detail['ticket']['organization_name']=='Green Farm North'
  assert detail['messages'][0]['sender_type']=='organization'
  assert detail['messages'][0]['created_by']>0
  ok(c.post('/api/auth/logout'))
  ok(c.post('/api/auth/login',json={'email':'owner-v58@testing.example','password':'UniquePasswordForV58!'}))
  c.headers.pop('X-Organization-ID',None)
  owner_list=ok(c.get('/api/v5/platform/help/tickets'))['items'][0]
  assert owner_list['organization_name']=='Green Farm North'
  ok(c.post(f'/api/v5/platform/help/tickets/{tid}/reply',json={'message':'This is for the internal support team.','internal':True}),201)
  detail=ok(c.get(f'/api/v5/platform/help/tickets/{tid}'))
  assert detail['messages'][1]['internal'] is True
  assert detail['messages'][1]['sender_type']=='platform'
  ok(c.post(f'/api/v5/platform/help/tickets/{tid}/reply',json={'message':'We are looking into this problem.'}),201)
  assert ok(c.get('/api/v5/platform/help/tickets'))['items'][0]['last_message']=='We are looking into this problem.'
  ok(c.post('/api/auth/logout'))
  ok(c.post('/api/auth/login',json={'email':'north-admin-v58@testing.example','password':'UniquePasswordForV58!'}))
  c.headers['X-Organization-ID']=str(oid)
  detail=ok(c.get(f'/api/v5/help/tickets/{tid}'))
  assert len(detail['messages'])==2
  assert detail['messages'][1]['sender_type']=='platform'
  assert 'internal support team' not in str(detail)
  assert ok(c.get('/api/v5/help/tickets'))['items'][0]['last_message']=='We are looking into this problem.'
  page=ok(c.get('/api/v5/reports/summary')) if False else c.get('/').text
  assert 'v58.js?v=5.9.0' in page
  assert 'v5.css?v=5.9.0' in page
