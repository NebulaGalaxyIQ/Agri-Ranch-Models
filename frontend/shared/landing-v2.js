// Public marketing landing only. Never imports the authenticated application shell.
const menuButton = document.querySelector('.cr-menu-toggle');
const nav = document.querySelector('#cr-navigation');
if (menuButton && nav) {
  menuButton.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('cr-open');
    menuButton.setAttribute('aria-expanded', String(isOpen));
    menuButton.setAttribute('aria-label', isOpen ? 'Close menu' : 'Open menu');
  });
  nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    nav.classList.remove('cr-open');
    menuButton.setAttribute('aria-expanded','false');
    menuButton.setAttribute('aria-label','Open menu');
  }));
  document.addEventListener('keydown', e => {
    if(e.key === 'Escape' && nav.classList.contains('cr-open')) {
      nav.classList.remove('cr-open'); menuButton.setAttribute('aria-expanded','false'); menuButton.focus();
    }
  });
}
document.querySelectorAll('[data-current-year]').forEach(el=>{el.textContent=String(new Date().getFullYear())});
const tour = document.querySelector('#cr-tour-dialog');
document.querySelectorAll('[data-tour]').forEach(btn=>btn.addEventListener('click',()=>{
  if(tour && typeof tour.showModal === 'function') tour.showModal();
  else document.querySelector('#platform')?.scrollIntoView({behavior:'smooth'});
}));
tour?.addEventListener('click',e=>{if(e.target===tour)tour.close()});
// Reveal is decorative, do not conceal elements if reduced motion or IntersectionObserver unsupported.
if('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches){
  const items=Array.from(document.querySelectorAll('.cr-reveal'));
  const observer=new IntersectionObserver(entries=>{
    for(const entry of entries){if(entry.isIntersecting){entry.target.classList.add('cr-visible');observer.unobserve(entry.target)}}
  },{rootMargin:'0px 0px 65px 0px',threshold:.05});
  document.documentElement.classList.add('cr-js');
  items.forEach(el=>observer.observe(el));
}
// Existing signed-in users should reach the application directly; no login UI flashed.
// This check is optional; guests remain on the public page when the endpoint returns 401.
(async()=>{
  try{
    const response=await fetch('/api/auth/me',{credentials:'same-origin',headers:{Accept:'application/json'},cache:'no-store'});
    if(response.ok){const data=await response.json();if(data?.user?.id && location.pathname==='/') location.replace('/app');}
  }catch{ /* public marketing page also works when backend is temporarily offline */ }
})();
