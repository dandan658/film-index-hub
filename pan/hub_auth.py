"""Private gateway authorization using the existing Baidu backend accounts."""
import base64
import hmac
import os
from functools import lru_cache
from pathlib import Path
from flask import request, make_response

@lru_cache(maxsize=1)
def shared_secret():
    return Path(os.environ['HUB_SECRET_FILE']).read_text(encoding='utf8').strip()

def install(app, valid_session, username):
    @app.route('/internal/hub-auth')
    def hub_authorize():
        if os.environ.get('HUB_MODE') != '1':
            return '', 404
        token = request.headers.get('X-Hub-Token', '')
        if not token or not hmac.compare_digest(token, shared_secret()):
            return '', 403
        if not valid_session():
            return '', 401
        response = make_response('', 200)
        response.headers['X-Hub-User'] = base64.urlsafe_b64encode(username().encode('utf8')).decode('ascii')
        response.headers['Cache-Control'] = 'no-store'
        return response
