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
class Task(Base):
    __tablename__='v5_tasks'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    category:Mapped[str]=mapped_column(String(40))
    title:Mapped[str]=mapped_column(String(150))
    assigned_to:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    batch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_batches.id'))
    pen_id:Mapped[int|None]=mapped_column(ForeignKey('v5_pens.id'))
    frequency:Mapped[str]=mapped_column(String(20),default='daily')
    shift:Mapped[str]=mapped_column(String(20),default='Morning')
    status:Mapped[str]=mapped_column(String(20),default='pending')
    due_date:Mapped[date|None]=mapped_column(__import__('sqlalchemy').Date)
    completed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    completed_at:Mapped[date|None]=mapped_column(DateTime(timezone=True))
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)


class Notification(Base):
    __tablename__='v5_notifications'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    category:Mapped[str]=mapped_column(String(50))
    title:Mapped[str]=mapped_column(String(180))
    message:Mapped[str]=mapped_column(Text)
    is_read:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)


class TaskCompletion(Base):
    __tablename__='v5_task_completions'
    __table_args__=(UniqueConstraint('organization_id','task_id','occurrence_date',name='uq_v5_task_day'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    task_id:Mapped[int]=mapped_column(ForeignKey('v5_tasks.id'),index=True)
    occurrence_date:Mapped[date]=mapped_column(Date,index=True)
    completed_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    completed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class RoutineShiftClaim(Base):
    __tablename__='v5_routine_shift_claims'
    __table_args__=(UniqueConstraint('organization_id','category','target','occurrence_date','shift',
                                     name='uq_v5_routine_shift_per_target_day'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    category:Mapped[str]=mapped_column(String(40))
    target:Mapped[str]=mapped_column(String(80))
    occurrence_date:Mapped[date]=mapped_column(Date,index=True)
    shift:Mapped[str]=mapped_column(String(30))
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class RecoveryCode(Base):
    __tablename__='v57_recovery_codes'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    membership_id:Mapped[int]=mapped_column(ForeignKey('v5_memberships.id'),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))


class OrgRole(Base):
    __tablename__='v57_org_roles'
    __table_args__=(UniqueConstraint('organization_id','name',name='uq_v57_role_name'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    name:Mapped[str]=mapped_column(String(90))
    permissions:Mapped[str]=mapped_column(Text,default='')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class MemberRole(Base):
    __tablename__='v57_member_roles'
    __table_args__=(UniqueConstraint('membership_id','role_id',name='uq_v57_membership_role'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    membership_id:Mapped[int]=mapped_column(ForeignKey('v5_memberships.id'),index=True)
    role_id:Mapped[int]=mapped_column(ForeignKey('v57_org_roles.id'),index=True)
