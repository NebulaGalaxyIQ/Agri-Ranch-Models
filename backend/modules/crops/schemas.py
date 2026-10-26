"""Existing request validation remains on the established API until migration."""

# === GHR_CROPS_V9_SCHEMAS ===
"""V9 global crop-record contracts. Metadata is delivered to the frontend unchanged.

`field` specs: key | caption | kind | required; define unit/currency separately.
Server validation uses the SAME metadata as the browser forms.
"""
from datetime import date
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator


def f(key, label, kind='text', required=False, **options):
    return {'key':key,'label':label,'kind':kind,'required':required,**options}


def specs(*items): return list(items)

SECTIONS = [
 {'id':'overview','title':'Overview','description':'Production, alerts, trial outcomes and financial intelligence','fields':[]},
 {'id':'projects','title':'Projects','description':'Farms, goals, production programs, seasons and approvals','fields':[]},
 {'id':'fields','title':'Fields & Blocks','description':'Farm geography, permanent fields and production-unit capacity','fields':[]},
 {'id':'catalogue','title':'Crops & Varieties','description':'Global crop catalogue, variety characteristics and provenance','fields':[]},
 {'id':'soil','title':'Soil & Land Preparation','description':'Laboratory testing, soil stewardship and preparation operations','fields':specs(f('sample_code','Sample / activity reference'),f('activity_type','Record type','choice',True,options=['soil_sample','laboratory_result','tillage','bed_preparation','soil_amendment','erosion_management']),f('sampling_depth_cm','Sampling depth (cm)','number'),f('soil_ph','Soil pH','number'),f('organic_matter_pct','Organic matter (%)','number'),f('nitrogen_mg_kg','Nitrogen (mg/kg)','number'),f('phosphorus_mg_kg','Phosphorus (mg/kg)','number'),f('potassium_mg_kg','Potassium (mg/kg)','number'),f('conductivity_ds_m','Electrical conductivity (dS/m)','number'),f('texture','Soil texture'),f('method','Sampling/preparation method'),f('laboratory','Laboratory / service provider'))},
 {'id':'budgets','title':'Planning & Budgets','description':'Approved quantities, unit costs, budget revisions and variance','fields':[]},
 {'id':'planting','title':'Nursery & Planting','description':'Propagation, seed lots, emergence, transplanting and establishment','fields':specs(f('propagation','Propagation method','choice',True,options=['direct_seed','transplant','cutting','graft','tissue_culture','tuber','other']),f('seed_lot','Seed/propagation batch'),f('source','Supplier / source'),f('seed_quantity','Quantity sown','number'),f('seed_unit','Seed quantity unit'),f('nursery_unit','Nursery / bed / tray'),f('spacing_cm','Plant spacing (cm)','number'),f('row_spacing_cm','Row spacing (cm)','number'),f('depth_cm','Planting depth (cm)','number'),f('germinated','Germinated plants','integer'),f('surviving','Surviving plants','integer'),f('transplanted','Transplanted plants','integer'),f('establishment_pct','Establishment (%)','number'),f('method','Establishment method'))},
 {'id':'inputs','title':'Inputs & Procurement','description':'Material use, lot provenance and procurement references','fields':specs(f('input_category','Input category','choice',True,options=['seed','seedling','fertilizer','manure','crop_protection','growing_media','fuel','packaging','water','other']),f('item_name','Input item','text',True),f('supplier','Supplier'),f('lot_number','Supplier lot / batch'),f('stock_reference','Existing Inventory issue reference'),f('manufacture_date','Manufacture date','date'),f('expiry_date','Expiry date','date'),f('storage_location','Storage location'),f('consumption_type','Transaction type','choice',True,options=['use_record_only','linked_inventory_issue','procurement_reference']),f('quality_status','Quality status'))},
 {'id':'routine','title':'Daily Routine','description':'Reusable scheduled checklists, shift handovers and missed tasks','fields':[]},
 {'id':'irrigation','title':'Irrigation & Weather','description':'Water volumes, sensor readings, forecast and greenhouse conditions','fields':specs(f('water_source','Water source'),f('system','Irrigation system','choice',True,options=['drip','sprinkler','pivot','furrow','flood','manual','hydroponic','other']),f('water_m3','Applied water (m³)','number'),f('duration_minutes','Duration (minutes)','number'),f('rainfall_mm','Rainfall (mm)','number'),f('soil_moisture_pct','Soil moisture (%)','number'),f('air_temp_c','Air temperature (°C)','number'),f('humidity_pct','Relative humidity (%)','number'),f('ec_ds_m','Water EC (dS/m)','number'),f('water_ph','Water pH','number'),f('sensor_id','Sensor or meter ID'),f('measurement_source','Measurement source','choice',True,options=['manual','meter','sensor','weather_provider']),f('weather_provider','Weather data provider'))},
 {'id':'nutrition','title':'Crop Nutrition','description':'Fertilizer recommendations, application rates and nutrient tracking','fields':specs(f('material','Fertilizer / amendment','text',True),f('material_batch','Material lot'),f('composition','Nutrient formulation'),f('target_nutrient','Target nutrient'),f('application_method','Application method','choice',True,options=['broadcast','band','side_dress','foliar','fertigation','other']),f('treated_area_ha','Treated area (ha)','number'),f('rate_kg_ha','Applied rate (kg/ha)','number'),f('stock_reference','Inventory issue reference'),f('recommendation','Agronomist recommendation'),f('crop_response','Observed crop response'))},
 {'id':'protection','title':'Pests & Crop Protection','description':'Scouting, treatment, label compliance and re-inspection','fields':specs(f('event_type','Record type','choice',True,options=['scouting','monitoring','biological_control','cultural_control','chemical_application','follow_up']),f('issue','Pest/disease/weed or symptom','text',True),f('scientific_name','Scientific name'),f('plants_inspected','Plants inspected','integer'),f('plants_affected','Plants affected','integer'),f('affected_area_ha','Affected area (ha)','number'),f('severity_pct','Severity (%)','number'),f('control_decision','Decision / treatment'),f('product_name','Product name'),f('registration_reference','Local registration / label reference'),f('active_ingredient','Active ingredient'),f('rate','Rate and unit'),f('ppe','Required PPE'),f('rei_hours','Restricted-entry interval (hours)','number'),f('phi_days','Pre-harvest interval (days)','integer'),f('treatment_outcome','Observed treatment outcome'),f('next_check','Next inspection date','date'))},
 {'id':'growth','title':'Growth & Monitoring','description':'Phenology, crop population, sampling and yield forecasting','fields':specs(f('stage','Crop growth stage','text',True),f('sample_size','Plants sampled','integer'),f('plant_count','Observed plant population','integer'),f('plant_height_cm','Mean plant height (cm)','number'),f('stem_diameter_mm','Stem diameter (mm)','number'),f('leaf_count','Leaves per plant','number'),f('flowering_pct','Flowering (%)','number'),f('fruit_set_pct','Fruit set (%)','number'),f('canopy_pct','Canopy cover (%)','number'),f('ndvi','Vegetation index (NDVI)','number'),f('stress','Crop stress / damage'),f('forecast_kg','Estimated harvest (kg)','number'),f('forecast_method','Forecast method / assumptions'),f('photo_reference','Photo/document reference'))},
 {'id':'trials','title':'Trials & Experiments','description':'Research questions, replicated treatments and traceable observations','fields':[]},
 {'id':'resources','title':'Labor & Machinery','description':'Staff time, machine hours, fuel, contractors and productivity','fields':specs(f('resource_type','Resource type','choice',True,options=['employee','contractor','machine','vehicle','pump','other']),f('staff_or_asset','Employee / registered asset / contractor','text',True),f('work_description','Work performed','text',True),f('hours','Working/operating hours','number'),f('fuel_l','Fuel consumed (L)','number'),f('area_ha','Area serviced (ha)','number'),f('distance_km','Distance traveled (km)','number'),f('meter_start','Starting meter','number'),f('meter_end','Ending meter','number'),f('maintenance_reference','Maintenance/calibration reference'))},
 {'id':'harvest','title':'Harvest & Quality','description':'Source blocks, harvest passes, grade and physical output','fields':[]},
 {'id':'postharvest','title':'Postharvest & Traceability','description':'Quality, packing, storage and traceable lot transformation','fields':specs(f('lot_id','Harvest lot ID','integer',True),f('event_type','Postharvest event','choice',True,options=['wash','sort','grade','dry','pack','store','transfer','quarantine','inspection']),f('source_quantity_kg','Input quantity (kg)','number'),f('output_quantity_kg','Output quantity (kg)','number'),f('loss_kg','Loss quantity (kg)','number'),f('grade','Produce grade'),f('storage','Storage facility/bin'),f('temperature_c','Storage temperature (°C)','number'),f('humidity_pct','Relative humidity (%)','number'),f('pack_type','Package type'),f('packages','Number of packages','integer'),f('destination','Next storage / shipping location'))},
 {'id':'sales','title':'Sales & Deliveries','description':'Lot-level produce sales, price, buyers and fulfillment','fields':[]},
 {'id':'costs','title':'Costs & Profitability','description':'Actual operating expenses, allocations and currency-separated results','fields':specs(f('category','Cost category','choice',True,options=['land','seed','fertilizer','crop_protection','labor','irrigation','fuel','machinery','infrastructure','harvesting','postharvest','transport','compliance','other']),f('expense_name','Expense name','text',True),f('allocation_method','Allocation method','choice',False,options=['direct','area','hours','quantity','percentage']),f('invoice_reference','Invoice/reference'),f('supplier','Supplier'),f('payment_status','Payment status','choice',False,options=['unpaid','partial','paid','not_applicable']))},
 {'id':'outcomes','title':'Outcomes & Analytics','description':'Objectives, results, lessons learned and future decisions','fields':specs(f('outcome_type','Outcome category','choice',True,options=['production','financial','research','environmental','operations','project_closeout']),f('trial_id','Related trial ID (optional)','integer'),f('objective','Original objective','text',True),f('result','Observed result','text',True),f('variance_reason','Variance explanation'),f('lesson','Lesson learned'),f('recommendation','Recommended change'),f('decision','Management decision','choice',False,options=['repeat','expand','modify','discontinue','investigate']),f('reviewer','Reviewer'),f('approved','Approved result','boolean'))},
 {'id':'compliance','title':'Compliance & Sustainability','description':'Jurisdiction-specific evidence, safety checks and stewardship','fields':specs(f('jurisdiction','Country / jurisdiction','text',True),f('standard','Applicable law/standard'),f('control_id','Control / requirement'),f('inspection_type','Inspection type'),f('finding','Finding','text',True),f('severity','Severity','choice',False,options=['observation','minor','major','critical']),f('action','Corrective action'),f('due_date','Follow-up deadline','date'),f('responsible_person','Responsible employee'),f('certification_reference','Certification / permit reference'),f('evidence_reference','Evidence/document reference'),f('verification_status','Verification','choice',False,options=['pending','verified','failed','not_applicable']))},
]
SECTION_BY_ID={s['id']:s for s in SECTIONS}
GENERIC_SECTIONS={s['id'] for s in SECTIONS if s['fields']}

class ProjectIn(BaseModel):
    ranch_id:int;name:str=Field(min_length=2,max_length=160);code:str=Field(min_length=2,max_length=64)
    category:str='commercial';objective:str|None=None;method:str='open_field';season:str|None=None
    start_date:date=Field(default_factory=date.today);end_date:date|None=None
    manager_id:int|None=None;currency:str=Field(default='USD',pattern=r'^[A-Z]{3}$')
    planned_budget:Decimal|None=Field(default=None,ge=0);target_yield_kg:Decimal|None=Field(default=None,ge=0)
    expected_price:Decimal|None=Field(default=None,ge=0);status:str='planned';notes:str|None=None
    @model_validator(mode='after')
    def dates(self):
        if self.end_date and self.end_date<self.start_date:raise ValueError('End date cannot precede start date')
        return self

class UnitIn(BaseModel):
    field_id:int;name:str=Field(min_length=2,max_length=120);kind:str='block';area_ha:Decimal=Field(gt=0)
    capacity:int|None=Field(default=None,ge=0);latitude:float|None=None;longitude:float|None=None
    irrigation_system:str|None=None;status:str='available';notes:str|None=None

class VarietyIn(BaseModel):
    name:str=Field(min_length=2,max_length=150);scientific_name:str|None=None;family:str|None=None
    category:str='other';variety:str=Field(min_length=1,max_length=150);life_cycle:str='annual';days_to_maturity:int|None=Field(default=None,gt=0)
    growing_method:str|None=None;source:str|None=None;seed_certification:str|None=None;notes:str|None=None

class CycleInV9(BaseModel):
    project_id:int;unit_id:int;variety_id:int;planted_area_ha:Decimal=Field(gt=0)
    planted_on:date;expected_harvest:date|None=None;method:str='direct_seed';
    status:str='planned';target_yield_kg:Decimal|None=Field(default=None,ge=0);notes:str|None=None
    @model_validator(mode='after')
    def dates(self):
        if self.expected_harvest and self.expected_harvest<self.planted_on:raise ValueError('Harvest date cannot precede planting')
        return self

class RecordIn(BaseModel):
    project_id:int;cycle_id:int|None=None;unit_id:int|None=None
    performed_on:date=Field(default_factory=date.today)
    title:str=Field(min_length=2,max_length=160)
    quantity:Decimal|None=Field(default=None,ge=0);unit:str|None=Field(default=None,max_length=30)
    unit_cost:Decimal|None=Field(default=None,ge=0);other_cost:Decimal|None=Field(default=None,ge=0)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    reference:str|None=Field(default=None,max_length=100)
    notes:str|None=Field(default=None,max_length=5000)
    data:dict[str,Any]=Field(default_factory=dict)
    @model_validator(mode='after')
    def cost_pair(self):
        if self.unit_cost is not None and self.quantity is None:raise ValueError('Quantity is required when unit cost is entered')
        return self

class BudgetIn(BaseModel):
    project_id:int;cycle_id:int|None=None;category:str=Field(min_length=2,max_length=80)
    description:str=Field(min_length=2,max_length=220);quantity:Decimal=Field(gt=0)
    unit:str=Field(min_length=1,max_length=30);unit_cost:Decimal=Field(ge=0)
    currency:str=Field(pattern=r'^[A-Z]{3}$');version:int=Field(default=1,ge=1)
    status:str='draft';planned_on:date|None=None

class RoutineIn(BaseModel):
    project_id:int;cycle_id:int|None=None;unit_id:int|None=None
    title:str=Field(min_length=2,max_length=180);instructions:str|None=None
    frequency:str='daily';weekdays:list[int]=Field(default_factory=list)
    shift:str='morning';start_date:date=Field(default_factory=date.today);end_date:date|None=None
    assigned_to:int|None=None;planned_quantity:Decimal|None=Field(default=None,ge=0);unit:str|None=None
    estimated_minutes:int|None=Field(default=None,ge=0);enabled:bool=True

class CompletionIn(BaseModel):
    day:date=Field(default_factory=date.today);status:str='completed'
    notes:str|None=None;actual_quantity:Decimal|None=Field(default=None,ge=0)
    amount:Decimal|None=Field(default=None,ge=0);currency:str|None=None

class TrialIn(BaseModel):
    project_id:int;cycle_id:int;title:str=Field(min_length=2,max_length=180)
    question:str=Field(min_length=5);hypothesis:str|None=None;design:str='rcbd';replications:int=Field(default=2,ge=1,le=100)
    start_date:date=Field(default_factory=date.today);end_date:date|None=None;status:str='planned';notes:str|None=None

class PlotIn(BaseModel):
    trial_id:int;unit_id:int;code:str=Field(min_length=1,max_length=60)
    treatment:str=Field(min_length=1,max_length=150);replicate:int=Field(ge=1)
    area_ha:Decimal=Field(gt=0);randomization_order:int|None=None;is_control:bool=False

class HarvestIn(BaseModel):
    project_id:int;cycle_id:int;unit_id:int;harvested_on:date=Field(default_factory=date.today)
    pass_number:int=Field(default=1,ge=1);gross_kg:Decimal=Field(gt=0);tare_kg:Decimal=Field(default=0,ge=0)
    rejected_kg:Decimal=Field(default=0,ge=0);grade:str='ungraded';quality:dict[str,Any]=Field(default_factory=dict)
    batch_ref:str=Field(min_length=3,max_length=100);cost:Decimal|None=Field(default=None,ge=0);currency:str|None=None
    @model_validator(mode='after')
    def weights(self):
        if self.tare_kg+self.rejected_kg>self.gross_kg:raise ValueError('Tare plus rejected weight exceeds gross weight')
        return self

class SaleIn(BaseModel):
    lot_id:int;buyer:str=Field(min_length=2,max_length=180);quantity_kg:Decimal=Field(gt=0)
    price_per_kg:Decimal=Field(gt=0);currency:str=Field(pattern=r'^[A-Z]{3}$')
    sold_on:date=Field(default_factory=date.today);delivery_ref:str|None=None
    selling_cost:Decimal|None=Field(default=None,ge=0);notes:str|None=None

class StatusIn(BaseModel):
    status:str=Field(min_length=3,max_length=30)

class StockIn(BaseModel):
    lot_id:int;action:str;quantity_kg:Decimal=Field(gt=0)
    reference:str=Field(min_length=3,max_length=100);notes:str|None=None

# Trial observations are collected within the Trials section, not a 22nd menu card.
TRIAL_OBSERVATION = {'id':'trial_observations','title':'Trial measurements','description':'Measured results from a designated experimental plot',
 'fields':specs(f('trial_id','Trial ID','integer',True),f('plot_id','Experimental plot ID','integer',True),
 f('trait','Measured trait','text',True),f('value','Measured numeric value','number',True),
 f('measurement_unit','Measurement unit','text',True),f('method','Measurement method','text',True),
 f('replicate_note','Sampling / observation details'))}
SECTION_BY_ID['trial_observations']=TRIAL_OBSERVATION
GENERIC_SECTIONS.add('trial_observations')

# === END_GHR_CROPS_V9_SCHEMAS ===
