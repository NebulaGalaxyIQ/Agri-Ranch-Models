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
class SupportTicket(Base):
    __tablename__='v57_support_tickets'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int|None]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    subject:Mapped[str]=mapped_column(String(200))
    category:Mapped[str]=mapped_column(String(50),default='technical')
    priority:Mapped[str]=mapped_column(String(30),default='normal')
    status:Mapped[str]=mapped_column(String(30),default='open')
    assigned_to:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class SupportMessage(Base):
    __tablename__='v57_support_messages'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    ticket_id:Mapped[int]=mapped_column(ForeignKey('v57_support_tickets.id'),index=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    message:Mapped[str]=mapped_column(Text)
    internal:Mapped[bool]=mapped_column(__import__('sqlalchemy').Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class SupportAttachment(Base):
 __tablename__='v57_support_attachments'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 ticket_id:Mapped[int]=mapped_column(ForeignKey('v57_support_tickets.id'),index=True)
 uploaded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
 filename:Mapped[str]=mapped_column(String(180))
 media_type:Mapped[str]=mapped_column(String(100))
 content:Mapped[bytes]=mapped_column(LargeBinary)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
