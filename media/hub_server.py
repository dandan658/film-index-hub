"""Single lightweight WSGI process; no PM2, browser, or virtual display."""
import run
from waitress import serve
serve(run.App, host='0.0.0.0', port=3000, threads=4, channel_timeout=60)
