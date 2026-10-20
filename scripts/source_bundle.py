from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
with zipfile.ZipFile(ROOT/'source-bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in ROOT.rglob('*'):
        rel=path.relative_to(ROOT)
        if not path.is_file() or any(p in ('.git','data','node_modules','__pycache__','dist') for p in rel.parts) or path.name in ('.env','source-bundle.zip') or path.suffix=='.pyc':continue
        archive.write(path,'Film-Index-Hub/'+rel.as_posix())
