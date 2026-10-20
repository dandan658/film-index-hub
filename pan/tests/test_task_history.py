import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from task_history import TaskHistory, delete_task_history, history_path


class TaskHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = os.getcwd()
        os.chdir(self.temp.name)
        self.deleted = patch('task_history._deleted', set())
        self.deleted.start()
        self.source = {'fs_id': 123, 'size': 100, 'md5': 'known-md5'}

    def tearDown(self):
        self.deleted.stop()
        os.chdir(self.original)
        self.temp.cleanup()

    def test_persists_by_task_uid_independent_of_cloud_path_and_link(self):
        history = TaskHistory('one', 'https://pan.baidu.com/s/source')
        history.remember(self.source, '/旧位置/01.mp4')
        self.assertTrue(TaskHistory('one', 'https://pan.baidu.com/s/new-link').contains(self.source))
        self.assertFalse(TaskHistory('two', 'https://pan.baidu.com/s/source').contains(self.source))

    def test_delete_removes_memory_and_owned_organized_records(self):
        history = TaskHistory('one', 'https://pan.baidu.com/s/source')
        organized = Path('config/organized/owned.json')
        organized.parent.mkdir(parents=True)
        organized.write_text('{}')
        history.register_organized(organized)
        history.remember(self.source, '/旧位置/01.mp4')
        delete_task_history('one')
        self.assertFalse(history_path('one').exists())
        self.assertFalse(organized.exists())
        history.remember(self.source, '/新位置/01.mp4')
        self.assertFalse(history_path('one').exists(), 'in-flight work must not recreate deleted memory')
        self.assertFalse(TaskHistory('new-task', 'https://pan.baidu.com/s/source').contains(self.source))

    def test_deletion_cannot_remove_unrelated_files(self):
        unrelated = Path('unrelated.json')
        unrelated.write_text('{}')
        history = TaskHistory('one', 'https://pan.baidu.com/s/source')
        history.register_organized(unrelated)
        delete_task_history('one')
        self.assertTrue(unrelated.exists())
