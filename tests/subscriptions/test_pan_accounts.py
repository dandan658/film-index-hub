"""Account probes/switches against a fake Baidu network; source methods run locally without the native SDK."""
import ast
import copy
import importlib.util
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / 'film_index/subscriptions/storage.py').exists():
    ROOT = Path.cwd()
source = ast.parse((ROOT / 'film_index/subscriptions/storage.py').read_text(encoding='utf8'))
original = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'BaiduStorage')
names = {'_probe_user', 'check_user', '_account_check', 'list_users', 'switch_user', 'remove_user', '_parse_cookies', '_validate_cookies', 'get_user_info'}
original.body = [node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in names]
namespace = {'BaiduPCSApi': Mock(), 'logger': Mock(), 'time': time}
exec(compile(ast.Module(body=[original], type_ignores=[]), '<production account methods>', 'exec'), namespace)
Storage = namespace['BaiduStorage']

class PanAccountTests(unittest.TestCase):
    def setUp(self):
        self.store = Storage()
        self.store.config = {'baidu': {'current_user': 'first', 'users': {
            'first': {'cookies': 'BDUSS=first; STOKEN=first'},
            'second': {'cookies': 'BDUSS=second; STOKEN=second'}},
            'tasks': [{'task_uid': 'unchanged', 'name': '保留任务'}]}}
        self.store.client = Mock(name='original client')
        self.store._client_lock = threading.Lock()
        self.store._user_info_cache = None
        self.store._user_info_cache_time = 0
        self.store._cache_ttl = 30
        self.store._save_config = Mock()
        self.api = Mock(); self.api.quota.return_value = (1024**3, 512)
        namespace['BaiduPCSApi'] = Mock(return_value=self.api)

    def test_check_other_account_preserves_active_account_client_and_tasks(self):
        original = copy.deepcopy(self.store.config); client = self.store.client
        result = self.store.check_user('second')
        self.assertTrue(result['valid']); self.assertEqual(result['quota']['total'], 1024**3)
        self.assertEqual(self.store.config, original); self.assertIs(self.store.client, client)
        self.store._save_config.assert_not_called()
        summaries = self.store.list_users()
        self.assertIsNone(summaries[0]['cookies_valid']); self.assertTrue(summaries[1]['cookies_valid'])
        self.assertNotIn('cookies', summaries[1])

    def test_authentication_failure_is_invalid_but_network_failure_is_unknown(self):
        error = RuntimeError('sensitive response must not leak'); error.error_code = -6
        self.api.quota.side_effect = error
        result = self.store.check_user('second')
        self.assertFalse(result['valid']); self.assertNotIn('sensitive', result['message'])
        self.api.quota.side_effect = TimeoutError('network timeout')
        self.assertIsNone(self.store.check_user('second')['valid'])

    def test_missing_cookies_and_changed_credentials_do_not_reuse_previous_check(self):
        self.store.check_user('second')
        self.store.config['baidu']['users']['second']['cookies'] = 'BDUSS=changed'
        self.assertIsNone(self.store.list_users()[1]['cookies_valid'])
        self.assertFalse(self.store.check_user('second')['valid'])

    def test_switch_commits_probed_client_and_quota_without_altering_tasks(self):
        tasks = copy.deepcopy(self.store.config['baidu']['tasks'])
        self.assertTrue(self.store.switch_user('second'))
        self.assertEqual(self.store.config['baidu']['current_user'], 'second')
        self.assertIs(self.store.client, self.api)
        self.assertEqual(self.store._user_info_cache['quota']['total'], 1024**3)
        self.assertEqual(self.store.config['baidu']['tasks'], tasks)
        self.store._save_config.assert_called_once_with(update_scheduler=False)

    def test_failed_probe_or_failed_save_keeps_original_account(self):
        original = copy.deepcopy(self.store.config); client = self.store.client
        self.api.quota.side_effect = TimeoutError()
        self.assertFalse(self.store.switch_user('second'))
        self.assertEqual(self.store.config, original); self.assertIs(self.store.client, client)
        self.api.quota.side_effect = None
        self.store._save_config.side_effect = OSError('disk full')
        self.assertFalse(self.store.switch_user('second'))
        self.assertEqual(self.store.config, original); self.assertIs(self.store.client, client)

    def test_old_inflight_quota_does_not_pollute_new_accounts_backend_cache(self):
        old = self.store.client
        def delayed_quota():
            self.assertTrue(self.store.switch_user('second'))
            return (99999, 999)
        old.quota.side_effect = delayed_quota
        old._baidupcs.user_info.side_effect = RuntimeError('details unavailable')
        result = self.store.get_user_info()
        self.assertEqual(result['quota']['total'], 99999)
        self.assertEqual(self.store._user_info_cache['quota']['total'], 1024**3)
        self.assertEqual(self.store.get_user_info()['quota']['total'], 1024**3)

    def test_deleted_or_edited_account_during_probe_cannot_become_active(self):
        def edit():
            self.store.config['baidu']['users']['second']['cookies'] = 'changed during check'
            return (1000, 1)
        self.api.quota.side_effect = edit
        self.assertFalse(self.store.switch_user('second'))
        self.assertEqual(self.store.config['baidu']['current_user'], 'first')

    def test_delete_keeps_current_account_and_tasks_and_rolls_back_failed_save(self):
        original = copy.deepcopy(self.store.config)
        self.assertFalse(self.store.remove_user('first'))
        self.store._save_config.side_effect = OSError()
        self.assertFalse(self.store.remove_user('second')); self.assertEqual(self.store.config, original)
        self.store._save_config.side_effect = None
        self.assertTrue(self.store.remove_user('second'))
        self.assertEqual(self.store.config['baidu']['tasks'], original['baidu']['tasks'])
        self.assertEqual(self.store.config['baidu']['current_user'], 'first')

AVAILABLE = importlib.util.find_spec('baidupcs_py') is not None
@unittest.skipUnless(AVAILABLE, 'Full authenticated API checks run in the Docker image with its native SDK')
class PanAccountApiTests(unittest.TestCase):
    def setUp(self):
        from film_index.subscriptions import web_app
        self.web = web_app
        self.store = Mock(config={'auth': {'users': 'admin', 'password': 'fixture'}, 'baidu': {'current_user': 'first', 'users': {'first': {}, 'second': {}}}})
        self.store.check_user.return_value = {'valid': True, 'quota': {'total': 1000, 'used': 5}}
        self.store.switch_user.return_value = True
        self.store.list_users.return_value = [{'username': 'second', 'cookies_valid': True}]
        self.patch = patch.object(web_app, 'storage', self.store); self.patch.start()
        self.client = web_app.app.test_client()
        with self.client.session_transaction() as state:
            state['username'] = 'admin'; state['login_time'] = time.time()
    def tearDown(self): self.patch.stop()
    def test_check_requires_login_and_known_account(self):
        self.assertEqual(self.web.app.test_client().post('/api/user/check', json={'username': 'second'}).status_code, 401)
        self.assertEqual(self.client.post('/api/user/check', json={'username': 'missing'}).status_code, 404)
        self.assertTrue(self.client.post('/api/user/check', json={'username': 'second'}).json['valid'])
    def test_switch_does_not_reinitialize_application_or_return_credentials(self):
        with patch.object(self.web, 'init_app') as init:
            response = self.client.post('/api/user/switch', json={'username': 'second'})
            self.assertTrue(response.json['success']); init.assert_not_called()
            self.assertNotIn('cookies', response.json['current_user'])
    def test_delete_current_is_blocked_and_another_account_can_be_deleted(self):
        self.assertFalse(self.client.post('/api/user/delete', json={'username': 'first'}).json['success'])
        self.store.remove_user.return_value = True
        self.assertTrue(self.client.post('/api/user/delete', json={'username': 'second'}).json['success'])

if __name__ == '__main__': unittest.main()
