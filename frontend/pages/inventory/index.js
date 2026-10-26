import {get,post,patch,can,esc} from '../../shared/api.js';
import {head,button,table,kpis,modalForm,detailModal,listenRows,submoduleDirectory,recordsPreview,submoduleWorkspace,bindSubmodules,rememberedSubmodule,rememberSubmodule} from '../../shared/ui.js';
import {stock,ledger,receive,issue} from './service.js';
const TYPES=['feed','medicine','herbicide','fertilizer','seed','uniform','boots','equipment','maintenance_part','gardening_tool','fuel','cleaning_supply','other'];
const categoryFields={medicine:[['strength_or_concentration','Strength'],['storage_instructions','Storage requirements']],herbicide:[['strength_or_concentration','Concentration'],['storage_instructions','Safety / storage']],fertilizer:[['strength_or_concentration','Nutrient grade']],uniform:[['size','Size']],boots:[['size','Size']],equipment:[['specification','Model / serial number']],maintenance_part:[['specification','Part number / compatible machine']],gardening_tool:[['specification','Tool details']],seed:[['specification','Crop / variety']],feed:[],other:[['specification','Description']]};
const now=()=>new Date().toISOString().slice(0,10);
export async function render(root){let {items}=await stock();const writable=can('stock.write');let action=rememberedSubmodule('inventory'),type='feed',history=false,recordType=null,mode=items.some(x=>x.category==='feed')?'existing':'new';
 async function refresh(){await render(root)}
 const sections=[{id:'items',title:'Stock records',icon:'▦',description:'View balances by inventory category'},
    {id:'stockin',title:'Stock In',icon:'↓',description:'Register or receive physical stock'},
    {id:'out',title:'Stock Out',icon:'↑',description:'Record issues and transfers'}];
 const categoryNames={feed:'Feeds & mixes',medicine:'Medicines',herbicide:'Herbicides & crop chemicals',
  fertilizer:'Fertilizers',seed:'Seeds',uniform:'Staff uniforms',boots:'Boots & footwear',
  equipment:'Machinery & equipment',maintenance_part:'Maintenance parts',gardening_tool:'Gardening tools',
  fuel:'Fuel',cleaning_supply:'Cleaning supplies',other:'Other supplies'};
 if(action&&!sections.some(x=>x.id===action)){action=null;}
 function draw(){
  if(!action){root.innerHTML=submoduleDirectory('Inventory',sections,{items:items.length})+
   `<div class="submodule-overview-metrics">${kpis([{label:'Registered items',value:items.length},{label:'Categories in use',value:new Set(items.map(x=>x.category)).size},
     {label:'Reorder alerts',value:items.filter(x=>x.reorder).length},
     {label:'Usable feed items',value:items.filter(x=>x.category==='feed'&&x.usable_balance>0).length}])}</div>`+
      `<div class="module-previews inventory-previews">${recordsPreview('Current stock',items.slice(-7),[['name','Item'],['category','Category'],['usable_balance','Usable stock'],['unit','Unit'],['reorder','Reorder alert']])}</div>`;
   root.querySelector('.submodule-overview-metrics')?.insertAdjacentHTML('afterend',`<section class="inventory-category-section"><div class="directory-title"><h2>Inventory categories</h2><p>Browse supplies by their recorded type.</p></div><div class="inventory-category-gallery">${[['feed','Feeds'],['medicine','Medicine'],['seed','Seeds'],['fertilizer','Fertilizer'],['herbicide','Herbicides'],['equipment','Tools & equipment'],['uniform','Uniforms & boots'],['other','Other']].map(([id,label])=>`<button type="button" class="inventory-category-tile" data-home-category="${id}"><img src="/frontend/public/images/v65/categories/${id}.webp" alt="" loading="lazy"><strong>${label}</strong></button>`).join('')}</div></section>`);
   root.querySelectorAll('[data-home-category]').forEach(b=>b.addEventListener('click',()=>{recordType=b.dataset.homeCategory;action='items';rememberSubmodule('inventory','items');draw()}));
   bindSubmodules(root,id=>{action=id;rememberSubmodule('inventory',id);draw()});return;
  }
  const availableCategories=[...new Set(items.map(x=>x.category||'other'))].sort();
  if(!recordType||!availableCategories.includes(recordType))recordType=availableCategories[0]||'feed';
  const records=items.filter(x=>x.category===recordType);
  const recordGroups=`<h3>Stock categories</h3><p class="muted">Choose the type of stock you want to view. Select a saved item to view or correct it.</p>
   <div class="inventory-record-groups">${availableCategories.map(c=>`<button type="button" class="inventory-record-group ${recordType===c?'selected':''}" data-record-type="${esc(c)}"><span>${esc(categoryNames[c]||c.replaceAll('_',' '))}</span><small>${items.filter(x=>x.category===c).length}</small></button>`).join('')}</div>
   <div class="section-heading"><h3>${esc(categoryNames[recordType]||recordType.replaceAll('_',' '))}</h3><span class="muted">${records.length} registered items</span></div>`;
  const content=action==='items'?recordGroups+table(records,
     [['name','Item'],['category','Category'],['usable_balance','Available'],['unit','Unit'],['unit_cost','Cost/unit'],['currency','Currency'],['reorder','Reorder',x=>x.reorder?'Reorder':'Available']],{empty:'No items in this category.'}):
   action==='stockin'?`<h3>What would you like to receive?</h3><p class="muted">Select the correct category before entering the receipt.</p>
    <div class="inventory-categories">${TYPES.map(c=>`<button type="button" class="pill ${type===c?'active':''}" data-type="${c}">${esc(categoryNames[c]||c.replaceAll('_',' '))}</button>`).join('')}</div>
    <div class="toolbar"><label>Stock action <select id="stockin-mode"><option value="existing">Receive existing item</option><option value="new">Record new item and receive</option></select></label>
    ${mode==='existing'?`<label>Registered item <select id="stock-item"><option value="">Select item</option>${items.filter(x=>x.category===type).map(i=>`<option value="${i.id}">${esc(i.name)} (${esc(i.unit)})</option>`).join('')}</select></label>`:''}
    ${writable?button('Continue to Stock In form','record','commit'):''}</div>`:
   action==='out'?`<div class="toolbar"><label>Choose stock item <select id="stock-item"><option value="">Choose available stock</option>${items.filter(x=>x.usable_balance>0).map(i=>`<option value="${i.id}">${esc(i.name)} · ${xUnit(i)}</option>`).join('')}</select></label>${writable?button('Record Stock Out','record','commit'):''}</div>`:
   `<p class="muted">Choose a stock area from the Inventory home page.</p>`;
  root.innerHTML=head(sections.find(x=>x.id===action)?.title||'Inventory',sections.find(x=>x.id===action)?.description||'',
   button('📜 View transaction history','history','commit')+' '+button('Refresh table','refresh','commit'))+
   submoduleWorkspace('Inventory',sections,action,content);
  bindSubmodules(root,id=>{action=id;rememberSubmodule('inventory',id);draw()});
  root.querySelectorAll('[data-record-type]').forEach(b=>b.onclick=()=>{recordType=b.dataset.recordType;draw()});
  root.querySelectorAll('[data-type]').forEach(b=>b.onclick=()=>{type=b.dataset.type;mode=items.some(x=>x.category===type)?'existing':'new';draw()});
  const sm=root.querySelector('#stockin-mode');if(sm)sm.value=mode;if(sm)sm.onchange=()=>{mode=sm.value;draw()};
  root.querySelector('#record')?.addEventListener('click',action==='out'?openIssue:openStockIn);
  root.querySelector('#refresh')?.addEventListener('click',refresh);
  root.querySelector('#history')?.addEventListener('click',async()=>{
    const response=await ledger();const records=response.items||[];
    root.querySelector('.submodule-content').innerHTML='<div class="section-heading"><h2>Transaction history</h2></div>'+table(records,
      [['transaction_date','Date'],['item_name','Item'],['direction','Movement'],['quantity','Quantity'],['reference','Reference'],['unit_cost','Unit cost']]);
    listenRows(root,records,x=>detailModal(x,{title:'Stock transaction'}));
  });
  if(action==='items')listenRows(root,records,x=>modalForm({title:`${x.name} — stock details`,readOnly:!writable,
    fields:writable?[{name:'reorder_level',label:'Reorder threshold',type:'number',min:0,step:'.001',value:x.reorder_level},
     {name:'reason',label:'Reason for change',required:true,type:'textarea'}]:[],
    intro:`<p>${esc(x.name)} · ${esc(x.usable_balance)} ${esc(x.unit)} available</p>`,
    onSave:async d=>{await patch(`v5/stock/items/${x.id}`,d);await refresh()}}));
 }
 function xUnit(x){return `${x.usable_balance} ${esc(x.unit)}`}
 function receiptFields(unit,currency='TZS',needExpiry=false){return [{name:'quantity',label:`Quantity (${unit})`,type:'number',min:'.001',step:'.001',required:true},{name:'total_cost',label:'Item purchase cost',type:'number',min:0,step:'.01',required:true},{name:'transport_cost',label:'Transport cost',type:'number',min:0,value:0},{name:'other_cost',label:'Other purchase costs',type:'number',min:0,value:0},{name:'currency',label:'Purchase currency',type:'select',options:['TZS','USD','KES','EUR'],value:currency},{name:'exchange_rate',label:'Exchange rate (only for a different currency)',type:'number',step:'.00000001',min:'.00000001'},{name:'supplier_name',label:'Supplier'},{name:'supplier_contact',label:'Supplier contact'},{name:'origin',label:'Origin'},{name:'invoice_number',label:'Invoice number'},{name:'transaction_date',label:'Date received',type:'date',value:now(),required:true},{name:'expiry_date',label:'Expiry date',type:'date',required:needExpiry}];}
 function openStockIn(){const existing=mode==='existing',id=+(root.querySelector('#stock-item')?.value||((items.filter(x=>x.category===type).length===1)?items.find(x=>x.category===type)?.id:0));const item=items.find(x=>x.id===id);
  if(existing&&!item){alert('Choose an existing item or select New item first.');return}
  if(existing){modalForm({title:`Receive ${item.name}`,saveLabel:'Save Stock In',fields:receiptFields(item.unit,item.currency,item.category==='medicine'),onSave:async d=>{d.item_id=item.id;if(d.currency===item.currency)delete d.exchange_rate;await receive(d);await refresh()}});return}
  const attrs=categoryFields[type]||categoryFields.other;
  const f=[{name:'name',label:'Item name',required:true},{name:'unit',label:'Measurement unit',type:'select',required:true,options:type==='feed'?['kg']:['kg','litres','ml','pieces','pairs','bags','units','tonnes'],value:type==='feed'?'kg':undefined},{name:'valuation_currency',label:'Stock valuation currency',type:'select',options:['TZS','USD','KES','EUR'],value:'TZS'},...attrs.map(([k,v])=>({name:`attr_${k}`,label:v})),...receiptFields(type==='feed'?'kg':'units','TZS',type==='medicine')];
  modalForm({title:`Stock In — New ${type.replaceAll('_',' ')}`,fields:f,saveLabel:'Register and receive stock',onSave:async d=>{
   const attributes={};for(const k of Object.keys(d))if(k.startsWith('attr_')){attributes[k.slice(5)]=d[k];delete d[k]}
   const {name,unit,valuation_currency,...receipt}=d;
   await post('v5/stock/receive/new-item',{name,unit,valuation_currency,category:type,attributes,receipt:{item_id:0,...receipt}});
   await refresh()}});
 }
 function openIssue(){const id=+root.querySelector('#stock-item')?.value;const item=items.find(x=>x.id===id);if(!item){alert('Select a stocked item first.');return}
  modalForm({title:`Stock Out — ${item.name}`,saveLabel:'Complete Stock Out',fields:[{name:'quantity',label:`Quantity (${item.unit})`,type:'number',min:'.001',step:'.001',required:true},{name:'transaction_date',label:'Date issued',type:'date',value:now(),required:true},{name:'note',label:'Destination / reason',type:'textarea',required:true}],onSave:async d=>{await issue({item_id:id,...d});await refresh()}});
 }
 draw();
}
