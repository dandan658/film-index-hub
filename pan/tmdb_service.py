"""Bounded TMDB searches using a server-side credential and fixed official API host."""
import json
import os
import posixpath
import re
import urllib.error
import urllib.parse
import urllib.request
from media_rules import safe_name


def default_root(value):
    if not isinstance(value, str) or len(value) > 1000 or not value.startswith('/'):
        raise ValueError('默认保存位置必须是以 / 开头的百度网盘路径，例如 /001')
    if '\\' in value or any(part in ('.', '..') for part in value.split('/')) or re.search(r'[\x00-\x1f]', value):
        raise ValueError('默认保存位置不能包含路径跳转或控制字符')
    return posixpath.normpath('/' + value.lstrip('/'))


def credential(config):
    return str(config.get('credential') or os.environ.get('TMDB_API_TOKEN') or os.environ.get('TMDB_API_KEY') or '').strip()


def public_settings(config):
    return {'configured': bool(credential(config)), 'default_root': config.get('default_root', '/001')}


def settings_update(previous, data):
    if not isinstance(data, dict):
        raise ValueError('TMDB 配置格式不正确')
    updated = dict(previous)
    updated['default_root'] = default_root(data.get('default_root', previous.get('default_root', '/001')))
    value = data.get('credential', '')
    if not isinstance(value, str) or len(value) > 4096 or any(c.isspace() for c in value.strip()):
        raise ValueError('请填写有效的 TMDB API Key 或 Read Access Token')
    if value.strip():
        updated['credential'] = value.strip()
    return updated


def search(config, query, media_type):
    if media_type not in ('tv', 'movie'):
        raise ValueError('请先选择电影或电视剧')
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 150:
        raise ValueError('搜索名称需要 1 至 150 个字符')
    token = credential(config)
    if not token:
        raise ValueError('请先配置 TMDB API Key 或 Read Access Token')
    params = {'query': query.strip(), 'language': 'zh-CN', 'include_adult': 'false', 'page': 1}
    headers = {'Accept': 'application/json', 'User-Agent': 'BaiduAutosave/1.6.0'}
    if re.fullmatch(r'[0-9a-fA-F]{32}', token):
        params['api_key'] = token
    else:
        headers['Authorization'] = 'Bearer ' + token.removeprefix('Bearer ')
    request = urllib.request.Request('https://api.themoviedb.org/3/search/' + media_type + '?' + urllib.parse.urlencode(params), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read(2_000_000))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ValueError('TMDB 凭据无效或无访问权限，请检查配置') from None
        if error.code == 429:
            raise ValueError('TMDB 请求过多，请稍后再试') from None
        raise ValueError('TMDB 服务暂时不可用，请稍后再试') from None
    except (OSError, ValueError):
        raise ValueError('无法连接 TMDB，请检查 NAS 网络后重试') from None
    results = []
    for item in payload.get('results', [])[:20]:
        title = item.get('name' if media_type == 'tv' else 'title') or item.get('original_name' if media_type == 'tv' else 'original_title')
        if not title or not isinstance(item.get('id'), int):
            continue
        title = safe_name(title[:200])
        results.append({'id': item['id'], 'media_type': media_type, 'title': title,
                        'original_title': item.get('original_name' if media_type == 'tv' else 'original_title', ''),
                        'year': str(item.get('first_air_date' if media_type == 'tv' else 'release_date') or '')[:4],
                        'overview': str(item.get('overview') or '暂无简介')[:3000],
                        'vote_average': item.get('vote_average', 0),
                        'save_dir': posixpath.join(default_root(config.get('default_root', '/001')), title)})
    return results
