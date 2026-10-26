from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow
"""Commercial offers, separate from redeemed product-key grants.
Existing subscription and license tables are NOT redeclared here.
"""
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric
from datetime import datetime, date
from decimal import Decimal
from database import Base, utcnow


class Offer(Base):
    __tablename__='v66_platform_offers'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(120),nullable=False)
    code:Mapped[str]=mapped_column(String(60),unique=True,nullable=False)
    description:Mapped[str|None]=mapped_column(Text)
    discount_pct:Mapped[Decimal]=mapped_column(Numeric(5,2),default=0,nullable=False)
    bonus_days:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    max_redemptions:Mapped[int|None]=mapped_column(Integer)
    starts_on:Mapped[date]=mapped_column(Date,nullable=False)
    ends_on:Mapped[date]=mapped_column(Date,nullable=False)
    active:Mapped[bool]=mapped_column(__import__('sqlalchemy').Boolean,default=True)
    created_by:Mapped[int]=mapped_column(Integer,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

from datetime import date,datetime,timedelta,timezone
from typing import Literal
from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Integer, String, Text, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped,mapped_column
from database import Base,utcnow

# Canonical organization/subscription entities; existing PostgreSQL table names are unchanged.
class Subscription(Base):
    __tablename__ = 'v5_subscriptions'
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), primary_key=True)
    plan: Mapped[str] = mapped_column(String(40), default='professional')
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_employees: Mapped[int] = mapped_column(Integer, default=25)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)


class LicenseKey(Base):
    __tablename__ = 'v5_license_keys'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('v5_organizations.id'), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    max_employees: Mapped[int] = mapped_column(Integer, default=25)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
