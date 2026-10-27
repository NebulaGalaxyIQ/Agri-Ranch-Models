"""Dark footer regression tests; Python stdlib only."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/landing.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/shared/landing-v3.css").read_text(encoding="utf-8")

class CapeRanchDarkFooter(unittest.TestCase):
    def test_footer_and_cta_are_near_black(self):
        self.assertRegex(CSS, r"\.cr3-footer\{background:#080a0c;")
        self.assertRegex(CSS, r"\.cr3-final\{position:relative;background:#0c0e10;")
        self.assertNotIn("#072b25", CSS, "old green footer rule remains")
        self.assertNotIn("#0e382e 0%", CSS, "old gradient remains")

    def test_links_and_typography_remain_readable(self):
        for value in ("color:#f9fafb", "color:#c9d0d4", "color:#b7c0c5", "color:#ffae70"):
            self.assertIn(value, CSS)
        self.assertIn('.cr3-footer-bottom{border-top:1px solid #343a40', CSS)
        self.assertIn('background:linear-gradient(90deg,rgba(7,9,11,.97)', CSS)

    def test_white_footer_wordmark_and_registration_remain(self):
        self.assertIn('cape-ranch-footer-logo.webp', HTML)
        self.assertIn('class="cr3-footer"', HTML)
        self.assertIn('href="/login"', HTML)
        self.assertIn('href="/register-organization"', HTML)
        self.assertIn('href="/staff-recovery"', HTML)
        self.assertTrue((ROOT / 'frontend/public/images/landing-v3/cape-ranch-footer-logo.webp').is_file())

    def test_css_cache_busted_but_js_untouched(self):
        self.assertIn('landing-v3.css?v=3.2.0', HTML)
        self.assertIn('landing-v3.js?v=3.1.0', HTML)
        self.assertIn('@media(max-width:620px)',CSS)
        self.assertIn('prefers-reduced-motion:reduce',CSS)

if __name__ == '__main__':
    unittest.main()
