# TrueNAS Exporter

There are a couple of goals to this project:

1. The TrueNAS isn't completely monitored now. We are monitoring SNMP and
  CollectD statistics, but those are lacking in visibility to things like disk
  health, ZFS health, and any tasks' status.
2. The CollectD statistics are necessary for whatever we have now,
  but they are hacky. They lose their CollectD exporter configuration on every
  reboot, failover, or update, and it needs to be setup again as per the
  [docs](https://docs.iracing.at/operations/networking/truenas/).
3. The API can be designed to be a publicly useful thing we can publish on
  GitHub or BitBucket for more community usefulness.


## Features to Implement

* Monitor ZFS replication status
* Monitor ZFS health only visible via CollectD right now
* Monitor disk health statistics, SMART maybe?
* Monitor tasks like cloud sync tasks.
* Look for other things useful from CollectD and start using API for those too
  
* Available via CollectD
    * Disk IO/Queue/latency
    * CPU Load/utilization/temperature
    * memory utilization, swap
    * ZFS ARC Hash Collisions, ARC eviction, L2ARC Throughput
* Available over SNMP (optional if --include-available-by-snmp)
    * Dataset Utilization available over SNMP
    * Network Interface traffic
    * Zpool Utilization
    * ZFS ARC/L2ARC size, ARC/L2ARC Cache hit ratio, ARC/L2ARC requests