export const appState={user:null,org:null,orgs:[],permissions:[],modules:[],subscription:null,page:'overview'};
export async function request(endpoint,{method='GET',body=null,formData=null,platform=false}={}){
  const headers={};if(!platform&&appState.org)headers['X-Organization-ID']=String(appState.org.id);
  if(body!==null)headers['Content-Type']='application/json';
  const res=await fetch(endpoint.startsWith('/api/')?endpoint:`/api/${endpoint}`,{method,credentials:'same-origin',headers,body:formData|| (body!==null?JSON.stringify(body):undefined)});
  if(!res.ok){const e=await res.json().catch(()=>({detail:`HTTP ${res.status}`}));
    let msg=typeof e.detail==='string'?e.detail:Array.isArray(e.detail)?e.detail.map(x=>`${x.loc?.at(-1)||'Field'}: ${x.msg}`).join('; '):JSON.stringify(e.detail||e);
    throw Error(msg)}
  const type=res.headers.get('content-type')||'';
  if(type.includes('json'))return res.json();return res;
}
export const get=url=>request(url);
export const post=(url,body)=>request(url,{method:'POST',body});
export const patch=(url,body)=>request(url,{method:'PATCH',body});
export const put=(url,body)=>request(url,{method:'PUT',body});
export const esc=value=>String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
export const dateString=value=>value?new Date(value).toLocaleDateString():'—';
export const number=value=>Number(value||0).toLocaleString();
export function can(permission){const role=appState.org?.role;return role==='org_admin'||role==='manager'||appState.permissions.includes(permission)}
export function toast(msg,isError=false){const e=document.querySelector('#toast');e.textContent=msg;e.className=isError?'toast error':'toast';setTimeout(()=>e.className='',4600)}
export async function safe(getter,fallback={items:[]}){try{return await getter()}catch(e){console.warn(e.message);return fallback}}
