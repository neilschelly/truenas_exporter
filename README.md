# TrueNAS Exporter

The TrueNAS devices can be monitored by SNMP and CollectD. The CollectD stuff is
only really visible in the UI in RRD graphs, unless you install the [collectd
exporter](https://github.com/prometheus/collectd_exporter) onto the devices.
That works, but is unreliable, because many things like system upgrades, HA
failovers, etc will "fix" the installation and remove it.

## Usage

### CLI

```shell
$ ./truenas_exporter.py --help
usage: truenas_exporter.py [-h] [--port PORT] --target TARGET [--skip-snmp]

Return Prometheus metrics from querying the TrueNAS API

optional arguments:
  -h, --help       show this help message and exit
  --port PORT      Listening HTTP port for Prometheus exporter
  --target TARGET  Target IP/Name of TrueNAS Device
  --skip-snmp      Skip metrics available via SNMP - may save about a second
                   in scrape time
  --cache-smart    Number of hours to cache SMART test results. These shouldn't
                   change often, and they are heavy to request. Default: 24
```
At a minimum, you must give it a target TrueNAS device on the command line. It
will read the environment variables `TRUENAS_USER` and `TRUENAS_PASS` for
authenticating to the API. For TrueNAS devices, the `TRUENAS_USER` must be
`root`.  The `--port` option can be specified to any port you'd like to listen
on for scrape requests.

The `--skip-snmp` option should shave about a second or two off the scrape time
by skipping metrics that can also be easily retrieved via SNMP.

### Docker Container

* `make build` will create a container.
* `TARGET=truenas.example.net make run` will run it, targeting a TrueNAS device
  called truenas.example.net.

## Bugs

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
