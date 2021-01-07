#!/usr/bin/env python3

from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
import random 

class TrueNasCollector(object):
    def collect(self):
        yield GaugeMetricFamily('my_gauge', 'Help text', value=7)
        c = CounterMetricFamily('my_counter_total', 'Help text', labels=['foo'])
        c.add_metric(['bar'], 1.7)
        if random.choice([True, False]):
            c.add_metric(['baz'], 3.8)
        yield c
