"""Cape Ranch — modular API entrypoint.

Each operational feature owns its ORM and route implementation in backend/modules.
Only application wiring, lifecycle, middleware and static delivery live here.
Historical SQL table names are intentionally unchanged to preserve existing data.
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import init_db, seed_defaults
from auth import auth_router, user_router

from modules.organizations.router import router as organizations_router
from modules.fattening.router import fattening_routers
from modules.inventory.service import router as stock_audit_router
from modules.inventory.router import router as inventory_router
from modules.inventory.router import operations_router as inventory_operations_router
from modules.finance.router import operations_router as finance_operations_router
from modules.inventory import models as inventory_models
from modules.employees.service import router as tasks_router
from modules.employees.router import router as employee_recovery_router
from modules.employees.router import operations_router as employees_operations_router
from modules.reports.service import router as insights_router
from modules.reports.router import extra_router as operations_export_router
from modules.reports.router import operations_router as reports_operations_router
from modules.reports.v10_router import router as reports_v10_router
from modules.platform_admin.service import router as platform_router
from modules.platform_admin.router import router as branding_router
from modules.platform_admin.models import FeatureUsage
from modules.crops.models import router as module_settings_router
from modules.crops.router import v9_router as crops_v9_router
from modules.crops.router import basic_router as crops_router, extra_router as crop_input_router, sales_router as crop_sales_router
from modules.crops.service import router as extended_shared_router
from modules.livestock.router import basic_router as livestock_router, extra_router as livestock_project_router
from modules.livestock.service import router as livestock_production_router
from modules.gardening.router import router as gardening_router
from modules.machinery.router import router as machinery_router
from modules.subscriptions.router import router as subscription_offers_router
from modules.cape_access import models as cape_subscription_models
from modules.cape_access.router import router as cape_access_router
from modules.help_center.router import router as support_router

ROOT=Path(__file__).resolve().parents[1]
FRONTEND=ROOT/'frontend'
APP_NAME=os.getenv('APP_NAME','Cape Ranch')

@asynccontextmanager
async def lifespan(app:FastAPI):
    init_db()
    # Compatibility schema upgrade for existing live PostgreSQL installations.
    # Keep database table identifiers unchanged; perform backup before applying.
    from modules.organizations.schemas import upgrade_v5_schema,migrate_bootstrap_owner
    upgrade_v5_schema()
    migrate_bootstrap_owner()
    seed_defaults()
    yield

app=FastAPI(title=APP_NAME,version='7.0.0',lifespan=lifespan)
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://127.0.0.1:8000,http://localhost:8000').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

for domain_router in (
    auth_router,user_router,organizations_router,*fattening_routers,stock_audit_router,inventory_router,tasks_router,employee_recovery_router,
    insights_router,operations_export_router,reports_v10_router,platform_router,branding_router,module_settings_router,
    crops_router,crop_input_router,crop_sales_router,extended_shared_router,
    livestock_router,livestock_project_router,livestock_production_router,gardening_router,
    machinery_router,subscription_offers_router,cape_access_router,support_router,finance_operations_router,reports_operations_router,employees_operations_router,inventory_operations_router,
):
    app.include_router(domain_router)

app.include_router(crops_v9_router)

@app.get('/api/healthcheck')
def healthcheck():
    return {'status':'ok','app':APP_NAME}

app.mount('/frontend',StaticFiles(directory=FRONTEND),name='frontend')

@app.get('/',include_in_schema=False)
def homepage():
    return FileResponse(FRONTEND/'landing.html')

# Dedicated browser pages, sharing the ES-module application shell.
@app.get('/register-organization',include_in_schema=False)
@app.get('/staff-recovery',include_in_schema=False)
@app.get('/first-time-setup',include_in_schema=False)
def cape_registration_page():
    return FileResponse(FRONTEND/'index.html')

# Cape Ranch public landing: authenticated UI is retained at /app and /login.
@app.get('/app',include_in_schema=False)
@app.get('/login',include_in_schema=False)
def cape_ranch_application_page():
    return FileResponse(FRONTEND/'index.html')
