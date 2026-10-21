import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
# Load the real TMDB package without initializing the full database application.
import importlib
from pathlib import Path
from types import ModuleType
package = ModuleType('film_tmdb_runtime_test')
package.__path__ = [str(Path(__file__).resolve().parents[2] / 'film_index/media/app/media/tmdbv3api')]
sys.modules.setdefault(package.__name__, package)
module = importlib.import_module('film_tmdb_runtime_test.tmdb')
TMDb, LAST_TMDB_ERROR = module.TMDb, module.LAST_TMDB_ERROR
TMDbException = importlib.import_module('film_tmdb_runtime_test.exceptions').TMDbException
from film_index.media.tmdb_credentials import media_tmdb_credential

class MediaTmdbTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'TMDB_API_KEY':'a'*32,'TMDB_DOMAIN':'https://api.themoviedb.org/3','TMDB_CACHE_ENABLED':'True'}, clear=False)
        self.env.start()
        os.environ.pop('TMDB_PROXIES',None)
        TMDb.cached_request.cache_clear()
    def tearDown(self): self.env.stop(); TMDb.cached_request.cache_clear()

    @patch('requests.request')
    def test_absent_proxy_and_cleared_proxy_work(self, request):
        request.return_value=Mock(status_code=200,headers={},json=lambda: {'id':226045,'name':'大主宰'})
        tmdb=TMDb()
        self.assertEqual(tmdb._call('/tv/226045','')['name'],'大主宰')
        self.assertIsNone(request.call_args.kwargs['proxies'])
        tmdb.proxies={'http':'http://old:7890'}
        tmdb.proxies=None
        self.assertIsNone(TMDb.parse_proxies(tmdb.proxies))

    @patch('requests.request')
    def test_read_token_goes_in_header_not_key_query(self, request):
        request.return_value=Mock(status_code=200,headers={},json=lambda: {'id':1})
        tmdb=TMDb();tmdb.api_key='fixture-read-token'
        tmdb._call('/tv/1','')
        self.assertEqual(request.call_args.kwargs['headers']['Authorization'],'Bearer fixture-read-token')
        self.assertNotIn('fixture-read-token',request.call_args.args[1])
        self.assertNotIn('api_key=',request.call_args.args[1])

    @patch('requests.request')
    def test_bad_auth_is_not_cached_and_diagnostic_has_no_secret(self, request):
        request.side_effect=[Mock(status_code=401),Mock(status_code=200,headers={},json=lambda:{'id':1})]
        tmdb=TMDb()
        with self.assertRaisesRegex(TMDbException,'凭据无效'):
            tmdb._call('/tv/1','')
        self.assertNotIn('a'*32,LAST_TMDB_ERROR.get())
        self.assertEqual(tmdb._call('/tv/1','')['id'],1)
        self.assertEqual(request.call_count,2)

    def test_shared_subscription_credentials_and_explicit_media_precedence(self):
        with patch.dict(sys.modules, {'film_index.subscriptions.web_app':SimpleNamespace(storage=SimpleNamespace(config={'tmdb':{'credential':'shared-token'}}))}):
            self.assertEqual(media_tmdb_credential({}),'shared-token')
            self.assertEqual(media_tmdb_credential({'rmt_tmdbkey':'legacy-key'}),'legacy-key')
        self.assertIsNone(TMDb.parse_proxies(None))
        with self.assertRaises((ValueError,TMDbException)):
            TMDb.parse_proxies("__import__('os').system('false')")
