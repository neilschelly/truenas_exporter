#!/usr/bin/env python3

from prometheus_client.core import REGISTRY
from prometheus_client import make_wsgi_app, Summary, Counter
from prometheus_client.exposition import ThreadingWSGIServer
from wsgiref.simple_server import make_server, WSGIRequestHandler
import argparse, os, sys
from urllib.parse import parse_qs
import threading
from truenas_collector import TrueNasCollector

metrics_app = make_wsgi_app()

REQUESTS = Summary('requests_seconds', 'Time spent processing requests')
@REQUESTS.time()

def truenas_exporter(environ, start_fn):
    params = parse_qs(environ['QUERY_STRING'])

    if environ['PATH_INFO'] == '/metrics':
        if not 'target' in params:
            start_fn('500 Target Not Found', [])
            return [b'Usage: The URL query parameter `target` should be the TrueNAS device IP or DNS Name.']
        else:
            print(params['target'][0])
            response = metrics_app(environ, start_fn)
            return response

    start_fn('404 Not Found', [])
    return [b'Usage: Metrics can be retrieved from /metrics, and the URL query parameter `target` should be the TrueNAS device IP or DNS Name.']

class _TrueNasExporter(WSGIRequestHandler):
    """WSGI handler that does not log requests."""

    def log_message(self, format, *args):
        """Log nothing."""

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Return Prometheus metrics from querying the TrueNAS API')
    parser.add_argument('--port', dest='port', default=9912,
                        help='Listening HTTP port for Prometheus exporter')
    args = parser.parse_args()

    username = os.environ.get('TRUENAS_USER')
    password = os.environ.get('TRUENAS_PASS')

    if (username == None or len(username) == 0):
        print("Make sure to set TRUENAS_USER environment variable to the API " +
            "user.", file=sys.stderr)
        parser.print_help()
        exit(1)
    if (password == None or len(password) == 0):
        print("Make sure to set TRUENAS_PASS environment variable to the API " +
            "user's password.", file=sys.stderr)
        parser.print_help()
        exit(1)

    print(args, username, password)

    # httpd = make_server('', args.port, truenas_exporter)
    # httpd.serve_forever()

    httpd = make_server('', args.port, truenas_exporter, ThreadingWSGIServer, handler_class=_TrueNasExporter)
    t = threading.Thread(target=httpd.serve_forever)
    #t.daemon = True
    t.start()