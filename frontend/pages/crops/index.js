import {get,esc,number,can,toast} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,listenRows,submoduleDirectory,submoduleWorkspace,bindSubmodules,rememberSubmodule,rememberedSubmodule,parentField,recordsPreview} from '../../shared/ui.js';
import * as api from './service.js?v=9.0.1';

const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
const val=x=>x===null||x===undefined||x===''?'—':x;
const amt=x=>x===null||x===undefined?'Not recorded':number(x);
const idOption=(items,label)=>items.map(x=>({value:x.id,label:label?label(x):x.name||x.title||x.code||`#${x.id}`}));
const choose=(name,label,items,required=true)=>({name,label,type:'select',required,options:idOption(items)});
const fld=(name,label,type='text',other={})=>({name,label,type,...other});
const num=(name,label,required=false,other={})=>fld(name,label,'number',{min:0,step:'.001',required,...other});
const standardCost=currency=>[num('quantity','Quantity (optional)'),fld('unit','Unit (kg, L, hours, etc.)'),num('unit_cost','Unit cost (optional)'),num('other_cost','Other directly attributable cost'),fld('currency','Project currency','fixed',{value:currency,display:currency}),fld('reference','Unique source/reference (optional)'),fld('notes','Notes / observations','textarea',{wide:true})];
const smallOptions=(items)=>idOption(items,x=>x.code?`${x.code} — ${x.name||''}`:x.name||x.title||`#${x.id}`);
const columns={projects:[['code','Code'],['name','Project'],['method','Method'],['season','Season'],['status','Status']],
 fields:[['name','Field'],['area_ha','Area (ha)'],['soil_type','Soil'],['irrigation','Irrigation']],
 catalogue:[['name','Crop'],['variety','Variety'],['category','Category'],['days_to_maturity','Days to maturity']],
 budgets:[['description','Budget item'],['category','Category'],['quantity','Quantity'],['amount','Planned amount'],['currency','Currency'],['status','Approval']],
 routine:[['title','Routine'],['frequency','Frequency'],['shift','Shift'],['start_date','Start']],
 trials:[['title','Trial'],['design','Design'],['replications','Replicates'],['status','Status']],
 harvest:[['batch_ref','Harvest lot'],['grade','Grade'],['marketable_kg','Marketable kg'],['available_kg','Available kg'],['harvested_on','Date']],
 sales:[['buyer','Buyer'],['quantity_kg','Sold kg'],['gross','Gross revenue'],['currency','Currency'],['sold_on','Date']],
 general:[['title','Record'],['performed_on','Date'],['quantity','Quantity'],['unit','Unit'],['other_cost','Other cost'],['currency','Currency']]};
const colors=['#169b72','#ea8d2a','#328fe2','#9461d2','#ed5c67','#15b8c0','#b9a143'];
const barGraph=(entries,label)=>{
 const positives=entries.filter(x=>Number(x.value)>=0&&Number.isFinite(Number(x.value))).slice(0,9);
 if(!positives.length)return '<p class="muted">No verified measurements for this chart yet.</p>';
 const mx=Math.max(1,...positives.map(x=>+x.value));
 return `<div class="cv9-bars" role="img" aria-label="${esc(label)}">${positives.map((x,i)=>`<div class="cv9-bar-row"><div class="cv9-bar-label" title="${esc(x.name)}">${esc(x.name)}</div><div class="cv9-bar-track"><div class="cv9-bar-fill" style="width:${Math.min(100,(Number(x.value)/mx)*100).toFixed(1)}%;background:${colors[i%colors.length]}"></div></div><strong>${esc(Number(x.value).toLocaleString(undefined,{maximumFractionDigits:2}))}</strong></div>`).join('')}</div>`;
};

export async function render(root){
 let state,meta,ranches,due;
 try{[state,meta,ranches,due]=await Promise.all([api.workspace(),api.metadata(),get('v5/ranches'),api.dueRoutines(today())]);}
 catch(e){root.innerHTML=head('Crop Farming','Unable to load crop records')+`<div class="panel"><p class="error-text">${esc(e.message)}</p></div>`;return;}
 const writable=can('crops.write');const sections=meta.sections;
 let tab=rememberedSubmodule('crops');if(!sections.some(x=>x.id===tab))tab=null;
 let projectId=Number(sessionStorage.getItem('ghr_crop_project_'+String(meta.organization_id))||0);
 if(projectId&&!state.projects.some(p=>p.id===projectId))projectId=0;
 const project=()=>state.projects.find(x=>x.id===projectId)||null;
 const scopeRows=(rows)=>projectId?rows.filter(r=>r.project_id===projectId):rows;
 const projectUnits=()=>state.units.filter(u=>!projectId||state.fields.some(f=>f.id===u.field_id&&f.ranch_id===project()?.ranch_id));
 const projectCycles=()=>state.cycles.filter(c=>!projectId||c.project_id===projectId);
 const cropLabel=c=>{const v=state.varieties.find(x=>x.id===c.variety_id);return `${v?.name||'Crop'} / ${v?.variety||'Variety'} · Cycle ${c.id}`};
 const cycleChoices=()=>projectCycles().map(x=>({value:x.id,label:cropLabel(x)}));
 const projectChoices=()=>state.projects.map(x=>({value:x.id,label:x.code+' · '+x.name}));
 const recordSet=section=>scopeRows(state.records.filter(r=>r.section===section));
 const selectProject=()=>{
  if(projectId)return project();
  if(state.projects.length===1){projectId=state.projects[0].id;return project()}
  return null;
 };
 const requireProject=()=>{let p=selectProject();if(!p){alert('Select a project from the project selector above before recording this activity.');return null}return p};
 const launch=(title,fields,save,saveLabel='Save record')=>modalForm({title,fields,onSave:async d=>{await save(d);await refresh()},saveLabel});
 async function refresh(){[state,due]=await Promise.all([api.workspace(),api.dueRoutines(today())]);draw()}
 function top(){return `<div class="cv9-toolbar"><div class="cv9-project-picker"><label for="cv9-project-select">Active project</label><select id="cv9-project-select"><option value="0">All projects</option>${projectChoices().map(x=>`<option value="${x.value}" ${x.value===projectId?'selected':''}>${esc(x.label)}</option>`).join('')}</select></div><span class="cv9-count">${esc(state.projects.length)} projects · ${esc(state.cycles.length)} crop cycles</span></div>`}
 function metrics(){
  const cycles=scopeRows(state.cycles),harvest=scopeRows(state.harvest),sales=scopeRows(state.sales),records=scopeRows(state.records);
  return kpis([{label:'Active projects',value:state.projects.filter(x=>(!projectId||x.id===projectId)&&(x.status==='active'||x.status==='planned')).length},
   {label:'Planted area (ha)',value:number(cycles.reduce((v,x)=>v+Number(x.planted_area_ha||0),0).toFixed(2))},
   {label:'Marketable harvest (kg)',value:number(harvest.reduce((v,x)=>v+Number(x.marketable_kg||0),0).toFixed(2))},
   {label:'Recorded activities',value:records.length},
   {label:'Produce sales',value:sales.length}]);
 }
 function analytics(){const lines=state.analytics.filter(x=>!projectId||x.project_id===projectId);
  if(!lines.length)return '<div class="panel muted">Register projects and record operations to see real results.</div>';
  const currencyRows=lines.flatMap(p=>p.currencies.map(x=>({...x,project:p.project})));
  return `<div class="cv9-chart-grid">${[
   ['Harvested by project (kg)',lines.map(x=>({name:x.project,value:x.harvested_marketable_kg}))],
   ['Sold by project (kg)',lines.map(x=>({name:x.project,value:x.sold_kg}))],
   ['Recorded costs by project & currency',currencyRows.map(x=>({name:x.project+' · '+x.currency,value:x.recorded_cost}))],
   ['Sales by project & currency',currencyRows.map(x=>({name:x.project+' · '+x.currency,value:x.sales_revenue}))]
  ].map(([title,items])=>`<section class="panel"><h3>${esc(title)}</h3>${barGraph(items,title)}</section>`).join('')}</div>
  ${currencyRows.length?table(currencyRows,[['project','Project'],['currency','Currency'],['approved_budget','Approved budget'],['recorded_cost','Recorded cost'],['sales_revenue','Sales'],['recorded_contribution','Contribution']]):''}
  <p class="muted cv9-note">Recorded contribution is not audited net profit. Unallocated overhead, stock valuation, and unrecorded costs are excluded. Different currencies are shown separately.</p>`;
 }
 function routineCards(){const rows=due.items.filter(r=>!projectId||r.project_id===projectId);
  return `<div class="cv9-routine-grid">${rows.length?rows.map(x=>`<div class="panel cv9-routine"><label><input type="checkbox" data-check="${x.id}" ${x.check?.status==='completed'?'checked disabled':''} ${!writable?'disabled':''}><span><strong>${esc(x.title)}</strong><small>${esc(x.shift)} · ${esc(x.frequency)} · ${esc(x.instructions||'Follow routine instructions')}</small></span></label>${x.check?`<p class="muted">${esc(x.check.status)} · ${esc(x.check.day)}</p>`:''}</div>`).join(''):'<p class="muted">No routines are due today. Create a reusable routine to begin.</p>'}</div>`;
 }
 function chartFor(section){const rows=recordSet(section);
  if(!rows.length)return '';
  const days={};for(const r of rows)days[r.performed_on]=(days[r.performed_on]||0)+1;
  return `<div class="panel cv9-chart"><h3>Recorded activities by date</h3>${barGraph(Object.entries(days).sort().slice(-8).map(([name,value])=>({name,value})),'Activities by date')}</div>`;
 }
 function details(){
  if(!tab)return '';
  if(tab==='overview')return analytics();
  if(tab==='outcomes')return `${analytics()}<h3>Recorded conclusions and improvement decisions</h3>${table(recordSet('outcomes'),columns.general)}${chartFor('outcomes')}`;
  if(tab==='fields')return `<div class="cv9-note">Register a permanent field once, then divide it into reusable blocks, beds or greenhouse production units.</div><h3>Registered fields</h3>${table(state.fields,columns.fields)}<h3>Field blocks / production units</h3>${table(state.units,[['name','Block/unit'],['kind','Type'],['field_id','Field ID'],['area_ha','Size (ha)'],['status','Status']])}${barGraph(state.fields.map(f=>({name:f.name,value:f.area_ha})),'Registered field area in hectares')}`;
  if(tab==='catalogue')return `${table(state.varieties,columns.catalogue)}${barGraph(Object.entries(state.varieties.reduce((a,v)=>(a[v.category]=(a[v.category]||0)+1,a),{})).map(([name,value])=>({name,value})),'Registered crop varieties by category')}`;
  if(tab==='projects')return `${table(state.projects.filter(x=>!projectId||x.id===projectId),columns.projects)}<div class="cv9-panel-space">${analytics()}</div>`;
  if(tab==='budgets')return `${table(scopeRows(state.budgets),columns.budgets)}${barGraph(scopeRows(state.budgets).filter(b=>b.status==='approved').map(b=>({name:b.description+' · '+b.currency,value:b.amount})),'Approved budget allocation')}<div class="cv9-panel-space">${analytics()}</div>`;
  if(tab==='routine')return `<h3>Today's due tasks · ${esc(today())}</h3>${routineCards()}<h3>Recurring templates</h3>${table(scopeRows(state.routine),columns.routine)}${barGraph([{name:'Templates',value:scopeRows(state.routine).length},{name:'Due today',value:due.items.filter(r=>!projectId||r.project_id===projectId).length},{name:'Completed today',value:due.items.filter(r=>(!projectId||r.project_id===projectId)&&r.check?.status==='completed').length}],'Daily checklist status')}<h3>Completion history</h3>${table(state.completions.filter(c=>state.routine.some(r=>r.id===c.routine_id&&(!projectId||r.project_id===projectId))),[['routine_id','Routine ID'],['day','Date'],['status','Status'],['actual_quantity','Actual quantity'],['amount','Cost']])}`;
  if(tab==='trials')return `${table(scopeRows(state.trials),columns.trials)}<h3>Experimental plots</h3>${table(state.plots.filter(x=>state.trials.some(t=>t.id===x.trial_id&&(!projectId||t.project_id===projectId))),[['code','Plot'],['trial_id','Trial ID'],['treatment','Treatment'],['replicate','Replicate'],['area_ha','Area (ha)']])}${barGraph(scopeRows(state.trials).map(t=>({name:t.title,value:state.plots.filter(x=>x.trial_id===t.id).length})),'Experimental plots by trial')}<h3>Trait measurements</h3>${table(recordSet('trial_observations'),[['title','Measurement'],['performed_on','Date'],['data','Trait / value',r=>`${r.data?.trait||''}: ${r.data?.value||''} ${r.data?.measurement_unit||''}`]])}`;
  if(tab==='harvest')return `${table(scopeRows(state.harvest),columns.harvest)}${barGraph(scopeRows(state.harvest).map(x=>({name:x.batch_ref,value:x.marketable_kg})),'Marketable harvest per lot')}`;
  if(tab==='postharvest')return `${table(recordSet(tab),columns.general)}<h3>Lot adjustments / losses</h3>${table(state.stock.filter(s=>state.harvest.some(h=>h.id===s.lot_id&&(!projectId||h.project_id===projectId))),[['lot_id','Harvest lot'],['action','Movement'],['quantity_kg','Quantity kg'],['reference','Reference']])}`;
  if(tab==='sales')return `${table(scopeRows(state.sales),columns.sales)}${analytics()}`;
  if(tab==='costs')return `${analytics()}<h3>Additional attributable expenses</h3>${table(recordSet('costs'),columns.general)}`;
  if(tab==='planting')return `<h3>Registered crop cycles</h3>${table(scopeRows(state.cycles).map(c=>({...c,crop:cropLabel(c)})),[['crop','Crop / Cycle'],['planted_area_ha','Area (ha)'],['planted_on','Planted'],['expected_harvest','Expected harvest'],['status','Status']])}<h3>Planting / nursery records</h3>${table(recordSet(tab),columns.general)}${chartFor(tab)}`;
  if(meta.sections.find(x=>x.id===tab)?.fields.length)return `${table(recordSet(tab),columns.general)}${chartFor(tab)}`;
  return '';
 }
 function actionBtns(){if(!writable||!tab||tab==='overview')return '';
  const actions={fields:[['Register field','field'],['Add block / unit','unit']],catalogue:[['Register crop / variety','variety']],projects:[['Create project','project'],['Update project status','project_status']],budgets:[['Add budget item','budget']],planting:[['Start crop cycle','cycle'],['Update cycle status','cycle_status'],['Record planting','record']],routine:[['Create routine','routine']],trials:[['Create trial','trial'],['Add trial plot','plot'],['Record measurement','trial_measure'],['Update trial status','trial_status']],harvest:[['Record harvest','harvest']],postharvest:[['Record postharvest work','record'],['Record stock loss / use','stock']],sales:[['Record produce sale','sale']],costs:[['Record additional cost','record']]};
  return (actions[tab]||[['+ Add record','record']]).map(([label,op])=>`<button class="btn commit" type="button" data-create="${op}">${esc(label)}</button>`).join(' ');
 }
 function draw(){
  const counts={};for(const s of sections){counts[s.id]=s.id==='overview'?state.projects.length:s.id==='projects'?state.projects.length:s.id==='fields'?state.fields.length+state.units.length:s.id==='catalogue'?state.varieties.length:s.id==='budgets'?scopeRows(state.budgets).length:s.id==='routine'?scopeRows(state.routine).length:s.id==='trials'?scopeRows(state.trials).length:s.id==='harvest'?scopeRows(state.harvest).length:s.id==='sales'?scopeRows(state.sales).length:s.id==='postharvest'?recordSet(s.id).length:s.id==='outcomes'?scopeRows(state.analytics).length:s.id==='planting'?scopeRows(state.cycles).length+recordSet('planting').length:recordSet(s.id).length;}
  if(!tab)root.innerHTML=top()+submoduleDirectory('Crop Farming',sections,counts)+metrics()+`<div class="cv9-chart-grid">${recordsPreview('Recent projects',state.projects.slice(0,5),columns.projects)}${recordsPreview('Recent harvests',state.harvest.slice(0,5),columns.harvest)}</div>`;
  else root.innerHTML=top()+submoduleWorkspace('Crop Farming',sections,tab,head(sections.find(s=>s.id===tab).title,sections.find(s=>s.id===tab).description,actionBtns())+`<div class="cv9-workspace">${details()}</div>`);
  root.querySelector('#cv9-project-select')?.addEventListener('change',e=>{projectId=Number(e.target.value);sessionStorage.setItem('ghr_crop_project_'+String(meta.organization_id),String(projectId));draw()});
  bindSubmodules(root,id=>{tab=id;rememberSubmodule('crops',id);draw()});
  root.querySelectorAll('[data-create]').forEach(el=>el.addEventListener('click',()=>create(el.dataset.create)));
  root.querySelectorAll('[data-check]').forEach(el=>el.addEventListener('change',async()=>{
    try{await api.finishRoutine(Number(el.dataset.check),{day:today(),status:'completed'});toast('Routine completed');await refresh()}catch(e){toast(e.message,true);el.checked=false;el.disabled=false}
  }));
  // Record detail panels never execute instructions embedded in database fields.
  root.querySelectorAll('.cv9-workspace tr[data-index]').forEach(tr=>tr.addEventListener('click',()=>{}));
 }
 const dateFld=(name,label,required=false)=>fld(name,label,'date',{required,value:today()});
 const projectField=p=>fld('project_id','Project','fixed',{value:p.id,display:p.name});
 const cycleField=(required=false)=>({name:'cycle_id',label:'Crop cycle',type:'select',required,options:cycleChoices()});
 const unitField=(required=false)=>({name:'unit_id',label:'Field block / growing unit',type:'select',required,options:idOption(projectUnits())});
 function recordFields(section,p){const config=meta.sections.find(s=>s.id===section);
  const fields=[projectField(p),cycleField(['planting','growth','nutrition','protection','irrigation'].includes(section)),unitField(),dateFld('performed_on','Date',true),fld('title','Activity / record title','text',{required:true})];
  for(const f of config.fields){const type={integer:'number',number:'number',choice:'select',boolean:'checkbox',date:'date',text:'text'}[f.kind]||'text';
    fields.push({name:'field_'+f.key,label:f.label,type,required:f.required,options:f.options,step:f.kind==='integer'?1:'.001'});}
  return [...fields,...standardCost(p.currency)];
 }
 function encodeRecord(section,d,p){const data={};for(const field of meta.sections.find(x=>x.id===section).fields){const key='field_'+field.key;if(d[key]!==undefined&&d[key]!=='')data[field.key]=d[key];delete d[key]}
  d.project_id=p.id;d.cycle_id=d.cycle_id?+d.cycle_id:null;d.unit_id=d.unit_id?+d.unit_id:null;d.data=data;
  for(const key of ['quantity','unit_cost','other_cost'])if(d[key]==='')delete d[key];
  if(!d.quantity)delete d.quantity;if(!d.unit_cost)delete d.unit_cost;if(!d.other_cost)delete d.other_cost;
  return d;
 }
 function create(op){const p=!['project','project_status','field','unit','variety'].includes(op)?requireProject():null;
  if(!['project','project_status','field','unit','variety'].includes(op)&&!p)return;
  if(op==='project'){if(!ranches.items?.length){alert('Register a ranch in Ranches first.');return}
   launch('Create crop project',[choose('ranch_id','Registered ranch',ranches.items),fld('code','Unique project code','text',{required:true}),fld('name','Project name','text',{required:true}),fld('category','Project category','select',{options:['commercial','research','seed_production','demonstration','mixed']}),fld('objective','Objectives','textarea',{wide:true}),fld('method','Farming method','select',{options:['open_field','rainfed','irrigated','greenhouse','hydroponic','aeroponic','orchard','vineyard','intercropping','conservation','organic','precision','other']}),fld('season','Season / year'),dateFld('start_date','Start date',true),dateFld('end_date','End date'),fld('currency','ISO currency code (e.g. USD)','text',{value:'USD',required:true}),num('planned_budget','Planned budget'),num('target_yield_kg','Target yield (kg)'),num('expected_price','Forecast selling price / kg'),fld('notes','Notes','textarea',{wide:true})],d=>api.addProject({...d,ranch_id:+d.ranch_id}));return}
  if(op==='project_status'){
   launch('Update project status',[choose('record_id','Project',state.projects),fld('status','New project status','select',{required:true,options:['planned','active','paused','completed','cancelled']})],d=>api.updateProjectStatus(+d.record_id,d.status));return}
  if(op==='cycle_status'){
   launch('Update crop cycle status',[choose('record_id','Crop cycle',projectCycles().map(c=>({...c,name:cropLabel(c)}))),fld('status','New cycle status','select',{required:true,options:['planned','growing','harvested','completed','failed','cancelled']})],d=>api.updateCycleStatus(+d.record_id,d.status));return}
  if(op==='trial_status'){
   launch('Update trial status',[choose('record_id','Trial',scopeRows(state.trials)),fld('status','New trial status','select',{required:true,options:['planned','active','completed','cancelled']})],d=>api.updateTrialStatus(+d.record_id,d.status));return}
  if(op==='field'){launch('Register permanent field',[choose('ranch_id','Farm / ranch',ranches.items||[]),fld('name','Field name','text',{required:true}),num('area_ha','Area (hectares)',true,{min:.0001}),fld('soil_type','Soil type'),fld('irrigation','Irrigation capability'),fld('location','Location / coordinates')],d=>api.addField({...d,ranch_id:+d.ranch_id}));return}
  if(op==='unit'){if(!state.fields.length){alert('Register a field first.');return}
   launch('Add field block or production unit',[choose('field_id','Parent field',state.fields),fld('name','Block/bed/house name','text',{required:true}),fld('kind','Unit type','select',{options:['block','plot','bed','greenhouse','nursery','orchard','vineyard','hydroponic','other']}),num('area_ha','Area (ha)',true,{min:.0001}),num('capacity','Growing positions / plants (optional)'),num('latitude','Latitude',false,{min:-90,max:90}),num('longitude','Longitude',false,{min:-180,max:180}),fld('irrigation_system','Irrigation system'),fld('notes','Notes','textarea',{wide:true})],d=>api.addUnit({...d,field_id:+d.field_id}));return}
  if(op==='variety'){launch('Register crop and variety',[fld('name','Crop common name','text',{required:true}),fld('scientific_name','Scientific name'),fld('family','Plant family'),fld('variety','Variety / cultivar','text',{required:true}),fld('category','Crop category','select',{options:['cereal','legume','vegetable','fruit','root_tuber','oilseed','fiber','forage','flower','herb','other']}),fld('life_cycle','Life cycle','select',{options:['annual','biennial','perennial']}),num('days_to_maturity','Typical days to maturity'),fld('growing_method','Growing method'),fld('source','Variety breeder / source'),fld('seed_certification','Seed certification reference'),fld('notes','Notes','textarea',{wide:true})],d=>api.addVariety(d));return}
  if(op==='cycle'){if(!projectUnits().length||!state.varieties.length){alert('Create a block and register crop varieties first.');return}
   launch('Start connected crop cycle',[projectField(p),choose('unit_id','Field block',projectUnits()),{name:'variety_id',label:'Registered crop / variety',type:'select',required:true,options:state.varieties.map(v=>({value:v.id,label:v.name+' · '+v.variety}))},num('planted_area_ha','Planted area (ha)',true,{min:.0001}),dateFld('planted_on','Planting date',true),dateFld('expected_harvest','Expected harvest date'),fld('method','Planting method','select',{options:['direct_seed','transplant','cutting','graft','tissue_culture','other']}),num('target_yield_kg','Target harvest (kg)'),fld('notes','Notes','textarea',{wide:true})],d=>api.addCycle({...d,project_id:p.id,unit_id:+d.unit_id,variety_id:+d.variety_id}));return}
  if(op==='budget'){launch('Add planned budget line',[projectField(p),cycleField(),fld('category','Cost category','select',{required:true,options:['land','seed','fertilizer','crop_protection','labor','irrigation','machinery','infrastructure','harvest','postharvest','transport','other']}),fld('description','Budget item','text',{required:true}),num('quantity','Planned quantity',true,{min:.0001}),fld('unit','Unit','text',{required:true}),num('unit_cost','Unit cost',true),fld('currency','Project currency','fixed',{value:p.currency,display:p.currency}),num('version','Budget version',true,{value:1,min:1,step:1}),fld('status','Approval status','select',{options:['draft','submitted','approved']}),dateFld('planned_on','Planned date')],d=>api.addBudget({...d,project_id:p.id,cycle_id:d.cycle_id?+d.cycle_id:null}));return}
  if(op==='routine'){launch('Create recurring field checklist',[projectField(p),cycleField(),unitField(),fld('title','Routine name','text',{required:true}),fld('instructions','Instructions','textarea',{wide:true}),fld('frequency','Frequency','select',{options:['daily','weekdays','weekly','monthly','once','every_2','every_3','every_7','every_14']}),fld('shift','Shift','select',{options:['morning','afternoon','evening','night','custom']}),dateFld('start_date','Start',true),dateFld('end_date','Stop (optional)'),num('estimated_minutes','Estimated duration (minutes)'),num('planned_quantity','Expected quantity'),fld('unit','Unit')],d=>api.addRoutine({...d,project_id:p.id,cycle_id:d.cycle_id?+d.cycle_id:null,unit_id:d.unit_id?+d.unit_id:null}));return}
  if(op==='trial'){if(!projectCycles().length){alert('Start a crop cycle first.');return}
   launch('Create agronomic experiment',[projectField(p),{name:'cycle_id',label:'Crop cycle',type:'select',options:cycleChoices(),required:true},fld('title','Trial title','text',{required:true}),fld('question','Research question','textarea',{required:true,wide:true}),fld('hypothesis','Hypothesis','textarea',{wide:true}),fld('design','Experimental design','select',{options:['rcbd','crd','split_plot','factorial','demonstration','other']}),num('replications','Number of replications',true,{min:1,step:1,value:4}),dateFld('start_date','Start date',true),dateFld('end_date','End date'),fld('notes','Protocol / notes','textarea',{wide:true})],d=>api.addTrial({...d,project_id:p.id,cycle_id:+d.cycle_id}));return}
  if(op==='plot'){const trials=scopeRows(state.trials);if(!trials.length){alert('Create a trial first.');return}
   launch('Register trial plot',[choose('trial_id','Trial',trials),choose('unit_id','Trial field block',projectUnits()),fld('code','Plot code','text',{required:true}),fld('treatment','Treatment / control','text',{required:true}),num('replicate','Replication number',true,{step:1,min:1}),num('area_ha','Plot area (ha)',true,{min:.0001}),num('randomization_order','Randomized order',false,{step:1}),fld('is_control','Is this a control plot?','checkbox')],d=>api.addPlot({...d,trial_id:+d.trial_id,unit_id:+d.unit_id}));return}
  if(op==='trial_measure'){const trials=scopeRows(state.trials);const plots=state.plots.filter(x=>trials.some(t=>t.id===x.trial_id));if(!plots.length){alert('Register an experiment and its plots first.');return}
   launch('Record scientific plot observation',[projectField(p),choose('trial_id','Experiment',trials),choose('plot_id','Experimental plot',plots.map(x=>({...x,name:x.code+' · '+x.treatment}))),dateFld('performed_on','Measurement date',true),fld('title','Measurement title','text',{required:true}),fld('trait','Measured trait','text',{required:true}),num('value','Measured numeric value',true),fld('measurement_unit','Unit','text',{required:true}),fld('method','Measurement method','text',{required:true}),fld('notes','Observation notes','textarea',{wide:true})],async d=>{const trial=trials.find(t=>t.id===+d.trial_id);await api.addRecord('trial_observations',{project_id:p.id,cycle_id:trial.cycle_id,performed_on:d.performed_on,title:d.title,notes:d.notes||null,data:{trial_id:+d.trial_id,plot_id:+d.plot_id,trait:d.trait,value:d.value,measurement_unit:d.measurement_unit,method:d.method}})});return}
  if(op==='harvest'){if(!projectCycles().length){alert('Start a crop cycle first.');return}
   launch('Record traceable crop harvest',[projectField(p),choose('cycle_id','Crop cycle',projectCycles().map(x=>({...x,name:cropLabel(x)}))),choose('unit_id','Harvest origin block',projectUnits()),fld('batch_ref','Unique harvest batch reference','text',{required:true}),dateFld('harvested_on','Harvest date',true),num('pass_number','Harvest pass number',true,{value:1,step:1,min:1}),num('gross_kg','Gross weighed quantity (kg)',true,{min:.001}),num('tare_kg','Tare (kg)',false,{value:0}),num('rejected_kg','Rejected/unsellable (kg)',false,{value:0}),fld('grade','Quality grade','text',{value:'ungraded'}),num('cost','Optional harvest expense'),fld('currency','Project currency','fixed',{value:p.currency,display:p.currency})],d=>api.addHarvest({...d,project_id:p.id,cycle_id:+d.cycle_id,unit_id:+d.unit_id}));return}
  if(op==='sale'){const lots=scopeRows(state.harvest).filter(x=>Number(x.available_kg)>0);if(!lots.length){alert('Register a harvest with available marketable stock first.');return}
   launch('Sell traceable harvested produce',[choose('lot_id','Available harvest lot',lots.map(x=>({...x,name:x.batch_ref+' · '+x.available_kg+' kg available'}))),fld('buyer','Buyer','text',{required:true}),num('quantity_kg','Sale quantity (kg)',true,{min:.001}),num('price_per_kg','Sale price per kg',true,{min:.0001}),fld('currency','Project currency','fixed',{value:p.currency,display:p.currency}),dateFld('sold_on','Sale date',true),fld('delivery_ref','Delivery/invoice reference'),num('selling_cost','Selling expenses (optional)'),fld('notes','Notes','textarea',{wide:true})],d=>api.addSale({...d,lot_id:+d.lot_id}));return}
  if(op==='stock'){const lots=scopeRows(state.harvest).filter(x=>Number(x.available_kg)>0);if(!lots.length){alert('No available harvest lots.');return}
   launch('Adjust physical harvest lot',[choose('lot_id','Harvest lot',lots.map(x=>({...x,name:x.batch_ref+' · '+x.available_kg+' kg'}))),fld('action','Stock movement','select',{options:['loss','writeoff','internal_use'],required:true}),num('quantity_kg','Quantity (kg)',true,{min:.001}),fld('reference','Unique movement reference','text',{required:true}),fld('notes','Reason / destination','textarea',{wide:true})],d=>api.addStock({...d,lot_id:+d.lot_id}));return}
  if(op==='record')launch(`Record ${meta.sections.find(x=>x.id===tab).title}`,recordFields(tab,p),d=>api.addRecord(tab,encodeRecord(tab,d,p)));
 }
 draw();
}
