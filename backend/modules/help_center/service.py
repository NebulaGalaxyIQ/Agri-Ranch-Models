"""Platform-owned support conversations and attachment validation."""
from __future__ import annotations
import os
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.responses import Response
from database import User,utcnow
from modules.organizations.models import Organization,Membership
from modules.help_center.models import SupportTicket, SupportMessage, SupportAttachment
from auth import audit
_ALLOWED_MEDIA={
 'image/jpeg':(b'\xff\xd8\xff',),'image/png':(b'\x89PNG\r\n\x1a\n',),
 'application/pdf':(b'%PDF-',),
}


def _ticket(t):
 return {'id':t.id,'organization_id':t.organization_id,'created_by':t.created_by,'subject':t.subject,'category':t.category,
 'priority':t.priority,'status':t.status,'assigned_to':t.assigned_to,'created_at':t.created_at.isoformat(),
 'updated_at':t.updated_at.isoformat()}


def _ticket_list(db:Session, rows:list[SupportTicket], include_internal:bool=False):
 """Bulk-load sender/organization context and a safe latest-message preview.
 The organization inbox never receives internal platform notes.
 """
 if not rows:return []
 ids=[t.id for t in rows]
 org_ids={t.organization_id for t in rows if t.organization_id is not None}
 user_ids={t.created_by for t in rows}
 organizations={o.id:o.name for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}
 messages_query=db.query(SupportMessage).filter(SupportMessage.ticket_id.in_(ids))
 if not include_internal:messages_query=messages_query.filter(SupportMessage.internal.is_(False))
 messages=messages_query.order_by(SupportMessage.id.desc()).all()
 last={}
 for m in messages:
  if m.ticket_id not in last:last[m.ticket_id]=m
  user_ids.add(m.created_by)
 names={u.id:u.full_name for u in db.query(User).filter(User.id.in_(user_ids)).all()}
 return [{**_ticket(t),'organization_name':organizations.get(t.organization_id,'Platform'),
  'created_by_name':names.get(t.created_by,'Unknown'),
  'last_message':last[t.id].message[:180] if t.id in last else '',
  'last_sender':names.get(last[t.id].created_by,'Unknown') if t.id in last else '',
  'last_message_at':last[t.id].created_at.isoformat() if t.id in last else t.created_at.isoformat()}
  for t in rows]


def _ticket_for_user(db,user,ticket_id,org_id=None):
 t=db.get(SupportTicket,ticket_id)
 if not t:raise HTTPException(404,'Ticket not found')
 if user.role=='platform_owner':return t
 if not org_id or t.organization_id!=org_id:raise HTTPException(404,'Ticket not found')
 m=db.query(Membership).filter_by(user_id=user.id,organization_id=org_id,active=True).first()
 if not m:raise HTTPException(403,'Not a current organization member')
 if t.created_by!=user.id and m.role not in ('org_admin','manager'):raise HTTPException(403,'Ticket is private to its submitter and authorized management')
 return t


def organization_help_retired():
    # V5.10: Customers no longer have a Help Center. The owner retains a
    # read-only view of historical tickets plus owner-side support actions.
    raise HTTPException(status_code=410, detail='Help Center was removed from organization workspaces')


def _attachments(db,ticket_id):
 return [{'id':x.id,'filename':x.filename,'media_type':x.media_type,'size':len(x.content)}
 for x in db.query(SupportAttachment).filter_by(ticket_id=ticket_id).order_by(SupportAttachment.id)]


def _save_attachment(db,ticket,user,file,content):
 if file.content_type not in _ALLOWED_MEDIA:raise HTTPException(422,'Upload a JPG, PNG or PDF only')
 if len(content)>4*1024*1024:raise HTTPException(413,'File must be 4 MB or smaller')
 if not content or not any(content.startswith(sig) for sig in _ALLOWED_MEDIA[file.content_type]):
  raise HTTPException(422,'File content does not match the supported type')
 if db.query(SupportAttachment).filter_by(ticket_id=ticket.id).count()>=5:
  raise HTTPException(409,'Maximum five attachments per ticket')
 name=os.path.basename(file.filename or 'attachment')[:180].replace('"','').replace('\n','')
 record=SupportAttachment(ticket_id=ticket.id,uploaded_by=user.id,filename=name,media_type=file.content_type,content=content)
 db.add(record);db.flush();audit(db,user.id,'support_attachment','v57_support_ticket',ticket.id,name)
 db.commit();return {'id':record.id,'filename':name}


def _download(db,t,attachment_id):
 attachment=db.query(SupportAttachment).filter_by(id=attachment_id,ticket_id=t.id).first()
 if not attachment:raise HTTPException(404,'Attachment not found')
 # Safe, non-executable attachment types only; force download rather than inline HTML rendering.
 from urllib.parse import quote
 return Response(content=attachment.content,media_type=attachment.media_type,headers={
  'Content-Disposition':f"attachment; filename*=UTF-8''{quote(attachment.filename)}",
  'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})
