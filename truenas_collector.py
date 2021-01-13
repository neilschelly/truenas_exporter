#!/usr/bin/env python3

from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily
from prometheus_client import Counter
from datetime import datetime
import requests, urllib3, sys
from types import FunctionType
urllib3.disable_warnings()

from pprint import pprint

unknown_enumerations = Counter('truenas_exporter_unknown_enumerations', 'Enumerations that cannot be identified. Check the logs.')

class TrueNasCollector(object):
    def __init__(self, target, username, password):
        self.target = target
        self.username = username
        self.password = password

    def collect(self):
        metrics = []
        for collection in self._collections(): 
            """ Collect metrics from all the _collect functions """
            metrics = eval(f"self.{collection}()")
            for metric in metrics:
                """ Return all the metrics """
                yield metric

    def _collections(self):
        """ List of collect functions in this class to call """
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
        cloudsync = self.request('cloudsync')

        progress = GaugeMetricFamily(
            'truenas_cloudsync_progress',
            'Progress of last CloudSync job',
            labels=["description", "path"])
        state = GaugeMetricFamily(
            'truenas_cloudsync_state',
            'Current state of CloudSync job: 0==UNKNOWN, 1==RUNNING, 2==SUCCESS',
            labels=["description", "path"])
        result = GaugeMetricFamily(
            'truenas_cloudsync_result',
            'Result of last CloudSync job: 0==UNKNOWN, 1==None',
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

        unknown_enumerations.inc()
        print(f"Unknown/new CloudSync state: {value}. Needs to be added to " +
            " TrueNasCollector._cloudsync_state_enum()", file=sys.stderr)
        return 0

    def _cloudsync_result_enum(self, value):
        if value is None:
            return 1

        unknown_enumerations.inc()
        print(f"Unknown/new CloudSync result: {value}. Needs to be added to " +
            " TrueNasCollector._cloudsync_result_enum()", file=sys.stderr)
        return 0

    def _collect_alerts(self):
        alerts = self.request('alert/list')

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

    def _collect_disks(self):
        disks = self.request('disk')

        metrics = GaugeMetricFamily(
            'truenas_disk_bytes',
            'Disk size/info inventory',
            labels=["name", "serial", "type", "model"])

        for disk in disks:
            metrics.add_metric(
                [disk['name'], disk['serial'], disk['type'], disk['model']],
                disk['size']
            )            

        return [metrics]

    def _collect_interfaces(self):
        interfaces = self.request('interface')

        metrics = GaugeMetricFamily(
            'truenas_interface_state',
            'Interface state/info inventory:  0==UNKNOWN, 1==LINK_STATE_UP, 2==LINK_STATE_DOWN',
            labels=["name", "description", "type"])

        for interface in interfaces:
            metrics.add_metric(
                [interface['name'], interface['description'] or "", interface['type']],
                self._interfaces_state_enum(interface['state']['link_state'])
            )            

        return [metrics]

    def _interfaces_state_enum(self, value):
        if value == "LINK_STATE_UP":
            return 1
        if value == "LINK_STATE_DOWN":
            return 2

        unknown_enumerations.inc()
        print(f"Unknown/new Interface state: {value}. Needs to be added to " +
            " TrueNasCollector._interfaces_state_enum()", file=sys.stderr)
        return 0

    def _collect_pool_datasets(self):
        datasets = self.request('pool/dataset')

        size = GaugeMetricFamily(
            'truenas_pool_dataset_max_bytes',
            'Dataset size in bytes',
            labels=["name", "pool", "type"])
        used = GaugeMetricFamily(
            'truenas_pool_dataset_used_bytes',
            'Dataset used in bytes',
            labels=["name", "pool", "type"])
        children = GaugeMetricFamily(
            'truenas_pool_dataset_children',
            'Number of children inside dataset',
            labels=["name", "pool", "type"])

        for dataset in datasets:
            size.add_metric(
                [dataset['name'], dataset['pool'], dataset['type']],
                dataset['available']['parsed']
            )
            used.add_metric(
                [dataset['name'], dataset['pool'], dataset['type']],
                dataset['used']['parsed']
            )
            children.add_metric(
                [dataset['name'], dataset['pool'], dataset['type']],
                len(dataset['children'])
            )

        return [size,used,children]

    def _collect_pool(self):
        pools = self.request('pool')

        status = GaugeMetricFamily(
            'truenas_pool_status',
            'Pool status: 0=UNKNOWN, 1=ONLINE',
            labels=["name", "path"])
        healthy = GaugeMetricFamily(
            'truenas_pool_healthy',
            'Pool health',
            labels=["name", "path"])
        disk_status = GaugeMetricFamily(
            'truenas_pool_disk_status',
            'Status of disk in pool: 0=UNKNOWN, 1=ONLINE',
            labels=["name", "path", "device", "spare"])
        disk_errors = CounterMetricFamily(
            'truenas_pool_disk_errors',
            'Count of errors on disk in pool',
            labels=["name", "path", "device", "errortype"])

        for pool in pools:
            status.add_metric(
                [pool['name'], pool['path']],
                self._pool_health_enum(pool['status'])
            )
            healthy.add_metric(
                [pool['name'], pool['path']],
                int(pool['healthy'])
            )
            for topology in pool['topology']['data']:
                for disk in topology['children']:
                    disk_status.add_metric(
                        [pool['name'], pool['path'], disk['disk'] or disk['path'], "false"],
                        self._pool_health_enum(disk['status'])
                    )
                    disk_errors.add_metric(
                        [pool['name'], pool['path'], disk['disk'] or disk['path'], "read"],
                        disk['stats']['read_errors']
                    )
                    disk_errors.add_metric(
                        [pool['name'], pool['path'], disk['disk'] or disk['path'], "write"],
                        disk['stats']['write_errors']
                    )
                    disk_errors.add_metric(
                        [pool['name'], pool['path'], disk['disk'] or disk['path'], "checksum"],
                        disk['stats']['checksum_errors']
                    )
            for disk in pool['topology']['spare']:
                disk_status.add_metric(
                    [pool['name'], pool['path'], disk['disk'] or disk['path'], "true"],
                    self._pool_health_enum(disk['status'])
                )
                disk_errors.add_metric(
                    [pool['name'], pool['path'], disk['disk'] or disk['path'], "read"],
                    disk['stats']['read_errors']
                )
                disk_errors.add_metric(
                    [pool['name'], pool['path'], disk['disk'] or disk['path'], "write"],
                    disk['stats']['write_errors']
                )
                disk_errors.add_metric(
                    [pool['name'], pool['path'], disk['disk'] or disk['path'], "checksum"],
                    disk['stats']['checksum_errors']
                )

        return [status, healthy, disk_status, disk_errors]

    def _pool_health_enum(self, value):
        if value == "ONLINE":
            return 1

        unknown_enumerations.inc()
        print(f"Unknown/new Pool or Disk state: {value}. Needs to be added to " +
            " TrueNasCollector._pool_health_enum()", file=sys.stderr)
        return 0

    def _collect_replications(self):
        replications = self.request('replication')

        state = GaugeMetricFamily(
            'truenas_replication_state',
            'Current replication state: 0=UNKNOWN 1=SUCCESS 2=RUNNING',
            labels=["sources", "target", "target_system", "transport"])
        last_finished = GaugeMetricFamily(
            'truenas_replication_last_finished',
            'Replication last finished',
            labels=["sources", "target", "target_system", "transport"])
        elapsed = GaugeMetricFamily(
            'truenas_replication_last_elapsed',
            'Last replication elapsed milliseconds',
            labels=["sources", "target", "target_system", "transport"])
        progress = GaugeMetricFamily(
            'truenas_replication_progress',
            'Current replication progress',
            labels=["sources", "target", "target_system", "transport"])

        for replication in replications:
            labels = [
                ' '.join(replication['source_datasets']),
                replication['target_dataset'],
                replication['ssh_credentials']['attributes']['host'],
                replication['transport']
            ]
            state.add_metric(
                labels,
                self._replication_state_enum(replication['job']['state'])
            )
            if 'datetime' in replication['state']:
                last_finished.add_metric(
                    labels,
                    replication['state']['datetime']['$date']
                )
            if 'time_started' in replication['job']:
                if replication['job']['time_finished']:
                    elapsed.add_metric(
                        labels,
                        replication['job']['time_finished']['$date'] - replication['job']['time_started']['$date']
                    )
                else:
                    elapsed.add_metric(
                        labels,
                        1000*datetime.utcnow().timestamp() - replication['job']['time_started']['$date']
                    )
            progress.add_metric(
                labels,
                replication['job']['progress']['percent']
            )

        return [state, last_finished, elapsed, progress]

    def _replication_state_enum(self, value):
        if value == "SUCCESS":
            return 1
        if value == "RUNNING":
            return 2

        unknown_enumerations.inc()
        print(f"Unknown/new Replication state: {value}. Needs to be added to " +
            " TrueNasCollector._replication_state_enum()", file=sys.stderr)
        return 0

    def _collect_pool_snapshot_tasks(self):
        tasks = self.request('pool/snapshottask')

        status = GaugeMetricFamily(
            'truenas_pool_snapshot_task_status',
            'Pool snapshot task status: 0=UNKNOWN, 1=FINISHED',
            labels=["dataset"])
        timestamp = GaugeMetricFamily(
            'truenas_pool_snapshot_task_timestamp',
            'Pool snapshot task timestamp',
            labels=["dataset"])

        for task in tasks:
            status.add_metric(
                [task['dataset']],
                self._pool_snapshottask_status_enum(task['state']['state'])
            )
            if task['state']['datetime']:
                timestamp.add_metric(
                    [task['dataset']],
                    task['state']['datetime']['$date']
                )

        return [status, timestamp]

    def _pool_snapshottask_status_enum(self, value):
        if value == "FINISHED":
            return 1

        unknown_enumerations.inc()
        print(f"Unknown/new Snapshot Task state: {value}. Needs to be added to " +
            " TrueNasCollector._pool_snapshottask_status_enum()", file=sys.stderr)
        return 0

    def _collect_system_info(self):
        info = self.request('system/info')
        network = self.request('network/configuration')

        uptime = CounterMetricFamily(
            'truenas_uptime',
            'TrueNAS uptime',
            labels=["hostname"])
        cores = GaugeMetricFamily(
            'truenas_cores',
            'TrueNAS CPU core count',
            labels=["hostname"])
        memory = GaugeMetricFamily(
            'truenas_memory',
            'TrueNAS physical memory',
            labels=["hostname"])
        infometric = InfoMetricFamily(
            'truenas_info',
            'TrueNAS Information',
            labels=["hostname", "version", "serial", "serial_ha", "model", "product", "manufacturer"])
        ha = GaugeMetricFamily(
            'truenas_ha',
            'TrueNAS High Availability Controller Status: 0=N/A 1=hostname_1 master 2=hostname_2 master',
            labels=["hostname", "hostname_1", "hostname_2"])

        uptime.add_metric(
            [info['hostname']],
            info['uptime_seconds']
        )
        cores.add_metric(
            [info['hostname']],
            info['cores']
        )
        memory.add_metric(
            [info['hostname']],
            info['physmem']
        )
        infolabels = {
            'hostname': info['hostname'],
            'version': info['version'],
            'serial': info['license']['system_serial'],
            'serial_ha': info['license']['system_serial_ha'],
            'model': info['license']['model'],
            'product': info['system_product'],
            'manufacturer': info['system_manufacturer']
        }
        infometric.add_metric(
            infolabels.keys(),
            infolabels
        )
        ha_status = 0
        if network['hostname_virtual'] and network['hostname_local'] == network['hostname']:
            ha_status = 1
        elif network['hostname_virtual'] and network['hostname_local'] == network['hostname_b']:
            ha_status = 2
        ha.add_metric(
            [info['hostname'], network['hostname'], network['hostname_b']],
            ha_status
        )

        return [uptime, cores, memory, infometric, ha]

    def _collect_enclosure(self):
        enclosure = self.request('enclosure')

        health_metrics = GaugeMetricFamily(
            'truenas_enclosure_health',
            'TrueNAS enclosure device metrics',
            labels=["devicename", "devicemodel", "metrictype", "metricdevice", "metricelement"])
        health_status = GaugeMetricFamily(
            'truenas_enclosure_status',
            'TrueNAS enclosure device health 0=UNKNOWN, 1=OK',
            labels=["devicename", "devicemodel", "metrictype", "metricdevice", "metricelement"])

        for device in enclosure:
            devicename = device['name']
            devicemodel = device['model']

            for element in device['elements']:
                metrictype = element['name']
                metricdevice = element['descriptor']

                for leaf in element['elements']:
                    metricelement = leaf['descriptor']

                    health_metrics.add_metric(
                        [devicename, devicemodel, metrictype, metricdevice, metricelement],
                        self._enclosure_status_enum(leaf['status'])
                    )

                    if leaf['value'] and leaf['status'] not in ['Unknown', 'Not installed']:
                        if metrictype == "Cooling":
                            health_status.add_metric(
                                [devicename, devicemodel, metrictype, metricdevice, metricelement],
                                float(leaf['value'].split()[0])
                            )
                        elif metrictype == "Enclosure Services Controller Electronics":
                            health_status.add_metric(
                                [devicename, devicemodel, metrictype, metricdevice, metricelement],
                                leaf['value']
                            )
                        elif metrictype == "Temperature Sensor":
                            health_status.add_metric(
                                [devicename, devicemodel, metrictype, metricdevice, metricelement],
                                float(leaf['value'].split('C')[0])
                            )
                        elif metrictype == "Voltage Sensor":
                            health_status.add_metric(
                                [devicename, devicemodel, metrictype, metricdevice, metricelement],
                                float(leaf['value'].split('V')[0])
                            )

        return [health_metrics, health_status]

    def _enclosure_status_enum(self, value):
        if value == "OK":
            return 1
        elif value == "Unknown" or value == "Not installed":
            return 2

        unknown_enumerations.inc()
        print(f"Unknown/new enclosure health state: {value}. Needs to be added to " +
            " TrueNasCollector._enclosure_status_enum()", file=sys.stderr)
        return 0

    def _collect_smarttest(self):
        smarttests = self.request('smart/test/results')

        smarttest = GaugeMetricFamily(
            'truenas_smarttest_status',
            'TrueNAS SMART test result: 0=UNKNOWN 1=SUCCESS',
            labels=['disk', 'description'])
        lifetime = CounterMetricFamily(
            'truenas_smarttest_lifetime',
            'TrueNAS SMART lifetime',
            labels=['disk','description'])

        for disk in smarttests:
            smarttest.add_metric(
                [disk['disk'], disk['tests'][0]['description']],
                self._smart_test_result_enum(disk['tests'][0]['status'])
            )  
            lifetime.add_metric(
                [disk['disk'], disk['tests'][0]['description']],
                disk['tests'][0]['lifetime']
            )

        return [smarttest, lifetime]

    def _smart_test_result_enum(self, value):
        if value == "SUCCESS":
            return 1

        unknown_enumerations.inc()
        print(f"Unknown/new SMART health state: {value}. Needs to be added to " +
            " TrueNasCollector._smart_test_result_enum()", file=sys.stderr)
        return 0



    # FIXME: Need to monitor stats - might be a window to collectd stuff?
    # def _collect_stats(self):
    #     replications = self.request('stats')