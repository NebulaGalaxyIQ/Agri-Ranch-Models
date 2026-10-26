from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal

class OrganizationRegistration(BaseModel):
    name: str = Field(min_length=3,max_length=180)
    trading_name: str|None=Field(default=None,max_length=180)
    legal_entity_type: str = Field(min_length=2,max_length=100)
    registration_number: str|None=Field(default=None,max_length=100)
    tax_number: str|None=Field(default=None,max_length=100)
    incorporation_date: date|None=None
    email: EmailStr
    billing_email: EmailStr|None=None
    phone: str = Field(min_length=6,max_length=40)
    website: str|None=Field(default=None,max_length=255)
    country: str = Field(min_length=2,max_length=90)
    state_province: str|None=Field(default=None,max_length=120)
    region: str|None=Field(default=None,max_length=100)
    district: str|None=Field(default=None,max_length=100)
    city: str|None=Field(default=None,max_length=120)
    postal_code: str|None=Field(default=None,max_length=35)
    address: str = Field(min_length=6,max_length=1500)
    operational_countries: str|None=Field(default=None,max_length=2000)
    industry_sectors: str = Field(min_length=3,max_length=1000)
    production_focus: str|None=Field(default=None,max_length=1800)
    operations_description: str = Field(min_length=15,max_length=4000)
    employee_count: int = Field(ge=1,le=1000000)
    expected_system_users: int = Field(ge=1,le=1000000)
    farms_count: int = Field(ge=0,le=100000)
    total_land_hectares: float|None=Field(default=None,ge=0,le=100000000)
    preferred_currency: str = Field(min_length=3,max_length=3)
    timezone: str = Field(min_length=3,max_length=90)
    contact_person: str = Field(min_length=2,max_length=150)
    contact_position: str|None=Field(default=None,max_length=100)
    contact_phone: str|None=Field(default=None,max_length=50)
    admin_name: str=Field(min_length=2,max_length=150)
    admin_email: EmailStr
    admin_password: str=Field(min_length=10,max_length=128)

    @field_validator('preferred_currency')
    @classmethod
    def currency(cls,v):
        if not v.isalpha():raise ValueError('Use a valid three-letter currency code')
        return v.upper()

class PolicyUpdate(BaseModel):
    trial_enabled:bool
    trial_days:Literal[30]=30
    minimum_paid_days:Literal[30]=30
    default_employee_seats:int=Field(default=25,ge=1,le=100000)

class RequestSubscription(BaseModel):
    days:int=Field(ge=30,le=3650)
    employee_seats:int=Field(default=25,ge=1,le=100000)
    notes:str|None=Field(default=None,max_length=2000)

class ApproveRequest(BaseModel):
    decision:Literal['approve','reject']
