import {get,can,safe,esc,number} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,listenRows,parentField,submoduleDirectory,recordsPreview,submoduleWorkspace,bindSubmodules,rememberedSubmodule,rememberSubmodule} from '../../shared/ui.js';
import {assets,records,createAsset,createRecord} from './service.js';
const today=()=>new Date().toISOString().slice(0,10);
const sections=[
 {id:'assets',title:'Assets',description:'Register and manage farm equipment'},
 {id:'maintenance',title:'Maintenance',description:'Repairs and preventive maintenance'},
 {id:'service',title:'Service schedule',description:'Inspections and service history'},
 {id:'operators',title:'Operators',description:'Recorded machine operations'},
 {id:'fuel',title:'Fuel & usage',description:'Fuel transactions and operating hours'},
 {id:'parts',title:'Spare parts',description:'Spare parts available in Inventory'},
 {id:'breakdowns',title:'Breakdowns',description:'Machine faults and recorded repairs'},
 {id:'costs',title:'Cost & performance',description:'Operating expenses by recorded currency'},
];
const modeActions={maintenance:['maintenance','repair'],service:['inspection'],operators:['operation'],fuel:['fuel','operation'],breakdowns:['breakdown','repair']};
export async function render(root){
 const [ar,rr,rawRanches,st]=await Promise.all([assets(),records(),get('v5/ranches'),safe(()=>get('v5/stock/status'))]);
 const machines=ar.items||[],logs=rr.items||[],ranches=rawRanches.items||[],inventory=st.items||[];
 let section=rememberedSubmodule('machinery');const writable=can('machinery.write');
 if(section&&!sections.some(x=>x.id===section))section=null;
 function selected(){return logs.filter(x=>(modeActions[section]||[]).includes(x.action))}
 function draw(){
  const counts={assets:machines.length,parts:inventory.filter(x=>x.category==='maintenance_part').length,costs:logs.length};
  for(const [type,actions] of Object.entries(modeActions))counts[type]=logs.filter(x=>actions.includes(x.action)).length;
  if(!section){
   root.innerHTML=submoduleDirectory('Machinery',sections,counts)+
    `<div class="submodule-overview-metrics">${kpis([{label:'Equipment',value:machines.length,icon:'machinery'},{label:'Maintenance records',value:counts.maintenance,icon:'maintenance'},{label:'Recorded hours',value:number(logs.reduce((n,x)=>n+(+x.meter_hours||0),0)),icon:'calendar'},{label:'Operating records',value:logs.length,icon:'records'}])}</div>`+
    `<div class="module-previews">${recordsPreview('Equipment overview',machines.slice(0,5),[['name','Equipment'],['model','Model'],['status','Status']])}${recordsPreview('Service & usage records',logs.slice(0,5),[['action','Activity'],['performed_on','Date'],['meter_hours','Hours'],['expense','Cost']])}</div>`;
  }else{
   const isAsset=section==='assets',isPart=section==='parts',isCost=section==='costs';
   const rows=isAsset?machines:isPart?inventory.filter(x=>x.category==='maintenance_part'):isCost?logs:selected();
   const cols=isAsset?[['asset_code','Code'],['name','Machine'],['category','Type'],['model','Model'],['status','Status']]:isPart?[['name','Spare part'],['usable_balance','Available'],['unit','Unit'],['reorder','Reorder']]:[['machine_id','Machine'],['action','Activity'],['performed_on','Date'],['meter_hours','Hours'],['expense','Cost'],['currency','Currency']];
   const spending={};for(const record of logs){const cur=record.currency||'TZS';spending[cur]=(spending[cur]||0)+Number(record.expense||0)}
   const summary=isCost?`<div class="machinery-cost-summary">${Object.entries(spending).map(([cur,val])=>`<div class="panel"><span class="muted">Recorded cost · ${esc(cur)}</span><strong>${number(val)}</strong></div>`).join('')||'<p class="muted">No operating costs recorded yet.</p>'}</div><p class="muted">Different currencies are reported separately until a verified exchange rate is available.</p>`:isPart?'<p class="notice">Spare parts are received and issued in the shared Inventory module. This view does not duplicate stock transactions.</p>':'';
   root.innerHTML=head(sections.find(s=>s.id===section)?.title||'Machinery','Equipment and service records',writable&&!isPart&&!isCost?button(isAsset?'Register equipment':`Record ${section}`,'add','commit'):'')+
    submoduleWorkspace('Machinery',sections,section,summary+table(rows,cols,{empty:'No records in this area yet.'}));
   listenRows(root,rows,x=>detailModal(x));root.querySelector('#add')?.addEventListener('click',openForm);
  }
  bindSubmodules(root,id=>{section=id;rememberSubmodule('machinery',id);draw()});
 }
 function openForm(){
  const isAsset=section==='assets';
  if(isAsset&&!ranches.length){alert('Create a ranch first.');return}
  if(!isAsset&&!machines.length){alert('Register equipment first.');return}
  const actions=modeActions[section]||['operation'];
  const fields=isAsset?[parentField('ranch_id','Ranch',ranches),
    {name:'asset_code',label:'Equipment reference',required:true},{name:'name',label:'Equipment name',required:true},
    {name:'category',label:'Type',type:'select',options:['tractor','truck','generator','water_pump','sprayer','harvester','machinery','other']},
    {name:'model',label:'Model'},{name:'serial_number',label:'Serial number'},{name:'acquired_on',label:'Acquisition date',type:'date'}]:[
    parentField('machine_id','Equipment',machines),
    {name:'action',label:'Work performed',type:actions.length===1?'fixed':'select',value:actions.length===1?actions[0]:undefined,display:actions[0],options:actions,required:true},
    {name:'performed_on',label:'Date',type:'date',value:today(),required:true},
    {name:'meter_hours',label:'Operating hours (optional)',type:'number',step:'.01',min:0},
    {name:'expense',label:'Direct cost',type:'number',step:'.01',min:0,value:0},
    {name:'currency',label:'Currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'},
    {name:'notes',label:'Observation',type:'textarea',wide:true}];
  modalForm({title:isAsset?'Register equipment':`Record ${section}`,fields,saveLabel:isAsset?'Save equipment':'Complete record',onSave:async d=>{
   if(d.ranch_id)d.ranch_id=+d.ranch_id;if(d.machine_id)d.machine_id=+d.machine_id;
   await(isAsset?createAsset(d):createRecord(d));await render(root);
  }});
 }
 draw();
}
