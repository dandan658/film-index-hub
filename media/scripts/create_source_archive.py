"""Bundle project source; never include mounted configuration or media data."""
from pathlib import Path
import json
import sys
import zipfile

EXCLUDED = {'.git', '.github', '__pycache__', 'data', 'media', 'windows'}


def create(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        manifest = root / 'SOURCE_FILES.json'
        paths = [root / name for name in json.loads(manifest.read_text(encoding='utf8'))] if manifest.is_file() else sorted(root.rglob('*'))
        for path in paths:
            relative = path.relative_to(root)
            if (not path.is_file() or any(part in EXCLUDED for part in relative.parts)
                    or path.suffix in ('.pyc', '.zip') or path.name == '.env' or path == target):
                continue
            archive.write(path, 'Film-and-Television-Index/' + relative.as_posix())


if __name__ == '__main__': create(sys.argv[1], sys.argv[2])
