// Cape Ranch public marketing page. Isolated from the authenticated application.
const nav = document.querySelector('#cr-navigation');
const menuButton = document.querySelector('.cr-menu-toggle');
function closeMenu() {
  nav?.classList.remove('cr-open');
  menuButton?.setAttribute('aria-expanded', 'false');
  menuButton?.setAttribute('aria-label', 'Open menu');
}
if (menuButton && nav) {
  menuButton.addEventListener('click', () => {
    const opened = nav.classList.toggle('cr-open');
    menuButton.setAttribute('aria-expanded', String(opened));
    menuButton.setAttribute('aria-label', opened ? 'Close menu' : 'Open menu');
  });
  nav.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && nav.classList.contains('cr-open')) {
      closeMenu(); menuButton.focus();
    }
  });
  document.addEventListener('click', event => {
    if (nav.classList.contains('cr-open') && !nav.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
  });
}

document.querySelectorAll('[data-current-year]').forEach(el => {
  el.textContent = String(new Date().getFullYear());
});

const tour = document.querySelector('#cr-tour-dialog');
document.querySelectorAll('[data-tour]').forEach(btn => btn.addEventListener('click', () => {
  if (tour && typeof tour.showModal === 'function') tour.showModal();
  else document.querySelector('#platform')?.scrollIntoView({ behavior: 'smooth' });
}));
tour?.addEventListener('click', event => { if (event.target === tour) tour.close(); });

// Real entrance animations: progressively reveal card rows/sections as the
// visitor scrolls. Add hidden states only after the observer is available,
// and never hide visible-above-the-fold content. Hover remains independent.
const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
const revealItems = [...document.querySelectorAll('.cr-reveal')];
if (!reducedMotion && 'IntersectionObserver' in window && revealItems.length) {
  const visibleNow = item => item.getBoundingClientRect().top <= innerHeight * 0.94;
  // Above-the-fold cards are never hidden while waiting for an animation.
  revealItems.forEach(item => { if (visibleNow(item)) item.classList.add('cr-visible'); });
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('cr-visible');
        observer.unobserve(entry.target);
      }
    }
  }, { threshold: 0.07, rootMargin: '0px 0px -5% 0px' });
  revealItems.filter(item => !item.classList.contains('cr-visible')).forEach(item => observer.observe(item));
  document.documentElement.classList.add('cr-motion-ready');
  // Pages restored from browser history should not have invisible elements.
  window.addEventListener('pageshow', event => {
    if (event.persisted) revealItems.forEach(item => item.classList.add('cr-visible'));
  });
}

// A thin scroll progress line offers unobtrusive visual feedback on long pages.
let scrollTicking = false;
function updateProgress() {
  const scrollable = document.documentElement.scrollHeight - innerHeight;
  const progress = scrollable > 0 ? Math.max(0, Math.min(1, scrollY / scrollable)) : 0;
  document.documentElement.style.setProperty('--cr-scroll', String(progress));
  scrollTicking = false;
}
window.addEventListener('scroll', () => {
  if (!scrollTicking) { scrollTicking = true; requestAnimationFrame(updateProgress); }
}, { passive: true });
window.addEventListener('resize', updateProgress, { passive: true });
updateProgress();

// Keep signed-in users on their existing management app. This optional probe
// never blocks the public page, even when the backend is unavailable.
(async () => {
  try {
    const response = await fetch('/api/auth/me', {
      credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store'
    });
    if (response.ok) {
      const data = await response.json();
      if (data?.user?.id && location.pathname === '/') location.replace('/app');
    }
  } catch { /* the public page can run without a backend response */ }
})();
