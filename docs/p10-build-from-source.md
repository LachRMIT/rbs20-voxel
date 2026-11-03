# P10: building the RBS20 firmware from NETGEAR's source

P10 is the first build where everything that can be compiled is compiled here, from NETGEAR's GPL release. Only the parts NETGEAR never published source for come from firmware images.

| Part | Where it comes from |
|---|---|
| Linux 3.14.77 kernel, device trees, uClibc, BusyBox, NETGEAR's own programs and scripts | Compiled from NETGEAR's Orbi-Micro 2.7.3.22 GPL source |
| dropbear (SSH), iperf3, nano, haveged, vnstat, htop, mtr, bmon, Lua, LuaSocket, Prometheus node exporter, BusyBox ntpd | Compiled from source (recipes in `gpl/packages/`) |
| Qualcomm Wi-Fi driver, radio firmware and board data, other prebuilt NETGEAR binaries | Stock RBS20 2.7.6.6 (`manifest/stock-closed-files.txt`) |
| Wi-Fi SON mesh: hyd, wsplcd, lbd, hostapd, wpa_supplicant and their libraries | Voxel RBS50 9.2.5.2.39 (`manifest/p10-donor-files.txt`), for interop with Voxel routers |
| Sync monitor, P10 services and fixes | This repo (`overlay/`, `overlay-p10/`) |

## Build

```sh
# 1. Compile NETGEAR's source plus the extra packages (Docker, about 45 minutes)
sh gpl/build-gpl.sh gpl-work

# 2. Assemble the satellite firmware
fakeroot python3 scripts/build_p10.py \
    --gpl gpl-work/src/bin/ipq806x/RBS20-V2.7.3.22.img \
    --stock RBS20-V2.7.6.6.img \
    --donor RBR50_to_RBS50-V9.2.5.2.39SF-HW.img \
    --unsquashfs gpl-work/src/staging_dir/host/bin/unsquashfs4 \
    --mksquashfs gpl-work/src/staging_dir/host/bin/mksquashfs4 \
    --readelf gpl-work/src/staging_dir/toolchain-arm_cortex-a7_gcc-5.2.0_uClibc-1.0.14_eabi/bin/arm-openwrt-linux-readelf \
    -o out/
```

`build_p10.py` refuses to finish if any program in the image is missing a shared library.

## Why the closed parts still fit

- The kernel built from source produces the same 9 device trees as stock 2.7.6.6, byte for byte.
- Its configuration differs from stock in one line (`CONFIG_NF_CONNTRACK_CHECK_TCP_UDP_TIMEOUT_IN_EARLY_DROP`).
- All 2,074 kernel symbols that the 189 stock modules use are exported by the new kernel. The kernel has no `MODVERSIONS` and the modules carry no `vermagic`, so they load as before.
- The libc is the same uClibc-ng 1.0.14 that stock uses.

## What P10 adds on the unit

| Service | Port | Notes |
|---|---|---|
| SSH (dropbear) | 22 | Root password = web admin password. If only the hashed admin password is stored, root stays locked until you first log in to the dashboard. No fallback password. |
| Sync monitor / dashboard | 8080 | HTTP Basic auth with the web admin password. |
| Prometheus node exporter | 9100 | CPU, memory, network, conntrack, plus `orbi_*` metrics: backhaul signal and bit rate, clients per radio, mesh daemons up. |
| vnstat | - | Traffic history per interface (kept in RAM, resets on reboot). |
| Time sync | - | BusyBox ntpd: the router first, then public NTP. |
| Remote syslog | - | `config set rbs20_syslog_host=<ip>; config commit` streams logs over UDP 514. |

Ports 22, 8080 and 9100 are dropped on every interface except the LAN bridge `br0` (`/usr/sbin/rbs20-guard` re-applies the rules every 30 seconds).

Removed because a satellite never uses them (stock RBS20 doesn't ship them either): the router web UI (`/www`, 24 MB), Armor and Circle.

## P11

P11 adds a new dashboard on port 8080. See [p11-dashboard.md](p11-dashboard.md).
