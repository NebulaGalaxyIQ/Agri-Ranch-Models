"""V5.6 sale accounting/tenant access/legacy migration regression."""
import os,tempfile
from pathlib import Path
p=Path(tempfile.gettempdir())/'gh_v56_sales.sqlite'
if p.exists():p.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(p)
from fastapi.testclient import TestClient
from sqlalchemy import text, inspect
import main
from database import engine

def ok(response, status=200):
    assert response.status_code==status, (response.status_code,response.text[:1200])
    return response.json()

def signup(c,name,email):
    org=ok(c.post('/api/v5/organizations/register',json={'name':name,'email':email.replace('@','-org@'),
        'admin_name':'Admin '+name,'admin_email':email,'admin_password':'UniquePassword123!'}),201)['organization']['id']
    ok(c.put(f'/api/v5/platform/organizations/{org}/verification',json={'status':'approved'}))
    key=ok(c.post('/api/v5/platform/license-keys',json={'organization_id':org,'duration_days':45}))['key']
    return org,key

def test_sales_and_profitability_with_strict_tenant_isolation():
  with TestClient(main.app) as c:
    ok(c.post('/api/auth/setup',json={'full_name':'Owner','email':'owner-v56@example.com','password':'UniquePassword123!'}))
    org,key=signup(c,'Farm 56','farm56@example.com')
    org2,key2=signup(c,'Farm 57','farm57@example.com')
    ok(c.post('/api/auth/logout'))
    ok(c.post('/api/auth/login',json={'email':'farm56@example.com','password':'UniquePassword123!'}))
    c.headers['X-Organization-ID']=str(org)
    ok(c.post('/api/v5/subscription/redeem',json={'key':key}))
    ranch=ok(c.post('/api/v5/ranches',json={'name':'North Ranch'}))['id']
    project=ok(c.post('/api/v5/projects',json={'name':'Sale Project','ranch_id':ranch}),201)['id']
    batch=ok(c.post('/api/v5/batches',json={'name':'Sale Batch','project_id':project,'capacity':1}))['id']
    animal=ok(c.post('/api/v5/animals',json={'batch_id':batch,'tag':'SALE-1',
        'purchase_cost':300000,'purchase_currency':'TZS','entry_weight_kg':30}),201)['id']
    assert ok(c.get('/api/v5/batches'))['items'][0]['animal_count']==1
    assert c.post('/api/v5/animals',json={'batch_id':batch,'tag':'FULL-2'}).status_code==409
    assert c.patch(f'/api/v5/animals/{animal}/status',json={'status':'sold'}).status_code==409
    assert c.post(f'/api/v5/animals/{animal}/sale',json={'buyer_name':'Buyer A','reason':'Market',
        'price_basis':'per_kg','price_per_unit':'10000'}).status_code==422
    sale=ok(c.post(f'/api/v5/animals/{animal}/sale',json={'buyer_name':'Buyer A','buyer_contact':'2557000001',
        'reason':'Market-ready','price_basis':'per_kg','price_per_unit':'10000',
        'weight_kg':'42.25','transport_cost':'2500','commission_cost':'1000',
        'sale_date':'2026-10-23','currency':'TZS','invoice_ref':'INV-56'}),201)
    assert sale['gross_amount']==422500 and sale['selling_expenses']==3500
    assert ok(c.get('/api/v5/batches'))['items'][0]['animal_count']==0
    assert ok(c.get('/api/v5/animals'))['items'][0]['status']=='sold'
    assert c.post(f'/api/v5/animals/{animal}/sale',json={'buyer_name':'Buyer B','reason':'Market',
        'price_basis':'per_head','price_per_unit':430000}).status_code==409
    finance=ok(c.get('/api/v5/finance'))['items']
    assert len(finance)==3, finance
    assert sorted((x['category'],x['amount']) for x in finance)==[
        ('Animal procurement',300000.0),('Livestock sales',422500.0),('Selling expenses',3500.0)]
    profitability=ok(c.get('/api/v5/finance/animal-profitability'))
    assert profitability['items'][0]['direct_contribution']==119000.0
    statement=ok(c.get('/api/v5/finance/profit-summary'))['by_currency']
    assert next(x for x in statement if x['currency']=='TZS')['recorded_period_result']==119000.0
    assert next(x for x in statement if x['currency']=='TZS')['sold_livestock_cogs']==300000.0
    assert c.post('/api/v5/finance',json={'kind':'revenue','category':'Livestock sales',
        'amount':422500,'currency':'TZS'}).status_code==422
    assert ok(c.get('/api/v5/reports/details',params={'section':'sales'}))['items'][0]['animal_tag']=='SALE-1'
    assert c.get('/api/v5/reports/export-detail?section=sales&format=pdf').status_code==200
    assert c.get('/api/v5/reports/export-detail?section=sales&format=csv').status_code==200
    assert ok(c.get('/api/v5/audit/entries',params={'section':'sales'}))['items'][0]['id']==sale['id']
    assert c.get('/api/v5/audit/export?section=sales').status_code==200
    # Completing a sale allows a new animal in a formerly full batch.
    animal2=ok(c.post('/api/v5/animals',json={'batch_id':batch,'tag':'REPLACEMENT-1'}),201)['id']
    assert c.post(f'/api/v5/sales/{sale["id"]}/void',json={'reason':'Buyer cancelled sale'}).status_code==409
    assert c.post(f'/api/v5/animals/{animal}/weight',json={'weight_kg':43}).status_code==409
    # Empty the batch before reverting the sale so occupancy remains valid.
    ok(c.patch(f'/api/v5/animals/{animal2}/status',json={'status':'removed'}))
    void=ok(c.post(f'/api/v5/sales/{sale["id"]}/void',json={'reason':'Buyer cancelled sale'}))
    assert void['status']=='voided'
    assert c.post(f'/api/v5/sales/{sale["id"]}/void',json={'reason':'Buyer cancelled sale'}).status_code==409
    assert ok(c.get('/api/v5/animals'))['items'][1]['status']=='active'
    assert ok(c.get('/api/v5/batches'))['items'][0]['animal_count']==1
    f=ok(c.get('/api/v5/finance'))['items']
    assert sum(e['amount'] for e in f if e['category']=='Livestock sales')==0
    assert sum(e['amount'] for e in f if e['category']=='Selling expenses')==0
    assert ok(c.get('/api/v5/finance/animal-profitability'))['items']==[]
    # A corrected real sale can be entered after void with a different sale id.
    again=ok(c.post(f'/api/v5/animals/{animal}/sale',json={'buyer_name':'Buyer C','reason':'Healthy stock sale',
        'price_basis':'per_head','price_per_unit':'450000','currency':'TZS'}),201)
    assert again['gross_amount']==450000
    ok(c.post('/api/v5/members',json={'name':'Field worker','email':'staff56@example.com',
        'password':'UniquePassword123!','role':'worker'}),201)
    ok(c.post('/api/auth/logout'))
    ok(c.post('/api/auth/login',json={'email':'staff56@example.com','password':'UniquePassword123!'}))
    c.headers['X-Organization-ID']=str(org)
    assert c.get('/api/v5/sales').status_code==403
    assert c.get('/api/v5/finance/animal-profitability').status_code==403
    assert c.post(f'/api/v5/animals/{animal}/sale',json={'buyer_name':'Other','reason':'Market',
        'price_basis':'per_head','price_per_unit':5000}).status_code==403
    ok(c.post('/api/auth/logout'))
    ok(c.post('/api/auth/login',json={'email':'farm57@example.com','password':'UniquePassword123!'}))
    c.headers['X-Organization-ID']=str(org2)
    ok(c.post('/api/v5/subscription/redeem',json={'key':key2}))
    assert ok(c.get('/api/v5/sales'))['items']==[]
    assert c.post(f'/api/v5/animals/{animal}/sale',json={'buyer_name':'Other','reason':'Sale',
        'price_basis':'per_head','price_per_unit':5000}).status_code==404
    assert c.post(f'/api/v5/sales/{again["id"]}/void',json={'reason':'Not my transaction'}).status_code==404


def test_legacy_pen_column_auto_upgrade():
    # Simulate a pre-V5.5 PostgreSQL schema without a pen foreign key, using an
    # isolated temporary database so production-mapped SQLite foreign keys remain safe.
    from sqlalchemy import create_engine
    import modules.organizations.schemas as v5_schema
    legacy=create_engine('sqlite:///'+str(Path(tempfile.gettempdir())/'gh_v56_old_tasks.sqlite'))
    with legacy.begin() as connection:
        connection.execute(text('DROP TABLE IF EXISTS v5_tasks'))
        connection.execute(text('CREATE TABLE v5_tasks (id INTEGER PRIMARY KEY, organization_id INTEGER, status VARCHAR(20))'))
    assert 'pen_id' not in {x['name'] for x in inspect(legacy).get_columns('v5_tasks')}
    real=v5_schema.engine
    try:
        v5_schema.engine=legacy
        v5_schema.upgrade_v5_schema()
        assert 'pen_id' in {x['name'] for x in inspect(legacy).get_columns('v5_tasks')}
        v5_schema.upgrade_v5_schema()
    finally:v5_schema.engine=real
