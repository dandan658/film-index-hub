import unittest
from threading import Lock
from unittest.mock import Mock


class ScheduledExecutionTests(unittest.TestCase):
    def test_scheduled_run_records_start_and_skipped_result(self):
        from film_index.subscriptions.scheduler import TaskScheduler

        task = {
            'task_uid': 'scheduled-test', 'order': 1, 'name': '测试订阅',
            'url': 'https://example.invalid/share', 'save_dir': '/test',
        }
        messages = []
        storage = Mock()
        storage.config = {'baidu': {'tasks': [task]}}
        storage.list_tasks.return_value = [task]
        storage.get_task_by_uid.return_value = task
        storage.is_valid.return_value = True
        storage.transfer_share.return_value = {'success': True, 'skipped': True}
        storage.task_log_callback = lambda order, message, level, uid: messages.append((uid, message, level))

        scheduler = TaskScheduler.__new__(TaskScheduler)
        scheduler.storage = storage
        scheduler._execution_lock = Lock()
        scheduler._add_to_notification_buffer = Mock()

        self.assertEqual(scheduler._get_current_tasks(), [task])
        self.assertTrue(scheduler._execute_single_task(task))
        self.assertTrue(any('定时执行开始' in message for _, message, _ in messages))
        self.assertTrue(any('没有新文件' in message for _, message, _ in messages))
        self.assertTrue(all(uid == task['task_uid'] for uid, _, _ in messages))
        self.assertEqual(storage.update_task_status_by_order.call_args_list[0].args[1], 'running')
        self.assertEqual(storage.update_task_status_by_order.call_args_list[-1].args[1], 'skipped')


if __name__ == '__main__':
    unittest.main()
