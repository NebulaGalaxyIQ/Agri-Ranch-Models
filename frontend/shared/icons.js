// Local vector icons for the compact V6.4 submodule directory.
// SVGs are decorative; the accessible card label is the submodule title.
const paths={
 farm:'<path d="M3 21V10l9-6 9 6v11M3 10l9 5 9-5M8 21v-7h8v7M4 21h16"/>',
 folders:'<path d="M3 7h7l2 3h9v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 10V6a2 2 0 0 1 2-2h4"/>',
 layers:'<path d="m12 2 9 5-9 5-9-5 9-5Zm-9 10 9 5 9-5M3 17l9 5 9-5"/>',
 pen:'<path d="M3 20V6h18v14M3 11h18M8 6v14M16 6v14M3 20h18"/>',
 cow:'<path d="M6 9 3 7 2 9l3 4 1 6h2l1-5h6l1 5h2l1-7 2-3-1-2-4 1-2-3h-4L6 9Zm3 0h.01M15 9h.01M5 13l-2 1"/>',
 scale:'<path d="M4 7h16M8 7l-4 8h8L8 7Zm8 0-4 8h8l-4-8ZM12 3v17m-6 1h12"/>',
 leaf:'<path d="M20 4C10 4 4 8 4 16c0 2 1 4 3 4 9 0 13-10 13-16ZM4 20c2-6 6-8 11-11"/>',
 feed:'<path d="M5 8h14l-2 12H7L5 8ZM3 8h18M8 5l3-3M16 5l-3-3M9 12h6M9 16h6"/>',
 sale:'<path d="M3 4h2l3 11h10l3-8H6M9 20h.01M18 20h.01M8 16h11"/>',
 field:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 10h18M10 3v18M16 10v11M3 16h7"/>',
 seed:'<path d="M12 22V11M12 13C5 13 4 8 5 5c6 0 8 4 7 8Zm0-3c0-5 4-8 8-8 1 6-3 8-8 8Z"/>',
 tools:'<path d="M14 7a5 5 0 0 0 6 6L11 22 2 13l9-9a5 5 0 0 0 6 6M6 17l2 2"/>',
 clipboard:'<rect x="5" y="4" width="14" height="18" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6M9 15h6M9 19h4"/>',
 coins:'<ellipse cx="9" cy="6" rx="6" ry="3"/><path d="M3 6v5c0 2 3 3 6 3m-6-3v5c0 2 3 3 6 3M15 6v3M15 15h7v6h-7zM18 12v3"/>',
 chart:'<path d="M3 21V4M3 21h18M7 15l4-4 4 2 6-8M17 5h4v4"/>',
 chicken:'<path d="M7 6c-1-4 3-4 4-1 2-3 5 0 3 2 4 1 6 4 5 8-1 4-5 6-9 5S4 13 6 10M6 10l-3-1 3-2M10 20v2m5-2v2"/>',
 egg:'<path d="M12 2C7 2 5 9 5 14a7 7 0 0 0 14 0c0-5-2-12-7-12Z"/>',
 shield:'<path d="m12 2 9 4v6c0 5-4 9-9 10-5-1-9-5-9-10V6zM8 12l3 3 5-6"/>',
 heart:'<path d="M20 9c0-5-6-6-8-2C10 3 4 4 4 9c0 4 8 10 8 10s8-6 8-10ZM7 12h3l2-3 2 6 2-3h3"/>',
 milk:'<path d="M8 3h8M8 3v5l-3 4v8a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-8l-3-4V3M5 14h14M9 18h6"/>',
 tractor:'<circle cx="7" cy="18" r="4"/><circle cx="19" cy="19" r="2"/><path d="M3 18V9h11l3 6h4v4M7 9V4h6v5M14 15H4"/>',
 wrench:'<path d="M20 7a6 6 0 0 1-8 6L6 19a3 3 0 0 1-4-4l6-6a6 6 0 0 1 8-8l-4 4 3 3z"/>',
 flower:'<circle cx="12" cy="10" r="2"/><path d="M12 8C8 3 5 7 9 10c-5-2-6 4-1 4-2 4 3 7 4 2 1 5 6 2 4-2 5 0 4-6-1-4 4-3 1-7-3-2M12 17v5m0-1-4-2m4 2 4-2"/>',
 water:'<path d="M12 2C8 9 5 12 5 16a7 7 0 0 0 14 0c0-4-3-7-7-14Z"/>',
 package:'<path d="M3 7 12 2l9 5v10l-9 5-9-5V7Zm0 0 9 5 9-5M12 12v10M8 5l9 5"/>',
 arrows:'<path d="M7 3v17m0 0-4-4m4 4 4-4M17 21V4m0 0-4 4m4-4 4 4"/>',
 warehouse:'<path d="M3 21V8l9-5 9 5v13M3 9h18M7 21V12h10v9M7 16h10M3 21h18"/>',
 people:'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3c0-4 12-4 12 0v3M18 10a3 3 0 0 0 0-6M17 15c3-1 5 1 5 4v2"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h4M7 17h7"/>',
 letter:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 7 9-7"/>',
 settings:'<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M4 4l2 2m12 12 2 2M2 12h3m14 0h3M4 20l2-2M18 6l2-2"/>',
 check:'<path d="M4 12 10 18 20 6"/>',
};
const exact={
 fattening:'cow',livestock:'chicken',crops:'field',gardening:'flower',machinery:'tractor',inventory:'package',overview:'farm',staff:'people',finance:'coins',analytics:'chart',platform:'shield',subscription:'shield',
 ranches:'farm',projects:'folders',batches:'layers',pens:'pen',animals:'cow',weighing:'scale',feeding:'feed',mixes:'feed',sales:'sale',
 fields:'field',cycles:'seed',inputs:'tools',records:'clipboard',profit:'chart',
 groups:'chicken',production:'milk',products:'package',costs:'coins',productSales:'sale',performance:'chart',
 assets:'tractor',activities:'flower',areas:'flower',stockin:'package',items:'warehouse',out:'arrows',
 organizations:'warehouse',usage:'chart',support:'letter',branding:'settings',
};
export function iconSvg(key,{size=21}={}){
 const name=exact[key]||(/animal|cattle|flock/.test(key)?'cow':/feed/.test(key)?'feed':/health|medicine/.test(key)?'heart':/garden|plant/.test(key)?'flower':/machin|equip/.test(key)?'tractor':'folders');
 return `<svg class="ui-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name]}</svg>`;
}
