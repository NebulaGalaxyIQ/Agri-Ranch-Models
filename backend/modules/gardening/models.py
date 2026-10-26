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
class GardenArea(Base):
    __tablename__='v6_garden_areas'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    name:Mapped[str]=mapped_column(String(160))
    area_m2:Mapped[Decimal|None]=mapped_column(Numeric(12,2))
    type:Mapped[str]=mapped_column(String(80),default='landscaping')
    notes:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class GardenRecord(Base):
    __tablename__='v6_garden_records'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    area_id:Mapped[int]=mapped_column(ForeignKey('v6_garden_areas.id'),index=True)
    action:Mapped[str]=mapped_column(String(40))
    performed_on:Mapped[date]=mapped_column(Date)
    observations:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
