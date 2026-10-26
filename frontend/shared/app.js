import {appState,request,get,post,esc,toast,safe} from './api.js';
import {head,button,panel,modalForm,tiles,kpis} from './ui.js';
import {iconSvg} from './icons.js';
import {renderAuthPage} from './auth-pages.js';
const MODULES=[
 {id:'fattening',title:'Animal Fattening',description:'Projects, batches, feeding, weighing and animal sales',rights:['projects.read','animals.read']},
 {id:'livestock',title:'Livestock & Poultry',description:'Herds, flocks, animal records and breeding',rights:['livestock.read']},
 {id:'crops',title:'Crop Farming',description:'Fields, planting, crop care and harvests',rights:['crops.read']},
 {id:'gardening',title:'Gardening',description:'Gardens, landscaping and scheduled care',rights:['gardening.read','routine.maintenance']},
 {id:'machinery',title:'Machinery',description:'Assets, maintenance, service and usage',rights:['machinery.read']},
 {id:'inventory',title:'Inventory',description:'Register items, receive stock and stock out',rights:['stock.read']},
];
const SHARED=[{id:'finance',title:'Finance',symbol:'▤',rights:['finance.read']},{id:'staff',title:'Employees & Tasks',symbol:'♧',rights:['tasks.manage','routine.read']},{id:'analytics',title:'Analytics & Reports',symbol:'▥',rights:['analytics.read']},{id:'subscription',title:'Subscription & Licensing',symbol:'▣',rights:[]}];
const OWNER=[{id:'platform',label:'Organizations & Licensing',symbol:'▦'},{id:'platform',label:'Platform Dashboard',symbol:'◫'},{id:'platform',label:'Branding & Settings',symbol:'◈'}];
const icons={overview:'⌂',fattening:'♧',livestock:'♜',crops:'❀',gardening:'✿',machinery:'⚙',inventory:'▣',finance:'▤',staff:'♙',analytics:'▥',subscription:'▣',platform:'▦'};
let routeGeneration=0;
const root=document.querySelector('#app');
const access=perm=>appState.org?.role==='org_admin'||appState.org?.role==='manager'||appState.permissions.includes(perm);
const enabled=m=>appState.modules.find(x=>x.name===m)?.enabled!==false;
function available(){return MODULES.filter(m=>enabled(m.id)&&m.rights.some(access))}
function nav(){const owner=appState.user?.role==='platform_owner';const basic=owner?['platform']:['overview',...available().map(m=>m.id),...SHARED.filter(m=>m.id==='staff'||m.id==='subscription'||m.rights.some(access)).map(m=>m.id)];
 const names={overview:'Dashboard',...Object.fromEntries([...MODULES,...SHARED].map(x=>[x.id,x.title])),platform:'Platform Administration'};
 return `<aside class="sidebar" id="sidebar"><div class="cape-sidebar-header"><div class="brand"><div class="brand-icon" aria-hidden="true"><img src="/frontend/public/images/branding/cape-ranch-mark.png" alt=""/></div><div class="brand-name">Cape Ranch<small>RANCHING PLATFORM</small></div></div><div class="cape-sidebar-controls"><span class="cape-menu-caption">MENU</span><button type="button" class="sidebar-toggle" id="menu" aria-label="Expand or collapse navigation" aria-expanded="true" title="Expand or collapse menu">☰</button></div></div>${owner?'<div class="nav-label">PLATFORM MANAGEMENT</div>':'<div class="nav-label">WORKSPACE</div>'}${basic.map(id=>`${id==='finance'?'<div class="nav-label">SHARED SERVICES</div>':''}<button class="nav-link ${appState.page===id?'active':''}" data-page="${id}" title="${esc(names[id])}"><span class="nav-ico">${iconSvg(id,{size:17})}</span><span class="nav-text">${esc(names[id])}</span></button>`).join('')}<div class="nav-bottom"><button id="logout" class="nav-link" title="Sign out"><span class="nav-ico">↪</span><span class="nav-text">Sign out</span></button></div></aside>`}
function shell(){const owner=appState.user?.role==='platform_owner';return `<div class="app-shell" id="app-shell">${nav()}<div class="main-area"><button type="button" class="sidebar-drawer-trigger" id="mobile-menu" aria-label="Open navigation">☰</button><header class="topbar"><div class="topbar-left">${owner?'<strong>Platform Owner</strong>':`<select id="org-select">${appState.orgs.map(o=>`<option value="${o.id}" ${appState.org?.id===o.id?'selected':''}>${esc(o.name)}</option>`).join('')}</select>`}<span class="muted">/ ${esc(appState.page)}</span></div><div class="topbar-right"><label class="topbar-search"><svg width="15" height="15" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></svg><input id="page-search" aria-label="Search current page" placeholder="Search current page…" autocomplete="off"></label><span class="avatar">${esc(appState.user?.full_name?.charAt(0)||'U')}</span><span>${esc(appState.user?.full_name||'')}</span></div></header><main class="content" id="main-content"></main></div></div>`}
function loginPage(){renderAuthPage(root,{onAuthenticated:async()=>initialize(true)})}
async function initialize(authenticated=false){try{
  const data=await get('auth/me');appState.user=data.user;
  if(data.user.role!=='platform_owner'){
    appState.orgs=(await get('v5/organizations')).items||[];
    appState.org=appState.orgs[0]||null;
    if(appState.org){const [accessResult,mods]=await Promise.all([safe(()=>get('v5/access'),{permissions:[]}),safe(()=>get('v6/modules'),{items:[]})]);appState.permissions=accessResult.permissions||[];appState.modules=mods.items||[]}
    appState.subscription=appState.org?await safe(()=>get('cape/subscription/status'),{active:false}):{active:false};
    appState.page=appState.subscription.active?((appState.org?.role==='org_admin'||appState.org?.role==='manager')?'overview':'staff'):'subscription';
    const requested=new URLSearchParams(window.location.search).get('module');
    if(requested&&(['overview','staff',...available().map(x=>x.id),...SHARED.filter(m=>m.id==='staff'||m.id==='subscription'||m.rights.some(access)).map(m=>m.id)].includes(requested)) && (appState.subscription.active || requested==='subscription'))appState.page=requested;
  }else appState.page='platform';
  root.innerHTML=shell();wireShell();await go(appState.page,{restore:true});
 }catch(e){loginPage()}}
function wireShell(){document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>go(b.dataset.page));document.getElementById('menu')?.addEventListener('click',()=>{const shell=document.getElementById('app-shell');if(matchMedia('(max-width:710px)').matches){document.getElementById('sidebar').classList.remove('open')}else shell.classList.toggle('is-collapsed');document.getElementById('menu').setAttribute('aria-expanded',String(!shell.classList.contains('is-collapsed')))});
 document.getElementById('mobile-menu')?.addEventListener('click',()=>document.getElementById('sidebar').classList.add('open'));
 document.getElementById('page-search')?.addEventListener('input',e=>{const value=e.target.value.trim().toLowerCase();document.querySelectorAll('#main-content .submodule-card, #main-content .module-card, #main-content .data-table tbody tr').forEach(row=>{row.hidden=Boolean(value)&&!row.textContent.toLowerCase().includes(value)});});
 document.getElementById('logout').onclick=async()=>{await request('auth/logout',{method:'POST'}).catch(()=>{});appState.user=null;appState.org=null;loginPage()};
 document.getElementById('org-select')?.addEventListener('change',async e=>{appState.org=appState.orgs.find(x=>String(x.id)===e.target.value);const [a,m]=await Promise.all([safe(()=>get('v5/access'),{permissions:[]}),safe(()=>get('v6/modules'),{items:[]})]);appState.permissions=a.permissions||[];appState.modules=m.items||[];appState.subscription=await safe(()=>get('cape/subscription/status'),{active:false});appState.page=appState.subscription.active?'overview':'subscription';root.innerHTML=shell();wireShell();await go(appState.page)})}
async function go(name,{restore=false}={}){const isOwner=appState.user?.role==='platform_owner';if(isOwner&&name!=='platform')name='platform';if(!isOwner&&!appState.subscription?.active)name='subscription';
 if(!isOwner&&name!=='overview'&&name!=='staff'&&name!=='subscription'&&![...available().map(m=>m.id),...SHARED.filter(m=>m.id==='staff'||m.id==='subscription'||m.rights.some(access)).map(m=>m.id)].includes(name)){toast('This module is not enabled for your role or organization',true);return}
 // Main sidebar navigation opens the module directory, never a second sidebar.
 if(!restore){const url=new URL(window.location.href);url.searchParams.set('module',name);url.searchParams.delete('area');if(url.toString()!==window.location.href)history.pushState({module:name,area:null},'',url.pathname+url.search+url.hash)}
 appState.page=name;const gen=++routeGeneration;document.querySelectorAll('[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===name));document.getElementById('sidebar')?.classList.remove('open');const node=document.getElementById('main-content');node.innerHTML='<div class="panel">Loading module…</div>';
 try{const oldStyle=document.getElementById('module-css');if(oldStyle)oldStyle.remove();const css=document.createElement('link');css.id='module-css';css.rel='stylesheet';css.href=`/frontend/pages/${name}/style.css?v=${name==='crops'?'9.0.1':(name==='livestock'?'8.3.0':(name==='fattening'?'7.8.0':'7.6.0'))}`;if(name==='analytics')css.href='/frontend/pages/analytics/style.css?v=reports-catalog-fix-20261026';document.head.appendChild(css);const mod=await import(name==='analytics'?'/frontend/pages/analytics/index.js?v=reports-catalog-fix-20261026':`/frontend/pages/${name}/index.js?v=${name==='crops'?'9.0.1':(name==='livestock'?'8.3.0':(name==='fattening'?'7.8.0':'7.6.0'))}`);if(gen===routeGeneration){node.innerHTML='';await mod.render(node,{navigate:go,modules:available(),state:appState});}}catch(err){if(gen===routeGeneration)node.innerHTML=panel('Unable to display module',`<p class="error-text">${esc(err.message)}</p>`)}window.scrollTo({top:0,behavior:'instant'})}
window.addEventListener('popstate',()=>{
 if(!appState.user)return;
 const url=new URL(window.location.href);
 const requested=url.searchParams.get('module');
 const page=appState.user?.role==='platform_owner'?'platform':requested||((appState.org?.role==='org_admin'||appState.org?.role==='manager')?'overview':'staff');
 go(page,{restore:true});
});
export {go,available};initialize();
