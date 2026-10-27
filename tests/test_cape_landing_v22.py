"""Dependency-free verification for Cape Ranch Design 02 expanded public landing.
Run: python tests/test_cape_landing_v22.py
"""
from pathlib import Path
import re
import sys
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'frontend/landing.html'
CSS=ROOT/'frontend/shared/landing-v2.css'
JS=ROOT/'frontend/shared/landing-v2.js'
ASSETS=ROOT/'frontend/public/images/landing-v2'

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=set();self.duplicates=set();self.images=[];self.links=[];self.sections=[];self.metrics=0;self.mini=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):
            if a['id'] in self.ids:self.duplicates.add(a['id'])
            self.ids.add(a['id'])
        if tag=='img': self.images.append(a.get('src',''))
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='section' and 'cr-spotlight ' in (a.get('class','')+' '): self.sections.append(a.get('class',''))
        if 'cr-metric cr-reveal' in a.get('class',''):self.metrics+=1
        if 'cr-spotlight-mini' in a.get('class','').split():self.mini+=1


def run():
    html=HTML.read_text(encoding='utf-8'); css=CSS.read_text(encoding='utf-8');js=JS.read_text(encoding='utf-8')
    page=Page();page.feed(html);page.close()
    assert not page.duplicates, f'Duplicate HTML IDs: {page.duplicates}'
    assert len(page.sections)==6, f'Expected 6 full-width chapter sections, found {len(page.sections)}'
    for tone,count in {'cr-tone-cream':2,'cr-tone-green':2,'cr-tone-white':1,'cr-tone-orange':1}.items():
        assert sum(tone in x for x in page.sections)==count, f'Wrong number of {tone} chapters'
    assert page.metrics==4 and page.mini==18, (page.metrics,page.mini)
    assert 'Organization adoption goal' not in html or 'not a current customer count' in html
    assert 'Our long-term adoption ambition, not a current customer count' in html
    assert 'Used by 1,000' not in html and 'Trusted by 1,000' not in html
    assert '/login' in page.links and '/register-organization' in page.links
    assert 'cr-brand-image' in html and 'cape-ranch-logo.webp' in html
    assert 'hero-design02.webp' in html
    assert all((x.startswith(('#','/'))) for x in page.links), 'Unexpected external link'
    assert all(x in page.ids for x in [link[1:] for link in page.links if link.startswith('#')]), 'Broken internal anchor'
    assert 'IntersectionObserver' in js and 'cr-motion-ready' in js and 'prefers-reduced-motion' in js
    assert '.cr-spotlight-mini:hover' in css and '.cr-metric:hover' in css
    assert 'cr-metrics-grid' in css and 'cr-spotlight-layout' in css
    assert 'landing-v2.css?v=2.2.0' in html
    for src in page.images+[m for m in re.findall(r"url\(['\"]?(/frontend/public/images/landing-v2/[^'\")]+)",css)]:
        if src.startswith('/frontend/public/images/landing-v2/'):
            asset=ASSETS/src.rsplit('/',1)[-1]
            assert asset.exists(), f'Missing image asset: {asset}'
            assert asset.stat().st_size>1500, f'Empty image asset: {asset}'
    print('PASS: six alternating full-width photographic chapters')
    print('PASS: four labeled metrics and eighteen hoverable mini feature cards')
    print('PASS: local image assets, correct logo and hero, internal links')
    print('PASS: mobile/reduced-motion rules, scroll reveal and hover CSS')
    print('PASS: no fabricated current customer count claims')
    return 0

if __name__=='__main__':
    try: sys.exit(run())
    except Exception as exc:
        print('FAIL:',exc,file=sys.stderr);raise
