import unittest
from film_index.subscriptions.media_rules import destination_name, task_options


def task(**changes):
    data = dict(name='百炼成神', media_type='tv', auto_rename=True, flatten=True,
                season=1, episode_mapping=True,
                season_folders=[dict(source='第一季', season=1, name='Season 01', episode_offset=0),
                                dict(source='第二季', season=1, name='Season 01', episode_offset=0),
                                dict(source='第三季', season=1, name='Season 01', episode_offset=104)])
    data.update(changes)
    return data


class EpisodeMappingTests(unittest.TestCase):
    def test_continuous_numbering_at_every_boundary(self):
        for directory, original, target in [('第一季', 1, 1), ('第一季', 52, 52),
                                             ('第二季', 53, 53), ('第二季', 104, 104),
                                             ('第三季', 1, 105), ('第三季', 26, 130),
                                             ('第三季', 27, 131)]:
            included, name, warning = destination_name(f'{directory}/{original:02d}.mkv', task())
            self.assertTrue(included)
            self.assertFalse(warning)
            self.assertEqual(name, f'百炼成神 - S01E{target:02d}.mkv')

    def test_disabled_mapping_retains_original_behavior(self):
        legacy = task(episode_mapping=False)
        self.assertEqual(destination_name('第三季/01.mp4', legacy)[1], '百炼成神 - S01E01.mp4')
        self.assertEqual(destination_name('普通第四季/01.mp4', task())[1], '百炼成神 - S04E01.mp4')
        self.assertFalse(task_options(dict(name='普通', media_type='tv'))['episode_mapping'])

    def test_tmdb_checks_target_instead_of_conflicting_source_tags(self):
        configured = task(tmdb_auto_season=True, _tmdb_seasons={1: 156})
        self.assertEqual(destination_name('第三季/S03E01.mp4', configured)[1], '百炼成神 - S01E105.mp4')
        self.assertFalse(destination_name('第三季/S03E53.mp4', configured)[0])
        configured['episode_mapping'] = False
        self.assertFalse(destination_name('第三季/S03E01.mp4', configured)[0])

    def test_nested_rules_subtitles_and_season_directory(self):
        configured = task(season_directories=True)
        self.assertEqual(destination_name('第三季/4K/S03E26.chs.ass', configured)[1],
                         'Season 01/百炼成神 - S01E130.chs.ass')
        configured['season_folders'].append(dict(source='第三季/特别篇', season=2, name='Season 02', episode_offset=0))
        self.assertEqual(destination_name('第三季/特别篇/01.mp4', configured)[1],
                         'Season 02/百炼成神 - S02E01.mp4')

    def test_invalid_offsets_are_rejected_and_preserved_on_edit(self):
        for value in (True, '104', 1.5, 9999, -9999):
            configured = task()
            configured['season_folders'][-1]['episode_offset'] = value
            with self.assertRaises(ValueError):
                task_options(configured)
        previous = task_options(task())
        self.assertEqual(task_options(dict(name='百炼成神'), previous)['season_folders'][-1]['episode_offset'], 104)
        for changes in (dict(auto_rename=False), dict(season_folders=[])):
            with self.assertRaises(ValueError):
                task_options(task(**changes))

    def test_invalid_result_skips_file_without_clamping(self):
        configured = task()
        configured['season_folders'][-1]['episode_offset'] = -1
        included, _, warning = destination_name('第三季/01.mp4', configured)
        self.assertFalse(included)
        self.assertIn('映射后集数', warning)


if __name__ == '__main__':
    unittest.main()
