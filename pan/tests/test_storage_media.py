"""Exercise real task persistence and recursive traversal in the built image."""
import copy
import importlib.util
from collections import namedtuple
import unittest
from unittest.mock import Mock, patch

AVAILABLE = importlib.util.find_spec('baidupcs_py') is not None
if AVAILABLE:
    from storage import BaiduStorage


@unittest.skipUnless(AVAILABLE, 'BaiduPCS dependencies are verified inside the Docker image')
class StorageTests(unittest.TestCase):
    def setUp(self):
        self.storage = BaiduStorage.__new__(BaiduStorage)
        self.storage.config = {'baidu': {'tasks': []}}
        self.storage._save_config = Mock()
        self.storage.client = Mock()
        self.data = dict(name='自定义剧名', url='https://pan.baidu.com/s/test', save_dir='/剧集',
                         media_type='tv', flatten=False, auto_rename=True, season=1,
                         season_folders=[{'source': 'Part B', 'season': 2, 'name': 'Season 02'}])

    def test_create_update_and_legacy_update_keep_custom_name_and_options(self):
        with patch('scheduler.TaskScheduler.instance', None, create=True):
            self.assertTrue(self.storage.add_task(**self.data))
            task = self.storage.config['baidu']['tasks'][0]
            self.assertEqual(task['name'], '自定义剧名')
            self.assertFalse(task['flatten'])
            self.assertEqual(task['season_folders'][0]['season'], 2)
            uid = task['task_uid']
            update = dict(self.data, name='更新的名称', flatten=True, regex_pattern=r'^(\d+)\.mp4$', regex_replace='第$1集.mp4')
            self.assertTrue(self.storage.update_task_by_order(1, update))
            self.assertEqual(task['name'], '更新的名称')
            self.assertEqual(task['task_uid'], uid)
            self.assertTrue(task['flatten'])
            self.assertTrue(self.storage.update_task(0, dict(update, name='手动名称'))[0])
            self.assertEqual(task['name'], '手动名称')
            self.assertEqual(task['regex_replace'], '第$1集.mp4')

    def test_invalid_rules_do_not_partially_mutate_existing_task(self):
        with patch('scheduler.TaskScheduler.instance', None, create=True):
            self.storage.add_task(**self.data)
            before = copy.deepcopy(self.storage.config)
            self.assertFalse(self.storage.update_task_by_order(1, dict(self.data, season=0)))
            self.assertEqual(before, self.storage.config)

    def test_recursive_share_listing_supports_namedtuples_and_dicts(self):
        Shared = namedtuple('Shared', 'path fs_id size is_dir md5')
        root = Shared('/sharelink1-2/分享', 10, 0, True, '')
        nested = Shared('/sharelink1-2/分享/第一季', 11, 0, True, '')
        file = {'path': '/sharelink1-2/分享/第一季/01.mp4', 'fs_id': 12, 'size': 100, 'isdir': 0, 'md5': 'checksum'}
        self.storage._list_shared_paths_with_retry = Mock(side_effect=[[nested], [file]])
        result = self.storage._list_shared_dir_files(root, 1, 2, 'test')
        self.assertEqual(result[0]['path'], '分享/第一季/01.mp4')
        self.assertEqual(result[0]['md5'], 'checksum')
        self.assertEqual(result[0]['fs_id'], 12)

    def test_share_listing_error_is_not_silently_reported_as_empty(self):
        root = Mock(path='/sharelink1-2/分享')
        self.storage._list_shared_paths_with_retry = Mock(side_effect=RuntimeError('source unavailable'))
        with self.assertRaises(RuntimeError):
            self.storage._list_shared_dir_files(root, 1, 2, 'test')

    def test_progress_keeps_running_without_disk_writes_or_scheduler_reloads(self):
        self.storage.config['baidu']['tasks'] = [{'order': 1}]
        self.assertTrue(self.storage.update_task_status_by_order(1, 'running', '整理成功：01.mp4'))
        self.assertEqual(self.storage.config['baidu']['tasks'][0]['status'], 'running')
        self.storage._save_config.assert_not_called()
        self.storage.update_task_status_by_order(1, 'normal', '转存成功')
        self.storage._save_config.assert_called_once_with(update_scheduler=False)

    def test_each_delete_api_clears_only_its_task_history(self):
        from task_history import TaskHistory, history_path
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            original = os.getcwd()
            os.chdir(directory)
            try:
                for index, method in enumerate(('remove_task', 'remove_task_by_order', 'remove_tasks')):
                    uid = 'delete-case-' + str(index)
                    self.storage.config['baidu']['tasks'] = [{'order': 1, 'task_uid': uid, 'url': 'https://pan.baidu.com/s/test'}]
                    TaskHistory(uid, 'https://pan.baidu.com/s/test').remember({'fs_id': 1, 'size': 1}, '/01.mp4')
                    argument = 'https://pan.baidu.com/s/test' if method == 'remove_task' else 1 if method == 'remove_task_by_order' else [1]
                    self.assertTrue(getattr(self.storage, method)(argument))
                    self.assertFalse(history_path(uid).exists())
            finally:
                os.chdir(original)
