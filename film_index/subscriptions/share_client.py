"""Instance-local compatibility for Baidu's inline share metadata."""
import json
import re
from types import MethodType
from baidupcs_py.baidupcs import BaiduPCSApi as SDKApi
from baidupcs_py.baidupcs.pcs import Method

class ShareMetadataUnavailable(ValueError):
    pass

def parse_share_metadata(html):
    decoder = json.JSONDecoder()
    for marker in re.finditer(r'(?:yunData\.setData|locals\.mset)\s*\(\s*', html):
        try:
            value, _ = decoder.raw_decode(html[marker.end():])
        except ValueError:
            continue
        if isinstance(value, dict) and (value.get('share_uk') or value.get('uk')) and value.get('shareid') is not None and 'bdstoken' in value:
            return value
    raise ShareMetadataUnavailable('百度分享页面暂未返回文件资料，请稍后重试；若持续失败，请检查分享链接、提取码和网盘登录状态')

def read_shared_metadata(client, shared_url):
    response = client._request(Method.Get, shared_url, params=None)
    client._cookies_update(response.cookies.get_dict())
    return parse_share_metadata(response.text)

class BaiduPCSApi(SDKApi):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Do not patch the SDK globally or change its transfer implementation.
        self._baidupcs.shared_paths = MethodType(read_shared_metadata, self._baidupcs)
