import {get,can,safe,number,esc} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,listenRows,parentField,
 submoduleDirectory,recordsPreview,submoduleWorkspace,bindSubmodules,
 rememberedSubmodule,rememberSubmodule,barChart,panel} from '../../shared/ui.js';
import * as api from './service.js';

const fmt = (n,digits=0) => Number(n||0).toLocaleString(undefined,{maximumFractionDigits:digits});
const today = () => {const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')};
const labels={watering:'Watering',planting:'Planting',weeding:'Weeding',pruning:'Pruning',landscaping:'Landscaping',cleaning:'Cleaning',mowing:'Lawn mowing',mulching:'Mulching',fertilizing:'Fertilizing',inspection:'Inspection',other:'Other'};
const sections=[
 {id:'dashboard',title:'Dashboard',description:'Actual garden performance and key indicators'},
 {id:'areas',title:'Garden Areas',description:'Garden locations, size and purpose'},
 {id:'plants',title:'Plant Registry',description:'Plants, varieties, quantities and condition'},
 {id:'nursery',title:'Planting & Nursery',description:'Propagation and seedling survival'},
 {id:'watering',title:'Watering & Irrigation',description:'Shift-based water and irrigation records'},
 {id:'maintenance',title:'Maintenance & Landscaping',description:'Garden maintenance and planting records'},
 {id:'health',title:'Plant Health',description:'Disease, pests, treatment and follow-up'},
 {id:'routines',title:'Routines & Tasks',description:'Scheduled assignments and completion'},
 {id:'expenses',title:'Supplies & Costs',description:'Recorded materials, labour and expenses'},
 {id:'inspections',title:'Inspections',description:'Garden condition and corrective actions'},
 {id:'analytics',title:'Analytics & Reports',description:'Real-data operational and cost trends'},
];
const SHIFT=['morning','afternoon','evening','unscheduled'];
const workActions=['planting','weeding','pruning','landscaping','cleaning','mowing','mulching','fertilizing','inspection','other'];
const options=arr=>arr.map(x=>({value:x,label:labels[x]||x.replaceAll('_',' ')}));
const dates=(name,label='Date',value=today())=>({name,label,type:'date',value,required:true});
const money=()=>[{name:'direct_cost',label:'Other direct cost (not in Supplies)',type:'number',min:0,step:'.01',value:0},
 {name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'}];
const waterFields=()=>[{name:'water_litres',label:'Water used (litres)',type:'number',min:0,step:'.01',value:0},
 {name:'area_covered_m2',label:'Area covered (m²)',type:'number',min:0,step:'.01',value:0},
 {name:'labor_hours',label:'Employee hours',type:'number',min:0,step:'.01',value:0}];
const message=(txt)=>`<p class="garden-note">${esc(txt)}</p>`;
const sumCost = totals => (totals||[]).length ? totals.map(v=>`${fmt(v.amount,2)} ${esc(v.currency)}`).join(' · ') : 'No costs recorded';
const areaName=(areas,id)=>areas.find(x=>x.id===Number(id))?.name||`Area #${id}`;
const dueToday=(t,day)=>{
 if(!t.is_active || day<t.starts_on || (t.ends_on&&day>t.ends_on))return false;
 if(t.frequency==='once')return day===t.starts_on;
 const [a,b,c]=day.split('-').map(Number),[x,y,z]=t.starts_on.split('-').map(Number);
 if(t.frequency==='monthly')return c===z;
 if(t.frequency==='weekly')return new Date(a,b-1,c).getDay()===new Date(x,y-1,z).getDay();
 return t.frequency==='daily';
};
const gardenChart=(items,key,title,displayKey='month')=>{
 if(!items.length)return panel(title,message('No recorded data for this chart yet.'));
 return panel(title,barChart(items.map(p=>({label:p[displayKey],value:Number(p[key]||0)}))));
};

export async function render(root){
 const responses=await Promise.all([
  api.areas(),api.records(),api.dashboard(),api.plants(),api.nursery(),api.activities(),
  api.schedules(),api.health(),api.expenses(),api.inspections(),
  safe(()=>get('v5/ranches')),safe(()=>get('v5/stock/status')),safe(()=>get('v5/members')),
 ]);
 const [areaRes,legacyRes,report,plantRes,nurseryRes,workRes,scheduleRes,healthRes,expenseRes,inspectionRes,ranchRes,stockRes,membersRes]=responses;
 const gardens=areaRes.items||[], legacy=legacyRes.items||[], plants=plantRes.items||[],nursery=nurseryRes.items||[];
 const activities=workRes.items||[],schedules=scheduleRes.items||[],health=healthRes.items||[],expenses=expenseRes.items||[],inspections=inspectionRes.items||[];
 const ranches=ranchRes.items||[],inventory=(stockRes.items||[]).filter(x=>['gardening_tool','seed','seedling','fertilizer','compost','cleaning_supply'].includes(x.category));
 const members=(membersRes.items||[]).filter(x=>x.active);
 const editable=can('gardening.write'), supervisory=can('tasks.manage')||can('members.read');
 const byArea=(row)=>areaName(gardens,row.area_id);
 let section=rememberedSubmodule('gardening');if(section&&!sections.some(s=>s.id===section))section=null;
 const workByAction=(type)=>activities.filter(x=>type==='watering'?x.action==='watering':x.action!=='watering');
 const due=schedules.filter(t=>dueToday(t,today()));
 const todaysDone=new Set(activities.filter(a=>a.performed_on===today()&&a.schedule_id).map(a=>a.schedule_id));
 const m={...report.summary},monthly=report.monthly||[];
 const counts={dashboard:0,areas:gardens.length,plants:plants.length,nursery:nursery.length,watering:workByAction('watering').length+legacy.filter(x=>x.action==='watering').length,
  maintenance:workByAction('maintenance').length+legacy.filter(x=>x.action!=='watering').length,health:health.length,routines:schedules.length,expenses:expenses.length,inspections:inspections.length,analytics:monthly.length};
 const totalCosts=sumCost(m.expenses_by_currency);
 const gardenMetrics=()=>kpis([
  {label:'Garden areas',value:fmt(m.areas),icon:'gardening'},
  {label:'Total garden area',value:`${fmt(m.area_m2,2)} m²`,icon:'field'},
  {label:'Living plants',value:fmt(m.plants),icon:'planting'},
  {label:'Tasks completed today',value:`${fmt(m.today_complete)} / ${fmt(m.today_due)}`,icon:'calendar'},
  {label:'Water recorded',value:`${fmt(m.water_litres,2)} L`,icon:'watering'},
  {label:'Garden condition',value:m.condition_score==null?'Not inspected':`${fmt(m.condition_score,2)} / 5`,icon:'records'},
  {label:'Open health issues',value:fmt(m.health_open),icon:'health'},
  {label:'Overdue tasks (7 days)',value:fmt(m.overdue_tasks_7d),icon:'calendar'},
  {label:'Nursery survival',value:m.nursery_survival_pct==null?'Not recorded':`${fmt(m.nursery_survival_pct,1)}%`,icon:'planting'},
  {label:'Activities recorded',value:fmt(m.recorded_activities),icon:'records'},
 ]);
 function charts(){
  return `<div class="garden-charts">${gardenChart(monthly,'activities','Activities by month')}${gardenChart(monthly,'water_litres','Water consumption (litres)')}</div>
    ${panel('Recorded expenditure',`<strong>${totalCosts}</strong>${message('Currencies are kept separate; amounts are actual recorded costs, not estimated net profit.')}`)}
    ${panel('Monthly costs by currency',monthly.length?table(monthly.flatMap(v=>(v.costs||[]).map(c=>({month:v.month,currency:c.currency,amount:c.amount}))),[['month','Month'],['currency','Currency'],['amount','Recorded cost']],{click:false}):message('No expenditure data recorded.'))}
    ${panel('Plant condition',table(report.plant_conditions||[],[['condition','Condition'],['quantity','Quantity']],{click:false,empty:'No plants registered.'}))}
    ${panel('Latest inspections',table((report.latest_inspections||[]).map(x=>({...x,area:areaName(gardens,x.area_id)})),[['area','Garden area'],['inspected_on','Inspected'],['score','Score / 5']],{click:false,empty:'No inspections recorded.'}))}`;
 }
 function home(){return submoduleDirectory('Gardening',sections,counts)+
  `<section class="garden-metrics">${gardenMetrics()}</section>`+
  `<div class="garden-summary-row"><section class="panel"><h2>Recorded garden costs</h2><div class="garden-feature-metric">${totalCosts}</div>${message('Total reflects completed work, logged expenses and health treatment costs.')}</section>
   <section class="panel"><h2>Today’s tasks</h2><div class="garden-feature-metric">${fmt(m.today_complete)} / ${fmt(m.today_due)}</div>${message('Scheduled gardening work due today. Completed routines are counted once per schedule and day.')}</section></div>`+
  `<div class="module-previews">${recordsPreview('Recent garden activities',activities.slice(0,5).map(a=>({...a,area:byArea(a)})),[['area','Garden'],['action','Work'],['performed_on','Date'],['shift','Shift']])}
  ${recordsPreview('Garden areas',gardens.slice(0,5),[['name','Garden'],['type','Purpose'],['area_m2','m²']])}</div>${charts()}`}
 const configs={
  areas:{title:'Garden Areas',items:gardens,cols:[['name','Garden area'],['type','Purpose'],['area_m2','Area m²'],['ranch_id','Ranch ID']],action:'Add garden area'},
  plants:{title:'Plant Registry',items:plants.map(x=>({...x,area:byArea(x)})),cols:[['area','Garden'],['name','Plant'],['category','Category'],['quantity','Quantity'],['condition','Condition']],action:'Register plants'},
  nursery:{title:'Planting & Nursery',items:nursery.map(x=>({...x,area:byArea(x),survival_rate:x.seeds_started?`${fmt(x.survived/x.seeds_started*100,1)}%`:'—'})),cols:[['area','Garden'],['plant_name','Plant'],['seeds_started','Started'],['germinated','Germinated'],['survived','Survived'],['survival_rate','Survival']],action:'Add nursery batch'},
  watering:{title:'Watering & Irrigation',items:[...activities.filter(x=>x.action==='watering'),...legacy.filter(x=>x.action==='watering').map(x=>({...x,shift:'Legacy',water_litres:null}))].map(x=>({...x,area:byArea(x)})),cols:[['area','Garden'],['performed_on','Date'],['shift','Shift'],['water_litres','Water L'],['labor_hours','Hours']],action:'Record watering'},
  maintenance:{title:'Maintenance & Landscaping',items:[...activities.filter(x=>x.action!=='watering'),...legacy.filter(x=>x.action!=='watering').map(x=>({...x,shift:'Legacy'}))].map(x=>({...x,area:byArea(x)})),cols:[['area','Garden'],['action','Activity'],['performed_on','Date'],['shift','Shift'],['labor_hours','Hours']],action:'Record maintenance'},
  health:{title:'Plant Health',items:health.map(x=>({...x,area:byArea(x)})),cols:[['area','Garden'],['observed_on','Date'],['issue','Issue'],['severity','Severity'],['status','Status'],['follow_up_on','Follow-up']],action:'Record health issue'},
  routines:{title:'Routines & Tasks',items:schedules.map(x=>({...x,area:byArea(x),assigned_name:members.find(m=>m.user_id===x.assigned_to)?.name||'Unassigned',today_status:dueToday(x,today())?(todaysDone.has(x.id)?'Completed':'Due today'):'Not due today'})),cols:[['title','Task'],['area','Garden'],['action','Activity'],['shift','Shift'],['frequency','Frequency'],['assigned_name','Assigned to'],['today_status','Today']],action:'Schedule garden task'},
  expenses:{title:'Supplies & Costs',items:expenses.map(x=>({...x,area:byArea(x)})),cols:[['area','Garden'],['spent_on','Date'],['category','Category'],['description','Item / Work'],['total_cost','Amount'],['currency','Currency']],action:'Record expense'},
  inspections:{title:'Inspections',items:inspections.map(x=>({...x,area:byArea(x)})),cols:[['area','Garden'],['inspected_on','Date'],['overall_score','Score / 5'],['corrective_action','Follow-up action'],['follow_up_on','Due']],action:'Record inspection'},
 };
 function draw(){
  if(!section){root.innerHTML=home();bind();return;}
  if(section==='dashboard'||section==='analytics'){
   root.innerHTML=head(section==='dashboard'?'Garden Dashboard':'Garden Analytics','Real figures derived from your registered garden records')+
     submoduleWorkspace('Gardening',sections,section,`<div class="garden-report-actions"><strong>Export actual garden records</strong> <button type="button" class="btn" data-export="xlsx">Excel</button> <button type="button" class="btn" data-export="pdf">PDF</button> <button type="button" class="btn" data-export="csv">CSV</button></div><div class="garden-metrics">${gardenMetrics()}</div>${charts()}`);
   root.querySelectorAll('[data-export]').forEach(btn=>btn.addEventListener('click',()=>exportReport(btn.dataset.export)));
   bind();return;
  }
  const cfg=configs[section];if(!cfg)return;
  let intro='';
  if(section==='watering')intro=message('Record morning, afternoon or evening watering separately. Original V6 records remain visible as legacy entries.');
  if(section==='expenses')intro=message('Costs are grouped by currency. Garden supplies remain managed in central Inventory; adding a cost here does not automatically issue inventory stock.');
  if(section==='routines')intro=message('Assigned staff can complete due tasks below. This schedule is dedicated to Gardening and does not automatically create a task in the separate employee Tasks module.');
  if(section==='nursery')intro=message('Nursery survival rates use registered counts. Harvest and commercial vegetable sales remain in Crop Farming.');
  if(section==='inspections')intro=message('Ratings use four criteria scored 1–5. Photos require persistent storage and are not yet enabled.');
  const extra=section==='routines'?`<section class="panel garden-due"><h2>Tasks due today</h2>${due.length?due.map(t=>`<div class="garden-due-row"><span><strong>${esc(t.title)}</strong><small>${esc(areaName(gardens,t.area_id))} · ${esc(t.shift)} · ${esc(t.action)}</small></span>${todaysDone.has(t.id)?'<span class="garden-done">Completed</span>':editable?`<button type="button" class="btn small" data-complete="${t.id}">Complete</button>`:'<span>Pending</span>'}</div>`).join(''):message('No gardening routines are scheduled for today.')}</section>`:'';
  root.innerHTML=head(cfg.title,'Gardening records and operations',editable&&(!['routines'].includes(section)||supervisory)?button(cfg.action,'garden-add','commit'):'')+
    submoduleWorkspace('Gardening',sections,section,`${intro}${extra}${table(cfg.items,cfg.cols,{empty:'No records available yet. Add an entry to begin.'})}`);
  listenRows(root,cfg.items,x=> editable && ['areas','plants','nursery','health','routines'].includes(section) && (supervisory || !['areas','routines'].includes(section)) ? edit(section,x) : detailModal(x,{title:cfg.title+' details'}));
  root.querySelector('#garden-add')?.addEventListener('click',create);
  root.querySelectorAll('[data-complete]').forEach(btn=>btn.onclick=()=>complete(Number(btn.dataset.complete)));
  bind();
 }
 function bind(){bindSubmodules(root,id=>{section=id;rememberSubmodule('gardening',id);draw()})}
 async function exportReport(format){
  const btn=root.querySelector(`[data-export="${format}"]`);
  if(btn)btn.disabled=true;
  try{
   const response=await get(`v6/gardening/v2/export?format=${format}`);
   const blob=await response.blob();
   const u=URL.createObjectURL(blob);
   const link=document.createElement('a');link.href=u;link.download=`cape-ranch-gardening-${today()}.${format}`;
   document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(u);
  }catch(e){alert(e.message)}finally{if(btn)btn.disabled=false}
 }
 function complete(id){
  const t=schedules.find(t=>t.id===id);if(!t)return;
  modalForm({title:`Complete: ${t.title}`,saveLabel:'Record completion',fields:[dates('performed_on'),...waterFields(),...money(),{name:'observations',label:'Observations',type:'textarea',wide:true}],onSave:async d=>{await api.completeSchedule(id,d);await render(root)}});
 }
 function edit(mode, item){
  if(mode==='areas')return form('Update garden area',[
   {name:'name',label:'Garden area',required:true,value:item.name},
   {name:'area_m2',label:'Area (m²)',type:'number',min:'.01',step:'.01',value:item.area_m2},
   {name:'type',label:'Garden purpose',type:'select',options:['landscaping','flower_beds','vegetables','lawn','trees','other'],value:item.type},
   {name:'notes',label:'Notes',type:'textarea',wide:true,value:item.notes||''}],d=>api.updateArea(item.id,d));
  if(mode==='plants')return form('Update plant condition and quantity',[
   {name:'quantity',label:'Living / recorded quantity',type:'number',min:0,step:1,value:item.quantity,required:true},
   {name:'condition',label:'Condition',type:'select',options:['healthy','stressed','diseased','damaged','dead','replaced'],value:item.condition},
   {name:'notes',label:'Notes',type:'textarea',wide:true,value:item.notes||''}],d=>api.updatePlant(item.id,d));
  if(mode==='nursery')return form('Update nursery progress',[
   {name:'germinated',label:'Germinated count',type:'number',min:0,step:1,value:item.germinated,required:true},
   {name:'survived',label:'Survived count',type:'number',min:0,step:1,value:item.survived,required:true},
   {name:'status',label:'Status',type:'select',options:['active','transplanted','completed','cancelled'],value:item.status},
   {name:'notes',label:'Notes',type:'textarea',wide:true,value:item.notes||''}],d=>api.updateNursery(item.id,d));
  if(mode==='health')return form('Update plant health follow-up',[
   {name:'treatment',label:'Treatment / safety requirements',type:'textarea',wide:true,value:item.treatment||''},
   {name:'follow_up_on',label:'Follow-up date',type:'date',value:item.follow_up_on||''},
   {name:'status',label:'Status',type:'select',options:['open','treating','recovered','closed'],value:item.status}],d=>api.updateHealth(item.id,d));
  if(mode==='routines')return form('Manage routine',[
   {name:'is_active',label:'Task remains active',type:'checkbox',value:item.is_active}],d=>api.updateSchedule(item.id,d));
 }
 function create(){
  if(section==='areas'){
   if(!ranches.length){alert('Register a ranch first.');return}
   return form('Register garden area',[parentField('ranch_id','Ranch',ranches),{name:'name',label:'Garden area',required:true},
   {name:'type',label:'Garden purpose',type:'select',options:['landscaping','flower_beds','vegetables','lawn','trees','other'],value:'landscaping'},
   {name:'area_m2',label:'Size (m²)',type:'number',min:'.01',step:'.01',required:true},{name:'notes',label:'Notes',type:'textarea',wide:true}],api.createArea);
  }
  if(!gardens.length){alert('Register a garden area first.');return}
  const area=()=>parentField('area_id','Garden area',gardens);
  if(section==='plants')return form('Register garden plants',[area(),{name:'name',label:'Plant name',required:true},
    {name:'category',label:'Plant category',type:'select',options:['ornamental','flower','tree','hedge','vegetable','lawn','herb','other'],value:'ornamental'},
    {name:'variety',label:'Variety'},{name:'quantity',label:'Number of plants',type:'number',min:1,step:1,value:1,required:true},
    {name:'planted_on',label:'Planted date',type:'date'},{name:'source',label:'Source / supplier'},
    {name:'unit_purchase_cost',label:'Purchase cost per plant',type:'number',min:0,step:'.01',value:0},
    {name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'},
    {name:'condition',label:'Condition',type:'select',options:['healthy','stressed','diseased','damaged','dead','replaced'],value:'healthy'},
    {name:'notes',label:'Notes',type:'textarea',wide:true}],api.createPlant);
  if(section==='nursery')return form('Start nursery batch',[area(),{name:'plant_name',label:'Plant / variety',required:true},
   {name:'method',label:'Method',type:'select',options:['seed','cutting','transplant','grafting','other'],value:'seed'},dates('started_on','Started on'),
   {name:'seeds_started',label:'Started quantity',type:'number',min:1,step:1,required:true},
   {name:'germinated',label:'Germinated count',type:'number',min:0,step:1,value:0},
   {name:'survived',label:'Survived count',type:'number',min:0,step:1,value:0},
   {name:'status',label:'Status',type:'select',options:['active','transplanted','completed','cancelled'],value:'active'},
   {name:'notes',label:'Notes',type:'textarea',wide:true}],api.createNursery);
  if(section==='watering'||section==='maintenance')return form(section==='watering'?'Record watering':'Record garden maintenance',[
   area(),{name:'action',label:'Activity',type:section==='watering'?'fixed':'select',display:'Watering',value:section==='watering'?'watering':'planting',options:options(workActions),required:true},
   dates('performed_on'),{name:'shift',label:'Shift',type:'select',options:SHIFT,value:section==='watering'?'morning':'unscheduled'},
   ...waterFields(),...money(),{name:'observations',label:'Observations',type:'textarea',wide:true}],api.createActivity);
  if(section==='health')return form('Record garden health',[area(),{name:'observed_on',label:'Observed date',type:'date',value:today(),required:true},
   {name:'issue',label:'Pest, disease or problem',required:true},
   {name:'severity',label:'Severity',type:'select',options:['low','moderate','high','critical'],value:'low'},
   {name:'affected_count',label:'Affected plants',type:'number',min:0,step:1,value:0},
   {name:'treatment',label:'Treatment / safety requirements',type:'textarea',wide:true},
   {name:'follow_up_on',label:'Follow-up date',type:'date'},
   {name:'status',label:'Status',type:'select',options:['open','treating','recovered','closed'],value:'open'},
   {name:'expense',label:'Treatment expense',type:'number',min:0,step:'.01',value:0},
   {name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'}],api.createHealth);
  if(section==='routines')return form('Schedule garden routine',[area(),{name:'title',label:'Task',required:true},
   {name:'action',label:'Activity',type:'select',options:options(Object.keys(labels)),value:'watering'},
   {name:'frequency',label:'Recurrence',type:'select',options:['once','daily','weekly','monthly'],value:'daily'},
   {name:'shift',label:'Shift',type:'select',options:SHIFT,value:'morning'},
   ...(members.length?[{name:'assigned_to',label:'Assigned employee (optional)',type:'select',options:members.map(m=>({value:m.user_id,label:m.name}))}]:[]),
   dates('starts_on','Start date'),{name:'ends_on',label:'End date',type:'date'},
   {name:'instructions',label:'Instructions',type:'textarea',wide:true}],api.createSchedule);
  if(section==='expenses')return form('Record garden expense',[area(),dates('spent_on'),
   {name:'category',label:'Cost category',type:'select',options:['seed','seedling','fertilizer','compost','treatment','tools','water','labor','machinery','transport','other'],value:'labor'},
   {name:'description',label:'Expense description',required:true},
   {name:'quantity',label:'Quantity',type:'number',min:'.001',step:'.001',value:1,required:true},
   {name:'unit',label:'Unit',value:'unit',required:true},
   {name:'unit_cost',label:'Price per unit',type:'number',min:0,step:'.01',value:0},
   {name:'other_cost',label:'Other cost',type:'number',min:0,step:'.01',value:0},
   {name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'},
   ...(inventory.length?[{name:'inventory_item_id',label:'Inventory item reference (no stock issue)',type:'select',options:inventory.map(i=>({value:i.id,label:i.name}))}]:[]),
   {name:'notes',label:'Notes',type:'textarea',wide:true}],api.createExpense);
  if(section==='inspections')return form('Inspect garden area',[area(),dates('inspected_on'),
   ...['cleanliness','plant_health','weed_control','irrigation'].map(name=>({name,label:name.replaceAll('_',' ')+' (1 to 5)',type:'number',min:1,step:1,value:3,required:true})),
   {name:'corrective_action',label:'Corrective action',type:'textarea',wide:true},
   {name:'follow_up_on',label:'Follow-up due date',type:'date'}],api.createInspection);
 }
 function form(title,fields,submit){modalForm({title,fields,saveLabel:'Save record',onSave:async d=>{
   for(const key of ['ranch_id','area_id','plant_id','assigned_to','inventory_item_id'])if(d[key]!==undefined)d[key]=Number(d[key]);
   await submit(d);await render(root);
 }})}
 draw();
}
