"""Initialize persistent configuration, then replace this process with the server."""
import json
import os
from pathlib import Path
import secrets
import sys


def initialize(root=Path('.')):
    if os.environ.get('HUB_MODE') == '1':
        shared_path = Path(os.environ['HUB_SECRET_FILE'])
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        if not shared_path.exists():
            with shared_path.open('x', encoding='utf8') as handle:
                handle.write(secrets.token_hex(32))
            shared_path.chmod(0o600)
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    (root / 'log').mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.json'
    if not config_path.exists():
        config = json.loads((root / 'template/config.template.json').read_text(encoding='utf-8'))
        config['auth']['users'] = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(24)
        config['auth']['password'] = password
        with config_path.open('x', encoding='utf-8') as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        config_path.chmod(0o600)
        if not os.environ.get('ADMIN_PASSWORD'):
            print(f'Initial admin password: {password}', flush=True)
    # Validate existing data; never replace a broken configuration silently.
    json.loads(config_path.read_text(encoding='utf-8'))
    secret_path = config_dir / '.session-secret'
    if not secret_path.exists():
        with secret_path.open('x', encoding='utf-8') as handle:
            handle.write(secrets.token_hex(32))
        secret_path.chmod(0o600)
    os.environ['FLASK_SECRET_KEY'] = secret_path.read_text(encoding='utf-8').strip()


if __name__ == '__main__':
    os.umask(0o077)
    initialize()
    os.execv(sys.executable, [sys.executable, 'web_app.py'])
