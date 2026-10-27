/**
 * Cape Ranch V3.3 public landing interactions.
 * Progressive enhancement only: without JavaScript, all content stays visible.
 * Does not modify the authenticated app shell or API routes.
 */
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
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && menu?.classList.contains('cr3-open')) {
    closeMenu();
    menuButton?.focus();
  }
});
document.addEventListener('click', e => {
  if (menu?.classList.contains('cr3-open') && !menu.contains(e.target) && !menuButton?.contains(e.target)) closeMenu();
});
for (const el of document.querySelectorAll('[data-current-year]')) {
  el.textContent = String(new Date().getFullYear());
}

// Reveal-on-scroll: prepare ONLY below-the-fold elements to avoid hiding visible
// content or creating a blank page if the observer is unavailable. Each chapter
// reveals its photo and text in a staggered sequence; cards stagger by row.
const motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)');
const items = [...document.querySelectorAll('.cr3-reveal')];
const pending = new Set();
let revealObserver;

function showElement(el) {
  pending.delete(el);
  if (!el.classList.contains('cr3-waiting')) return;
  el.classList.add('cr3-is-visible');
  revealObserver?.unobserve(el);
}
function finishElement(el) {
  // Keep the last frame of the reveal, then return control of transform to
  // normal :hover and :focus-visible effects (especially on category tabs).
  if (!el.classList.contains('cr3-is-visible')) return;
  el.classList.remove('cr3-waiting');
  el.style.removeProperty('--cr3-reveal-delay');
}
function prepareReveals() {
  if (motionQuery?.matches || !('IntersectionObserver' in window) || !items.length) return;

  const viewport = window.innerHeight || document.documentElement.clientHeight;
  revealObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) showElement(entry.target);
    }
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.08 });

  for (const el of items) {
    const bounds = el.getBoundingClientRect();
    // In-view and above-view content is immediately visible, including when
    // navigating to /#features or /#solutions and on page refresh.
    if (bounds.top < viewport * 0.91) continue;
    const group = el.closest('.cr3-metrics-grid, .cr3-tab-grid, .cr3-band-inner, .cr3-platform-grid, .cr3-steps, .cr3-faq-grid, .cr3-final-content');
    const siblings = group ? [...group.querySelectorAll('.cr3-reveal')] : [el];
    const order = Math.max(0, siblings.indexOf(el));
    el.style.setProperty('--cr3-reveal-delay', `${Math.min(order, 5) * 85}ms`);
    el.classList.add('cr3-waiting');
    pending.add(el);
    el.addEventListener('transitionend', e => {
      if (e.target === el && (e.propertyName === 'opacity' || e.propertyName === 'transform')) finishElement(el);
    });
    // Observing starts after hidden styles have been committed to avoid flicker.
  }

  // Arm the hidden states only after every below-fold element has been tagged.
  // This avoids an accidental fade-OUT during initial page load.
  root.classList.add('cr3-js');
  // Commit the initial below-fold hidden state before enabling transitions;
  // otherwise browser paints a distracting fade-OUT instead of only fading IN.
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    root.classList.add('cr3-animate');
    for (const el of pending) revealObserver?.observe(el);
    scheduleVisibilityCheck();
  }));

  // Defensive visibility check for mobile viewport changes, restored tabs,
  // hash navigation, and edge cases where browser observers are delayed.
  let scheduled = false;
  function checkVisibility() {
    scheduled = false;
    const threshold = (window.innerHeight || viewport) * 0.97;
    for (const el of pending) {
      const r = el.getBoundingClientRect();
      if (r.top <= threshold && r.bottom >= 0) showElement(el);
    }
  }
  function scheduleVisibilityCheck() {
    if (scheduled || !pending.size) return;
    scheduled = true;
    window.requestAnimationFrame(checkVisibility);
  }
  window.addEventListener('scroll', scheduleVisibilityCheck, { passive: true });
  window.addEventListener('resize', scheduleVisibilityCheck, { passive: true });
  window.addEventListener('hashchange', scheduleVisibilityCheck);
  window.addEventListener('pageshow', scheduleVisibilityCheck);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) scheduleVisibilityCheck(); });
  scheduleVisibilityCheck();
}
prepareReveals();

// If the OS accessibility setting changes while the page is open, never leave
// any section invisible; reduced-motion users get an instant full view.
motionQuery?.addEventListener?.('change', e => {
  if (!e.matches) return;
  revealObserver?.disconnect();
  items.forEach(el => {
    el.classList.add('cr3-is-visible');
    finishElement(el);
  });
  pending.clear();
  root.classList.remove('cr3-js', 'cr3-animate');
});

const tabs = [...document.querySelectorAll('.cr3-tab')];
if ('IntersectionObserver' in window && tabs.length) {
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
  const height = document.documentElement.scrollHeight - (window.innerHeight || 0);
  root.style.setProperty('--cr3-scroll', String(height > 0 ? Math.min(1, Math.max(0, window.scrollY / height)) : 0));
  ticking = false;
}
window.addEventListener('scroll', () => {
  if (!ticking) { ticking = true; window.requestAnimationFrame(progress); }
}, { passive: true });
window.addEventListener('resize', progress, { passive: true });
progress();

// Keep the old signed-in-user behavior. A failed/unknown auth response should
// never redirect visitors away from the public landing page.
(async () => {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    if (data?.user?.id && location.pathname === '/') location.replace('/app');
  } catch { /* public site works even when API is temporarily unavailable */ }
})();
