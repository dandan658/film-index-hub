import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

AVAILABLE = importlib.util.find_spec('baidupcs_py') is not None


@unittest.skipUnless(AVAILABLE, 'Real authentication API is verified inside the Docker image')
class BackendAccountApiTests(unittest.TestCase):
    def setUp(self):
        import web_app
        from storage import BaiduStorage
        self.web = web_app
        self.temp = tempfile.TemporaryDirectory(); self.previous = os.getcwd(); os.chdir(self.temp.name)
        Path('config/history').mkdir(parents=True)
        Path('config/history/keep.json').write_text('{"entries":{"already-saved":{}}}', encoding='utf8')
        self.store = BaiduStorage.__new__(BaiduStorage)
        self.original = {'auth': {'users': 'owner', 'password': 'original-pass', 'session_timeout': 3600},
                         'baidu': {'users': {'my-pan': {'cookies': 'fixture-only'}}, 'current_user': None,
                                   'tasks': [{'order': 1, 'task_uid': 'keep', 'name': '保留任务', 'url': 'fixture'}]}}
        self.store.config = copy.deepcopy(self.original)
        self.store._save_config(update_scheduler=False)
        self.store.list_tasks = lambda: self.store.config['baidu']['tasks']
        self.patch = patch.object(web_app, 'storage', self.store); self.patch.start()
        self.admin = web_app.app.test_client()
        self.assertEqual(self.login(self.admin, 'owner', 'original-pass').status_code, 200)

    def tearDown(self):
        self.patch.stop(); os.chdir(self.previous); self.temp.cleanup()

    def login(self, client, username, password): return client.post('/api/auth/login', json={'username': username, 'password': password})
    def add(self, username='member'):
        response = self.admin.post('/api/auth/accounts', json={'username': username, 'password': 'member-pass', 'current_password': 'original-pass'})
        self.assertTrue(response.json['success'], response.json)
    def assert_shared_data(self):
        self.assertEqual(self.store.config['baidu'], self.original['baidu'])
        self.assertEqual(json.loads(Path('config/config.json').read_text())['baidu'], self.original['baidu'])
        self.assertEqual(Path('config/history/keep.json').read_text(), '{"entries":{"already-saved":{}}}')

    def test_new_login_persists_and_old_form_and_api_logins_still_work(self):
        self.add()
        self.store.config = json.loads(Path('config/config.json').read_text())
        self.assertEqual(self.login(self.web.app.test_client(), 'member', 'member-pass').status_code, 200)
        self.assertEqual(self.login(self.web.app.test_client(), 'owner', 'original-pass').status_code, 200)
        self.assertEqual(self.web.app.test_client().post('/login', data={'username': 'member', 'password': 'member-pass'}).status_code, 200)
        self.assertEqual(self.store.config['auth']['password'], 'original-pass')
        self.assert_shared_data()

    def test_management_requires_login_and_current_password(self):
        stranger = self.web.app.test_client()
        self.assertEqual(stranger.get('/api/auth/accounts').status_code, 401)
        before = Path('config/config.json').read_bytes()
        response = self.admin.post('/api/auth/accounts', json={'username': 'member', 'password': 'member-pass', 'current_password': 'wrong'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Path('config/config.json').read_bytes(), before)

    def test_reset_revokes_only_target_sessions(self):
        self.add(); member = self.web.app.test_client(); self.login(member, 'member', 'member-pass')
        response = self.admin.post('/api/auth/accounts/member/password', json={'password': 'new-member-pass', 'current_password': 'original-pass'})
        self.assertTrue(response.json['success'])
        self.assertEqual(member.get('/api/tasks').status_code, 401)
        self.assertEqual(self.admin.get('/api/auth/check').status_code, 200)
        self.assertEqual(self.login(self.web.app.test_client(), 'member', 'member-pass').status_code, 401)
        self.assertEqual(self.login(self.web.app.test_client(), 'member', 'new-member-pass').status_code, 200)
        self.assert_shared_data()

    def test_delete_preserves_shared_data_and_protects_primary_and_self(self):
        self.add(); member = self.web.app.test_client(); self.login(member, 'member', 'member-pass')
        self.assertEqual(self.admin.delete('/api/auth/accounts/owner', json={'current_password': 'original-pass'}).status_code, 400)
        self.assertEqual(member.delete('/api/auth/accounts/member', json={'current_password': 'member-pass'}).status_code, 400)
        response = self.admin.delete('/api/auth/accounts/member', json={'current_password': 'original-pass'})
        self.assertTrue(response.json['success'])
        self.assertEqual(member.get('/api/auth/check').status_code, 401)
        self.assertEqual(self.login(self.web.app.test_client(), 'member', 'member-pass').status_code, 401)
        self.assertEqual(self.login(self.web.app.test_client(), 'owner', 'original-pass').status_code, 200)
        self.assert_shared_data()

    def test_new_account_can_change_only_own_password(self):
        self.add(); member = self.web.app.test_client(); other = self.web.app.test_client()
        self.login(member, 'member', 'member-pass'); self.login(other, 'member', 'member-pass')
        response = member.post('/api/auth/update', json={'username': 'member', 'old_password': 'member-pass', 'password': 'changed-member'})
        self.assertTrue(response.json['success'])
        self.assertEqual(member.get('/api/auth/check').status_code, 200)
        self.assertEqual(other.get('/api/auth/check').status_code, 401)
        self.assertEqual(self.store.config['auth']['password'], 'original-pass')
        self.assertEqual(member.post('/api/auth/update', json={'username': 'owner', 'old_password': 'changed-member', 'password': 'attack-pass'}).status_code, 400)
        self.assertEqual(member.post('/api/auth/accounts/owner/password', json={'current_password': 'changed-member', 'password': 'attack-pass'}).status_code, 400)
        self.assert_shared_data()

    def test_old_session_survives_upgrade_and_primary_password_change_is_scoped(self):
        legacy = self.web.app.test_client()
        with legacy.session_transaction() as state:
            state['username'] = 'owner'; state['login_time'] = time.time()
        self.assertEqual(legacy.get('/api/auth/check').status_code, 200)
        self.add()
        response = self.admin.post('/api/auth/update', json={'username': 'owner', 'old_password': 'original-pass', 'password': 'changed-owner'})
        self.assertTrue(response.json['success'])
        self.assertEqual(legacy.get('/api/auth/check').status_code, 401)
        self.assertEqual(self.admin.get('/api/auth/check').status_code, 200)
        self.assertEqual(self.login(self.web.app.test_client(), 'member', 'member-pass').status_code, 200)
        self.assert_shared_data()

    def test_public_config_never_discloses_hashes_and_updates_preserve_accounts(self):
        self.add(); before = copy.deepcopy(self.store.config['auth'])
        response = self.admin.get('/api/config')
        self.assertTrue(response.json['success'])
        self.assertNotIn('password', response.json['config']['auth'])
        self.assertNotIn('login_accounts', response.json['config']['auth'])
        self.assertNotIn('password_hash', response.get_data(as_text=True))
        self.assertEqual(self.admin.post('/api/config/update', json={'auth': {'users': 'owner', 'session_timeout': 7200}}).status_code, 200)
        self.assertEqual(self.store.config['auth']['login_accounts'], before['login_accounts'])
        self.assertEqual(self.store.config['auth']['password'], before['password'])
        self.assertEqual(self.admin.post('/api/config/update', json={'auth': {'login_accounts': []}}).status_code, 400)
        self.assertEqual(self.admin.post('/api/config/update', json={'auth': {'password': 'attack-pass'}}).status_code, 400)
        self.assert_shared_data()

    def test_failed_save_rolls_back_new_credentials(self):
        before = copy.deepcopy(self.store.config)
        self.store._save_config = Mock(side_effect=OSError('simulated disk failure'))
        response = self.admin.post('/api/auth/accounts', json={'username': 'member', 'password': 'member-pass', 'current_password': 'original-pass'})
        self.assertFalse(response.json['success'])
        self.assertEqual(self.store.config, before)
        self.assert_shared_data()

    def test_tmdb_settings_protected_persisted_and_secret_not_returned(self):
        self.assertEqual(self.web.app.test_client().get('/api/tmdb/settings').status_code, 401)
        response = self.admin.post('/api/tmdb/settings', json={'credential': 'fixture-tmdb-secret', 'default_root': '/001'})
        self.assertTrue(response.json['success'])
        self.assertNotIn('fixture-tmdb-secret', response.get_data(as_text=True))
        self.assertTrue(self.admin.get('/api/tmdb/settings').json['settings']['configured'])
        self.assertEqual(json.loads(Path('config/config.json').read_text())['tmdb']['default_root'], '/001')
        self.assert_shared_data()
        with patch('web_app.tmdb_service.search', return_value=[{'title': '牧神记', 'save_dir': '/001/牧神记'}]) as search:
            response = self.admin.get('/api/tmdb/search', query_string={'query': '牧神记', 'media_type': 'tv'})
            self.assertEqual(response.json['results'][0]['save_dir'], '/001/牧神记')
            self.assertEqual(search.call_args.args[1:], ('牧神记', 'tv'))
