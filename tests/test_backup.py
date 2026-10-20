from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile
from film_index.backup import export_backup, validate_backup, restore_pending

class BackupTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'config/history').mkdir(parents=True)
        (root / 'media').mkdir()
        (root / 'config/config.json').write_text(json.dumps({'auth': {'users': 'original'}, 'tasks': ['task-uid']}))
        (root / 'config/history/memory.json').write_text('{"md5":"retained"}')
        (root / 'config/.session-secret').write_text('original-secret')
        with closing(sqlite3.connect(root / 'media/media.db')) as db:
            db.execute('CREATE TABLE history (name TEXT)')
            db.execute("INSERT INTO history VALUES ('retained')")
            db.commit()

    def test_round_trip_and_rollback_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            payload = export_backup(root).getvalue()
            meta = validate_backup(payload)
            self.assertIn('config/history/memory.json', meta['files'])
            (root / 'config/config.json').write_text('{"auth":{"users":"changed"}}')
            (root / '.restore-pending.zip').write_bytes(payload)
            restore_pending(root)
            self.assertEqual(json.loads((root / 'config/config.json').read_text())['auth']['users'], 'original')
            self.assertEqual((root / 'config/.session-secret').read_text(), 'original-secret')
            self.assertFalse((root / '.restore-pending.zip').exists())
            self.assertEqual(len(list((root / 'backups').glob('*.zip'))), 1)
            with closing(sqlite3.connect(root / 'media/media.db')) as db:
                self.assertEqual(db.execute('SELECT name FROM history').fetchone()[0], 'retained')

    def test_reject_tampered_and_traversal_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            payload = export_backup(root).getvalue()
            for name in ('config/config.json', '../escape'):
                output = io.BytesIO()
                with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(output, 'w') as target:
                    for item in source.infolist():
                        target.writestr(item.filename, b'changed' if item.filename == name else source.read(item.filename))
                    if name == '../escape': target.writestr(name, 'bad')
                with self.assertRaises(ValueError): validate_backup(output.getvalue())
