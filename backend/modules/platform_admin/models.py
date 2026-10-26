from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, utcnow

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, LargeBinary, func, text
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, utcnow


# Domain-owned database entities. Table names are preserved for existing installations.
class ModuleSetting(Base):
    __tablename__='v6_module_settings'
    __table_args__=(UniqueConstraint('organization_id','module',name='uq_v6_org_module'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    module:Mapped[str]=mapped_column(String(35))
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)


class FeatureUsage(Base):
    __tablename__='v57_feature_usage'
    __table_args__=(UniqueConstraint('organization_id','feature',name='uq_v57_feature_org'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    feature:Mapped[str]=mapped_column(String(90))
    actions:Mapped[int]=mapped_column(Integer,default=0)
    last_used_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class BrandImage(Base):
    __tablename__='v6_brand_images'
    __table_args__=(UniqueConstraint('scope','organization_id',name='uq_v6_brand_scoped'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    scope:Mapped[str]=mapped_column(String(32),index=True)
    organization_id:Mapped[int|None]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    mime:Mapped[str]=mapped_column(String(40),default='image/png')
    content:Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
