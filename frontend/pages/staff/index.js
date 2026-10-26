import {get,post,can,appState,esc,safe} from '../../shared/api.js';import {head,button,kpis,modalForm,table,listenRows,detailModal,choice,panel} from '../../shared/ui.js';import {tasks,members,roles,complete} from './service.js';
const map={feeding:'fattening',watering:'fattening',cleaning:'fattening',weighing:'fattening',movement:'fattening',medication:'fattening',dipping:'fattening',health:'fattening',crop:'crops',planting:'crops',harvest:'crops',garden:'gardening',gardening:'gardening',machinery:'machinery',maintenance:'machinery',stock_receive:'inventory',stock_out:'inventory',finance:'finance',other:'staff'};
export async function render(root,{navigate}){const manage=can('tasks.manage')||appState.org?.role==='org_admin';const res=manage?await tasks():await get('v5/tasks/my');const rows=manage?(res.items||[]):[...(res.due||[]),...(res.overdue||[]),...(res.completed||[]),...(res.upcoming||[])];const pending=manage?rows.filter(t=>t.status!=='completed'):res.due||[];const overdue=manage?pending.filter(t=>t.due_date&&t.due_date<new Date().toISOString().slice(0,10)):res.overdue||[];const upcoming=manage?[]:res.upcoming||[];const done=manage?rows.filter(t=>t.status==='completed'):res.completed||[];const [people,roleData]=manage?await Promise.all([safe(()=>members()),safe(()=>roles())]):[{items:[]},{items:[],allowed_permissions:[]}];const userId=appState.user.id;
 let tab='pending';
 function draw(){const items=tab==='pending'?pending:tab==='overdue'?overdue:tab==='upcoming'?upcoming:done;root.innerHTML=head(manage?'Employees & Tasks':'My Tasks',manage?'Assign duties and review what has been completed':'Choose a duty, record the activity and return to your task list.',manage?button('+ Assign task','assign','commit')+button('+ Add employee','member','commit')+button('+ Create role','role','commit'):'')+
 kpis([{label:'To complete',value:pending.length},{label:'Completed',value:done.length},{label:'Overdue',value:overdue.length},{label:'Assigned tasks',value:rows.length}])+`<div style="height:17px"></div><section class="panel"><div class="task-status-switch" aria-label="Filter tasks"><button data-tab="pending" class="task-status-button ${tab==='pending'?'selected':''}">To complete</button><button data-tab="done" class="task-status-button ${tab==='done'?'selected':''}">Completed</button><button data-tab="overdue" class="task-status-button ${tab==='overdue'?'selected':''}">Overdue</button><button data-tab="upcoming" class="task-status-button ${tab==='upcoming'?'selected':''}">Upcoming</button></div>${!items.length?`<div class="task-notice">${tab==='pending'?'✓ All your tasks for today are completed.':'No tasks in this category.'}</div>`:items.map(t=>`<div class="task-row ${t.status==='completed'?'done':''}"><div><strong>${esc(t.title)}</strong><small>${esc(t.category)} · ${esc(t.shift||t.frequency)} · Due ${esc(t.due_date||'when assigned')}</small></div><div class="actions">${t.status!=='completed'&&t.status!=='upcoming'?button('Open task',`go-${t.id}`)+button('Complete',`done-${t.id}`,'commit'):'<span class="tag">Completed</span>'}</div></div>`).join('')}</section>${manage?'<div style="height:16px"></div>'+panel('Current employees',table(people.items||[],[['name','Name'],['email','Email'],['role','Main role'],['active','Active']])):''}`;
 root.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;draw()});
 for(const t of items){root.querySelector(`#go-${t.id}`)?.addEventListener('click',()=>openTask(t,navigate,root));root.querySelector(`#done-${t.id}`)?.addEventListener('click',async()=>{try{await complete(t.id);await render(root,{navigate})}catch(e){alert(e.message)}})}
 root.querySelector('#assign')?.addEventListener('click',()=>modalForm({title:'Assign an employee task',fields:[{name:'title',label:'Task',required:true},{name:'category',label:'Activity',type:'select',options:['feeding','watering','cleaning','dipping','medication','weighing','health','movement','inspection','maintenance','other','stock_receive','stock_out','finance','planting','harvest','crop','gardening','machinery'],required:true},{name:'assigned_to',label:'Employee',type:'select',options:(people.items||[]).map(p=>({value:p.user_id,label:p.name||p.email}))},{name:'frequency',label:'Frequency',type:'select',options:['once','daily','weekly','monthly'],value:'daily'},{name:'shift',label:'Shift / period',type:'select',options:['Morning','Afternoon','Evening','Daily','Weekly','Monthly']},{name:'due_date',label:'Due date',type:'date',value:new Date().toISOString().slice(0,10)}],onSave:async d=>{if(d.assigned_to)d.assigned_to=+d.assigned_to;await post('v5/tasks',d);await render(root,{navigate})}}));
 root.querySelector('#member')?.addEventListener('click',()=>modalForm({title:'Add employee',fields:[{name:'name',label:'Full name',required:true},{name:'email',label:'Email',required:true,type:'email'},{name:'password',label:'Temporary password (10+ characters)',required:true,type:'password'},{name:'role',label:'Initial role',type:'select',required:true,options:['worker','feeding_recorder','weighing_recorder','movement_recorder','storekeeper','veterinary','finance','cleaner','gardener','crop_worker','livestock_keeper','mechanic','department_head','manager','viewer']}],onSave:async d=>{await post('v5/members',d);await render(root,{navigate})}}));
 root.querySelector('#role')?.addEventListener('click',()=>modalForm({title:'Create organization role',fields:[{name:'name',label:'Role name',required:true},{name:'permissions',label:'Permissions (comma separated)',placeholder:'e.g. crops.read,crops.write'}],onSave:async d=>{d.permissions=(d.permissions||'').split(',').map(x=>x.trim()).filter(Boolean);await post('v5/roles',d);await render(root,{navigate})}}));
 }draw()}


// Staff activity forms are contextual: workers choose existing records, never re-enter animals,
// batches or stock. Server-side idempotency and period claims are the final authority.
async function openTask(task,navigate,root){
 const category=task.category;
 if(['planting','harvest','crop','gardening','machinery'].includes(category)){
   navigate(map[category]||'staff');return;
 }
 if(['stock_receive','stock_out','finance'].includes(category)){navigate(map[category]);return}
 const options=await safe(()=>get('v5/routine/options'),{batches:[],animals:[],feeds:[],mixes:[],medicines:[]});
 const batches=options.batches||[], animals=options.animals||[], feeds=[...(options.feeds||[]),...(options.mixes||[]).map(x=>({...x,available_kg:x.available_kg}))];
 const subject=task.batch_id?[{value:task.batch_id,label:batches.find(b=>b.id===task.batch_id)?.name||`Batch ${task.batch_id}`}]:batches.map(b=>({value:b.id,label:b.name}));
 let fields=[],title=task.title;
 if(category==='feeding'){
   const selectedBatch=task.batch_id||(batches.length===1?batches[0].id:null);
   if(!selectedBatch){
    modalForm({title:'Choose the batch to feed',fields:[{name:'batch_id',label:'Batch',type:'select',required:true,
      options:batches.map(x=>({value:x.id,label:x.name}))}],saveLabel:'Continue',onSave:async d=>{
       window.setTimeout(()=>openTask({...task,batch_id:Number(d.batch_id)},navigate,root),0);
      }});return;
   }
   let recommended;
   try{recommended=await get(`v5/feed/recommendation?batch_id=${Number(selectedBatch)}&shift=${encodeURIComponent(task.shift||'Morning')}`)}
   catch(e){alert(e.message);return}
   const strict=Boolean(recommended.restrict_to_assigned_mix||recommended.ration_id);
   const candidates=(strict?feeds.filter(x=>Number(x.item_id||x.id)===Number(recommended.assigned_item_id)):feeds)
     .filter(x=>Number(x.available_kg)>0);
   if(!candidates.length){
    alert(strict?`Assigned mix ${recommended.ration_name||''} is out of stock. Ask the storekeeper to receive or manufacture it.`:
     'No usable feed is in stock. Ask the storekeeper to receive it.');return;
   }
   const selected=candidates[0];
   fields=[{name:'batch_id',label:'Batch',type:'fixed',value:selectedBatch,
      display:batches.find(x=>x.id===Number(selectedBatch))?.name||`Batch ${selectedBatch}`},
    {name:'shift',label:'Shift',type:'fixed',value:task.shift||'Morning'},
    strict?{name:'item_id',label:'Assigned mix',type:'fixed',value:selected.item_id||selected.id,
       display:`${selected.name} · ${selected.available_kg} kg available`}:
      {name:'item_id',label:'Available feed or mix',type:'select',required:true,
       options:candidates.map(i=>({value:i.item_id||i.id,label:`${i.name} · ${i.available_kg} kg`}))},
    {name:'quantity_kg',label:'Actual quantity fed (kg)',type:'number',required:true,min:'.001',step:'.001'},
    {name:'notes',label:'Observation',type:'textarea',wide:true}];
 } else if(category==='watering')fields=[{name:'batch_id',label:'Batch',type:'select',required:true,options:subject},{name:'shift',label:'Shift',type:'select',required:true,options:[task.shift||'Morning']},{name:'notes',label:'Observations',type:'textarea',wide:true}];
 else if(category==='cleaning'){
   const p=(await safe(()=>get('v5/pens'),{items:[]})).items||[];
   const pens=p.filter(x=>!task.pen_id||x.id===task.pen_id);
   if(!pens.length)return alert('The manager needs to create and assign a pen before cleaning can be recorded.');
   fields=[{name:'pen_id',label:'Pen cleaned',type:'select',required:true,options:pens.map(x=>({value:x.id,label:`${x.name} · ${x.batch_name}`}))},{name:'frequency',label:'Period',type:'select',options:['daily','weekly','monthly'],value:task.frequency==='once'?'daily':task.frequency},{name:'notes',label:'Observation',type:'textarea',wide:true}];
 } else if(category==='weighing'){
   fields=[{name:'animal_id',label:'Animal',type:'select',required:true,options:animals.map(x=>({value:x.id,label:x.tag}))},{name:'weight_kg',label:'Weight (kg)',type:'number',required:true,min:'.001',step:'.001'},{name:'notes',label:'Observations',type:'textarea',wide:true}];
 } else if(category==='medication')fields=[{name:'animal_id',label:'Animal',type:'select',required:true,options:animals.map(x=>({value:x.id,label:x.tag}))},{name:'medicine_id',label:'Existing medicine',type:'select',required:true,options:(options.medicines||[]).map(x=>({value:x.id,label:x.name}))},{name:'frequency',label:'Period',type:'select',options:['daily','weekly','monthly'],value:task.frequency==='once'?'daily':task.frequency},{name:'notes',label:'Dose and veterinarian instructions / observations',type:'textarea',wide:true,required:true}];
 else if(category==='dipping')fields=[{name:'batch_id',label:'Batch',type:'select',required:true,options:subject},{name:'frequency',label:'Period',type:'select',options:['daily','weekly','monthly'],value:task.frequency==='once'?'daily':task.frequency},{name:'notes',label:'Dip / observation',type:'textarea',wide:true}];
 else if(category==='movement'){
   fields=[{name:'animal_id',label:'Animal being moved',type:'select',required:true,options:animals.map(x=>({value:x.id,label:x.tag}))},{name:'destination_batch_id',label:'Destination batch',type:'select',required:true,options:batches.map(x=>({value:x.id,label:x.name}))},{name:'notes',label:'Reason / observation',type:'textarea',wide:true}];
 } else fields=[{name:'batch_id',label:'Batch',type:'select',required:true,options:subject},{name:'frequency',label:'Period',type:'select',options:['daily','weekly','monthly'],value:task.frequency==='once'?'daily':task.frequency},{name:'notes',label:'Observation',type:'textarea',wide:true,required:true}];
 modalForm({title,fields,saveLabel:'Complete task',onSave:async d=>{
   for(const key of ['batch_id','pen_id','animal_id','medicine_id','item_id'])if(d[key])d[key]=Number(d[key]);
   if(category==='movement')await post('v5/routine/move',{animal_id:d.animal_id,destination_batch_id:+d.destination_batch_id,notes:d.notes,client_reference:crypto.randomUUID()});
   else if(category==='feeding')await post('v5/feeding/record',{batch_id:d.batch_id,shift:d.shift,extras:[{item_id:d.item_id,quantity_kg:d.quantity_kg}],notes:d.notes,client_reference:crypto.randomUUID()});
   else if(category==='weighing')await post(`v5/animals/${d.animal_id}/weight`,{weight_kg:d.weight_kg,notes:d.notes});
   else await post('v5/routines',{category,shift:d.shift||'Other',frequency:d.frequency||'daily',batch_id:category==='cleaning'?null:d.batch_id||null,pen_id:d.pen_id||null,animal_id:d.animal_id||null,product:category==='medication'?(options.medicines||[]).find(i=>i.id===d.medicine_id)?.name:null,notes:d.notes,client_reference:crypto.randomUUID()});
   await render(root,{navigate});
 }});
}
