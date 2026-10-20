import base64
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
hub=load('pan_hub_auth','pan/hub_auth.py')
media=load('media_hub_identity','media/hub_identity.py')
class HubIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.secret=Path(self.tmp.name)/'shared';self.secret.write_text('a'*64)
        self.environment=patch.dict(os.environ,{'HUB_MODE':'1','HUB_SECRET_FILE':str(self.secret),'NASTOOL_CONFIG':str(Path(self.tmp.name)/'media/config.yaml')})
        self.environment.start();self.addCleanup(self.environment.stop)
        hub.shared_secret.cache_clear();media.shared_secret.cache_clear()
    def test_primary_login_is_required_even_with_gateway_key(self):
        state={'logged':False};app=Flask(__name__);hub.install(app,lambda:state['logged'],lambda:'原后台账号');client=app.test_client()
        self.assertEqual(client.get('/internal/hub-auth').status_code,403)
        self.assertEqual(client.get('/internal/hub-auth',headers={'X-Hub-Token':'a'*64}).status_code,401)
        state['logged']=True
        reply=client.get('/internal/hub-auth',headers={'X-Hub-Token':'a'*64})
        self.assertEqual(reply.status_code,200)
        self.assertEqual(base64.urlsafe_b64decode(reply.headers['X-Hub-User']).decode(),'原后台账号')
    def test_gateway_identity_is_verified_and_maps_without_account_mutation(self):
        app=Flask(__name__)
        user=base64.urlsafe_b64encode('original-login'.encode()).decode()
        with app.test_request_context('/',headers={'X-Hub-User':user}):self.assertIsNone(media.identity(__import__('flask').request))
        with app.test_request_context('/',headers={'X-Hub-Token':'wrong','X-Hub-User':user}):self.assertIsNone(media.identity(__import__('flask').request))
        with app.test_request_context('/',headers={'X-Hub-Token':'a'*64,'X-Hub-User':user}):
            identity=media.identity(__import__('flask').request);self.assertEqual(identity.username,'original-login');self.assertTrue(identity.is_authenticated)
    def test_media_session_key_is_stable_and_cookie_names_are_separate(self):
        a,b=Flask('a'),Flask('b');media.configure_session(a);media.configure_session(b)
        self.assertEqual(a.secret_key,b.secret_key);self.assertEqual(a.config['SESSION_COOKIE_NAME'],'film_index_session')
        self.assertNotEqual(a.config['SESSION_COOKIE_NAME'],'film_hub_session')
    def test_unified_guard_rejects_local_login_and_account_editor(self):
        from flask_login import LoginManager
        app=Flask(__name__);media.configure_session(app);manager=LoginManager(app);media.install(app,manager)
        app.add_url_rule('/users','users',lambda:'no');app.add_url_rule('/library','library',lambda:'yes')
        client=app.test_client();self.assertEqual(client.get('/library').status_code,401)
        headers={'X-Hub-Token':'a'*64,'X-Hub-User':base64.urlsafe_b64encode(b'admin').decode()}
        self.assertEqual(client.get('/users',headers=headers).status_code,403);self.assertEqual(client.get('/library',headers=headers).status_code,200)
    def test_file_browser_does_not_connect_to_pt_clients(self):
        import ast
        tree=ast.parse((ROOT/'media/web/main.py').read_text(encoding='utf8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='mediafile')
        function.decorator_list=[]
        args=type('Args',(),{'get':lambda self,name: None})()
        scope={'request':type('Request',(),{'args':args})(),'render_template':lambda name,**kwargs:kwargs}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'mediafile','exec'),scope)
        self.assertEqual(scope['mediafile']()['Dir'],'/media')

if __name__=='__main__':unittest.main()
