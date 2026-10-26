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

"""Traceable purchase lots for new receipts and FEFO issue allocations.
Old V5 stock remains an untracked legacy balance; it is not retroactively assigned fictional expiry dates.
"""
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import Date, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class StockLot(Base):
    __tablename__='v57_stock_lots'
    __table_args__=(UniqueConstraint('receipt_movement_id',name='uq_v57_lot_receipt'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'),index=True)
    receipt_movement_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_movements.id'))
    expiry_date:Mapped[date|None]=mapped_column(Date)
    received_quantity:Mapped[Decimal]=mapped_column(Numeric(16,3))
    remaining_quantity:Mapped[Decimal]=mapped_column(Numeric(16,3))

class StockLotIssue(Base):
    __tablename__='v57_lot_issues'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    lot_id:Mapped[int]=mapped_column(ForeignKey('v57_stock_lots.id'),index=True)
    issue_movement_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_movements.id'),index=True)
    quantity:Mapped[Decimal]=mapped_column(Numeric(16,3))

def register_lot(db,org,movement,expiry_date):
    db.add(StockLot(organization_id=org.id,item_id=movement.item_id,receipt_movement_id=movement.id,
                    expiry_date=expiry_date,received_quantity=movement.quantity,remaining_quantity=movement.quantity))

def usable_qty(db,org,item_id,physical_qty):
    """Uses only real receipt lot expiry information; legacy/untracked stock remains usable."""
    lots=db.query(StockLot).filter_by(organization_id=org.id,item_id=item_id).all()
    if not lots:return Decimal(physical_qty)
    tracked=sum((Decimal(x.remaining_quantity) for x in lots),Decimal(0))
    historical=max(Decimal(0),Decimal(physical_qty)-tracked)
    nonexpired=sum((Decimal(x.remaining_quantity) for x in lots if not x.expiry_date or x.expiry_date>=date.today()),Decimal(0))
    return min(Decimal(physical_qty),historical+nonexpired)

def allocate_fefo(db,org,item_id,issue_id,qty,physical_available,when):
    """Must be called within stock item row-locked transaction, before commit."""
    rows=db.query(StockLot).filter_by(organization_id=org.id,item_id=item_id).with_for_update().all()
    if not rows:return
    tracked=sum((Decimal(x.remaining_quantity) for x in rows),Decimal(0))
    legacy=max(Decimal(0),Decimal(physical_available)-tracked)
    usable=legacy+sum((Decimal(x.remaining_quantity) for x in rows if not x.expiry_date or x.expiry_date>=when),Decimal(0))
    if usable<qty:raise HTTPException(409,f'Only {usable} usable stock remains; expired lots cannot be issued')
    outstanding=Decimal(qty)
    for lot in sorted((x for x in rows if not x.expiry_date or x.expiry_date>=when),key=lambda x:(x.expiry_date or date.max,x.id)):
        used=min(outstanding,Decimal(lot.remaining_quantity))
        if used>0:
            lot.remaining_quantity=Decimal(lot.remaining_quantity)-used
            db.add(StockLotIssue(organization_id=org.id,lot_id=lot.id,issue_movement_id=issue_id,quantity=used))
            outstanding-=used
        if outstanding==0:break
    # Remaining amount is consumed from untracked legacy inventory, without fabricating lot provenance.
    if outstanding>legacy:raise HTTPException(409,'Lot allocation mismatch; review stock movement history')


# Domain-owned database entities. Table names are preserved for existing installations.
class StockItem(Base):
    __tablename__='v5_stock_items';__table_args__=(UniqueConstraint('organization_id','name'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    name:Mapped[str]=mapped_column(String(180))
    unit:Mapped[str]=mapped_column(String(30),default='kg')
    category:Mapped[str]=mapped_column(String(40),default='feed')
    cost_per_unit:Mapped[Decimal]=mapped_column(Numeric(16,4),default=0)
    currency:Mapped[str]=mapped_column(String(10),default='TZS')
    reorder_level:Mapped[Decimal]=mapped_column(Numeric(16,3),default=0)


class StockMovement(Base):
    __tablename__='v5_stock_movements';__table_args__=(UniqueConstraint('organization_id','reference'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'),index=True)
    direction:Mapped[str]=mapped_column(String(20))
    quantity:Mapped[Decimal]=mapped_column(Numeric(16,3))
    unit_cost:Mapped[Decimal]=mapped_column(Numeric(16,4),default=0)
    reference:Mapped[str]=mapped_column(String(100))
    note:Mapped[str|None]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    batch_id:Mapped[int|None]=mapped_column(ForeignKey('v5_batches.id'))
    transaction_date:Mapped[date|None]=mapped_column(__import__('sqlalchemy').Date)
    source_type:Mapped[str|None]=mapped_column(String(30))
    created_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow)


class FeedItemNutrients(Base):
    __tablename__='v5_feed_item_nutrients'
    __table_args__=(UniqueConstraint('organization_id','item_id',name='uq_v5_nutrition_feed_item'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'))
    nutrients:Mapped[str]=mapped_column(Text,nullable=False,default='{}')
    notes:Mapped[str|None]=mapped_column(Text)
    updated_at:Mapped[date]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)


class StockReceipt(Base):
    __tablename__='v5_stock_receipts'
    movement_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_movements.id'),primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    supplier_name:Mapped[str|None]=mapped_column(String(180))
    supplier_contact:Mapped[str|None]=mapped_column(String(120))
    origin:Mapped[str|None]=mapped_column(String(180))
    invoice_number:Mapped[str|None]=mapped_column(String(120))
    expiry_date:Mapped[date|None]=mapped_column(Date)
    total_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    transport_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    other_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    currency:Mapped[str]=mapped_column(String(10),default='TZS')
    exchange_rate:Mapped[Decimal]=mapped_column(Numeric(18,8),default=1)
    base_currency:Mapped[str]=mapped_column(String(10),default='TZS')
    base_total_cost:Mapped[Decimal|None]=mapped_column(Numeric(18,2))


class FeedMixProduct(Base):
    __tablename__='v5_mix_products'
    __table_args__=(UniqueConstraint('organization_id','item_id',name='uq_v5_mix_product_item'),)
    ration_id:Mapped[int]=mapped_column(ForeignKey('v5_rations.id'),primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'))


class StockItemDetails(Base):
    __tablename__='v59_stock_item_details'
    item_id:Mapped[int]=mapped_column(ForeignKey('v5_stock_items.id'),primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('v5_organizations.id'),index=True)
    attributes_json:Mapped[str]=mapped_column(Text,default='{}')
