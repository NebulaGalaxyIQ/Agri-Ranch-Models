import {get,post,esc,toast} from './api.js';
const pagePath={login:'/',register:'/register-organization',reset:'/staff-recovery',setup:'/first-time-setup'};
export const authRoute=()=>Object.entries(pagePath).find(([key,path])=>key!=='login'&&location.pathname.replace(/\/$/,'')===path)?.[0]||'login';
const field=(name,title,{type='text',required=false,wide=false,placeholder='',min=undefined,options=undefined,minlength=undefined}={})=>
 `<label class="${wide?'wide':''}">${esc(title)}${options?`<select name="${name}" ${required?'required':''}>${options.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select>`:
 `<input name="${name}" type="${type}" ${required?'required':''} ${min!==undefined?`min="${min}"`:''} ${minlength!==undefined?`minlength="${minlength}"`:''} placeholder="${esc(placeholder)}">`}</label>`;
const registrationFields=`
 <div class="auth-section-title">01 · Organization identity</div>
 ${field('name','Legal registered name',{required:true,wide:true})}${field('trading_name','Trading name')}${field('legal_entity_type','Legal entity type',{required:true,options:['Company','Partnership','Cooperative','Sole proprietor','Nonprofit','Government institution','Research institution','Other']})}
 ${field('registration_number','Registration number')}${field('tax_number','Tax identification number')}${field('incorporation_date','Incorporation date',{type:'date'})}
 ${field('email','Official organization email',{type:'email',required:true})}${field('billing_email','Billing email',{type:'email'})}${field('phone','Business phone',{required:true})}${field('website','Website (optional)',{type:'url'})}
 <div class="auth-section-title">02 · Locations and operations</div>
 ${field('country','Country',{required:true,placeholder:'e.g. Kenya, Brazil, Australia'})}${field('state_province','State / Province')}${field('region','Region')}${field('district','District')}${field('city','City / Town')}${field('postal_code','Postal code')}${field('address','Physical address',{required:true,wide:true})}
 ${field('operational_countries','Other countries where you operate',{wide:true,placeholder:'Comma-separated, if applicable'})}
 ${field('industry_sectors','Agricultural sectors',{required:true,wide:true,placeholder:'Livestock, Poultry, Crop Farming, Processing...'})}
 <label class="wide">Activities and services provided<textarea name="operations_description" required minlength="15" placeholder="Describe your organization, crops, livestock, agricultural services and production methods"></textarea></label>
 ${field('production_focus','Main products / species / crops',{wide:true})}
 ${field('employee_count','Current number of employees',{type:'number',min:1,required:true})}${field('expected_system_users','Expected users of Cape Ranch',{type:'number',min:1,required:true})}
 ${field('farms_count','Number of farms / facilities',{type:'number',min:0,required:true})}${field('total_land_hectares','Total land area (hectares, optional)',{type:'number',min:0})}
 ${field('preferred_currency','Reporting currency (ISO code)',{required:true,placeholder:'USD'})}${field('timezone','Time zone (IANA)',{required:true,placeholder:'Africa/Nairobi, Europe/London'})}
 <div class="auth-section-title">03 · Authorized contact</div>
 ${field('contact_person','Primary contact person',{required:true})}${field('contact_position','Job title')}${field('contact_phone','Direct telephone')}
 <div class="auth-section-title">04 · Organization administrator</div>
 ${field('admin_name','Administrator full name',{required:true})}${field('admin_email','Administrator email',{type:'email',required:true})}
 ${field('admin_password','Administrator password (10+ characters)',{type:'password',required:true,minlength:10,wide:true})}
 <p class="auth-helper wide">Registration creates an organization awaiting review. Subscription activation is a separate step; registration alone does not grant operational access.</p>`;
export function renderAuthPage(root,{onAuthenticated}){
 const view=authRoute();const title={login:'Welcome back',register:'Register your organization',reset:'Staff password recovery',setup:'First-time platform setup'}[view];
 const intro={login:'Sign in securely to manage your operations.',register:'Tell us about your business, locations, farming activities and team.',reset:'Use the one-time code issued by your organization administrator.',setup:'Create the first platform-owner account. Only available before any account exists.'}[view];
 const fields=view==='login'?`${field('email','Work email',{type:'email',required:true,wide:true})}${field('password','Password',{type:'password',required:true,wide:true})}<label class="wide auth-check"><input type="checkbox" name="remember_me"> Remember me on this device</label>`:
 view==='register'?registrationFields:
 view==='reset'?`${field('code','One-time staff recovery code',{required:true,wide:true})}${field('new_password','New password (10+ characters)',{type:'password',required:true,minlength:10,wide:true})}`:
 `${field('full_name','Owner full name',{required:true,wide:true})}${field('email','Owner email',{type:'email',required:true,wide:true})}${field('password','Secure password (10+ characters)',{type:'password',required:true,minlength:10,wide:true})}${field('bootstrap_token','Owner bootstrap token (required for production)',{type:'password',wide:true})}`;
 const links=[['Register organization','/register-organization'],['Staff recovery','/staff-recovery'],['First-time setup','/first-time-setup']];
 root.innerHTML=`<div class="login-page cape-auth" id="login-bg"><section class="login-card ${view==='register'?'registration-card':''}">
 <div class="auth-logo"><img src="/frontend/public/images/branding/cape-ranch-logo.png" alt="Cape Ranch"></div>
 <h1>${title}</h1><p>${intro}</p><form id="auth-form" class="form-grid">${fields}<button class="btn commit wide auth-submit" type="submit">${{login:'Sign in',register:'Submit organization registration',reset:'Update password',setup:'Create platform owner'}[view]}</button></form>
 <nav class="auth-nav" aria-label="Account pages">${view!=='login'?'<a href="/">Sign in</a>':''}${links.filter(([_,href])=>href!==pagePath[view]).map(([label,href])=>`<a href="${href}">${label}</a>`).join('')}</nav>
 <div id="auth-feedback" role="status" aria-live="polite"></div></section></div>`;
 get('v6/public/branding').then(x=>{if(x.background_url){const bg=root.querySelector('#login-bg');if(bg)bg.style.backgroundImage=`linear-gradient(90deg,#0a3e2e99,#0d473977),url('${x.background_url}')`}}).catch(()=>{});
 const form=root.querySelector('#auth-form');form.onsubmit=async e=>{
  e.preventDefault();const btn=form.querySelector('.auth-submit');btn.disabled=true;const data=Object.fromEntries(new FormData(form));
  if(view==='login')data.remember_me=form.elements.remember_me.checked;
  if(view==='register'){
   for(const k of ['employee_count','expected_system_users','farms_count','total_land_hectares']){
    if(data[k]==='')delete data[k];else data[k]=Number(data[k]);
   }
   if(data.incorporation_date==='')delete data.incorporation_date;
  }
  const paths={login:'auth/login',register:'cape/public/organizations/register',reset:'v5/auth/password-reset/complete',setup:'auth/setup'};
  try{const result=await post(paths[view],data);
   if(view==='login')return await onAuthenticated();
   if(view==='register'){
    form.replaceWith(document.createElement('div'));
    root.querySelector('#auth-feedback').innerHTML=`<div class="auth-success"><strong>Registration submitted.</strong><p>Your organization is awaiting verification. You can sign in to check subscription options once approved.</p><a href="/">Return to sign in</a></div>`;
    return;
   }
   location.assign('/');
  }catch(error){const feedback=root.querySelector('#auth-feedback');feedback.textContent=error.message;feedback.className='auth-error';btn.disabled=false}
 };
}
