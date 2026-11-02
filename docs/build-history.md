# Build history (P1 to P8)

The prototype log, oldest first, as written while the work was happening. The images themselves are not in this repo (they contain NETGEAR and Voxel binaries); the MD5s are listed so anyone who builds their own can compare. Builds from `scripts/build.py` will not match these MD5s exactly, because squashfs timestamps differ and the shared SSH host key is no longer included.

## Prototype 1: 9.2.7.6.6SF-P1 (superseded: booted as a router on the RBR20)

| File | Header device | Flash on | MD5 |
|---|---|---|---|
| RBR20_to_RBS20-V9.2.7.6.6SF-P1.img | RBR20 | an RBR20 you want to run as a satellite | c40b380a32945262114292739b36fa8b |
| RBS20-V9.2.7.6.6SF-P1.img | RBS20 | a real RBS20 (later) | b2ab5523f0cc8ad9d127c674a74a4104 |

Both images contain the same firmware. Only the header differs.

### What's in it
- The base is stock NETGEAR RBS20 **2.7.6.6**: its kernel, drivers, WiFi firmware and mesh stack are untouched. The kernel partition is byte-identical to stock.
- Voxel SSH is added: dropbear 2026.94 from Voxel LBR20 9.2.5.2.57SF-HW. It runs on port 22 and generates host keys on first connection (`-R`). Voxel's builds share fixed keys; this one doesn't. According to Voxel's notes, the login is root with your web GUI password.
- NETGEAR's locked `sshenable` service is turned off so dropbear gets port 22.
- Also added from the Voxel build: haveged (entropy), iperf3 (for backhaul speed tests) and nano.
- The web UI shows firmware version `V9.2.7.6.6SF-P1`, which tells you it booted.
- Every added binary links only against libraries that are byte-identical in stock 2.7.6.6.
- **Not included yet:** Voxel's older mesh binaries (hyd, wsplcd, hostapd, wpa_supplicant). They're planned for P2, once P1 boots.

### Flashing the RBR20
1. Keep the RBR20 out of your live network. Connect a PC to its LAN port by cable.
2. If the RBR20 is already running the RBR20_to_RBS20 2.7.4.24 satellite firmware, open its web UI and upload `RBR20_to_RBS20-V9.2.7.6.6SF-P1.img` under Firmware Update.
3. If possible, watch the serial console (`ttyMSM0`, 115200 8N1, 3.3 V, Vcc not connected) while it boots.
4. After it boots, check the firmware version in the web UI, then try `ssh root@<satellite IP>`.
5. **Recovery:** the kernel is stock, so the bootloader's TFTP recovery is unaffected. You can re-flash `RBR20_to_RBS20-V2.7.4.24.img` or stock firmware from there.

### How it was built (reproducible)
1. Extract the stock 2.7.6.6 squashfs, which starts at 0x320080.
2. Add the files listed above and the `rc.d` links S98dropbear, K30dropbear and S13haveged. Remove the `sshenable.init` links.
3. Rebuild the rootfs with `mksquashfs root out.sqfs -noappend -comp xz -b 262144 -no-xattrs -all-root`.
4. Pack it with `python3 tools/orbipack.py --base RBS20-V2.7.6.6.img --squashfs out.sqfs --device RBR20 --version 9.2.7.6.6SF-P1 -o out.img`.

orbipack was checked against two stock images: it rebuilds stock RBS20 2.7.6.6 and RBR20_to_RBS20 2.7.4.24 byte-for-byte from their own rootfs.

## Prototype 2: 9.2.7.6.6SF-P2 (superseded by P4)

| File | Header device | MD5 |
|---|---|---|
| RBR20_to_RBS20-V9.2.7.6.6SF-P2.img | RBR20 | cbf2eddcfe1495c293de22f2a6d91cb2 |
| RBS20-V9.2.7.6.6SF-P2.img | RBS20 | c49372ad38db9219e05d993b8e2c0706 |

**What changed from P1:** P1 came up as a router on the RBR20.
- The cause is in `lib/dni_platform/project/dni_project.sh` (`project_boot_stage0`). The firmware reads the model name from the factory (ART) partition and writes it to `/tmp/board_model_id`. `dni_board_data_detect` then sets `/tmp/orbi_type` to Base if the third letter of that name is R, or Satellite if it is S. Every service and the web UI follow `orbi_type`.
- P2 applies the same one-line change the RBR20_to_RBS20 2.7.4.24 conversion makes: `echo "RBS20" > /tmp/board_model_id` in place of the ART read. That function is now byte-identical to the conversion's.
- `80_mount_root` still reads the real ART model, so the ntgrdata UBI layout stays right for the RBR20 flash, exactly as in the conversion image.
- After flashing, factory-reset the unit (hold reset for about 10 s). The router setup it ran under P1 left settings behind.

## Prototype 4: 9.2.7.6.6SF-P4 (booted as a satellite on the RBR20; superseded by P5)

| File | Header | MD5 |
|---|---|---|
| RBR20_to_RBS20-V9.2.7.6.6SF-P4.img | device:RBR20, hd_id **29765641+0+256+512+2x2+2x2+2x2** (the stock RBR20's own) | a30d56eb3dc5d525525b1cae50b82cc8 |
| RBS20-V9.2.7.6.6SF-P4.img | device:RBS20, hd_id …+128… | 8e7d175e94a559cfce91e09bf441dd35 |

- **Contents** are the same as P3: P2's satellite fix, plus haveged and nano with their libraries (P1 and P2 were missing `libhavege` and `libncursesw`).
- **The RBR20 header now carries the RBR20's real board ID.** Stock RBR20 2.7.6.6 uses `+256`. The NETGEAR web upgrader rejects a header whose `hd_id` doesn't match the board ID stored in the unit's factory data ("Not match hw id").
- **Why P1/P2 kept booting as a router: Orbi has two firmware slots** (`firmware` and `firmware2`). The factory-data flag `boot_part` picks which one boots. The web UI upgrade (`fw_upg.sh`) writes the *inactive* slot and then flips `boot_part`. An NMRP/TFTP flash from the bootloader can land in a slot that isn't the one `boot_part` points to, so the old stock RBR20 router firmware keeps booting. *(Inferred from the firmware scripts; not yet confirmed on the device.)*

### Flashing P4 on the RBR20
1. Boot the RBR20 into its current router firmware (192.168.1.1).
2. Go through or skip the setup wizard until you reach **Settings → Administration → Firmware Update**.
3. Upload `RBR20_to_RBS20-V9.2.7.6.6SF-P4.img`. This writes the other slot and switches `boot_part` to it.
4. After it reboots, factory reset (hold reset for about 10 s).
5. It should come up as a satellite showing `V9.2.7.6.6SF-P4`.
6. If the web UI rejects the file, note the exact error message.

## Prototype 5: 9.2.7.6.6SF-P5 (superseded by P6: SSH login never worked)

| File | Header | MD5 |
|---|---|---|
| RBR20_to_RBS20-V9.2.7.6.6SF-P5.img | device:RBR20, hd_id 29765641+0+256+512+2x2+2x2+2x2 | 033bb7cb3d60d9d2dd7c0fe9d1ebd88f |
| RBS20-V9.2.7.6.6SF-P5.img | device:RBS20, hd_id …+128… | c2d70c0767c61d5046412a9378c4e001 |
| RBR20_as_RBS20-satupgrade-V9.2.7.6.6SF-P5.img | device:**RBS20**, hd_id **+256** (for an RBR20 already running P4 or later as a satellite) | 37c0948f421bbb8476864768feffcfb7 |

Which file: an RBR20 still on router firmware takes `RBR20_to_RBS20-…`. An RBR20 already running our satellite firmware takes `RBR20_as_RBS20-satupgrade-…`, because its upgrade page checks the header `device:` against the model it reports (now RBS20) as well as `hd_id` against the board's real ID (+256). A real RBS20 takes `RBS20-…`.

P4 plus:
- **SSH login uses the admin password.** Stock 2.7.6.6 sets root's password to the uppercase SHA256 hex of the admin password (`user-manager.sh update_users` prefers `http_passwd_hashed`), which is why SSH said "Permission denied". P5 prefers the plaintext `http_passwd`, and `/etc/init.d/dropbear` also sets root's password from it at boot. If plaintext isn't stored, the old behaviour remains and the SSH password is the SHA256 hex (for `password` that is `5E884898DA28047151D0E56F8DC6292773603D0D6AABBDD62A11EF721D1542D8`).
- **Voxel's RBK50 mesh stack** for interop with the Voxel RBR50v2/RBS50v2. From Voxel RBS50: `hyd`, `wsplcd`, `lbd`, `hostapd`, `wpa_supplicant`, `hostapd_cli`, `wpa_cli`, `hyctl`, `ucpkgen`, and their SON libraries (`libhyfi-bridge`, `libhyficommon`, `libieee1905`, `liblbcmnlibs`, `libmcfwdtbl*`, `libpluginManager`, `libpsService`, `libstorage`, `libwpa2`). Voxel LBR20 ships the same files byte-for-byte.
  - Checked: every binary resolves all symbols against the P5 tree; the WiFi driver is the same qca-wifi 10.4-g0.1.453.110 in stock RBS20 and Voxel RBS50; the stock RBS20 init scripts that write the daemons' config differ from Voxel's only in shell style.
  - Kept stock: libssl/libcrypto/libnl/libubox/libuci/libjansson (shared with other stock programs), the RBS20 wifi scripts, repacd, the kernel and the WiFi drivers.
- Flash it exactly like P4 (web UI firmware update). The unit then boots the other slot, so if P5 misbehaves, a web-UI upgrade back to P4 (or stock) restores it.

What P5 is not: a from-source Voxel build. That needs NETGEAR's RBK20 GPL source rebuilt with Voxel's toolchain and patches, which aren't available here.

## Prototype 6: 9.2.7.6.6SF-P6 (SSH confirmed working; userspace-only, known good)

| File | Use when | MD5 |
|---|---|---|
| RBR20_as_RBS20-satupgrade-V9.2.7.6.6SF-P6.img | RBR20 already running P4/P5 (upgrade from the satellite page) | 6591f8d5624915d6247dd854701adc56 |
| RBR20_to_RBS20-V9.2.7.6.6SF-P6.img | RBR20 still on router firmware | 8785272cbcd92ea7d6dc3415d47f1c73 |
| RBS20-V9.2.7.6.6SF-P6.img | a real RBS20 | a7f00a9ebb90db07ae4b6d47dc495552 |

P5 plus an SSH fix:
- **Why no password worked on P4/P5:** stock stores root's password as a SHA crypt hash (`passwd -a sha`, `$5$`). Dropbear checks passwords with the C library's `crypt()`, and this uClibc `libcrypt` only does MD5 and DES (no SHA-256 constants in it). So every login failed. Voxel's own `update_user` uses plain `passwd` (MD5), which is why SSH works on Voxel.
- P6 uses MD5 (`-a md5`) in `user-manager.sh`, and `/etc/init.d/dropbear` sets root's password at boot to the stored web admin password, or to `password` if no plain password is stored.
- A fixed ed25519 host key was baked in so the "REMOTE HOST IDENTIFICATION HAS CHANGED" warning only appeared once. That turned out to be a security mistake (every unit shares one private key), so this repo does **not** ship the key and `scripts/build.py` leaves it out. See [SECURITY.md](../SECURITY.md).

## Prototype 7: 9.2.7.6.6SF-P7 (first build with a kernel compiled from source)

| File | Use when | MD5 |
|---|---|---|
| RBR20_as_RBS20-satupgrade-V9.2.7.6.6SF-P7.img | RBR20 already running P4-P6 (satellite page) | b3ddd78b3fc3c09c177d0b29b6c85030 |
| RBR20_to_RBS20-V9.2.7.6.6SF-P7.img | RBR20 still on router firmware | 842016315f77b7a4d7db80b433d52325 |
| RBS20-V9.2.7.6.6SF-P7.img | a real RBS20 | be702c6556fa12ab3f0e4cb62ef6e67f |

P6 rootfs (unchanged apart from the version) plus a **Linux 3.14.77 kernel built from NETGEAR's RBR20/RBS20 GPL source** (Orbi-Micro 2.5.1.26, from the Internet Archive `netgear-gpl-source` collection):
- Config = stock RBS20 2.7.6.6's kernel config, except: optimised for speed (`CC_OPTIMIZE_FOR_SIZE` off, as Voxel does) and Westwood TCP built in (default stays cubic; switch with `sysctl net.ipv4.tcp_congestion_control=westwood`).
- Built in an Ubuntu 14.04 chroot with NETGEAR's own GCC 5.2 / uClibc-ng 1.0.14 toolchain.
- Checks: all 9 device trees the source builds are byte-identical to stock 2.7.6.6's; every undefined symbol in all 189 stock kernel modules (incl. NETGEAR's prebuilt WiFi drivers) resolves against the new kernel; the modules carry no vermagic and the kernel has no MODVERSIONS, so they load as before.
- FIT image: the faster kernel is bigger (3.09 MB gz vs 2.91 MB), so the FIT keeps only the RBx20 device tree (`dk04.1-micro_cc`, the stock default `config@1`) and points all 9 configs at it. Fits the 0x320000 kernel partition.
- **Risk:** first build that changes the kernel. If it doesn't boot, recover with nmrpflash (boot_part is 1, which NMRP writes) using P6.

## Prototype 8: 9.2.7.6.6SF-P8 (live sync monitor + Voxel look)

| File | Use when | MD5 |
|---|---|---|
| RBR20_as_RBS20-satupgrade-V9.2.7.6.6SF-P8.img | RBR20 already running P4-P7 (satellite page) | f74af2b3d6039258635f6820991e2246 |
| RBR20_to_RBS20-V9.2.7.6.6SF-P8.img | RBR20 still on router firmware | 0995369e6c4b132863353ed4c1f24f7f |
| RBS20-V9.2.7.6.6SF-P8.img | a real RBS20 | 4e6207da22bd5306a7b7c8734bdbf670 |

P6 (stock kernel, known good) plus:
- **Live sync monitor** at `http://<satellite IP>:8080/` (login `admin` + web admin password; `password` if none set). Refreshes every 2 s. It shows:
  - a sync-progress tracker (Waiting > Pairing > Connected > Settings synced > In mesh);
  - repacd's state in plain English;
  - the 5 GHz/2.4 GHz backhaul links (router BSSID, signal, rate);
  - a signal chart;
  - which mesh programs are running;
  - a timestamped event timeline;
  - tabs for the repacd, wsplcd, Wi-Fi/hyd logs, the hyd topology and the satellites linked to this unit.
- How it works:
  - `/usr/sbin/syncmon-watch` (started by `/etc/init.d/syncmon`) writes `/tmp/syncmon/state.json`.
  - A second lighttpd (`/etc/lighttpd/lighttpd_syncmon.conf`, IPv4 port 8080) serves `/www.syncmon`.
  - repacd now writes its state to `/tmp/syncmon_repacd_state`.
  - wsplcd logs at INFO to `/tmp/wsplcd.log`, capped at 1 MB.
  - Passwords and keys are masked in the logs shown.
- **Voxel look:** Voxel's banner logo, cube favicon and spinner on the satellite web UI (assets copied from Voxel's RBS50 build).
- Tested in an emulator running the real ARM busybox and lighttpd (with only the secure-storage library stubbed). The login, JSON and page render were checked there. On the real unit it is untested.
- **Update (2026-10-21):** tested on hardware. P8 on an RBR20 running as an RBS20 joined a Voxel RBR50v2 mesh on both backhaul bands; see the Results section of the main README.
