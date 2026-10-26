"""V8.3.0 regression: a newly loaded page must not reuse an old service.js."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_livestock_v802_cache_contract():
    page = (ROOT / 'frontend/pages/livestock/index.js').read_text(encoding='utf-8')
    service = (ROOT / 'frontend/pages/livestock/service.js').read_text(encoding='utf-8')
    shell = (ROOT / 'frontend/shared/app.js').read_text(encoding='utf-8')
    html = (ROOT / 'frontend/index.html').read_text(encoding='utf-8')
    assert "import * as api from './service.js?v=8.3.0'" in page
    assert 'export const workspace=' in service
    assert 'api.workspace(),api.connectedContext()' in page
    assert shell.count("name==='livestock'?'8.3.0'") == 2
    assert re.search(r'/frontend/shared/app\.js\?v=8\.3\.0', html)
