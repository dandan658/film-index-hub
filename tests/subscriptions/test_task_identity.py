import unittest
from unittest.mock import Mock, patch
import time

class TaskIdentityApiTests(unittest.TestCase):
    def setUp(self):
        from film_index.subscriptions import web_app
        self.web = web_app
        self.first = {'task_uid':'a'*32,'order':1,'name':'光阴之外','url':'url-a','status':'normal'}
        self.second = {'task_uid':'b'*32,'order':2,'name':'择日飞升','url':'url-b','status':'normal'}
        self.storage = Mock(config={'auth':{'users':'admin','password':'fixture-password'}})
        self.storage.list_tasks.side_effect = lambda: [self.second,self.first]
        self.storage.resolve_task.side_effect = self.resolve
        self.patch = patch.object(web_app,'storage',self.storage);self.patch.start()
        self.client = web_app.app.test_client()
        with self.client.session_transaction() as session:
            session['username']='admin';session['login_time']=time.time()
        web_app._ensure_task_runtime_state()
        web_app.app.task_logs = {}

    def resolve(self, ref=None, **kwargs):
        if isinstance(ref, dict): ref=ref.get('task_uid')
        return next((t for t in [self.first,self.second] if t['task_uid']==ref),None)

    def tearDown(self): self.patch.stop()

    def test_status_and_logs_follow_uid_after_reorder(self):
        self.web._append_task_log(1,'光阴日志',task_uid=self.first['task_uid'])
        self.web._append_task_log(2,'择日日志',task_uid=self.second['task_uid'])
        self.first['order'], self.second['order'] = 2,1
        uid=self.first['task_uid']
        status=self.client.get('/api/tasks/0/status?task_uid='+uid).json
        self.assertEqual(status['status']['name'],'光阴之外')
        logs=self.client.get('/api/task/log/0?task_uid='+uid).json['logs']
        self.assertEqual([log['message'] for log in logs],['光阴日志'])
        self.assertEqual(self.web._build_task_stream_snapshot(self.first)['logs'],logs)

    def test_deleted_uid_never_falls_back_to_adjacent_index(self):
        for path in ['/api/tasks/0/status','/api/task/log/0']:
            self.assertFalse(self.client.get(path+'?task_uid='+'c'*32).json['success'])
        result=self.client.post('/api/task/execute',json={'task_id':0,'task_uid':'c'*32}).json
        self.assertFalse(result['success'])
        self.storage.transfer_files.assert_not_called()


class StableStatusStorageTests(unittest.TestCase):
    def test_status_update_does_not_follow_old_order(self):
        from film_index.subscriptions.storage import BaiduStorage
        storage = BaiduStorage.__new__(BaiduStorage)
        selected = {'task_uid':'a'*32,'order':2,'status':'normal'}
        adjacent = {'task_uid':'b'*32,'order':1,'status':'normal'}
        storage.config = {'baidu':{'tasks':[adjacent,selected]}}
        storage._save_config = Mock()
        self.assertTrue(storage.update_task_status_by_order(1,'running','progress',task_uid='a'*32))
        self.assertEqual(selected['status'],'running')
        self.assertEqual(adjacent['status'],'normal')
        self.assertFalse(storage.update_task_status_by_order(1,'error','deleted',task_uid='c'*32))
        self.assertEqual(adjacent['status'],'normal')

    def test_deleted_uid_never_resolves_by_old_order(self):
        from film_index.subscriptions.storage import BaiduStorage
        storage = Mock()
        storage.get_task_by_uid.return_value = None
        self.assertIsNone(BaiduStorage.resolve_task(storage,'c'*32,order=1,url='old-url'))
        storage.get_task_by_order.assert_not_called()
