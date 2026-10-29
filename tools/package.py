#!/usr/bin/env python3
"""Package only the Home Assistant component for manual installation."""
import json
import os
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
component = root / 'custom_components' / 'kitchen_dashboard'
version = json.loads((component / 'manifest.json').read_text())['version']
tag = os.environ.get('RELEASE_TAG')
if tag and tag != f'v{version}':
    raise SystemExit('Release tag does not match integration version')
output = root / 'dist' / 'kitchen_dashboard.zip'
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            archive.write(path, path.relative_to(component.parent))
print(f'Built integration {version}: {output}')
