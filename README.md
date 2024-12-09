# TrueNAS Exporter

The TrueNAS devices can be monitored by SNMP and CollectD. The CollectD stuff is
only really visible in the UI in RRD graphs, unless you install the [collectd
exporter](https://github.com/prometheus/collectd_exporter) onto the devices.
That works, but is unreliable, because many things like system upgrades, HA
failovers, etc will "fix" the installation and remove it. This exporter aims
to fill that gap by monitoring TrueNAS devices via their API.

**Important Note:**
We have used this on TrueNAS releases from 11.x up to 13.0 on TrueNAS X20
hardware. It has been mostly derived from reverse-engineering the API. The
TrueNAS docs do tell you how to query things, but not necessarily the
structure and meaning of the responses. It has worked well enough for us to
make use of things for a few years.

## Usage

### CLI

```shell
$ ./truenas_exporter.py --help
usage: truenas_exporter.py [-h] [--port PORT] --target TARGET [--skip-snmp]
                           [--cache-smart] [--skip-df-regex SKIP_DF_REGEX]

Return Prometheus metrics from querying the TrueNAS API.Set TRUENAS_USER and
TRUENAS_PASS as needed to reach the API.

optional arguments:
  -h, --help            show this help message and exit
  --port PORT           Listening HTTP port for Prometheus exporter
  --target TARGET       Target IP/Name of TrueNAS Device
  --skip-snmp           Skip metrics available via SNMP - may save about a
                        second in scrape time
  --cache-smart         Time to cache SMART test results for in hours. These
                        probably only update once a week.
  --skip-df-regex SKIP_DF_REGEX
                        Regular expression that will match filesystems to skip
                        for costly df metrics.
```

At a minimum, you must give it a target TrueNAS device on the command line. It
will read the environment variables `TRUENAS_USER` and `TRUENAS_PASS` for
authenticating to the API. For TrueNAS devices, the `TRUENAS_USER` must be
`root`.  The `--port` option can be specified to any port you'd like to listen
on for scrape requests.

The `--skip-snmp` option should shave about a second or two off the scrape time
by skipping metrics that can also be easily retrieved via SNMP.

If you have a lot of filesystems mounted, then the stats collector that pulls
information on filesystems from collectd can get really slow. Use the
`--skip-df-regex` option to give a regular expression for any filesystems' df
metrics that should be skipped. The string you're matching against will be
something like `df-mnt-tank-path-to-mount-point`. Note that the slashes are
replaced with dashes in "path-to-mount-point."

### Docker Container

* `make build` will create a container.
* `TARGET=truenas.example.net make run` will run it, targeting a TrueNAS device
  called truenas.example.net.

### Metrics

|| Metric name || Type || Description ||
| truenas_exporter_unknown_enumerations | Counter | Enumerations that cannot be identified. Check the logs. |
| truenas_exporter_SOMETHING_seconds | Summary | Time spent making _SOMETHING_ API requests. |
| truenas_rsynctask_progress | Gauge | Progress of last rsynctask job |
| truenas_rsynctask_state | Gauge | Current state of rsynctask job: 0==UNKNOWN, 1==RUNNING, 2==SUCCESS, 3==FAILED |
| truenas_rsynctask_elapsed_seconds | Gauge | Elapsed time in seconds of last rsynctask job |
| truenas_cloudsync_progress | Gauge | Progress of last CloudSync job |
| truenas_cloudsync_state | Gauge | Current state of CloudSync job: 0==UNKNOWN, 1==RUNNING, 2==SUCCESS, 3==NEVER, 4==FAILED, 5==ABORTED, 6==WAITING |
| truenas_cloudsync_result | Gauge | Result of last CloudSync job: 0==UNKNOWN, 1==None, 2==NEVE |
| truenas_cloudsync_elapsed_seconds | Gauge | Elapsed time in seconds of last CloudSync jo |
| truenas_alerts | Gauge | Current count of un-dismissed alerts |
| truenas_disk_bytes | Gauge | Disk size/info inventory |
| truenas_interface_state | Gauge | Interface state/info inventory:  0==UNKNOWN, 1==LINK_STATE_UP, 2==LINK_STATE_DOWN |
| truenas_pool_dataset_max_bytes | Gauge | Dataset size in bytes |
| truenas_pool_dataset_used_bytes | Gauge | Dataset used in bytes |
| truenas_pool_dataset_children | Gauge | Number of children inside dataset |
| truenas_pool_dataset_encrypted | Gauge | Dataset encryption enabled? |
| truenas_pool_dataset_locked | Gauge | Dataset encryption locked? |
| truenas_pool_status | Gauge | Pool status: 0=UNKNOWN, 1=ONLINE |
| truenas_pool_healthy | Gauge | Pool health |
| truenas_pool_disk_status | Gauge | Status of disk in pool: 0=UNKNOWN, 1=ONLINE |
| truenas_pool_disk_errors | Counter | Count of errors on disk in pool |
| truenas_replication_state | Gauge | Current replication state: 0=UNKNOWN 1=SUCCESS 2=RUNNING 3=FAILED 4=WAITING |
| truenas_replication_last_finished | Gauge | Replication last finished |
| truenas_replication_last_elapsed | Gauge | Last replication elapsed milliseconds |
| truenas_replication_progress | Gauge | Current replication progress |
| truenas_pool_snapshot_task_status | Gauge | Pool snapshot task status: 0=UNKNOWN, 1=FINISHED, 2=RUNNING, 3=ERROR, 4=PENDING, 5=HOLD |
| truenas_pool_snapshot_task_timestamp | Gauge | Pool snapshot task timestamp |
| truenas_uptime | Counter | TrueNAS uptime |
| truenas_cores | Gauge | TrueNAS CPU core count |
| truenas_memory | Gauge | TrueNAS physical memory |
| truenas | Info | TrueNAS Information: hostname, version, serial, serial_ha, model, product, manufacturer |
| truenas_ha | Gauge | TrueNAS High Availability Controller Status: 0=N/A 1=hostname_1 master 2=hostname_2 master |
| truenas_enclosure_health | Gauge | TrueNAS enclosure device metrics |
| truenas_enclosure_status | Gauge | TrueNAS enclosure device health 0=UNKNOWN, 1=OK, 2=Unknown/Not-installed 3=Critical |
| truenas_smarttest_status | Gauge | TrueNAS SMART test result: 0=UNKNOWN 1=SUCCESS 2=RUNNING 3=FAILED |
| truenas_smarttest_cache_age_seconds | Gauge | Seconds since last check of the smart/tests/results API. |
| truenas_smarttest_lifetime | Counter | truenas_smarttest_lifetime |
| truenas_collectd | Gauge | TrueNAS CollectD Metrics |

## Bugs

### Unknown Enumerations

There's a metric here that is called `truenas_exporter_unknown_enumerations`. I
was unable to find any documented list of the possible enumerated values that
can come back from several of the API calls. I did try to spelunk in the
`middlewared` modules for this, but was unable to come to a complete list.

For that reason, this metric will count the number of times a new number comes
back from the API to indicate some status that isn't recognized. If you run into
these, please submit a PR or at least report the error message (exactly) and
what the status of that job, task, or whatever is.

### Bug in core.jobs call Makes Job Information Disappear

Many API calls will internally use the core.get_jobs API function to get a list
of all jobs that run on the TrueNAS, and they will pull the latest job status
from that. That API endpoint will only return 999 records. This is the same
function that underlies the `/api/v2.0/core/get_jobs` REST endpoint, and it will
respond with all types of jobs, like periodic snapshots, cron jobs, cloudsync
jobs, certificate renewals, AD cache refreshes, update/download checks, etc.

If you have a task/job that runs once a week, it might have last run so long ago
that it is no longer visible in these results. If you have a cron job that runs
every minute, that will be 1,440 entries a day just for that cron job. At some
point, you won't be able to see jobs anymore.

In the UI, I have seen Cloud Sync jobs that suddenly have `NOT RUN SINCE LAST
BOOT` as their Status, and this is why. The job status cannot be found in the
last 999 jobs completed. The `core/get_jobs` API supports offsets and limits,
but no combination will get you past the last 999 tasks. Regardless of that,
none of the internal calls to it are actually taking advantage of that anyway.

### Slow-Down of TrueNAS Device Scraping

The queries that pull data from CollectD can pile up if they hang or never
complete for some reason. On the TrueNAS, you can see a lot fo these
processes running like:

```
% ps ax|grep 'rrdtool xport'
  100  -  I          0:00.23 /usr/local/bin/rrdtool xport --daemon unix:/var/run/rrdcached.sock --json --start 1616227509 --end 1616228409 --step 10 DEF:xxx0=/var/db/collectd/rrd/localhost//aggregation-cpu-average/cpu-idle.rrd:value:AVERAGE XPORT:xxx0:aggregation-cpu-average/cpu-idle DEF:xxx1=/var/db/collectd/rrd/localhost//aggregation-cpu-ave
  333  -  I          0:00.23 /usr/local/bin/rrdtool xport --daemon unix:/var/run/rrdcached.sock --json --start 1616227536 --end 1616228436 --step 10 DEF:xxx0=/var/db/collectd/rrd/localhost//aggregation-cpu-average/cpu-idle.rrd:value:AVERAGE XPORT:xxx0:aggregation-cpu-average/cpu-idle DEF:xxx1=/var/db/collectd/rrd/localhost//aggregation-cpu-ave
  414  -  I          0:00.26 /usr/local/bin/rrdtool xport --daemon unix:/var/run/rrdcached.sock --json --start 1616227556 --end 1616228456 --step 10 DEF:xxx0=/var/db/collectd/rrd/localhost//aggregation-cpu-average/cpu-idle.rrd:value:AVERAGE XPORT:xxx0:aggregation-cpu-average/cpu-idle DEF:xxx1=/var/db/collectd/rrd/localhost//aggregation-cpu-ave
<SNIP>
```

If you see this happen, then you can kill off all the `rrdtool xport` runs
and restore normal performance. You could also put this in a cron job:

```bash
#!/bin/bash

# Get list of processes, listing elapsed_time, pid, and command
# Filter to only the `rrdtool xport` ones
# Use awk to only consider the ones where the command begins with `rrdtool` so we don't consider the `grep` command
# Use awk to only consider the ones that have been running more than 600s (10m)
# Print list of pids, then kill them all
ps ax -o etimes,pid,command | grep 'rrdtool xport' | awk '$3 == "rrdtool" && $1 > 600 { print $2 }' | xargs kill
```

### Overall Performance

It's tough to get all this stuff from the API on-demand. It might be better to
just repeatedly collect the metrics and report the most recent data each time
the `/metrics` endpoint is requested.
