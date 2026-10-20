"""Gateway identity for the integrated edition; no second account database login."""
import base64
import hmac
import os
import secrets
from pathlib import Path
from functools import lru_cache
from flask import request
from flask_login import UserMixin

def enabled():
    return os.environ.get('HUB_MODE') == '1'

def configure_session(app):
    directory = Path(os.environ.get('NASTOOL_CONFIG', '/config/config.yaml')).parent
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.film-session-secret'
    if not path.exists():
        with path.open('x', encoding='utf8') as handle:
            handle.write(secrets.token_hex(32))
        path.chmod(0o600)
    app.secret_key = path.read_text(encoding='utf8').strip()
    app.config.update(SESSION_COOKIE_NAME='film_index_session', REMEMBER_COOKIE_NAME='film_index_remember',
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

@lru_cache(maxsize=1)
def shared_secret():
    return Path(os.environ['HUB_SECRET_FILE']).read_text(encoding='utf8').strip()

class HubUser(UserMixin):
    def __init__(self, username):
        self.id = 'hub:' + username
        self.username = username
        self.pris = '媒体整理,服务,系统设置'

def identity(req):
    if not enabled():
        return None
    token = req.headers.get('X-Hub-Token', '')
    if not token or not hmac.compare_digest(token, shared_secret()):
        return None
    try:
        user = base64.b64decode(req.headers.get('X-Hub-User', ''), altchars=b'-_', validate=True).decode('utf8')
    except (ValueError, UnicodeError):
        return None
    return HubUser(user) if user and len(user) <= 256 else None

def install(app, login_manager):
    @login_manager.request_loader
    def load_hub_request(req):
        return identity(req)
    @app.before_request
    def unified_identity_required():
        if not enabled() or request.path.startswith('/static/') or request.path in ('/profile-info', '/project-source.zip'):
            return None
        if identity(request) is None:
            return {'success': False, 'message': '请从统一工作台登录'}, 401
        if request.path in ('/users', '/api/v1/user/login') or (request.path == '/do' and request.form.get('cmd') in ('user_manager', 'restart')):
            return {'success': False, 'message': '账号和重启操作请在统一工作台管理'}, 403
