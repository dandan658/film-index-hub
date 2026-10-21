import json
import unittest
from unittest.mock import Mock, patch
from film_index.subscriptions.share_client import parse_share_metadata, ShareMetadataUnavailable, read_shared_metadata
from film_index.subscriptions.storage import BaiduStorage

class ShareMetadataTests(unittest.TestCase):
    def test_multiline_and_embedded_delimiters(self):
        info = {'share_uk': 12, 'shareid': 34, 'bdstoken': 'fixture', 'file_list': [{'server_filename': '片名 ); 特别篇'}]}
        html = '<script>locals.mset(' + json.dumps(info, indent=2) + ');</script>'
        self.assertEqual(parse_share_metadata(html), info)
        self.assertEqual(parse_share_metadata('yunData.setData(' + json.dumps(info) + ');'), info)

    def test_invalid_response_and_unrelated_blocks(self):
        with self.assertRaises(ShareMetadataUnavailable): parse_share_metadata('locals.mset({"theme":"light"});')
        with self.assertRaises(ShareMetadataUnavailable): parse_share_metadata('<html>login</html>')

    @patch('film_index.subscriptions.storage.time.sleep')
    def test_transient_missing_data_reestablishes_access(self, sleep):
        client = Mock()
        client.shared_paths.side_effect = [ShareMetadataUnavailable('temporary'), ['file']]
        result = BaiduStorage._shared_paths_with_retry(object(), 'https://pan.baidu.com/s/fixture', client=client, pwd='1234')
        self.assertEqual(result, ['file'])
        client.access_shared.assert_called_once_with('https://pan.baidu.com/s/fixture', '1234', show_vcode=False)

    @patch('film_index.subscriptions.storage.time.sleep')
    def test_retries_bounded_and_real_errors_not_retried(self, sleep):
        client = Mock()
        client.shared_paths.side_effect = ShareMetadataUnavailable('temporary')
        with self.assertRaisesRegex(ValueError, '暂时无法读取'):
            BaiduStorage._shared_paths_with_retry(object(), 'url', client=client)
        self.assertEqual(client.shared_paths.call_count, 3)
        client.reset_mock()
        client.shared_paths.side_effect = RuntimeError('提取码错误')
        with self.assertRaisesRegex(RuntimeError, '提取码错误'):
            BaiduStorage._shared_paths_with_retry(object(), 'url', client=client)
        self.assertEqual(client.shared_paths.call_count, 1)
        client.access_shared.assert_not_called()
