"""Standard-library-only regression checks for Design 02 refinement.
Run with: python tests/test_landing_v2_refinement.py
"""
from pathlib import Path
import re
import unittest
import struct

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'frontend/landing.html'
CSS = ROOT / 'frontend/shared/landing-v2.css'
JS = ROOT / 'frontend/shared/landing-v2.js'
PHOTO = ROOT / 'frontend/public/images/landing-v2/hero.webp'
LOGO = ROOT / 'frontend/public/images/landing-v2/cape-ranch-logo.webp'

class LandingRefinementTest(unittest.TestCase):
    def test_essential_assets_and_links(self):
        html=HTML.read_text(encoding='utf-8')
        self.assertIn('cape-ranch-logo.webp',html)
        self.assertIn('cr-brand-image',html)
        self.assertNotIn('viewBox="0 0 44 38"',html, 'Old placeholder logo must be gone')
        for t in ('href="/login"','href="/register-organization"','id="solutions"','id="features"','id="platform"','id="questions"','id="how-it-works"'):
            self.assertIn(t,html)
        self.assertEqual(len(re.findall(r'class="cr-feature cr-reveal"',html)),8)
        self.assertEqual(len(re.findall(r'class="cr-solution cr-reveal"',html)),4)
        for ref in re.findall(r'(?:src|href)="(/frontend/public/images/landing-v2/[^"?]+)',html):
            # Existing feature photos are retained from the already-installed V2 package.
            if ref.endswith('/cape-ranch-logo.webp'):
                self.assertTrue((ROOT/ref.lstrip('/')).is_file(),ref)
    def test_hero_and_brand_resolution(self):
        for f in (PHOTO, LOGO):
            self.assertGreater(f.stat().st_size,5000)
            self.assertEqual(f.read_bytes()[:4], b"RIFF")
            self.assertEqual(f.read_bytes()[8:12], b"WEBP")
        self.assertIn(b"WEBP", PHOTO.read_bytes()[:20])
    def test_scroll_reveal_and_hover(self):
        css=CSS.read_text(encoding='utf-8')
        js=JS.read_text(encoding='utf-8')
        self.assertIn('cr-motion-ready .cr-reveal',css)
        self.assertIn('cr-motion-ready .cr-reveal.cr-visible',css)
        self.assertIn('cr-feature:hover',css)
        self.assertIn('cr-solution:hover',css)
        self.assertIn('IntersectionObserver',js)
        self.assertIn("observer.unobserve(entry.target)",js)
        self.assertRegex(css, r'prefers-reduced-motion:\s*reduce')
        self.assertNotIn('.cr-js .cr-reveal:not(.cr-visible){opacity:1;transform:none}',css)
    def test_preserves_isolated_login_and_public_page(self):
        html=HTML.read_text(encoding='utf-8')
        js=JS.read_text(encoding='utf-8')
        self.assertIn('data-tour',html)
        self.assertIn("location.replace('/app')",js)
        self.assertIn('cr-tour-dialog',html)
        self.assertNotIn('type="submit"',html, 'No standalone auth forms in public marketing page')

if __name__ == '__main__':
    unittest.main(verbosity=2)
