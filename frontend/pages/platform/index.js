import {get,post,put,patch,request,esc,toast,number,dateString} from '../../shared/api.js';
import {head,button,table,kpis,barChart,panel,modalForm,detailModal,listenRows,submoduleDirectory,submoduleWorkspace,bindSubmodules,rememberedSubmodule,rememberSubmodule} from '../../shared/ui.js';import {organizations,insights,support,detail,offers,createOffer,updateOffer} from './service.js';
export async function render(root){const [orgs,stats,tickets]=await Promise.all([organizations(),insights(),support()]);const items=orgs.items||[],ts=tickets.items||[];let tab=rememberedSubmodule('platform'),selected=null;
 const sections=[
  {id:'organizations',title:'Organizations',description:'Customers, verification and approvals'},
  {id:'subscriptions',title:'Subscriptions',description:'Subscription status and renewal dates'},
  {id:'subscription_policy',title:'Subscription policy & requests',description:'Trial promotion, subscription requests and key approval'},
  {id:'keys',title:'Product keys',description:'Activation keys, licensing and redemption'},
  {id:'offers',title:'Promotional offers',description:'Commercial offers with dates and eligibility'},
  {id:'users',title:'Users',description:'Employees in subscribed organizations'},
  {id:'usage',title:'Usage analytics',description:'Organization activity and feature adoption'},
  {id:'branding',title:'Branding',description:'Platform login background and visual identity'},
  {id:'support',title:'Support inbox',description:'Customer support conversations'},
  {id:'audit',title:'Audit logs',description:'Platform administrative actions and history'},
 ];
 if(tab&&!sections.some(x=>x.id===tab)){tab=null;}
 function draw(){
  const controls=button('Upload login background','upload-background','commit');
  const counters=kpis([{label:'Organizations',value:stats.organizations},{label:'Approved',value:stats.approved},
    {label:'Active subscriptions',value:stats.active_subscriptions},{label:'Open support tickets',value:stats.open_tickets}]);
  root.innerHTML=head(tab?sections.find(x=>x.id===tab)?.title||'Platform Administration':'Platform Administration',tab?'Platform management':'Choose an administration area',controls)+
    (!tab?counters+submoduleDirectory('Platform Administration',sections,{organizations:items.length,subscriptions:stats.active_subscriptions,keys:items.filter(x=>x.latest_key_status).length,users:stats.users||'—',usage:(stats.features||[]).length,support:ts.length}):
      submoduleWorkspace('Platform Administration',sections,tab,'<div id="owner-section"></div>'));
  bindSubmodules(root,id=>{tab=id;rememberSubmodule('platform',id);draw()});
  root.querySelector('#upload-background')?.addEventListener('click',uploadBackground);
  if(tab)section();
 }
 function section(){root.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));const box=root.querySelector('#owner-section');if(['organizations','keys','users'].includes(tab)){
  const cols=tab==='subscriptions'?[['name','Organization'],['license_status','Subscription'],['expires_at','Renewal / expiry',x=>dateString(x.expires_at)],['status','Approval']]:
   tab==='keys'?[['name','Organization'],['latest_key_status','Latest key'],['latest_key_days','Duration (days)'],['expires_at','Paid through',x=>dateString(x.expires_at)]]:
   tab==='users'?[['name','Organization'],['email','Organization email'],['status','Verification']]:
   [['name','Organization'],['status','Approval'],['license_status','Subscription'],['latest_key_status','Product key'],['latest_key_days','Key duration (days)'],['expires_at','Subscription expiry',x=>dateString(x.expires_at)]];
  box.innerHTML=table(items,cols);listenRows(box,items,organizationDetails);return;
 }
 if(tab==='subscriptions'){
   box.innerHTML='<div class="panel">Loading organization subscriptions…</div>';
   get('cape/platform/organization-subscriptions').then(data=>{
    if(tab!=='subscriptions'||!root.querySelector('#owner-section'))return;
    const all=data.items||[], counts=data.counts||{};
    const statusLabels={active:'Active',expiring_soon:'Expiring soon',expired:'Expired',suspended:'Suspended',pending_verification:'Awaiting verification',pending_activation:'Request pending',not_activated:'Not activated'};
    const modeLabels={trial:'Free Trial',paid:'Paid subscription',none:'Not activated'};
    const stat=n=>Number(counts[n]||0).toLocaleString();
    const tiles=[['Organizations',stat('all'),'all'],['On free trial',stat('trial'),'trial'],['Professional',stat('professional'),'paid'],['Enterprise',stat('enterprise'),'paid'],['Expiring soon',stat('expiring_soon'),'expiring_soon'],['Expired',stat('expired'),'expired']];
    box.innerHTML=`<div class="cape-license-page">
      <div class="cape-license-summary">${tiles.map(([label,value,code])=>`<button type="button" class="cape-license-kpi" data-focus="${code}"><span>${esc(label)}</span><strong>${esc(value)}</strong></button>`).join('')}</div>
      <div class="panel cape-license-main"><div class="cape-license-title"><div><h2>Organization subscription register</h2><p class="muted">One organization per row, classified using redeemed licenses. A pending product key is not an active subscription.</p></div><span class="cape-license-count" id="cape-license-count"></span></div>
      <div class="cape-license-filters"><label>Find organization<input type="search" id="cape-license-search" placeholder="Search name, country, plan…"></label><label>Subscription type<select id="cape-license-mode"><option value="all">All types</option><option value="trial">Free Trial</option><option value="paid">Paid (Professional or Enterprise)</option><option value="none">Not activated</option></select></label><label>Access status<select id="cape-license-status"><option value="all">All statuses</option>${Object.entries(statusLabels).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('')}</select></label></div>
      <div class="cape-license-table-wrap"><table class="cape-license-table"><thead><tr><th>Organization</th><th>Subscription</th><th>Access</th><th>Employees</th><th>Activated</th><th>Expires</th><th>Remaining</th><th></th></tr></thead><tbody id="cape-license-rows"></tbody></table></div>
      <p class="cape-license-help">Trial eligibility is tracked permanently. Paid plans retain their actual plan name (Professional or Enterprise). Statuses and remaining days are calculated by the backend.</p>
      </div></div>`;
    const escValue=x=>esc(x==null?'—':String(x));
    const when=x=>x?dateString(x):'—';
    const tbody=box.querySelector('#cape-license-rows');
    const search=box.querySelector('#cape-license-search'),mode=box.querySelector('#cape-license-mode'),status=box.querySelector('#cape-license-status');
    function renderRows(){
      const q=search.value.trim().toLowerCase();
      const filtered=all.filter(r=>(mode.value==='all'||mode.value===r.mode)&&(status.value==='all'||status.value===r.access_status)&&(!q||[r.name,r.country,r.plan_label,r.verification].some(x=>String(x||'').toLowerCase().includes(q))));
      box.querySelector('#cape-license-count').textContent=`${filtered.length} of ${all.length} organizations`;
      tbody.innerHTML=filtered.length?filtered.map(r=>`<tr>
        <td><strong>${escValue(r.name)}</strong><small>${escValue(r.country)} · ID ${escValue(r.id)}</small></td>
        <td><span class="cape-license-pill mode-${escValue(r.mode)}">${escValue(modeLabels[r.mode]||r.mode)}</span><small>${escValue(r.plan_label)}</small></td>
        <td><span class="cape-license-pill status-${escValue(r.access_status)}">${escValue(statusLabels[r.access_status]||r.access_status)}</span>${r.pending_request_id?'<small>Renewal request pending</small>':''}</td>
        <td>${escValue(r.active_employees)} / ${escValue(r.max_employees)}</td><td>${when(r.activated_at)}</td><td>${when(r.expires_at)}</td>
        <td class="cape-license-days">${r.is_active?`${Number(r.days_remaining)} days`:'—'}</td>
        <td><button type="button" class="cape-license-view" data-license-org="${Number(r.id)}">Details</button></td></tr>`).join(''):'<tr><td colspan="8" class="cape-license-empty">No organizations match these filters.</td></tr>';
      tbody.querySelectorAll('[data-license-org]').forEach(btn=>btn.addEventListener('click',()=>{
        const r=all.find(x=>Number(x.id)===Number(btn.dataset.licenseOrg));
        if(r)showSubscriptionDetail(r);
      }));
    }
    function showSubscriptionDetail(r){
       const modeText=modeLabels[r.mode]||r.mode, stateText=statusLabels[r.access_status]||r.access_status;
       const fields=[['Organization',r.name],['Country',r.country],['Verification',r.verification],['Subscription class',modeText],['Actual plan',r.plan_label],['Access status',stateText],['Activation date',when(r.activated_at)],['Expiry date',when(r.expires_at)],['Remaining',r.is_active?`${r.days_remaining} days`:'Not active'],['Active employees',r.active_employees],['Licensed seats',r.max_employees],['Trial used',r.trial_used?'Yes':'No'],['Trial started',when(r.trial_started_at)],['Trial ended / due',when(r.trial_ends_at)],['Pending request days',r.requested_days||'None'],['Unredeemed keys',r.issued_unredeemed_keys]];
       const html=`<div class="cape-license-detail"><h3>${escValue(r.name)}</h3>${fields.map(([k,v])=>`<div><span>${esc(k)}</span><strong>${escValue(v)}</strong></div>`).join('')}</div>`;
       modalForm({title:`Subscription · ${r.name}`,fields:[],intro:html,readOnly:true,saveLabel:'Close'});
    }
    [search,mode,status].forEach(el=>el.addEventListener('input',renderRows));
    box.querySelectorAll('[data-focus]').forEach(b=>b.addEventListener('click',()=>{const key=b.dataset.focus;mode.value=['trial','paid','none'].includes(key)?key:'all';status.value=['expiring_soon','expired','pending_verification'].includes(key)?key:'all';renderRows();}));
    renderRows();
   }).catch(e=>{if(tab==='subscriptions')box.innerHTML=`<div class="empty">Subscription overview unavailable: ${esc(e.message)}</div>`});
   return;
 }
 if(tab==='subscription_policy'){
   box.innerHTML='<div class="panel">Loading subscription policy…</div>';
   Promise.all([get('cape/platform/subscription-policy'),get('cape/platform/subscription-requests')]).then(([p,requests])=>{
    if(tab!=='subscription_policy'||!root.querySelector('#owner-section'))return;
    box.innerHTML=`<div class="panel" style="max-width:860px"><h2>Global subscription rules</h2><p class="muted">Free trials are disabled unless you explicitly enable the promotion. Each organization is eligible only once.</p>
      <form id="owner-policy" class="form-grid" style="margin-top:16px"><label class="wide" style="display:flex;flex-direction:row;align-items:center;gap:10px"><input type="checkbox" name="trial_enabled" ${p.trial_enabled?'checked':''}> Allow a free 30-day trial for eligible organizations</label>
       <label>Minimum paid days<input value="30" disabled></label><label>Free-trial days<input value="30" disabled></label>
       <label>Default licensed employees<input type="number" name="default_employee_seats" min="1" value="${p.default_employee_seats}" required></label>
       <button class="btn commit wide" type="submit">Save subscription policy</button></form></div>
       <div class="panel" style="margin-top:18px"><h2>Subscription applications</h2>${table(requests.items||[],[['organization','Organization'],['days','Requested days'],['employee_seats','Employees'],['status','Status'],['created_at','Submitted']],{empty:'No requests yet.'})}
       <p class="muted" style="margin-top:10px">Select a pending application to issue a one-time product key after you verify payment.</p></div>`;
    box.querySelector('#owner-policy').onsubmit=async event=>{event.preventDefault();const f=event.currentTarget;try{await put('cape/platform/subscription-policy',{trial_enabled:f.elements.trial_enabled.checked,trial_days:30,minimum_paid_days:30,default_employee_seats:Number(f.elements.default_employee_seats.value)});toast('Policy saved');section()}catch(e){toast(e.message,true)}};
    listenRows(box,requests.items||[],r=>{if(r.status!=='pending')return toast('This request was already reviewed',true);
      modalForm({title:`Subscription request · ${r.organization}`,fields:[{name:'decision',label:'Review decision',type:'select',required:true,options:[{value:'approve',label:'Approve and issue product key'},{value:'reject',label:'Reject'}]}],saveLabel:'Confirm decision',onSave:async d=>{
       const result=await post(`cape/platform/subscription-requests/${r.id}/review`,{decision:d.decision});
       if(result.key)window.prompt('Copy this product key NOW and deliver it securely to the organization administrator. It cannot be retrieved again.',result.key);
       toast('Request reviewed');section();}});
    });
   }).catch(e=>{box.innerHTML=`<div class="empty">Subscription administration unavailable: ${esc(e.message)}</div>`});return;
 }
 if(tab==='offers'){
   box.innerHTML='<div class="panel">Loading offers…</div>';
   offers().then(data=>{if(!root.querySelector('#owner-section')||tab!=='offers')return;
    const items=data.items||[];
    box.innerHTML=`<div class="toolbar" style="margin-bottom:12px">${button('Create offer','create-offer','commit')}${button('Refresh table','refresh-offers','commit')}</div>`+
      table(items,[['name','Offer'],['code','Code'],['discount_pct','Discount %'],['bonus_days','Bonus days'],['starts_on','Starts'],['ends_on','Ends'],['active','Status',x=>x.active?'Active':'Disabled']],{empty:'No offers created yet.'});
    box.querySelector('#refresh-offers')?.addEventListener('click',()=>section());
    box.querySelector('#create-offer')?.addEventListener('click',()=>modalForm({title:'Create promotional offer',fields:[
     {name:'name',label:'Offer name',required:true},{name:'code',label:'Unique offer code',required:true},
     {name:'discount_pct',label:'Discount percentage',type:'number',min:0,max:100,value:0},
     {name:'bonus_days',label:'Bonus days',type:'number',min:0,value:0},
     {name:'max_redemptions',label:'Maximum redemptions (optional)',type:'number',min:1},
     {name:'starts_on',label:'Valid from',type:'date',required:true},
     {name:'ends_on',label:'Valid through',type:'date',required:true},
     {name:'description',label:'Offer conditions',type:'textarea',wide:true}],saveLabel:'Save offer',onSave:async d=>{if(!d.max_redemptions)delete d.max_redemptions;await createOffer(d);toast('Offer saved successfully');section()}}));
    listenRows(box,items,offer=>modalForm({title:`Offer: ${offer.name}`,readOnly:true,fields:[],intro:`<p>${esc(offer.description||'No description')}</p><p>Code ${esc(offer.code)} · ${esc(offer.discount_pct)}% off · ${esc(offer.bonus_days)} bonus days</p><p>Valid ${esc(offer.starts_on)} to ${esc(offer.ends_on)}</p><p><strong>${offer.active?'Active':'Disabled'}</strong></p>`,saveLabel:'Close'}));
   }).catch(e=>{box.innerHTML=`<div class="empty">Offers unavailable: ${esc(e.message)}</div>`});return;
 }
 if(tab==='usage'){box.innerHTML=`<div class="grid two">${panel('Features actually used',barChart((stats.features||[]).slice(0,10).map(x=>({label:x.feature.slice(0,11),value:x.actions}))))}${panel('Features with no recorded actions',(stats.unused_features||[]).map(x=>`<span class="tag" style="margin:4px">${esc(x)}</span>`).join('')||'All tracked features have activity')}</div><div style="height:14px"></div>`+panel('Expiring in 30 days',table(stats.expiring||[],[['name','Organization'],['expires_at','Expiry'],['days_remaining','Days remaining']]));return}
 if(tab==='audit'){box.innerHTML='<div class="panel">Loading audit history…</div>';
  get('v5/platform/audit/summary').then(result=>{if(!root.querySelector('#owner-section'))return;box.innerHTML=table(result.items||[],[['created_at','Time'],['actor','Administrator'],['action','Action'],['entity_type','Record type'],['description','Details']],{empty:'No platform actions recorded yet.'});}).catch(e=>{box.innerHTML=`<div class="empty">Audit is unavailable: ${esc(e.message)}</div>`});return;}
 if(tab==='branding'){box.innerHTML=panel('Platform appearance',`<p>Choose the global login background. Organization admins can upload their own logo.</p><div style="margin-top:14px"><img src="/api/v6/public/branding/image" alt="Current login background" style="max-width:100%;height:180px;object-fit:cover;border-radius:8px" onerror="this.style.display='none'"></div><div class="actions" style="margin-top:12px">${button('Change background','background','commit')}${button('Restore default','restore')}</div>`);box.querySelector('#background').onclick=uploadBackground;box.querySelector('#restore').onclick=async()=>{try{await request('v6/platform/branding/background',{method:'DELETE'});toast('Default background restored');section()}catch(e){toast(e.message,true)}};return}
 if(tab==='support'){box.innerHTML=`<div class="owner-inbox"><div class="owner-thread-list">${ts.length?ts.map(t=>`<div class="owner-thread ${selected===t.id?'selected':''}" data-ticket="${t.id}"><strong>${esc(t.subject)}</strong><div class="muted">${esc(t.organization_name||t.organization_id||'Platform')} · ${esc(t.status)}</div><small>${dateString(t.updated_at||t.created_at)}</small></div>`).join(''):'<div class="empty">No messages yet</div>'}</div><div id="chat" class="conversation-history"><div class="empty">Select a conversation to view its messages.</div></div></div>`;box.querySelectorAll('[data-ticket]').forEach(n=>n.onclick=()=>showThread(Number(n.dataset.ticket)));if(selected)showThread(selected);return}
 }
 async function organizationDetails(org){const [x,mods,keys]=await Promise.all([detail(org.id),get(`v6/platform/organizations/${org.id}/modules`),get(`v5/platform/organizations/${org.id}/license-keys`)]);
 const entries=Object.entries(x.counts||{}).map(([k,v])=>`${k}: ${v}`).join(' · ');
 modalForm({title:`${org.name} — Organization`,readOnly:true,saveLabel:'Close',intro:`<div class="owner-detail"><p><strong>Approval:</strong> ${esc(org.status)}</p><p><strong>Subscription:</strong> ${esc(org.license_status)} · ${dateString(org.expires_at)}</p><p><strong>Email:</strong> ${esc(org.email)}</p><p><strong>Registered users:</strong> ${x.employees.length}</p><p><strong>Operations:</strong> ${esc(entries)}</p><p><strong>Features:</strong> ${(mods.items||[]).map(m=>esc(m.name)+(m.enabled?' ✓':' ✕')).join(', ')}</p><p><strong>Recent license keys:</strong> ${(keys.items||[]).map(k=>`${k.status} ${k.duration_days}d`).join(', ')||'None'}</p></div><div class="actions" style="margin-top:15px">${button('Registration details','org-profile')}${button('Approve organization','approve','commit')}${button('Issue product key','issue','commit')}${button('Configure modules','modules')}</div>`,fields:[]});
 document.getElementById('org-profile')?.addEventListener('click',async()=>{
  try{const x=await get(`cape/platform/organization-profile/${org.id}`);
   document.getElementById('modal-root').replaceChildren();document.body.style.overflow='';
   const rows=Object.entries(x.profile||{}).filter(([k,v])=>!['organization_id','created_at'].includes(k)&&v!==null&&v!==undefined&&v!=='');
   modalForm({title:`Registration profile · ${x.name}`,readOnly:true,fields:[],saveLabel:'Close',intro:`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Registration field</th><th>Provided information</th></tr></thead><tbody>${rows.map(([k,v])=>`<tr><td>${esc(k.replaceAll('_',' '))}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div>`});
  }catch(e){toast(e.message,true)}
 });
 document.getElementById('approve')?.addEventListener('click',async()=>{try{await put(`v5/platform/organizations/${org.id}/verification`,{status:'approved'});toast('Organization approved')}catch(e){toast(e.message,true)}});
 document.getElementById('issue')?.addEventListener('click',()=>{document.getElementById('modal-root').replaceChildren();document.body.style.overflow='';modalForm({title:`Issue product key · ${org.name}`,fields:[{name:'duration_days',label:'Licensed days',type:'number',min:30,value:30,required:true},{name:'max_employees',label:'Employee seats',type:'number',min:1,value:25,required:true}],saveLabel:'Generate license key',onSave:async d=>{const result=await post('v5/platform/license-keys',{...d,organization_id:org.id});window.prompt('Copy the license key now; it cannot be shown again',result.key)}})});
 document.getElementById('modules')?.addEventListener('click',()=>{document.getElementById('modal-root').replaceChildren();document.body.style.overflow='';modalForm({title:`Enable organization module · ${org.name}`,fields:[{name:'module',label:'Module',type:'select',options:(mods.items||[]).map(x=>({value:x.name,label:x.name})),required:true},{name:'enabled',label:'Enabled',type:'checkbox',value:true}],saveLabel:'Save module access',onSave:async d=>{await put(`v6/platform/organizations/${org.id}/modules/${d.module}`,{enabled:d.enabled})}})})
 }
 async function showThread(id){selected=id;const result=await get(`v5/platform/help/tickets/${id}`);const chat=root.querySelector('#chat');if(!chat)return;const t=result.ticket;chat.innerHTML=`<div class="modal-head"><div><strong>${esc(t.subject)}</strong><div class="muted">${esc(t.organization_name||'Platform')} · ${esc(t.status)}</div></div></div><div class="conversation-messages">${(result.messages||[]).map(x=>`<div class="bubble ${x.sender_type==='platform'?'owner':''}"><small>${esc(x.user)} · ${dateString(x.created_at)}${x.internal?' · Internal':''}</small>${esc(x.message)}</div>`).join('')}</div><form class="conversation-compose" id="reply"><textarea name="message" aria-label="Your reply" placeholder="Type your response…" required></textarea><button class="btn commit">Send</button></form>`;chat.querySelector('#reply').onsubmit=async e=>{e.preventDefault();const msg=e.target.elements.message.value;await post(`v5/platform/help/tickets/${id}/reply`,{message:msg,internal:false});await showThread(id)};}
 function uploadBackground(){modalForm({title:'Upload platform login background',fields:[{name:'file',label:'JPG, PNG or WebP (max 6 MB)',type:'file',required:true,wide:true}],saveLabel:'Upload background',onSave:async d=>{const f=document.querySelector('#modal-root input[type=file]')?.files?.[0];if(!f)throw Error('Choose an image');const formData=new FormData();formData.append('file',f);await request('v6/platform/branding/background',{method:'POST',formData});toast('Login background updated');section()}})}draw()}
