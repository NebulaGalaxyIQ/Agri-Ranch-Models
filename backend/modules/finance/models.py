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
class FinanceEntry(Base):
    __tablename__='v5_finance_entries'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    batch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_batches.id'))
    animal_id:Mapped[int|None]=mapped_column(ForeignKey('v5_animals.id'),index=True)
    kind:Mapped[str]=mapped_column(String(20))
    category:Mapped[str]=mapped_column(String(100))
    amount:Mapped[Decimal]=mapped_column(Numeric(18,2))
    currency:Mapped[str]=mapped_column(String(10),default='TZS')
    note:Mapped[str|None]=mapped_column(Text)
    source_type:Mapped[str|None]=mapped_column(String(40))
    source_id:Mapped[int|None]=mapped_column(Integer)
    created_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)
