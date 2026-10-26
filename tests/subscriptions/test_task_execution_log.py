import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from film_index.subscriptions import task_execution_log


class TaskExecutionLogTests(unittest.TestCase):
    def test_runs_survive_in_memory_reset_and_stay_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(task_execution_log, '_root', Path(temporary)):
                first = {'timestamp': '2026-10-26T09:00:00+08:00', 'level': 'INFO', 'message': '定时执行开始'}
                second = {'timestamp': '2026-10-26T09:01:00+08:00', 'level': 'INFO', 'message': '定时执行完成'}
                task_execution_log.append('task-a', first)
                task_execution_log.append('task-a', second)
                task_execution_log.append('task-b', {'message': 'other task'})
                self.assertEqual(task_execution_log.read('task-a'), [first, second])
                self.assertEqual(task_execution_log.read('task-b'), [{'message': 'other task'}])
                self.assertEqual(task_execution_log.read('task-a', 1), [second])


if __name__ == '__main__':
    unittest.main()
