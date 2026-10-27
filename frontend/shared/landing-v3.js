/** Cape Ranch V3 public-only behavior. No interaction with authenticated app shell. */
const root = document.documentElement;
const menuButton = document.querySelector('.cr3-menu-toggle');
const menu = document.querySelector('#cr3-nav');
function closeMenu() {
  menu?.classList.remove('cr3-open');
  menuButton?.setAttribute('aria-expanded', 'false');
  menuButton?.setAttribute('aria-label', 'Open menu');
}
menuButton?.addEventListener('click', () => {
  const opened = menu?.classList.toggle('cr3-open') ?? false;
  menuButton.setAttribute('aria-expanded', String(opened));
  menuButton.setAttribute('aria-label', opened ? 'Close menu' : 'Open menu');
});
menu?.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeMenu(); menuButton?.focus(); } });
document.addEventListener('click', e => { if (menu?.classList.contains('cr3-open') && !menu.contains(e.target) && !menuButton?.contains(e.target)) closeMenu(); });
for (const el of document.querySelectorAll('[data-current-year]')) el.textContent = String(new Date().getFullYear());

// Animated entrances only after JS is active. Content remains readable when
// IntersectionObserver is unsupported, disabled, or reduced motion is set.
const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false;
const items = [...document.querySelectorAll('.cr3-reveal')];
if (!reduced && 'IntersectionObserver' in window && items.length) {
  root.classList.add('cr3-js');
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('cr3-is-visible');
      observer.unobserve(entry.target);
    }
  }, { threshold: 0.065, rootMargin: '0px 0px -4% 0px' });
  // Delay only below-fold elements; avoid flashing or hidden sections on refresh.
  items.forEach((el, i) => {
    if (el.getBoundingClientRect().top <= innerHeight * 0.94) return;
    el.classList.add('cr3-waiting');
    el.style.transitionDelay = `${(i % 5) * 65}ms`;
    observer.observe(el);
  });
  window.addEventListener('pageshow', e => { if (e.persisted) items.forEach(el => el.classList.add('cr3-is-visible')); });
}

const tabs = [...document.querySelectorAll('.cr3-tab')];
if ('IntersectionObserver' in window) {
  const bandObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      tabs.forEach(tab => tab.classList.toggle('cr3-tab-active', tab.hash === '#' + entry.target.id));
    }
  }, { rootMargin: '-25% 0px -50% 0px', threshold: 0 });
  document.querySelectorAll('.cr3-feature-chapters > section[id]').forEach(band => bandObserver.observe(band));
}

let ticking = false;
function progress() {
  const height = document.documentElement.scrollHeight - innerHeight;
  root.style.setProperty('--cr3-scroll', String(height > 0 ? Math.min(1,Math.max(0,scrollY/height)) : 0));
  ticking = false;
}
window.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(progress); } }, { passive:true });
window.addEventListener('resize',progress,{passive:true});progress();

// A signed-in visitor should enter their existing management app, not the
// public introduction. Do not redirect if the server's response is unknown.
(async () => {
  try {
    const res = await fetch('/api/auth/me', { credentials:'same-origin', headers:{Accept:'application/json'}, cache:'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    if (data?.user?.id && location.pathname === '/') location.replace('/app');
  } catch { /* public page remains available without API access */ }
})();
