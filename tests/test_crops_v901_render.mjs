// Headless render-contract regression: all 21 Crop Farming pages must contain
// their actual content and must not expose the literal "undefined".
// Uses actual shared UI and the actual Crop Farming ES module, no browser install.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const schema = readFileSync(path.join(root, 'backend/modules/crops/schemas.py'), 'utf8');
const found = [...schema.matchAll(/\{'id':'([^']+)','title':'([^']+)','description':'([^']+)'/g)]
    .filter(x => x[1] !== 'trial_observations')
    .map(x => ({id:x[1], title:x[2], description:x[3], fields:[]}));
assert.equal(found.length, 21, 'Expected 21 registered crop sections');
const storage = new Map();
globalThis.sessionStorage = {getItem:k=>storage.get(k)??null, setItem:(k,v)=>storage.set(k,String(v))};
globalThis.window = {location:{href:'http://localhost:8000/?module=crops',pathname:'/',search:'?module=crops',hash:''},
 history:{pushState(_state,_unused,url){const u=new URL(url,'http://localhost:8000');window.location={href:u.href,pathname:u.pathname,search:u.search,hash:u.hash};}},
 scrollTo(){}};
globalThis.document={querySelector:()=>null};
const sample = {
 projects:[{id:1,ranch_id:1,code:'C-01',name:'Maize crop project',method:'irrigated',season:'2026',status:'active'}],
 fields:[{id:10,ranch_id:1,name:'East Field',area_ha:12,soil_type:'loam',irrigation:'drip'}],
 units:[{id:20,field_id:10,name:'East Block',area_ha:6,kind:'block',status:'available'}],
 varieties:[{id:30,name:'Maize',variety:'Hybrid A',category:'cereal',days_to_maturity:110}],
 cycles:[{id:40,project_id:1,unit_id:20,variety_id:30,planted_area_ha:5,planted_on:'2026-09-01',status:'growing'}],
 budgets:[{id:50,project_id:1,description:'Seed',category:'seed',quantity:10,amount:100,currency:'USD',status:'approved'}],
 routine:[{id:60,project_id:1,title:'Inspect maize',frequency:'daily',shift:'morning',start_date:'2026-09-01'}],
 completions:[{id:61,routine_id:60,day:'2026-10-25',status:'completed',actual_quantity:1,amount:0}],
 trials:[{id:70,project_id:1,cycle_id:40,title:'Fertilizer trial',design:'rcbd',replications:4,status:'active'}],
 plots:[{id:71,trial_id:70,unit_id:20,code:'A-1',treatment:'Control',replicate:1,area_ha:0.1}],
 harvest:[{id:80,project_id:1,batch_ref:'HAR-01',grade:'A',marketable_kg:100,available_kg:80,harvested_on:'2026-10-20'}],
 sales:[{id:90,project_id:1,buyer:'Buyer A',quantity_kg:20,gross:40,currency:'USD',sold_on:'2026-10-23'}],
 stock:[{id:91,lot_id:80,action:'loss',quantity_kg:1,reference:'LOSS01'}],
 records: found.map((x,i)=>({id:i+1,section:x.id,project_id:1,cycle_id:40,unit_id:20,title:`${x.title} entry`,performed_on:'2026-10-24',quantity:1,unit:'kg',currency:'USD',other_cost:1,data:{trait:'Height',value:15,measurement_unit:'cm'}})),
 analytics:[{project_id:1,project:'Maize crop project',harvested_marketable_kg:100,sold_kg:20,currencies:[{currency:'USD',recorded_cost:150,sales_revenue:40,approved_budget:500,recorded_contribution:-110}]}]
};
const empty=Object.fromEntries(Object.keys(sample).map(k=>[k,[]]));
const metadata={sections:found,organization_id:1};
let testData=empty;
globalThis.fetch=async url=>{
  const key=String(url);
  let value;
  if(key.endsWith('/api/v9/crops/meta'))value=metadata;
  else if(key.endsWith('/api/v9/crops/workspace'))value=testData;
  else if(key.includes('/api/v9/crops/routines/due?'))value={items:testData.routine.map(r=>({...r,check:null}))};
  else if(key.endsWith('/api/v5/ranches'))value={items:[{id:1,name:'Farm A'}]};
  else throw Error('Unexpected API request: '+key);
  return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>value};
};
const {appState}=await import('../frontend/shared/api.js');
appState.org={id:1,role:'org_admin'};
const {render}=await import('../frontend/pages/crops/index.js');
class RenderTarget {
  constructor(){this.innerHTML='';}
  querySelector(){return null;}
  querySelectorAll(){return [];}
}
let checked=0;
for(const [mode,data] of [['empty',empty],['populated',sample]]){
  testData=data;
  for(const section of found){
    const href=`http://localhost:8000/?module=crops&area=${section.id}`;
    const u=new URL(href);window.location={href:u.href,pathname:u.pathname,search:u.search,hash:u.hash};
    const target=new RenderTarget();
    await render(target);
    assert.ok(target.innerHTML.includes(`data-submodule-home`),`No return navigation in ${section.id} (${mode})`);
    assert.ok(target.innerHTML.includes('cv9-workspace'),`Missing section body in ${section.id} (${mode})`);
    assert.ok(target.innerHTML.includes(section.title.replaceAll('&','&amp;')),`Missing heading in ${section.id} (${mode})`);
    assert.ok(!target.innerHTML.includes('>undefined<')&&!target.innerHTML.includes('>undefined'),`Undefined appears in ${section.id} (${mode})`);
    assert.ok(!target.innerHTML.includes('Unable to load crop records'),`Backend error view in ${section.id} (${mode})`);
    checked++;
  }
  // Directory must have 21 photographic cards and usable metrics.
  const u=new URL('http://localhost:8000/?module=crops');window.location={href:u.href,pathname:u.pathname,search:u.search,hash:u.hash};
  const target=new RenderTarget();await render(target);
  assert.equal((target.innerHTML.match(/data-submodule="/g)||[]).length,21,`Missing section cards in ${mode}`);
  assert.ok(target.innerHTML.includes('Crop Farming'),`Missing directory in ${mode}`);
}
console.log(`PASS: ${checked} section renders (21 sections x 2 data states), plus 2 module directories`);
