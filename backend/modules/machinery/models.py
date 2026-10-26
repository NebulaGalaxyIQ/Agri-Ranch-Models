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
class Machine(Base):
    __tablename__='v6_machines'
    __table_args__=(UniqueConstraint('organization_id','asset_code',name='uq_v6_machine_code'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    ranch_id:Mapped[int]=mapped_column(ForeignKey('v5_ranches.id'),index=True)
    asset_code:Mapped[str]=mapped_column(String(100))
    name:Mapped[str]=mapped_column(String(180))
    category:Mapped[str]=mapped_column(String(70),default='machinery')
    model:Mapped[str|None]=mapped_column(String(140))
    serial_number:Mapped[str|None]=mapped_column(String(140))
    acquired_on:Mapped[date|None]=mapped_column(Date)
    status:Mapped[str]=mapped_column(String(30),default='active')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class MachineRecord(Base):
    __tablename__='v6_machine_records'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    machine_id:Mapped[int]=mapped_column(ForeignKey('v6_machines.id'),index=True)
    action:Mapped[str]=mapped_column(String(30))
    performed_on:Mapped[date]=mapped_column(Date)
    meter_hours:Mapped[Decimal|None]=mapped_column(Numeric(12,2))
    expense:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    currency:Mapped[str]=mapped_column(String(8),default='TZS')
    notes:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
