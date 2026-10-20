"""Durable, task-owned transfer memory independent of cloud destination paths."""
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
from urllib.parse import urlsplit, urlunsplit

_lock = threading.RLock()
_deleted = set()


def history_path(uid):
    return Path('config/history') / (hashlib.sha256(str(uid).encode()).hexdigest() + '.json')


def source_key(source, share_url):
    size, md5 = source.get('size', 0), source.get('md5')
    if md5:
        identity = f'md5:{str(md5).lower()}:{size}'
    else:
        url = urlsplit(share_url)
        canonical = urlunsplit((url.scheme, url.netloc, url.path, '', ''))
        identity = f'id:{canonical}:{source["fs_id"]}:{size}'
    return hashlib.sha256(identity.encode()).hexdigest()


class TaskHistory:
    def __init__(self, uid, share_url):
        self.uid, self.share_url = str(uid), share_url
        self.path = history_path(uid)
        with _lock:
            self.data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'entries': {}, 'organized_files': []}

    @property
    def deleted(self):
        return self.uid in _deleted

    def contains(self, source):
        return source_key(source, self.share_url) in self.data['entries']

    def _save(self):
        if self.deleted:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('w', encoding='utf-8') as handle:
                json.dump(self.data, handle, ensure_ascii=False)
            os.replace(temporary, self.path)
        finally:
            if temporary.exists(): temporary.unlink()

    def remember(self, source, destination):
        with _lock:
            if self.deleted: return
            self.data['entries'][source_key(source, self.share_url)] = {
                'fs_id': source['fs_id'], 'size': source.get('size'), 'md5': source.get('md5'), 'path': destination,
            }
            self._save()

    def register_organized(self, path):
        with _lock:
            if str(path) not in self.data['organized_files']:
                self.data['organized_files'].append(str(path))
                self._save()


def delete_task_history(uid):
    if not uid:
        return
    with _lock:
        _deleted.add(str(uid))
        path = history_path(uid)
        if not path.exists(): return
        state = json.loads(path.read_text(encoding='utf-8'))
        organized_root = Path('config/organized').resolve()
        for name in state.get('organized_files', []):
            candidate = Path(name).resolve()
            if candidate.parent == organized_root and candidate.suffix == '.json' and candidate.exists():
                candidate.unlink()
        path.unlink()
