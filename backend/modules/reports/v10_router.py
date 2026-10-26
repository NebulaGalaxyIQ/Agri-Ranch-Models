"""V10 read-oriented reporting API. Organization from trusted membership context only."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from modules.organizations.service import context
from modules.fattening.models import permission
from modules.reports.v10_models import SavedReport,ReportRun,ReportSchedule
from modules.reports.v10_schemas import ReportRequest,ExportRequest,SavedReportIn,ScheduleIn
from modules.reports.v10_analysis import label
from modules.reports.v10_service import (catalogue,all_tables,report_sources,read_report,export_datasets,
    make_pdf,make_excel,make_csv_zip,DEFINITIONS,models_by_table,columns,q_for,date_column,serialize,primary_key)

router=APIRouter(prefix='/api/v10/reports',tags=['Advanced Reports'])

def access(db,ctx):
    permission(ctx,db,'analytics.read')
    return ctx[0],ctx[1],ctx[2]

@router.get('/catalog')
def catalog(db:Session=Depends(get_db),ctx=Depends(context)):
    access(db,ctx)
    return catalogue(ctx)

@router.get('/filters')
def filters(section_id:str,db:Session=Depends(get_db),ctx=Depends(context)):
    access(db,ctx)
    sources=report_sources(section_id,ctx)
    models=models_by_table()
    fields=set()
    dates=set()
    for tab in sources:
        cls=models.get(tab)
        if cls:
            fields.update(c for c in ('project_id','ranch_id','batch_id','group_id','cycle_id','animal_id','item_id','machine_id','trial_id','lot_id','field_id','house_id','status','species','currency') if c in cls.__table__.columns)
            dates.update(c.name for c in cls.__table__.columns if c.name in ('created_at','day','date','weigh_date','sold_on','start_date','due_date','harvested_on','service_date'))
    return {'section_id':section_id,'available_fields':sorted(fields),'date_fields':sorted(dates),
      'date_note':'Date filters use the first relevant source date column per dataset, or your explicit selection when that column exists.'}

@router.get('/source/{table_name}/{record_id}')
def source_detail(table_name:str,record_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    access(db,ctx)
    if table_name not in all_tables(ctx):raise HTTPException(404,'Source is unavailable')
    model=models_by_table()[table_name]
    row=db.query(model).filter(primary_key(model)==record_id,model.organization_id==ctx[1].id).first()
    if not row:raise HTTPException(404,'Source record not found')
    return {'source':label(table_name),'record':serialize(row,columns(model)),
            'note':'Original persisted operational record (read-only).'}

@router.post('/query')
def query(payload:ReportRequest,db:Session=Depends(get_db),ctx=Depends(context)):
    access(db,ctx)
    return read_report(db,ctx,payload)

@router.post('/export')
def export(payload:ExportRequest,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,member=access(db,ctx)
    selected,omitted,total=export_datasets(db,ctx,payload)
    if not selected and not omitted:raise HTTPException(404,'No authorized data source was found for this report')
    base=read_report(db,ctx,payload,include_rows=False)
    if payload.mode=='summary':
        # Summary exports still document data sources and totals; detailed mode includes all matching rows.
        selected_summary=selected
    else:selected_summary=selected
    if payload.format=='pdf':
        stream=make_pdf(base,selected_summary,omitted,payload.mode,payload.include_charts,payload.paper,payload.orientation)
        mime='application/pdf';ext='pdf'
    elif payload.format=='xlsx':
        stream=make_excel(base,selected_summary,omitted,payload.mode,payload.include_charts)
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';ext='xlsx'
    else:
        stream=make_csv_zip(selected_summary);mime='application/zip';ext='zip'
    db.add(ReportRun(organization_id=org.id,requested_by=actor.id,section_id=payload.section_id,
                      format=payload.format,filters=payload.filters.model_dump(mode='json'),row_count=total,status='completed'))
    db.commit()
    # Bytes only exist during the request and are not persisted to public storage.
    return StreamingResponse(stream,media_type=mime,headers={
        'Content-Disposition':f'attachment; filename="GHR_{payload.section_id.replace(":","_")}_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.{ext}"',
        'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

@router.get('/saved')
def saved(db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=access(db,ctx)
    rows=db.query(SavedReport).filter(SavedReport.organization_id==org.id).order_by(SavedReport.id.desc()).limit(150).all()
    return {'items':[{'id':x.id,'title':x.title,'section_id':x.section_id,'configuration':x.configuration,
                      'visibility':x.visibility,'created_by':x.created_by} for x in rows if x.created_by==actor.id or x.visibility=='organization']}

@router.post('/saved',status_code=201)
def save(p:SavedReportIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=access(db,ctx)
    report_sources(p.section_id,ctx)
    if len(str(p.configuration))>9000:raise HTTPException(422,'Saved report settings are too large')
    row=SavedReport(organization_id=org.id,created_by=actor.id,title=p.title,section_id=p.section_id,
                    configuration=p.configuration,visibility=p.visibility)
    db.add(row);db.commit();db.refresh(row)
    return {'id':row.id,'title':row.title,'section_id':row.section_id}

@router.delete('/saved/{saved_id}')
def delete_saved(saved_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=access(db,ctx)
    row=db.query(SavedReport).filter_by(id=saved_id,organization_id=org.id,created_by=actor.id).first()
    if row is None:raise HTTPException(404,'Saved report not found')
    db.query(ReportSchedule).filter_by(saved_report_id=row.id,organization_id=org.id).delete()
    db.delete(row);db.commit();return {'deleted':saved_id}

@router.get('/runs')
def runs(db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=access(db,ctx)
    rows=db.query(ReportRun).filter_by(organization_id=org.id,requested_by=actor.id).order_by(ReportRun.id.desc()).limit(100).all()
    return {'items':[{'id':r.id,'section_id':r.section_id,'format':r.format,'filters':r.filters,'rows':r.row_count,
                      'created_at':r.created_at.isoformat() if r.created_at else None,'status':r.status} for r in rows]}

@router.get('/schedules')
def schedules(db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=access(db,ctx)
    rows=db.query(ReportSchedule).filter_by(organization_id=org.id,created_by=actor.id).order_by(ReportSchedule.id.desc()).limit(100).all()
    return {'items':[{'id':r.id,'saved_report_id':r.saved_report_id,'cadence':r.cadence,'timezone':r.timezone,
                      'format':r.format,'enabled':r.enabled,'status':'Configuration stored; delivery requires an external scheduler.'} for r in rows]}

@router.post('/schedules',status_code=201)
def create_schedule(p:ScheduleIn,db:Session=Depends(get_db),ctx=Depends(context)):
    actor,org,_=access(db,ctx)
    saved=db.query(SavedReport).filter_by(id=p.saved_report_id,organization_id=org.id,created_by=actor.id).first()
    if not saved:raise HTTPException(404,'Your saved report was not found')
    # This version stores configuration only. Never imply a task is active without a worker.
    row=ReportSchedule(organization_id=org.id,created_by=actor.id,saved_report_id=saved.id,
          cadence=p.cadence,timezone=p.timezone,format=p.format,enabled=False)
    db.add(row);db.commit();db.refresh(row)
    return {'id':row.id,'enabled':False,'message':'Schedule saved but inactive. Connect an authorized background scheduler before enabling delivery.'}
