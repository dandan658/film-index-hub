"""Resolve media credentials without copying secrets into a second config file."""
import os
import sys

def media_tmdb_credential(app_config):
    explicit = str(app_config.get('rmt_tmdbkey') or '').strip()
    if explicit:
        return explicit
    subscriptions = sys.modules.get('film_index.subscriptions.web_app')
    storage = getattr(subscriptions, 'storage', None)
    settings = getattr(storage, 'config', {}).get('tmdb', {}) if storage is not None else {}
    from film_index.subscriptions.tmdb_service import credential
    return credential(settings)
