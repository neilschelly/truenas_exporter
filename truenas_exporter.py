#!/usr/bin/env python3

from prometheus_client.core import REGISTRY
from prometheus_client import make_wsgi_app, Summary, Counter
from wsgiref.simple_server import make_server, WSGIRequestHandler
import argparse, os, sys
from urllib.parse import parse_qs
import threading
from truenas_collector import TrueNasCollector
import requests

REQUESTS = Summary('truenas_exporter_requests_seconds', 'Time spent processing requests')
@REQUESTS.time()
def truenas_exporter(environ, start_fn):
    if environ['PATH_INFO'] == '/metrics':
        return metrics_app(environ, start_fn)

    start_fn('404 Not Found', [])
    return [b'Usage: Metrics can be retrieved from /metrics']


class _SilentHandler(WSGIRequestHandler):
    """WSGI handler that does not log requests."""
    # Blatantly stolen from client_python exposition.py

    def log_message(self, format, *args):
        """Log nothing."""

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Return Prometheus metrics from querying the TrueNAS API.' +
        'Set TRUENAS_USER and TRUENAS_PASS as needed to reach the API.')
    parser.add_argument('--port', dest='port', default='9912',
        help='Listening HTTP port for Prometheus exporter')
    parser.add_argument('--target', dest='target', required=True,
        help='Target IP/Name of TrueNAS Device')
    parser.add_argument('--skip-snmp', dest='skip_snmp', default=False,
        action='store_true', help='Skip metrics available via SNMP - may ' +
        'save about a second in scrape time')
    parser.add_argument('--cache-smart', dest='cache_smart', default=24,
        action='store_true', help='Time to cache SMART test results for in ' +
        'hours. These probably only update once a week.')

    args = parser.parse_args()

    metrics_app = make_wsgi_app()
    username = os.environ.get('TRUENAS_USER')
    password = os.environ.get('TRUENAS_PASS')
    target = args.target
    skip_snmp = args.skip_snmp
    cache_smart = args.cache_smart

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

    try:
        r = requests.get(
            f'https://{target}/api/v2.0/core/ping',
            auth=(username, password),
            headers={'Content-Type': 'application/json'},
            verify=False,
            timeout=5
        )
        if r.status_code != 200 or r.text != '"pong"':
            print("Unable to confirm TrueNAS connectivity: " + r.text +
                f' at https://{target}/api/v2.0/core/ping', file=sys.stderr)
            parser.print_help()
            exit(1)
    except Exception as e: 
            print("Unable to confirm TrueNAS connectivity: " + str(e), file=sys.stderr)
            parser.print_help()
            exit(1)

    REGISTRY.register(TrueNasCollector(target, username, password, cache_smart, skip_snmp))
    print(f"Starting listening on 0.0.0.0:{args.port} now...", file=sys.stderr)
    httpd = make_server('', int(args.port), truenas_exporter, handler_class=_SilentHandler)
    httpd.serve_forever()
