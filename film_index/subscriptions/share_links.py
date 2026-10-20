"""Normalize supported Baidu share URLs without losing extraction codes."""
import re
from urllib.parse import parse_qs, urlsplit


def normalize_share(raw_url, password=None, fallback_password=''):
    raw_url = str(raw_url or '').strip()
    parsed = urlsplit(raw_url)
    if parsed.scheme not in ('http', 'https') or parsed.netloc.lower() != 'pan.baidu.com':
        raise ValueError('请输入有效的百度网盘分享链接')
    query = parse_qs(parsed.query)
    embedded = query.get('pwd', [''])[0].strip()
    if parsed.path.rstrip('/') == '/share/init':
        surl = query.get('surl', [''])[0]
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', surl):
            raise ValueError('分享链接缺少有效的 surl')
        path = '/s/1' + surl
    elif re.fullmatch(r'/s/[a-zA-Z0-9_-]+/?', parsed.path):
        path = parsed.path.rstrip('/')
    else:
        raise ValueError('请输入 /s/ 或 /share/init 格式的百度网盘链接')
    # An explicit field wins, including an intentional clear. Old clients that
    # omit the field still accept embedded codes or preserve the saved value.
    code = str(password).strip() if password is not None else embedded or str(fallback_password or '').strip()
    if code and not re.fullmatch(r'[a-zA-Z0-9]{4}', code):
        raise ValueError('提取码应为 4 位字母或数字')
    return 'https://pan.baidu.com' + path, code
