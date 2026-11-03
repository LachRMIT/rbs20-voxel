# P11: the RBS20 dashboard

P11 is P10 plus a new web dashboard on `http://<satellite IP>:8080/`. NETGEAR's own satellite page stays on port 80. Log in as `admin` with the web admin password.

The files are in `overlay-p11/`. To build P11, run the P10 build with `--overlay overlay-p11 --version 9.2.7.3.22SF-P11` (see [p10-build-from-source.md](p10-build-from-source.md)).

## What it shows

| Section | Source | Refresh |
|---|---|---|
| Mesh status and the five sync steps, with the time each was reached | `syncmon-watch` (repacd state, backhaul `wpa_cli` state, event log) | 2 s |
| Path to the router: router, uplink satellite if there is one, this unit, and satellites behind it | Default gateway and its MAC compared with the backhaul BSSID; signal and rate from `iwconfig` | 2 s / 10 s |
| Backhaul cards, devices per band, CPU, memory and temperature | `iwconfig`, `wlanconfig list sta`, `/proc`, `/proc/simple_config/sensor_temp` | 10 s |
| Traffic for the last 24 hours, per hour | `vnstat --dumpdb` on the backhaul interfaces. All client traffic to the router crosses them. | 10 s |
| Services | `pidof` and pidfiles | 10 s |
| Recent events and logs (repacd, wsplcd, Wi-Fi, hyd topology) | `syncmon-watch` | 2 s |

`/www.syncmon/api.cgi` serves the fast state. `/www.syncmon/sys.cgi` runs `/usr/share/syncmon/sys.lua` for the rest. Both return JSON and need the login.

The page works out whether the uplink is the router or another satellite by comparing the last three bytes of the backhaul BSSID with the gateway's MAC. Orbi radio MACs sit within a few steps of the unit's base MAC. The hop between the router and an uplink satellite can't be measured from this unit, so the page doesn't show numbers for it.

## Tools

`POST /action.cgi?do=<name>` with the header `X-RBS20: 1` starts `/usr/sbin/rbs20-action <name>` in the background. The page reads the result from `/tmp/syncmon/action`. Only one tool runs at a time.

| Tool | What it runs |
|---|---|
| Speed test to router | `iperf3 -c <gateway> -t 5`, once in each direction. The router needs an iperf3 server running (`iperf3 -s -D` over SSH on Voxel). |
| Re-run mesh sync | `/etc/init.d/repacd restart` |
| Restart Wi-Fi | `wlan updateconf; wlan down; wlan up` (the same steps NETGEAR's `wifison-monitor.sh` uses) |
| Reboot satellite | `reboot` |

The custom header matters because the browser re-sends the saved Basic-auth login automatically. Another website can't add that header without a CORS preflight, and this server never answers one, so a malicious page can't reboot the unit through your browser.

## Tested so far

These were run under ARM emulation (qemu-user chroot of the built root filesystem, with stubs for the radio tools):

- `sys.lua` returns valid JSON.
- Wrong passwords get 401.
- `action.cgi` refuses GET requests, POSTs without the header and unknown actions.
- The speed test reports a result with an iperf3 server running and a clear message without one.
- A second tool started while one is running gets 409.
- The page renders without errors at 1280 px and on a phone, with no sideways scrolling.

NETGEAR's lighttpd can't start under emulation because it needs the unit's secure storage, so the CGIs were served by a small test server that runs them inside the chroot.

It has not been tested on a real unit yet.

## Fixed along the way

BusyBox 1.24, the version in the GPL build, only accepts `timeout -t SECS`. `syncmon-watch` called `timeout 2 wpa_cli`, which fails there. On P10 that makes every backhaul show as `NO_SUPPLICANT` on the monitor page. Both scripts now detect which form works.
