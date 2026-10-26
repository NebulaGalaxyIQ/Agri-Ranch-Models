import {get,can,safe,number,esc} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,listenRows,parentField,submoduleDirectory,recordsPreview,submoduleWorkspace,bindSubmodules,rememberedSubmodule,rememberSubmodule} from '../../shared/ui.js';
import {areas,records,createArea,createRecord} from './service.js';
const today=()=>new Date().toISOString().slice(0,10);
const sections=[
 {id:'areas',title:'Garden areas',description:'Manage garden beds, plots and locations'},
 {id:'planting',title:'Planting',description:'Record planting and garden development'},
 {id:'watering',title:'Watering',description:'Complete watering activities'},
 {id:'weeding',title:'Weeding',description:'Record completed weeding'},
 {id:'pruning',title:'Pruning',description:'Track pruning and plant care'},
 {id:'landscaping',title:'Landscaping',description:'Maintain garden and landscaped spaces'},
 {id:'supplies',title:'Supplies',description:'Check gardening and cleaning supplies'},
 {id:'schedule',title:'Schedule & tasks',description:'Assigned garden activities and history'},
];
const ACTIVITY_TYPES=['planting','watering','weeding','pruning','landscaping'];
export async function render(root){
 const [ar,logs,rr,stock,tasks]=await Promise.all([areas(),records(),get('v5/ranches'),safe(()=>get('v5/stock/status')),safe(()=>get('v5/tasks'))]);
 const items=ar.items||[],events=logs.items||[],ranches=rr.items||[],inventory=stock.items||[],taskList=tasks.items||[];
 let section=rememberedSubmodule('gardening');const editable=can('gardening.write');
 if(section&&!sections.some(x=>x.id===section))section=null;
 const gardens=events.filter(x=>ACTIVITY_TYPES.includes(x.action));
 function draw(){
  const counts={areas:items.length,schedule:taskList.length,supplies:inventory.filter(x=>['gardening_tool','seed','fertilizer','cleaning_supply'].includes(x.category)).length};
  for(const type of ACTIVITY_TYPES)counts[type]=events.filter(x=>x.action===type).length;
  if(!section){
   root.innerHTML=submoduleDirectory('Gardening',sections,counts)+
    `<div class="submodule-overview-metrics">${kpis([{label:'Garden areas',value:items.length,icon:'gardening'},{label:'Recorded activities',value:events.length,icon:'records'},{label:'Watering records',value:counts.watering,icon:'watering'},{label:'Assigned tasks',value:taskList.length,icon:'calendar'}])}</div>`+
    `<div class="module-previews">${recordsPreview('Recent gardening activities',events.slice(0,6),[['action','Activity'],['performed_on','Date'],['observations','Observations']])}${recordsPreview('Garden areas',items.slice(0,5),[['name','Area'],['type','Purpose'],['area_m2','Size (m²)']])}</div>`;
  }else{
   const mode=section;
   const isArea=mode==='areas',isSupplies=mode==='supplies',isSchedule=mode==='schedule';
   const source=isArea?items:isSupplies?inventory.filter(x=>['gardening_tool','seed','fertilizer','cleaning_supply'].includes(x.category)):isSchedule?taskList.filter(x=>['gardening','gardener','garden'].some(w=>String(x.category||x.title||'').toLowerCase().includes(w))):events.filter(x=>x.action===mode);
   const cols=isArea?[['name','Garden area'],['type','Purpose'],['area_m2','Area (m²)'],['notes','Notes']]:isSupplies?[['name','Item'],['category','Type'],['usable_balance','Available'],['unit','Unit']]:isSchedule?[['title','Task'],['assigned_to','Assigned employee'],['due_date','Due date'],['status','Status']]:[['action','Activity'],['area_id','Garden area'],['performed_on','Date'],['observations','Observation']];
   const intro=isSupplies?'<p class="notice">Garden supplies are managed centrally in Inventory. Only stock visible to your role appears here.</p>':isSchedule?'<p class="notice">Tasks are assigned by authorized management. Completed garden records remain in their activity areas.</p>':'';
   root.innerHTML=head(sections.find(s=>s.id===mode)?.title||'Gardening','Gardening records and operations',editable&&!isSupplies&&!isSchedule?button(isArea?'Add garden area':`Record ${mode}`,'add','commit'):'')+
    submoduleWorkspace('Gardening',sections,mode,intro+table(source,cols,{empty:'No records for this area yet.'}));
   listenRows(root,source,x=>detailModal(x));
   root.querySelector('#add')?.addEventListener('click',openForm);
  }
  bindSubmodules(root,id=>{section=id;rememberSubmodule('gardening',id);draw()});
 }
 function openForm(){
  const isArea=section==='areas';if(isArea&&!ranches.length){alert('Register a ranch first.');return}
  if(!isArea&&!items.length){alert('Create a garden area first.');return}
  const fields=isArea?[parentField('ranch_id','Ranch',ranches),
   {name:'name',label:'Garden area',required:true},{name:'type',label:'Purpose',type:'select',options:['landscaping','flower_beds','vegetables','lawn','trees','other']},
   {name:'area_m2',label:'Area (m²)',type:'number',min:'.01',step:'.01'},{name:'notes',label:'Notes',type:'textarea',wide:true}]:[
   parentField('area_id','Garden area',items),{name:'action',label:'Activity',type:'fixed',value:section,display:sections.find(s=>s.id===section)?.title,required:true},
   {name:'performed_on',label:'Date completed',type:'date',value:today(),required:true},
   {name:'observations',label:'Observation',type:'textarea',wide:true}];
  modalForm({title:isArea?'Register garden area':`Record ${section}`,fields,saveLabel:isArea?'Save area':'Complete activity',onSave:async d=>{
   if(d.ranch_id)d.ranch_id=+d.ranch_id;if(d.area_id)d.area_id=+d.area_id;
   await(isArea?createArea(d):createRecord(d));await render(root);
  }});
 }
 draw();
}
