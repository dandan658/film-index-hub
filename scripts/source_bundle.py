"""Build the complete public source bundle from an explicit file allowlist."""
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
names = json.loads((root / 'SOURCE_FILES.json').read_text(encoding='utf8'))
with zipfile.ZipFile(root / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in names:
        assert not any(part in ('data', 'node_modules', '.git', '__pycache__', 'dist') for part in Path(name).parts)
        assert Path(name).name != '.env'
        archive.write(root / name, 'Film-Index/' + name)
print('Public source files:', len(names))

