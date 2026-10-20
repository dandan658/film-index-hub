import unittest
from share_links import normalize_share


class ShareLinkTests(unittest.TestCase):
    def test_query_order_extra_parameters_and_fragment(self):
        self.assertEqual(normalize_share('https://pan.baidu.com/s/1example?foo=bar&pwd=ab12#list/path=%2F'),
                         ('https://pan.baidu.com/s/1example', 'ab12'))

    def test_explicit_code_has_priority_and_can_be_cleared(self):
        url = 'https://pan.baidu.com/s/1example?pwd=ab12'
        self.assertEqual(normalize_share(url, 'cd34')[1], 'cd34')
        self.assertEqual(normalize_share(url, '')[1], '')

    def test_legacy_edits_preserve_saved_code(self):
        self.assertEqual(normalize_share('https://pan.baidu.com/s/1example', None, 'ab12')[1], 'ab12')

    def test_init_link_and_encoded_code(self):
        self.assertEqual(normalize_share('https://pan.baidu.com/share/init?foo=bar&surl=example&pwd=%61b12'),
                         ('https://pan.baidu.com/s/1example', 'ab12'))

    def test_invalid_host_or_code_is_rejected(self):
        for url, code in [('https://example.com/s/1example', None), ('https://pan.baidu.com/s/1example', 'too-long')]:
            with self.assertRaises(ValueError): normalize_share(url, code)
