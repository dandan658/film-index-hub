"""The only Flask application in Film Index."""
from flask import Flask, request
from flask_compress import Compress

app = Flask('film_index', static_folder=None)
app.config['COMPRESS_ALGORITHM'] = 'gzip'
Compress(app)


@app.after_request
def response_cache_policy(response):
    if request.path.startswith('/assets/') and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=2592000, immutable'
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

