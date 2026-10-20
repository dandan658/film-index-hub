"""Use independent request threads so slow external APIs and SSE do not block UI APIs."""
import os


def server_options(port=5000):
    try:
        threads = int(os.environ.get('WEB_THREADS', '16'))
    except ValueError:
        threads = 16
    return dict(host='0.0.0.0', port=port, threads=max(8, min(64, threads)),
                channel_request_lookahead=1, channel_timeout=60,
                clear_untrusted_proxy_headers=True)
