#!/usr/bin/env python3

from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
import requests, urllib3, sys
from types import FunctionType

from pprint import pprint

urllib3.disable_warnings()

class TrueNasCollector(object):
    def __init__(self, target, username, password):
        self.target = target
        self.username = username
        self.password = password
        pprint(self.__dict__)

    def collect(self):
        metrics = []
        for collection in self._collections(): 
            metrics += eval(f"self.{collection}()")
        for metric in metrics:
            yield metric

    def _collections(self):
        return [x for x, y in TrueNasCollector.__dict__.items() if type(y) == FunctionType and y.__name__.startswith("_collect_")]

    def request(self, apipath):
        r = requests.get(
            f'https://{self.target}/api/v2.0/{apipath}',
            auth=(self.username, self.password),
            headers={'Content-Type': 'application/json'},
            verify=False
        )
        return r.json()

    def _collect_cloudsync(self):
        cloudsync = self.request('cloudsync/')
        pprint(cloudsync)
        progress = GaugeMetricFamily(
            'truenas_cloudsync_progress',
            'Progress of last CloudSync job',
            labels=["description", "path"])
        state = GaugeMetricFamily(
            'truenas_cloudsync_state',
            'Current state of CloudSync job',
            labels=["description", "path"])
        result = GaugeMetricFamily(
            'truenas_cloudsync_result',
            'Result of last CloudSync job',
            labels=["description", "path"])
        elapsed = GaugeMetricFamily(
            'truenas_cloudsync_elapsed_seconds',
            'Elapsed time in seconds of last CloudSync job',
            labels=["description", "path"])

        for sync in cloudsync:
            progress.add_metric(
                [sync['description'], sync['path']],
                sync['job']['progress']['percent']
            )
            state.add_metric(
                [sync['description'], sync['path']],
                self._cloudsync_state_enum(sync['job']['state'])
            )
            result.add_metric(
                [sync['description'], sync['path']],
                self._cloudsync_result_enum(sync['job']['result'])
            )
            if sync['job']['time_finished']:
                elapsed.add_metric(
                    [sync['description'], sync['path']],
                    sync['job']['time_finished']['$date'] - sync['job']['time_started']['$date'] 
                )
        
        return [progress, state, result, elapsed]

    def _cloudsync_state_enum(self, value):
        if value == "RUNNING":
            return 1
        if value == "SUCCESS":
            return 2
        print(f"Unknown/new CloudSync state: {value}. Needs to be added to " +
            " TrueNasCollector._cloudsync_state_enum()", file=sys.stderr)
        return 0

    def _cloudsync_result_enum(self, value):
        if value is None:
            return 1
        print(f"Unknown/new CloudSync result: {value}. Needs to be added to " +
            " TrueNasCollector._cloudsync_result_enum()", file=sys.stderr)
        return 0

    def _collect_alerts(self):
        alerts = self.request('alert/list')
        pprint(alerts)

        count = GaugeMetricFamily(
            'truenas_alerts',
            'Current count of un-dismissed alerts',
            labels=["node", "klass", "level"])

        counts = {}
        for alert in alerts:
            if alert['dismissed']:
                continue
            key = f"{alert['klass']}_{alert['level']}_{alert['node']}"
            if not key in counts:
                counts[key] = 0
            counts[key] += 1

        for metric in counts:
            (klass, level, node) = metric.split('_', 2)
            count.add_metric(
                [node, klass, level],
                counts[metric]
            )
        return [count]
