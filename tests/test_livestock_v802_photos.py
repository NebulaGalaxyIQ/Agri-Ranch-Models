"""Livestock & Poultry V8.0.2: exactly one image per section, no duplicate bytes."""
from pathlib import Path
import hashlib,re

ROOT=Path(__file__).resolve().parents[1]
NAMES='overview projects groups animals houses routine breeding health weights production incubations products costs sales product_sales performance'.split()


def test_livestock_v802_photo_assets():
    page=(ROOT/'frontend/pages/livestock/index.js').read_text(encoding='utf8')
    folder=ROOT/'frontend/public/images/v65/livestock'
    assert "livestockDirectory('Livestock & Poultry'" in page
    assert 'v=8.3.0' in page
    digests=[]
    for name in NAMES:
        assert re.search(r"\['"+re.escape(name)+r"','",page), name
        img=folder/f'{name}.webp'
        blob=img.read_bytes()
        assert len(blob)>10000,(name,len(blob))
        assert blob[0:4]==b'RIFF' and blob[8:12]==b'WEBP',name
        digests.append(hashlib.sha256(blob).digest())
    assert len(set(digests))==len(NAMES), 'At least two section photos are duplicated'
