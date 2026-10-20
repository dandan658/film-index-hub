"""Film and Television Index media-only profile, modified 2026-10-20.

Underlying clients remain available for recognition, organization and settings.
Removed acquisition features cannot be entered through old URLs or commands.
"""
import json

PRODUCT_NAME = 'Film and Television Index'
PROFILE_VERSION = 'v1.2.0'
PERMISSIONS = ('媒体整理', '服务', '系统设置')
REMOVED_PAGES = frozenset(('index', 'search', 'movie_rss', 'tv_rss', 'rss_history', 'rss_calendar',
    'site', 'sitelist', 'resources', 'recommend', 'ranking', 'douban_movie', 'douban_tv',
    'tmdb_movie', 'tmdb_tv', 'bangumi', 'discovery_person', 'downloading', 'downloaded',
    'torrent_remove', 'statistics', 'brushtask', 'userdownloader', 'user_rss', 'rss_parser', 'subscribe'))
REMOVED_NAMESPACES = frozenset(('site', 'subscribe', 'rss', 'recommend', 'search', 'download', 'torrentremover', 'brushtask'))
REMOVED_ACTIONS = frozenset(('search', 'download', 'download_link', 'download_torrent', 'pt_start', 'pt_stop', 'pt_remove', 'pt_info',
    'update_site', 'get_site', 'del_site', 'get_site_favicon', 'remove_rss_media', 'add_rss_media', 'refresh_rss',
    'movie_calendar_data', 'tv_calendar_data', 'rss_detail', 'truncate_rsshistory', 'add_brushtask', 'del_brushtask',
    'brushtask_detail', 'get_site_activity', 'get_site_history', 'get_recommend', 'get_downloaded', 'get_site_seeding_info',
    'check_site_attr', 'get_userrss_task', 'delete_userrss_task', 'update_userrss_task', 'get_rssparser', 'delete_rssparser',
    'update_rssparser', 'run_userrss', 'run_brushtask', 'list_site_resources', 'list_rss_articles', 'rss_article_test',
    'list_rss_history', 'rss_articles_check', 'rss_articles_download', 're_rss_history', 'delete_rss_history',
    'get_search_result', 'get_movie_rss_list', 'get_tv_rss_list', 'get_rss_history', 'get_downloading', 'test_site',
    'get_sites', 'update_sites_cookie_ua', 'set_site_captcha_code', 'update_torrent_remove_task', 'get_torrent_remove_task',
    'delete_torrent_remove_task', 'get_remove_torrents', 'auto_remove_torrents', 'list_brushtask_torrents',
    'get_site_user_statistics', 'cookiecloud_sync', 'update_system'))
# PT clients and acquisition settings are unavailable even with an old configuration.
REMOVED_PAGES = REMOVED_PAGES | frozenset(('indexer', 'downloader', 'download_setting', 'douban', 'upload', 'filterrule'))
REMOVED_NAMESPACES = REMOVED_NAMESPACES | frozenset(('indexer', 'downloader', 'douban', 'torrent', 'siteconf', 'filterrule'))
REMOVED_ACTIONS = REMOVED_ACTIONS | frozenset(('add_downloader', 'delete_downloader', 'get_downloader',
    'get_indexers', 'get_download_dirs', 'get_download_setting', 'update_download_setting', 'delete_download_setting',
    'get_douban_history', 'delete_douban_history', 'rule_test', 'add_filtergroup', 'restore_filtergroup',
    'set_default_filtergroup', 'del_filtergroup', 'add_filterrule', 'del_filterrule', 'filterrule_detail'))
SERVICES = frozenset(('sync', 'blacklist', 'nametest', 'nettest', 'backup'))


def action_allowed(command, data=None):
    if command == 'test_connection' and any(token in json.dumps(data or {}).lower() for token in ('app.downloader', 'app.indexer', 'qbittorrent', 'transmission', 'sites()', 'downloader()')):
        return False
    if command in REMOVED_ACTIONS:
        return False
    return command != 'sch' or (isinstance(data, dict) and data.get('item') in ('sync',))


def permissions(value):
    values = value.split(',') if isinstance(value, str) else value
    return [name for name in PERMISSIONS if name in (values or [])]


def landing_page(value):
    available = permissions(value)
    for permission, page in (('媒体整理', 'mediafile'), ('服务', 'service'), ('系统设置', 'basic')):
        if permission in available:
            return page
    return ''


def install(app):
    from flask import request, send_file

    @app.before_request
    def media_only_requests():
        page = request.path.strip('/').split('/')[0]
        if page in REMOVED_PAGES:
            return {'code': 404, 'success': False, 'message': '此功能已从媒体整理版移除'}, 404
        if request.path.startswith('/api/v1/'):
            namespace = request.path.split('/')[3]
            if namespace in REMOVED_NAMESPACES:
                return {'code': 404, 'success': False, 'message': '此功能已从媒体整理版移除'}, 404
        if request.path == '/do':
            command = request.form.get('cmd')
            try:
                data = json.loads(request.form.get('data') or '{}')
            except (ValueError, TypeError):
                return {'code': -1, 'msg': '请求数据格式错误'}, 400
            if not action_allowed(command, data):
                return {'code': -1, 'msg': '此功能已从媒体整理版移除'}, 403

    @app.route('/project-source.zip')
    def film_index_source():
        return send_file('/opt/film-index-source.zip', as_attachment=True, download_name='Film-and-Television-Index-source.zip')

    @app.route('/profile-info')
    def film_index_profile():
        return {'name': PRODUCT_NAME, 'version': PROFILE_VERSION, 'source': '/project-source.zip', 'license': 'AGPL-3.0'}
