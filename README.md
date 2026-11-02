# RBS20 Voxel: custom firmware for the NETGEAR Orbi RBS20 satellite

Custom firmware for the NETGEAR Orbi **RBS20** satellite (and an **RBR20 router converted into an RBS20**), so it can join a mesh of Orbi units running Voxel's custom firmware. Voxel has no RBS20 build. This project reverse-engineers the Orbi image format and grafts Voxel's mesh stack and tools onto NETGEAR's last RBS20 release. It also adds a live web dashboard for watching a satellite sync.

**Result:** on 2026-10-21 a P8 build running on an RBR20-converted-to-RBS20 synced into a Voxel RBR50v2 mesh on both backhaul bands (5 GHz at -52 dBm and 867 Mb/s, 2.4 GHz at -36 dBm).

![Sync monitor](docs/images/sync-monitor.png)
*The sync monitor (port 8080), shown here in the ARM emulator used to test it before it went on hardware.*

> **No firmware images are in this repo.** They contain NETGEAR and Voxel binaries that I can't redistribute. `scripts/build.py` builds the images from copies you supply. See [NOTICE.md](NOTICE.md) and [SECURITY.md](SECURITY.md).

## Why
My home mesh is an RBR50v2 router and an RBS50v2 satellite, both on Voxel, plus an RBS20 on stock firmware. The RBS20 runs a newer, different build of Qualcomm's mesh (SON) software than the Voxel units, and it has no SSH or diagnostic tools. I wanted the RBS20 on the same mesh stack as the rest of the network, with SSH and iperf3 for testing. I also wanted the same image to work on a spare RBR20 router running as a satellite.

## What I worked out
All of this came from taking images apart. The details are in [docs/](docs/).

- **Image format** ([docs/full-firmware-diff.md](docs/full-firmware-diff.md)). A 128-byte text header (`device`, `version`, `hd_id`), a FIT kernel with 9 IPQ40xx device trees padded to 0x320000, then a 64-byte uImage header whose size and CRC32 cover the rootfs region. Next comes an xz squashfs (256 KiB blocks) with `0xDEADC0DE` padding markers, and a final byte that makes the byte sum 0xFF. [`tools/orbipack.py`](tools/orbipack.py) rebuilds two stock images **byte-for-byte** from their own rootfs, which shows the layout is right.
- **Router vs satellite.** RBR20 and RBS20 share a board and a kernel. The role is decided at boot by the third letter of the model name read from factory data (`RBR20` vs `RBS20`). Forcing `echo "RBS20"` in `dni_project.sh` turns an RBR20 into a satellite. NETGEAR's own conversion image does the same thing.
- **Why early builds booted the old firmware.** Orbi has A/B firmware slots. A bootloader (NMRP) flash doesn't flip the `boot_part` flag, so it can write the slot that isn't booted. The web UI upgrader writes the inactive slot and flips the flag, but it also checks that the header's `device` and `hd_id` match the unit. That's why there are three image variants (see below).
- **What Voxel actually is** ([docs/voxel-vs-stock.md](docs/voxel-vs-stock.md)). A full rebuild with GCC 9.5 on NETGEAR's older 2.5.2.x tree; it shares zero ELF files with stock. Its Wi-Fi drivers are NETGEAR's prebuilt blobs, built for each product. The mesh binaries (`hyd`, `wsplcd`, `hostapd`, `wpa_supplicant`, `lbd` and the SON libraries) are byte-identical across Voxel's RBS50 and LBR20 builds. They also link cleanly against the RBS20's stock uClibc 1.0.14, which is what makes a graft possible.
- **Why SSH logins failed** (P4, P5). Stock stores root's password as SHA-256 crypt (`$5$`), but this uClibc `libcrypt` only supports MD5 and DES, so dropbear could never verify it. Switching `user-manager.sh` to MD5 crypt fixed it.

## How the build works
The approach is a **rootfs graft**, not a from-source rebuild. Keep NETGEAR's RBS20 2.7.6.6 kernel, device trees, Wi-Fi drivers and scripts, which match the hardware, and replace or add userland from Voxel.

```
stock RBS20 2.7.6.6 .img ─┐
Voxel RBS50 .img ─────────┼─ unsquashfs ─┬─ copy 35 donor files (MD5-checked, manifest/donor-files.txt)
Voxel LBR20 .img ─────────┘              ├─ apply patches/ (4 small edits to NETGEAR scripts)
                                         ├─ copy overlay/ (sync monitor, init scripts)
                                         ├─ rc.d links: dropbear and haveged on, sshenable off
                                         └─ mksquashfs ─ orbipack.py ─┬─ RBS20-V…img                    (real RBS20)
                                                                      ├─ RBR20_to_RBS20-V…img           (RBR20 on router firmware)
                                                                      └─ RBR20_as_RBS20-satupgrade-V…img (RBR20 already a satellite)
```

| From Voxel | Why |
|---|---|
| `hyd`, `wsplcd`, `lbd`, `hostapd`, `wpa_supplicant`, `hyctl`, `ucpkgen`, SON libraries | Same mesh stack as the Voxel RBR50/RBS50 for interop |
| dropbear, haveged, iperf3, nano (+ libhavege, ncurses, terminfo) | SSH, entropy, backhaul speed tests, editing |
| banner logo, favicon, spinner | Voxel look on the satellite web UI |

| Patch | Change |
|---|---|
| `01-dni_project-sh` | Force model `RBS20` so an RBR20 boots as a satellite |
| `02-user-manager-sh` | MD5 crypt for system passwords; prefer the plaintext admin password |
| `03-repacd-run-sh` | Publish repacd's state to `/tmp/syncmon_repacd_state` for the monitor |
| `04-wsplcd` | wsplcd logs at INFO to a file, so config sync can be watched |

### Building
```sh
# Debian/Ubuntu: sudo apt install squashfs-tools patch fakeroot python3
fakeroot python3 scripts/build.py \
  --stock  inputs/RBS20-V2.7.6.6.img \
  --donor  inputs/RBR50_to_RBS50-V9.2.5.2.39SF-HW.img \
  --donor  inputs/LBR20-V9.2.5.2.57SF-HW.img \
  -o out/
```
The script checks the stock image's MD5 (`b0c6bf4a4fe9afd405b5a639ed466f82`) and every donor file's MD5. I checked it by rebuilding P8 from the stock image: the resulting rootfs matches the P8 that ran on hardware file for file, except for the SSH host key, which is now left out on purpose.

### Flashing
Use the unit's own web UI (**Firmware Update**), and pick the variant that matches the unit:
- a real RBS20 takes `RBS20-…`;
- an RBR20 still on router firmware takes `RBR20_to_RBS20-…`;
- an RBR20 already running one of these satellite builds takes `RBR20_as_RBS20-satupgrade-…`.

Then factory-reset the unit (hold reset for about 10 s) and sync it to the router. The upgrade writes the inactive slot, so a web upgrade back to stock undoes it. The serial console is `ttyMSM0`, 115200 8N1, 3.3 V.

**Use at your own risk.** Flashing custom firmware can brick a unit and voids the warranty.

## Live sync monitor
Watching a satellite sync normally means guessing from LED colours. P8 adds a dashboard at `http://<satellite IP>:8080/` (log in as `admin` with the web admin password). It refreshes every 2 s and shows:
- a progress tracker (Waiting, Pairing, Connected, Settings synced, In mesh) and repacd's state explained in plain English;
- both backhaul links (router BSSID, signal, PHY rate, frequency) and a signal chart;
- which mesh daemons are running, and a timestamped event timeline;
- tabs for the repacd, wsplcd and Wi-Fi logs (passwords and keys masked), the `hyd` 1905 topology, and the satellites linked to this unit.

It is plain BusyBox shell with no new binaries. [`syncmon-watch`](overlay/usr/sbin/syncmon-watch) polls `wpa_cli`, `iwconfig`, `wlanconfig`, `logread` and hyd's debug port into `/tmp/syncmon/state.json`. A second instance of the stock lighttpd serves an auth-gated CGI and a single-file HTML page ([`index.html`](overlay/usr/share/syncmon/index.html)). Before it went on hardware I tested it in a qemu-user ARM chroot running the image's own BusyBox and lighttpd, with only NETGEAR's secure-storage library stubbed out.

## Results
| Build | What it was for | Outcome on hardware |
|---|---|---|
| P1 | Stock + dropbear, haveged, iperf3, nano | Booted the old router firmware (A/B slot issue) |
| P2/P3 | + RBS20 role fix, missing libraries | Same slot issue (NMRP) |
| P4 | RBR20 header with the board's real `hd_id`, flashed via the web UI | **Booted as a satellite** |
| P5 | + Voxel mesh stack, SSH using the admin password | SSH still refused (crypt issue) |
| P6 | MD5 crypt fix | **SSH works** |
| P7 | Kernel 3.14.77 compiled from NETGEAR's GPL source (-O2, Westwood TCP), 9 device trees byte-identical to stock | Built, not yet tested on hardware |
| P8 | P6 + sync monitor + Voxel look | **Synced into the Voxel RBR50v2 mesh** |

The full log is in [docs/build-history.md](docs/build-history.md). In the P8 sync, the first WPS pairing timed out, repacd retried by itself, and the second attempt worked. wsplcd then reported "1905.1 AP Auto Configuration Done", and both backhauls came up: 5 GHz on channel 157 and 2.4 GHz.

## Known limitations
- **NETGEAR's "Config Sync" doesn't complete.** The 1905 mesh config sync succeeds, but the RBR50's own SOAP-based sync status for this unit stays at "not done" (`/tmp/soapclient/allconfig_result` = 1), so the router's UI keeps showing "Config Sync". P8 ships the stock RBS20 SOAP handler. Swapping in Voxel's version is the next experiment.
- **No band steering:** `lbd` stays stopped on the satellite.
- **Tested only on an RBR20 converted to an RBS20.** A real RBS20 takes the same rootfs, but that variant hasn't been flashed yet. The P7 kernel hasn't been tested either.
- **Not a from-source Voxel build.** That would need NETGEAR's RBK20 GPL tree rebuilt with Voxel's toolchain and patches, which aren't public.
- **Open security issues** in the SSH and monitor setup: see [SECURITY.md](SECURITY.md).

## Other write-ups
- [docs/security-audit.md](docs/security-audit.md): a static audit of the stock firmware and of my own builds.
- [docs/daisy-chain-sync.md](docs/daisy-chain-sync.md): how a satellite can onboard another satellite when the router is out of range, traced through the firmware scripts.
- [docs/raw/](docs/raw/): kernel configs, package lists and file diffs used in the analysis.

## Repository layout
```
scripts/build.py          build images from user-supplied stock + Voxel images
tools/orbipack.py         Orbi RBx20 image packer (header, uImage CRC, padding, checksum)
manifest/donor-files.txt  files taken from Voxel, with MD5s
patches/                  edits to NETGEAR scripts
overlay/                  files added to the rootfs (sync monitor, init scripts)
docs/                     analysis, audit, build history
```

## Licence
My code and docs are MIT ([LICENSE](LICENSE)). NETGEAR and Voxel material is not included; see [NOTICE.md](NOTICE.md). This project is not affiliated with NETGEAR or Voxel.

## Generative AI declaration
I used generative AI (Anthropic's Claude) as an assistant on this project: to help analyse the firmware images, write the build and monitor scripts, and draft the documentation. I set the goals, did all the flashing and testing on my own hardware, and reviewed everything published here.
