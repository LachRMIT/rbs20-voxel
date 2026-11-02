# Full firmware diff: stock vs RBR→RBS conversion vs Voxel

Compared (user-supplied images; none are included in this repo):

| Short name | File | What it is |
|---|---|---|
| **stock** | RBS20-V2.7.6.6.img | NETGEAR stock RBS20 satellite, built 2025-10-28 |
| **conv20** | RBR20_to_RBS20-V2.7.4.24.img | stock RBS20 2.7.4.24, converted to flash on an RBR20 |
| **vox50** | RBR50_to_RBS50-V9.2.5.2.39SF-HW.img | Voxel RBS50 satellite, converted to flash on an RBR50 |
| **vox-lbr** | LBR20-V9.2.5.2.57SF-HW.img | Voxel LBR20 router |

**Limits.** NETGEAR's download server was not reachable from the analysis environment. **Stock RBR20 2.7.6.6** was added later **stock RBR20 2.7.6.6** (section 5); stock RBS50 2.5.2.x, stock RBS20 2.7.4.24 and stock LBR20 2.5.2.20 are still missing. Where a finding depends on that, it is inferred from the other images, and I say so. Raw data is in [raw/](raw/).

---

## 1. Container format (the same in all four)

```
[0x00  128 B ] text header: device / version / region / hd_id, zero padded
[0x80        ] FIT image: kernel@1 (gzip) + 9 IPQ40xx DTBs, zero padded to the kernel-partition size
[kpart-64    ] 64 B legacy uImage header "ARM OpenWrt Linux-3.14.77" (type 2, comp 3): size + CRC32 of the whole rootfs region
[kpart       ] squashfs 4.0 xz, 256 KiB blocks
[            ] padjffs2-style 0xFF padding with 0xDEADC0DE markers, then a 128 KiB block of zeros
[last byte   ] checksum = 0xFF - (sum of all preceding bytes & 0xFF)
```

| | stock | conv20 | vox50 | vox-lbr |
|---|---|---|---|---|
| header `device` | RBS20 | **RBR20** | **RBR50** | LBR20 |
| header `version` | 2.7.6.6 | 2.7.4.24 | 9.2.5.2.39SF-HW | 9.2.5.2.57SF-HW |
| header `hd_id` | 29765641+0+128+512+2x2+2x2+2x2 | **same as RBS20** | 29765352+0+4000+512+2x2+2x2+4x4 | 29766182+0+256+512+2x2+2x2+2x2+1 |
| kernel partition size | 0x320000 | 0x320000 | 0x3C0000 | 0x3C0000 |
| FIT timestamp | 2025-10-28 | 2022-03-07 | 2025-04-10 | 2026-10-15 |
| uImage hdr time | 2025-10-28 | 2022-03-07 (original kept) | 2025-04-10 (original kept) | 2026-10-15 |
| squashfs mkfs time | 2025-10-28 | **2024-10-10** | **2025-05-01** | 2026-10-15 |
| squashfs compressor-options flag | yes (0x6C0) | **no (0xC0)** | **no (0xC0)** | yes (0x6C0) |
| padding right after squashfs | 0xFF | **0x00 to 4 KiB, then 0xFF** | **0x00 to 4 KiB, then 0xFF** | 0xFF |
| inodes | 3304 | 3321 | 3774 | 4540 |
| flash | NAND | NAND | eMMC | NAND |

`tools/orbipack.py` rebuilds stock and conv20 byte-for-byte from their own rootfs, which confirms this layout.

---

## 2. What a conversion (RBRxx → RBSxx) changes

Both conversion images were made the same way, at the file level. There are four changes:

1. **Header:** `device:` is set to the router name (RBR20 or RBR50) so the router's bootloader and web UI accept the image. `hd_id` stays the satellite's. RBR/RBS pairs share a board ID; OpenWrt lists the RBR20 as `…+256+…`, but conv20 keeps the RBS20 `…+128+…` and is still accepted.
2. **One line in `lib/dni_platform/project/dni_project.sh`** forces the model name:
   - conv20 changes `project_boot_stage0` (line 593): the ART read `/sbin/artmtd -r board_model_id | cut -f 2 -d ":" > /tmp/board_model_id` becomes `echo "RBS20" | cut -f 2 -d ":" > /tmp/board_model_id`.
   - vox50 changes `dni_board_data_init` (line 62) to `echo "RBS50" > /tmp/board_model_id`.
   - `/tmp/board_model_id` drives everything. `dni_board_data_detect` writes `/tmp/orbi_type` = Base when the third character is R and Satellite when it is S. Every init script and lighttpd (`/www` vs `/www.satellite`) branch on `orbi_type`.
   - In each image this is the **only file with a different mtime** (2024-10-10 and 2025-05-01). Every other file keeps the original build date.
3. **The rootfs is repacked** with standard mksquashfs. The new squashfs has no compressor options and is zero-padded to 4 KiB, then the 0xFF/DEADC0DE trailer follows. The uImage size and CRC are recomputed, but its timestamp is left alone.
4. **The kernel is untouched.** The conv20 kernel is NETGEAR's own build (`kun.hk.huang@CNXMDNICP07`, GCC 5.2.0, 2022-03-07).

**Still read from the real ART (factory data) after conversion:** `80_mount_root` (it picks `ntgrdata.cfg` for a real RBR20 and `ntgrdata-rbs20.cfg` otherwise, which keeps the UBI layout matched to the physical flash), `hyd` (unused), `bdf-sanitycheck.sh` and `wifison-sanity-check.sh`.

**conv20 vs stock 2.7.6.6, everything else:** 502 files changed, 26 added and 15 removed. That is ordinary 2.7.4.24 → 2.7.6.6 version churn: only 3 package versions differ, and the kernel config and all 9 DTBs are byte-identical. *(Inferred: I couldn't diff against true stock 2.7.4.24.)*

---

## 3. What Voxel changes

### 3a. It's a full rebuild, not a patch
- **No binary in either Voxel image matches stock RBS20 byte-for-byte.** The images share 0 of their ~700 ELF files with stock; conv20, by contrast, shares 533. 478 ELFs are identical between vox50 and vox-lbr.
- The kernel was rebuilt by Voxel: `voxel@dell` / `voxel@intel`, **GCC 9.5.0** (stock uses GCC 5.2.0), still **Linux 3.14.77**, both rebuilt with the same toolchain. ELF `.comment` sections are stripped, so compiler provenance can't be read per file.
- The QCA WiFi driver (`umac.ko` etc.) still contains **NETGEAR build paths**. vox50 has `/home/release/orbi-maintrunk-buildroot-20191028…` and vox-lbr has `/home/figo.yan/project/orbi/lbr20-release/…`, with the same driver source `qca-wifi_dni-10.4-g0.1.453.110` as stock. These are NETGEAR prebuilt WiFi blobs taken from each product's GPL tree. **For RBS20, the WiFi driver must come from RBS20/RBK20 stock.**
- Voxel's base is the **older NETGEAR 2.5.2.x tree**, while stock RBS20 2.7.6.6 is newer in a few NETGEAR packages: busybox 1.31.1 vs 1.24.1, ppp 2.4.9 vs 2.4.7, and newer QCA SON userland. The mesh binaries (hyd, wsplcd, hostapd, wpa_supplicant) are identical across both Voxel builds and different from stock.

### 3b. Kernel config: changes found in both Voxel kernels (vs stock RBS20)
Full lists: [raw/kconfig_voxel_added_both.txt](raw/kconfig_voxel_added_both.txt) and [raw/kconfig_voxel_removed_both.txt](raw/kconfig_voxel_removed_both.txt).
- **Added:** `WIREGUARD=m`, a TCP congestion set with **default Westwood** (stock uses Cubic) plus HTCP/HSTCP/Illinois/Vegas/YeAH, `IP(6)_NF_MATCH_RPFILTER`, `NETFILTER_XT_TARGET_TEE`, CIFS/SMB2 + FSCACHE, NTFS/XFS/EXT4 as modules, JFFS2 (LZMA), `NF_CONNTRACK_CHECK_TCP_UDP_TIMEOUT_IN_EARLY_DROP`, `AIO`, `CRYPTO_CMAC/MD4/ECB`, and USB storage/serial/QMI (those are product-dependent, since RBx20 has no USB).
- **Removed:** `CC_OPTIMIZE_FOR_SIZE` (so built with -O2), IPsec (`INET_AH/ESP/IPCOMP`, XFRM), GRE/IPIP/VTI tunnels, built-in PPTP, `NF_NAT_IPV6` + IPv6 MASQUERADE/NPT, `CRYPTO_XTS`, `DEBUG_USER`.
- stock 2.7.4.24 and stock 2.7.6.6 kernel configs are identical.

### 3c. Device trees
- stock and conv20 DTBs are byte-identical.
- vox-lbr's DTBs differ from RBS20's in the **Ethernet switch map**: `phy_mdio_addr` 0→3, the LAN/WAN VLAN tags, `switch_lan_bmp` 0x1E→0x2E and `switch_wan_bmp` 0x20→0x10.
- **Correction (after the stock RBR20 was added):** that switch map is the **RBR20 router's** map. Stock RBR20 2.7.6.6 has the same values; the RBS20 has no WAN port. The LBR20 DTB is the RBR20 DTB minus the SD-card pinmux, plus modem GPIOs (gpio28-31).
- **Don't use the LBR20 kernel/DTB on an RBS20.** Keep the RBS20 DTBs for satellite builds; the conversion image does this on RBR20 hardware too.

### 3d. Packages (opkg status)
Full lists are in [raw/pk_*.txt](raw/). stock has 354 packages, vox50 386 and vox-lbr 377.
- **Added in both Voxel builds:** dropbear, wireguard-tools + kmod-wireguard, openvpn-openssl (client), dnscrypt-proxy-2, stubby/getdns/unbound, haveged, iperf3, nano, less, procps-ng (ps/top), bind-dig, ethtool/ip-tiny, iptables-mod-rpfilter/tee, OpenSSL 1.0.2 compatibility libraries, redis, samba36, proftpd, avahi, cifsmount, bluetopia (RBR50 Bluetooth) and ca-certificates.
- **Upgraded:** OpenSSL 1.0.2n → 3.0.16, curl 7.74 → 8.13, iptables 1.4.21 → 1.8.7, lighttpd 1.4.55 → 1.4.79, zlib 1.2.8 → 1.3.1, dbus 1.9 → 1.14, ncurses 5.9 → 6.4, e2fsprogs, tcpdump, util-linux, jansson, expat, ipset and more (~70 total).
- **Removed vs stock RBS20 2.7.6.6:** openssh-server-pam + sshenable (replaced by dropbear), aws-iot-device-sdk, ntgrcrypt, user-manager, lvm2/cryptsetup, the IPsec/GRE/tunnel kmods, libpam, sqlite3, csh and `ra` (router analytics). *(Some may simply be absent from the 2.5.2.x base; this is inferred.)*

### 3e. Boot services
- **Enabled in both Voxel builds:** dropbear, haveged, dnscrypt-proxy-2, stubby, openvpn-client, wg-client, https_cert_update, avahi, samba, dbus, bluetopia.
- **Enabled in stock but not Voxel:** sshenable, ASH, CSH, RA (analytics), ntgrcrypt, lvm2, check_nmrp, create_cronjob, adt_init and `user`. Voxel calls `update_user` from `net-lan` instead of running `user`.

### 3f. Voxel's hooks in NETGEAR scripts
- `armor_init` uses `noarmor`, `circle_init` uses `nocircle`, `aws` uses `noaws`, and `XAgent` uses `nocloud`.
- `/mnt/circle/overlay` is a persistent overlay on the Circle partition.
- `init6` and `dropbear` run `net-wall` (Voxel's firewall, with `netwall.conf` and `firewall-start.sh` hooks).
- `wg-client` only runs when the module is RBR50 or LBR20, so it never runs on a satellite.
- `update_user` sets the root password to the web GUI password. Stock 2.7.6.6 does the same through `user-manager.sh` (`change_password_of_system_user root`), which is why SSH as root works in P2/P3.
- dropbear 2026.94 ships with **fixed host keys** in `/etc/dropbear`, the same for every user of that build.

---

## 4. What this means for the RBS20/RBR20 build
- **Conversion recipe (proven):** the header `device:` change plus the one-line `board_model_id` override. P2/P3 have both.
- **Graft approach (P1→P3):** stock RBS20 kernel, DTBs and WiFi blobs, plus Voxel userland that only needs the stock uClibc 1.0.14 libraries. P3's audit adds 22 files plus 5 terminfo entries and removes 2 rc links (`sshenable.init`). Only 2 files are changed: `firmware_version` and `dni_project.sh`. Every added binary resolves all its symbols against libraries in the image.
- **A "real" Voxel build** needs the NETGEAR RBK20 GPL source tree, rebuilt with GCC 9.5 and Voxel's package set and script hooks from sections 3b-3f. Keep the RBx20 DTBs and the RBS20 WiFi blobs.
- **Mesh interop:** Voxel units run the 2.5.2.x SON userland, and stock RBS20 runs a newer 2.7.x build. Whether swapping to Voxel's SON binaries helps is a test for a later prototype.

---

## 5. Stock RBR20 2.7.6.6 vs stock RBS20 2.7.6.6 (router vs satellite, same release)

| | RBR20 | RBS20 |
|---|---|---|
| header `device` / `hd_id` | RBR20 / 29765641+0+**256**+512+… | RBS20 / 29765641+0+**128**+512+… |
| kernel | **byte-identical** (same build, md5 627f5474…) | |
| DTBs | router switch map (WAN = port mask 0x10) + SD-card pinmux | no WAN (0x20), no SD |
| rootfs | +1053 files in `/www` (router UI), +27 router-only files: ASH, CSH, DALH, UPAgent, XAgent, bst, d2, dil, remGenie, ookla, circled, Armor and Circle data | `/www.satellite` (177 files) |
| scripts | **identical** | |
| `/hw_id` | …+256… | …+128… |

The two firmwares share every script. **The role is decided only at runtime:** the third letter of `/tmp/board_model_id` (read from ART) sets Base or Satellite. That's why the one-line conversion works.

### Dual firmware slots (explains the "still a router" result)
- Every image here, stock and Voxel, ships `/usr/sbin/fw_upg.sh`. Its logic:
  - It reads `boot_part` (1 or 2) from ART.
  - It writes the new image to the **other** partition (`firmware` or `firmware2`) through `firmware_update -p <module_name> -i <hw_id>`.
  - Then it runs `artmtd -w boot_part <new>`.
- `net-cgi` checks an uploaded header against ART `board_hw_id` ("Not match hw id") and checks the checksum. On secure-boot boards it also verifies a signed kernel; the RBx20 isn't secure-boot.
- **An NMRP flash from the bootloader doesn't run `fw_upg.sh`, so `boot_part` isn't changed.** If it writes a slot that `boot_part` doesn't point to, the old firmware keeps booting. Our images have no `/www`, so a working router setup wizard means the running firmware isn't ours. *(Inferred from the scripts; not yet confirmed on the device.)*
- **What to do:** flash via the running router's web UI with a header matching the unit's board ID. That's P4 (`hd_id …+256…`, the stock RBR20's own).
