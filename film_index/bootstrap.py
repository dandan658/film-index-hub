"""Prepare existing data in place, preserving primary accounts and task history."""
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
from datetime import datetime, timezone

VERSION = '3.0.1'


def prepare(data_dir):
    root = Path(data_dir).resolve()
    for name in ('config', 'media', 'log'):
        (root / name).mkdir(parents=True, exist_ok=True)
    from film_index.backup import restore_pending
    restore_pending(root)
    config = root / 'config/config.json'
    if config.exists():
        # Invalid existing data must stop startup rather than reset the user's tasks.
        json.loads(config.read_text(encoding='utf8'))
    else:
        template = Path(__file__).parent / 'templates/config.template.json'
        value = json.loads(template.read_text(encoding='utf8'))
        value.setdefault('auth', {})['users'] = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(24)
        value['auth']['password'] = password
        with config.open('x', encoding='utf8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        config.chmod(0o600)
        if not os.environ.get('ADMIN_PASSWORD'):
            print('Initial admin password: ' + password, flush=True)
    secret = root / 'config/.session-secret'
    if not secret.exists():
        with secret.open('x', encoding='utf8') as handle:
            handle.write(secrets.token_hex(32))
        secret.chmod(0o600)
    os.environ['FLASK_SECRET_KEY'] = secret.read_text(encoding='utf8').strip()
    os.environ['NASTOOL_CONFIG'] = str(root / 'media/config.yaml')
    if (root / 'media/config.yaml').exists():
        from ruamel.yaml import YAML
        value = YAML(typ='safe').load((root / 'media/config.yaml').read_text(encoding='utf8'))
        if not isinstance(value, dict) or not isinstance(value.get('app'), dict):
            raise ValueError('原媒体 config.yaml 无效；已停止启动，不会用默认配置覆盖')
    os.environ['NASTOOL_LOG'] = str(root / 'log/media')
    os.environ.setdefault('TZ', 'Asia/Shanghai')
    os.environ['FILM_INDEX_DATA'] = str(root)
    os.chdir(root)
    return root


def snapshot_before_upgrade(root):
    """Make one consistent backup of critical data for each application upgrade."""
    marker = root / '.film-index-version'
    if marker.exists() and marker.read_text(encoding='utf8').strip() == VERSION:
        return
    target = root / 'backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-before-' + VERSION)
    target.mkdir(parents=True)
    shutil.copytree(root / 'config', target / 'config')
    media_target = target / 'media'
    media_target.mkdir()
    for source in (root / 'media').iterdir():
        if not source.is_file():
            continue
        if source.suffix == '.db':
            # Includes committed WAL changes; file copying a live SQLite DB does not.
            with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as original:
                with sqlite3.connect(media_target / source.name) as backup:
                    original.backup(backup)
        elif source.name == 'config.yaml' or source.suffix in ('.json', '.pkl', '.pickle', '.dat'):
            shutil.copy2(source, media_target / source.name)
    print('Configuration backup: ' + str(target), flush=True)
    # Written after the entire application starts, by mark_started().
    return marker


def mark_started(root):
    temporary = root / '.film-index-version.tmp'
    temporary.write_text(VERSION + '\n', encoding='utf8')
    os.replace(temporary, root / '.film-index-version')

