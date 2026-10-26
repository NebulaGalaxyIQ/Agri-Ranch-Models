import {get,post,put} from '../../shared/api.js';
export const fatGet=path=>get('v6/fattening/'+path);
export const fatPost=(path,data)=>post('v6/fattening/'+path,data);
export const createMixByQuantity=data=>post('v6/feed/mixes/by-quantity',data);
export const collect=()=>Promise.all(['ranches','projects','batches','animals'].map(fatGet));
export const createRanch=d=>fatPost('ranches',d);export const createProject=d=>fatPost('projects',d);export const createBatch=d=>fatPost('batches',d);export const createAnimal=d=>fatPost('animals',d);

export const animalProfile=id=>get(`v6/fattening/animals/${Number(id)}/profile`);
export const fatteningOverview=()=>get('v6/fattening/overview');

// V7.1 read-only operational analytics and formatted mix details.
export const fatInsights=(area,currency='',animalId=null)=>{
 const params=new URLSearchParams();
 if(currency)params.set('currency',currency);
 if(area==='weighing'&&animalId!=null)params.set('animal_id',String(Number(animalId)));
 return fatGet(`insights/${encodeURIComponent(area)}${params.size?'?'+params.toString():''}`);
};
export const mixDetails=(id)=>fatGet(`mixes/${Number(id)}/details`);

// V7.6: independent project planning and accounting reconciliation.
export const projectDashboard=id=>fatGet(`projects/${Number(id)}/dashboard`);
export const saveProjectPlan=(id,data)=>put(`v6/fattening/projects/${Number(id)}/plan`,data);
export const saveProjectSection=(id,section,data,revision)=>put(`v6/fattening/projects/${Number(id)}/plan/section`,{section,data,revision});
export const approveProjectPlan=id=>fatPost(`projects/${Number(id)}/plan/approve`,{});
export const reviseProjectPlan=id=>fatPost(`projects/${Number(id)}/plan/revise`,{});
export const previewAnimalSale=(id,data)=>fatPost(`animals/${Number(id)}/sale/preview`,data);
