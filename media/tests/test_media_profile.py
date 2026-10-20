"""Local profile checks; no NAS, network credentials or media files are used."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from media_profile import action_allowed, install, landing_page, permissions, REMOVED_ACTIONS, REMOVED_PAGES

ROOT = Path(__file__).resolve().parents[1]


def method(path, name):
    node = next(n for n in ast.walk(ast.parse((ROOT / path).read_text(encoding='utf8')))
                if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    return compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), path, 'exec')


class ProfileTests(unittest.TestCase):
    def test_removed_actions_disabled_but_retained_settings_and_recognition_work(self):
        for name in REMOVED_ACTIONS:
            self.assertFalse(action_allowed(name, {}), name)
        for name in ('rename', 'rename_udf', 're_identification', 'name_test', 'search_media_infos', 'get_users',
                     'download_subtitle', 'modify_tmdb_cache', 'run_directory_sync',
                     'update_message_client', 'test_connection', 'update_config'):
            self.assertTrue(action_allowed(name, {}), name)
        self.assertTrue(action_allowed('sch', {'item': 'sync'}))
        self.assertFalse(action_allowed('sch', {'item': 'pttransfer'}))
        for item in ('rssdownload', 'ptsignin', 'autoremovetorrents', 'subscribe_search_all'):
            self.assertFalse(action_allowed('sch', {'item': item}))

    def test_permissions_and_landing_do_not_rewrite_input(self):
        original = ['探索', '资源搜索', '媒体整理', '服务', '系统设置']
        before = list(original)
        self.assertEqual(permissions(original), ['媒体整理', '服务', '系统设置'])
        self.assertEqual(original, before)
        self.assertEqual(landing_page(original), 'mediafile')
        self.assertEqual(landing_page('系统设置'), 'basic')
        self.assertEqual(landing_page('探索'), '')

    def test_retained_real_page_handlers_keep_login_protection(self):
        tree = ast.parse((ROOT / 'web/main.py').read_text(encoding='utf8'))
        pages = {'mediafile', 'unidentification', 'history', 'tmdbcache', 'service', 'basic', 'users', 'library',
                 'directorysync', 'notification', 'customwords', 'mediaserver', 'subtitle'}
        checked = set()
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef): continue
            routes = [d.args[0].value.strip('/') for d in node.decorator_list if isinstance(d, ast.Call)
                      and isinstance(d.func, ast.Attribute) and d.func.attr == 'route' and d.args]
            for page in pages.intersection(routes):
                self.assertTrue(any(isinstance(d, ast.Name) and d.id == 'login_required' for d in node.decorator_list), page)
                checked.add(page)
        self.assertEqual(checked, pages)

    def test_scheduler_retains_organization_without_removed_jobs_or_config_mutation(self):
        jobs = []
        class FakeScheduler:
            def __init__(self, **kwargs): pass
            def add_job(self, func, *args, **kwargs): jobs.append(func.__name__)
            def start(self): pass
        class Helper:
            def transfer(self): pass
            def sync_mediaserver(self): pass
            def save_meta_data(self): pass
            def transfer_mon_files(self): pass
            def delete_unknown_meta(self): pass
            def get_timezone(self): return 'Asia/Shanghai'
        scope = dict(BackgroundScheduler=FakeScheduler, ThreadPoolExecutor=lambda count: None,
                     Config=Helper, Downloader=Helper, MediaServer=Helper, MetaHelper=Helper, Sync=Helper,
                     PT_TRANSFER_INTERVAL=300, METAINFO_SAVE_INTERVAL=600, SYNC_TRANSFER_INTERVAL=60,
                     META_DELETE_UNKNOWN_INTERVAL=24, REFRESH_WALLPAPER_INTERVAL=12, get_login_wallpaper=lambda: None)
        exec(method('app/scheduler.py', 'run_service'), scope)
        instance = type('SchedulerFixture', (), {})()
        instance._pt = {'pt_monitor': True, 'pt_check_interval': 300, 'ptsignin_cron': '1:00', 'search_rss_interval': 6}
        instance._douban = {'interval': 1}; instance._media = {'mediasync_interval': 1}
        before = copy.deepcopy(instance.__dict__)
        scope['run_service'](instance)
        self.assertEqual(jobs, ['sync_mediaserver', 'save_meta_data', 'transfer_mon_files', 'delete_unknown_meta'])
        self.assertEqual(instance._pt, before['_pt'])
        self.assertEqual(instance._douban, before['_douban'])

    def test_startup_does_not_initialize_removed_services(self):
        calls = []
        scope = dict(os=__import__('os'), log=type('Log', (), {'console': lambda *_: None})(),
                     DisplayHelper=lambda: calls.append('display'), run_scheduler=lambda: calls.append('scheduler'),
                     run_monitor=lambda: calls.append('monitor'))
        exec(method('run.py', 'start_service'), scope)
        scope['start_service']()
        self.assertEqual(calls, ['display', 'scheduler', 'monitor'])

    def test_archive_excludes_runtime_config_media_and_secrets(self):
        spec = importlib.util.spec_from_file_location('archive_builder', ROOT / 'scripts/create_source_archive.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'; root.mkdir()
            for name in ('app.py', 'LICENSE.md', 'data/config/config.yaml', 'media/movie.mkv', '.env'):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture')
            output = Path(temporary) / 'source.zip'; module.create(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {'Film-and-Television-Index/app.py', 'Film-and-Television-Index/LICENSE.md'})


@unittest.skipUnless(importlib.util.find_spec('flask'), 'Install Flask for request-policy checks')
class RequestTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        app = Flask(__name__); install(app)
        app.add_url_rule('/do', 'fixture_action', lambda: {'success': True}, methods=['POST'])
        for index, page in enumerate(('mediafile', 'unidentification', 'history', 'tmdbcache', 'service', 'basic', 'users', 'library',
                                     'directorysync', 'notification', 'customwords', 'mediaserver', 'subtitle')):
            app.add_url_rule('/' + page, 'page' + str(index), lambda: 'retained')
        self.client = app.test_client()

    def test_removed_urls_and_namespaces_are_unavailable(self):
        for page in REMOVED_PAGES:
            self.assertEqual(self.client.get('/' + page).status_code, 404, page)
        for name in ('site', 'subscribe', 'rss', 'recommend', 'search', 'download', 'torrentremover', 'brushtask'):
            self.assertEqual(self.client.post('/api/v1/' + name + '/test').status_code, 404)

    def test_all_requested_pages_still_pass_guard(self):
        for page in ('mediafile', 'unidentification', 'history', 'tmdbcache', 'service', 'basic', 'users', 'library',
                     'directorysync', 'notification', 'customwords', 'mediaserver', 'subtitle'):
            self.assertEqual(self.client.get('/' + page).status_code, 200, page)

    def test_removed_commands_and_bad_input_blocked(self):
        self.assertEqual(self.client.post('/do', data={'cmd': 'download', 'data': '{}'}).status_code, 403)
        self.assertEqual(self.client.post('/do', data={'cmd': 'sch', 'data': json.dumps({'item': 'rssdownload'})}).status_code, 403)
        self.assertEqual(self.client.post('/do', data={'cmd': 'rename', 'data': '{}'}).status_code, 200)
        self.assertEqual(self.client.post('/do', data={'cmd': 'sch', 'data': json.dumps({'item': 'sync'})}).status_code, 200)
        self.assertEqual(self.client.post('/do', data={'cmd': 'sch', 'data': '{'}).status_code, 400)


if __name__ == '__main__': unittest.main()
