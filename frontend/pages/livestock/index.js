import {can,esc,number,toast} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,parentField,listenRows,submoduleDirectory,recordsPreview,submoduleWorkspace,bindSubmodules,rememberedSubmodule,rememberSubmodule} from '../../shared/ui.js';
// Keep the page and its service on the same release URL. A new page with a
// cached V7 service fails with `api.workspace is not a function`.
import * as api from './service.js?v=8.3.0';

// Livestock & Poultry V8: all figures are based on the current organization's records.
// Existing approved V6.5 shared UI and photographic layout stay untouched.
const isoToday=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
const currencies=['TZS','USD','KES','EUR'];
const species=['cattle','goat','sheep','pig','horse','rabbit','chicken','duck','turkey','quail','goose','guinea_fowl','other'];
const poultry=new Set(['chicken','duck','turkey','quail','goose','guinea_fowl']);
const sections=[
 ['overview','Overview','Livestock numbers, activity and financial snapshot'],
 ['projects','Projects','Plan and manage animal production projects'],
 ['groups','Herds & Flocks','Species, populations and group management'],
 ['animals','Animals & Birds','Separate animal and bird registration with herd/flock inheritance'],
 ['houses','Housing','Barns, pens, coops, assignments and capacity'],
 ['routine','Daily Routine','Reusable shift reminders and daily completion checklists'],
 ['breeding','Breeding','Mating, pregnancy alerts, birth cohorts and pedigree'],
 ['health','Veterinary & Health','Treatment, vaccination and follow-up care'],
 ['weights','Growth & Weighing','Body weights, weight gain and daily growth'],
 ['production','Production','Eggs, milk, births, mortality and wool'],
 ['incubations','Hatchery & Incubation','Egg setting, hatch dates and results'],
 ['products','Product Inventory','Collected products available for selling'],
 ['costs','Project Costs','Project expenses and finance posting'],
 ['sales','Animal Sales','Per-head and per-kg sales with live preview'],
 ['product_sales','Product Sales','Sell eggs, milk, wool and other products'],
 ['performance','Performance & Analytics','Project contribution and production trends']
].map(([id,title,description])=>({id,title,description}));
// Keep Livestock image URLs independently versioned; no shared UI changes.
// Every section has one unique, locally stored photograph in public/images/v65/livestock.
const livestockDirectory=(...args)=>submoduleDirectory(...args).replace(
 /(src="\/frontend\/public\/images\/v65\/livestock\/[^"?]+\.webp)"/g,
 '$1?v=8.3.0"'
);
const rowsFor={overview:null,projects:'projects',groups:'groups',animals:'animals',houses:'houses',routine:'care',breeding:'breeding',health:'health',weights:'weights',production:'production',incubations:'incubations',products:'products',costs:'costs',sales:'sales',product_sales:'product_sales',performance:null};
const cols={
 projects:[['name','Project'],['purpose','Purpose'],['start_date','Start'],['currency','Currency']],
 groups:[['name','Herd / flock'],['species','Species'],['breed','Breed'],['purpose','Purpose'],['project_name','Project'],['head_count','Population']],
 animals:[['tag','Tag'],['species','Species'],['breed','Breed'],['sex','Sex'],['group_name','Herd/flock'],['birth_date','Born'],['age_days','Age (days)'],['status','Status']],
 houses:[['code','Code'],['name','House'],['house_type','Type'],['capacity','Capacity'],['occupancy','Occupied'],['available','Free places']],
 routine:[['target_name','Animal / flock'],['performed_on','Date'],['shift','Shift'],['activity','Activity'],['quantity','Quantity'],['unit','Unit'],['expense','Cost'],['currency','Currency']],
 breeding:[['target_name','Animal / flock'],['service_date','Service date'],['method','Method'],['sire_tag','Sire'],['expected_date','Expected'],['days_until_delivery','Days remaining'],['alert','Follow-up'],['outcome','Outcome']],
 health:[['target_name','Animal / flock'],['performed_on','Date'],['action','Action'],['condition','Condition'],['medication','Medication'],['next_due','Next due'],['status','Status']],
 weights:[['target_name','Animal / flock'],['measured_on','Date'],['weight_kg','Weight (kg)'],['sample_size','Sample'],['gain_kg','Gain (kg)'],['adg_kg_day','ADG (kg/day)']],
 production:[['target_name','Animal / flock'],['performed_on','Date'],['action','Event'],['quantity','Quantity'],['unit','Unit'],['cost','Cost']],
 incubations:[['target_name','Flock'],['batch_code','Batch'],['eggs_set','Eggs set'],['set_on','Set date'],['expected_on','Expected hatch'],['eggs_hatched','Hatched'],['hatch_rate_pct','Hatch %'],['status','Status']],
 products:[['target_name','Source'],['product','Product'],['collected_on','Collected'],['quantity_received','Received'],['quantity_sold','Sold'],['available','Available'],['unit','Unit']],
 costs:[['project_name','Project'],['category','Category'],['description','Description'],['amount','Cost'],['currency','Currency'],['performed_on','Date']],
 sales:[['target_name','Animal / flock'],['sale_date','Date'],['buyer','Buyer'],['price_basis','Basis'],['quantity','Head'],['weight_kg','Weight (kg)'],['gross','Revenue'],['currency','Currency']],
 product_sales:[['sold_on','Date'],['buyer','Buyer'],['quantity','Quantity'],['price_per_unit','Unit price'],['gross','Revenue'],['currency','Currency']]
};
const actions={projects:'+ New project',groups:'+ Register herd / flock',houses:'+ Add housing',routine:'+ Create routine reminder',breeding:'+ Breeding record',health:'+ Veterinary record',weights:'+ Record weight',production:'+ Production event',incubations:'+ Incubation batch',costs:'+ Record cost',sales:'+ Sell livestock',product_sales:'+ Sell product'};
const choose=(name,label,items,required=true)=>parentField(name,label,items,{required});
const f=(name,label,extra={})=>({name,label,...extra});
const dateField=(name,label='Date')=>f(name,label,{type:'date',required:true,value:isoToday()});
const currencyField=()=>f('currency','Currency',{type:'select',options:currencies,value:'TZS',required:true});
const num=(name,label,min=0,step='.001',required=false)=>f(name,label,{type:'number',min,step,required});
const optCharge=()=>[num('cost_quantity','Optional cost quantity',0.001,'.001'),f('cost_unit','Unit (head, item, hour)',{value:'head'}),num('unit_cost','Optional cost per unit',0,'.01'),f('cost_description','Cost description'),currencyField()];
function takeCharge(d){const quantity=d.cost_quantity;const unit_cost=d.unit_cost;const unit=d.cost_unit||'head';const description=d.cost_description;const currency=d.currency||'TZS';delete d.cost_quantity;delete d.cost_unit;delete d.unit_cost;delete d.cost_description;delete d.currency;if(quantity!==undefined||unit_cost!==undefined){if(quantity===undefined||unit_cost===undefined)throw Error('Enter both cost quantity and unit cost');d.charge={quantity,unit,unit_cost,description,currency}}return d}
const kindOf=s=>poultry.has(String(s||'').toLowerCase())?'bird':'animal';
const weekdayOptions=['Every day','Monday to Friday','Weekends','Custom days'];
const noteField=()=>f('notes','Notes',{type:'textarea',wide:true});
const options=(name,label,values,required=true)=>f(name,label,{type:'select',options:values,required});
const n=v=>Number(v||0);
const nice=v=>n(v).toLocaleString(undefined,{maximumFractionDigits:2});
const pickTargets=(ws,{flocksOnly=false,femaleOnly=false}={})=>[
 ...(flocksOnly?[]:(ws.animals||[]).filter(x=>x.status==='active'&&(!femaleOnly||x.sex!=='male')).map(x=>({value:`a-${x.id}`,label:`Animal · ${x.tag}`}))),
 ...(ws.groups||[]).filter(x=>!flocksOnly||poultry.has(String(x.species).toLowerCase())).map(x=>({value:`g-${x.id}`,label:`Group · ${x.name}`}))
];
const targetField=(ws,filters={})=>{
 const targets=pickTargets(ws,filters);
 return {name:'target',label:'Animal or group',type:targets.length===1?'fixed':'select',value:targets.length===1?targets[0].value:undefined,display:targets[0]?.label,options:targets,required:true};
};
function resolveTarget(d){const value=String(d.target||'');const [type,id]=value.split('-');delete d.target;if(!['a','g'].includes(type)||!Number.isInteger(+id)||+id<=0)throw Error('Select a valid animal or group');d[type==='a'?'animal_id':'group_id']=+id;return d}
function requireItems(items,message){if(!items.length){toast(message,true);return false}return true}
function form(title,fields,onSave,saveLabel='Save record',intro=''){
 modalForm({title,fields,saveLabel,intro,onSave:async values=>{await onSave({...values})}});
 const modal=document.querySelector('#modal-root');
 const qty=modal?.querySelector('[name=cost_quantity]'),rate=modal?.querySelector('[name=unit_cost]');
 if(qty&&rate){
  const preview=document.createElement('div');preview.className='liv-sale-preview liv-cost-preview';
  rate.closest('label')?.after(preview);
  const update=()=>{const q=n(qty.value),r=n(rate.value);preview.textContent=qty.value&&rate.value?`Optional cost total: ${(q*r).toLocaleString(undefined,{maximumFractionDigits:2})} (${modal.querySelector('[name=currency]')?.value||'TZS'})`:'Optional cost: leave both quantity and cost per unit empty if there is no expense.'};
  ['input','change'].forEach(e=>modal.querySelector('form')?.addEventListener(e,update));update();
 }
}
function figure(title,values,{unit='',precision=0}={}){
 const data=(values||[]).filter(x=>Number.isFinite(+x.value)).slice(0,12);
 if(!data.length)return `<section class="liv-figure"><h3>${esc(title)}</h3><p class="muted">No recorded activity yet.</p></section>`;
 const top=Math.max(1,...data.map(v=>n(v.value)));
 return `<section class="liv-figure"><h3>${esc(title)}</h3><div class="liv-bars" role="img" aria-label="${esc(title)}">${data.map(item=>{
 const val=n(item.value);const percentage=Math.max(val>0?3:0,Math.min(100,100*val/top));
 return `<div class="liv-bar"><span class="liv-bar-value" title="${esc(item.label)}: ${esc(val)} ${esc(unit)}">${esc(val.toLocaleString(undefined,{maximumFractionDigits:precision}))}</span><div class="liv-bar-track"><span style="height:${percentage}%;--liv-bar-color:${['#12865c','#e59138','#3f82d3','#8159b7','#d95a66','#139ca7','#a0a13e','#c47839'][data.indexOf(item)%8]}"></span></div><span class="liv-bar-label" title="${esc(item.label)}">${esc(item.label)}</span></div>`;
 }).join('')}</div></section>`;
}
function distribution(rows,key,{measure=null}={}){
 const groups=new Map();for(const row of rows){const category=String(row[key]??'Unspecified');groups.set(category,(groups.get(category)||0)+(measure?n(row[measure]):1))}
 return [...groups].sort((a,b)=>b[1]-a[1]).slice(0,12).map(([label,value])=>({label,value}));
}
function financialFigures(rows,amountField,groupField){
 const byCurrency={};for(const row of rows){const currency=String(row.currency||'TZS');byCurrency[currency]??={};const key=String(row[groupField]||'other');byCurrency[currency][key]=(byCurrency[currency][key]||0)+n(row[amountField])}
 return Object.entries(byCurrency).map(([currency,items])=>figure(`Recorded ${amountField.replaceAll('_',' ')} · ${currency}`,Object.entries(items).sort((a,b)=>b[1]-a[1]).map(([label,value])=>({label,value})),{precision:0})).join('');
}
function chartsFor(area,rows){
 if(!rows.length)return '';
 if(area==='houses')return figure('Occupied places by housing',rows.map(r=>({label:r.code,value:r.occupancy})),{unit:'head'});
 if(area==='groups')return figure('Herd and flock population by species',distribution(rows,'species',{measure:'head_count'}));
 if(area==='weights')return figure('Recent weight recordings (kg)',rows.slice(0,12).reverse().map(r=>({label:`#${r.id}`,value:r.weight_kg})),{precision:1});
 if(area==='costs')return financialFigures(rows,'amount','category');
 if(area==='sales'||area==='product_sales')return financialFigures(rows,'gross','buyer');
 if(area==='routine')return figure('Completed routine checks',distribution(rows,'task_name'));
 if(area==='production')return figure('Recorded event counts by activity',distribution(rows,'action'));
 if(area==='incubations')return figure('Incubation batches by status',distribution(rows,'status'));
 if(area==='products')return figure('Product lot counts',distribution(rows,'product'));
 if(area==='projects')return figure('Projects by purpose',distribution(rows,'purpose'));
 if(area==='animals')return figure('Registered animals by species',distribution(rows,'species'));
 if(area==='breeding')return figure('Breeding outcomes',distribution(rows,'outcome'));
 if(area==='health')return figure('Health activities',distribution(rows,'action'));
 return '';
}
function financeTable(data){return data.length?table(data,[['currency','Currency'],['revenue','Recorded revenue'],['tracked_costs','Tracked costs'],['recorded_contribution','Recorded contribution']],{click:false}):'<p class="muted">No eligible financial transactions recorded yet.</p>'}
function overview(ws){const s=ws.dashboard;return `<div class="liv-overview">${kpis([
 {label:'Herd/flock population',value:number(s.population),icon:'livestock'},
 {label:'Herds & flocks',value:number(s.herds),icon:'livestock'},
 {label:'Registered active tags',value:number(s.registered_animals),icon:'livestock'},
 {label:'Health due',value:number(s.health_due),icon:'livestock'},
 {label:'Housing capacity alerts',value:number(s.over_capacity),icon:'livestock'},
 {label:'Active incubations',value:number(s.active_incubations),icon:'livestock'},
 {label:'Product lots',value:number(s.product_lots),icon:'inventory'},
 {label:'Deliveries due ≤14d',value:number(ws.linked.alerts.births_due_14_days),icon:'livestock'}
 ])}<div class="liv-chart-grid">
 ${figure('Population by species',s.species.map(x=>({label:x.species,value:x.head_count})))}
 ${figure('Eggs collected by month · pieces',s.months.map(x=>({label:x.month.slice(5),value:x.eggs})))}
 ${figure('Births by month · head',s.months.map(x=>({label:x.month.slice(5),value:x.births})))}
 ${figure('Mortality by month · head',s.months.map(x=>({label:x.month.slice(5),value:x.mortality})))}
 </div><section class="panel liv-finance"><h3>Recorded commercial position</h3>${financeTable(s.finance)}<p class="muted liv-note">${esc(s.note)}</p></section>
 <div class="module-previews">${recordsPreview('Recent production',s.recent_production,[['action','Activity'],['performed_on','Date'],['quantity','Quantity'],['unit','Unit']])}${recordsPreview('Recent animal sales',s.recent_sales,[['buyer','Buyer'],['quantity','Head'],['gross','Revenue'],['currency','Currency']])}</div></div>`}
function performanceView(projects){const money=projects.flatMap(p=>(p.currencies||[]).map(x=>({...x,name:p.name})));return (money.length?`<div class="liv-chart-grid">${financialFigures(money,'product_revenue','name')}${financialFigures(money,'direct_costs','name')}</div>`:'')+(projects.length?projects.map(p=>`<div class="panel liv-project-panel"><h3>${esc(p.name)}</h3><p class="muted">${esc(p.groups)} assigned herds or flocks</p>${p.currencies?.length?table(p.currencies,[['currency','Currency'],['direct_costs','Project costs'],['activity_costs','Production costs'],['care_costs','Care costs'],['veterinary_costs','Veterinary costs'],['registration_costs','Registration costs'],['routine_costs','Daily routines'],['product_revenue','Product revenue'],['animal_sales','Livestock sales'],['recorded_contribution','Recorded contribution']],{click:false}):'<p class="muted">No traceable costs or sales yet.</p>'}</div>`).join(''):'<div class="empty">No projects yet. Create a project and assign herds or flocks.</div>')}

export async function render(root){
 if (typeof api.workspace !== 'function') {
   throw new Error('Livestock V8.0.1 service is missing. Reapply the V8.0.1 installer and reload the page.');
 }
 const [ws,linked]=await Promise.all([api.workspace(),api.connectedContext()]);
 const profiles=new Map(linked.group_profiles.map(x=>[x.group_id,x]));
 const projectByGroup=new Map(linked.group_projects.map(x=>[x.group_id,x.project_id]));
 const projectNames=new Map(ws.projects.map(x=>[x.id,x.name]));
 ws.groups=ws.groups.map(x=>({...x,breed:profiles.get(x.id)?.breed||null,production_stage:profiles.get(x.id)?.production_stage||null,project_id:projectByGroup.get(x.id),project_name:projectNames.get(projectByGroup.get(x.id))||'Not assigned'}));
 ws.animals=ws.animals.map(x=>({...x,group_name:ws.groups.find(g=>g.id===x.group_id)?.name||'—',age_days:x.birth_date?Math.max(0,Math.floor((new Date(linked.today+'T00:00:00Z')-new Date(x.birth_date+'T00:00:00Z'))/86400000)):null}));
 ws.linked=linked;
 const write=can('livestock.write');let area=rememberedSubmodule('livestock');if(area&&!sections.some(x=>x.id===area))area=null;
 let rows=[],projectResults=[],housingHistory=[],housingAssignments=[],routineToday=null,lineageData=null,loading=false,shift='all';
 const decorate=x=>({...x,target_name:x.animal_id?(ws.animals.find(a=>a.id===x.animal_id)?.tag||`Animal #${x.animal_id}`):x.group_id?(ws.groups.find(g=>g.id===x.group_id)?.name||`Group #${x.group_id}`):'—'});
 const selectArea=async id=>{area=id;shift='all';rememberSubmodule('livestock',id);await load()};
 const load=async()=>{
  if(!area){rows=[];draw();return}
  loading=true;draw();
  try{if(area==='performance'){projectResults=(await api.performance()).items||[]}else if(area==='houses'){const [a,b,c]=await Promise.all([api.records('houses'),api.records('placements'),api.records('movements')]);rows=(a.items||[]).map(decorate);housingAssignments=b.items||[];housingHistory=c.items||[]}else if(area==='groups'){rows=ws.groups;}else if(area==='animals'){rows=ws.animals;}else if(area==='routine'){const [history,legacy,today]=await Promise.all([api.records('routine_completions'),api.records('care'),api.todayRoutines()]);rows=[...(history.items||[]).map(x=>({...x,task_name:today.items.find(t=>t.id===x.template_id)?.name||`Routine #${x.template_id}`})),...(legacy.items||[]).map(x=>({...x,task_name:`Historic · ${x.activity}`,completed_on:x.performed_on,expense:x.expense}))].sort((a,b)=>String(b.completed_on||'').localeCompare(String(a.completed_on||'')));routineToday=today;}else if(area==='breeding'){rows=(ws.linked.breeding||[]).map(decorate).sort((a,b)=>b.id-a.id)}else{rows=((await api.records(rowsFor[area]||'projects')).items||[]).map(decorate)}}
  catch(error){rows=[];toast(error.message,true)}finally{loading=false;draw()}
 };
 const rowView=()=>area==='routine'&&shift!=='all'?rows.filter(x=>x.shift===shift):rows;
 function draw(){
  if(!area){
   root.innerHTML=livestockDirectory('Livestock & Poultry',sections,Object.fromEntries(sections.map(x=>[x.id,{groups:ws.dashboard.herds,animals:ws.dashboard.registered_animals,houses:ws.dashboard.houses,products:ws.dashboard.product_lots,incubations:ws.dashboard.active_incubations}[x.id]])))+overview(ws);
   bindSubmodules(root,selectArea);return;
  }
  const section=sections.find(x=>x.id===area);const data=rowView();
  const topActions=write&&actions[area]?button(actions[area],'liv-add','commit'):'';
  const extras=write&&area==='animals'?button('+ Register animal','liv-reg-animal','commit')+button('+ Register bird','liv-reg-bird','commit')+button('View lineage','liv-lineage',''):
   write&&area==='projects'?button('Assign herd / flock','liv-assign-project',''):
   write&&area==='houses'?button('Assign / move flock','liv-place',''):
   write&&area==='breeding'?button('Update progress','liv-breeding-result','')+button('Record delivery / offspring','liv-birth',''):
   write&&area==='health'?button('Complete planned care','liv-health-complete',''):
   write&&area==='incubations'?button('Record hatch & offspring','liv-hatch',''):
   write&&area==='products'?button('Sell product','liv-open-sales',''):
   '';
  const filters=area==='routine'?`<div class="liv-shifts"><span class="muted">View shift</span>${['all','morning','afternoon','evening','night'].map(x=>`<button type="button" class="btn small ${shift===x?'liv-shift-active':''}" data-liv-shift="${esc(x)}">${esc(x[0].toUpperCase()+x.slice(1))}</button>`).join('')}</div>`:'';
  const housingExtra=area==='houses'&&!loading?`<div class="liv-housing-tables"><h3>Current herd and flock assignments</h3>${table(housingAssignments.map(x=>({...x,group_name:ws.groups.find(g=>g.id===x.group_id)?.name||'Unknown',house_name:ws.houses.find(h=>h.id===x.house_id)?.name||'Unknown'})),[['group_name','Herd or flock'],['house_name','Housing'],['assigned_on','Assigned on']],{click:false})}<h3>Housing transfer history</h3>${table(housingHistory.map(x=>({...x,group_name:ws.groups.find(g=>g.id===x.group_id)?.name||'Unknown',from_house:ws.houses.find(h=>h.id===x.from_house_id)?.name||'New assignment',to_house:ws.houses.find(h=>h.id===x.to_house_id)?.name||'Unknown'})),[['moved_on','Date'],['group_name','Group'],['from_house','From'],['to_house','To']],{click:false})}</div>`:'';
  const routineBoard=area==='routine'&&!loading?routineChecklist(routineToday,shift):'';
  const deliveryAlerts=area==='breeding'&&!loading?`<div class="liv-alert-line"><strong>${ws.linked.alerts.births_overdue} overdue deliveries</strong><span>${ws.linked.alerts.births_due_14_days} expected within 14 days</span><span>Estimates are planning guides; confirm actual delivery and record offspring</span></div>`:'';
  const offspringExtra=area==='breeding'&&!loading?`<div class="liv-housing-tables"><h3>Breeding timeline & follow-up history</h3>${table(ws.linked.breeding_timeline.map(x=>({...x,animal_name:ws.linked.breeding.find(b=>b.id===x.breeding_id)?.target_name||`Cycle #${x.breeding_id}`})),[['breeding_id','Cycle'],['event_on','Date'],['event','Stage'],['notes','Notes']],{click:false})}<h3>Delivered offspring & parentage</h3>${table(ws.linked.offspring.map(o=>({...o,child_group_name:ws.groups.find(g=>g.id===o.child_group_id)?.name||'—',parent_group_name:ws.groups.find(g=>g.id===o.parent_group_id)?.name||'—'})),[['born_on','Born / hatched'],['child_group_name','Offspring cohort'],['parent_group_name','Origin'],['total_born','Total'],['live_count','Live'],['breed','Breed']],{click:false})}</div>`:'';
  const lineageExtra=lineageData?`<div class="liv-housing-tables"><h3>Lineage and care: ${esc(lineageData.group.name)}</h3><p class="muted">${lineageData.offspring?`Born ${esc(lineageData.offspring.born_on)} · ${esc(lineageData.offspring.live_count)} surviving · ${esc(lineageData.offspring.breed||'Breed not recorded')} · ${lineageData.source_breeding?'Linked mating cycle '+esc(lineageData.source_breeding.id):'Parent breeding cycle not linked'}`:'Existing herd/flock without registered parentage'}</p>${table(lineageData.individuals,[['tag','Identity'],['sex','Sex'],['breed','Breed'],['birth_date','Born']],{click:false})}<h3>Weight progression</h3>${table(lineageData.weights,[['measured_on','Date'],['weight_kg','Weight (kg)'],['animal_id','Individual ID']],{click:false})}<h3>Medication / veterinary history</h3>${table(lineageData.health,[['performed_on','Date'],['medication','Medication'],['condition','Condition'],['next_due','Next due']],{click:false})}<h3>Feeding and other historical care</h3>${table(lineageData.care,[['performed_on','Date'],['activity','Activity'],['quantity','Quantity'],['unit','Unit']],{click:false})}<h3>Daily checklist completions</h3>${table(lineageData.routine_completions||[],[['completed_on','Date'],['quantity','Quantity'],['expense','Cost']],{click:false})}</div>`:'';
  const main=loading?'<div class="empty">Loading live records…</div>':area==='overview'?overview(ws):area==='performance'?performanceView(projectResults):`<div class="liv-chart-grid">${chartsFor(area,data)}</div>${routineBoard}${deliveryAlerts}${filters}${table(data,area==='routine'?[['task_name','Reminder'],['completed_on','Completed'],['quantity','Quantity'],['expense','Cost'],['currency','Currency']]:cols[area],{empty:'No records saved. Use the action above to start.'})}${housingExtra}${offspringExtra}${lineageExtra}`;
  root.innerHTML=head(section.title,section.description,topActions)+submoduleWorkspace('Livestock & Poultry',sections,area,`${extras?`<div class="liv-secondary-actions">${extras}</div>`:''}${main}`);
  bindSubmodules(root,selectArea);
  root.querySelector('#liv-add')?.addEventListener('click',add);
  root.querySelector('#liv-assign-project')?.addEventListener('click',assignProject);
  root.querySelector('#liv-reg-animal')?.addEventListener('click',()=>registerIndividual('animals'));
  root.querySelector('#liv-reg-bird')?.addEventListener('click',()=>registerIndividual('birds'));
  root.querySelector('#liv-lineage')?.addEventListener('click',openLineage);
  root.querySelector('#liv-birth')?.addEventListener('click',recordBirth);
  root.querySelectorAll('[data-routine-complete]').forEach(x=>x.onchange=async()=>{
    if(!x.checked)return; x.disabled=true;
    try{await api.completeRoutine(Number(x.dataset.routineComplete),{completed_on:routineToday.today});await refresh()}catch(e){x.checked=false;x.disabled=false;toast(e.message,true)}
  });
  root.querySelectorAll('[data-routine-toggle]').forEach(x=>x.onclick=async()=>{
    x.disabled=true;try{await api.toggleRoutine(Number(x.dataset.routineToggle),x.dataset.active==='true');await refresh()}catch(e){x.disabled=false;toast(e.message,true)}
  });
  root.querySelector('#liv-place')?.addEventListener('click',assignHouse);
  root.querySelector('#liv-breeding-result')?.addEventListener('click',changeBreeding);
  root.querySelector('#liv-health-complete')?.addEventListener('click',completePlanned);
  root.querySelector('#liv-hatch')?.addEventListener('click',finishIncubation);
  root.querySelector('#liv-open-sales')?.addEventListener('click',()=>selectArea('product_sales'));
  root.querySelectorAll('[data-liv-shift]').forEach(x=>x.onclick=()=>{shift=x.dataset.livShift;draw()});
  if(!loading&&area!=='performance'&&area!=='overview')listenRows(root,data,x=>detailModal(x,{title:`${section.title} · record #${x.id}`}));
 }

 function routineChecklist(data,which){if(!data)return '<div class="empty">Loading routine reminders…</div>';
 const tasks=data.items.filter(x=>which==='all'||x.shift===which);
 const due=tasks.filter(t=>t.scheduled_today&&!t.completed_today);
 return `<section class="liv-tasks"><div class="liv-tasks-head"><h3>Daily checklist · ${esc(data.today)}</h3><span>${data.completed} completed · ${data.due} awaiting completion</span></div>
 <p class="muted">Check a task once after completing it. Every new day begins unchecked; past dates remain in history. Reminders appear when the module is open.</p>
 ${tasks.length?tasks.map(t=>`<div class="liv-task ${t.completed_today?'liv-task-done':''}"><label><input type="checkbox" data-routine-complete="${t.id}" ${t.completed_today?'checked disabled':''} ${!t.scheduled_today?'disabled':''}> <span><strong>${esc(t.name)}</strong><small>${esc(t.group_name)} · ${esc(t.shift)} · ${esc(t.activity)} · ${esc(t.reminder_time||'No time set')} · ${esc(t.default_quantity??'—')} ${esc(t.unit||'')}</small>${t.instructions?`<small>${esc(t.instructions)}</small>`:''}</span></label><span class="liv-task-status">${!t.active?'Paused':t.completed_today?'Completed':t.scheduled_today?'Due today':'Not scheduled'}</span><button type="button" class="btn small" data-routine-toggle="${t.id}" data-active="${!t.active}">${t.active?'Pause':'Resume'}</button></div>`).join(''):'<div class="empty">Create your first recurring checklist reminder.</div>'}
 </section>`;
 }
 function registrationContext(groupId){const group=ws.groups.find(x=>String(x.id)===String(groupId));return group?`<div class="liv-context"><strong>Linked group: ${esc(group.name)}</strong><span>${esc(group.species)} · ${esc(group.breed||'Breed not recorded')} · ${esc(group.purpose)} · ${esc(group.project_name)} · ${esc(group.head_count)} head/birds</span><small>Species, project, ranch and breed are inherited and checked on the server.</small></div>`:'';}
 function validHousing(group,type){if(!group)return false;const bird=kindOf(group.species)==='bird';
  if(bird&&!['coop','brooder','layer_house','broiler_house','free_range'].includes(type))return false;
  if(!bird&&!['barn','paddock','shed','stable','free_range'].includes(type))return false;
  if(type==='layer_house')return group.species==='chicken'&&group.purpose==='egg_production';
  if(type==='broiler_house')return group.purpose==='meat';
  if(type==='brooder')return ['rearing','breeding','general'].includes(group.purpose);
  return true;
 }
 function showGroupContext(){const m=document.querySelector('#modal-root');const select=m?.querySelector('[name=group_id]');const panel=m?.querySelector('#liv-group-preview');if(!select)return;
  const update=()=>{const group=ws.groups.find(g=>String(g.id)===String(select.value));if(panel)panel.innerHTML=registrationContext(select.value);
   const houseType=m.querySelector('[name=house_type]');if(houseType&&group){
    [...houseType.options].forEach(o=>{if(!o.value)return;const valid=validHousing(group,o.value);o.hidden=!valid;o.disabled=!valid});
    if(houseType.selectedOptions[0]?.disabled)houseType.value='';
   }
   const destination=m.querySelector('[name=house_id]');if(destination&&group){
    [...destination.options].forEach(o=>{if(!o.value)return;const house=ws.houses.find(h=>String(h.id)===o.value);
      const valid=!!house&&house.active&&house.ranch_id===group.ranch_id&&house.species?.toLowerCase()===group.species?.toLowerCase()&&validHousing(group,house.house_type)&&house.available>=group.head_count;
      o.hidden=!valid;o.disabled=!valid;});if(destination.selectedOptions[0]?.disabled)destination.value='';
   }
  };select.addEventListener('change',update);update();
 }
 function registerIndividual(kind){const bird=kind==='birds',groups=ws.groups.filter(g=>kindOf(g.species)===(bird?'bird':'animal')&&g.head_count>0);
 if(!requireItems(groups,`Register a ${bird?'flock':'herd'} with an existing population first`))return;
 const related=ws.linked.offspring.filter(x=>groups.some(g=>g.id===x.child_group_id));
 const fields=[choose('group_id',bird?'Registered flock':'Registered herd',groups),f('tag',bird?'Bird ID / leg band (optional)':'Animal ID / ear tag (optional)'),options('sex','Sex',['female','male','unknown']),f('birth_date','Birth / hatch date',{type:'date'}),f('origin','Origin / source'),f('characteristics','Characteristics / color / traits',{type:'textarea',wide:true}),num('initial_weight_kg','Entry weight (kg)',0.001,'.001'),...optCharge()];
 if(related.length)fields.splice(2,0,{name:'offspring_cohort_id',label:'Born / hatched cohort (optional)',type:'select',options:related.map(x=>({value:x.id,label:ws.groups.find(g=>g.id===x.child_group_id)?.name||`Cohort #${x.id}`}))});
 form(bird?'Register identified bird':'Register identified animal',fields,async d=>{d.group_id=Number(d.group_id);if(d.offspring_cohort_id)d.offspring_cohort_id=Number(d.offspring_cohort_id);takeCharge(d);await (bird?api.registerBird(d):api.registerAnimal(d));await refresh()},'Register identity','<div id="liv-group-preview"></div><p class="muted">The tag identifies one existing member. Registration does not increase flock/herd population. Project, species and breed come from the selected group.</p>');showGroupContext();}
 function openLineage(){if(!requireItems(ws.groups,'Register a herd or flock first'))return;
 form('View offspring lineage and health history',[choose('group_id','Herd / flock',ws.groups)],async d=>{lineageData=await api.lineage(Number(d.group_id));draw()},'Show history');}
 function recordBirth(){const births=rows.filter(x=>!poultry.has(String(ws.groups.find(g=>g.id===x.group_id)?.species).toLowerCase())&&!['failed','cancelled','delivered'].includes(x.outcome));
 if(!requireItems(births,'No open livestock breeding cycles. Poultry hatches are registered in Incubation.'))return;
 form('Record delivery & register offspring cohort',[choose('record_id','Breeding cycle',births.map(x=>({...x,name:`${x.target_name} · ${x.service_date} · ${x.outcome}`}))),dateField('born_on','Actual delivery date'),f('cohort_name','New offspring cohort name',{required:true}),num('total_born','Total born',0,1,true),num('live_count','Live offspring',0,1,true),num('male_count','Male (optional)',0,1),num('female_count','Female (optional)',0,1),num('initial_weight_kg','Average birth weight (kg)',0.001,'.001'),f('characteristics','Breed / offspring characteristics',{type:'textarea',wide:true}),noteField(),...optCharge()],async d=>{const id=Number(d.record_id);delete d.record_id;takeCharge(d);await api.registerBirth(id,d);await refresh()},'Register birth & new cohort','<p class="muted">A new herd of offspring is created and linked to the breeding record, mother, source herd, breed and project. Its live population is counted once. Further weighing, feeding and medication can be recorded against this cohort.</p>');}

 const refresh=async()=>render(root);
 function assignProject(){if(!requireItems(ws.projects,'Create a project first')||!requireItems(ws.groups,'Create a herd/flock first'))return;
  form('Assign herd or flock to project',[choose('project_id','Project',ws.projects),choose('group_id','Herd or flock',ws.groups)],async d=>{await api.linkGroup(+d.project_id,{group_id:+d.group_id});await refresh()},'Link group');
 }
 function assignHouse(){if(!requireItems(ws.houses,'Add housing first')||!requireItems(ws.groups,'Add a herd or flock first'))return;
  const houses=ws.houses.filter(x=>x.active).map(x=>({...x,name:`${x.name} (${x.available} free places) · ${x.code}`}));
  if(!requireItems(houses,'No active housing available'))return;
  form('Assign / move herd or flock',[choose('group_id','Group',ws.groups),choose('house_id','Destination housing',houses),dateField('moved_on','Transfer date'),noteField()],async d=>{d.group_id=+d.group_id;d.house_id=+d.house_id;await api.addPlacement(d);await refresh()},'Save assignment','<div id="liv-group-preview"></div><p class="muted">Only compatible housing is selectable for the chosen flock/herd: same ranch, correct species/purpose and sufficient capacity.</p>');showGroupContext();
 }
 function changeBreeding(){const pending=rows.filter(x=>!['delivered','failed','cancelled'].includes(x.outcome));if(!requireItems(pending,'No active breeding cycles'))return;
  form('Record breeding follow-up',[choose('record_id','Breeding cycle',pending.map(x=>({...x,name:`${x.target_name} · ${x.service_date} · ${x.outcome}`}))),options('outcome','Progress',['served','confirmed','failed','cancelled']),dateField('event_on','Follow-up date'),noteField()],async d=>{const id=+d.record_id;delete d.record_id;await api.breedingProgress(id,d);await refresh()},'Save progress','<p class="muted">Successful delivery is registered separately with the newborn-cohort form. Every follow-up stays in the breeding timeline.</p>');
 }
 function completePlanned(){const pending=rows.filter(x=>x.status==='planned');if(!requireItems(pending,'No planned health actions to complete'))return;
  form('Complete planned veterinary care',[choose('record_id','Planned action',pending.map(x=>({...x,name:`#${x.id} · ${x.action} · ${x.performed_on}`}))),dateField('performed_on','Completed on'),num('cost','Actual cost',0,'.01'),currencyField(),noteField()],async d=>{const id=+d.record_id;delete d.record_id;await api.completeHealth(id,d);await refresh()},'Complete treatment');
 }
 function finishIncubation(){const pending=rows.filter(x=>!ws.linked.offspring.some(o=>o.incubation_id===x.id));if(!requireItems(pending,'No incubation batches awaiting offspring registration'))return;
 form('Record hatch & linked offspring flock',[choose('record_id','Incubation',pending.map(x=>({...x,name:`${x.batch_code} · ${x.eggs_set} eggs set · ${x.status}`}))),dateField('born_on','Actual hatch date'),f('cohort_name','New chick/duckling cohort name',{required:true}),num('total_born','Eggs successfully hatched',0,1,true),num('live_count','Live chicks / birds',0,1,true),num('male_count','Male (if known)',0,1),num('female_count','Female (if known)',0,1),num('initial_weight_kg','Average hatch weight (kg)',0.001,'.001'),f('characteristics','Characteristics / observations',{type:'textarea',wide:true}),noteField(),...optCharge()],async d=>{const id=+d.record_id;delete d.record_id;takeCharge(d);await api.hatchOffspring(id,d);await refresh()},'Save hatch & new flock','<p class="muted">Saves actual hatch rate, creates a traceable offspring flock, and links it to the original breeding/egg flock and project without counting the birds twice.</p>');
 }
 function add(){
  if(area==='projects'){
   if(!requireItems(ws.ranches,'Register a ranch first'))return;
   form('New livestock or poultry project',[choose('ranch_id','Ranch',ws.ranches),f('name','Project name',{required:true}),options('purpose','Project purpose',['general','breeding','egg_production','dairy','meat','wool','other']),dateField('start_date','Start date'),f('end_date','End date',{type:'date'}),currencyField(),noteField()],async d=>{d.ranch_id=+d.ranch_id;await api.addProject(d);await refresh()});return;
  }
  if(area==='groups'){
   if(!requireItems(ws.projects,'Create a Livestock or Poultry project first'))return;
   form('Register herd / flock in existing project',[choose('project_id','Project',ws.projects),f('name','Herd / flock name',{required:true}),options('species','Species',species),options('purpose','Production purpose',['general','breeding','dairy','egg_production','meat','wool','rearing','other']),f('breed','Breed / strain'),f('production_stage','Stage / life phase'),num('head_count','Population (including any individually tagged members)',0,1,true),f('location','Location'),noteField(),...optCharge()],async d=>{d.project_id=Number(d.project_id);takeCharge(d);await api.registerGroup(d);await refresh()},'Register herd / flock','<p class="muted">The selected project supplies the ranch automatically. The herd/flock becomes the source of truth for all later animal, bird, housing, breeding and care records.</p>');return;
  }
  if(area==='animals'){registerIndividual('animals');return;}
  if(area==='houses'){
   if(!requireItems(ws.groups,'Register a herd or flock first'))return;
   form('Create species-compatible housing',[choose('group_id','Herd / flock to accommodate',ws.groups),f('code','Housing code',{required:true}),f('name','Housing name',{required:true}),options('house_type','Housing type',['barn','paddock','shed','stable','coop','brooder','layer_house','broiler_house','free_range']),num('capacity','Maximum places',1,1,true),f('location','Physical location'),f('assign_now','Assign selected group immediately',{type:'checkbox'}),...optCharge()],async d=>{d.group_id=+d.group_id;d.assign_now=!!d.assign_now;takeCharge(d);await api.registerHouse(d);await refresh()},'Register house','<div id="liv-group-preview"></div><p class="muted">Housing is automatically reserved for the chosen group’s species and purpose. A layers house cannot accommodate goats, broilers or a non-layer flock.</p>');showGroupContext();return;
  }
  if(['routine','breeding','health','weights','production','sales'].includes(area)){
   const targets=pickTargets(ws,{femaleOnly:area==='breeding'});
   if(!requireItems(targets,'Register an active animal or group first'))return;
  }
  const target=()=>targetField(ws,{femaleOnly:area==='breeding'});
  if(area==='routine'){
   if(!requireItems(ws.groups,'Register a herd or flock first'))return;
   form('Create recurring daily routine',[choose('group_id','Herd or flock',ws.groups),f('name','Reminder name, e.g. Morning feed',{required:true}),options('activity','Activity',['feeding','watering','cleaning','bedding','inspection','grazing','milking','egg_collection_check','biosecurity','medication','other']),options('shift','Shift',['morning','afternoon','evening','night']),f('reminder_time','Reminder time (optional)',{type:'time'}),options('frequency','Repeat',['Every day','Monday to Friday','Weekends','Custom days']),f('custom_days','Custom weekday numbers (0=Mon…6=Sun), optional'),dateField('starts_on','Begin on'),num('default_quantity','Expected quantity each completion',0.001,'.001'),f('unit','Unit (kg, litres, doses etc.)'),num('default_expense','Optional cost per completion',0,'.01'),currencyField(),f('instructions','Custom checklist instructions',{type:'textarea',wide:true})],async d=>{d.group_id=Number(d.group_id);d.days_of_week=d.frequency==='Monday to Friday'?'01234':d.frequency==='Weekends'?'56':d.frequency==='Custom days'?(d.custom_days||'0123456'):'0123456';delete d.frequency;delete d.custom_days;await api.createRoutine(d);await refresh()},'Save recurring reminder','<div id="liv-group-preview"></div><p class="muted">Save the instructions once. Staff then only tick a checkbox after work is completed. A fresh checkbox appears on each scheduled day; completed history stays retained.</p>');showGroupContext();return;
  }
  if(area==='breeding'){
   const breedingGroups=ws.groups.filter(x=>x.purpose==='breeding');if(!requireItems(breedingGroups,'Register a group with breeding purpose first'))return;
   const females=ws.animals.filter(a=>a.status==='active'&&a.sex==='female'&&breedingGroups.some(g=>g.id===a.group_id));
   const targets=[...females.map(a=>({value:`a-${a.id}`,label:`Dam/hen ${a.tag} · ${ws.groups.find(g=>g.id===a.group_id)?.name}`})),...breedingGroups.map(g=>({value:`g-${g.id}`,label:`Breeding herd/flock · ${g.name}`}))];
   form('Register breeding, mating or insemination',[{name:'target',label:'Female / breeding group',type:'select',options:targets,required:true},options('method','Method',['natural','ai','synchronization','other']),f('sire_tag','Sire ID / semen / male parent'),dateField('service_date','Service date'),f('expected_date','Expected delivery (mammals only; optional)',{type:'date'}),options('outcome','Stage',['planned','served','confirmed','failed']),noteField(),...optCharge()],async d=>{resolveTarget(d);takeCharge(d);if(d.animal_id){const dam=ws.animals.find(x=>x.id===d.animal_id);d.group_id=dam.group_id;}await api.registerBreeding(d);await refresh()},'Save breeding cycle','<p class="muted">The registered species and purpose determine the rules. Mammal gestation dates are estimated when omitted (editable at entry); birds are followed through their egg incubation and hatch cycles. Pregnancy, follow-ups and offspring remain traceable.</p>');const m=document.querySelector('#modal-root'),target=m?.querySelector('[name=target]'),expected=m?.querySelector('[name=expected_date]');if(target&&expected){const update=()=>{const [type,id]=String(target.value).split('-');const group=type==='g'?ws.groups.find(g=>g.id===+id):ws.groups.find(g=>g.id===ws.animals.find(a=>a.id===+id)?.group_id);const bird=kindOf(group?.species)==='bird';expected.closest('label').hidden=bird;if(bird)expected.value='';};target.addEventListener('change',update);update()}return;
  }
  if(area==='health'){
   form('Veterinary / animal health record',[target(),options('action','Activity',['vaccination','deworming','treatment','checkup','diagnosis','quarantine','other']),options('status','Status',['completed','planned']),f('condition','Condition / diagnosis'),f('medication','Medication'),f('dosage','Dosage'),dateField('performed_on','Action date'),f('next_due','Next due date',{type:'date'}),num('cost','Actual cost (completed only)',0,'.01'),currencyField(),noteField()],async d=>{resolveTarget(d);await api.addHealth(d);await refresh()},'Save health record','<p class="muted">Planned treatments can later be marked completed; expenses post only at completion. Recording medication does not reduce inventory stock.</p>');return;
  }
  if(area==='weights'){
   form('Record live weight',[target(),dateField('measured_on','Measured on'),num('weight_kg','Individual or group average weight (kg)',0.001,'.001',true),num('sample_size','Animals sampled',1,1,true),noteField()],async d=>{resolveTarget(d);d.sample_size=d.sample_size||1;await api.addWeight(d);await refresh()},'Save weighing','<p class="muted">Group weighing uses the sample average. Individual animal weighing uses a sample of one. Gain and ADG compare consecutive records for the same target.</p>');return;
  }
  if(area==='production'){
   form('Record production or population event',[target(),options('action','Event',['egg_collection','milk_collection','wool_collection','meat_collection','chick_collection','byproduct_collection','mortality','vaccination','health_check','inspection','other']),dateField('performed_on'),num('quantity','Quantity',0.001,'.001'),f('unit','Unit (pieces, litres, kg, head)'),num('cost','Related cost',0,'.01'),currencyField(),noteField()],async d=>{resolveTarget(d);d.reference=crypto.randomUUID();await api.addEvent(d);await refresh()},'Record event','<p class="muted">Record deliveries through Breeding and hatching through Incubation so their offspring lineage and population stay synchronized. Mortality adjusts population; milk and eggs create traceable stock.</p>');return;
  }
  if(area==='incubations'){
   const flocks=ws.groups.filter(x=>poultry.has(String(x.species).toLowerCase()));
   if(!requireItems(flocks,'Register a chicken, duck, turkey or other poultry flock first'))return;
   const breeding=ws.linked.breeding.filter(x=>flocks.some(g=>g.id===x.group_id));
   const fields=[choose('group_id','Source flock',flocks),f('batch_code','Batch reference',{required:true}),num('eggs_set','Eggs set',1,1,true),dateField('set_on','Setting date'),f('expected_on','Expected hatch date (optional estimate)',{type:'date'}),noteField(),...optCharge()];
   if(breeding.length)fields.splice(1,0,{name:'breeding_id',label:'Related mating / fertilization cycle (optional)',type:'select',options:breeding.map(x=>({value:x.id,label:`${x.target_name} · ${x.service_date} · ${x.method}`}))});
   form('Register incubation linked to source breeding',fields,async d=>{d.group_id=+d.group_id;if(d.breeding_id)d.breeding_id=+d.breeding_id;takeCharge(d);await api.startIncubation(d);await refresh()},'Start incubation','<div id="liv-group-preview"></div><p class="muted">The source flock supplies species, breed, ranch, and project. The optional breeding-cycle link traces fertilization through hatch and offspring. Expected hatch date is estimated when left blank.</p>');showGroupContext();return;
  }
  if(area==='costs'){
   if(!requireItems(ws.projects,'Create a project first'))return;
   form('Add directly attributable project cost',[choose('project_id','Project',ws.projects),options('category','Category',['animal_procurement','feed','labor','medicine','housing','transport','machinery','utilities','other']),f('description','Description',{required:true}),num('amount','Expense amount',0.01,'.01',true),currencyField(),dateField('performed_on','Date')],async d=>{const id=+d.project_id;delete d.project_id;await api.addCost(id,d);await refresh()});return;
  }
  if(area==='sales'){
   const available=[...ws.animals.filter(x=>x.status==='active').map(x=>({value:`a-${x.id}`,label:`Animal · ${x.tag}`})),...ws.groups.filter(x=>x.head_count>0).map(x=>({value:`g-${x.id}`,label:`Group · ${x.name} (${x.head_count} head)`}))];
   if(!requireItems(available,'No active animals or herds available'))return;
   form('Complete livestock sale',[{name:'target',label:'Animal or group',type:'select',options:available,required:true},f('buyer','Buyer',{required:true}),f('buyer_contact','Buyer contact'),f('reason','Sale reason',{required:true}),num('quantity','Animals sold',1,1,true),options('price_basis','Pricing basis',['per_head','per_kg']),num('price_per_unit','Price per head or kg',0.01,'.01',true),num('weight_kg','Total measured weight (kg), if per kg',0.001,'.001'),currencyField(),dateField('sale_date','Sale date')],async d=>{resolveTarget(d);if(d.animal_id)d.quantity=1;await api.addAnimalSale(d);await refresh()},'Complete sale','<div class="liv-sale-preview" id="liv-sale-preview" aria-live="polite">Enter quantity and selling price to preview expected gross revenue.</div>');
   liveSalePreview();return;
  }
  if(area==='product_sales'){
   const lots=ws.lots.filter(x=>x.available>0).map(x=>({...x,name:`${x.product} · ${nice(x.available)} ${x.unit} available`}));
   if(!requireItems(lots,'Collect products in Production first'))return;
   form('Sell collected livestock product',[choose('lot_id','Available product lot',lots),num('quantity','Quantity sold',0.001,'.001',true),num('price_per_unit','Selling price per unit',0.01,'.01',true),f('buyer','Buyer',{required:true}),currencyField(),dateField('sold_on','Date'),f('reference','Sale reference (optional)')],async d=>{d.lot_id=+d.lot_id;await api.addProductSale(d);await refresh()},'Complete product sale','<div class="liv-sale-preview" id="liv-sale-preview" aria-live="polite">Revenue = units sold × unit price.</div>');
   liveSalePreview(true);return;
  }
 }
 function liveSalePreview(product=false){const modal=document.querySelector('#modal-root');const preview=modal?.querySelector('#liv-sale-preview');const form=modal?.querySelector('form');if(!preview||!form)return;
  const calculate=()=>{const v=name=>form.elements.namedItem(name)?.value||'';const qty=n(v('quantity'));const price=n(v('price_per_unit'));const basis=product?'per_unit':v('price_basis');const kg=n(v('weight_kg'));
   const amount=price*(basis==='per_kg'?kg:qty);
   const warning=!product&&basis==='per_kg'&&kg<=0?' Enter total measured weight for per-kg sales.':'';
   preview.textContent=`Expected gross revenue: ${v('currency')||'TZS'} ${amount.toLocaleString(undefined,{maximumFractionDigits:2})}. ${basis==='per_kg'?'Based on total kg':product?'Based on product units':'Based on number of head'}.${warning}`;
  };form.addEventListener('input',calculate);form.addEventListener('change',calculate);calculate();
 }
 draw();if(area)await load();
}
