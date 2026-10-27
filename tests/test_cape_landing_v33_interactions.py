"""Dependency-free regression checks for Cape Ranch public V3.3 interactions."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'frontend/landing.html'
CSS = ROOT / 'frontend/shared/landing-v3.css'
JS = ROOT / 'frontend/shared/landing-v3.js'


class LandingV33InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding='utf-8')
        cls.css = CSS.read_text(encoding='utf-8')
        cls.js = JS.read_text(encoding='utf-8')

    def test_script_and_stylesheets_share_fresh_version(self):
        self.assertIn('landing-v3.css?v=3.3.0', self.page)
        self.assertIn('landing-v3.js?v=3.3.0', self.page)
        self.assertNotIn('landing-v2.js', self.page)

    def test_reveal_is_both_styled_and_triggered(self):
        self.assertIn('.cr3-js .cr3-reveal.cr3-waiting:not(.cr3-is-visible)', self.css)
        self.assertIn('.cr3-js.cr3-animate .cr3-reveal.cr3-waiting', self.css)
        for value in ['opacity: 0', 'translate3d(0, 25px, 0)', "el.classList.add('cr3-waiting')", "el.classList.add('cr3-is-visible')", 'IntersectionObserver', 'requestAnimationFrame']:
            self.assertIn(value, self.css + self.js)
        self.assertIn("root.classList.add('cr3-animate')", self.js)
        self.assertIn('scheduleVisibilityCheck()', self.js)

    def test_reveal_covers_features_and_chapters(self):
        self.assertGreaterEqual(len(re.findall(r'cr3-tab cr3-reveal', self.page)), 6)
        self.assertGreaterEqual(len(re.findall(r'cr3-band-visual cr3-reveal', self.page)), 6)
        self.assertGreaterEqual(len(re.findall(r'cr3-band-info cr3-reveal', self.page)), 6)
        self.assertGreaterEqual(len(re.findall(r'cr3-mini', self.page)), 18)

    def test_actual_hover_states_for_visuals_and_small_cards(self):
        for selector in ['.cr3-tab:hover', '.cr3-mini:hover', '.cr3-band-visual:hover', '.cr3-metric:hover', '.cr3-faq-list details:hover', '.cr3-step:hover']:
            self.assertIn(selector, self.css)
        self.assertIn('scale(1.09)', self.css)
        self.assertIn('translateY(-5px)', self.css)

    def test_accessibility_and_fallback(self):
        self.assertIn('prefers-reduced-motion: reduce', self.css)
        self.assertIn("motionQuery?.addEventListener?.('change'", self.js)
        self.assertIn('root.classList.remove(\'cr3-js\', \'cr3-animate\')', self.js)
        self.assertIn("if (motionQuery?.matches || !('IntersectionObserver' in window)", self.js)
        self.assertNotIn('.cr3-reveal { opacity: 0', self.css)  # no-JS default must be visible

    def test_authenticated_app_and_black_footer_preserved(self):
        self.assertIn("location.replace('/app')", self.js)
        self.assertIn('href="/login"', self.page)
        self.assertIn('href="/register-organization"', self.page)
        self.assertIn('.cr3-footer{background:#080a0c', self.css)
        self.assertIn('cape-ranch-footer-logo.webp', self.page)


if __name__ == '__main__':
    unittest.main()
