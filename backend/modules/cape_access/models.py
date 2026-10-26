"""Additive subscription administration and organization profiles.
Legacy v5_organization, v5_subscription and v5_license_keys remain canonical.
"""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow

class SubscriptionPolicy(Base):
    __tablename__ = 'cape_subscription_policies'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trial_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    minimum_paid_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    default_employee_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class TrialGrant(Base):
    __tablename__='cape_trial_grants'
    organization_id: Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),primary_key=True)
    license_key_id: Mapped[int]=mapped_column(ForeignKey('v5_license_keys.id'),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    ends_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)

class SubscriptionRequest(Base):
    __tablename__='cape_subscription_requests'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True,nullable=False)
    requested_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    days:Mapped[int]=mapped_column(Integer,nullable=False)
    employee_seats:Mapped[int]=mapped_column(Integer,nullable=False,default=25)
    notes:Mapped[str|None]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default='pending',nullable=False)
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    license_key_id:Mapped[int|None]=mapped_column(ForeignKey('v5_license_keys.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class OrganizationProfile(Base):
    __tablename__='cape_organization_profiles'
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),primary_key=True)
    legal_entity_type:Mapped[str|None]=mapped_column(String(100))
    industry_sectors:Mapped[str|None]=mapped_column(Text)
    operations_description:Mapped[str|None]=mapped_column(Text)
    employee_count:Mapped[int|None]=mapped_column(Integer)
    expected_system_users:Mapped[int|None]=mapped_column(Integer)
    farms_count:Mapped[int|None]=mapped_column(Integer)
    total_land_hectares:Mapped[str|None]=mapped_column(String(70))
    city:Mapped[str|None]=mapped_column(String(120))
    state_province:Mapped[str|None]=mapped_column(String(120))
    postal_code:Mapped[str|None]=mapped_column(String(35))
    website:Mapped[str|None]=mapped_column(String(255))
    incorporation_date:Mapped[str|None]=mapped_column(String(20))
    contact_person:Mapped[str|None]=mapped_column(String(150))
    contact_position:Mapped[str|None]=mapped_column(String(100))
    contact_phone:Mapped[str|None]=mapped_column(String(50))
    preferred_currency:Mapped[str|None]=mapped_column(String(3))
    timezone:Mapped[str|None]=mapped_column(String(90))
    operational_countries:Mapped[str|None]=mapped_column(Text)
    production_focus:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
