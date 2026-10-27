"""Cape Ranch V3.1 public copy and branding regression checks; stdlib only."""
from pathlib import Path
from html.parser import HTMLParser
import re, unittest
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'frontend/landing.html').read_text('utf-8')
CSS=(ROOT/'frontend/shared/landing-v3.css').read_text('utf-8')
JS=(ROOT/'frontend/shared/landing-v3.js').read_text('utf-8')
class Tags(HTMLParser):
 def __init__(self): super().__init__();self.images=[];self.links=[];self.h1=[];self.in_h1=False
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=='img':self.images.append(a)
  if t=='a':self.links.append(a.get('href'))
  if t=='h1':self.in_h1=True
 def handle_endtag(self,t):
  if t=='h1':self.in_h1=False
 def handle_data(self,s):
  if self.in_h1:self.h1.append(s)
class LandingV31(unittest.TestCase):
 def test_hero_explains_capabilities_and_outcome(self):
  p=Tags();p.feed(HTML)
  title=' '.join(p.h1)
  for w in ('Ranching, Crops','Animal Fattening','Other Farming Models','All in One Place'):
   self.assertIn(w,title)
  for w in ('scattered records','manual follow-ups','costs','Track daily work','reliable operational data'):
   self.assertIn(w,HTML)
  self.assertNotIn('beautifully connected workspace',HTML.lower())
 def test_metric_is_capability_not_unverified_customer_count(self):
  self.assertIn('50<span>+</span>',HTML)
  self.assertIn('Trackable data fields',HTML)
  self.assertNotIn('Unified workspace</b>',HTML)
  self.assertIn('future adoption goal',HTML.lower())
 def test_photo_captions_no_numbers(self):
  self.assertNotIn('cr3-image-label',HTML)
  self.assertNotIn('.cr3-image-label{',CSS)
  self.assertEqual(HTML.count('class="cr3-band-visual cr3-reveal"'),6)
 def test_dark_footer_original_brand_retained(self):
  self.assertIn('background:radial-gradient(',CSS)
  self.assertIn('#072b25',CSS)
  self.assertIn('cape-ranch-footer-logo.webp',HTML)
  p=Tags();p.feed(HTML)
  names=[a['src'].rsplit('/',1)[-1] for a in p.images]
  self.assertIn('cape-ranch-logo.webp',names)
  self.assertIn('cape-ranch-footer-logo.webp',names)
  f=ROOT/'frontend/public/images/landing-v3/cape-ranch-footer-logo.webp'
  self.assertTrue(f.exists())
  self.assertEqual(f.read_bytes()[:4],b'RIFF')
  self.assertEqual(f.read_bytes()[8:12],b'WEBP')
 def test_nav_and_auth_preserved(self):
  p=Tags();p.feed(HTML)
  for route in ['/login','/register-organization','/staff-recovery']:
   self.assertIn(route,p.links)
  self.assertIn('IntersectionObserver',JS)
  self.assertIn('landing-v3.js?v=3.1.0',HTML)
if __name__=='__main__':unittest.main()
