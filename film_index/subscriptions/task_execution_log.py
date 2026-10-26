"""Small, durable per-task execution log for manual and scheduled runs."""
import hashlib
import json
from pathlib import Path
from threading import RLock

_lock = RLock()
_root = Path('config/task-logs')
_max_entries = 1000


def _path(task_uid):
    digest = hashlib.sha256(str(task_uid).encode('utf-8')).hexdigest()
    return _root / f'{digest}.jsonl'


def read(task_uid, limit=300):
    if not task_uid:
        return []
    with _lock:
        path = _path(task_uid)
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding='utf-8').splitlines()[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


def append(task_uid, entry):
    if not task_uid:
        return
    with _lock:
        path = _path(task_uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
        if path.stat().st_size > 1024 * 1024:
            lines = path.read_text(encoding='utf-8').splitlines()[-_max_entries:]
            temporary = path.with_suffix('.tmp')
            temporary.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            temporary.replace(path)
