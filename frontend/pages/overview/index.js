import {get,safe,number,can,appState,request,toast} from '../../shared/api.js';
import {head,tiles,kpis,panel,barChart,button,modalForm,photoHero} from '../../shared/ui.js';

export async function render(el,{navigate,modules}){
 const [v6,summary,inventory]=await Promise.all([
   safe(()=>get('v6/overview'),{}),safe(()=>get('v5/reports/summary'),{}),safe(()=>get('v5/stock/status'),{})]);
 const assets=(inventory?.items||[]).length;
 el.innerHTML=photoHero('overview',`Good day — welcome to ${appState.org?.name||'your organization'}`,'Manage farm operations, monitor performance and keep your teams organized.')+
 kpis([{label:'Active fattening animals',value:number(summary.active_animals),icon:'fattening'},{label:'General livestock',value:number(v6.general_animals),icon:'livestock'},{label:'Crop fields',value:number(v6.fields),icon:'crops'},{label:'Machinery assets',value:number(v6.machinery),icon:'machinery'}])+
 `<div class="home-section">${head('Your operational modules','Choose a module to manage your farm activities.',appState.org?.role==='org_admin'?button('Upload organization logo','org-logo','commit'):'')}</div>`+
 tiles(modules)+`<div class="grid two home-summary">${panel('Operations at a glance',barChart([{label:'Animals',value:summary.active_animals||0},{label:'Projects',value:summary.project_count||0},{label:'Fields',value:v6.fields||0},{label:'Machines',value:v6.machinery||0}]))}${panel('Available operational records',`<div class="overview-record-list"><p><strong>${number(summary.active_animals||0)}</strong> active fattening animals</p><p><strong>${number(v6.crop_cycles||0)}</strong> crop cycles</p><p><strong>${number(v6.gardens||0)}</strong> garden areas</p><p><strong>${number(assets)}</strong> registered stock items</p></div>`)}</div>`;
 el.querySelector('#org-logo')?.addEventListener('click',()=>modalForm({title:'Upload organization logo',fields:[{name:'logo',label:'Choose JPG, PNG or WebP',type:'file',required:true}],saveLabel:'Save organization logo',onSave:async ()=>{const file=document.querySelector('#modal-root input[type=file]')?.files?.[0];if(!file)throw Error('Select an image');const formData=new FormData();formData.append('file',file);await request('v6/organizations/me/logo',{method:'POST',formData});toast('Organization logo saved')}}));
 el.querySelectorAll('[data-module]').forEach(x=>{const navigateTo=()=>navigate(x.dataset.module);x.addEventListener('click',navigateTo);x.addEventListener('keydown',e=>{if(e.key==='Enter')navigateTo()})});
}
