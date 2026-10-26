"""Organization-scoped recorded performance insights, not predictive clinical advice.

Only compare actual dated observations; never manufacture measurement dates or assign
batch feed totals to individual animals as though consumption were measured.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from statistics import median
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, utcnow
from modules.organizations.service import V5Batch, V5Ranch, V5Routine, context
from modules.fattening.models import V5Animal, WeightObservation, FinanceEntry, StockItem, StockMovement, Ration, permission
from modules.fattening.service import V5Project, FeedPlan, FeedingLine

router=APIRouter(prefix='/api/v5',tags=['v5-insights'])

def report(db,org,project_id=None):
    projects=db.query(V5Project).filter_by(organization_id=org.id).all()
    if project_id is not None and all(p.id!=project_id for p in projects):raise HTTPException(404,'Project not found')
    ranches={r.id:r for r in db.query(V5Ranch).filter_by(organization_id=org.id)}
    projects_by_id={p.id:p for p in projects}
    batches=[b for b in db.query(V5Batch).filter_by(organization_id=org.id).all() if project_id is None or b.project_id==project_id]
    batch_by_id={b.id:b for b in batches}
    animals=db.query(V5Animal).filter_by(organization_id=org.id).all()
    animals=[a for a in animals if a.batch_id in batch_by_id]
    ids=[a.id for a in animals]
    weights=(db.query(WeightObservation).filter(WeightObservation.organization_id==org.id,WeightObservation.animal_id.in_(ids))
             .order_by(WeightObservation.created_at,WeightObservation.id).all()) if ids else []
    by_animal=defaultdict(list)
    for w in weights:by_animal[w.animal_id].append(w)
    rows=[]
    for a in animals:
        b=batch_by_id[a.batch_id]
        history=by_animal[a.id]
        start_kg=None;end_kg=None;start_date=None;end_date=None;source=None
        if len(history)>1:
            first,last=history[0],history[-1]
            start_kg,end_kg=first.weight_kg,last.weight_kg
            start_date,end_date=first.created_at.date(),last.created_at.date()
            source='dated weight observations'
        elif a.arrival_date and a.entry_weight_kg is not None and a.current_weight_kg is not None:
            start_kg,end_kg=a.entry_weight_kg,a.current_weight_kg
            start_date,end_date=a.arrival_date,date.today()
            source='entry weight and arrival date'
        elapsed=(end_date-start_date).days if start_date and end_date else None
        # Same-day measurements, missing dates, and future arrivals have no meaningful ADG.
        adg=round(float((end_kg-start_kg)/Decimal(elapsed)),3) if elapsed is not None and elapsed>=1 else None
        gain=round(float(a.current_weight_kg-a.entry_weight_kg),3) if a.entry_weight_kg is not None and a.current_weight_kg is not None else None
        rows.append({'animal_id':a.id,'tag':a.tag,'species':a.species,'batch_id':b.id,'batch':b.name,
              'project_id':b.project_id,'project':projects_by_id[b.project_id].name if b.project_id in projects_by_id else 'Unassigned legacy batch',
              'status':a.status,'entry_kg':float(a.entry_weight_kg) if a.entry_weight_kg is not None else None,
              'current_kg':float(a.current_weight_kg) if a.current_weight_kg is not None else None,
              'gain_kg':gain,'adg_kg_per_day':adg,'elapsed_days':elapsed,'measurement_source':source,
              'purchase_cost':float(a.purchase_cost or 0),'assessment':'Not assessed','advice':'Record weight on another date to establish a reliable trend.'})
    # Only compare to peers in the SAME batch + species, and only from dated observations.
    by_peer=defaultdict(list)
    for x in rows:
        if x['status']=='active' and x['adg_kg_per_day'] is not None and x['elapsed_days']>=7:
            by_peer[(x['batch_id'],x['species'])].append(x['adg_kg_per_day'])
    for x in rows:
        if x['status']!='active':x['assessment']='Inactive';x['advice']='Historical record retained.';continue
        adg=x['adg_kg_per_day']; peers=by_peer[(x['batch_id'],x['species'])]
        if adg is None or x['elapsed_days']<7:
            x['assessment']='Insufficient observations';x['advice']='Reweigh after at least seven days. Do not infer growth from one measurement.'
        elif adg<=0:
            x['assessment']='Needs review';x['advice']='Verify the scale and dates; review feed, water and health records. Consult a qualified veterinarian if warranted.'
        elif len(peers)<3:
            x['assessment']='Growth recorded';x['advice']='Continue weighing; at least three comparable animals are needed for a relative batch assessment.'
        else:
            typical=median(peers)
            if typical<=0:
                x['assessment']='Needs review';x['advice']='Batch growth trend is non-positive; verify weights and check husbandry conditions.'
            elif adg < typical*0.75:
                x['assessment']='Below batch peers';x['advice']='Verify measurements; review ration, access to feed and water, health and competition at the trough.'
            elif adg >=typical*1.15:
                x['assessment']='Above batch peers';x['advice']='Maintain the feeding plan and continue regular weighing; check feed efficiency with measured consumption data.'
            else:
                x['assessment']='Within batch range';x['advice']='Maintain routine and monitor the next weighing against the project target.'
    cash=db.query(FinanceEntry).filter_by(organization_id=org.id).all()
    cash=[x for x in cash if project_id is None or x.batch_id in batch_by_id]
    per_currency=defaultdict(lambda:{'cost':Decimal(0),'revenue':Decimal(0),'by_category':defaultdict(lambda:Decimal(0))})
    for x in cash:
        f=per_currency[x.currency]
        if x.kind in ('cost','revenue'):f[x.kind]+=x.amount
        f['by_category'][(x.kind,x.category)]+=x.amount
    active_head_count=sum(a.status=='active' for a in animals)
    live_weight_kg=sum(a.current_weight_kg for a in animals if a.status=='active' and a.current_weight_kg is not None)
    # Cost ratios use recorded cash costs only; these do NOT claim full livestock cost price.
    accounts=[{'currency':cur,'cost_per_active_head_recorded':round(float(x['cost'])/active_head_count,2) if active_head_count else None,
               'cost_per_current_live_kg_recorded':round(float(x['cost'])/float(live_weight_kg),2) if live_weight_kg>0 and all(a.current_weight_kg is not None for a in animals if a.status=='active') else None,
               'cost':float(x['cost']),'revenue':float(x['revenue']),
               'net_cash_records':float(x['revenue']-x['cost']),
               'categories':[{'kind':kind,'category':cat,'amount':float(amount)} for (kind,cat),amount in sorted(x['by_category'].items())]}
              for cur,x in sorted(per_currency.items())]
    projects_data=[]
    for p in projects:
        if project_id and p.id!=project_id:continue
        pb=[b for b in batches if b.project_id==p.id]
        members=[a for a in animals if a.batch_id in {b.id for b in pb}]
        projects_data.append({'id':p.id,'name':p.name,'ranch':ranches[p.ranch_id].name if p.ranch_id in ranches else None,
              'status':p.status,'start':p.start_date.isoformat(),'end':p.end_date.isoformat() if p.end_date else None,
              'target_kg':float(p.target_weight_kg) if p.target_weight_kg else None,'target_animals':p.target_animals,
              'batches':len(pb),'active_animals':sum(a.status=='active' for a in members),'batch_capacity':sum(b.capacity or 0 for b in pb)})
    feeding=db.query(V5Routine).filter_by(organization_id=org.id,category='feeding').all()
    feeding=[x for x in feeding if x.batch_id in batch_by_id]
    feeding_kg=sum(Decimal(str(x.quantity)) for x in feeding if x.quantity is not None and x.unit=='kg')
    recorded_costs=sum((a.purchase_cost or Decimal(0)) for a in animals)
    from modules.fattening.router import AnimalSale
    completed_sales=db.query(AnimalSale).filter_by(organization_id=org.id,status='completed').all()
    completed_sales=[s for s in completed_sales if s.animal_id in ids]
    sales_totals=defaultdict(lambda:Decimal(0))
    for sale in completed_sales:sales_totals[sale.currency]+=sale.gross_amount
    return {'organization':org.name,'generated_at':utcnow().isoformat(),'project_id':project_id,
            'hierarchy':projects_data,'batch_count':len(batches),'animal_count':len(animals),'animal_performance':rows,
            'assessments':{status:sum(x['assessment']==status for x in rows) for status in sorted({x['assessment'] for x in rows})},
            'feeding_events':len(feeding),'actual_feed_recorded_kg':float(feeding_kg),
            'animal_purchase_cost_recorded':float(recorded_costs),'completed_animal_sales':len(completed_sales),'animal_sales_by_currency':[{'currency':c,'amount':float(v)} for c,v in sorted(sales_totals.items())],
            'finance':accounts,
            'alerts':[{'level':'review','animal':x['tag'],'message':x['advice']} for x in rows if x['assessment'] in {'Needs review','Below batch peers'}],
            'notes':['ADG is calculated from dated weight observations at least one day apart, or from known entry weight and arrival date.',
              'Comparative assessments require at least 7 days and 3 comparable animals in the same batch/species; labels are relative, not veterinary diagnoses.',
              'Animal procurement is automatically entered in finance once during registration; the animal purchase subtotal is a separate descriptive view, not an additional expense.',
              'Batch feeding is not measured individual intake. No individual feed-conversion ratios are inferred.',
              'Different currencies are kept separate. No unsupported conversion is applied.',
              'Recorded cost per head and per current live kilogram exclude uncaptured costs and are not true production cost unless records are complete.']}

@router.get('/analytics/performance')
def performance(project_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    _,org,_=permission(ctx,db,'analytics.read')
    return report(db,org,project_id)

@router.get('/analytics/performance/export')
def performance_export(format:str='csv',project_id:int|None=None,db:Session=Depends(get_db),ctx=Depends(context)):
    """Complete scoped operations performance report with transparent data limits."""
    import csv,io
    from fastapi.responses import StreamingResponse
    _,org,_=permission(ctx,db,'analytics.read')
    if format not in ('csv','pdf'):raise HTTPException(422,'Supported formats: csv or pdf')
    data=report(db,org,project_id)
    cols=['tag','species','project','batch','status','entry_kg','current_kg','gain_kg','adg_kg_per_day','elapsed_days','measurement_source','assessment','advice']
    if format=='csv':
        out=io.StringIO();w=csv.writer(out)
        def safe(x):
            v='' if x is None else str(x)
            return "'"+v if v.startswith(('=','+','-','@','\t','\r')) else v
        w.writerow(['Ranch Livestock Performance','Organization',safe(data['organization']),'Generated',data['generated_at']])
        w.writerow([]);w.writerow(['Ranch / project / batch overview']);w.writerow(['Project','Ranch','Batches','Active animals','Capacity','Target kg'])
        for x in data['hierarchy']:w.writerow([safe(x['name']),safe(x['ranch']),x['batches'],x['active_animals'],x['batch_capacity'],x['target_kg']])
        w.writerow([]);w.writerow(['Animal sales (already included as Finance revenue)']);w.writerow(['Currency','Amount']);[w.writerow([v['currency'],v['amount']]) for v in data['animal_sales_by_currency']];w.writerow([]);w.writerow(['Animal weight and relative performance']);w.writerow(cols)
        for a in data['animal_performance']:w.writerow([safe(a.get(k)) for k in cols])
        w.writerow([]);w.writerow(['Financial records — currencies never mixed']);w.writerow(['Currency','Recorded costs','Recorded revenue','Recorded net cash','Cost per active head (cash records)','Cost per known live kg (cash records)','Notes'])
        for x in data['finance']:w.writerow([safe(x['currency']),x['cost'],x['revenue'],x['net_cash_records'],x['cost_per_active_head_recorded'],x['cost_per_current_live_kg_recorded'],'Cash records, not full profit'])
        w.writerow([]);w.writerow(['Financial category details']);w.writerow(['Currency','Type','Category','Amount'])
        for x in data['finance']:
            for y in x['categories']:w.writerow([safe(x['currency']),y['kind'],safe(y['category']),y['amount']])
        w.writerow([]);w.writerow(['Activity and purchase cost']);w.writerow(['Feed events',data['feeding_events']]);w.writerow(['Feeding kg recorded',data['actual_feed_recorded_kg']]);w.writerow(['Animal purchase cost recorded (descriptive subtotal; included in finance when registered under V5.4)',data['animal_purchase_cost_recorded']])
        w.writerow([]);w.writerow(['Management flags']);w.writerow(['Animal','Recommendation'])
        for a in data['alerts']:w.writerow([safe(a['animal']),safe(a['message'])])
        w.writerow([]);w.writerow(['Limitations / methodology']);[w.writerow([x]) for x in data['notes']]
        return StreamingResponse(iter([out.getvalue().encode('utf-8-sig')]),media_type='text/csv',
              headers={'Content-Disposition':'attachment; filename="livestock-performance.csv"'})
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,LongTable,KeepTogether
    from xml.sax.saxutils import escape
    page=landscape(A4);out=io.BytesIO();styles=getSampleStyleSheet();body=styles['BodyText']
    def txt(v):return Paragraph(escape('—' if v is None else str(v))[:360],body)
    story=[Paragraph('Ranch Operations & Livestock Performance',styles['Title']),
           Paragraph(escape(data['organization']),styles['Heading2']),
           Paragraph('Generated: '+escape(data['generated_at']),styles['Normal']),Spacer(1,12)]
    def table(title,headers,rows,widths=None):
        story.append(Paragraph(title,styles['Heading2']))
        dataset=[[txt(v) for v in headers]]+[[txt(v) for v in row] for row in rows]
        if len(dataset)==1:story.append(Paragraph('No records available.',styles['Normal']));return
        t=LongTable(dataset,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3ec')),
             ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#cedacf')),
             ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5)]))
        story.extend([t,Spacer(1,12)])
    table('Projects and batch capacities',['Project','Ranch','Batches','Active animals','Capacity'],[
        [x['name'],x['ranch'],x['batches'],x['active_animals'],x['batch_capacity']] for x in data['hierarchy']],[240,220,90,105,100])
    story.append(Paragraph(f"Feeding recorded: {data['actual_feed_recorded_kg']:.3f} kg from {data['feeding_events']} event(s).",body))
    story.append(Paragraph('Completed animal sales: '+str(data['completed_animal_sales'])+'; revenue included in Finance (do not add twice).',body))
    story.append(Paragraph('Registered animal purchase subtotal (already included in V5.4 finance entries): '+str(data['animal_purchase_cost_recorded']),body))
    story.append(Spacer(1,12))
    table('Animal weight performance',['Animal','Batch','Entry kg','Current kg','ADG kg/day','Assessment'],[
        [x['tag'],x['batch'],x['entry_kg'],x['current_kg'],x['adg_kg_per_day'],x['assessment']] for x in data['animal_performance']],[130,150,85,95,100,195])
    table('Recorded finance',['Currency','Costs','Revenue','Recorded net'],[
        [x['currency'],x['cost'],x['revenue'],x['net_cash_records']] for x in data['finance']],[140,195,200,220])
    table('Financial category breakdown',['Currency','Kind','Category','Amount'],[
        [x['currency'],y['kind'],y['category'],y['amount']] for x in data['finance'] for y in x['categories']],[130,120,315,190])
    table('Attention and recommended review',['Animal','Next action'],[
        [x['animal'],x['message']] for x in data['alerts']],[130,625])
    story.append(Paragraph('Interpretation and limitations',styles['Heading2']))
    story.extend([Paragraph(escape(n),body) for n in data['notes']])
    pdf=SimpleDocTemplate(out,pagesize=page,leftMargin=40,rightMargin=40,topMargin=34,bottomMargin=34,
        title='Livestock management performance report')
    pdf.build(story);out.seek(0)
    return StreamingResponse(out,media_type='application/pdf',
      headers={'Content-Disposition':'attachment; filename="livestock-performance.pdf"'})
