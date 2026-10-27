"""Smoke checks for the standalone public Cape Ranch landing.
Does not require database credentials or modify any database.
Run: python -m pytest -q tests/test_landing_v2.py
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'


def test_landing_files_and_image_paths():
    html = (FRONTEND / 'landing.html').read_text(encoding='utf-8')
    js = (FRONTEND / 'shared/landing-v2.js').read_text(encoding='utf-8')
    css = (FRONTEND / 'shared/landing-v2.css').read_text(encoding='utf-8')
    assert '<main id="main">' in html
    for value in ['href="/login"', 'href="/register-organization"', 'id="features"',
                  'id="platform"', 'id="how-it-works"', 'id="questions"']:
        assert value in html
    assert 'location.replace(\'/app\')' in js
    assert '@media(max-width:600px)' in css
    for ref in re.findall(r'(?:src|href)="(/frontend/public/images/landing-v2/[^\"]+)"', html):
        path = ROOT / ref.lstrip('/')
        assert path.is_file() and path.stat().st_size > 100, f'Missing landing photo: {ref}'
    assert len(re.findall(r'class="cr-feature cr-reveal"', html)) >= 8


def test_public_and_app_routes_are_separate():
    main = (ROOT / 'backend/main.py').read_text(encoding='utf-8')
    assert "FileResponse(FRONTEND/'landing.html')" in main
    assert "@app.get('/login',include_in_schema=False)" in main
    assert "@app.get('/app',include_in_schema=False)" in main
    assert "FileResponse(FRONTEND/'index.html')" in main
