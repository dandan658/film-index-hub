import io
import json
import unittest
import urllib.error
from unittest.mock import patch
import tmdb_service as tmdb
from media_rules import destination_name, task_options


class FirstSeasonTests(unittest.TestCase):
    def task(self, **changes):
        return dict(name='测试', media_type='tv', auto_rename=True, flatten=False, force_first_season=True, **changes)

    def test_force_overrides_directory_filename_and_manual_rule(self):
        for path in ('第三季/S03E02.mp4', '第二季/02.mp4', 'S04E02.mp4'):
            self.assertEqual(destination_name(path, self.task())[1], 'Season 01/测试 - S01E02.mp4')
        task = self.task(season_folders=[{'source': 'Part B', 'season': 3, 'name': '自定义季'}])
        self.assertEqual(destination_name('Part B/S03E02.mp4', task)[1], 'Season 01/测试 - S01E02.mp4')

    def test_flatten_and_subtitle_remain_distinct(self):
        task = self.task(); task['flatten'] = True
        self.assertEqual(destination_name('第二季/S02E01.zh.srt', task)[1], '测试 - S01E01.zh.srt')
        self.assertEqual(destination_name('第三季/1080p.mp4', task)[0], False)

    def test_disabled_and_old_tasks_keep_automatic_seasons(self):
        task = self.task(); task['force_first_season'] = False
        self.assertEqual(destination_name('第二季/S01E02.mp4', task)[1], 'Season 02/测试 - S02E02.mp4')
        self.assertIn('S03E02', destination_name('测试第三季 第02集.mp4', task)[1])
        del task['force_first_season']
        self.assertIn('S04E02', destination_name('S04E02.mp4', task)[1])
        self.assertFalse(task_options({})['force_first_season'])
        with self.assertRaises(ValueError): task_options({'force_first_season': 'true'})

    def test_tmdb_metadata_survives_edits_and_validates_type(self):
        data = {'media_type': 'tv', 'tmdb': {'id': 123, 'media_type': 'tv', 'title': '片名', 'year': '2024'}}
        previous = task_options(data)
        self.assertEqual(task_options({}, previous)['tmdb'], previous['tmdb'])
        self.assertIsNone(task_options({'tmdb': None}, previous)['tmdb'])
        with self.assertRaises(ValueError): task_options(dict(data, media_type='movie'))


class TmdbTests(unittest.TestCase):
    def test_default_root_and_secret_preservation(self):
        config = {'credential': 'secret', 'default_root': '/001'}
        self.assertEqual(tmdb.settings_update(config, {'credential': '', 'default_root': '/002//'})['credential'], 'secret')
        self.assertNotIn('credential', tmdb.public_settings(config))
        self.assertEqual(config['default_root'], '/001')
        for path in ('001', '/001/../002', '/001\\002', '/a\nb'):
            with self.assertRaises(ValueError): tmdb.default_root(path)

    @patch('tmdb_service.urllib.request.urlopen')
    def test_search_type_credentials_and_directory(self, fetch):
        fetch.return_value.__enter__.return_value = io.BytesIO(json.dumps({'results': [{'id': 123, 'name': '牧神记', 'first_air_date': '2024-01-01', 'overview': '简介'}]}).encode())
        result = tmdb.search({'credential': 'fixture-token', 'default_root': '/001'}, '牧神记', 'tv')[0]
        self.assertEqual(result['save_dir'], '/001/牧神记')
        self.assertEqual(result['year'], '2024')
        request = fetch.call_args.args[0]
        self.assertTrue(request.full_url.startswith('https://api.themoviedb.org/3/search/tv?'))
        self.assertEqual(request.get_header('Authorization'), 'Bearer fixture-token')
        self.assertEqual(fetch.call_args.kwargs['timeout'], 8)

    @patch('tmdb_service.urllib.request.urlopen')
    def test_movie_key_and_bad_filename_characters(self, fetch):
        fetch.return_value.__enter__.return_value = io.BytesIO(json.dumps({'results': [{'id': 4, 'title': '名称/特别篇', 'release_date': '2025-01-02'}]}).encode())
        result = tmdb.search({'credential': 'a' * 32}, '名称', 'movie')[0]
        self.assertEqual(result['save_dir'], '/001/名称_特别篇')
        self.assertIn('api_key=', fetch.call_args.args[0].full_url)

    @patch('tmdb_service.urllib.request.urlopen')
    def test_errors_never_echo_credential(self, fetch):
        fetch.side_effect = urllib.error.HTTPError('https://fixture/?api_key=secret', 401, 'bad', {}, None)
        with self.assertRaisesRegex(ValueError, '凭据无效') as error: tmdb.search({'credential': 'secret'}, '片名', 'tv')
        self.assertNotIn('secret', str(error.exception))
        with self.assertRaises(ValueError): tmdb.search({}, '片名', 'other')


if __name__ == '__main__': unittest.main()
