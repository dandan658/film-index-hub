import importlib.util
import time
import unittest
from unittest.mock import Mock, patch

AVAILABLE = importlib.util.find_spec('baidupcs_py') is not None


@unittest.skipUnless(AVAILABLE, 'API integration verified inside the Docker image')
class ShareApiTests(unittest.TestCase):
    def setUp(self):
        import web_app
        self.web = web_app
        self.storage = Mock(config={'auth': {'users': 'admin', 'password': 'fixture-password'}})
        self.storage.list_tasks.return_value = [{'order': 1, 'url': 'https://pan.baidu.com/s/1example', 'pwd': 'ab12', 'name': '名称', 'save_dir': '/目录'}]
        self.storage.add_task.return_value = True
        self.storage.update_task_by_order.return_value = True
        self.storage.get_share_folder_name.return_value = {'success': True, 'folder_name': '名称'}
        self.patch = patch.object(web_app, 'storage', self.storage)
        self.patch.start()
        self.client = web_app.app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'admin'
            session['login_time'] = time.time()

    def tearDown(self): self.patch.stop()

    def test_add_and_share_info_use_explicit_field_in_preference_to_link_code(self):
        payload = {'url': 'https://pan.baidu.com/s/1example?pwd=ab12&foo=bar', 'pwd': 'cd34', 'save_dir': '/目录'}
        self.assertTrue(self.client.post('/api/task/add', json=payload).json['success'])
        self.assertEqual(self.storage.add_task.call_args.args[0:3], ('https://pan.baidu.com/s/1example', '/目录', 'cd34'))
        self.assertTrue(self.client.post('/api/share/info', json=payload).json['success'])
        self.storage.get_share_folder_name.assert_called_with('https://pan.baidu.com/s/1example', 'cd34')

    def test_legacy_edit_does_not_erase_saved_code(self):
        response = self.client.post('/api/task/update', json={'task_id': 0, 'url': 'https://pan.baidu.com/s/1example', 'save_dir': '/目录'})
        self.assertTrue(response.json['success'])
        self.assertEqual(self.storage.update_task_by_order.call_args.args[1]['pwd'], 'ab12')

    def test_explicit_clear_is_saved(self):
        response = self.client.post('/api/task/update', json={'task_id': 0, 'url': 'https://pan.baidu.com/s/1example', 'save_dir': '/目录', 'pwd': ''})
        self.assertTrue(response.json['success'])
        self.assertEqual(self.storage.update_task_by_order.call_args.args[1]['pwd'], '')
