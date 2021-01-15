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
