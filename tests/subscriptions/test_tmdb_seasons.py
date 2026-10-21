import unittest
from unittest.mock import patch, Mock
import io
import json
from film_index.subscriptions.media_rules import task_options, destination_name
from film_index.subscriptions import tmdb_service

class TmdbSeasonRulesTests(unittest.TestCase):
    def task(self, **changes):
        value = {'name':'剧集 (2024)', 'media_type':'tv', 'auto_rename':True, 'flatten':True,
                 'tmdb_auto_season':True, 'season_directories':True,
                 'tmdb':{'id':123, 'media_type':'tv', 'title':'剧集','year':'2024'}, '_tmdb_seasons':{1:12,2:10}}
        value.update(changes)
        return value

    def test_explicit_season_has_same_directory_and_filename(self):
        ok, path, warning = destination_name('质量/S02E03.mkv', self.task())
        self.assertTrue(ok)
        self.assertEqual(path, 'Season 02/剧集 (2024) - S02E03.mkv')
        self.assertFalse(warning)

    def test_ambiguous_conflicting_and_out_of_range_are_not_saved(self):
        for source in ['03.mkv','第二季/S01E03.mkv','S02E11.mkv','S03E01.mkv']:
            ok, _, warning = destination_name(source, self.task())
            self.assertFalse(ok, source)
            self.assertIn('待确认', warning)

    def test_single_season_and_force_first_season(self):
        self.assertEqual(destination_name('03.mkv', self.task(_tmdb_seasons={2:10}))[1], 'Season 02/剧集 (2024) - S02E03.mkv')
        task = self.task(tmdb_auto_season=False, force_first_season=True)
        self.assertEqual(destination_name('第二季/S02E03.mkv', task)[1], 'Season 01/剧集 (2024) - S01E03.mkv')

    def test_exclusive_switches_and_persistence(self):
        with self.assertRaisesRegex(ValueError, '不能同时开启'):
            task_options(self.task(force_first_season=True))
        with self.assertRaises(ValueError): task_options(self.task(tmdb=None))
        validated = dict(task_options(self.task()), name='剧集 (2024)')
        self.assertTrue(task_options({}, validated)['tmdb_auto_season'])
        self.assertTrue(task_options({}, validated)['season_directories'])

    @patch('film_index.subscriptions.tmdb_service.urllib.request.urlopen')
    def test_cached_metadata_and_no_stale_fallback_on_error(self, fetch):
        tmdb_service._season_cache.clear()
        fetch.return_value.__enter__.return_value = io.BytesIO(json.dumps({'id':123,'seasons':[{'season_number':1,'episode_count':12},{'season_number':2,'episode_count':10}]}).encode())
        config = {'credential':'test-only'}
        self.assertEqual(tmdb_service.tv_seasons(config,123), {1:12,2:10})
        self.assertEqual(tmdb_service.tv_seasons(config,123), {1:12,2:10})
        self.assertEqual(fetch.call_count,1)
        tmdb_service._season_cache.clear()
        fetch.side_effect = OSError('network failure')
        with self.assertRaisesRegex(ValueError, '本次未转存'): tmdb_service.tv_seasons(config,123)
