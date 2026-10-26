import unittest
from unittest.mock import Mock, patch


class MediaSyncScheduleTests(unittest.TestCase):
    def test_interval_job_is_registered_only_when_enabled(self):
        from film_index.media.app import scheduler as module

        for interval, expected in [('2', True), (0, False), ('bad', False)]:
            with self.subTest(interval=interval):
                jobs = Mock()
                config = Mock()
                config.get_timezone.return_value = 'Asia/Shanghai'
                config.get_config.side_effect = lambda key: {
                    'sync': {'full_sync_interval': interval},
                    'media': {},
                }.get(key, {})
                with patch.object(module, 'Config', return_value=config), \
                        patch.object(module, 'BackgroundScheduler', return_value=jobs), \
                        patch.object(module, 'MetaHelper'), \
                        patch.object(module, 'Sync'):
                    instance = module.Scheduler.__new__(module.Scheduler)
                    instance._media = {}
                    instance.run_service()
                sync_calls = [call for call in jobs.add_job.call_args_list
                              if call.kwargs.get('id') == 'directory_full_sync']
                self.assertEqual(len(sync_calls), int(expected))
                if expected:
                    self.assertEqual(sync_calls[0].kwargs['hours'], 2.0)
                    self.assertEqual(sync_calls[0].kwargs['max_instances'], 1)

    def test_schedule_reports_completed_or_skipped_scan(self):
        from film_index.media.app import scheduler as module

        sync = Mock()
        for result, message in [(True, '任务结束'), (False, '跳过')]:
            with self.subTest(result=result), \
                    patch.object(module, 'Sync', return_value=sync), \
                    patch.object(module.log, 'info') as info:
                sync.transfer_all_sync.return_value = result
                module.Scheduler._run_directory_sync()
                self.assertTrue(any(message in call.args[0] for call in info.call_args_list))


if __name__ == '__main__':
    unittest.main()
