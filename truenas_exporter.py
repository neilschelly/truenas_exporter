#!/usr/bin/env python3

from prometheus_client.core import REGISTRY
from prometheus_client import make_wsgi_app, Summary, Counter
from prometheus_client.exposition import ThreadingWSGIServer
from wsgiref.simple_server import make_server
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

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Return Prometheus metrics from querying the TrueNAS API')
    parser.add_argument('--port', dest='port', default=9912,
        help='Listening HTTP port for Prometheus exporter')
    parser.add_argument('--target', dest='target', required=True,
        help='Target IP/Name of TrueNAS Device')
    parser.add_argument('--skip-snmp', dest='skip_snmp', default=False,
        action='store_true', help='Skip metrics available via SNMP - may ' +
        'save about a second in scrape time')

    args = parser.parse_args()

    metrics_app = make_wsgi_app()
    username = os.environ.get('TRUENAS_USER')
    password = os.environ.get('TRUENAS_PASS')
    target = args.target
    skip_snmp = args.skip_snmp

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

    r = requests.get(
        f'https://{target}/api/v2.0/core/ping',
        auth=(username, password),
        headers={'Content-Type': 'application/json'},
        verify=False
    )
    if r.status_code != 200 or r.text != '"pong"':
        print("Unable to confirm TrueNAS connectivity: " + r.text +
            f' at https://{target}/api/v2.0/core/ping', file=sys.stderr)
        parser.print_help()
        exit(1)

    REGISTRY.register(TrueNasCollector(target, username, password, skip_snmp))
    httpd = make_server('', args.port, truenas_exporter)
    httpd.serve_forever()
