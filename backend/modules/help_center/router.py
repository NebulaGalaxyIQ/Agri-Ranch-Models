"""Help Center message APIs, private to platform administration."""
from __future__ import annotations
from fastapi import APIRouter,Depends,File,UploadFile,HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import get_db,User,utcnow
from modules.organizations.models import Organization
from modules.organizations.service import context,licensed,owner
from modules.help_center.models import SupportTicket,SupportMessage,SupportAttachment
from modules.platform_admin.service import TicketIn, ReplyIn, StatusIn
from modules.help_center.service import _ticket,_ticket_list,_ticket_for_user,organization_help_retired,_attachments,_save_attachment,_download
from auth import audit
router=APIRouter(prefix='/api/v5',tags=['Help Center'])

@router.get('/help/tickets',dependencies=[Depends(organization_help_retired)])
def help_tickets(db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,m=ctx;licensed(db,org,False)
 q=db.query(SupportTicket).filter_by(organization_id=org.id)
 if m.role not in ('org_admin','manager'):q=q.filter_by(created_by=user.id)
 return {'items':_ticket_list(db,q.order_by(SupportTicket.updated_at.desc(),SupportTicket.id.desc()).limit(150).all())}


@router.post('/help/tickets',status_code=201,dependencies=[Depends(organization_help_retired)])
def create_ticket(p:TicketIn,db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,m=ctx;licensed(db,org,False) # help remains accessible when license expires
 t=SupportTicket(organization_id=org.id,created_by=user.id,subject=p.subject,category=p.category,priority=p.priority)
 db.add(t);db.flush();db.add(SupportMessage(ticket_id=t.id,created_by=user.id,message=p.message))
 audit(db,user.id,'support_created','v57_support_ticket',t.id,p.subject);db.commit()
 return {'id':t.id,'message':'Help request submitted'}


@router.get('/help/tickets/{ticket_id}',dependencies=[Depends(organization_help_retired)])
def ticket_detail(ticket_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,_=ctx
 t=_ticket_for_user(db,user,ticket_id,org.id)
 return {'ticket':{**_ticket(t),'organization_name':org.name},'attachments':_attachments(db,t.id),'messages':[{'id':r.id,'user':db.get(User,r.created_by).full_name if db.get(User,r.created_by) else 'Unknown',
 'created_by':r.created_by,'sender_type':'platform' if db.get(User,r.created_by) and db.get(User,r.created_by).role=='platform_owner' else 'organization',
 'message':r.message,'created_at':r.created_at.isoformat()} for r in db.query(SupportMessage).filter_by(ticket_id=t.id,internal=False).order_by(SupportMessage.id)]}


@router.post('/help/tickets/{ticket_id}/reply',status_code=201,dependencies=[Depends(organization_help_retired)])
def ticket_reply(ticket_id:int,p:ReplyIn,db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,_=ctx;t=_ticket_for_user(db,user,ticket_id,org.id)
 if p.internal:raise HTTPException(403,'Internal support notes are platform-only')
 if t.status=='closed':raise HTTPException(409,'Ticket is closed')
 db.add(SupportMessage(ticket_id=t.id,created_by=user.id,message=p.message))
 t.updated_at=utcnow();audit(db,user.id,'support_reply','v57_support_ticket',t.id)
 db.commit();return {'message':'Reply sent'}


@router.get('/platform/help/tickets')
def owner_tickets(db:Session=Depends(get_db),user:User=Depends(owner)):
 return {'items':_ticket_list(db,db.query(SupportTicket).order_by(SupportTicket.updated_at.desc(),SupportTicket.id.desc()).limit(500).all(),True)}


@router.get('/platform/help/tickets/{ticket_id}')
def owner_ticket_detail(ticket_id:int,db:Session=Depends(get_db),user:User=Depends(owner)):
 t=_ticket_for_user(db,user,ticket_id)
 return {'ticket':{**_ticket(t),'organization_name':db.get(Organization,t.organization_id).name if t.organization_id and db.get(Organization,t.organization_id) else 'Platform'},'attachments':_attachments(db,t.id),'messages':[{'id':r.id,'user':db.get(User,r.created_by).full_name if db.get(User,r.created_by) else 'Unknown',
 'created_by':r.created_by,'sender_type':'platform' if db.get(User,r.created_by) and db.get(User,r.created_by).role=='platform_owner' else 'organization',
 'message':r.message,'internal':r.internal,'created_at':r.created_at.isoformat()} for r in db.query(SupportMessage).filter_by(ticket_id=t.id).order_by(SupportMessage.id)]}


@router.post('/platform/help/tickets/{ticket_id}/reply',status_code=201)
def owner_reply(ticket_id:int,p:ReplyIn,db:Session=Depends(get_db),user:User=Depends(owner)):
 t=_ticket_for_user(db,user,ticket_id)
 db.add(SupportMessage(ticket_id=t.id,created_by=user.id,message=p.message,internal=p.internal))
 t.updated_at=utcnow();t.status='in_progress' if t.status=='open' else t.status
 audit(db,user.id,'support_reply','v57_support_ticket',t.id);db.commit();return {'message':'Support response saved'}


@router.patch('/platform/help/tickets/{ticket_id}')
def change_ticket(ticket_id:int,p:StatusIn,db:Session=Depends(get_db),user:User=Depends(owner)):
 t=_ticket_for_user(db,user,ticket_id)
 if p.assigned_to is not None and not db.get(User,p.assigned_to):raise HTTPException(404,'Assignee missing')
 t.status=p.status;t.assigned_to=p.assigned_to;t.updated_at=utcnow()
 audit(db,user.id,'support_status','v57_support_ticket',t.id,p.status);db.commit();return _ticket(t)


@router.post('/help/tickets/{ticket_id}/attachments',status_code=201,dependencies=[Depends(organization_help_retired)])
async def upload_ticket_attachment(ticket_id:int,file:UploadFile=File(...),db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,_=ctx;t=_ticket_for_user(db,user,ticket_id,org.id)
 if t.status=='closed':raise HTTPException(409,'Ticket is closed')
 contents=await file.read(4*1024*1024+1)
 return _save_attachment(db,t,user,file,contents)


@router.post('/platform/help/tickets/{ticket_id}/attachments',status_code=201)
async def owner_upload_attachment(ticket_id:int,file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(owner)):
 t=_ticket_for_user(db,user,ticket_id)
 contents=await file.read(4*1024*1024+1)
 return _save_attachment(db,t,user,file,contents)


@router.get('/help/tickets/{ticket_id}/attachments/{attachment_id}',dependencies=[Depends(organization_help_retired)])
def download_ticket_file(ticket_id:int,attachment_id:int,db:Session=Depends(get_db),ctx=Depends(context)):
 user,org,_=ctx
 return _download(db,_ticket_for_user(db,user,ticket_id,org.id),attachment_id)


@router.get('/platform/help/tickets/{ticket_id}/attachments/{attachment_id}')
def owner_download_ticket_file(ticket_id:int,attachment_id:int,db:Session=Depends(get_db),user:User=Depends(owner)):
 return _download(db,_ticket_for_user(db,user,ticket_id),attachment_id)
