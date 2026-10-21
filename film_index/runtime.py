"""Initialize both feature modules in one application and one Python process."""
import atexit
import os
import signal
from pathlib import Path

from film_index.bootstrap import prepare, snapshot_before_upgrade, mark_started


def create_app(data_dir=None, start_services=True):
    root = prepare(data_dir or os.environ.get('FILM_INDEX_DATA', '/data'))
    snapshot_before_upgrade(root)
    from film_index.subscriptions import web_app as subscriptions
    app = subscriptions.app
    if app.extensions.get('film_index_initialized'):
        return app

    from film_index.identity import install
    install(app, subscriptions)
    from film_index.backup import install as install_backup
    install_backup(app, subscriptions, root)
    from film_index.media.web.main import bp, dirlist
    from film_index.media.web.apiv1 import apiv1_bp
    from film_index.media import media_profile
    media_profile.install(bp)
    app.register_blueprint(bp, url_prefix='/media-engine')
    app.register_blueprint(apiv1_bp, url_prefix='/api/v1')
    app.add_url_rule('/dirlist', 'media_directory', dirlist, methods=['POST'])
    # Keep existing media-server webhook paths and their configured IP checks.
    from film_index.media.web.main import emby_webhook, jellyfin_webhook, plex_webhook
    for path, view in (('/emby', emby_webhook), ('/jellyfin', jellyfin_webhook), ('/plex', plex_webhook)):
        app.add_url_rule(path, 'media_event_' + path[1:], view, methods=['POST'])

    from flask import send_from_directory, send_file, current_app

    @app.route('/static/<path:filename>')
    def media_assets(filename):
        return send_from_directory(Path(__file__).parent / 'media/web/static', filename, max_age=3600)

    @app.route('/project-source.zip')
    def source_archive():
        return send_file('/opt/film-index/source.zip', as_attachment=True, download_name='Film-Index-source.zip')

    @app.route('/api/system/architecture')
    @subscriptions.login_required
    def architecture():
        return {'success': True, 'version': '3.0.4', 'application_count': 1,
                'process_id': os.getpid(), 'application_id': id(current_app._get_current_object()), 'features': ['subscriptions', 'media'],
                'gateway': False}

    from film_index.media.app.db import init_db, update_db, init_data, release_sessions

    @app.teardown_appcontext
    def release_request_database_sessions(error=None):
        release_sessions()
    from film_index.media.check_config import update_config
    init_db()
    update_db()
    init_data()
    update_config()
    if start_services:
        ready, error = subscriptions.init_app()
        if not ready:
            raise RuntimeError(error)
        from film_index.media.app.scheduler import run_scheduler, stop_scheduler
        from film_index.media.app.sync import run_monitor, stop_monitor
        run_scheduler()
        run_monitor()
        from film_index.media.runtime import watch_configuration
        stop_configuration_watch = watch_configuration()

        def shutdown():
            stop_configuration_watch()
            stop_monitor()
            stop_scheduler()
            subscriptions.cleanup()

        atexit.register(shutdown)
        app.extensions['film_index_shutdown'] = shutdown
    app.extensions['film_index_initialized'] = True
    release_sessions()
    mark_started(root)
    return app


def main():
    app = create_app()
    from waitress import serve

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print('Film Index 3.0.4: one application, one process, port 5000', flush=True)
    from film_index.subscriptions.server_runtime import server_options
    serve(app, **server_options(5000))

