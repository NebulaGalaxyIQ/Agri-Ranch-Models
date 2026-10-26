import {esc,toast,appState} from '../../shared/api.js';
import {catalog,filterSpec,query,saved,saveReport,recentRuns,exportReport,sourceDetail} from './service.js?v=reports-catalog-fix-20261026';

const COLORS=['#1a9269','#258bd3','#ef9b44','#8b6cc6','#e26770','#17b8ae','#9d752f','#5a80b8','#b45692','#5aa15d'];
const nice=(v)=>String(v||'').replaceAll('_',' ').replace(/\b(id|kg|adg|usd|tzs|ha)\b/gi,m=>m.toUpperCase());
const fmt=(v)=>v===null||v===undefined||v===''?'—':typeof v==='number'?v.toLocaleString(undefined,{maximumFractionDigits:3}):String(v);
const skeleton='<div class="v10-empty">Loading report information…</div>';
const sel=(id,items,value='')=>`<select id="${id}">${items.map(x=>`<option value="${esc(x.value)}" ${String(x.value)===String(value)?'selected':''}>${esc(x.label)}</option>`).join('')}</select>`;
let generation=0;
function initial(){return {section_id:'executive',filters:{},dataset:null,page:1,page_size:40,order:'desc',sort_by:null};}
let state=initial(), catalogueData=null, filtersData=null, current=null, savedData=[],runsData=[];
let activeRoot;
const formValue=(id)=>activeRoot?.querySelector('#'+id)?.value||'';
const empty=(msg)=>`<div class="v10-empty">${esc(msg)}</div>`;
function chartView(chart){
 const pts=(chart?.points||[]).filter(x=>Number.isFinite(Number(x.value))).slice(0,chart?.type==='line'?75:12);
 if(!pts.length)return empty('No matching records to chart. Record activity in the source module.');
 if(chart?.type==='line'){
  const values=pts.map(x=>Number(x.value));const max=Math.max(...values,1),min=Math.min(0,...values);
  const den=max-min||1;
  const coords=pts.map((p,i)=>({x:35+(i/(Math.max(1,pts.length-1)))*555,y:148-(Number(p.value)-min)/den*120}));
  const path=coords.map(p=>`${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  return `<div class="v10-line-chart"><svg viewBox="0 0 625 173" role="img" aria-label="${esc(chart.title)}" preserveAspectRatio="none"><path d="M35 16 V148 H598" fill="none" stroke="#d8e4dc" stroke-width="1.4"/><polyline points="${path}" fill="none" stroke="${chart.title?.toLowerCase().includes('gain')?'#ed903a':'#2684ca'}" stroke-width="3.8" stroke-linejoin="round" stroke-linecap="round"/>${coords.map((p,i)=>`<circle cx="${p.x}" cy="${p.y}" r="5.4" fill="${COLORS[i%COLORS.length]}" stroke="white" stroke-width="1.8"><title>${esc(pts[i].label)}: ${esc(fmt(pts[i].value))}</title></circle>`).join('')}</svg><div class="v10-line-labels"><span>${esc(pts[0]?.label)}</span><span>${esc(pts[pts.length-1]?.label)}</span></div></div><small class="v10-foot">${esc(chart.title)} · ${esc(chart.unit)}</small>`;
 }
 const peak=Math.max(...pts.map(x=>Number(x.value)),1);
 return `<div class="v10-chart" role="img" aria-label="${esc(chart.title||'Report distribution')}">${pts.map((x,i)=>`<div class="v10-chart-line"><span title="${esc(x.label)}">${esc(x.label)}</span><div class="v10-track"><div style="width:${Math.max(.5,Number(x.value)/peak*100)}%;background:${COLORS[i%COLORS.length]}"></div></div><strong>${esc(fmt(x.value))}</strong></div>`).join('')}</div><small class="v10-foot">${esc(chart.title||'Records by category')} · Units: ${esc(chart.unit||'records')}</small>`;
}
function tile(text,value,sub){return `<div class="v10-kpi"><small>${esc(text)}</small><b>${esc(fmt(value))}</b>${sub?`<small>${esc(sub)}</small>`:''}</div>`;}
function baseLayout(root){
 const cats=(catalogueData?.sections||[]);
 // Build an actual group map. Array.push() returns a number, not the accumulator.
 const groups=Object.create(null);
 for(const item of cats){
  if(!item || typeof item.group!=='string' || !item.id)continue;
  (groups[item.group]??=[]).push(item);
 }
 const chosen=cats.find(x=>x.id===state.section_id)||cats[0];
 const reportGroup=chosen?.group||'Executive';
 const extras=[
   ['v10-ranch','Ranch ID','ranch_id'],['v10-batch','Batch ID','batch_id'],
   ['v10-group-id','Herd / Flock ID','group_id'],['v10-cycle','Crop Cycle ID','cycle_id'],
   ['v10-animal-id','Individual Animal ID','animal_id'],['v10-item-id','Inventory Item ID','item_id'],
   ['v10-machine-id','Machinery ID','machine_id'],['v10-trial-id','Trial ID','trial_id'],
   ['v10-lot-id','Stock Lot ID','lot_id']
 ];
 const options=extras.map(([id,title,key])=>`<label>${title}<input id="${id}" type="number" min="1" value="${esc(state.filters[key]||'')}" placeholder="All"></label>`).join('');
 root.innerHTML=`<div class="v10-shell">
 <header class="v10-hero"><div class="v10-eyebrow">CAPE RANCH · BUSINESS INTELLIGENCE</div><h1>Management Reports</h1><p>Practical, complete reporting from actual operational records.</p></header>
 <section class="panel v10-filters"><div class="v10-section-head"><div><h2>Choose a report</h2><p>Set the report and period; additional filters are available below.</p></div></div>
 <div class="v10-filter-grid">
 <label>Reporting area ${sel('v10-group',Object.keys(groups).map(g=>({label:g,value:g})),reportGroup)}</label>
 <label>Report ${sel('v10-section',cats.filter(x=>x.group===reportGroup).map(x=>({label:x.title,value:x.id})),state.section_id)}</label>
 <label>Start date<input id="v10-from" type="date" value="${esc(state.filters.from_date||'')}"></label>
 <label>End date<input id="v10-to" type="date" value="${esc(state.filters.to_date||'')}"></label>
 <label>Project ID<input id="v10-project" type="number" min="1" value="${esc(state.filters.project_id||'')}" placeholder="All projects"></label>
 <label>Source records ${sel('v10-explorer',[{label:'Predefined reports',value:''},...(catalogueData?.explorer||[]).map(x=>({label:x.title,value:x.id}))],state.section_id.startsWith('table:')?state.section_id:'')}</label>
 </div>
 <details class="v10-more-filters" ${Object.keys(state.filters||{}).some(k=>!['from_date','to_date','project_id'].includes(k))?'open':''}><summary>Additional filters · animal, batch, ranch, stock and status</summary>
 <div class="v10-filter-grid v10-extra-filter-grid">${options}
 <label>Status<input id="v10-status" maxlength="60" value="${esc(state.filters.status||'')}" placeholder="All statuses"></label>
 <label>Species<input id="v10-species" maxlength="80" value="${esc(state.filters.species||'')}" placeholder="All species"></label>
 <label>Currency<input id="v10-currency" maxlength="10" value="${esc(state.filters.currency||'')}" placeholder="All currencies"></label>
 <label>Search records<input id="v10-search" maxlength="100" value="${esc(state.filters.search||'')}" placeholder="Name or reference"></label>
 </div></details>
 <div class="v10-filter-actions"><button id="v10-run" class="btn commit">Generate report</button><button id="v10-reset" class="btn">Clear filters</button><button id="v10-save" class="btn">Save report view</button></div>
 <p class="v10-filter-hint" id="v10-filter-hint">Filters and permissions are validated by the reporting service.</p>
 </section>
 <div id="v10-output">${skeleton}</div>
 <section class="panel v10-export-panel"><div class="v10-section-head"><div><h2>Download the full report</h2><p>Detailed PDF and Excel retain all authorized filtered source records.</p></div></div><div class="v10-actions"><button class="btn" id="v10-refresh">Refresh data</button><button class="btn commit" id="v10-export-pdf">Download PDF</button><button class="btn commit" id="v10-export-xlsx">Download Excel</button></div></section>
 <section class="v10-foot-panels"><div class="panel"><h2>Saved report views</h2><div id="v10-saved">${empty('No saved report views yet.')}</div></div><div class="panel"><h2>Recent downloads</h2><div id="v10-runs">${empty('No recent report exports.')}</div></div></section>
 </div>`;
 const group=root.querySelector('#v10-group'),section=root.querySelector('#v10-section');
 group.onchange=()=>{
  const available=groups[group.value]||[];
  section.innerHTML=available.map(x=>`<option value="${esc(x.id)}">${esc(x.title)}</option>`).join('');
  if(available.length){state.section_id=available[0].id;state.dataset=null;state.page=1;showSpec();}
 };
 section.onchange=()=>{state.section_id=section.value;state.dataset=null;state.page=1;showSpec();};
 root.querySelector('#v10-explorer').onchange=e=>{if(!e.target.value)return;state.section_id=e.target.value;state.dataset=null;state.page=1;generate();};
 root.querySelector('#v10-run').onclick=()=>{collect();generate()};
 root.querySelector('#v10-refresh').onclick=()=>{collect();generate()};
 root.querySelector('#v10-reset').onclick=()=>{state=initial();baseLayout(root);generate()};
 root.querySelector('#v10-export-pdf').onclick=()=>{collect();download('pdf')};
 root.querySelector('#v10-export-xlsx').onclick=()=>{collect();download('xlsx')};
 root.querySelector('#v10-save').onclick=async()=>{collect();const title=prompt('Name this saved report view',current?.title||'Management Report');if(!title)return;try{await saveReport({title,section_id:state.section_id,configuration:{filters:state.filters,dataset:state.dataset},visibility:'private'});toast('Saved report view created');loadHistory()}catch(e){toast(e.message,true)}};
}

async function showSpec(){
 try{filtersData=await filterSpec(state.section_id);
  const hint=activeRoot.querySelector('#v10-filter-hint');if(hint)hint.textContent='Supported filters: '+(filtersData.available_fields||[]).join(', ')+(filtersData.date_fields?.length?' · Dates: '+filtersData.date_fields.join(', '):'');
 }catch(e){console.warn(e.message)}
}
function collect(){
 const filters={};for(const [id,key] of [['v10-from','from_date'],['v10-to','to_date'],['v10-project','project_id'],['v10-ranch','ranch_id'],['v10-batch','batch_id'],['v10-group-id','group_id'],['v10-cycle','cycle_id'],['v10-animal-id','animal_id'],['v10-item-id','item_id'],['v10-machine-id','machine_id'],['v10-trial-id','trial_id'],['v10-lot-id','lot_id'],['v10-status','status'],['v10-species','species'],['v10-currency','currency'],['v10-search','search']]){
  const v=formValue(id).trim();if(v)filters[key]=['project_id','ranch_id','batch_id','group_id','cycle_id','animal_id','item_id','machine_id','trial_id','lot_id'].includes(key)?Number(v):v;
 }
 state.filters=filters;
 const s=formValue('v10-section');if(s&&!state.section_id.startsWith('table:'))state.section_id=s;
 state.page=1;state.dataset=null;
}
function compactColumns(cols,kind){
 const priority=kind==='animal_performance'
  ?['tag','species','batch_id','entry_weight_kg','latest_weight_kg','weight_change_kg','average_daily_gain_kg','status']
  :kind==='animal_weight_history'
  ?['measured_on','reading_type','weight_kg','change_since_previous_kg','gain_since_entry_kg','interval_adg_kg_day']
  :['date','name','tag','project','project_id','batch_id','item','currency','cost','amount','quantity_kg','status'];
 const selected=priority.filter(c=>cols.includes(c));
 return [...selected,...cols.filter(c=>!selected.includes(c))].slice(0,kind==='animal_performance'?8:7);
}
function reportTable(rows,allCols,kind,source){
 const cols=compactColumns(allCols,kind);
 const heading=cols.map(c=>`<th>${esc(nice(c))}</th>`).join('');
 const extra=allCols.length>cols.length?`<small class="v10-muted">Showing ${cols.length} key columns of ${allCols.length}. Full columns are included in PDF and Excel.</small>`:'';
 const body=rows.map(r=>`<tr>${cols.map(c=>`<td title="${esc(fmt(r[c]))}">${esc(fmt(r[c]))}</td>`).join('')}${kind==='animal_performance'?`<td><button class="v10-inline-action" data-open-animal="${esc(String(r.animal_id))}">Weight history & graphs</button></td>`:''}</tr>`).join('')||`<tr><td colspan="${cols.length+(kind==='animal_performance'?1:0)}">No matching records.</td></tr>`;
 return `${extra}<div class="v10-table-wrap"><table class="v10-table"><thead><tr>${heading}${kind==='animal_performance'?'<th>Progression</th>':''}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function renderData(data){
 current=data;
 const datasets=data.datasets||[];
 const selected=datasets.find(x=>x.key===state.dataset)||datasets[0];
 const analyses=data.analysis_views||[];
 const individual=analyses.find(x=>x.id==='animal_performance');
 const history=analyses.find(x=>x.id==='animal_weight_history');
 const selectedAnimal=state.filters.animal_id?individual?.rows?.find(x=>Number(x.animal_id)===Number(state.filters.animal_id)):null;
 const count=datasets.reduce((s,d)=>s+d.total_rows,0);
 let html=`<section class="v10-kpis">${tile('Report',data.title)}${tile('Source records',count)}${tile('Data sources',datasets.length)}${tile('Updated (UTC)',data.generated_at?.slice(0,16).replace('T',' '))}</section>`;
 if(selectedAnimal){
    html+=`<section class="panel v10-animal-card"><div class="v10-section-head"><div><h2>${esc(selectedAnimal.tag)} · Individual animal progression</h2><p>Recorded changes over time. Dates and scale measurements are preserved.</p></div><button class="btn" id="v10-clear-animal">All animals</button></div>
    <div class="v10-kpis">${tile('Entry weight',selectedAnimal.entry_weight_kg,'kg')}${tile('Latest weight',selectedAnimal.latest_weight_kg,'kg')}${tile('Total change',selectedAnimal.weight_change_kg,'kg')}${tile('Average daily gain',selectedAnimal.average_daily_gain_kg,'kg/day')}</div>
    ${history?`<div class="v10-progress-charts">${(history.charts||[]).map(c=>`<div class="v10-chart-card"><h3>${esc(c.title)}</h3>${chartView(c)}</div>`).join('')}</div><h3>Complete weighing history</h3>${reportTable(history.rows||[],history.columns||[],'animal_weight_history')}</div>`:empty('No dated weighing history is available for the chosen animal.')}
    </section>`;
 }
 if(individual&&!state.filters.animal_id){
    html+=`<section class="panel"><div class="v10-section-head"><div><h2>Individual animal performance</h2><p>Choose an animal to view its full weight trajectory, interval growth and dated records.</p></div></div>
    ${reportTable(individual.rows||[],individual.columns||[],'animal_performance')}
    <p class="v10-muted">Showing up to 60 animals. Use Individual Animal ID in Additional filters for other records; exports include all matching data.</p></section>`;
 }
 const remaining=analyses.filter(v=>v.id!=='animal_weight_history' && v.id!=='animal_performance');
 if(remaining.length){
    html+=`<section class="panel v10-analysis-head"><div class="v10-section-head"><div><h2>Operational analysis</h2><p>Select an analysis below. Each opens in the same column, not beside other sections.</p></div></div>
    <div class="v10-analysis-tabs">${remaining.map((a,i)=>`<button class="btn ${i===0?'active':''}" data-analysis="${i}">${esc(a.title)} <small>${fmt(a.total_rows)} records</small></button>`).join('')}</div><div id="v10-analysis-body"></div></section>`;
 }
 if(selected){
    const metrics=selected.metrics||{};
    const vals=[{label:'Matching records',value:metrics.count,unit:'records'},...Object.entries(metrics).filter(([k])=>k.startsWith('sum_')).map(([k,v])=>({label:nice(k.slice(4)),value:v,unit:metrics['unit_'+k.slice(4)]||'source unit'})),...(metrics.by_currency||[]).map(x=>({label:'Recorded value '+x.currency,value:x.amount,unit:x.currency}))];
    html+=`<section class="panel"><div class="v10-section-head"><h2>Source measurements</h2><small>${esc(selected.title)}</small></div><div class="v10-measure-grid">${vals.map(v=>`<div class="v10-measure"><small>${esc(v.label)}</small><strong>${esc(fmt(v.value))}</strong><small>${esc(v.unit)}</small></div>`).join('')}</div></section>`;
 }
 // Sources and chart follow each other vertically. Tables never resize the page.
 html+=`<section class="panel"><div class="v10-section-head"><div><h2>Source datasets</h2><p>Choose the original records you want to examine.</p></div></div><div class="v10-source-list">${datasets.map(ds=>`<button class="v10-source ${selected?.key===ds.key?'active':''}" data-source="${esc(ds.key)}"><span>${esc(ds.title)}</span><strong>${fmt(ds.total_rows)}</strong></button>`).join('')||empty('No accessible source datasets in this report.')}</div></section>`;
 if(selected){
   html+=`<section class="panel"><div class="v10-section-head"><h2>Visual trends</h2><small>Actual filtered source data</small></div><div class="v10-visual-stack">${[selected.chart,...(selected.additional_charts||[])].filter(c=>c?.points?.length).map(c=>`<div class="v10-chart-card"><h3>${esc(c.title)}</h3>${chartView(c)}</div>`).join('')||empty('No recorded trend or distribution for this selection.')}</div></section>`;
   const cols=selected.columns||[],rows=selected.rows||[];
   html+=`<section class="panel v10-detail"><div class="v10-section-head"><div><h2>${esc(selected.title)} · Source records</h2><p>A concise table here; full details in PDF/Excel and in the record viewer.</p></div><div class="v10-actions"><button class="btn" id="v10-csv">Export CSV</button><button class="btn" id="v10-print">Print</button></div></div>
   ${reportTable(rows,cols,'source')}
   ${cols.includes('id')?`<div class="v10-record-actions">${rows.slice(0,25).map(r=>`<button class="v10-inline-action" data-record="${esc(String(r.id))}" data-table="${esc(selected.key)}">Open record #${esc(String(r.id))}</button>`).join('')}</div>`:''}
   <div class="v10-pager"><span>${fmt(selected.total_rows)} records · Page ${state.page} of ${Math.max(1,Math.ceil(selected.total_rows/state.page_size))}</span><div><button class="btn" id="v10-prev" ${state.page<=1?'disabled':''}>Previous</button><button class="btn" id="v10-next" ${state.page>=Math.ceil(selected.total_rows/state.page_size)?'disabled':''}>Next</button></div></div></section>`;
 }
 if(data.omitted?.length)html+=`<section class="panel v10-warnings"><h2>Filter exclusions</h2>${data.omitted.map(x=>`<p><strong>${esc(x.title||'Unavailable source')}</strong>: ${esc(x.reason)}</p>`).join('')}</section>`;
 html+=`<section class="panel v10-method"><h2>Data quality & methodology</h2>${(data.methodology||[]).map(t=>`<p>${esc(t)}</p>`).join('')}</section>`;
 activeRoot.querySelector('#v10-output').innerHTML=html;
 const chooseAnimal=(id)=>{if(!id)return;state.filters.animal_id=Number(id);state.dataset=null;state.page=1;baseLayout(activeRoot);generate();loadHistory()};
 activeRoot.querySelectorAll('[data-open-animal]').forEach(b=>b.onclick=()=>chooseAnimal(b.dataset.openAnimal));
 activeRoot.querySelector('#v10-clear-animal')?.addEventListener('click',()=>{delete state.filters.animal_id;baseLayout(activeRoot);generate();loadHistory()});
 const drawAnalysis=(idx)=>{
  const v=remaining[idx],target=activeRoot.querySelector('#v10-analysis-body');if(!v||!target)return;
  activeRoot.querySelectorAll('[data-analysis]').forEach(b=>b.classList.toggle('active',Number(b.dataset.analysis)===idx));
  target.innerHTML=`<h3>${esc(v.title)}</h3><p class="v10-muted">${fmt(v.total_rows)} linked records · Full columns and rows in downloadable reports.</p>
  <div class="v10-progress-charts">${(v.charts||[]).filter(c=>c.points?.length).map(c=>`<div class="v10-chart-card"><h3>${esc(c.title)}</h3>${chartView(c)}</div>`).join('')}</div>
  ${reportTable((v.rows||[]).slice(0,60),v.columns||[],v.id)}<div class="v10-analysis-notes"><strong>Data quality</strong>${(v.notes||[]).map(note=>`<p>${esc(note)}</p>`).join('')}</div>`;
 };
 activeRoot.querySelectorAll('[data-analysis]').forEach(b=>b.onclick=()=>drawAnalysis(Number(b.dataset.analysis)));
 if(remaining.length)drawAnalysis(0);
 activeRoot.querySelectorAll('[data-source]').forEach(b=>b.onclick=()=>{state.dataset=b.dataset.source;state.page=1;generate()});
 activeRoot.querySelectorAll('[data-record]').forEach(b=>b.onclick=async()=>{
   try{const details=await sourceDetail(b.dataset.table,b.dataset.record);const dialog=document.createElement('dialog');dialog.className='v10-dialog';
     dialog.innerHTML=`<div class="v10-dialog-head"><h2>${esc(details.source)} · #${esc(b.dataset.record)}</h2><button class="btn" data-close>Close</button></div><div class="v10-detail-fields">${Object.entries(details.record||{}).map(([k,v])=>`<div><strong>${esc(nice(k))}</strong><span>${esc(fmt(v))}</span></div>`).join('')}</div>`;
     document.body.appendChild(dialog);dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove(),{once:true});dialog.showModal();
   }catch(e){toast(e.message,true)}
 });
 activeRoot.querySelector('#v10-prev')?.addEventListener('click',()=>{state.page--;generate()});
 activeRoot.querySelector('#v10-next')?.addEventListener('click',()=>{state.page++;generate()});
 activeRoot.querySelector('#v10-csv')?.addEventListener('click',()=>download('csv'));
 activeRoot.querySelector('#v10-print')?.addEventListener('click',()=>window.print());
}

async function generate(){
 const gen=++generation;const output=activeRoot.querySelector('#v10-output');if(output)output.innerHTML=skeleton;
 try{const result=await query(state);if(gen!==generation)return;renderData(result);showSpec()}
 catch(e){if(gen===generation)activeRoot.querySelector('#v10-output').innerHTML=`<div class="panel v10-warnings">${esc(e.message)}</div>`;toast(e.message,true)}
}
async function download(format){
 const btn=activeRoot.querySelector('#v10-export-'+format);if(btn)btn.disabled=true;
 try{
  const cfg={...state,format,mode:'complete',include_charts:true,paper:'a3',orientation:'landscape'};
  if(format==='csv'&&state.dataset)cfg.dataset=state.dataset;
  const name=await exportReport(cfg);toast('Report downloaded: '+name);loadHistory()
 }catch(e){toast(e.message,true)}finally{if(btn)btn.disabled=false}
}
async function loadHistory(){
 const [sv,rs]=await Promise.all([saved().catch(()=>({items:[]})),recentRuns().catch(()=>({items:[]}))]);savedData=sv.items||[];runsData=rs.items||[];
 const savedBox=activeRoot.querySelector('#v10-saved'),runsBox=activeRoot.querySelector('#v10-runs');
 if(savedBox)savedBox.innerHTML=savedData.length?savedData.slice(0,12).map(x=>`<button class="v10-saved-item" data-saved="${x.id}">${esc(x.title)} <small>${esc(catalogueData?.sections?.find(s=>s.id===x.section_id)?.title||'Saved custom report')}</small></button>`).join(''):empty('No saved reports. Choose filters and select Save report view.');
 if(runsBox)runsBox.innerHTML=runsData.length?runsData.slice(0,12).map(x=>`<div class="v10-run"><strong>${esc(catalogueData?.sections?.find(s=>s.id===x.section_id)?.title||'Saved custom report')}</strong> · ${esc(x.format.toUpperCase())}<small>${esc(x.created_at||'')} · ${fmt(x.rows)} records</small></div>`).join(''):empty('No exports recorded.');
 activeRoot.querySelectorAll('[data-saved]').forEach(b=>b.onclick=()=>{const x=savedData.find(s=>String(s.id)===b.dataset.saved);if(!x)return;state={...initial(),section_id:x.section_id,filters:x.configuration?.filters||{},dataset:x.configuration?.dataset||null};baseLayout(activeRoot);loadHistory();generate()});
}
export async function render(root){activeRoot=root;state=initial();generation++;root.innerHTML='<div class="panel">Loading reporting catalogue…</div>';
 try{
  catalogueData=await catalog();
  if(!Array.isArray(catalogueData?.sections) || !catalogueData.sections.length){
   root.innerHTML='<section class="panel v10-empty"><h2>No report categories available</h2><p>Check your organization access and reporting permissions.</p></section>';
   return;
  }
  baseLayout(root);await Promise.all([generate(),loadHistory()]);
 }
 catch(e){root.innerHTML=`<section class="panel v10-warnings"><h2>Reports unavailable</h2>${esc(e.message)}</section>`}
}
