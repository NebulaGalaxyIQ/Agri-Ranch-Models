"""Cape Ranch public landing V3: no pytest or third-party dependency required.
Usage: python -m unittest discover -s tests -p test_cape_landing_v3.py -v
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'frontend/landing.html';CSS=ROOT/'frontend/shared/landing-v3.css';JS=ROOT/'frontend/shared/landing-v3.js'
ASSETS=ROOT/'frontend/public/images/landing-v3'

class Elements(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=[];self.images=[];self.links=[];self.classes=[];self.tags=[]
    def handle_starttag(self,tag,attrs):
        x=dict(attrs);self.tags.append(tag)
        if 'id' in x:self.ids.append(x['id'])
        if tag=='img':self.images.append(x)
        if tag=='a':self.links.append(x.get('href',''))
        self.classes.extend(x.get('class','').split())

class LandingV3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text('utf-8');cls.css=CSS.read_text('utf-8');cls.js=JS.read_text('utf-8');cls.page=Elements();cls.page.feed(cls.html)
    def test_routes_and_accessible_navigation(self):
        p=self.page
        self.assertEqual(len(p.ids),len(set(p.ids)),'Duplicate element IDs')
        for route in ('/login','/register-organization','/staff-recovery'):
            self.assertIn(route,p.links)
        for url in p.links:
            self.assertTrue(url.startswith(('#','/')),url)
            if url.startswith('#'):
                self.assertIn(url[1:],p.ids,'Broken internal jump link')
        self.assertIn('aria-expanded',self.html)
        self.assertIn('cr3-skip',p.classes)
        self.assertIn('Cape Ranch',self.html)
    def test_compact_design_01_03_06_combination(self):
        self.assertEqual(self.page.classes.count('cr3-tab'),6)
        self.assertEqual(self.page.classes.count('cr3-band'),6)
        self.assertEqual(self.page.classes.count('cr3-mini'),18)
        self.assertEqual(self.page.classes.count('cr3-metric'),4)
        for color in ('cream','white','dark','orange'):
            self.assertIn('cr3-band-'+color,self.page.classes)
        self.assertIn('.cr3-tab{height:134px',self.css)
        self.assertIn('.cr3-band-visual{height:266px',self.css)
        self.assertIn('cr3-ui-showcase',self.html)
        self.assertIn('cr3-faq',self.page.classes)
    def test_real_photos_and_logo_not_small_v2_thumbnails(self):
        images=[a['src'] for a in self.page.images]
        self.assertIn('/frontend/public/images/landing-v3/cape-ranch-logo.webp',images)
        self.assertIn('hero-rancher.webp',self.css)
        self.assertIn('hero-rancher.webp',self.html)
        self.assertNotIn('/landing-v2/',self.html+self.css+self.js)
        photo_names=('hero-rancher','livestock-landscape','crops-landscape','gardening-landscape','finance-landscape','machinery-landscape','team-landscape','routines-landscape','analytics-landscape')
        for name in photo_names:
            path=ASSETS/(name+'.webp')
            self.assertTrue(path.is_file(),str(path))
            self.assertGreater(path.stat().st_size,60000,str(path))
            self.assertEqual(path.read_bytes()[:4],b'RIFF',str(path))
            self.assertEqual(path.read_bytes()[8:12],b'WEBP',str(path))
        for a in self.page.images:
            if a['src'].startswith('/frontend/public/images/landing-v3/'):
                self.assertTrue((ASSETS/a['src'].split('/')[-1]).exists(),a['src'])
    def test_scroll_reveal_responsive_and_genuine_metrics(self):
        self.assertIn('IntersectionObserver',self.js)
        self.assertIn('prefers-reduced-motion',self.js)
        self.assertIn('cr3-waiting',self.css)
        self.assertIn('cr3-is-visible',self.js)
        self.assertIn('.cr3-tab:hover',self.css)
        self.assertIn('@media(max-width:620px)',self.css)
        self.assertIn('future adoption goal',self.html.lower())
        self.assertNotIn('Trusted by 1,000',self.html)
        self.assertNotIn('used by 1,000',self.html.lower())
        self.assertIn('Illustrative preview — not live data',self.html)
        self.assertNotIn('fonts.googleapis.com',self.css)
    def test_auth_app_is_not_modified_by_v3(self):
        # V3 is scoped to public landing; the script verifies server routing
        # before publishing instead of overwriting auth/backend files.
        self.assertNotIn('loginPage(',self.js)
        self.assertNotIn('localStorage.setItem',self.js)
        self.assertIn("location.replace('/app')",self.js)

if __name__=='__main__':unittest.main()
