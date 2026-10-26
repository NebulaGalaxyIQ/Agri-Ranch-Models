"""Detailed, tenant-scoped management analyses built solely from recorded source data.

These views supplement (never replace) all exported source rows. No aggregation across
currencies or invented allocations. Inputs stay in the owning operational modules.
"""
from __future__ import annotations
from collections import defaultdict
import json
from decimal import Decimal
from datetime import date, datetime, timezone
from fastapi import HTTPException

# Human-facing labels must never expose storage generations or internal table versions.
LABELS={
'v5_animals':'Individual Fattening Animals','v5_weight_observations':'Individual Weighing History',
'v5_projects':'Fattening Projects','v5_batches':'Fattening Batches','v5_pens':'Fattening Pens',
'v5_feeding_lines':'Feed Consumption Lines','v5_feed_plans':'Feed Schedules',
'v5_rations':'Feed Formulations','v5_mix_production':'Feed Mix Production',
'v5_finance_entries':'Recorded Financial Transactions','v5_animal_sales':'Animal Sales',
'fattening_sale_cost_snapshots':'Recorded Sale Cost Breakdowns',
'v5_stock_items':'Inventory Items','v5_stock_movements':'Inventory Movements',
'v57_stock_lots':'Inventory Lots','v57_lot_issues':'Inventory Lot Issues',
'v5_stock_receipts':'Purchase Receipts',
'v6_machines':'Machinery & Equipment','v6_machine_records':'Machinery Activity & Maintenance',
'v9_crop_projects':'Crop Projects','v9_crop_units':'Crop Production Blocks',
'v9_crop_cycles':'Crop Production Cycles','v9_crop_varieties':'Crops & Varieties',
'v9_crop_records':'Field Operations','v9_crop_harvest_lots':'Harvest Batches & Quality',
'v9_crop_sales':'Crop Sales','v9_crop_stock_movements':'Crop Stock Movements',
'v9_crop_budgets':'Crop Project Budgets','v9_crop_trials':'Agricultural Trials',
'v9_crop_trial_plots':'Experimental Treatment Plots',
'v6_livestock_groups':'Herds & Flocks','v6_general_animals':'Registered Livestock & Birds',
'v61_livestock_projects':'Livestock Projects','v61_livestock_project_costs':'Livestock Project Expenses',
'v61_livestock_product_lots':'Livestock Product Stock','v61_livestock_product_sales':'Livestock Product Sales',
'v8_livestock_breeding_records':'Breeding & Pregnancy Records',
'v83_livestock_offspring_cohorts':'Births, Hatchings & Offspring',
'v8_livestock_incubations':'Poultry Incubation Batches',
'v8_livestock_health_records':'Veterinary & Health Events',
'v8_livestock_weight_records':'Livestock Weighing History',
'v8_livestock_care_records':'Daily Care & Routine Records',
'v83_livestock_routine_completions':'Livestock Routine Checklist History',
'v9_crop_completions':'Crop Routine Checklist History',
'v5_tasks':'Assigned Staff Tasks','v5_task_completions':'Staff Task Completions',
}
def label(table):
    import re
    if table in LABELS:return LABELS[table]
    clean=re.sub(r'^(?:v\d+_|fattening_)','',table)
    return clean.replace('_',' ').title()

def num(value):
    if value is None:return None
    return float(value)

def roundnum(value, places=2):
    return round(float(value),places) if value is not None else None

def dt(value):
    return value.date() if isinstance(value,datetime) else value

def iso(value):
    return value.isoformat() if isinstance(value,(date,datetime)) else value

def within(value,filters):
    day=dt(value)
    if day is None:return not(filters.from_date or filters.to_date)
    return (not filters.from_date or day>=filters.from_date) and (not filters.to_date or day<=filters.to_date)

def view(key,title,columns,rows,notes=None,charts=None):
    return {'id':key,'title':title,'columns':columns,'rows':rows,'total_rows':len(rows),
            'notes':notes or [],'charts':charts or []}

def chart(title,measure,rows,group,unit,typ='bar',limit=15):
    data=defaultdict(float)
    for row in rows:
        value=row.get(measure)
        if value is not None:data[str(row.get(group) or 'Not recorded')]+=float(value)
    pts=[{'label':k,'value':round(v,3)} for k,v in sorted(data.items(),key=lambda x:-abs(x[1]))[:limit]]
    return {'title':title,'type':typ,'unit':unit,'points':pts}

def analyses(db,ctx,payload,models,allowed_tables):
    from modules.reports.v10_service import q_for
    org=ctx[1].id
    views=[];warnings=[]
    section=payload.section_id
    family={
      'fattening_population':['projects'], 'fattening_weights':['animals'],
      'fattening_sales':['animals','project_position'], 'fattening_feed':['feeding'],
      'inventory':['stock'], 'machinery':['machinery'],
      'crop_planting':['crop_yield','projects'], 'crop_harvest':['crop_yield'],
      'crop_finance':['crop_yield','project_position','projects'], 'crop_trials':['trials'],
      'livestock_breeding':['breeding'], 'livestock_hatchery':['poultry'],
      'livestock_groups':['poultry'], 'livestock_products':['poultry'],
      'finance':['finance','project_position','projects'], 'commercial':['sales'],
      'portfolio':['projects','project_position','crop_yield'],
      'executive':['projects','project_position','finance','animals','stock','crop_yield','machinery'],
      'employees':['routine'], 'crop_fieldwork':['routine'],
    }
    family.update({
      'individual_animals':['animals'], 'fattening_acquisition':['animals'],
      'feed_consumption':['feeding'], 'feed_formulations':['feeding'],
      'fattening_project_costs':['project_position'],
      'animal_sales_detail':['animals'],
      'livestock_housing':['poultry'], 'livestock_offspring':['breeding'],
      'livestock_costs':['project_position'], 'livestock_routines':['routine'],
      'livestock_production':['poultry'],
      'crop_soils':['agronomy'], 'crop_irrigation':['agronomy'],
      'crop_nutrition':['agronomy'], 'crop_protection':['agronomy'],
      'crop_growth':['agronomy'], 'crop_budget_detail':['agronomy','project_position'],
      'crop_trial_detail':['trials','agronomy'], 'crop_produce_stock':['crop_yield'],
      'crop_sales_detail':['crop_yield'], 'crop_fieldwork':['agronomy','routine'],
      'stock_balances':['stock'], 'stock_procurement':['stock'],
      'equipment_maintenance':['machinery'], 'staff_activity':['routine'],
      'finance_transactions':['finance'], 'operating_project_results':['project_position','finance']})
    jobs=family.get(section,[])
    if section.startswith('table:'):
        table=section[6:]
        jobs=[job for job,sources in {'animals':['v5_animals','v5_weight_observations','v5_animal_sales'],
           'feeding':['v5_feeding_lines','v5_rations'], 'stock':['v5_stock_items','v5_stock_movements'],
           'crop_yield':['v9_crop_harvest_lots','v9_crop_sales'], 'machinery':['v6_machines','v6_machine_records'],
           'finance':['v5_finance_entries'],'breeding':['v8_livestock_breeding_records'],
           'poultry':['v61_livestock_product_lots','v8_livestock_incubations'],
           'trials':['v9_crop_trials'],'projects':['v5_projects','v9_crop_projects','v61_livestock_projects']}.items() if table in sources]
    def fetch(t,limit=20000,remove_dates=False):
        if t not in models or t not in allowed_tables:return []
        filterobj=payload.filters.model_copy()
        if remove_dates:
            filterobj.from_date=None;filterobj.to_date=None
        query,why=q_for(db,models[t],org,filterobj)
        if query is None:return []
        rows=query.limit(limit+1).all()
        if len(rows)>limit:raise HTTPException(413,f'Detailed analysis for {label(t)} exceeds {limit:,} records. Filter by project, batch or dates; no results are silently truncated.')
        return rows
    def pick(t):
        # Related master records must not inherit a child-only selector (for example
        # animal_id cannot directly filter v5_batches). Tenant scope stays mandatory.
        if t not in models or t not in allowed_tables:return {}
        f=payload.filters.model_copy()
        f.from_date=None;f.to_date=None
        for key in ('animal_id','item_id','machine_id','trial_id','lot_id','cycle_id','group_id'):
            setattr(f,key,None)
        query,why=q_for(db,models[t],org,f)
        if query is None:return {}
        objects=query.limit(20001).all()
        if len(objects)>20000:raise HTTPException(413,'Related master records exceed the allowed report scope; narrow the project or ranch filter.')
        return {r.id:r for r in objects}
    def ok(t):return t in allowed_tables and t in models
    def scope_matches_batch(batch):
        f=payload.filters
        return bool(batch and (not f.project_id or batch.project_id==f.project_id) and (not f.ranch_id or batch.ranch_id==f.ranch_id))
    # Primary rows are fetched through q_for; secondary metadata and observations are tenant scoped.
    for job in jobs:
      if job in ('animals','feeding') and not ok('v5_animals'):continue
      if job=='animals':
        batches=pick('v5_batches');weights=fetch('v5_weight_observations',remove_dates=True);sales=fetch('v5_animal_sales',remove_dates=True)
        snapshots={r.sale_id:r for r in fetch('fattening_sale_cost_snapshots',remove_dates=True)}
        routine_ids=defaultdict(list)
        for r in fetch('v5_routine_entries',remove_dates=True):
            if r.animal_tag:routine_ids[(r.batch_id,r.animal_tag)].append(r.id)
        feed_for_routine=defaultdict(float)
        for line in fetch('v5_feeding_lines',remove_dates=True):
            feed_for_routine[line.routine_id]+=num(line.quantity_kg) or 0
        by_weight=defaultdict(list);by_sale=defaultdict(list)
        for w in weights:by_weight[w.animal_id].append(w)
        for s in sales:
            if s.status=='completed':by_sale[s.animal_id].append(s)
        direct=defaultdict(lambda:defaultdict(lambda:{'cost':0.0,'revenue':0.0}))
        for e in fetch('v5_finance_entries',remove_dates=True):
            if e.animal_id is not None and e.kind in ('cost','revenue'):
                direct[e.animal_id][e.currency][e.kind]+=num(e.amount) or 0
        rows=[]
        for a in fetch('v5_animals',remove_dates=True):
            batch=batches.get(a.batch_id)
            if not scope_matches_batch(batch):continue
            if payload.filters.species and a.species!=payload.filters.species:continue
            if payload.filters.status and a.status!=payload.filters.status:continue
            ws=sorted((w for w in by_weight[a.id] if not payload.filters.to_date or dt(w.created_at)<=payload.filters.to_date),key=lambda w:(w.created_at,w.id))
            first=ws[0] if ws else None;last=ws[-1] if ws else None
            original=num(a.entry_weight_kg)
            current=num(last.weight_kg) if last else (num(a.current_weight_kg) if not payload.filters.to_date else None)
            start=dt(a.arrival_date or a.created_at)
            final=dt(last.created_at) if last else None
            elapsed=(final-start).days if start and final else None
            gain=roundnum(current-original,3) if current is not None and original is not None else None
            adg=roundnum(gain/elapsed,3) if gain is not None and elapsed and elapsed>0 else None
            sold=next((s for s in sorted(by_sale[a.id],key=lambda z:z.sale_date,reverse=True) if not payload.filters.to_date or s.sale_date<=payload.filters.to_date),None)
            sale_amount=num(sold.gross_amount) if sold else None
            sale_expense=sum(num(getattr(sold,k)) or 0 for k in ['transport_cost','commission_cost','other_cost']) if sold else None
            cur=a.purchase_currency
            cost=direct.get(a.id,{}).get(cur,{}).get('cost',0.0)
            # Expense completeness is not provable from animal-specific ledger entries.
            revenue_comparable=bool(sold and sold.currency==cur)
            partial_break_even=roundnum(num(a.purchase_cost)+cost+(sale_expense if revenue_comparable else 0)) if a.purchase_cost is not None else None
            snapshot={}
            if sold and sold.id in snapshots:
                try:snapshot=json.loads(snapshots[sold.id].cost_snapshot_json)
                except (ValueError,TypeError):snapshot={}
            feed_ids=routine_ids[(a.batch_id,a.tag)]
            directly_measured_feed=roundnum(sum(feed_for_routine[i] for i in feed_ids),3) if feed_ids else None
            profit=roundnum(snapshot.get('projected_profit_loss')) if snapshot.get('comparable') else None
            break_even_at_sale=roundnum(snapshot.get('total_break_even')) if snapshot.get('comparable') else None
            rows.append({'animal_id':a.id,'tag':a.tag,'species':a.species,'breed':a.breed,'status':a.status,
              'project_id':batch.project_id if batch else None,'batch_id':a.batch_id,'arrival_date':iso(a.arrival_date),
              'sex':a.sex,'origin':a.origin,'supplier':a.supplier_name,'date_of_birth':iso(a.date_of_birth),'individual_measured_feed_kg':directly_measured_feed,
              'entry_weight_kg':original,'latest_weight_kg':current,'last_weighed_on':iso(last.created_at) if last else None,
              'weight_change_kg':gain,'elapsed_days':elapsed,'average_daily_gain_kg':adg,
              'weighing_count':len(ws),'purchase_cost':num(a.purchase_cost),'currency':cur,
              'direct_recorded_expenses':roundnum(cost), 'partial_cost_floor':partial_break_even,
              'sale_date':iso(sold.sale_date) if sold else None,'sale_currency':sold.currency if sold else None,
              'sale_revenue':sale_amount,'selling_expenses':sale_expense,'sale_snapshot_break_even':break_even_at_sale,
              'sale_snapshot_provisional_profit_loss':profit,'sale_snapshot_margin_percent':roundnum(snapshot.get('margin_percent')) if profit is not None else None,
              'cost_allocation_basis':'Sale-time snapshot (provisional)' if snapshot else 'Incomplete records'})
        cols=list(rows[0]) if rows else ['animal_id','tag','project_id','batch_id','species','breed','entry_weight_kg','latest_weight_kg','weight_change_kg','average_daily_gain_kg','purchase_cost','direct_recorded_expenses','partial_cost_floor','sale_revenue','sale_snapshot_break_even','sale_snapshot_provisional_profit_loss']
        views.append(view('animal_performance','Individual Animal Fattening & Weight Performance',cols,rows,
          ['Weight gain and daily gain use dated measurements; baseline is recorded entry weight.',
           'Partial cost floor includes purchase and directly tagged expenses; it is NOT total break-even or net profit.',
           'Batch-shared feed, labor, veterinary and overhead remain unallocated unless a verified attribution exists.',
           'Sale snapshot margin and profit/loss reflect the sale-time estimate, including its stated cost-allocation limitations. Blank means unsupported.'],
          [chart('Weight gain by animal','weight_change_kg',rows,'tag','kg'),chart('Average daily gain by animal','average_daily_gain_kg',rows,'tag','kg/day')]))
        # The detailed time series is loaded only for a chosen animal. This keeps the
        # main Fattening report compact while preserving complete dated observations.
        if payload.filters.animal_id:
            animal=next((a for a in fetch('v5_animals',remove_dates=True) if a.id==payload.filters.animal_id),None)
            batch=batches.get(animal.batch_id) if animal else None
            if animal and scope_matches_batch(batch):
                series=[]
                start=dt(animal.arrival_date or animal.created_at)
                original=num(animal.entry_weight_kg)
                previous_weight=original;previous_day=start
                if original is not None and start and within(start,payload.filters):
                    series.append({'animal_id':animal.id,'tag':animal.tag,'weighing_id':None,
                        'measured_on':iso(start),'reading_type':'Entry baseline',
                        'weight_kg':original,'change_since_previous_kg':None,'gain_since_entry_kg':0.0,
                        'days_since_previous':None,'interval_adg_kg_day':None,
                        'recorded_by':None,'notes':'Registered entry weight; not a scale observation'})
                observed=sorted((w for w in by_weight[animal.id]
                    if within(w.created_at,payload.filters)),key=lambda w:(w.created_at,w.id))
                # Recover the immediately preceding measurement for accurate interval change.
                before=sorted((w for w in by_weight[animal.id]
                    if payload.filters.from_date and dt(w.created_at)<payload.filters.from_date),key=lambda w:(w.created_at,w.id))
                if before:
                    previous_weight=num(before[-1].weight_kg)
                    previous_day=dt(before[-1].created_at)
                for w in observed:
                    day=dt(w.created_at);weight=num(w.weight_kg)
                    days=(day-previous_day).days if day and previous_day else None
                    delta=roundnum(weight-previous_weight,3) if weight is not None and previous_weight is not None else None
                    series.append({'animal_id':animal.id,'tag':animal.tag,'weighing_id':w.id,
                        'measured_on':iso(w.created_at),'reading_type':'Scale observation',
                        'weight_kg':weight,'change_since_previous_kg':delta,
                        'gain_since_entry_kg':roundnum(weight-original,3) if original is not None else None,
                        'days_since_previous':days,'interval_adg_kg_day':roundnum(delta/days,3) if delta is not None and days and days>0 else None,
                        'recorded_by':w.recorded_by,'notes':w.notes})
                    previous_weight=weight;previous_day=day
                cols2=['measured_on','reading_type','weight_kg','change_since_previous_kg',
                       'gain_since_entry_kg','days_since_previous','interval_adg_kg_day','recorded_by','notes']
                def points(key):
                    pts=[{'label':r['measured_on'][:10],'value':r[key]}
                         for r in series if r[key] is not None]
                    # All observations remain in detailed tables. For a long
                    # animal history the graph spans the full period, retaining
                    # both endpoints rather than truncating the latest values.
                    if len(pts)>75:
                        indices=sorted({round(i*(len(pts)-1)/74) for i in range(75)})
                        pts=[pts[i] for i in indices]
                    return pts
                views.append(view('animal_weight_history',f'Weight Progression — {animal.tag}',cols2,series,
                    ['Every dated scale observation is shown; the entry weight is explicitly marked as a registered baseline.',
                     'Changes are calculated between consecutive recorded measurements. Same-day interval ADG is left blank.',
                     'A date filter may omit earlier points; changes for the first included weighing reference the preceding actual observation where available.'],
                    [{'title':'Liveweight progression over time','type':'line','unit':'kg','points':points('weight_kg')},
                     {'title':'Total gain since entry over time','type':'line','unit':'kg','points':points('gain_since_entry_kg')},
                     {'title':'Interval average daily gain','type':'line','unit':'kg/day','points':points('interval_adg_kg_day')}]))
      elif job=='feeding':
        routines=pick('v5_routine_entries');batches=pick('v5_batches');items=pick('v5_stock_items');
        rows=[]
        for line in fetch('v5_feeding_lines',remove_dates=True):
            r=routines.get(line.routine_id)
            if not r or not within(r.created_at,payload.filters):continue
            batch=batches.get(r.batch_id)
            if not scope_matches_batch(batch):continue
            item=items.get(line.item_id)
            qty=num(line.quantity_kg)
            rows.append({'feeding_record_id':line.id,'date':iso(r.created_at),'project_id':batch.project_id if batch else None,
              'batch_id':r.batch_id,'shift':r.shift,'pen_id':r.pen_id,'feed_name':line.name or (item.name if item else None),
              'item_id':line.item_id,'ration_id':line.ration_id,'quantity_kg':qty,
              'inventory_reference_unit_cost':num(item.cost_per_unit) if item else None,
              'reference_currency':item.currency if item else None,
              'reference_value':roundnum(qty*num(item.cost_per_unit)) if item and qty is not None else None})
        cols=list(rows[0]) if rows else ['feeding_record_id','date','project_id','batch_id','feed_name','quantity_kg','inventory_reference_unit_cost','reference_currency','reference_value']
        views.append(view('feed_usage','Feed Consumption by Batch, Shift & Ingredient',cols,rows,
          ['Quantities come from completed feeding lines, not planned feed schedules.',
           'Inventory reference values are indicative, not actual feed expenses or cost of goods sold.',
           'Feed conversion ratio is unavailable without compatible verified intake and weight-gain periods.'],
          [chart('Recorded feed use by batch','quantity_kg',rows,'batch_id','kg'),chart('Feed by ingredient','quantity_kg',rows,'feed_name','kg')]))
      elif job=='stock':
        movements=fetch('v5_stock_movements',remove_dates=True);by_item=defaultdict(list)
        for move in movements:by_item[move.item_id].append(move)
        rows=[]
        for item in fetch('v5_stock_items',remove_dates=True):
            in_qty=out_qty=0.0
            for move in by_item[item.id]:
                if payload.filters.to_date and dt(move.transaction_date or move.created_at)>payload.filters.to_date:continue
                qty=num(move.quantity) or 0
                if move.direction in ('in','adjustment_in'):in_qty+=qty
                elif move.direction in ('out','adjustment_out'):out_qty+=qty
            balance=roundnum(in_qty-out_qty,3)
            rows.append({'item_id':item.id,'item':item.name,'category':item.category,'unit':item.unit,
              'recorded_receipts':roundnum(in_qty,3),'recorded_issues':roundnum(out_qty,3),
              'movement_balance':balance,'reorder_level':num(item.reorder_level),
              'reorder_alert':balance <= float(item.reorder_level or 0),'reference_cost_per_unit':num(item.cost_per_unit),
              'currency':item.currency,'reference_stock_value':roundnum(balance*num(item.cost_per_unit)) if item.cost_per_unit is not None else None})
        cols=list(rows[0]) if rows else ['item_id','item','unit','recorded_receipts','recorded_issues','movement_balance','reorder_level','reference_stock_value','currency']
        views.append(view('inventory_balances','Inventory Receipts, Issues & Stock Balances',cols,rows,
          ['Movement balance is reconstructed from recorded stock movements through the reporting cutoff.',
           'Reference stock value uses the item reference unit cost; it is NOT an audited FIFO/weighted-average valuation.',
           'Balances require complete opening inventory and movement history to represent actual on-hand stock.'],
          [chart('Reorder alerts by item','reorder_alert',[], 'item','items')]))
      elif job=='crop_yield':
        cycles=pick('v9_crop_cycles');projects=pick('v9_crop_projects');varieties=pick('v9_crop_varieties')
        lot_sales=defaultdict(list)
        for s in fetch('v9_crop_sales',remove_dates=True):lot_sales[s.lot_id].append(s)
        rows=[]
        for lot in fetch('v9_crop_harvest_lots',remove_dates=True):
            if not within(lot.harvested_on,payload.filters):continue
            cycle=cycles.get(lot.cycle_id);project=projects.get(lot.project_id)
            if payload.filters.project_id and lot.project_id!=payload.filters.project_id:continue
            if payload.filters.ranch_id and (not project or project.ranch_id!=payload.filters.ranch_id):continue
            if payload.filters.cycle_id and lot.cycle_id!=payload.filters.cycle_id:continue
            variety=varieties.get(cycle.variety_id) if cycle else None
            area=num(cycle.planted_area_ha) if cycle else None
            mk=num(lot.marketable_kg)
            sales=lot_sales[lot.id]
            quantity_sold=sum(num(s.quantity_kg) or 0 for s in sales if (not payload.filters.to_date or s.sold_on<=payload.filters.to_date))
            per_area=roundnum(mk/area,2) if mk is not None and area and area>0 else None
            rows.append({'harvest_lot_id':lot.id,'project_id':lot.project_id,'project_name':project.name if project else None,
              'cycle_id':lot.cycle_id,'crop':variety.name if variety else None,'variety':variety.variety if variety else None,
              'field_unit_id':lot.unit_id,'harvested_on':iso(lot.harvested_on),'harvest_pass':lot.pass_number,
              'planted_area_ha':area,'gross_kg':num(lot.gross_kg),'rejected_kg':num(lot.rejected_kg),
              'marketable_kg':mk,'yield_kg_per_planted_ha':per_area if lot.pass_number==1 else None,
              'grade':lot.grade,'sold_kg':roundnum(quantity_sold,3),
              'recorded_available_kg':num(lot.available_kg),'recorded_harvest_cost':num(lot.cost),'currency':lot.currency})
        cols=list(rows[0]) if rows else ['harvest_lot_id','project_id','crop','harvested_on','gross_kg','marketable_kg','recorded_available_kg','grade']
        views.append(view('crop_yields','Harvest Yield, Quality, Storage & Sales',cols,rows,
           ['Per-hectare yield on repeated-picking crops must use ALL relevant harvest passes over the crop cycle; one-pass ratio shown only when pass is first.',
            'Costs are recorded harvest-level costs only. Unsold produce is not recognized sales revenue.',
            'Area and product measurements are preserved in recorded units.'],
           [chart('Harvested output by crop','marketable_kg',rows,'crop','kg'),chart('Recorded output by project','marketable_kg',rows,'project_name','kg')]))
      elif job=='machinery':
        uses=defaultdict(list)
        for x in fetch('v6_machine_records',remove_dates=True):uses[x.machine_id].append(x)
        rows=[]
        for m in fetch('v6_machines',remove_dates=True):
            if payload.filters.ranch_id and m.ranch_id!=payload.filters.ranch_id:continue
            rec=[r for r in uses[m.id] if within(r.performed_on,payload.filters)]
            costs=defaultdict(float)
            for r in rec:
                if r.expense is not None:costs[r.currency]+=num(r.expense)
            rows.append({'asset_id':m.id,'asset_code':m.asset_code,'equipment':m.name,'category':m.category,
              'model':m.model,'ranch_id':m.ranch_id,'status':m.status,'activity_records':len(rec),
              'meter_reading_min_hours':min((num(r.meter_hours) for r in rec if r.meter_hours is not None),default=None),
              'meter_reading_max_hours':max((num(r.meter_hours) for r in rec if r.meter_hours is not None),default=None),
              'expense_by_currency':'; '.join(f'{c}: {v:,.2f}' for c,v in sorted(costs.items())) or None})
        cols=list(rows[0]) if rows else ['asset_id','asset_code','equipment','ranch_id','status','activity_records','expense_by_currency']
        views.append(view('machinery_utilization','Machinery Register, Activity & Expense',cols,rows,
            ['Meter readings are snapshots, not automatically additive operating hours.',
             'Equipment expenses remain grouped by source currency. Depreciation and fuel efficiency require supporting transactions.'],
            [chart('Machine activity records','activity_records',rows,'equipment','events')]))
      elif job=='breeding':
        animals=pick('v6_general_animals');groups=pick('v6_livestock_groups')
        outcomes=defaultdict(list)
        for c in fetch('v83_livestock_offspring_cohorts',remove_dates=True):
            if c.breeding_id:outcomes[c.breeding_id].append(c)
        rows=[]
        today=date.today()
        for b in fetch('v8_livestock_breeding_records',remove_dates=True):
            if not within(b.service_date,payload.filters):continue
            a=animals.get(b.animal_id);g=groups.get(b.group_id)
            if payload.filters.group_id and b.group_id!=payload.filters.group_id:continue
            if payload.filters.species and (not g or g.species!=payload.filters.species):continue
            children=outcomes[b.id]
            expected=b.expected_date
            rows.append({'breeding_id':b.id,'group_id':b.group_id,'species':g.species if g else None,
              'dam_tag':a.tag if a else None,'method':b.method,'sire_reference':b.sire_tag,
              'service_date':iso(b.service_date),'expected_delivery':iso(expected),
              'days_to_delivery':(expected-today).days if expected else None,'status':b.outcome,
              'documented_offspring':sum(c.live_count for c in children),
              'birth_or_hatch_dates':', '.join(str(c.born_on) for c in children) or None})
        cols=list(rows[0]) if rows else ['breeding_id','group_id','dam_tag','method','service_date','expected_delivery','days_to_delivery','status','documented_offspring']
        views.append(view('breeding_followups','Breeding Services, Expected Deliveries & Offspring',cols,rows,
            ['Delivery countdown uses the report generation date, not the animal service date.',
             'Expected dates are estimates. Offspring counts reflect recorded cohort outcomes only.'],
            [chart('Recorded offspring by species','documented_offspring',rows,'species','head')]))
      elif job=='poultry':
        groups=pick('v6_livestock_groups');sales=defaultdict(list)
        for s in fetch('v61_livestock_product_sales',remove_dates=True):sales[s.lot_id].append(s)
        rows=[]
        for lot in fetch('v61_livestock_product_lots',remove_dates=True):
            if not within(lot.collected_on,payload.filters):continue
            g=groups.get(lot.group_id)
            if payload.filters.group_id and lot.group_id!=payload.filters.group_id:continue
            if payload.filters.species and (not g or g.species!=payload.filters.species):continue
            rows.append({'lot_id':lot.id,'group_id':lot.group_id,'species':g.species if g else None,
              'product':lot.product,'unit':lot.unit,'collected_on':iso(lot.collected_on),
              'quantity_produced':num(lot.quantity_received),'quantity_sold':num(lot.quantity_sold),
              'remaining_quantity':roundnum(num(lot.quantity_received)-num(lot.quantity_sold)),
              'sale_transactions':len(sales[lot.id])})
        cols=list(rows[0]) if rows else ['lot_id','group_id','product','unit','quantity_produced','quantity_sold','remaining_quantity']
        views.append(view('livestock_product_yield','Livestock & Poultry Product Production and Balances',cols,rows,
            ['Product quantities may use eggs, litres, kg or other original units; totals must not mix unlike units.'],
            [chart('Product collection counts','sale_transactions',rows,'product','sales')]))
      elif job=='trials':
        trials=pick('v9_crop_trials');plots=fetch('v9_crop_trial_plots',remove_dates=True)
        rows=[]
        for p in plots:
            trial=trials.get(p.trial_id)
            if not trial or not within(trial.start_date,payload.filters):continue
            if payload.filters.project_id and trial.project_id!=payload.filters.project_id:continue
            rows.append({'trial_id':p.trial_id,'trial_name':trial.title,'project_id':trial.project_id,
              'trial_design':trial.design,'replications':trial.replications,'plot_id':p.id,'plot_code':p.code,
              'treatment':p.treatment,'replicate':p.replicate,'area_ha':num(p.area_ha),'is_control':p.is_control})
        cols=list(rows[0]) if rows else ['trial_id','trial_name','plot_code','treatment','replicate','area_ha','is_control']
        views.append(view('trial_design','Experiment Treatments, Plots & Replications',cols,rows,
            ['Treatment results and statistical claims require measured, plot-linked observations.',
             'This report describes recorded experimental design; it does not invent treatment effects.'],
            [chart('Recorded trial plots per treatment','plot_id',[], 'treatment','plots')]))
      elif job=='agronomy':
        projects=pick('v9_crop_projects');cycles=pick('v9_crop_cycles');varieties=pick('v9_crop_varieties')
        category={'crop_soils':'soil','crop_irrigation':'irrigation',
          'crop_nutrition':'nutrition','crop_protection':'protection',
          'crop_growth':'growth','crop_budget_detail':'costs',
          'crop_trial_detail':'trial_observations'}.get(section)
        entries=[];special=set()
        for r in fetch('v9_crop_records'):
            if category and r.section!=category:continue
            cycle=cycles.get(r.cycle_id);v=varieties.get(cycle.variety_id) if cycle else None
            p=projects.get(r.project_id)
            if payload.filters.ranch_id and (not p or p.ranch_id!=payload.filters.ranch_id):continue
            info=r.data if isinstance(r.data,dict) else {}
            special.update(k for k in info if isinstance(k,str) and not any(z in k.lower() for z in ('secret','password','token')))
            entries.append((r,p,v,info))
        base=['record_id','date','project_id','project','crop','variety','field_unit_id','crop_cycle_id','section','activity',
              'quantity','unit','unit_cost','additional_cost','recorded_expense','currency','reference','notes']
        fields=base+sorted(special)
        rows=[]
        for r,p,v,info in entries:
            row={'record_id':r.id,'date':iso(r.performed_on),'project_id':r.project_id,'project':p.name if p else None,
              'crop':v.name if v else None,'variety':v.variety if v else None,'field_unit_id':r.unit_id,
              'crop_cycle_id':r.cycle_id,'section':r.section,'activity':r.title,
              'quantity':num(r.quantity),'unit':r.unit,'unit_cost':num(r.unit_cost),
              'additional_cost':num(r.other_cost),'recorded_expense':roundnum((num(r.quantity) or 0)*(num(r.unit_cost) or 0)+(num(r.other_cost) or 0)) if r.unit_cost is not None or r.other_cost is not None else None,
              'currency':r.currency,'reference':r.reference,'notes':r.notes}
            for key in special:
                value=info.get(key)
                row[key]=str(value) if isinstance(value,(dict,list)) else value
            rows.append(row)
        views.append(view('agronomic_details','Detailed Crop Operations & Scientific Measurements',fields,rows,
          ['Detailed agronomic parameters are extracted from the persisted field-specific metadata for each activity.',
           'Values such as pH, NDVI, growth, nutrient concentration and rainfall are not added across incompatible measurement scales.',
           'Expense calculations only use recorded unit costs and other costs; blank inputs remain unknown.'],
          [chart('Recorded operations by section','record_id',[], 'section','operations')]))
      elif job=='finance':
        grouped=defaultdict(lambda:{'cost':0.0,'revenue':0.0,'transactions':0})
        for e in fetch('v5_finance_entries'):
            k=(str(e.currency or 'Unspecified'),e.category,e.batch_id)
            rec=grouped[k];rec['transactions']+=1
            if e.kind in ('cost','revenue'):rec[e.kind]+=num(e.amount) or 0
        rows=[{'currency':c,'category':category,'batch_id':batch,'transactions':v['transactions'],
               'recorded_revenue':roundnum(v['revenue']),'recorded_cost':roundnum(v['cost']),
               'recorded_difference':roundnum(v['revenue']-v['cost'])} for (c,category,batch),v in grouped.items()]
        cols=list(rows[0]) if rows else ['currency','category','batch_id','transactions','recorded_revenue','recorded_cost','recorded_difference']
        views.append(view('financial_ledger','Financial Transactions by Category & Currency',cols,rows,
           ['Recorded difference is not audited net profit. Do not add source sales again when they are already posted to Finance.',
            'Only like currencies may be compared. Other cost allocations may not be captured in the Finance ledger.']))
      elif job=='project_position':
        rows=[]
        # Fattening: actual Finance ledger entries linked to each batch. Those figures
        # must not be mixed with acquisition costs already posted in the ledger.
        if ok('v5_finance_entries') and ok('v5_batches') and ok('v5_projects'):
            batch_map=defaultdict(list)
            for b in fetch('v5_batches',remove_dates=True):batch_map[b.project_id].append(b.id)
            entries=fetch('v5_finance_entries')
            for p in fetch('v5_projects',remove_dates=True):
                if payload.filters.project_id and p.id!=payload.filters.project_id:continue
                if payload.filters.ranch_id and p.ranch_id!=payload.filters.ranch_id:continue
                batch_ids=set(batch_map[p.id]);bycur=defaultdict(lambda:{'cost':0.0,'revenue':0.0})
                for e in entries:
                    if e.batch_id in batch_ids and e.kind in ('cost','revenue'):
                        bycur[e.currency][e.kind]+=num(e.amount) or 0
                for cur,t in bycur.items():
                    rows.append({'module':'Animal Fattening','project_id':p.id,'project':p.name,'currency':cur,
                      'approved_or_planned_budget':num(p.budget) if p.currency==cur else None,
                      'recorded_revenue':roundnum(t['revenue']),'recorded_cost':roundnum(t['cost']),
                      'recorded_contribution':roundnum(t['revenue']-t['cost']),
                      'financial_basis':'Batch-linked Finance entries; may omit unallocated costs'})
        # Crop production: directly linked recorded operations and sales, not Finance
        # entries, because Finance reflects those same source transactions.
        if section not in ('fattening_project_costs','fattening_sales') and ok('v9_crop_projects') and ok('v9_crop_records') and ok('v9_crop_sales'):
            records=fetch('v9_crop_records');sales=fetch('v9_crop_sales');harvests=fetch('v9_crop_harvest_lots')
            for p in fetch('v9_crop_projects',remove_dates=True):
                if payload.filters.project_id and p.id!=payload.filters.project_id:continue
                if payload.filters.ranch_id and p.ranch_id!=payload.filters.ranch_id:continue
                bycur=defaultdict(lambda:{'cost':0.0,'revenue':0.0})
                for r in records:
                    if r.project_id!=p.id:continue
                    cost=(num(r.quantity) or 0)*(num(r.unit_cost) or 0)+(num(r.other_cost) or 0)
                    bycur[r.currency]['cost']+=cost
                for h in harvests:
                    if h.project_id==p.id and h.cost is not None:bycur[h.currency]['cost']+=num(h.cost)
                for s in sales:
                    if s.project_id==p.id:
                        bycur[s.currency]['revenue']+=num(s.gross) or 0
                        bycur[s.currency]['cost']+=num(s.selling_cost) or 0
                for cur,t in bycur.items():
                    rows.append({'module':'Crop Farming','project_id':p.id,'project':p.name,'currency':cur,
                      'approved_or_planned_budget':num(p.planned_budget) if p.currency==cur else None,
                      'recorded_revenue':roundnum(t['revenue']),'recorded_cost':roundnum(t['cost']),
                      'recorded_contribution':roundnum(t['revenue']-t['cost']),
                      'financial_basis':'Crop operation, harvest and sale records; excludes unallocated overhead'})
        if section not in ('fattening_project_costs','fattening_sales','crop_finance') and ok('v61_livestock_projects') and ok('v61_livestock_project_costs'):
            costs=fetch('v61_livestock_project_costs')
            for p in fetch('v61_livestock_projects',remove_dates=True):
                if payload.filters.project_id and p.id!=payload.filters.project_id:continue
                if payload.filters.ranch_id and p.ranch_id!=payload.filters.ranch_id:continue
                bycur=defaultdict(float)
                for c in costs:
                    if c.project_id==p.id:bycur[c.currency]+=num(c.amount) or 0
                for cur,total in bycur.items():
                    rows.append({'module':'Livestock & Poultry','project_id':p.id,'project':p.name,
                     'currency':cur,'approved_or_planned_budget':None,'recorded_revenue':None,
                     'recorded_cost':roundnum(total),'recorded_contribution':None,
                     'financial_basis':'Direct project expenses only; product revenue cannot be attributed without verified link'})
        cols=list(rows[0]) if rows else ['module','project_id','project','currency','approved_or_planned_budget','recorded_revenue','recorded_cost','recorded_contribution','financial_basis']
        views.append(view('project_financial_position','Project Financial Position by Currency',cols,rows,
         ['Recorded contribution = recorded revenue minus explicitly linked recorded costs; it is NOT audited net profit or necessarily full-life project margin.',
          'Missing shared expenses, other procurements, inventory valuation and unallocated indirect costs remain outside the calculation.',
          'Projects without verifiable revenue or cost attribution show blank results instead of fabricated profit.'],
          [chart('Project cost by module','recorded_cost',rows,'module','original currencies (do not sum across currencies)') if len({x['currency'] for x in rows})<=1 else {'title':'Costs by project','type':'bar','unit':'incompatible currencies — omitted','points':[]}]))
      elif job=='projects':
        rows=[]
        sources=[('v5_projects','Animal Fattening'),('v9_crop_projects','Crop Farming'),('v61_livestock_projects','Livestock & Poultry')]
        if section.startswith('fattening_'):sources=sources[:1]
        for source,kind in sources:
            for p in fetch(source,remove_dates=True):
                if payload.filters.project_id and p.id!=payload.filters.project_id:continue
                if payload.filters.ranch_id and p.ranch_id!=payload.filters.ranch_id:continue
                rows.append({'module':kind,'project_id':p.id,'project':p.name,'ranch_id':p.ranch_id,
                  'start_date':iso(p.start_date),'end_date':iso(p.end_date),
                  'status':getattr(p,'status',None),'planned_budget':num(getattr(p,'planned_budget',getattr(p,'budget',None))),
                  'currency':getattr(p,'currency',None)})
        cols=list(rows[0]) if rows else ['module','project_id','project','ranch_id','start_date','status','planned_budget','currency']
        views.append(view('project_portfolio','Project Register & Budget Commitments',cols,rows,
           ['Planned budget and actual expenses are different. A project budget is not treated as a cost.',
            'Project identifiers are scoped to their owning module. Cross-module IDs are not interchangeable.'],
           [chart('Registered projects by module','project_id',[],'module','projects')]))
      elif job=='sales':
        rows=[]
        for source,kind,dtfield,amountfield,buyerfield in [('v5_animal_sales','Animal Fattening','sale_date','gross_amount','buyer_name'),
                       ('v9_crop_sales','Crop Farming','sold_on','gross','buyer'),
                       ('v61_livestock_product_sales','Livestock Products','sold_on','gross','buyer')]:
            for s in fetch(source):
                if hasattr(s,'status') and s.status!='completed':continue
                rows.append({'source':kind,'sale_id':s.id,'buyer':getattr(s,buyerfield,None),
                    'date':iso(getattr(s,dtfield)),'quantity':num(getattr(s,'quantity_kg',getattr(s,'quantity',None))),
                    'unit': 'kg' if hasattr(s,'quantity_kg') else 'source unit',
                    'revenue':num(getattr(s,amountfield)),'currency':s.currency})
        cols=list(rows[0]) if rows else ['source','sale_id','buyer','date','quantity','unit','revenue','currency']
        views.append(view('sales_detail','Sales by Buyer, Product Domain & Currency',cols,rows,
            ['Sales are operational transactions and must not be added again to recognized Finance revenue.',
             'Quantities in incompatible units cannot be summed together.']))
      elif job=='routine':
        rows=[]
        for src,description in [('v5_task_completions','Staff Tasks'),('v83_livestock_routine_completions','Livestock Routine'),('v9_crop_completions','Crop Farming Routine')]:
            for x in fetch(src):
                rows.append({'module':description,'completion_id':x.id,'task_or_routine_id':getattr(x,'task_id',getattr(x,'template_id',getattr(x,'routine_id',None))),
                   'completed_on':iso(getattr(x,'occurrence_date',getattr(x,'completed_on',getattr(x,'day',None)))),
                   'completed_by':getattr(x,'completed_by',None),'status':getattr(x,'status','completed')})
        cols=list(rows[0]) if rows else ['module','completion_id','task_or_routine_id','completed_on','completed_by','status']
        views.append(view('activity_completion','Daily Work & Routine Completion History',cols,rows,
            ['These are recorded completions, not an attendance or employee-performance score.',
             'Overdue rates require expanding recurring schedules into due occurrences.']))
    return views,warnings
