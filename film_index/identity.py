"""One backend identity, validated from the original subscription account store."""
import time
from flask import request, session
from flask_login import LoginManager, UserMixin


class WorkspaceUser(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username
        self.pris = '媒体整理,服务,系统设置'


def install(app, subscriptions):
    manager = LoginManager(app)
    manager.login_view = 'login'

    @manager.request_loader
    def account_for_request(req):
        if subscriptions.valid_login_session():
            return WorkspaceUser(session['username'])
        return None

    # Even an old Flask-Login cookie must validate the current primary account.
    @manager.user_loader
    def obsolete_user_cookie(user_id):
        return account_for_request(request)

    @app.before_request
    def protect_media():
        media_request = request.path.startswith(('/media-engine/', '/api/v1/')) or request.path == '/dirlist'
        if not media_request or request.endpoint == 'media.static':
            return None
        if not subscriptions.valid_login_session():
            return {'success': False, 'message': '登录已失效，请重新登录'}, 401
        session['login_time'] = time.time()
        if request.path in ('/media-engine/users', '/api/v1/user/login'):
            return {'success': False, 'message': '请在统一后台管理登录账号'}, 403
        if request.endpoint == 'spa_routes':
            return {'success': False, 'message': '接口不存在'}, 404

