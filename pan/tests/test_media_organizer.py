import json
import os
from pathlib import Path
import posixpath
import tempfile
from types import SimpleNamespace
import unittest

from media_rules import destination_name, episode, regex_filename, task_options, season_in_folder
from organizer import transfer_organized


def tv(**changes):
    return dict(name='牧神记', media_type='tv', flatten=True, auto_rename=True,
                season=1, task_uid='test-task', **changes)


class NamingTests(unittest.TestCase):
    def test_decorated_chinese_and_english_season_folders(self):
        for folder, number in [('庆余年 第一季 4K', 1), ('剧名第二季【完结】', 2),
                               ('第三季', 3), ('第十一季', 11), ('第二十二季', 22),
                               ('第一百零三季', 103), ('剧名Season.02', 2),
                               ('剧名 S03 1080p', 3), ('Ｓ０４', 4), ('第２季', 2)]:
            with self.subTest(folder=folder):
                self.assertEqual(season_in_folder(folder), number)
        for folder in ('001-090', '091-100', '2026', '4K', '第一季-第三季', 'Season 01-03', '第零季'):
            self.assertIsNone(season_in_folder(folder), folder)

    def test_parent_season_overrides_incorrect_filename_season(self):
        self.assertEqual(episode('剧名第二季/S01E03.mp4'), (2, 3))
        for number, folder in enumerate(('第一季', '第二季', '第三季'), 1):
            self.assertEqual(destination_name(f'{folder}/S01E01.mp4', tv())[1],
                             f'牧神记 - S{number:02d}E01.mp4')

    def test_nearest_directory_and_manual_mapping_precedence(self):
        self.assertEqual(destination_name('第一季/剧名第二季/01.mp4', tv())[1], '牧神记 - S02E01.mp4')
        task = tv(season_folders=[{'source': '第二季', 'season': 5, 'name': '自定义第五季'}])
        self.assertEqual(destination_name('第二季/S01E01.mp4', task)[1], '牧神记 - S05E01.mp4')

    def test_unmerged_seasons_remain_separate(self):
        task = tv()
        task['flatten'] = False
        for number, folder in enumerate(('剧名 第一季 完结', '剧名第二季', '第三季'), 1):
            self.assertEqual(destination_name(f'{folder}/01.mp4', task)[1],
                             f'Season {number:02d}/牧神记 - S{number:02d}E01.mp4')

    def test_share_root_season_survives_stripping_and_quality_subfolder(self):
        task = tv()
        task['flatten'] = False
        self.assertEqual(destination_name('4K/S01E01.mp4', task,
                         source_path='剧名第三季/4K/S01E01.mp4')[1],
                         'Season 03/4K/牧神记 - S03E01.mp4')

    def test_episode_does_not_use_quality(self):
        self.assertEqual(episode('105 4K.mp4'), (1, 105))
        self.assertEqual(episode('S02E03.1080p.mkv'), (2, 3))
        self.assertEqual(episode('第12集 4K.mp4'), (1, 12))
        self.assertIsNone(episode('4K.mp4'))
        self.assertIsNone(episode('1080p.mp4'))
        self.assertIsNone(episode('2026 4K.mp4'))

    def test_regex_matches_basename_and_both_capture_syntaxes(self):
        for replace in ('第$1集.mp4', r'第\1集.mp4'):
            self.assertEqual(regex_filename('目录/101.mp4', {'regex_pattern': r'^(\d+)\.mp4$', 'regex_replace': replace}),
                             (True, '目录/第101集.mp4'))
        self.assertEqual(regex_filename('目录/101.mkv', {'regex_replace': '新名称'}), (True, '目录/新名称.mkv'))

    def test_movie_and_video_filter(self):
        task = dict(name='我的电影', media_type='movie', auto_rename=True, flatten=True)
        self.assertEqual(destination_name('4K/原名称.mkv', task)[1], '我的电影.mkv')
        self.assertFalse(destination_name('广告.png', task)[0])
        self.assertEqual(destination_name('105.chs.srt', tv())[1], '牧神记 - S01E105.chs.srt')

    def test_seasons_can_be_renamed_independently(self):
        task = tv()
        task['flatten'] = False
        task['season_folders'] = [{'source': 'Part A', 'season': 1, 'name': 'Season 01'},
                                  {'source': 'Part B', 'season': 2, 'name': '第二季整理'}]
        self.assertEqual(destination_name('Part A/01.mp4', task)[1], 'Season 01/牧神记 - S01E01.mp4')
        self.assertEqual(destination_name('Part B/01.mp4', task)[1], '第二季整理/牧神记 - S02E01.mp4')
        self.assertEqual(destination_name('Part B/S09E01.mp4', task)[1], '第二季整理/牧神记 - S02E01.mp4')
        self.assertEqual(destination_name('第二季/02.mkv', task)[1], 'Season 02/牧神记 - S02E02.mkv')
        self.assertEqual(destination_name('001-090/01.mp4', task)[1], '001-090/牧神记 - S01E01.mp4')

    def test_merge_uses_seasons_but_not_season_directories(self):
        task = tv(season_folders=[{'source': '第二季', 'season': 2, 'name': 'Season 02'}])
        self.assertEqual(destination_name('第二季/01.mp4', task)[1], '牧神记 - S02E01.mp4')

    def test_validation_and_legacy_defaults(self):
        self.assertFalse(task_options({})['auto_rename'])
        self.assertEqual(task_options({}, tv())['media_type'], 'tv')
        for task in (tv(season_folders=[{'source': '../bad', 'season': 1}]),
                     tv(season_folders=[{'source': 'a', 'season': 0}]),
                     dict(name='', media_type='tv', auto_rename=True),
                     {'regex_pattern': '(', 'regex_replace': '$1'},
                     {'flatten': 'false'}):
            with self.assertRaises((ValueError, __import__('re').error)):
                task_options(task)


class FakeStorage:
    def __init__(self, files):
        self.config = {'baidu': {'current_user': 'test'}, 'file_operations': {'rename_delay_seconds': 0}}
        self.sources = {f['fs_id']: f for f in files}
        self.files = {}
        self.dirs = {'/'}
        self.transfers = []
        self.fail_rename = False
        self.fail_listing = False

    def _ensure_dir_tree_exists(self, path, client=None):
        while path:
            self.dirs.add(path)
            if path == '/': break
            path = posixpath.dirname(path)
        return True

    def _list_dir_entries_with_fallback(self, path, client=None):
        if self.fail_listing: raise RuntimeError('listing failed')
        return [dict(meta, path=p, isdir=False) for p, meta in self.files.items() if posixpath.dirname(p) == path] + [
            {'path': p, 'isdir': True} for p in self.dirs if p != path and posixpath.dirname(p) == path]

    def _get_list_entry_path(self, entry): return entry['path']
    def _is_list_entry_dir(self, entry): return entry['isdir']

    def _transfer_shared_paths_with_retry(self, remotedir, fs_ids, **kwargs):
        self.transfers.extend(fs_ids)
        for fs_id in fs_ids:
            source = self.sources[fs_id]
            path = posixpath.join(remotedir, posixpath.basename(source['path']))
            if path in self.files: raise RuntimeError('would overwrite staged file')
            self.files[path] = source.copy()

    def rename(self, source, destination):
        if self.fail_rename: raise RuntimeError('rename failed')
        if destination in self.files: raise RuntimeError('would overwrite target')
        self.files[destination] = self.files.pop(source)

    def remove(self, path):
        assert not self._list_dir_entries_with_fallback(path)
        self.dirs.remove(path)


class TransferTests(unittest.TestCase):
    def test_multi_season_subscription_same_episode_names_remain_distinct(self):
        for source, folder in zip(self.files, ('剧名第一季', '剧名第二季', '剧名第三季')):
            source['path'] = f'合集/{folder}/S01E01.mp4'
        result = self.run_transfer()
        self.assertTrue(result['success'])
        self.assertEqual(set(self.storage.files), {f'/剧集/牧神记 - S{number:02d}E01.mp4' for number in (1, 2, 3)})
        self.storage.files.clear()  # The user moved everything for scraping.
        self.assertTrue(self.run_transfer()['skipped'])
        self.assertEqual(len(self.storage.transfers), 3)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.temp.name)
        self.roots = [SimpleNamespace(is_dir=True, uk=1, share_id=2, bdstoken='test')]
        self.files = [{'fs_id': i, 'path': path, 'size': 100 + i, 'md5': str(i)} for i, path in enumerate(
            ['分享/001-090/01 4K.mp4', '分享/091-100/91 4K.mp4', '分享/105 4K.mp4'], 1)]
        self.storage = FakeStorage(self.files)

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def run_transfer(self, task=None):
        return transfer_organized(self.storage, self.storage, self.files, self.roots,
                                  'https://pan.baidu.com/s/test', '/剧集', task or tv())

    def test_flatten_and_repeat_subscription(self):
        self.assertTrue(self.run_transfer()['success'])
        self.assertEqual(set(self.storage.files), {'/剧集/牧神记 - S01E01.mp4', '/剧集/牧神记 - S01E91.mp4', '/剧集/牧神记 - S01E105.mp4'})
        self.assertTrue(self.run_transfer()['skipped'])
        self.assertEqual(len(self.storage.transfers), 3)
        self.assertEqual(tv()['name'], '牧神记')

    def test_preserve_independently_named_season_folders(self):
        task = tv(season_folders=[{'source': '001-090', 'season': 1, 'name': 'Season 01'},
                                 {'source': '091-100', 'season': 2, 'name': 'Season 02'}])
        task['flatten'] = False
        self.assertTrue(self.run_transfer(task)['success'])
        self.assertIn('/剧集/Season 01/牧神记 - S01E01.mp4', self.storage.files)
        self.assertIn('/剧集/Season 02/牧神记 - S02E91.mp4', self.storage.files)
        self.assertTrue(self.run_transfer(task)['skipped'])

    def test_name_change_keeps_processed_files_and_affects_only_new_files(self):
        self.run_transfer()
        task = tv()
        task['name'] = '自定义剧名'
        self.assertTrue(self.run_transfer(task)['skipped'])
        self.assertEqual(len(self.storage.transfers), 3)
        self.assertTrue(all('牧神记' in p for p in self.storage.files))

    def test_moved_files_are_remembered_even_after_restart(self):
        self.run_transfer()
        self.storage.files.clear()  # The user moved everything elsewhere for scraping.
        self.assertTrue(self.run_transfer()['skipped'])
        self.assertFalse(self.storage.files)
        self.assertEqual(len(self.storage.transfers), 3)
        source = {'fs_id': 4, 'path': '分享/106 4K.mp4', 'size': 104, 'md5': '4'}
        self.files.append(source)
        self.storage.sources[4] = source
        self.assertTrue(self.run_transfer()['success'])
        self.assertEqual(self.storage.transfers, [1, 2, 3, 4])

    def test_destination_change_does_not_reset_memory(self):
        self.run_transfer()
        result = transfer_organized(self.storage, self.storage, self.files, self.roots,
                                    'https://pan.baidu.com/s/test', '/新位置', tv())
        self.assertTrue(result['skipped'])
        self.assertEqual(len(self.storage.transfers), 3)

    def test_legacy_organized_records_migrate_without_retransfer(self):
        self.run_transfer()
        for path in Path('config/history').glob('*.json'): path.unlink()
        self.storage.files.clear()
        self.assertTrue(self.run_transfer()['skipped'])
        self.assertEqual(len(self.storage.transfers), 3)

    def test_updated_content_is_a_new_file_version(self):
        self.run_transfer()
        self.files[0]['md5'] = 'new-checksum'
        self.files[0]['size'] = 200
        self.assertTrue(self.run_transfer()['success'])
        self.assertEqual(self.storage.transfers, [1, 2, 3, 1])

    def test_existing_nested_file_is_moved_instead_of_transferred(self):
        path = '/剧集/001-090/01 4K.mp4'
        self.storage._ensure_dir_tree_exists(posixpath.dirname(path))
        self.storage.files[path] = self.files[0].copy()
        self.assertTrue(self.run_transfer()['success'])
        self.assertNotIn(1, self.storage.transfers)
        self.assertNotIn(path, self.storage.files)

    def test_colliding_original_names_are_staged_separately(self):
        self.files[1]['path'] = '分享/another/01 4K.mp4'
        self.assertTrue(self.run_transfer()['success'])
        self.assertEqual(len(self.storage.files), 3)
        self.assertEqual({f['fs_id'] for f in self.storage.files.values()}, {1, 2, 3})
        self.assertTrue(self.run_transfer()['skipped'])
        self.assertEqual(len(self.storage.transfers), 3)

    def test_existing_unrelated_target_is_never_overwritten(self):
        self.storage.files['/剧集/牧神记 - S01E01.mp4'] = {'fs_id': 999, 'size': 999}
        self.assertTrue(self.run_transfer()['success'])
        self.assertEqual(self.storage.files['/剧集/牧神记 - S01E01.mp4']['fs_id'], 999)
        self.assertEqual(len(self.storage.files), 4)

    def test_rename_failure_is_reported_and_staged_data_reused(self):
        self.storage.fail_rename = True
        self.assertFalse(self.run_transfer()['success'])
        self.assertEqual(len(self.storage.files), 3)
        self.storage.fail_rename = False
        self.assertTrue(self.run_transfer()['success'])
        self.assertEqual(len(self.storage.transfers), 3)

    def test_listing_failure_does_not_transfer_anything(self):
        self.storage.fail_listing = True
        with self.assertRaises(RuntimeError): self.run_transfer()
        self.assertFalse(self.storage.transfers)

    def test_invalid_state_does_not_transfer_anything(self):
        self.run_transfer()
        for path in Path('config/organized').glob('*.json'): path.write_text('{')
        with self.assertRaises(json.JSONDecodeError): self.run_transfer()
        self.assertEqual(len(self.storage.transfers), 3)

    def test_unknown_episode_is_explicit_failure(self):
        self.files[0]['path'] = '分享/4K.mp4'
        result = self.run_transfer()
        self.assertFalse(result['success'])
        self.assertIn('无法识别集数', result['error'])


if __name__ == '__main__':
    unittest.main()
