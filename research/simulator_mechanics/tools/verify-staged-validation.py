"""Check index blob bytes against raw catalogs before cross-platform publication."""
import hashlib
import io
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'results/simulator_research/validation-2026-11-01'
catalog=json.loads((R/'analysis-final/raw-sha256.json').read_text())
checks={(R/name).relative_to(ROOT).as_posix():expected for name,expected in catalog.items()}
verification=json.loads((R/'verification.json').read_text())
checks.update({(R/'native-v05'/name).relative_to(ROOT).as_posix():expected for name,expected in verification['native_image_hashes'].items()})
manifest=json.loads((R/'real-data-raw/manifest.json').read_text())
checks[(R/'real-data-raw/raw.jsonl.gz').relative_to(ROOT).as_posix()]=manifest['raw_sha256']
request=''.join(':'+name+'\n' for name in checks).encode()
response=subprocess.run(['git','cat-file','--batch'],input=request,stdout=subprocess.PIPE,check=True,cwd=ROOT).stdout
stream=io.BytesIO(response)
for name,expected in checks.items():
    header=stream.readline().decode().split()
    assert len(header)==3 and header[1]=='blob',(name,header)
    data=stream.read(int(header[2]));assert stream.read(1)==b'\n'
    assert hashlib.sha256(data).hexdigest()==expected,name
print(f'Exact staged evidence hashes: {len(checks)}/{len(checks)} match')
