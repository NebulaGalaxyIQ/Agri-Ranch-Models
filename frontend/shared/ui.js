import {esc,toast} from './api.js';
import {iconSvg} from './icons.js';
export function head(title,subtitle='',actions=''){return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="actions">${actions}</div></div>`}
export function button(text,id='',kind=''){return `<button type="button" class="btn ${kind}" ${id?`id="${esc(id)}"`:''}>${esc(text)}</button>`}
export function tiles(items){return `<div class="grid modules">${items.map(x=>`<button type="button" class="panel module-card" data-module="${esc(x.id)}" aria-label="Open ${esc(x.title)}"><img alt="" loading="lazy" decoding="async" src="/frontend/public/images/v65/overview/${esc(x.id)}.webp" onerror="this.src='/frontend/public/images/v65/${esc(x.id)}-hero.webp'"><div class="module-desc"><span class="module-tile-icon">${iconSvg(x.id,{size:22})}</span><div><h3>${esc(x.title)}</h3><p>${esc(x.description)}</p></div><span class="module-tile-arrow" aria-hidden="true">→</span></div></button>`).join('')}</div>`}
export function kpis(items){return `<div class="grid kpi">${items.map((x,i)=>`<div class="panel kpi-card"><div class="metric-icon metric-${i%5}">${iconSvg(x.icon||['fattening','livestock','crops','machinery','inventory'][i%5],{size:23})}</div><div class="metric-copy"><div class="muted">${esc(x.label)}</div><span class="number">${esc(x.value??'—')}</span>${x.note?`<div class="metric-note">${esc(x.note)}</div>`:''}</div></div>`).join('')}</div>`}
export function table(items,columns,{empty='No records yet',click=true}={}){
 const rows=items||[];
 return rows.length?`<div class="data-table-wrap"><table class="data-table"><thead><tr>${columns.map(c=>`<th>${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${rows.map((r,i)=>`<tr class="${click?'clickable':''}" data-index="${i}">${columns.map(c=>`<td>${esc(typeof c[2]==='function'?c[2](r):r[c[0]]??'—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:`<div class="empty">${esc(empty)}</div>`
}
export function listenRows(root,items,callback){root.querySelectorAll('tr[data-index]').forEach(row=>{row.onclick=()=>callback(items[Number(row.dataset.index)])})}
export function barChart(data){const valid=(data||[]).filter(d=>Number.isFinite(+d.value));const top=Math.max(1,...valid.map(x=>+x.value));return `<div class="bar-chart">${valid.map(d=>`<div class="bar-column"><div class="bar-rect" title="${esc(d.label)}: ${esc(d.value)}" style="height:${Math.max(2,100*+d.value/top)}%"></div><span>${esc(d.label)}</span></div>`).join('')}</div>`}
export function panel(title,content,action=''){return `<section class="panel"><div class="section-heading"><h2>${esc(title)}</h2>${action}</div>${content}</section>`}
export function detailModal(record,{title='Record details'}={}){modalForm({title,fields:[],saveLabel:'Close',readOnly:true,intro:`<div class="form-grid">${Object.entries(record).filter(([k])=>!k.endsWith('_json')).map(([k,v])=>`<div><strong>${esc(k.replaceAll('_',' '))}</strong><div>${esc(v)}</div></div>`).join('')}</div>`})}
let closeHandler=null;
export function closeModal(){const node=document.querySelector('#modal-root');node.replaceChildren();document.body.style.overflow='';document.removeEventListener('keydown',closeHandler);closeHandler=null}
export function modalForm({title,fields=[],onSave=async()=>{},saveLabel='Save',intro='',steps=[],readOnly=false}){
 const root=document.querySelector('#modal-root');closeModal();document.body.style.overflow='hidden';let step=0;
 const formId=`modal-form`;
 function control(f){
  const attrs=`name="${esc(f.name)}" ${f.required?'required':''} ${f.min!==undefined?`min="${f.min}"`:''} ${f.step!==undefined?`step="${f.step}"`:''}`;
  const raw=f.value??'';
  if(f.type==='select'&&f.required&&f.options?.length===1){const only=typeof f.options[0]==='string'?{value:f.options[0],label:f.options[0]}:f.options[0];return `<div class="fixed-value">${esc(only.label)}<input type="hidden" name="${esc(f.name)}" value="${esc(only.value)}"></div>`}
  if(f.type==='select')return `<select ${attrs}><option value="">Select ${esc(f.label.toLowerCase())}</option>${(f.options||[]).map(v=>{const item=typeof v==='string'?{value:v,label:v}:v;return `<option value="${esc(item.value)}" ${String(raw)===String(item.value)?'selected':''}>${esc(item.label)}</option>`}).join('')}</select>`;
  if(f.type==='fixed')return `<div class="fixed-value">${esc(f.display??raw)}<input type="hidden" name="${esc(f.name)}" value="${esc(raw)}"></div>`;
  if(f.type==='textarea')return `<textarea ${attrs}>${esc(raw)}</textarea>`;
  if(f.type==='file')return `<input type="file" ${attrs} accept="${esc(f.accept||'image/png,image/jpeg,image/webp')}">`;
  if(f.type==='checkbox')return `<input type="checkbox" ${attrs} ${raw?'checked':''}>`;
  return `<input type="${esc(f.type||'text')}" ${attrs} placeholder="${esc(f.placeholder||'')}" value="${esc(raw)}">`;
 }
 function draw(){
  const visibles=steps.length?steps[step].fields:fields;
  root.innerHTML=`<div class="modal-overlay"><section class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-head"><h2>${esc(title)}</h2><button class="btn small" type="button" data-close>✕</button></div><div class="modal-main">${steps.length?`<div class="stepper">${steps.map((s,i)=>`<span class="${i===step?'current':''}">${i+1}. ${esc(s.title)}</span>`).join('')}</div>`:''}${intro}<form id="${formId}" class="form-grid">${visibles.map(f=>`<label class="${f.wide?'wide':''}">${esc(f.label)}${control(f)}</label>`).join('')}</form></div><div class="modal-actions"><button class="btn" type="button" data-close>Cancel</button>${step?'<button class="btn" data-back>Back</button>':''}<button class="btn commit" data-next>${readOnly?'Close':steps.length&&step<steps.length-1?'Continue':esc(saveLabel)}</button></div></section></div>`;
  root.querySelectorAll('[data-close]').forEach(b=>b.onclick=closeModal);
  const back=root.querySelector('[data-back]');if(back)back.onclick=()=>{step--;draw()};
  root.querySelector('[data-next]').onclick=async()=>{
    if(readOnly){closeModal();return}
    const form=root.querySelector('form');if(!form.reportValidity())return;
    const data=Object.fromEntries([...new FormData(form)].filter(([,v])=>v!==''));
    for(const f of visibles){if(f.type==='number'&&data[f.name]!==undefined)data[f.name]=Number(data[f.name]);if(f.type==='checkbox')data[f.name]=Boolean(form.elements[f.name].checked)}
    Object.assign(answers,data);
    if(steps.length&&step<steps.length-1){step++;draw();return}
    const btn=root.querySelector('[data-next]');btn.disabled=true;btn.textContent='Saving…';
    try{await onSave(answers);closeModal();toast('Saved successfully')}catch(e){toast(e.message,true);btn.disabled=false;btn.textContent=saveLabel}
  };
  root.querySelector('form input, form select, form textarea')?.focus({preventScroll:true});
 }
 const answers={};draw();closeHandler=e=>{if(e.key==='Escape')closeModal()};document.addEventListener('keydown',closeHandler);
}
export const choice=(items)=>items.map(x=>({value:x.id,label:x.name||x.tag||x.code||x.title||`#${x.id}`}));

// When there is only one valid parent, show it as an already-selected value.
export function parentField(name,label,items,{required=true}={}){
 const values=choice(items);
 return values.length===1?{name,label,type:'fixed',value:values[0].value,display:values[0].label,required}:{name,label,type:'select',options:values,required};
}

// Variable-length, no-duplicate list input: for feed compositions and reusable mixes.
// Ingredient quantities are recipe reference quantities, not a stock transaction.
export function mixComposer({feeds=[],onSave}){
 closeModal();const root=document.querySelector('#modal-root');document.body.style.overflow='hidden';
 let lines=[{item_id:'',quantity_kg:''}];const close=()=>closeModal();
 function render(){
  const used=new Set(lines.map(l=>String(l.item_id)).filter(Boolean));
  const total=lines.reduce((n,l)=>n+(Number(l.quantity_kg)||0),0);
  root.innerHTML=`<div class="modal-overlay"><section class="modal" role="dialog" aria-modal="true" aria-label="Create feed mix"><div class="modal-head"><h2>Create feed mix</h2><button class="btn small" data-close type="button">✕</button></div><div class="modal-main"><form id="mix-composer" class="form-grid"><label>Mix name<input name="name" required maxlength="150" placeholder="e.g. Starter Mix A"></label><label>Feed stage<select name="feed_type" required>${['starter','grower','finisher','maintenance','lactation','other'].map(s=>`<option value="${s}">${s}</option>`).join('')}</select></label><div class="wide"><h3>Ingredients and quantities</h3><p class="muted">Enter each ingredient once. Total mix quantity and proportions calculate automatically.</p><div id="mix-lines">${lines.map((l,i)=>`<div class="mix-line"><select data-feed="${i}" aria-label="Ingredient ${i+1}" required><option value="">Select feed</option>${feeds.filter(f=>!used.has(String(f.id))||String(f.id)===String(l.item_id)).map(f=>`<option value="${f.id}" ${String(f.id)===String(l.item_id)?'selected':''}>${esc(f.name)}</option>`).join('')}</select><input data-quantity="${i}" type="number" min="0.001" step="0.001" required value="${esc(l.quantity_kg)}" placeholder="Quantity (kg)"/><button class="btn" type="button" data-remove="${i}" aria-label="Remove ingredient">Remove</button></div>`).join('')}</div><button type="button" class="btn" id="add-mix-line" ${used.size>=feeds.length?'disabled':''}>+ Add another feed</button><div class="mix-total"><strong>Total mix: <span id="mix-total">${total.toLocaleString(undefined,{maximumFractionDigits:3})}</span> kg</strong></div></div><label>Optional target per head/day (kg)<input name="kg_per_head_day" type="number" min="0.001" step="0.001" placeholder="Optional"></label></form></div><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn commit" id="save-mix">Save mix</button></div></section></div>`;
  root.querySelectorAll('[data-close]').forEach(b=>b.onclick=close);
  root.querySelectorAll('[data-feed]').forEach(s=>s.onchange=()=>{const i=+s.dataset.feed;const snapshot={name:root.querySelector('[name=name]').value,feed_type:root.querySelector('[name=feed_type]').value,kg:root.querySelector('[name=kg_per_head_day]').value};lines[i].item_id=s.value;render();preserve(snapshot)});
  root.querySelectorAll('[data-quantity]').forEach(s=>s.oninput=()=>{lines[+s.dataset.quantity].quantity_kg=s.value;root.querySelector('#mix-total').textContent=lines.reduce((n,l)=>n+(Number(l.quantity_kg)||0),0).toLocaleString(undefined,{maximumFractionDigits:3})});
  function preserve(v){root.querySelector('[name=name]').value=v.name;root.querySelector('[name=feed_type]').value=v.feed_type;root.querySelector('[name=kg_per_head_day]').value=v.kg}
  function snapshot(){return {name:root.querySelector('[name=name]').value,feed_type:root.querySelector('[name=feed_type]').value,kg:root.querySelector('[name=kg_per_head_day]').value}}
  root.querySelector('#add-mix-line').onclick=()=>{const v=snapshot();if(lines.length<feeds.length){lines.push({item_id:'',quantity_kg:''});render();preserve(v)}};
  root.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{const v=snapshot();if(lines.length>1){lines.splice(+b.dataset.remove,1);render();preserve(v)}});
  root.querySelector('#save-mix').onclick=async()=>{
   if(!root.querySelector('form').reportValidity())return;
   if(!lines.length||lines.some(x=>!x.item_id||!(Number(x.quantity_kg)>0))||new Set(lines.map(x=>x.item_id)).size!==lines.length){toast('Choose each feed once and enter a positive quantity',true);return}
   const d={name:root.querySelector('[name=name]').value.trim(),feed_type:root.querySelector('[name=feed_type]').value,lines:lines.map(x=>({item_id:+x.item_id,quantity_kg:+x.quantity_kg}))};
   const kg=root.querySelector('[name=kg_per_head_day]').value;if(kg)d.kg_per_head_day=+kg;
   const btn=root.querySelector('#save-mix');btn.disabled=true;
   try{await onSave(d);close();toast('Feed mix saved successfully')}catch(e){toast(e.message,true);btn.disabled=false}
  };
 }
 render();closeHandler=e=>{if(e.key==='Escape')close()};document.addEventListener('keydown',closeHandler);
}

// Each area is a standalone, full-width destination within its parent module.
// The MAIN application sidebar is the only sidebar. Forms stay in pop-up dialogs.
// Design option 1: short, icon-led cards rather than photography-led tiles.
// Visual submodule navigation ONLY on module home; each destination stays full-width.
const MODULE_ART={
 'Animal Fattening':['fattening','Animal operations','Manage ranches, feeding, weighing and sales'],
 'Livestock & Poultry':['livestock','Livestock operations','Manage herds, flocks, production and sales'],
 'Crop Farming':['crops','Crop production','Manage fields, planting, inputs and harvests'],
 'Gardening':['gardening','Garden operations','Manage gardens, landscaping and maintenance'],
 'Machinery':['machinery','Machinery operations','Manage equipment, usage and service records'],
 'Inventory':['inventory','Stock management','Register, receive and issue inventory items'],
 'Platform Administration':['platform','Platform administration','Organizations, subscriptions, usage and branding']
};
const MODULE_BANNER={
 overview:['WELCOME TO YOUR OPERATIONS','Manage your farm operations, track performance and make better decisions.'],
 fattening:['ANIMAL FATTENING • HEALTHY ANIMALS','Manage feeding, monitor weight gain and improve profitability.'],
 livestock:['HEALTHY ANIMALS • QUALITY PRODUCTS','Manage herds, flocks, breeding, health, production and sales.'],
 crops:['HEALTHY SOILS • PRODUCTIVE FIELDS','Plan, grow, manage inputs and harvest better crops.'],
 gardening:['GREEN SPACES • HEALTHY GARDENS','Plan, maintain and track your gardens and landscaped areas.'],
 machinery:['RELIABLE EQUIPMENT • HIGHER UPTIME','Manage equipment, maintenance, fuel and operating costs.'],
 inventory:['WELL STOCKED • WELL MANAGED','Track supplies, stock movements and available inventory.'],
 platform:['PLATFORM MANAGEMENT • SCALABLE GROWTH','Manage organizations, subscriptions, users and platform operations.']
};
export function photoHero(module,title,subtitle=''){
 const desc=MODULE_BANNER[module]||['CAPE RANCH','Manage your operational records'];
 return `<section class="photo-hero" style="--photo:url('/frontend/public/images/v65/${esc(module)}-hero.webp')"><span class="photo-hero-eyebrow">${esc(desc[0])}</span><h1>${esc(title)}</h1><p>${esc(subtitle||desc[1])}</p></section>`;
}
export function submoduleDirectory(moduleName,sections,counts={}){
 const [module]=MODULE_ART[moduleName]||['overview'];
 const photoLayout=['livestock','crops','gardening','machinery'].includes(module)?'photo-top':module==='fattening'?'photo-side':'icons-only';
 const title=moduleName==='Animal Fattening'?'Manage your fattening operations':moduleName==='Crop Farming'?'Grow productive crops':moduleName==='Inventory'?'Your inventory areas':`Manage ${moduleName.toLowerCase()}`;
 return `<section class="submodule-directory" data-kind="${esc(module)}" aria-label="${esc(moduleName)} areas">
 ${photoHero(module,moduleName)}
 ${module==='inventory'?'':`<div class="directory-title"><h2>${esc(title)}</h2><p>Choose a work area to manage its records and activities.</p></div>`}
 <div class="submodule-grid ${photoLayout}">${sections.map((s,i)=>{
  const photo=module==='inventory'||module==='platform'?'':`/frontend/public/images/v65/${module}/${esc(s.id)}.webp`;
  const count=counts[s.id];
  return `<button type="button" class="submodule-card" data-submodule="${esc(s.id)}" aria-label="Open ${esc(s.title)}">
  ${photo?`<img loading="lazy" decoding="async" class="submodule-photo" src="${photo}" alt="" onerror="this.src='/frontend/public/images/v65/${module}-hero.webp'">`:''}
  <span class="submodule-inner"><span class="submodule-icon" aria-hidden="true">${iconSvg(s.id,{size:24})}</span><span class="submodule-card-copy"><span class="submodule-name">${esc(s.title)}</span>${count!==undefined?`<span class="submodule-count">${esc(count)}</span>`:''}<span class="submodule-description">${esc(s.description||'Open records and actions')}</span></span><span class="submodule-arrow" aria-hidden="true">→</span></span>
 </button>`}).join('')}</div>
 </section>`;
}
export function recordsPreview(title,items,columns){return `<section class="panel record-preview"><div class="section-heading"><h2>${esc(title)}</h2><span class="muted">${(items||[]).length} records shown</span></div>${table((items||[]).slice(0,5),columns,{click:false,empty:'No records available yet.'})}</section>`}
export function submoduleWorkspace(moduleName,sections,current,content){
 const active=sections.find(x=>x.id===current);
 if(!active)return `<section class="submodule-content">${content}</section>`;
 return `<div class="submodule-page"><div class="submodule-breadcrumb"><button type="button" class="btn submodule-back" data-submodule-home aria-label="Back to ${esc(moduleName)} areas">← All ${esc(moduleName)} areas</button><span aria-hidden="true">/</span><strong>${esc(active.title)}</strong></div><section class="submodule-content" aria-label="${esc(active.title)}">${content}</section></div>`;
}
export function bindSubmodules(root,onSelect){
 root.querySelectorAll('[data-submodule]').forEach(el=>el.addEventListener('click',()=>onSelect(el.dataset.submodule)));
 root.querySelectorAll('[data-submodule-home]').forEach(el=>el.addEventListener('click',()=>onSelect(null)));
}
// Browser-addressable submodule destinations. Supports back/forward and direct links.
// Keep the URL in sync without introducing a second navigation bar.
const activeSubmodules=new Map();
export function rememberedSubmodule(module){
 const url=new URL(window.location.href);
 return url.searchParams.get('module')===module ? (url.searchParams.get('area')||null) : null;
}
export function rememberSubmodule(module,id){
 if(id)activeSubmodules.set(module,id);else activeSubmodules.delete(module);
 const url=new URL(window.location.href);
 url.searchParams.set('module',module);
 if(id)url.searchParams.set('area',id);else url.searchParams.delete('area');
 if(url.toString()!==window.location.href)window.history.pushState({module,area:id||null},'',url.pathname+url.search+url.hash);
 window.scrollTo({top:0,behavior:'instant'});
}
