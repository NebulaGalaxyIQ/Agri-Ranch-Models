import {can,esc,safe,number} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,listenRows,choice,parentField,mixComposer,submoduleDirectory,recordsPreview,submoduleWorkspace,bindSubmodules,rememberedSubmodule,rememberSubmodule} from '../../shared/ui.js';
import {collect,createRanch,createProject,createBatch,createAnimal,animalProfile,fatGet,fatPost,createMixByQuantity,fatInsights,mixDetails,projectDashboard,saveProjectPlan,approveProjectPlan,reviseProjectPlan,saveProjectSection,previewAnimalSale} from './service.js?v=7.8.0';
const today=()=>new Date().toISOString().slice(0,10);
let selectedWeighAnimalId=null; // One animal per weighing view and per measurement.
// V7.6: distinguish metrics with professional blue, green and orange series.
const CHART_BLUE={line:'#5297CA',point:'#3476A8',bars:['#5297CA','#56A677','#E8A04C','#83B9E2','#7DBF9B','#EEC089']};
const CHART_COLORS=['#5297CA','#56A677','#E8A04C','#83B9E2','#7DBF9B','#EEC089'];
const fmt=(v,dec=1)=>v===null||v===undefined||v===''?'—':Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:dec}):String(v);
// Keep the shared modal logic untouched. Only Fattening dialogs receive the wider layout.
const fatModal = options => {
  modalForm(options);
  document.querySelector('#modal-root .modal')?.classList.add('fat78-fattening-modal');
};
const fatteningScrollTo = (root, destination='detail') => {
  const target = root.querySelector(destination==='header'?'.fat77-project-header':destination==='sections'?'.fat77-project-navigation':'.fat77-workspace-view');
  if (!target) return;
  const perform = () => {
    if (!target.isConnected) return;
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    target.scrollIntoView({behavior:reduceMotion?'auto':'smooth',block:'start',inline:'nearest'});
    // Screen-reader focus without resetting the scroll just performed.
    if (destination==='detail') {target.tabIndex=-1;target.focus({preventScroll:true});}
  };
  if (typeof requestAnimationFrame==='function') requestAnimationFrame(()=>requestAnimationFrame(perform));
  else perform();
};
const human=(v)=>!v?'—':String(v).replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const metric=(name,value,note='')=>`<div class="fat71-kpi"><div class="fat72-kpi-heading"><span>${esc(name)}</span></div><strong>${esc(String(value??'—'))}</strong>${note?`<small>${esc(note)}</small>`:''}</div>`;
const overviewIcons={
 ranches:'<path d="M4 21V6l8-3 8 3v15M2 21h20M9 21v-5h6v5M8 9h.01M16 9h.01M8 12h.01M16 12h.01"/>',
 projects:'<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M8 3h8v4H8zM8 12h8M8 16h6"/>',
 animals:'<circle cx="12" cy="12" r="7"/><path d="M8 10h.01M16 10h.01M9 15q3 2 6 0M5 5 3 3M19 5l2-2"/>',
 batches:'<path d="m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5"/>'
};
function overviewCards(items){
 return `<section class="fat72-overview-cards" aria-label="Animal Fattening key figures">${items.map(item=>`<article class="fat72-overview-card"><div class="fat72-overview-head"><span>${esc(item.label)}</span><span class="fat72-overview-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${overviewIcons[item.key]}</svg></span></div><strong>${esc(String(item.value))}</strong><small>${esc(item.note)}</small></article>`).join('')}</section>`;
}
function cleanTable(rows,cols,{empty='No records to display yet.'}={}){
 if(!rows?.length)return `<div class="fat71-empty">${esc(empty)}</div>`;
 return `<div class="fat71-table-scroll"><table class="fat71-table"><thead><tr>${cols.map(c=>`<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${rows.map((r,i)=>`<tr data-fat-index="${i}" tabindex="0" role="button" aria-label="Open record ${i+1}">${cols.map(c=>`<td>${esc(r[c.key]===null||r[c.key]===undefined||r[c.key]===''?'—':typeof r[c.key]==='number'?fmt(r[c.key],3):Array.isArray(r[c.key])?r[c.key].map(v=>typeof v==='object'?v?.name||v?.label||v?.tag||'View record':v).join(', '):typeof r[c.key]==='object'?'View details':String(r[c.key]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
const shorten=s=>String(s??'').length>18?String(s).slice(0,17)+'…':String(s??'');
function graph(panel){
 const list=(panel.points||[]).filter(p=>Number.isFinite(+p.value));
 const title=`${esc(panel.title)}${panel.unit?` <span class="fat71-unit">${esc(panel.unit)}</span>`:''}`;
 if(!list.length)return `<section class="fat71-chart"><h3>${title}</h3><div class="fat71-empty">No recorded data yet. Charts will appear automatically as records are entered.</div></section>`;
 const pts=list.slice(-20);const max=Math.max(1,...pts.map(p=>+p.value)),min=Math.min(0,...pts.map(p=>+p.value));
 if(panel.kind==='pie'){
  const nonzero=list.filter(p=>+p.value>0).slice(0,9);const total=nonzero.reduce((a,x)=>a+(+x.value),0);
  if(!total)return `<section class="fat71-chart"><h3>${title}</h3><div class="fat71-empty">There are no positive values to chart.</div></section>`;
  let running=0;
  const circles=nonzero.map((x,i)=>{const portion=100*(+x.value)/total;
    const ring=`<circle cx="95" cy="95" r="62" fill="none" stroke="${CHART_COLORS[i%CHART_COLORS.length]}" stroke-width="30" stroke-dasharray="${portion.toFixed(5)} ${(100-portion).toFixed(5)}" stroke-dashoffset="${(-running).toFixed(5)}" pathLength="100"><title>${esc(x.label)}: ${fmt(x.value,2)} ${esc(panel.unit||'')} (${portion.toFixed(1)}%)</title></circle>`;
    running+=portion;return ring;}).join('');
  return `<section class="fat71-chart"><h3>${title}</h3><div class="fat76-pie-layout"><svg viewBox="0 0 190 190" role="img" aria-label="${esc(panel.title)} composition pie chart"><g transform="rotate(-90 95 95)">${circles}</g><circle cx="95" cy="95" r="44" fill="white"/><text x="95" y="99" text-anchor="middle" fill="#34485b" font-size="14" font-weight="600">${esc(fmt(total,0))}</text></svg><div class="fat76-legend">${nonzero.map((x,i)=>`<div><i style="background:${CHART_COLORS[i%CHART_COLORS.length]}"></i><span title="${esc(x.label)}">${esc(x.label)}</span><b>${esc((100*(+x.value)/total).toFixed(1))}%</b></div>`).join('')}</div></div>${panel.note?`<p class="fat71-chart-note">${esc(panel.note)}</p>`:''}</section>`;
 }
 if(panel.kind==='line'){
  // Subtle light-blue series with neutral chart grid and accessible hover values.
  const range=max-min||1,left=38,right=620,top=20,bottom=176,width=right-left;
  const xy=pts.map((p,i)=>({x:left+(pts.length===1?width/2:width*i/(pts.length-1)),y:bottom-(+p.value-min)/range*(bottom-top),p}));
  const path=xy.map((q,i)=>`${i?'L':'M'}${q.x.toFixed(2)},${q.y.toFixed(2)}`).join(' ');
  const axis=[0,1,2,3].map(i=>{const y=bottom-(bottom-top)*i/3;return `<line x1="38" y1="${y}" x2="620" y2="${y}" stroke="#e6edf2"/><text x="29" y="${y+4}" text-anchor="end" font-size="10" fill="#65798f">${esc(fmt(min+range*i/3,0))}</text>`}).join('');
  const ticks=xy.filter((_,i)=>i===0||i===xy.length-1||i%Math.max(1,Math.ceil(xy.length/5))===0).map(q=>`<text x="${q.x}" y="194" text-anchor="middle" fill="#65798f" font-size="10">${esc(shorten(q.p.label))}</text>`).join('');
  return `<section class="fat71-chart"><h3>${title}</h3><svg viewBox="0 0 650 212" role="img" aria-label="${esc(panel.title)}. ${pts.length} recorded points">${axis}<path fill="none" stroke="${panel.color||CHART_BLUE.line}" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round" d="${path}"/>${xy.map(q=>`<circle cx="${q.x}" cy="${q.y}" r="4.5" fill="${panel.color||CHART_BLUE.point}" stroke="white" stroke-width="1.5"><title>${esc(q.p.label)}: ${esc(fmt(q.p.value,2))} ${esc(panel.unit||'')}</title></circle>`).join('')}${ticks}</svg>${panel.note?`<p class="fat71-chart-note">${esc(panel.note)}</p>`:''}</section>`;
 }
 return `<section class="fat71-chart"><h3>${title}</h3><div class="fat71-bars">${pts.map((p,i)=>`<div class="fat71-bar-row"><span title="${esc(p.label)}">${esc(shorten(p.label))}</span><div class="fat71-bar-track"><div class="fat71-bar-fill" style="width:${Math.max(0,100*(+p.value)/max).toFixed(2)}%;background:${CHART_BLUE.bars[i%CHART_BLUE.bars.length]}"></div></div><b>${esc(fmt(p.value,2))}</b></div>`).join('')}</div>${panel.note?`<p class="fat71-chart-note">${esc(panel.note)}</p>`:''}</section>`;
}
function insightPanels(payload){
 if(!payload)return '<p class="fat71-muted">Analytics are available to authorized management employees.</p>';
 return `<section class="fat71-analytics" aria-label="Recorded performance and charts"><div class="fat71-kpis">${(payload.kpis||[]).map(x=>metric(x.label,x.value,x.note)).join('')}</div><div class="fat71-charts">${(payload.charts||[]).map(graph).join('')}</div>${(payload.insights||[]).length?`<div class="fat71-insights"><h3>Management insights</h3>${payload.insights.map(i=>`<p>${esc(i)}</p>`).join('')}</div>`:''}</section>`;
}
function niceRecord(row,columns,title='Record details'){
 const body=`<div class="fat71-detail-table">${cleanTable([row],columns)}</div>`;
 fatModal({title,readOnly:true,intro:body,fields:[],saveLabel:'Close'});
}
export async function render(root){
 const [r,p,b,a]=await collect();const ranches=r.items||[],projects=p.items||[],batches=b.items||[],animals=a.items||[];
 const [pens,rations,sales,plans,assignments]=await Promise.all(['pens','rations','sales/accounting','feed/plans','feed/assignments'].map(u=>safe(()=>fatGet(u))));
 const mixes=rations.items||[];let tab=rememberedSubmodule('fattening');
 // Weighing is always an individual animal activity; preserve the selection when reloading.
 const selectedAnimal=animals.find(x=>Number(x.id)===Number(selectedWeighAnimalId))||animals.find(x=>x.status==='active')||animals[0]||null;
 selectedWeighAnimalId=selectedAnimal?.id==null?null:Number(selectedAnimal.id);
 const perf=tab==='animals'?await safe(()=>fatGet('animals/performance?limit=200'),{items:[]}):{items:[]};
 const analytics=(tab&&can('analytics.read'))?await safe(()=>fatInsights(tab,'',tab==='weighing'?selectedWeighAnimalId:null),null):null;
 const writable=can('ranch.manage')||can('animals.manage');
 const configs={
  ranches:{title:'Ranches',label:'+ Add ranch',cols:[['name','Ranch'],['location','Location']],items:ranches},
  projects:{title:'Projects',label:'+ New project',cols:[['name','Project'],['code','Code'],['status','Status']],items:projects},
  batches:{title:'Batches',label:'+ New batch',cols:[['name','Batch'],['project_id','Project'],['capacity','Maximum animals'],['animal_count','Current animals']],items:batches},
  pens:{title:'Pens',label:'+ Add pen',cols:[['name','Pen'],['batch_name','Batch']],items:pens.items||[]},
  animals:{title:'Animals',label:'+ Add animal',cols:[['tag','Animal ID'],['batch','Batch'],['entry_date','Entry date'],['age_months_at_entry','Age (months)'],['days_spent','Days spent'],['entry_weight_kg','Entry weight kg'],['current_weight_kg','Current weight kg'],['individual_feed_kg','Individual feed kg'],['purchase_price','Purchase price'],['direct_fattening_costs','Direct fattening costs'],['allocated_batch_costs','Allocated batch costs'],['fattening_costs','All attributed fattening costs'],['break_even_point','Break-even point'],['break_even_per_kg','Break-even/kg'],['currency','Currency'],['status','Status']],items:perf.items?.length?perf.items:animals},
  weighing:{title:'Weighing',label:'+ Record animal weight',cols:[['tag','Animal'],['current_weight_kg','Latest weight (kg)']],items:animals.filter(x=>Number(x.id)===Number(selectedWeighAnimalId))},
  feeding:{title:'Feeding',label:'+ Record feeding',cols:[['name','Batch'],['animal_count','Animals']],items:batches},
  mixes:{title:'Feed mixes',label:'+ Create mix',cols:[['name','Feed mix'],['feed_type','Feeding stage']],items:mixes},
  sales:{title:'Animal sales',label:'+ Sell animal',cols:[['animal_tag','Animal'],['buyer_name','Buyer'],['current_weight_kg','Last weight kg'],['weight_kg','Sale weight kg'],['purchase_cost','Animal purchase'],['direct_costs','Direct costs'],['allocated_batch_costs','Allocated batch costs'],['total_break_even','Break-even incl. selling'],['gross_amount','Revenue'],['profit_loss','Profit / loss'],['currency','Currency'],['status','Status']],items:sales.items||[]}
 };
 const label={mixes:'Feed mixes',sales:'Animal sales'};
 const sections=Object.entries(configs).map(([id,c],i)=>({id,title:label[id]||c.title,
  icon:['▦','◇','▤','▥','♧','⚖','◉','◈','▣'][i],
  description:{ranches:'Manage ranch locations',projects:'Manage fattening projects',batches:'Manage batch capacity and animals',pens:'Manage batch pens',animals:'Register and inspect animals',weighing:'Record live weights in kg',feeding:'Record scheduled feeding',mixes:'Create and assign finished feed mixes',sales:'Record animal sales and revenue'}[id]}));
 if(tab&&!sections.some(x=>x.id===tab)){tab=null;}
 function draw(){
  const counts={ranches:ranches.length,projects:projects.length,batches:batches.length,pens:(pens.items||[]).length,
   animals:animals.length,weighing:animals.filter(x=>x.status==='active').length,feeding:batches.length,
   mixes:mixes.length,sales:(sales.items||[]).length};
  if(!tab){
   root.innerHTML=submoduleDirectory('Animal Fattening',sections,counts)+
     overviewCards([
       {key:'ranches',label:'Registered ranches',value:ranches.length,note:'Organization ranch locations'},
       {key:'projects',label:'Fattening projects',value:projects.length,note:'Registered fattening projects'},
       {key:'animals',label:'Active animals',value:animals.filter(x=>x.status==='active').length,note:'Currently in fattening'},
       {key:'batches',label:'Batches',value:batches.length,note:'Registered animal groups'},
     ])+
      `<p class="fat74-release-note" data-fattening-version="7.8.0">Animal Fattening · UI 7.8.0</p>`+
      `<div class="module-previews">${recordsPreview('Recent animal records',animals.slice(-5).reverse(),[['tag','Animal'],['breed','Breed'],['current_weight_kg','Weight (kg)'],['status','Status']])}${recordsPreview('Animal sales',(sales.items||[]).slice(-5).reverse(),[['animal_tag','Animal'],['buyer_name','Buyer'],['gross_amount','Revenue'],['currency','Currency']])}</div>`;
   bindSubmodules(root,id=>{tab=id;rememberSubmodule('fattening',id);render(root)});return;
  }
  const cfg=configs[tab];
  const actions=writable?button(cfg.label,'new','commit')+(tab==='mixes'?button('Assign mix to batch or animal','assign','commit'):''):'';
  const reportRows=tab==='animals'&&perf.items?.length?perf.items:tab==='weighing'&&analytics?analytics.rows:(analytics?.rows?.length||0)?analytics.rows:null;
  const reportCols=tab==='animals'?cfg.cols.map(c=>({key:c[0],label:c[1]})):analytics?.columns?.length?analytics.columns:cfg.cols.map(c=>({key:c[0],label:c[1]}));
  const displayRows=reportRows||cfg.items;
  const data=cleanTable(displayRows,reportCols,{empty:`No ${cfg.title.toLowerCase()} records recorded yet.`});
  const displayAnalytics=analytics?{...analytics,charts:(analytics.charts||[]).map(c=>({
      ...c,kind:/ingredient composition|expense categories|cost composition|sale distribution|buyer distribution|project distribution|occupancy by batch|cleaning completion|by shift/i.test(c.title)?'pie':c.kind,
      color:/growth|weight|revenue/i.test(c.title)?CHART_COLORS[0]:/feed|completion|population/i.test(c.title)?CHART_COLORS[1]:CHART_COLORS[2]
    }))}:null;
  const visual=(writable||can('analytics.read'))?insightPanels(displayAnalytics):'';
  const weighingSelector=tab==='weighing'?`<section class="fat73-weighing-selector" aria-label="Select animal for individual weight history">
      <div><label for="fat73-weigh-animal">Animal being weighed</label><select id="fat73-weigh-animal" ${animals.length?'':'disabled'}>${animals.length?animals.map(a=>`<option value="${Number(a.id)}" ${Number(a.id)===Number(selectedWeighAnimalId)?'selected':''}>${esc(a.tag)}${a.status!=='active'?' · '+esc(human(a.status)):''}</option>`).join(''):'<option>No animals registered</option>'}</select></div>
      <p>Each weight belongs to one animal. The chart and records below show only the selected animal.</p>
    </section>`:'';
  root.innerHTML=head(cfg.title,sections.find(x=>x.id===tab)?.description||'',actions)+
    submoduleWorkspace('Animal Fattening',sections,tab,weighingSelector+visual+`<section class="fat71-records"><div class="fat71-record-title"><h2>${esc(cfg.title)} records</h2><span>${esc(displayRows.length)} shown</span></div>${data}</section>`);
  bindSubmodules(root,id=>{tab=id;rememberSubmodule('fattening',id);render(root)});
  root.querySelectorAll('tr[data-fat-index]').forEach(tr=>{
   const open=()=>rowAction(displayRows[Number(tr.dataset.fatIndex)]);
   tr.addEventListener('click',open);
   tr.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();open();}});
  });
  root.querySelector('#fat73-weigh-animal')?.addEventListener('change',e=>{
    selectedWeighAnimalId=Number(e.target.value)||null;
    render(root);
  });
  root.querySelector('#new')?.addEventListener('click',()=>{
    if(tab==='weighing'){
      const animal=animals.find(a=>Number(a.id)===Number(selectedWeighAnimalId));
      if(!animal){alert('Register an animal before recording a weight.');return;}
      if(animal.status!=='active'){alert('Only active animals can be weighed.');return;}
      add('weighing',{animal_id:animal.id,display:animal.tag});
    }else add();
  });
  root.querySelector('#assign')?.addEventListener('click',()=>assignMix());
 }
 function fieldsFor(t,context){const field=(name,items,label,needed=true)=>context&&context[name]?{name,label,type:'fixed',value:context[name],display:context.display||items.find(x=>x.id===context[name])?.name||String(context[name])}:{...parentField(name,label,items,{required:needed})};
  switch(t){
   case 'ranches':return [{name:'name',label:'Ranch name',required:true},{name:'location',label:'Location'}];
   case 'projects':return [field('ranch_id',ranches,'Ranch'),{name:'name',label:'Project name',required:true},{name:'objective',label:'Objective',type:'textarea'},{name:'livestock_type',label:'Animal type',type:'select',options:['cattle','sheep','goat','other']},{name:'target_animals',label:'Target animals',type:'number',min:1},{name:'target_weight_kg',label:'Target finishing weight (kg)',type:'number',min:'.001',step:'.001'},{name:'currency',label:'Project currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'},{name:'start_date',label:'Start date',type:'date',required:true,value:today()},{name:'end_date',label:'End date',type:'date'}];
   case 'batches':return [field('project_id',projects,'Project'),{name:'name',label:'Batch name',required:true},{name:'capacity',label:'Maximum animal capacity',type:'number',min:1,value:100,required:true},{name:'start_date',label:'Start date',type:'date',value:today(),required:true},{name:'end_date',label:'End date',type:'date'}];
   case 'pens':return [field('batch_id',batches,'Batch'),{name:'name',label:'Pen name',required:true}];
   case 'animals':return [field('batch_id',batches,'Batch'),{name:'tag',label:'Animal tag (leave empty to auto-generate)'},{name:'species',label:'Species',type:'select',required:true,options:['cattle','goat','sheep','pig','other']},{name:'sex',label:'Sex',type:'select',options:['male','female','unknown']},{name:'breed',label:'Breed'},{name:'color',label:'Color'},{name:'age_months',label:'Age (months)',type:'number',min:0},{name:'origin',label:'Origin'},{name:'supplier_name',label:'Supplier'},{name:'supplier_contact',label:'Supplier contact'},{name:'entry_weight_kg',label:'Initial weight (kg)',type:'number',min:'.001',step:'.001'},{name:'purchase_cost',label:'Purchase cost',type:'number',min:0,value:0},{name:'purchase_currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'}];
   case 'weighing':return [field('animal_id',animals.filter(x=>x.status==='active').map(x=>({...x,name:x.tag})), 'Animal'),{name:'weight_kg',label:'Measured weight (kg)',type:'number',min:'.001',step:'.001',required:true},{name:'notes',label:'Observation',type:'textarea',wide:true}];
   case 'sales':return [field('animal_id',animals.filter(x=>x.status==='active').map(x=>({...x,name:x.tag})),'Animal'),{name:'buyer_name',label:'Buyer',required:true},{name:'buyer_contact',label:'Buyer contact'},{name:'reason',label:'Reason for sale',required:true},{name:'price_basis',label:'Price basis',type:'select',required:true,options:['per_head','per_kg']},{name:'price_per_unit',label:'Price per unit',type:'number',min:'.01',step:'.01',required:true},{name:'weight_kg',label:'Final sale weight (kg)',type:'number',min:'.001',step:'.001'},{name:'transport_cost',label:'Selling transport cost',type:'number',min:0,value:0},{name:'commission_cost',label:'Sales commission',type:'number',min:0,value:0},{name:'other_cost',label:'Other selling expenses',type:'number',min:0,value:0},{name:'sale_date',label:'Date',type:'date',value:today(),required:true},{name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'},{name:'invoice_ref',label:'Invoice reference'},{name:'notes',label:'Notes',type:'textarea',wide:true}];
  }
 }
 async function add(t=tab,context={}){
  if(t==='sales'){await openSaleForm(context);return;}
  if(t==='cost'){await openAnimalCostForm(context);return;}
  if(t==='mixes'){const res=await safe(()=>fatGet('feed/catalog'));const ingredients=(res.items||[]).filter(x=>!x.is_mix);
   if(!ingredients.length){alert('Create or receive feed items first in Stock In.');return}
   mixComposer({feeds:ingredients,onSave:async d=>{await createMixByQuantity(d);await render(root)}});document.querySelector('#modal-root .modal')?.classList.add('fat78-fattening-modal');return}
  if(t==='feeding'){
    if(!context.batch_id&&!context.animal_id&&batches.length>1){
     fatModal({title:'Choose a batch to feed',fields:[parentField('batch_id','Batch',batches)],
      saveLabel:'Continue',onSave:async d=>{
       const picked=batches.find(b=>b.id===Number(d.batch_id));
       window.setTimeout(()=>openFeeding({batch_id:Number(d.batch_id),display:picked?.name}),0);
      }});return;
    }
    await openFeeding(context);return;
   }
  const prerequisite={projects:ranches,batches:projects,pens:batches,animals:batches,weighing:animals.filter(x=>x.status==='active'),sales:animals.filter(x=>x.status==='active')};
  if(prerequisite[t]&&!prerequisite[t].length){alert('Create the relevant parent record first.');return}
  const fields=fieldsFor(t,context);if(!fields)return;
  fatModal({title:configs[t].label.replace(/^\+ /,''),fields,saveLabel:t==='weighing'?'Save weight':t==='sales'?'Complete sale':'Save',onSave:async d=>{
   for(const key of ['ranch_id','project_id','batch_id','animal_id'])if(d[key])d[key]=+d[key];
   if(t==='ranches')await createRanch(d);
   else if(t==='projects')await createProject(d);
   else if(t==='batches')await createBatch(d);
   else if(t==='pens')await fatPost('pens',d);
   else if(t==='animals')await createAnimal(d);
   else if(t==='weighing'){const id=d.animal_id;await fatPost(`animals/${id}/weight`,{weight_kg:d.weight_kg,notes:d.notes})}
   else if(t==='sales'){const id=d.animal_id;delete d.animal_id;await fatPost(`animals/${id}/sale`,d)}
   await render(root)}});
 }
 async function openFeeding(context={}){
  const result=await safe(()=>fatGet('routine/options'),{batches:[],animals:[],feeds:[],mixes:[]});
  const batchesLive=result.batches||batches;
  if(!batchesLive.length){alert('Register a batch first.');return}
  const selectedBatchId=context.batch_id||(context.animal_id?animals.find(a=>a.id===Number(context.animal_id))?.batch_id:null)||(batchesLive.length===1?batchesLive[0].id:null);
  if(!context.animal_id&&!selectedBatchId){alert('Choose a batch before feeding.');return}
  const targetParams=new URLSearchParams(context.animal_id?{animal_id:String(context.animal_id)}:{batch_id:String(selectedBatchId)});
  targetParams.set('shift','Morning');
  let recommended;
  try{recommended=await fatGet(`feed/recommendation?${targetParams}`)}catch(e){alert(e.message);return}
  const catalog=[...(result.feeds||[]).map(x=>({...x,item_id:x.id})),...(result.mixes||[])];
  const assigned=Boolean(recommended.restrict_to_assigned_mix || recommended.ration_id);
  const options=assigned?catalog.filter(x=>Number(x.item_id)===Number(recommended.assigned_item_id)):catalog;
  const stocked=options.filter(x=>x.item_id&&Number(x.available_kg)>0);
  if(!stocked.length){
   alert(assigned?`The assigned mix ${recommended.ration_name||''} is unavailable or out of stock. Receive or manufacture this mix before recording feeding.`:'No usable feed stock available. Receive feed stock first.');return;
  }
  const chosen=stocked[0];
  const target=context.animal_id?
   {name:'animal_id',label:'Animal',type:'fixed',value:context.animal_id,display:context.display||animals.find(a=>a.id===Number(context.animal_id))?.tag}:
   {name:'batch_id',label:'Batch',type:'fixed',value:selectedBatchId,display:context.display||batchesLive.find(b=>b.id===Number(selectedBatchId))?.name};
  const feedField=assigned?
    {name:'item_id',label:'Assigned mix',type:'fixed',value:chosen.item_id,display:`${chosen.name} · ${chosen.available_kg} kg available`}:
    {name:'item_id',label:'Stocked feed or mix',type:'select',required:true,options:stocked.map(x=>({value:x.item_id,label:`${x.name} · ${x.available_kg} kg available`}))};
  fatModal({title:'Record feeding',intro:assigned?'<p class="notice">Only the mix assigned to this batch can be recorded. All its animals follow this assignment.</p>':'',
   fields:[target,{name:'shift',label:'Feeding shift',type:'select',required:true,options:['Morning','Afternoon','Evening']},feedField,
    {name:'quantity_kg',label:'Actual quantity fed (kg)',type:'number',min:'.001',step:'.001',required:true},
    {name:'notes',label:'Observation',type:'textarea',wide:true}],saveLabel:'Complete feeding',onSave:async d=>{
     await fatPost('feeding/record',{batch_id:d.batch_id?+d.batch_id:undefined,animal_id:d.animal_id?+d.animal_id:undefined,
      shift:d.shift,extras:[{item_id:+d.item_id,quantity_kg:+d.quantity_kg}],notes:d.notes,client_reference:crypto.randomUUID()});
     await render(root);
   }});
 }
 async function assignMix(){
  if(!mixes.length){alert('Create a feed mix first.');return}
  if(!batches.length&&!animals.length){alert('Create a batch or animal first.');return}
  const targets=[...batches.map(x=>({value:`b-${x.id}`,label:`Batch: ${x.name}`})),
   ...animals.filter(x=>x.status==='active').map(x=>({value:`a-${x.id}`,label:`Animal: ${x.tag}`}))];
  fatModal({title:'Assign feed mix',saveLabel:'Assign mix',fields:[
   {name:'ration_id',label:'Finished feed mix',type:'select',required:true,options:choice(mixes)},
   {name:'target',label:'Assign to',type:'select',required:true,options:targets},
   {name:'start_date',label:'Start date',type:'date',required:true,value:today()},
   {name:'end_date',label:'End date (optional)',type:'date'}],onSave:async d=>{
    const [kind,id]=d.target.split('-');delete d.target;d.ration_id=+d.ration_id;
    d[kind==='a'?'animal_id':'batch_id']=+id;
    await fatPost('feed/assignments',d);await render(root);
   }});
 }

 async function showSaleAccounting(sale){
   const content=`<div class="fat71-mix-view"><div class="fat71-kpis">${metric('Animal',sale.animal_tag||'—')}${metric('Latest weight',sale.current_weight_kg==null?'—':fmt(sale.current_weight_kg)+' kg')}${metric('Sale revenue',sale.currency+' '+fmt(sale.gross_amount))}${metric('Profit / loss',sale.profit_loss==null?'Historical cost unavailable':sale.currency+' '+fmt(sale.profit_loss))}</div>
     ${cleanTable([sale],[{key:'buyer_name',label:'Buyer'},{key:'price_basis',label:'Pricing basis'},{key:'price_per_unit',label:'Selling price/unit'},{key:'weight_kg',label:'Sale weight kg'},{key:'sale_date',label:'Date'},{key:'status',label:'Status'}])}
     <h3>Cost breakdown as recorded at sale</h3>${cleanTable([sale],[{key:'currency',label:'Currency'},{key:'purchase_cost',label:'Purchase price'},{key:'direct_costs',label:'Direct costs'},{key:'allocated_batch_costs',label:'Allocated batch costs'},{key:'animal_break_even',label:'Animal break-even'},{key:'selling_expenses',label:'Selling expenses'},{key:'total_break_even',label:'Total break-even'},{key:'profit_loss',label:'Profit / loss'}])}
     ${sale.cost_snapshot_available?graph({title:'Sale cost composition',kind:'pie',unit:sale.currency,points:[{label:'Purchase',value:sale.purchase_cost},{label:'Direct',value:sale.direct_costs},{label:'Allocated batch',value:sale.allocated_batch_costs},{label:'Selling',value:sale.selling_expenses}]}):'<p class="fat71-chart-note">Historical cost snapshots are unavailable for sales recorded before this update.</p>'}</div>`;
   fatModal({title:`Sale ${sale.invoice_ref||'#'+sale.id} — Accounting Review`,intro:content,fields:[],readOnly:true,saveLabel:'Close'});
 }
 const PROJECT_AREAS=[
  {id:'overview',name:'Overview & Performance',desc:'Live activity, financial position and charts',icon:'chart'},
  {id:'production',name:'Production Plan',desc:'Animal procurement, weights and targets',icon:'beef'},
  {id:'budget',name:'Budget & Costs',desc:'Per-animal funding and approved cost baseline',icon:'wallet'},
  {id:'resources',name:'Feeding & Resources',desc:'Rations, staffing, water, pens and equipment',icon:'leaf'},
  {id:'commercial',name:'Commercial Forecast',desc:'Market, sales assumptions and break-even',icon:'trending'},
  {id:'milestones',name:'Execution & Milestones',desc:'Project schedule, owners and progress',icon:'calendar'},
  {id:'cashflow',name:'Cash Flow',desc:'Planned monthly outflows and receipts',icon:'cash'},
  {id:'risks',name:'Risks & Controls',desc:'Mitigation measures and accountability',icon:'shield'},
  {id:'scenarios',name:'Scenario Forecasts',desc:'Alternative prices, feed costs and fattening days',icon:'trending'},
  {id:'approval',name:'Approval & Versions',desc:'Review, lock and revise budget plans',icon:'check'},
 ];
 const PROJECT_ICON_PATHS={chart:'<path d="M4 19V5M4 19h16M7 15l4-5 3 2 5-6"/>',beef:'<circle cx="12" cy="12" r="7"/><path d="M8 9h.01M16 9h.01M8 16q4 3 8 0"/>',wallet:'<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M16 15h2"/>',leaf:'<path d="M21 3C9 3 4 8 4 16a5 5 0 0 0 5 5c8 0 13-5 12-18ZM4 20 17 7"/>',trending:'<path d="M3 17 9 11l4 3 8-9M15 5h6v6"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',cash:'<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 12h.01M17 12h.01M10 12h4"/>',shield:'<path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3Z"/><path d="m9 12 2 2 4-4"/>',check:'<path d="M4 12 9 17 20 6"/><circle cx="12" cy="12" r="10"/>'};
 const projectIcon=name=>`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${PROJECT_ICON_PATHS[name]||PROJECT_ICON_PATHS.chart}</svg>`;
 const projectCells=(rows,cols,empty='No records entered yet.')=>{
   if(!rows?.length)return `<p class="fat77-empty">${esc(empty)}</p>`;
   return `<div class="fat71-table-scroll"><table class="fat71-table fat77-table"><thead><tr>${cols.map(c=>`<th>${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${esc(r[c[0]]===undefined||r[c[0]]===null||r[c[0]]===''?'—':typeof r[c[0]]==='number'?fmt(r[c[0]],2):r[c[0]])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
 };
 async function showProjectDashboard(projectId,focus='overview',scrollDestination=null){
   let info;try{info=await projectDashboard(projectId)}catch(e){alert(e.message);return}
   const project=info.project,plan=info.plan?.data||{},k=info.kpis||{},cur=project.currency||'TZS';
   const currentArea=PROJECT_AREAS.find(x=>x.id===focus)||PROJECT_AREAS[0];
   const editable=can('projects.manage')&&info.plan?.status!=='approved';
   const money=v=>v==null?'—':`${cur} ${fmt(v,2)}`;
   const lines=info.budget_lines||[],animalsRows=info.animal_rows||[],batchRows=info.batch_rows||[];
   const planBudget=(plan.budget_lines||[]);
   const financialRows=(info.currency_breakdown||[]).map(x=>({...x,total:x.recorded_costs_including_purchases,position:x.revenue_less_all_recorded_costs}));
   const table=(rows,columns,empty)=>projectCells(rows,columns,empty);
   const budgetCols=[['category','Category'],['amount_per_head','Cost/head'],['project_amount','Full project']];
   const projectHeader=`<header class="fat77-project-header"><div class="fat77-project-heading"><span class="fat77-eyebrow">ANIMAL FATTENING / PROJECT MANAGEMENT</span><h2>${esc(project.name)}</h2><p>${esc(project.code||'Project')} · ${esc(cur)} · ${esc(project.status||'active')} · ${info.plan?`Plan v${info.plan.version} — ${human(info.plan.status)}`:'No plan prepared'}</p></div><button class="btn" id="fat77-back-projects" type="button">← All projects</button></header>`;
   const tiles=`<section class="fat77-project-navigation" aria-label="Project planning sections"><div class="fat78-directory-head"><div><strong>Project workspaces</strong><p>Select an area to review details, record information or update a plan.</p></div><span>${PROJECT_AREAS.length} sections</span></div><div class="fat77-section-grid" aria-label="Project planning subsections">${PROJECT_AREAS.map((a,i)=>`<button class="fat77-section-card fat78-tone-${i%3} ${a.id===focus?'is-active':''}" type="button" data-project-area="${a.id}" aria-current="${a.id===focus?'page':'false'}" aria-label="Open ${esc(a.name)}"><span class="fat77-section-icon">${projectIcon(a.icon)}</span><span class="fat77-section-info"><span class="fat78-section-count">SECTION ${String(i+1).padStart(2,'0')}</span><strong>${esc(a.name)}</strong><small>${esc(a.desc)}</small></span><span class="fat78-section-right">${a.id!=='overview'&&a.id!=='approval'?`<span class="fat77-section-status ${info.section_completed?.[a.id]?'complete':''}">${info.section_completed?.[a.id]?'Ready':'To plan'}</span>`:''}<span class="fat78-card-arrow" aria-hidden="true">↗</span></span></button>`).join('')}</div></section>`;
   const approvalNote=info.plan?.status==='approved'?`<div class="fat77-locked">The current plan is approved and locked. Start a budget revision in Approval & Versions before making changes.</div>`:'';
   const action=(key,title='Edit this section')=>editable?`<button type="button" class="btn commit" data-project-edit="${key}">${esc(title)}</button>`:'';
   const subheading=(title,description,button='')=>`<div class="fat77-detail-head"><div><h3>${esc(title)}</h3><p>${esc(description)}</p></div>${button}</div>`;
   const wrap=(title,description,html,button='')=>`<section class="fat77-section-detail">${subheading(title,description,button)}${html}</section>`;
   const plannedHead=Number(k.budget_per_animal||0), planned=Number(k.planned_animals||0);
   const costChart=(info.actual_cost_categories||[]).filter(x=>x.currency===cur).map(x=>({label:x.category,value:x.amount}));
   const market=plan.target_market||'Not entered';
   let contents='';
   if(focus==='overview'){
     contents=`<div class="fat71-kpis">${metric('Planned animals',fmt(k.planned_animals,0))}${metric('Enrolled animals',fmt(k.enrolled_animals,0))}${metric('Active animals',fmt(k.active_animals,0))}${metric('Batches',fmt(k.batches,0))}${metric('Budget / animal',money(k.budget_per_animal))}${metric('Total project funding',money(k.funding_including_contingency))}${metric('Recorded costs',money(k.recorded_costs_base_currency))}${metric('Forecast contribution',money(k.forecast_contribution))}</div>
     <div class="fat77-dashboard-banner"><div><strong>Project control center</strong><p>All enrolled animals, posted costs, feeding activities and completed sales are reconciled automatically from their batches and Finance records.</p></div><span>${Object.values(info.section_completed||{}).filter(Boolean).length} / 8 sections prepared</span></div>
     <div class="fat71-charts">${graph({title:'Planned budget composition',kind:'pie',unit:cur,points:lines.map(x=>({label:x.category,value:x.project_amount}))})}${graph({title:'Actual operating cost distribution',kind:'pie',unit:cur,points:costChart,note:'Feed, labor, veterinary and other posted costs; excludes animal purchase.'})}${graph({title:'Animals enrolled by batch',kind:'bar',unit:'animals',points:batchRows.map(x=>({label:x.name,value:x.animals}))})}${graph({title:'Live animal weights',kind:'bar',unit:'kg',points:animalsRows.filter(x=>x.current_weight_kg!=null).map(x=>({label:x.tag,value:x.current_weight_kg})),note:'Measured animal weights, not artificially aggregated readings.'})}</div>
     ${wrap('Budget and recorded costs','Planned budgets come from the approved or draft plan; actual transactions update automatically.',table(lines,budgetCols,'Enter a project budget to display planned expenditure.'))}
     ${wrap('Actual financial position by currency','Project purchases, posting costs and confirmed sales are never double-counted.',table(financialRows,[['currency','Currency'],['animal_purchases','Animal purchases'],['operating_costs','Operating costs'],['selling_expenses','Selling expenses'],['sale_revenue','Actual revenue'],['position','Revenue less total costs']],'No posted project financial activity yet.')+'<p class="fat77-hint">The position is not realized accounting profit while animals remain unsold. Foreign currency amounts are kept separate.</p>')}
     ${wrap('Animals in this project','Registration automatically contributes to enrollment, cost, and performance.',table(animalsRows,[['tag','Animal'],['batch','Batch'],['status','Status'],['entry_weight_kg','Entry kg'],['current_weight_kg','Current kg'],['purchase_price','Purchase cost'],['currency','Currency']],'No project animals registered yet.'))}`;
   }else if(focus==='production'){
     contents=wrap('Animal procurement & production targets','Set acquisition strategy, initial weights, growth targets and expected finishing performance.',
      `<div class="fat77-fact-grid">${[['Planned headcount',k.planned_animals],['Expected entry weight',plan.entry_weight_kg!=null?plan.entry_weight_kg+' kg':'—'],['Target finishing weight',plan.finishing_weight_kg!=null?plan.finishing_weight_kg+' kg':'—'],['Target ADG',plan.target_adg_kg_day!=null?plan.target_adg_kg_day+' kg/day':'—'],['Fattening days',plan.duration_days||'—'],['Mortality allowance',plan.expected_mortality_percent!=null?plan.expected_mortality_percent+'%':'—']].map(([a,b])=>`<div><small>${esc(a)}</small><strong>${esc(b)}</strong></div>`).join('')}</div>
      ${table([{breeds:plan.planned_breeds,source:plan.sourcing_strategy,start:plan.procurement_start,end:plan.procurement_end,notes:plan.production_notes}],[['breeds','Planned breeds'],['source','Procurement strategy'],['start','Procurement from'],['end','Procurement until'],['notes','Production notes']])}
      <p class="fat77-hint">Registered animals are linked through their batches automatically. Planning targets never create fictitious animal records.</p>`,action('production','Edit production plan'));
   }else if(focus==='budget'){
     contents=wrap('Detailed budget per animal','Create an acquisition and fattening budget using consistent per-animal cost assumptions.',
      `<div class="fat71-kpis">${metric('Planned cost / animal',money(plannedHead))}${metric('Planned project cost',money(k.planned_project_cost))}${metric('Contingency / head',money(plan.contingency_per_head||0))}${metric('Total funding required',money(k.funding_including_contingency))}</div>
      ${table(lines,budgetCols,'Budget lines have not yet been entered.')}
      <div class="fat71-charts">${graph({title:'Planned cost composition',kind:'pie',unit:cur,points:lines.map(x=>({label:x.category,value:x.project_amount}))})}${graph({title:'Recorded cost composition',kind:'pie',unit:cur,points:costChart})}</div>
      <p class="fat77-hint">Contingency is a funding reserve, not an expense until utilized. Feed quantity-based forecasts are not added on top of an entered feed budget.</p>`,action('budget','Edit budget per animal'));
   }else if(focus==='resources'){
     const phases=info.feeding_phases||[];
     contents=wrap('Feed, workforce & ranch resources','Define daily feed, staffing, water, pens and supporting equipment.',
       `<div class="fat77-fact-grid">${[['Feed kg/head/day',plan.feed_kg_head_day],['Planned feed cost/kg',money(plan.planned_feed_cost_kg)],['Water liters/head/day',plan.water_liters_head_day],['Staff required',plan.staffing_required],['Pens required',plan.pens_required],['Funding source',plan.funding_source||'—']].map(([a,b])=>`<div><small>${esc(a)}</small><strong>${esc(b??'—')}</strong></div>`).join('')}</div>
        ${table([{feed:plan.feed_strategy,team:plan.staffing_plan,equipment:plan.equipment_plan,water:plan.water_plan}],[['feed','Feeding strategy'],['team','Staffing and shifts'],['equipment','Equipment'],['water','Water arrangement']])}
        <div class="fat77-subhead"><h4>Planned feeding stages</h4>${editable?'<button class="btn" data-project-add="phase">+ Add stage</button>':''}</div>${listTable(phases,[['stage','Feeding stage'],['duration_days','Days'],['kg_per_head_day','Kg/head/day'],['planned_mix','Target mix']], 'phase','No feeding phases planned yet.')}
        <p class="fat77-hint">Feed phases are planning assumptions. Actual mix assignments, feed issues and expenses remain in their operational modules and flow to project actuals.</p>`,action('resources','Edit resources'));
   }else if(focus==='commercial'){
     const basis=plan.expected_sale_price_kg!=null?'per kg':plan.expected_sale_price_head!=null?'per head':'Not set';
     contents=wrap('Market & sale forecast','Plan destination, pricing, selling costs, and expected recoveries.',
      `<div class="fat71-kpis">${metric('Target market',market)}${metric('Price basis',basis)}${metric('Expected revenue',money(k.planned_revenue))}${metric('Forecast contribution',money(k.forecast_contribution))}</div>
       ${table([{buyers:plan.customer_profile,window:plan.expected_sale_window,price:plan.expected_sale_price_kg??plan.expected_sale_price_head,expenses:plan.selling_expense_per_head,notes:plan.commercial_notes}],[['buyers','Target customer'],['window','Selling window'],['price','Planned selling price'],['expenses','Selling expense/head'],['notes','Commercial assumptions']])}
       <p class="fat77-hint">These are forecasts, not revenue. Only confirmed Animal Sales transactions enter the project realized sales register.</p>`,action('commercial','Edit commercial forecast'));
   }else if(focus==='milestones'){
     const milestones=info.milestones||[];
     contents=wrap('Execution schedule & milestones','Track planned dates, responsible employees, actual completion and delays.',
       `<div class="fat77-progress"><span style="width:${milestones.length?Math.round(100*milestones.filter(m=>m.status==='completed').length/milestones.length):0}%"></span></div><p class="fat77-hint">${milestones.filter(m=>m.status==='completed').length} of ${milestones.length} milestones complete</p>
       ${listTable(milestones,[['title','Milestone'],['owner','Owner'],['target_date','Planned'],['actual_date','Actual'],['status','Status']], 'milestone','No milestones yet. Add the project preparation, procurement, fattening and sales phases.')}`,editable?'<button class="btn commit" data-project-add="milestone">+ Add milestone</button>':'');
   }else if(focus==='cashflow'){
     const flows=info.cashflow_lines||[];const plannedIn=flows.reduce((n,x)=>n+Number(x.expected_inflow||0),0),plannedOut=flows.reduce((n,x)=>n+Number(x.expected_outflow||0),0);
     contents=wrap('Monthly cash-flow planning','Track expected funding requirements and receipts by month. Cash flow is distinct from accounting profit.',
      `<div class="fat71-kpis">${metric('Expected cash inflows',money(plannedIn))}${metric('Expected cash outflows',money(plannedOut))}${metric('Projected net cash',money(plannedIn-plannedOut))}</div>
       ${listTable(flows,[['period','Month'],['description','Purpose'],['expected_inflow','Inflow'],['expected_outflow','Outflow']],'cashflow','No monthly forecast prepared yet.')}
       <div class="fat71-charts">${graph({title:'Planned cash outflows by month',kind:'bar',unit:cur,points:flows.map(f=>({label:f.period,value:f.expected_outflow}))})}${graph({title:'Planned cash inflows by month',kind:'bar',unit:cur,points:flows.map(f=>({label:f.period,value:f.expected_inflow}))})}</div>`,editable?'<button class="btn commit" data-project-add="cashflow">+ Add cash-flow entry</button>':'');
   }else if(focus==='risks'){
     const risks=info.risks||[];
     contents=wrap('Risk register & mitigation','Record operational, health, financial and market risks with clear accountable owners.',
      `${listTable(risks,[['title','Risk'],['likelihood','Likelihood'],['impact','Impact'],['owner','Owner'],['mitigation','Mitigation'],['review_date','Review'],['status','Status']],'risk','No risks entered yet.')}
       <div class="fat77-subhead"><h4>Additional management notes</h4>${editable?'<button class="btn" data-project-edit="riskNotes">Edit notes</button>':''}</div><p class="fat77-notes">${esc(plan.risk_notes||'No additional notes yet.')}</p>`,editable?'<button class="btn commit" data-project-add="risk">+ Register risk</button>':'');
   }else if(focus==='scenarios'){
     const scenarios=info.scenarios||[],results=info.scenario_rows||[];
     contents=wrap('Scenario planning & sensitivity analysis','Test lower selling prices, higher feed costs, delays and mortality without changing the approved budget.',
        `${listTable(scenarios,[['name','Scenario'],['price_change_percent','Sale price change %'],['feed_cost_change_percent','Feed cost change %'],['additional_days','Extra days'],['additional_mortality_percent','Extra mortality %']],'scenario','No alternative scenarios have been recorded.')}
        <div class="fat77-subhead"><h4>Calculated scenario outcomes</h4></div>
        ${table(results,[['name','Scenario'],['expected_sales_headcount','Expected animals sold'],['forecast_cost','Projected cost'],['forecast_revenue','Projected revenue'],['forecast_contribution','Projected contribution']],'Define an expected selling price in Commercial Forecast, then add a scenario to calculate an outcome.')}
        ${graph({title:'Scenario revenue comparison',kind:'bar',unit:cur,points:results.filter(x=>x.forecast_revenue!=null).map(x=>({label:x.name,value:x.forecast_revenue}))})}
        <p class="fat77-hint">These projections use the planned budget and sale assumptions. They are not historical financial statements or binding commitments.</p>`,editable?'<button class="btn commit" data-project-add="scenario">+ Add scenario</button>':'');
   }else if(focus==='approval'){
     contents=wrap('Plan approval, versions & controls','Authorized managers approve the baseline; subsequent adjustments require a traceable revision.',
       `<div class="fat77-fact-grid">${[['Plan status',human(info.plan?.status||'Not prepared')],['Current version',info.plan?.version||'—'],['Approved at',info.plan?.approved_at||'Not approved'],['Ready subsections',Object.values(info.section_completed||{}).filter(Boolean).length+' / 8']].map(([a,b])=>`<div><small>${esc(a)}</small><strong>${esc(b)}</strong></div>`).join('')}</div>
       ${projectCells((info.notes||[]).map((n,i)=>({index:i+1,message:n})),[['index','#'],['message','Accounting notes']])}
       <div class="fat77-subhead"><h4>Approved baseline history</h4></div>
       ${table(info.version_history||[],[['version','Version'],['status','Status'],['recorded_at','Approved / recorded on']],'No approved versions yet.')}
       <div class="fat77-action-row">${can('projects.manage')&&info.plan?.status==='draft'?'<button class="btn commit" id="fat77-approve">Approve and lock project plan</button>':''}${can('projects.manage')&&info.plan?.status==='approved'?'<button class="btn" id="fat77-revise">Start an auditable revision</button>':''}</div>
       <p class="fat77-hint">Approving publishes the budget and production targets to the core Projects register. Draft edits do not silently alter an approved baseline.</p>`);
   }
   const areaIndex=PROJECT_AREAS.findIndex(a=>a.id===currentArea.id);
   const pager=`<div class="fat78-workspace-pager"><button class="btn fat78-all-sections" type="button" data-project-jump="sections">↑ Choose another section</button><div class="fat78-pager-buttons">${areaIndex>0?`<button class="btn" type="button" data-project-pager="${PROJECT_AREAS[areaIndex-1].id}">← ${esc(PROJECT_AREAS[areaIndex-1].name)}</button>`:''}${areaIndex<PROJECT_AREAS.length-1?`<button class="btn commit" type="button" data-project-pager="${PROJECT_AREAS[areaIndex+1].id}">${esc(PROJECT_AREAS[areaIndex+1].name)} →</button>`:''}</div></div>`;
   const body=`<section class="fat77-project-workspace">${projectHeader}${tiles}${approvalNote}<div class="fat77-workspace-view"><div class="fat77-view-label"><span>${projectIcon(currentArea.icon)}</span><div><strong>${esc(currentArea.name)}</strong><small>${esc(currentArea.desc)}</small></div><button class="btn small fat78-back-to-sections" type="button" data-project-jump="sections">↑ Sections</button></div>${contents}${pager}</div></section>`;
   root.innerHTML=head('Project Management','Operational planning, budgeting, milestones, risks and live financial performance','')+submoduleWorkspace('Animal Fattening',sections,'projects',body);
   bindSubmodules(root,id=>{tab=id;rememberSubmodule('fattening',id);render(root)});
   root.querySelector('#fat77-back-projects')?.addEventListener('click',async()=>{await render(root);window.scrollTo({top:0,behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches?'auto':'smooth'});});
   root.querySelectorAll('[data-project-area]').forEach(btn=>btn.addEventListener('click',()=>showProjectDashboard(projectId,btn.dataset.projectArea,'detail')));
   root.querySelectorAll('[data-project-pager]').forEach(btn=>btn.addEventListener('click',()=>showProjectDashboard(projectId,btn.dataset.projectPager,'detail')));
   root.querySelectorAll('[data-project-jump]').forEach(btn=>btn.addEventListener('click',()=>fatteningScrollTo(root,'sections')));
   if(scrollDestination)fatteningScrollTo(root,scrollDestination);
   const submit=async(section,data)=>{await saveProjectSection(projectId,section,data,info.plan_revision||'new');await showProjectDashboard(projectId,focus,'detail')};
   function editForm(section,title,fields,transform=d=>d){
     if(!editable){alert('An approved plan must be revised before editing.');return;}
     fatModal({title:`${title} · ${project.name}`,intro:`<p class="fat77-modal-note">Changes are saved only to <b>${esc(title)}</b>. All other project sections stay unchanged.</p>`,fields,saveLabel:'Save '+title,onSave:async d=>{
       const result=transform(d);
       if(section==='production'||section==='resources'||section==='risks'){
         for(const f of fields)if(!Object.prototype.hasOwnProperty.call(d,f.name))result[f.name]=null;
       }
       await submit(section,result);
     }});
   }
   const numberField=(name,label,def=null,opts={})=>({name,label,type:'number',min:0,step:'.01',value:def??'',...opts});
   const textField=(name,label,def='',opts={})=>({name,label,value:def??'',...opts});
   const dateField=(name,label,def='')=>({name,label,type:'date',value:def??''});
   const budgetCategories=['Animal purchase','Feed','Veterinary','Labor','Transportation','Housing','Other'];
   const budgetValue=c=>planBudget.find(x=>x.category===c)?.amount_per_head??0;
   const editHandlers={
     production:()=>editForm('production','Production plan',[
       numberField('planned_animals','Number of animals planned',plan.planned_animals||project.target_animals||100,{required:true,min:1,step:1}),
       numberField('entry_weight_kg','Expected entry weight (kg)',plan.entry_weight_kg),numberField('finishing_weight_kg','Target final live weight (kg)',plan.finishing_weight_kg),
       numberField('target_adg_kg_day','Daily gain target (kg/head/day)',plan.target_adg_kg_day,{step:'.001'}),
       numberField('duration_days','Fattening duration (days)',plan.duration_days||90,{min:1,step:1,required:true}),
       numberField('expected_mortality_percent','Planned mortality allowance (%)',plan.expected_mortality_percent??0,{step:'.1'}),
       textField('planned_breeds','Planned breeds',plan.planned_breeds),textField('sourcing_strategy','Source / acquisition strategy',plan.sourcing_strategy,{type:'textarea',wide:true}),
       dateField('procurement_start','Procurement start date',plan.procurement_start),dateField('procurement_end','Procurement end date',plan.procurement_end),
       textField('production_notes','Production assumptions',plan.production_notes,{type:'textarea',wide:true})],
       d=>({...d,planned_animals:Number(d.planned_animals),duration_days:Number(d.duration_days)})),
     budget:()=>editForm('budget','Budget per animal',[
       ...budgetCategories.map((cat,i)=>numberField('item_'+i,cat+' cost per animal ('+cur+')',budgetValue(cat))),
       numberField('selling_expense_per_head','Selling expenses per animal',plan.selling_expense_per_head??0),
       numberField('contingency_per_head','Contingency reserve per animal',plan.contingency_per_head??0)
     ],d=>({budget_lines:budgetCategories.map((category,i)=>({category,amount_per_head:Number(d['item_'+i]||0)})),selling_expense_per_head:Number(d.selling_expense_per_head||0),contingency_per_head:Number(d.contingency_per_head||0)})),
     resources:()=>editForm('resources','Feeding & resources',[
       numberField('feed_kg_head_day','Planned daily feed per head (kg)',plan.feed_kg_head_day,{step:'.001'}),
       numberField('planned_feed_cost_kg','Planned feed price per kg ('+cur+')',plan.planned_feed_cost_kg),
       numberField('water_liters_head_day','Water requirement per head/day (liters)',plan.water_liters_head_day),
       numberField('staffing_required','Employees needed',plan.staffing_required,{step:1}),
       numberField('pens_required','Pens needed',plan.pens_required,{step:1}),
       textField('funding_source','Planned funding source',plan.funding_source),
       textField('feed_strategy','Feeding and ration strategy',plan.feed_strategy,{type:'textarea',wide:true}),
       textField('staffing_plan','Staff shifts and responsibilities',plan.staffing_plan,{type:'textarea',wide:true}),
       textField('equipment_plan','Equipment and infrastructure',plan.equipment_plan,{type:'textarea',wide:true}),
       textField('water_plan','Water provision and contingency',plan.water_plan,{type:'textarea',wide:true})]),
     commercial:()=>editForm('commercial','Commercial forecast',[
       textField('target_market','Target market or destination',plan.target_market),
       textField('customer_profile','Target customer/buyer group',plan.customer_profile),
       {name:'price_basis',label:'Expected selling price basis',type:'select',required:true,value:plan.expected_sale_price_head!=null?'head':'kg',options:[{value:'kg',label:'Per kilogram'},{value:'head',label:'Per head'}]},
       numberField('price','Expected sale price ('+cur+')',plan.expected_sale_price_kg??plan.expected_sale_price_head??0,{required:true}),
       textField('expected_sale_window','Anticipated sales window',plan.expected_sale_window),
       textField('commercial_notes','Buyer assumptions and sales strategy',plan.commercial_notes,{type:'textarea',wide:true})
     ],d=>({target_market:d.target_market||null,customer_profile:d.customer_profile||null,expected_sale_window:d.expected_sale_window||null,commercial_notes:d.commercial_notes||null,expected_sale_price_kg:d.price_basis==='kg'?Number(d.price):null,expected_sale_price_head:d.price_basis==='head'?Number(d.price):null})),
     riskNotes:()=>editForm('risks','Risk notes',[textField('risk_notes','Additional mitigation notes',plan.risk_notes,{type:'textarea',wide:true})]),
   };
   root.querySelectorAll('[data-project-edit]').forEach(btn=>btn.addEventListener('click',()=>editHandlers[btn.dataset.projectEdit]?.()));
   const listConfig={
      milestone:{section:'milestones',key:'milestones',label:'Milestone',fields:o=>[
       textField('title','Milestone title',o.title,{required:true}),textField('owner','Person responsible',o.owner),dateField('target_date','Target date',o.target_date),
       dateField('actual_date','Actual completion date',o.actual_date),{name:'status',label:'Progress status',type:'select',value:o.status||'planned',options:['planned','in_progress','completed','delayed']},textField('notes','Comments',o.notes,{type:'textarea',wide:true})]},
      risk:{section:'risks',key:'risks',label:'Risk',fields:o=>[
       textField('title','Risk description',o.title,{required:true}),{name:'likelihood',label:'Likelihood',type:'select',value:o.likelihood||'medium',options:['low','medium','high']},
       {name:'impact',label:'Financial / operational impact',type:'select',value:o.impact||'medium',options:['low','medium','high']},
       textField('owner','Risk owner',o.owner),dateField('review_date','Review date',o.review_date),
       {name:'status',label:'Status',type:'select',value:o.status||'open',options:['open','mitigating','closed']},
       textField('mitigation','Mitigation and response plan',o.mitigation,{type:'textarea',wide:true})]},
      cashflow:{section:'cashflow',key:'cashflow_lines',label:'Cash-flow entry',fields:o=>[
       textField('period','Period (YYYY-MM)',o.period,{required:true,placeholder:'2026-11'}),
       textField('description','Description',o.description,{required:true}),
       numberField('expected_inflow','Expected cash received ('+cur+')',o.expected_inflow??0),numberField('expected_outflow','Expected cash paid ('+cur+')',o.expected_outflow??0)]},
      scenario:{section:'scenarios',key:'scenarios',label:'Scenario',fields:o=>[
       textField('name','Scenario name',o.name,{required:true}),
       numberField('price_change_percent','Selling price change (%)',o.price_change_percent??0,{min:-95}),
       numberField('feed_cost_change_percent','Feed cost change (%)',o.feed_cost_change_percent??0,{min:-95}),
       numberField('additional_days','Extra fattening days',o.additional_days??0,{step:1}),
       numberField('additional_mortality_percent','Additional mortality (%)',o.additional_mortality_percent??0),
       textField('assumptions','Scenario assumptions',o.assumptions,{type:'textarea',wide:true})]},
      phase:{section:'resources',key:'feeding_phases',label:'Feeding phase',fields:o=>[
       {name:'stage',label:'Stage',type:'select',value:o.stage||'starter',options:['starter','grower','finisher','maintenance','other']},
       numberField('duration_days','Stage duration (days)',o.duration_days??30,{required:true,min:1,step:1}),
       numberField('kg_per_head_day','Feed per animal/day (kg)',o.kg_per_head_day??0,{required:true,step:'.001'}),
       textField('planned_mix','Proposed feed mix',o.planned_mix),textField('notes','Stage notes',o.notes,{type:'textarea',wide:true})]},
   };
   function entryEditor(type,index=null){
     if(!editable)return;
     const conf=listConfig[type],current=plan[conf.key]||[],old=index===null?{}:current[index]||{};
     fatModal({title:`${index===null?'Add':'Edit'} ${conf.label} · ${project.name}`,fields:conf.fields(old),saveLabel:index===null?'Add record':'Save changes',onSave:async data=>{
       const next=[...current];if(index===null)next.push(data);else next[index]=data;
       await submit(conf.section,{[conf.key]:next});
     }});
   }
   function listTable(rows,cols,type,empty){
     const view=projectCells(rows,cols,empty);
     if(!editable||!rows?.length)return view;
     // Add an action row outside the shared table rather than changing its semantics.
     return view+`<div class="fat77-record-actions">${rows.map((r,i)=>`<div><span>${esc(r.title||r.description||r.period||r.stage||'Entry '+(i+1))}</span><button class="btn small" data-project-entry-edit="${type}:${i}" type="button">Edit</button><button class="btn small" data-project-entry-delete="${type}:${i}" type="button">Remove</button></div>`).join('')}</div>`;
   }
   // Attach row-action buttons generated inside each specific subsection.
   root.querySelectorAll('[data-project-add]').forEach(b=>b.onclick=()=>entryEditor(b.dataset.projectAdd));
   root.querySelectorAll('[data-project-entry-edit]').forEach(b=>b.onclick=()=>{const [type,index]=b.dataset.projectEntryEdit.split(':');entryEditor(type,Number(index))});
   root.querySelectorAll('[data-project-entry-delete]').forEach(b=>b.onclick=async()=>{
     const [type,id]=b.dataset.projectEntryDelete.split(':'),conf=listConfig[type],index=Number(id);
     if(!editable||!confirm('Remove this '+conf.label.toLowerCase()+' from the draft project plan?'))return;
     try{await submit(conf.section,{[conf.key]:(plan[conf.key]||[]).filter((_,i)=>i!==index)})}catch(e){alert(e.message)}
   });
   root.querySelector('#fat77-approve')?.addEventListener('click',async()=>{if(!confirm('Approve and lock this budget baseline?'))return;try{await approveProjectPlan(projectId);await showProjectDashboard(projectId,'approval','detail')}catch(e){alert(e.message)}});
   root.querySelector('#fat77-revise')?.addEventListener('click',async()=>{if(!confirm('Create a new draft version while preserving the approved plan?'))return;try{await reviseProjectPlan(projectId);await showProjectDashboard(projectId,'approval','detail')}catch(e){alert(e.message)}});
 }
 async function openAnimalCostForm(context={}){
   const id=Number(context.animal_id);
   if(!id){alert('Choose an animal before entering its operating cost.');return;}
   let p;try{p=await animalProfile(id)}catch(e){alert(e.message);return;}
   if(p.status!=='active'){alert('Post historical cost corrections through Finance audit.');return;}
   fatModal({title:`Operating cost · ${p.tag} · ${p.project||''}`,
     intro:`<div class="fat76-project-notice">This expense is recorded once in Finance and automatically appears in the animal, its batch and its parent project. Do not use this form to re-enter animal purchase or existing feed consumption costs.</div>`,
     fields:[{name:'animal_id',label:'Animal',type:'fixed',value:id,display:p.tag},
       {name:'category',label:'Expense category',type:'select',required:true,options:['Veterinary','Medication','Transport','Labor','Housing','Maintenance','Other direct operating cost']},
       {name:'amount',label:'Expense amount',type:'number',min:'.01',step:'.01',required:true},
       {name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:p.currency||'TZS',required:true},
       {name:'description',label:'Expense details',type:'textarea',wide:true}],saveLabel:'Record expense',
     onSave:async d=>{await fatPost(`animals/${id}/costs`,{category:d.category,amount:d.amount,currency:d.currency,description:d.description});await render(root)}});
 }
 async function openSaleForm(context={}){
   const eligible=animals.filter(a=>a.status==='active');if(!eligible.length){alert('There are no eligible active animals for sale.');return;}
   let profile=null;
   const formFields=fieldsFor('sales',context);
   fatModal({title:'Animal Sale · Review profit or loss before confirming',fields:formFields,
     intro:'<div id="fat76-sale-preview" class="fat76-sale-preview" aria-live="polite">Select an animal to view latest weight, cost breakdown and break-even.</div>',
     saveLabel:'Review and confirm sale',onSave:async d=>{
       const id=Number(d.animal_id);delete d.animal_id;
       if(d.price_basis==='per_head'&&!d.weight_kg){/* weight is optional for per-head sale */}
       if(d.price_basis==='per_kg'&&!(Number(d.weight_kg)>0))throw Error('Measured sale weight is required for a per-kg sale.');
       const preview=await previewAnimalSale(id,d);
       if(!preview.comparable)throw Error(preview.warnings.join(' '));
       const amount=n=>n==null?'Unavailable':Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
       const message=`Final accounting review — ${preview.tag}\n\nPurchase: ${preview.currency} ${amount(preview.purchase_cost)}\nDirect fattening costs: ${amount(preview.direct_costs)}\nAllocated batch costs: ${amount(preview.allocated_batch_costs)}\nSelling expenses: ${amount(preview.selling_expenses)}\nTotal break-even: ${amount(preview.total_break_even)}\nExpected revenue: ${amount(preview.gross_revenue)}\nProjected profit/loss: ${amount(preview.projected_profit_loss)}\n\nConfirm and post this sale to Finance?`;
       if(!window.confirm(message))throw Error('Sale not confirmed; no financial entries were posted.');
       await fatPost(`animals/${id}/sale/confirm`,{...d,preview_token:preview.preview_token});
       await render(root);
     }});
   const node=document.querySelector('#modal-root');const form=node.querySelector('#modal-form');
   const refresh=async()=>{
     const selected=Number(form?.elements?.animal_id?.value||context.animal_id||0);
     if(!selected)return;
     const pnl=node.querySelector('#fat76-sale-preview');if(!pnl)return;
     if(!profile||profile.id!==selected){try{profile=await animalProfile(selected)}catch(e){pnl.textContent=e.message;return;}
       if(form.elements.currency)form.elements.currency.value=profile.currency||'TZS';
       if(form.elements.weight_kg&&!Number(form.elements.weight_kg.value))form.elements.weight_kg.value=profile.current_weight_kg||'';
     }
     const input=n=>Number(form?.elements?.[n]?.value||0);
     const base=profile.break_even||{},expenses=input('transport_cost')+input('commission_cost')+input('other_cost');
     const gross=input('price_per_unit')*(form?.elements?.price_basis?.value==='per_kg'?input('weight_kg'):1);
     const comparable=base.comparable&&form?.elements?.currency?.value===base.currency;
     const total=comparable&&base.amount!=null?Number(base.amount)+expenses:null;
     const profit=total==null?null:gross-total;
     const money=v=>v==null?'FX required / insufficient data':`${esc(base.currency)} ${fmt(v,2)}`;
     pnl.innerHTML=`<h3>Live animal costing · ${esc(profile.tag)}</h3><div class="fat76-sale-grid">
      ${metric('Latest weight',profile.current_weight_kg==null?'—':fmt(profile.current_weight_kg)+' kg')}
      ${metric('Animal purchase',money(base.purchase_cost))}
      ${metric('Direct fattening costs',money(base.direct_fattening_costs))}
      ${metric('Allocated batch expenses',money(base.allocated_batch_costs))}
      ${metric('Animal break-even',money(base.amount))}
      ${metric('Selling expenses',money(expenses))}
      ${metric('Total break-even',money(total))}
      ${metric('Expected revenue',money(gross))}</div>
      <div class="fat76-sale-result ${profit!=null&&profit<0?'is-loss':''}"><span>Projected ${profit==null?'profit/loss unavailable':profit<0?'loss':'profit'}</span><strong>${profit==null?'FX required':money(Math.abs(profit))}</strong></div>
      <p>Figures update as you edit the price, weight or expenses. Batch costs are allocated estimates. The server recalculates them before the sale is posted.</p>`;
   };
   form?.addEventListener('input',()=>{void refresh()});form?.addEventListener('change',()=>{void refresh()});
   await refresh();
 }
 async function showAnimalProfile(id){
   let record;
   try{record=await animalProfile(id)}catch(e){alert(e.message);return}
   const num=(v,d=2)=>v==null?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
   const kpi=(label,value)=>`<div class="fattening-metric"><div class="fat72-kpi-heading"><span>${esc(label)}</span></div><strong>${esc(value)}</strong></div>`;
   const currency=esc(record.currency||'TZS');
   const costs=(record.accounts||[]).map(c=>`<div class="fattening-cost"><strong>${esc(c.currency)}</strong><span>Purchase ${num(c.acquisition)} · Attributed operations ${num(c.fattening_costs)} · Combined ${num(c.total_recorded_cost)}</span></div>`).join('');
   const points=record.weight_series||[];
   const weights=points.map(p=>+p.kg).filter(Number.isFinite);const min=weights.length?Math.min(...weights)-5:0,max=weights.length?Math.max(...weights)+5:1;
   const chart=points.length>1?`<svg viewBox="0 0 600 160" class="fattening-profile-chart" role="img" aria-label="Animal live weight history"><polyline fill="none" stroke="${CHART_BLUE.line}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" points="${points.map((p,i)=>`${30+i*540/Math.max(1,points.length-1)},${138-116*(+p.kg-min)/(max-min||1)}`).join(' ')}"/>${points.map((p,i)=>`<circle cx="${30+i*540/Math.max(1,points.length-1)}" cy="${138-116*(+p.kg-min)/(max-min||1)}" r="3.5" fill="${CHART_BLUE.point}"><title>${esc(p.date)}: ${esc(p.kg)} kg</title></circle>`).join('')}</svg>`:'<p class="muted">Record weights on separate dates to display a growth chart.</p>';
   const expenseItems=(record.cost_breakdown||[]).filter(x=>x.amount>0);
   const totalsByCurrency={};expenseItems.forEach(x=>totalsByCurrency[x.currency]=(totalsByCurrency[x.currency]||0)+Number(x.amount));
   const costGraph=expenseItems.length?`<div class="fattening-cost-chart">${expenseItems.map(x=>{const pct=totalsByCurrency[x.currency]?Math.max(1,Number(x.amount)*100/totalsByCurrency[x.currency]):0;return `<div class="fattening-cost-row"><span>${esc(x.category)} (${esc(x.currency)})</span><strong>${num(x.amount)}</strong><div class="fattening-cost-track"><div class="fattening-cost-fill" style="width:${pct.toFixed(2)}%"></div></div></div>`}).join('')}</div>`:'<p class="muted">No detailed animal costs recorded.</p>';
   const fed=(record.feeding_series||[]).filter(p=>p.kg!=null);
   const feedGraph=fed.length?`<div class="fattening-feed-summary"><strong>${fed.length} individual feeding entries</strong><span>Latest: ${esc(fed[fed.length-1].date)} · ${num(fed[fed.length-1].kg)} kg</span></div>`:'<p class="muted">Individual feed intake has not been measured. Batch quantities are reported separately.</p>';
   const be=record.break_even||{};
   const showMoney=v=>v==null?'Currency conversion required':`${esc(be.currency||record.currency||'TZS')} ${num(v)}`;
   const financial=`${kpi('Animal purchase price',showMoney(be.purchase_cost))}${kpi('Direct fattening costs',showMoney(be.direct_fattening_costs))}${kpi('Allocated batch costs',showMoney(be.allocated_batch_costs))}${kpi('Total fattening costs',showMoney(be.fattening_costs))}<div class="fat72-break-even-card"><div class="fat72-break-even-icon">∑</div><span>BREAK-EVEN POINT <small>Per animal · Current recorded costs</small></span><strong>${showMoney(be.amount)}</strong><p>Break-even per kg: <b>${be.per_kg==null?'Weight unavailable / FX required':showMoney(be.per_kg)+' / kg'}</b></p></div>`;
   const feedData=(record.feeding_series||[]).filter(x=>x.date&&x.kg!=null).map(x=>({label:x.date,value:x.kg}));
   const financeRows=(record.accounts||[]).map(a=>({currency:a.currency,acquisition:a.acquisition,
     direct:a.direct_fattening_costs,allocated:a.allocated_batch_costs,fattening_costs:a.fattening_costs,total_cost:a.total_recorded_cost??'FX required',revenue:a.revenue}));
   const financialCols=[{key:'currency',label:'Currency'},{key:'acquisition',label:'Purchase price'},{key:'direct',label:'Direct costs'},{key:'allocated',label:'Allocated batch costs'},{key:'fattening_costs',label:'Fattening cost'},{key:'total_cost',label:'Break-even amount'},{key:'revenue',label:'Realized revenue'}];
   const html=`<div class="fattening-profile"><div class="fattening-metric-grid">${kpi('Entry date',record.entry_date||'—')}${kpi('Age at entry',record.age_months_at_entry==null?'—':record.age_months_at_entry+' months')}${kpi('Days spent',num(record.days_spent,0))}${kpi('Entry weight',record.entry_weight_kg==null?'—':num(record.entry_weight_kg)+' kg')}${kpi('Latest weight',record.current_weight_kg==null?'—':num(record.current_weight_kg)+' kg')}${kpi('Weight gain',record.gain_kg==null?'—':num(record.gain_kg)+' kg')}${kpi('ADG',record.adg_kg_day==null?'Insufficient data':num(record.adg_kg_day,3)+' kg/day')}${kpi('Individual feed',record.feed_consumed_kg==null?'Not measured':num(record.feed_consumed_kg)+' kg')}</div>
   <div class="fat71-charts">${graph({title:'Live weight progression',kind:'line',unit:'kg',points:points.map(x=>({label:x.date,value:x.kg})),note:'Based on actual dated animal weighings.'})}${graph({title:'Recorded individual feed',kind:'line',unit:'kg',points:feedData,note:'Batch quantities are not treated as individually measured intake.'})}${graph({title:'Animal cost breakdown',kind:'bar',unit:record.currency,points:expenseItems.filter(x=>x.currency===record.currency).map(x=>({label:x.category,value:x.amount})),note:'Purchase, direct operating costs, and eligible-headcount allocations of batch expenses; estimates are labelled.'})}</div>
   <section class="fattening-profile-section"><h3>Break-even costing and related expenses</h3>${cleanTable(financeRows,financialCols,{empty:'No linked Finance cost entries.'})}<div class="fattening-metric-grid fat72-financial-grid">${financial}</div><p class="fat72-be-note">${esc(be.note||'')}</p><p class="fat71-chart-note">Shared batch feed recorded: ${num(record.batch_feed_recorded_kg)} kg for the batch; not individual intake. Different currencies are not summed.</p></section>
   <section class="fattening-profile-section"><h3>Management insights</h3>${(record.insights||[]).map(i=>`<p class="fattening-insight">${esc(i)}</p>`).join('')||'<p class="muted">No exceptions detected from available records.</p>'}</section>
   <section class="fattening-profile-section"><h3>Animal identification</h3>${cleanTable([{tag:record.tag,species:record.species,breed:record.breed,sex:record.sex,origin:record.origin,supplier:record.supplier,batch:record.batch,project:record.project,ranch:record.ranch,status:record.status}],[{key:'tag',label:'Animal'},{key:'species',label:'Species'},{key:'breed',label:'Breed'},{key:'sex',label:'Sex'},{key:'origin',label:'Origin'},{key:'supplier',label:'Supplier'},{key:'batch',label:'Batch'},{key:'project',label:'Project'},{key:'status',label:'Status'}])}</section></div>`;
   fatModal({title:`Animal ${record.tag} — Performance & Financial Profile`,intro:html,fields:[],readOnly:true,saveLabel:'Close'});

 }
 async function showMix(row){
   try{
    const detail=await mixDetails(row.id);
    const ingredientColumns=[{key:'name',label:'Feed ingredient'},{key:'quantity_kg',label:'Quantity (kg)'},{key:'percentage',label:'Composition (%)'}];
    const assignmentColumns=[{key:'target',label:'Assigned batch or animal'},{key:'start_date',label:'Start date'},{key:'end_date',label:'End date'},{key:'status',label:'Status'}];
    const ingredients=detail.ingredients||[];
    const content=`<div class="fat71-mix-view"><div class="fat71-kpis">${metric('Feeding stage',human(detail.stage))}${metric('Reference mix quantity',detail.total_reference_kg==null?'Percentage recipe':fmt(detail.total_reference_kg)+' kg')}${metric('Ingredients',ingredients.length)}</div><h3>Ingredient composition</h3>${cleanTable(ingredients,ingredientColumns)}${graph({title:'Ingredient composition',kind:'pie',unit:'%',points:ingredients.map(x=>({label:x.name,value:x.percentage}))})}<h3>Mix assignments</h3>${cleanTable(detail.assignments||[],assignmentColumns,{empty:'This mix has no active or historical assignments yet.'})}<p class="fat71-chart-note">${esc(detail.note)}</p></div>`;
    fatModal({title:`${detail.name} — Feed Mix`,intro:content,fields:[],readOnly:true,saveLabel:'Close'});
   }catch(e){alert(e.message)}
 }
 function rowAction(row){
  if(tab==='projects'){showProjectDashboard(row.id,'overview','header');return;}
  if(tab==='sales'){showSaleAccounting(row);return;}
  if(tab==='mixes'){showMix(row);return;}
  if(tab==='animals'||tab==='weighing'||tab==='batches'||tab==='feeding'){
    const isAnimal=tab==='animals'||tab==='weighing';
    if(tab==='feeding'&&!row.batch_id){
      const batch=batches.find(b=>b.name===row.batch);
      if(!batch){niceRecord(row,analytics?.columns||[],'Feeding record');return;}
      row={...row,batch_id:batch.id,name:batch.name};
    }
    if(!isAnimal&&tab==='batches'&& !row.name)row={...row,name:batches.find(b=>b.id===row.id)?.name||row.batch||'Batch'};
    const animalId=isAnimal?row.id:null;
    const bId=!isAnimal?(tab==='feeding'?row.batch_id:row.id):null;
    const options=tab==='weighing'?[['profile','View animal profile'],...(animals.find(a=>a.id===animalId)?.status==='active'?[['weighing','Record this animal weight']]:[])]:isAnimal?[['profile','View complete profile'],['weighing','Record weight'],['feeding','Record feeding'],['sales','Sell animal'],...(can('finance.write')?[['cost','Add animal operating cost']]:[])]:[['feeding','Record feeding'],['animals','Add animal'],['pens','Add pen']];
    root.querySelector('#contextual-actions')?.remove();
    const box=document.createElement('div');box.id='contextual-actions';box.className='inline-record-actions';
    const tag=row.tag||row.animal||'Animal';const name=row.name||row.batch||'Batch';
    box.innerHTML=`<strong>${esc(isAnimal?'Animal '+tag:'Batch '+name)}</strong><span>What would you like to record?</span>`+options.map(([id,label])=>`<button class="btn" data-action="${id}">${label}</button>`).join('');
    root.querySelector('.submodule-work-title')?.after(box);
    box.querySelectorAll('[data-action]').forEach(btn=>btn.onclick=()=>btn.dataset.action==='profile'?showAnimalProfile(animalId):add(btn.dataset.action,isAnimal?{animal_id:animalId,display:tag}:{batch_id:bId,display:name}));
    box.scrollIntoView({block:'nearest',behavior:'smooth'});return;
  }
  const columns=(analytics?.columns?.length?analytics.columns:configs[tab].cols.map(c=>({key:c[0],label:c[1]})));
  niceRecord(row,columns,`${configs[tab].title} · Details`);
 }
 draw();
}
