import importlib.util
import queue
import threading
import time
import unittest
from urllib.request import urlopen

AVAILABLE = importlib.util.find_spec('waitress') is not None and importlib.util.find_spec('flask') is not None


@unittest.skipUnless(AVAILABLE, 'HTTP concurrency verified inside the Docker image')
class ConcurrencyTests(unittest.TestCase):
    def test_four_waiting_streams_do_not_block_regular_requests(self):
        from flask import Flask, Response
        from waitress import create_server
        from server_runtime import server_options
        app = Flask('concurrency-test')
        event = threading.Event()
        @app.route('/stream')
        def stream():
            def generate():
                yield 'data: connected\n\n'
                while not event.wait(0.05):
                    pass
                yield 'data: complete\n\n'
            return Response(generate(), mimetype='text/event-stream')
        @app.route('/health')
        def health(): return 'ok'
        options = server_options(0)
        options['host'] = '127.0.0.1'
        server = create_server(app, **options)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.effective_port}'
        streams = []
        try:
            for _ in range(4):
                response = urlopen(base + '/stream', timeout=2)
                self.assertEqual(response.read(1), b'd')
                streams.append(response)
            durations = []
            for _ in range(10):
                start = time.monotonic()
                with urlopen(base + '/health', timeout=2) as response:
                    self.assertEqual(response.read(), b'ok')
                durations.append(time.monotonic() - start)
            self.assertLess(max(durations), 1.0)
            print(f'HTTP concurrency: 4 waiting streams, 10 regular requests, max={max(durations):.3f}s')
        finally:
            event.set()
            for response in streams: response.close()
            server.close()
            server.task_dispatcher.shutdown(timeout=1)
