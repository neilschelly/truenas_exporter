#!/usr/bin/env python3

from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily
from prometheus_client import Counter, Summary
from datetime import datetime
import requests, urllib3, sys, re
from types import FunctionType
urllib3.disable_warnings()

from pprint import pprint

unknown_enumerations = Counter('truenas_exporter_unknown_enumerations', 'Enumerations that cannot be identified. Check the logs.')
rsynctask_timer = Summary('truenas_exporter_rsynctask_seconds', 'Time spent making rsynctask API requests')
cloudsync_timer = Summary('truenas_exporter_cloudsync_seconds', 'Time spent making cloudsync API requests')
alerts_timer = Summary('truenas_exporter_alerts_seconds', 'Time spent making alerts API requests')
disks_timer = Summary('truenas_exporter_disks_seconds', 'Time spent making disks API requests')
interfaces_timer = Summary('truenas_exporter_interfaces_seconds', 'Time spent making interfaces API requests')
datasets_timer = Summary('truenas_exporter_datasets_seconds', 'Time spent making datasets API requests')
pools_timer = Summary('truenas_exporter_pools_seconds', 'Time spent making pools API requests')
replications_timer = Summary('truenas_exporter_replications_seconds', 'Time spent making replications API requests')
snapshots_timer = Summary('truenas_exporter_snapshots_seconds', 'Time spent making snapshots APIrequests')
systeminfo_timer = Summary('truenas_exporter_systeminfo_seconds', 'Time spent making systeminfo API requests')
enclosure_timer = Summary('truenas_exporter_enclosure_seconds', 'Time spent making enclosure API requests')
smarttests_timer = Summary('truenas_exporter_smarttests_seconds', 'Time spent making SMART test API requests')
stats_timer = Summary('truenas_exporter_stats_seconds', 'Time spent making stats API requests')

class TrueNasCollector(object):
    def __init__(self, target, username, password, cache_smart = 24, skip_snmp = False, skip_df_regex = None):
        self.target = target
        self.username = username
        self.password = password
        self.skip_snmp = skip_snmp
        self.cache_smart = 60*60*cache_smart
        self.skip_df_regex = skip_df_regex
        self.last_smart_result = {}
        self.last_smart_time = 0

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

    def request(self, apipath, data=None):
        try:
            request_path = f'https://{self.target}/api/v2.0/{apipath}'
            if data:
                r = requests.post(
                    request_path,
                    auth=(self.username, self.password),
                    headers={'Content-Type': 'application/json'},
                    verify=False,
                    json=data,
                    timeout=15
                )
            else:
                r = requests.get(
                    request_path,
                    auth=(self.username, self.password),
                    headers={'Content-Type': 'application/json'},
                    verify=False,
                    timeout=15
                )
        except requests.exceptions.ReadTimeout as e:
            print(f'Timeout requesting {request_path}...', file=sys.stderr)
            print(str(e), file=sys.stderr)
            return {}
        except requests.exceptions.ConnectionError as e:
            print(f'Connection error requesting {request_path}...',
                  file=sys.stderr)
            print(str(e), file=sys.stderr)
            return {}
        return r.json()

    @rsynctask_timer.time()
    def _collect_rsynctask(self):
        rsynctask = self.request('rsynctask')

        progress = GaugeMetricFamily(
            'truenas_rsynctask_progress',
            'Progress of last rsynctask job',
            labels=["description", "localpath", "remotehost", "remotepath", "direction", "enabled"])
        state = GaugeMetricFamily(
            'truenas_rsynctask_state',
            'Current state of rsynctask job: 0==UNKNOWN, 1==RUNNING, 2==SUCCESS, 3==FAILED',
            labels=["description", "localpath", "remotehost", "remotepath", "direction", "enabled"])
        elapsed = GaugeMetricFamily(
            'truenas_rsynctask_elapsed_seconds',
            'Elapsed time in seconds of last rsynctask job',
            labels=["description", "localpath", "remotehost", "remotepath", "direction", "enabled"])

        for sync in rsynctask:
            if sync['job']['progress']['percent']:
                progress.add_metric(
                    [sync['desc'], sync['path'], sync['remotehost'], sync['remotepath'], sync['direction'], str(sync['enabled'])],
                    sync['job']['progress']['percent']
                )
            state.add_metric(
                [sync['desc'], sync['path'], sync['remotehost'], sync['remotepath'], sync['direction'], str(sync['enabled'])],
                self._rsynctask_state_enum(sync['job']['state'])
            )
            if sync['job']['time_finished']:
                elapsed.add_metric(
                    [sync['desc'], sync['path'], sync['remotehost'], sync['remotepath'], sync['direction'], str(sync['enabled'])],
                    sync['job']['time_finished']['$date'] - sync['job']['time_started']['$date']
                )
            else:
                elapsed.add_metric(
                    [sync['desc'], sync['path'], sync['remotehost'], sync['remotepath'], sync['direction'], str(sync['enabled'])],
                    1000*datetime.now().timestamp() - sync['job']['time_started']['$date']
                )


        return [progress, state, elapsed]

    def _rsynctask_state_enum(self, value):
        if value == "RUNNING":
            return 1
        if value == "SUCCESS":
            return 2
        if value == "FAILED":
            return 3

        unknown_enumerations.inc()
        print(f"Unknown/new rsynctask state: {value}. Needs to be added to " +
            " TrueNasCollector._rsynctask_state_enum()", file=sys.stderr)
        return 0

    @cloudsync_timer.time()
    def _collect_cloudsync(self):
        cloudsync = self.request('cloudsync')

        progress = GaugeMetricFamily(
            'truenas_cloudsync_progress',
            'Progress of last CloudSync job',
            labels=["description", "path"])
        state = GaugeMetricFamily(
            'truenas_cloudsync_state',
            'Current state of CloudSync job: 0==UNKNOWN, 1==RUNNING, 2==SUCCESS, 3==NEVER, 4==FAILED, 5==ABORTED, 6==WAITING',
            labels=["description", "path"])
        result = GaugeMetricFamily(
            'truenas_cloudsync_result',
            'Result of last CloudSync job: 0==UNKNOWN, 1==None, 2==NEVER',
            labels=["description", "path"])
        elapsed = GaugeMetricFamily(
            'truenas_cloudsync_elapsed_seconds',
            'Elapsed time in seconds of last CloudSync job',
            labels=["description", "path"])

        for sync in cloudsync:
            if sync['job']:
                if sync['job']['progress']['percent']:
                    progress.add_metric(
                        [sync['description'], sync['path']],
                        sync['job']['progress']['percent']
                    )
                else:
                    progress.add_metric(
                        [sync['description'], sync['path']],
                        -1
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
                else:
                    elapsed.add_metric(
                        [sync['description'], sync['path']],
                        1000*datetime.now().timestamp() - sync['job']['time_started']['$date']
                    )
            else:
                state.add_metric(
                    [sync['description'], sync['path']],
                    self._cloudsync_state_enum("NEVER")
                )
                result.add_metric(
                    [sync['description'], sync['path']],
                    self._cloudsync_result_enum("NEVER")
                )                
        
        return [progress, state, result, elapsed]

    def _cloudsync_state_enum(self, value):
        if value == "RUNNING":
            return 1
        if value == "SUCCESS":
            return 2
        if value == "NEVER":
            return 3
        if value == "FAILED":
            return 4
        if value == "ABORTED":
            return 5
        if value == "WAITING":
            return 6

        unknown_enumerations.inc()
        print(f"Unknown/new CloudSync state: {value}. Needs to be added to " +
            " TrueNasCollector._cloudsync_state_enum()", file=sys.stderr)
        return 0

    def _cloudsync_result_enum(self, value):
        if value is None:
            return 1
        if value == "NEVER":
            return 2

        unknown_enumerations.inc()
        print(f"Unknown/new CloudSync result: {value}. Needs to be added to " +
            " TrueNasCollector._cloudsync_result_enum()", file=sys.stderr)
        return 0

    @alerts_timer.time()
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

    @disks_timer.time()
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

    @interfaces_timer.time()
    def _collect_interfaces(self):
        if self.skip_snmp:
            return []

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

    @datasets_timer.time()
    def _collect_pool_datasets(self):
        if self.skip_snmp:
            return []

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
        encrypted = GaugeMetricFamily(
            'truenas_pool_dataset_encrypted',
            'Dataset encryption enabled?',
            labels=["name", "pool", "type"])
        locked = GaugeMetricFamily(
            'truenas_pool_dataset_locked',
            'Dataset encryption locked?',
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
            encrypted.add_metric(
                [dataset['name'], dataset['pool'], dataset['type']],
                int(dataset['encrypted'])
            )
            locked.add_metric(
                [dataset['name'], dataset['pool'], dataset['type']],
                int(dataset['locked'])
            )

        return [size,used,children,encrypted,locked]

    @pools_timer.time()
    def _collect_pool(self):
        if self.skip_snmp:
            return []

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
                    label = "None"
                    if 'disk' in disk:
                        label = disk['disk']
                    elif 'path' in disk:
                        label = disk['path']
                    label = label or "unlabelled"
                    disk_status.add_metric(
                        [pool['name'], pool['path'], label, "false"],
                        self._pool_health_enum(disk['status'])
                    )
                    disk_errors.add_metric(
                        [pool['name'], pool['path'], label, "read"],
                        disk['stats']['read_errors']
                    )
                    disk_errors.add_metric(
                        [pool['name'], pool['path'], label, "write"],
                        disk['stats']['write_errors']
                    )
                    disk_errors.add_metric(
                        [pool['name'], pool['path'], label, "checksum"],
                        disk['stats']['checksum_errors']
                    )
            for disk in pool['topology']['spare']:
                label = "None"
                if 'disk' in disk:
                    label = disk['disk']
                elif 'path' in disk:
                    label = disk['path']
                label = label or "unlabelled"
                disk_status.add_metric(
                    [pool['name'], pool['path'], label, "true"],
                    self._pool_health_enum(disk['status'])
                )
                disk_errors.add_metric(
                    [pool['name'], pool['path'], label, "read"],
                    disk['stats']['read_errors']
                )
                disk_errors.add_metric(
                    [pool['name'], pool['path'], label, "write"],
                    disk['stats']['write_errors']
                )
                disk_errors.add_metric(
                    [pool['name'], pool['path'], label, "checksum"],
                    disk['stats']['checksum_errors']
                )

        return [status, healthy, disk_status, disk_errors]

    def _pool_health_enum(self, value):
        if value == "ONLINE":
            return 1
        if value == "UNAVAIL":
            return 2
        if value == "DEGRADED":
            return 3
        if value == "REMOVED":
            return 4
        if value == "OFFLINE":
            return 5

        unknown_enumerations.inc()
        print(f"Unknown/new Pool or Disk state: {value}. Needs to be added to " +
            " TrueNasCollector._pool_health_enum()", file=sys.stderr)
        return 0

    @replications_timer.time()
    def _collect_replications(self):
        replications = self.request('replication')

        state = GaugeMetricFamily(
            'truenas_replication_state',
            'Current replication state: 0=UNKNOWN 1=SUCCESS 2=RUNNING 3=FAILED 4=WAITING',
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
            if replication['transport'] == 'SSH+NETCAT':
                labels = [
                    ' '.join(replication['source_datasets']),
                    replication['target_dataset'],
                    replication['ssh_credentials']['attributes']['host'],
                    replication['transport']
                ]
            elif replication['transport'] == 'LOCAL':
                labels = [
                    ' '.join(replication['source_datasets']),
                    replication['target_dataset'],
                    'localhost',
                    replication['transport']
                ]

            if replication['job'] and 'state' in replication['job']:
                state.add_metric(
                    labels,
                    self._replication_state_enum(replication['job']['state'])
                )
            if 'datetime' in replication['state']:
                last_finished.add_metric(
                    labels,
                    replication['state']['datetime']['$date']
                )
            if replication['job'] is not None and 'time_started' in replication['job']:
                if replication['job']['time_finished']:
                    elapsed.add_metric(
                        labels,
                        replication['job']['time_finished']['$date'] - replication['job']['time_started']['$date']
                    )
                else:
                    elapsed.add_metric(
                        labels,
                        1000*datetime.now().timestamp() - replication['job']['time_started']['$date']
                    )
            if replication['job'] is not None and replication['job']['progress']['percent']:
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
        if value == "FAILED":
            return 3
        if value == "WAITING":
            return 4

        unknown_enumerations.inc()
        print(f"Unknown/new Replication state: {value}. Needs to be added to " +
            " TrueNasCollector._replication_state_enum()", file=sys.stderr)
        return 0

    @snapshots_timer.time()
    def _collect_pool_snapshot_tasks(self):
        tasks = self.request('pool/snapshottask')

        status = GaugeMetricFamily(
            'truenas_pool_snapshot_task_status',
            'Pool snapshot task status: 0=UNKNOWN, 1=FINISHED, 2=RUNNING, 3=ERROR, 4=PENDING, 5=HOLD',
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
            try:
                if task['state']['datetime']:
                    timestamp.add_metric(
                        [task['dataset']],
                        task['state']['datetime']['$date']
                    )
            except KeyError:
                pass

        return [status, timestamp]

    def _pool_snapshottask_status_enum(self, value):
        if value == "FINISHED":
            return 1
        elif value == 'RUNNING':
            return 2
        elif value == 'ERROR':
            return 3
        elif value == 'PENDING':
            return 4
        elif value == 'HOLD':
            return 5

        unknown_enumerations.inc()
        print(f"Unknown/new Snapshot Task state: {value}. Needs to be added to " +
            " TrueNasCollector._pool_snapshottask_status_enum()", file=sys.stderr)
        return 0

    @systeminfo_timer.time()
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
            'truenas',
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

    @enclosure_timer.time()
    def _collect_enclosure(self):
        enclosure = self.request('enclosure')

        health_metrics = GaugeMetricFamily(
            'truenas_enclosure_health',
            'TrueNAS enclosure device metrics',
            labels=["devicename", "devicemodel", "metrictype", "metricdevice", "metricelement"])
        health_status = GaugeMetricFamily(
            'truenas_enclosure_status',
            'TrueNAS enclosure device health 0=UNKNOWN, 1=OK or (OK, Swapped), 2=Unknown/Not-installed 3=Critical, 4=Unsupported, 5=(Not Installed, Swapped)',
            labels=["devicename", "devicemodel", "metrictype", "metricdevice", "metricelement"])

        for device in enclosure:
            devicename = device['name']
            devicemodel = device['model']
            for elementname in device['elements']:
                metrictype = elementname
                element = device['elements'][elementname]
                for leafname in element:
                    metricdevice = f"{elementname} {leafname}"
                    leaf = element[leafname]
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
        if value in ["OK", "OK, Swapped"]:
            return 1
        elif value == "Unknown" or value == "Not installed":
            return 2
        elif value == "Critical":
            return 3
        elif value == "Unsupported":
            return 4
        elif value == "Not Installed, Swapped":
            return 5

        unknown_enumerations.inc()
        print(f"Unknown/new enclosure health state: {value}. Needs to be added to " +
            " TrueNasCollector._enclosure_status_enum()", file=sys.stderr)
        return 0

    @smarttests_timer.time()
    def _collect_smarttest(self):

        # self.cache_smart = cache_smart
        # self.last_smart_result = {}
        # self.last_smart_time = 0

        nowstamp = int(datetime.now().timestamp())
        if (nowstamp - self.last_smart_time) > (self.cache_smart):
            smarttests = self.request('smart/test/results')
            if smarttests:
                self.last_smart_time = nowstamp
                self.last_smart_result = smarttests
        else:
            smarttests = self.last_smart_result

        smarttest = GaugeMetricFamily(
            'truenas_smarttest_status',
            'TrueNAS SMART test result: 0=UNKNOWN 1=SUCCESS 2=RUNNING 3=FAILED',
            labels=['disk', 'description'])
        cachetime = GaugeMetricFamily(
            'truenas_smarttest_cache_age_seconds',
            'Seconds since last check of the smart/tests/results API.')
        lifetime = CounterMetricFamily(
            'truenas_smarttest_lifetime',
            'TrueNAS SMART lifetime',
            labels=['disk','description'])

        cachetime.add_metric([], nowstamp-self.last_smart_time)

        for disk in smarttests:
            if (len(disk['tests']) > 0):
                smarttest.add_metric(
                    [disk['disk'], disk['tests'][0]['description']],
                    self._smart_test_result_enum(disk['tests'][0]['status'])
                )
                if disk['tests'][0]['lifetime']:
                    lifetime.add_metric(
                        [disk['disk'], disk['tests'][0]['description']],
                        disk['tests'][0]['lifetime']
                    )

        return [smarttest, cachetime, lifetime]

    def _smart_test_result_enum(self, value):
        if value == "SUCCESS":
            return 1
        elif value == "RUNNING":
            return 2
        elif value == "FAILED":
            return 3

        unknown_enumerations.inc()
        print(f"Unknown/new SMART health state: {value}. Needs to be added to " +
            " TrueNasCollector._smart_test_result_enum()", file=sys.stderr)
        return 0

    @stats_timer.time()
    def _collect_stats(self):
        """ Return all current data from CollectD collections """

        # This is complicated for a bunch of performance reasons
        # /api/v2.0/stats/get_sources and available metrics for the source
        #
        # You can get the definition for a source/metric from above by sending a
        # POST like {"source": "zfs_arc", "type": "hash_collisions"} to
        # /api/v2.0/stats/get_dataset_info
        #
        # Requesting that for all items in the get_sources results one at a time
        # takes a prohibitively long time. Information from that process was
        # used to build this function that cycles through the hardware inventory
        # from /stats/get_sources and uses it to build a list of metrics to
        # request data from
        #
        # The actual data from these sources can be done with a single request
        # to /api/v2.0/stats/get_data, using the structure for each source
        # derived above.
        #
        # After all that, there's no way to get "the most recent data point" for
        # a given metric. As a result, we are requesting the metrics from 30s
        # ago because those should exist by now. Requesting metrics for "now"
        # will yield None for the values.

        stats = self.request('stats/get_sources')

        skip_df_regex = None

        if self.skip_df_regex:
            skip_df_regex = re.compile(self.skip_df_regex)

        collectd = GaugeMetricFamily(
            'truenas_collectd',
            'TrueNAS CollectD Metrics',
            labels=['source', 'metric', 'submetric', 'metrictype'])

        sources = {}
        sources['cpu'] = ['aggregation-cpu-average', 'aggregation-cpu-sum']
        sources['temperature'] = []
        sources['ctl'] = ['ctl-ioctl', 'ctl-tpc']
        sources['df'] = []
        sources['disk'] = []
        sources['interface'] = []

        disk_list = []

        for source in stats:
            if source.split('-')[0] == 'cpu':
                sources['cpu'] += [source]
            elif source.split('-')[0] == 'cputemp':
                sources['temperature'] += [source]
            elif source.split('-')[0] == 'df':
                sources['df'] += [source]
            elif source.split('-')[0] == 'disk':
                sources['disk'] += [source]
            elif source.split('-')[0] == 'disktemp':
                sources['temperature'] += [source]
            elif source.split('-')[0] == 'interface':
                sources['interface'] += [source]

        request_timestamp = int(datetime.now().timestamp())
        sources_metadata = []
        sources_request = {
            "stats_list": [],
            "stats-filter": {
                "start": request_timestamp-900,
                "end": request_timestamp
            }
        }

        for source in sources['cpu']:
            for metric in ['cpu-idle', 'cpu-nice', 'cpu-system', 'cpu-interrupt', 'cpu-user']:
                sources_request['stats_list'] += [{
                    "source": source,
                    "type": metric,
                    "dataset": "value"
                }]
                sources_metadata += [{
                    "source": source,
                    "metric": metric,
                    "submetric": "value",
                    "metrictype": "DERIVE"
                }]
        for source in sources['temperature']:
            sources_request['stats_list'] += [{
                "source": source,
                "type": "temperature",
                "dataset": "value"
            }]
            sources_metadata += [{
                "source": source,
                "metric": "temperature",
                "submetric": "value",
                "metrictype": "GAUGE"
            }]
        for source in sources['ctl']:
            for metric in ['disk_octets', 'disk_octets-0-0', 'disk_ops', 'disk_ops-0-0', 'disk_time', 'disk_time-0-0']:
                for submetric in ['read', 'write']:
                    sources_request['stats_list'] += [{
                        "source": source,
                        "type": metric,
                        "dataset": submetric
                    }]
                    sources_metadata += [{
                        "source": source,
                        "metric": metric,
                        "submetric": submetric,
                        "metrictype": "DERIVE"
                    }]
        for source in sources['df']:
            for metric in ['df_complex-free', 'df_complex-reserved', 'df_complex-used']:
                if self.skip_df_regex and not skip_df_regex.search(source):
                    # Only get these metrics if they aren't in the optional skip_df_regex
                    sources_request['stats_list'] += [{
                        "source": source,
                        "type": metric,
                        "dataset": "value"
                    }]
                    sources_metadata += [{
                        "source": source,
                        "metric": metric,
                        "submetric": "value",
                        "metrictype": "GAUGE"
                    }]
        for source in sources['disk']:
            disk_list += [source.split('-')[1]]
            for metric in ['disk_octets', 'disk_ops', 'disk_time']:
                for submetric in ['read', 'write']:
                    sources_request['stats_list'] += [{
                        "source": source,
                        "type": metric,
                        "dataset": submetric
                    }]
                    sources_metadata += [{
                        "source": source,
                        "metric": metric,
                        "submetric": submetric,
                        "metrictype": "DERIVE"
                    }]
        for source in sources['disk']:
            for submetric in ['io_time', 'weighted_io_time']:
                sources_request['stats_list'] += [{
                    "source": source,
                    "type": 'disk_io_time',
                    "dataset": submetric
                }]
                sources_metadata += [{
                    "source": source,
                    "metric": 'disk_io_time',
                    "submetric": submetric,
                    "metrictype": "DERIVE"
                }]
        for disk in disk_list:
            sources_request['stats_list'] += [{
                "source": 'geom_stat',
                "type": '-'.join(['geom_busy_percent', disk]),
                "dataset": "value"
            }]
            sources_metadata += [{
                "source": 'geom_stat',
                "metric": '-'.join(['geom_busy_percent', disk]),
                "submetric": "value",
                "metrictype": "GAUGE"
            }]
        for disk in disk_list:
            for metric in ['geom_ops', 'geom_queue']:
                sources_request['stats_list'] += [{
                    "source": 'geom_stat',
                    "type": '-'.join([metric, disk]),
                    "dataset": "length"
                }]
                sources_metadata += [{
                    "source": 'geom_stat',
                    "metric": '-'.join([metric, disk]),
                    "submetric": "length",
                    "metrictype": "GAUGE"
                }]
        for disk in disk_list:
            for metric in ['geom_bw', 'geom_latency', 'geom_ops_rwd']:
                for submetric in ['delete', 'read', 'write']:
                    sources_request['stats_list'] += [{
                        "source": 'geom_stat',
                        "type": '-'.join([metric, disk]),
                        "dataset": submetric
                    }]
                    sources_metadata += [{
                        "source": 'geom_stat',
                        "metric": '-'.join([metric, disk]),
                        "submetric": submetric,
                        "metrictype": "GAUGE"
                    }]
        if self.skip_snmp == False:
            for source in sources['interface']:
                for metric in ['if_errors', 'if_octets', 'if_packets']:
                    for submetric in ['rx', 'tx']:
                        sources_request['stats_list'] += [{
                            "source": source,
                            "type": metric,
                            "dataset": submetric
                        }]
                        sources_metadata += [{
                            "source": source,
                            "metric": metric,
                            "submetric": submetric,
                            "metrictype": "DERIVE"
                        }]
        for submetric in ['longterm', 'midterm', 'shortterm']:
            sources_request['stats_list'] += [{
                "source": "load",
                "type": 'load',
                "dataset": submetric
            }]
            sources_metadata += [{
                "source": "load",
                "metric": 'load',
                "submetric": submetric,
                "metrictype": "GAUGE"
            }]
        for metric in ['active', 'cache', 'free', 'inactive', 'laundry', 'wired']:
            sources_request['stats_list'] += [{
                "source": "memory",
                "type": '-'.join(['memory', metric]),
                "dataset": 'value'
            }]
            sources_metadata += [{
                "source": "memory",
                "metric": '-'.join(['memory', metric]),
                "submetric": 'value',
                "metrictype": "GAUGE"
            }]
        for source in ['nfsstat-client', 'nfsstat-server']:
            for metric in ['access', 'commit', 'create', 'fsinfo', 'fsstat', 'getattr', 'link', 'lookup', 'mkdir', 'mknod', 'pathconf', 'read', 'readdir', 'readirplus', 'readlink', 'remove', 'rename', 'rmdir', 'setattr', 'symlink', 'write']:
                sources_request['stats_list'] += [{
                    "source": source,
                    "type": '-'.join(['nfsstat', metric]),
                    "dataset": 'value'
                }]
                sources_metadata += [{
                    "source": "memory",
                    "metric": '-'.join(['memory', metric]),
                    "submetric": 'value',
                    "metrictype": "DERIVE"
                }]
        for metric in ['blocked', 'idle', 'running', 'sleeping', 'stopped', 'wait', 'zombies']:
            sources_request['stats_list'] += [{
                "source": "processes",
                "type": '-'.join(['ps_state', metric]),
                "dataset": 'value'
            }]
            sources_metadata += [{
                "source": "processes",
                "metric": '-'.join(['ps_state', metric]),
                "submetric": 'value',
                "metrictype": "GAUGE"
            }]
        for metric in ['swap-free', 'swap-used']:
            sources_request['stats_list'] += [{
                "source": "swap",
                "type": metric,
                "dataset": 'value'
            }]
            sources_metadata += [{
                "source": "swap",
                "metric": metric,
                "submetric": 'value',
                "metrictype": "GAUGE"
            }]
        sources_request['stats_list'] += [{
            "source": "uptime",
            "type": "uptime",
            "dataset": 'value'
        }]
        sources_metadata += [{
            "source": "uptime",
            "metric": "uptime",
            "submetric": 'value',
            "metrictype": "GAUGE"
        }]
        for metric in ['cache_eviction-cached', 'cache_eviction-eligible', 'cache_eviction-ineligible', 'cache_operation-allocated', 'cache_operation-deleted', 'cache_result-demand_data-hit', 'cache_result-demand_data-miss', 'cache_result-demand_metadata-hit', 'cache_result-demand_metadata-miss', 'cache_result-mfu-hit', 'cache_result-mfu_ghost-hit', 'cache_result-mru-hit', 'cache_result-mru_ghost-hit', 'cache_result-prefetch_data-hit', 'cache_result-prefetch_data-miss', 'cache_result-prefetch_metadata-hit', 'cache_result-prefetch_metadata-miss', 'hash_collisions', 'memory_throttle_count', 'mutex_operations-miss']:
            sources_request['stats_list'] += [{
                "source": "zfs_arc",
                "type": metric,
                "dataset": 'value'
            }]
            sources_metadata += [{
                "source": "zfs_arc",
                "metric": metric,
                "submetric": 'value',
                "metrictype": "DERIVE"
            }]
        for metric in ['cache_ratio-arc', 'cache_ratio-L2', 'cache_size-anon_size', 'cache_size-arc', 'cache_size-c', 'cache_size-c_max', 'cache_size-c_min', 'cache_size-hdr_size', 'cache_size-L2', 'cache_size-metadata_size', 'cache_size-mfu_ghost_size', 'cache_size-mfu_size', 'cache_size-mru_ghost_size', 'cache_size-mru_size', 'cache_size-other_size', 'cache_size-p']:
            sources_request['stats_list'] += [{
                "source": "zfs_arc",
                "type": metric,
                "dataset": 'value'
            }]
            sources_metadata += [{
                "source": "zfs_arc",
                "metric": metric,
                "submetric": 'value',
                "metrictype": "GAUGE"
            }]
        for submetric in ['rx', 'tx',]:
            sources_request['stats_list'] += [{
                "source": "zfs_arc",
                "type": "io_octets-L2",
                "dataset": submetric
            }]
            sources_metadata += [{
                "source": "zfs_arc",
                "metric": "io_octets-L2",
                "submetric": submetric,
                "metrictype": "DERIVE"
            }]
        for metric in ['arcstat_ratio_arc-hits', 'arcstat_ratio_arc-l2_hits', 'arcstat_ratio_arc-l2_misses', 'arcstat_ratio_arc-misses', 'arcstat_ratio_data-demand_data_hits', 'arcstat_ratio_data-demand_data_misses', 'arcstat_ratio_data-prefetch_data_hits', 'arcstat_ratio_data-prefetch_data_misses', 'arcstat_ratio_metadata-demand_metadata_hits', 'arcstat_ratio_metadata-demand_metadata_misses', 'arcstat_ratio_metadata-prefetch_metadata_hits', 'arcstat_ratio_metadata-prefetch_metadata_misses', 'arcstat_ratio_mu-mfu_ghost_hits', 'arcstat_ratio_mu-mfu_hits', 'arcstat_ratio_mu-mru_ghost_hits', 'arcstat_ratio_mu-mru_hits', 'gauge_arcstats_raw-l2_asize', 'gauge_arcstats_raw-l2_hdr_size', 'gauge_arcstats_raw-l2_size', 'gauge_arcstats_raw_arcmeta-arc_meta_limit', 'gauge_arcstats_raw_arcmeta-arc_meta_max', 'gauge_arcstats_raw_arcmeta-arc_meta_min', 'gauge_arcstats_raw_arcmeta-arc_meta_used', 'gauge_arcstats_raw_counts-allocated', 'gauge_arcstats_raw_counts-deleted', 'gauge_arcstats_raw_counts-mutex_miss', 'gauge_arcstats_raw_counts-recycle_miss', 'gauge_arcstats_raw_counts-stolen', 'gauge_arcstats_raw_cp-c', 'gauge_arcstats_raw_cp-c_max', 'gauge_arcstats_raw_cp-c_min', 'gauge_arcstats_raw_cp-p', 'gauge_arcstats_raw_demand-demand_data_hits', 'gauge_arcstats_raw_demand-demand_data_misses', 'gauge_arcstats_raw_demand-demand_metadata_hits', 'gauge_arcstats_raw_demand-demand_metadata_misses', 'gauge_arcstats_raw_duplicate-duplicate_buffers', 'gauge_arcstats_raw_duplicate-duplicate_buffers_size', 'gauge_arcstats_raw_duplicate-duplicate_reads', 'gauge_arcstats_raw_evict-evict_l2_cached', 'gauge_arcstats_raw_evict-evict_l2_eligible', 'gauge_arcstats_raw_evict-evict_l2_ineligible', 'gauge_arcstats_raw_evict-evict_skip', 'gauge_arcstats_raw_hash-hash_chain_max', 'gauge_arcstats_raw_hash-hash_chains', 'gauge_arcstats_raw_hash-hash_collisions', 'gauge_arcstats_raw_hash-hash_elements', 'gauge_arcstats_raw_hash-hash_elements_max', 'gauge_arcstats_raw_hits_misses-hits', 'gauge_arcstats_raw_hits_misses-misses', 'gauge_arcstats_raw_l2-l2_cksum_bad', 'gauge_arcstats_raw_l2-l2_feeds', 'gauge_arcstats_raw_l2-l2_hits', 'gauge_arcstats_raw_l2-l2_io_error', 'gauge_arcstats_raw_l2-l2_misses', 'gauge_arcstats_raw_l2-l2_rw_clash', 'gauge_arcstats_raw_l2_compress-l2_compress_failures', 'gauge_arcstats_raw_l2_compress-l2_compress_successes', 'gauge_arcstats_raw_l2_compress-l2_compress_zeros', 'gauge_arcstats_raw_l2_free-l2_cdata_free_on_write', 'gauge_arcstats_raw_l2_free-l2_free_on_write', 'gauge_arcstats_raw_l2abort-l2_abort_lowmem', 'gauge_arcstats_raw_l2bytes-l2_read_bytes', 'gauge_arcstats_raw_l2bytes-l2_write_bytes', 'gauge_arcstats_raw_l2evict-l2_evict_lock_retry', 'gauge_arcstats_raw_l2evict-l2_evict_reading', 'gauge_arcstats_raw_l2write-l2_write_buffer_bytes_scanned', 'gauge_arcstats_raw_l2write-l2_write_buffer_iter', 'gauge_arcstats_raw_l2write-l2_write_buffer_list_iter', 'gauge_arcstats_raw_l2write-l2_write_buffer_list_null_iter', 'gauge_arcstats_raw_l2write-l2_write_full', 'gauge_arcstats_raw_l2write-l2_write_in_l2', 'gauge_arcstats_raw_l2write-l2_write_io_in_progress', 'gauge_arcstats_raw_l2write-l2_write_not_cacheable', 'gauge_arcstats_raw_l2write-l2_write_passed_headroom', 'gauge_arcstats_raw_l2write-l2_write_pios', 'gauge_arcstats_raw_l2write-l2_write_spa_mismatch', 'gauge_arcstats_raw_l2write-l2_write_trylock_fail', 'gauge_arcstats_raw_l2writes-l2_writes_done', 'gauge_arcstats_raw_l2writes-l2_writes_error', 'gauge_arcstats_raw_l2writes-l2_writes_hdr_miss', 'gauge_arcstats_raw_l2writes-l2_writes_sent', 'gauge_arcstats_raw_memcount-memory_throttle_count', 'gauge_arcstats_raw_mru-mfu_ghost_hits', 'gauge_arcstats_raw_mru-mfu_hits', 'gauge_arcstats_raw_mru-mru_ghost_hits', 'gauge_arcstats_raw_mru-mru_hits', 'gauge_arcstats_raw_prefetch-prefetch_data_hits', 'gauge_arcstats_raw_prefetch-prefetch_data_misses', 'gauge_arcstats_raw_prefetch-prefetch_metadata_hits', 'gauge_arcstats_raw_prefetch-prefetch_metadata_misses', 'gauge_arcstats_raw_size-data_size', 'gauge_arcstats_raw_size-hdr_size', 'gauge_arcstats_raw_size-other_size', 'gauge_arcstats_raw_size-size']:
            sources_request['stats_list'] += [{
                "source": "zfs_arc_v2",
                "type": metric,
                "dataset": 'value'
            }]
            sources_metadata += [{
                "source": "zfs_arc_v2",
                "metric": metric,
                "submetric": 'value',
                "metrictype": "GAUGE"
            }]

        data = self._stats_request(sources_request)
        if len(data) and len(data['data']) > 0:
            for index, metric in enumerate(sources_metadata):
                value = self._stats_latest_data(index, data['data'])
                if metric['source'].split('-')[0] == 'cputemp':
                    """ value is in Kelvin, and it's off by a power of 10 """
                    try:
                        value = str(float(value)/10 - 273.15)
                    except TypeError:
                        value = None
                if value:
                    collectd.add_metric(
                        [metric['source'], metric['metric'], metric['submetric'], metric['metrictype']],
                        value
                    )
        else:
            print("Empty response for collectd metadata for unknown reason", file=sys.stderr)

        return [collectd]

    def _stats_request(self, sources_request):
        """ Make the API call(s) for stats"""

        # If sources_request includes too many stats_list items in it, like if
        # you have a lot of datasets, a single call to the API will fail. The
        # middleware on the TrueNAS will run `rrdtool` with so many arguments
        # that it will get an 'Argument list too long' error.

        # This function will break it up into multiple calls when over 1200
        # stats_list items, and recombine them as if they came from a single
        # call.

        # No way around it, if this has to make multiple calls, it will be slow

        index = 0
        max_items = 1200
        return_data = {'data':[]}

        while len(sources_request['stats_list']) > index:
            this_sources_request = {
                "stats_list": sources_request['stats_list'][index:index+max_items],
                "stats-filter": sources_request['stats-filter']
            }
            if this_sources_request['stats_list']:
                try:
                    data = self.request("stats/get_data", this_sources_request)
                    response = data['data']
                except KeyError as e:
                    print("Invalid response from TrueNAS API:")
                    print(data)
                    continue
                if return_data['data']:
                    # New metrics are appended to lists from old metrics
                    # See _stats_latest_data comments for an explanation of how
                    # this list of lists needs to look in the end
                    return_data['data'] = [i[0]+i[1] for i in list(zip(return_data['data'],response))]
                else:
                    # First data returns needs to create the return_data['data'] structure
                    return_data['data'] = response
            index += max_items

        return return_data

    def _stats_latest_data(self, index, data):
        """ find the latest data point for a given metric """

        # Here's the structure of data:
        #  "data": [ [29.0,29.98], [29.0,29.0], [29.0,29.02], [29.0,30.0] ]
        # Each of the lists in the list represents a different timestamp with
        # data. We reuested datapoints from the last 15 minutes.
        # Each of the numbers in each  of those lists represents the different
        # metrics requested. index is the one of these we want to return.

        # Start at the last list (latest data), and traverse the data backwards
        # until we find a valid data point for the metric.
        latest = len(data) - 1
        while latest >= 0:
            if data[latest][index]:
                return str(data[latest][index])
            latest -= 1

        return None
