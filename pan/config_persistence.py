"""Serialize complete configurations atomically without truncating existing data."""
import json
import os
from pathlib import Path
import tempfile
import threading

write_lock = threading.RLock()


def atomic_write_config(config, path='config/config.json'):
    path = Path(path)
    with write_lock:
        payload = json.dumps(config, ensure_ascii=False, indent=4)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.config-', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
