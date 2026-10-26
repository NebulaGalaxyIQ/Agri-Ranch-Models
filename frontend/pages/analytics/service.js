import {get,post,appState} from '../../shared/api.js';
const BASE='v10/reports';
export const catalog=()=>get(`${BASE}/catalog`);
export const filterSpec=id=>get(`${BASE}/filters?section_id=${encodeURIComponent(id)}`);
export const query=payload=>post(`${BASE}/query`,payload);
export const sourceDetail=(table,id)=>get(`${BASE}/source/${encodeURIComponent(table)}/${Number(id)}`);
export const saved=()=>get(`${BASE}/saved`);
export const saveReport=payload=>post(`${BASE}/saved`,payload);
export const recentRuns=()=>get(`${BASE}/runs`);
export async function exportReport(payload){
 const headers={'Content-Type':'application/json'};
 if(appState.org)headers['X-Organization-ID']=String(appState.org.id);
 const resp=await fetch('/api/v10/reports/export',{method:'POST',credentials:'same-origin',headers,body:JSON.stringify(payload)});
 if(!resp.ok){const err=await resp.json().catch(()=>({detail:`HTTP ${resp.status}`}));throw Error(typeof err.detail==='string'?err.detail:JSON.stringify(err.detail||err))}
 const content=resp.headers.get('content-disposition')||'';
 const found=content.match(/filename="([^"]+)"/);
 const filename=found?.[1]||`Cape_Ranch_Report.${payload.format}`;
 const blob=await resp.blob();const url=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),3000);return filename;
}
