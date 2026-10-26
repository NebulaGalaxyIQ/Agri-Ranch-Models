"""Gardening V2 calculations and recurrence rules. No mutations to legacy V6 rows."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from modules.gardening.models import (
    GardenArea, GardenPlant, GardenWork, GardenSchedule, GardenExpense,
    GardenHealth, GardenInspection, GardenNurseryBatch, GardenRecord,
)


def scheduled_for(task: GardenSchedule, day: date) -> bool:
    """A recurrence is due on its start weekday or month day, inclusively."""
    if not task.is_active or day < task.starts_on or (task.ends_on and day > task.ends_on):
        return False
    if task.frequency == 'once':
        return day == task.starts_on
    if task.frequency == 'weekly':
        return day.weekday() == task.starts_on.weekday()
    if task.frequency == 'monthly':
        return day.day == task.starts_on.day
    return task.frequency == 'daily'


def gardening_dashboard(db: Session, org_id: int, *, today: date | None = None) -> dict:
    """Return tenant-filtered real data; costs grouped per currency, never converted implicitly."""
    today = today or date.today()
    areas = db.query(GardenArea).filter_by(organization_id=org_id).all()
    cutoff = today - timedelta(days=370)
    plants = db.query(GardenPlant).filter_by(organization_id=org_id).all()
    schedules = db.query(GardenSchedule).filter_by(organization_id=org_id).all()
    works = db.query(GardenWork).filter_by(organization_id=org_id).filter(GardenWork.performed_on >= cutoff).all()
    work_count = db.query(func.count(GardenWork.id)).filter_by(organization_id=org_id).scalar() or 0
    expenses = db.query(GardenExpense).filter_by(organization_id=org_id).filter(GardenExpense.spent_on >= cutoff).all()
    health = db.query(GardenHealth).filter_by(organization_id=org_id).filter(GardenHealth.observed_on >= cutoff).all()
    health_open_count = db.query(func.count(GardenHealth.id)).filter_by(organization_id=org_id).filter(GardenHealth.status.in_(['open', 'treating'])).scalar() or 0
    inspections = db.query(GardenInspection).filter_by(organization_id=org_id).all()
    nursery = db.query(GardenNurseryBatch).filter_by(organization_id=org_id).all()
    legacy = db.query(GardenRecord).filter_by(organization_id=org_id).filter(GardenRecord.performed_on >= cutoff).all()
    legacy_count = db.query(func.count(GardenRecord.id)).filter_by(organization_id=org_id).scalar() or 0
    due = [t for t in schedules if scheduled_for(t, today)]
    completed_ids = {w.schedule_id for w in works if w.performed_on == today and w.schedule_id is not None}
    water = db.query(func.sum(GardenWork.water_litres)).filter_by(organization_id=org_id, action='watering').scalar() or Decimal(0)
    recorded_cost = defaultdict(Decimal)
    monthly = defaultdict(lambda: {'activities': 0, 'water_litres': Decimal(0), 'cost_by_currency': defaultdict(Decimal)})
    for w in works:
        month = w.performed_on.strftime('%Y-%m')
        monthly[month]['activities'] += 1
        monthly[month]['water_litres'] += w.water_litres
        monthly[month]['cost_by_currency'][w.currency] += w.direct_cost
    # Include historical V6 work in activity trends; no quantities or costs are invented.
    for x in legacy:
        monthly[x.performed_on.strftime('%Y-%m')]['activities'] += 1
    for x in expenses:
        monthly[x.spent_on.strftime('%Y-%m')]['cost_by_currency'][x.currency] += x.total_cost
    for h in health:
        monthly[h.observed_on.strftime('%Y-%m')]['cost_by_currency'][h.currency] += h.expense
    # Aggregate full-history money totals in PostgreSQL, without loading large ledgers.
    for model, amount in ((GardenWork, GardenWork.direct_cost),
                          (GardenExpense, GardenExpense.total_cost),
                          (GardenHealth, GardenHealth.expense)):
        totals = db.query(model.currency, func.sum(amount)).filter_by(organization_id=org_id).group_by(model.currency).all()
        for currency, value in totals:
            recorded_cost[currency] += value or Decimal(0)
    latest_inspections = {}
    for rec in inspections:
        current = latest_inspections.get(rec.area_id)
        if current is None or (rec.inspected_on, rec.id) > (current.inspected_on, current.id):
            latest_inspections[rec.area_id] = rec
    avg_condition = (sum((x.overall_score for x in latest_inspections.values()), Decimal(0)) /
                     len(latest_inspections)) if latest_inspections else None
    recent_days = [today - timedelta(days=d) for d in range(1, 8)]
    # Only seven days of completions are needed for the overdue calculation.
    recent_work = db.query(GardenWork.schedule_id, GardenWork.performed_on).filter(
        GardenWork.organization_id == org_id, GardenWork.performed_on >= today-timedelta(days=7)).all()
    completion_keys = {(s, d) for s, d in recent_work if s is not None}
    overdue = sum(1 for t in schedules for d in recent_days
                  if scheduled_for(t, d) and (t.id, d) not in completion_keys)
    nursery_total = sum(x.seeds_started for x in nursery)
    nursery_survived = sum(x.survived for x in nursery)
    summary = {
        'overdue_tasks_7d': overdue,
        'nursery_survival_pct': round(nursery_survived / nursery_total * 100, 2) if nursery_total else None,
        'areas': len(areas),
        'area_m2': round(sum(float(x.area_m2 or 0) for x in areas), 2),
        'plants': sum(x.quantity for x in plants if x.condition not in ('dead', 'replaced')),
        'plant_groups': len(plants),
        'nursery_batches': len(nursery),
        'recorded_activities': work_count + legacy_count,
        'water_litres': round(float(water), 2),
        'today_due': len(due),
        'today_complete': sum(t.id in completed_ids for t in due),
        'health_open': health_open_count,
        'condition_score': round(float(avg_condition), 2) if avg_condition is not None else None,
        'expenses_by_currency': [{'currency': c, 'amount': round(float(v), 2)} for c, v in sorted(recorded_cost.items())],
    }
    by_condition = defaultdict(int)
    for x in plants:
        by_condition[x.condition] += x.quantity
    return {
        'summary': summary,
        'plant_conditions': [{'condition': c, 'quantity': n} for c, n in sorted(by_condition.items())],
        'monthly': [
            {'month': k, 'activities': v['activities'], 'water_litres': round(float(v['water_litres']), 2),
             'costs': [{'currency': c, 'amount': round(float(a), 2)} for c, a in sorted(v['cost_by_currency'].items())]}
            for k, v in sorted(monthly.items())[-12:]
        ],
        'latest_inspections': [
            {'area_id': key, 'inspected_on': val.inspected_on.isoformat(), 'score': float(val.overall_score)}
            for key, val in sorted(latest_inspections.items())
        ],
    }
