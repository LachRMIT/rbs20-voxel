# Voxel builds vs stock RBS20: what's reusable

Read-only analysis of the stock and Voxel images listed below. None of the images are included in this repo.

## The images

| Image | Header `device` | Firmware | Board ID (`hd_id`) | Flash | Role | Built |
|---|---|---|---|---|---|---|
| RBS20-V2.7.6.6 (stock) | RBS20 | V2.7.6.6 | 29765641+0+128+512+2x2+2x2+2x2 | NAND 128 MB | satellite | 2025-10-28 |
| RBR20_to_RBS20-V2.7.4.24 | **RBR20** | V2.7.4.24 stock | 29765641 (same board) | NAND | satellite | 2022-03-07 |
| RBR50_to_RBS50-V9.2.5.2.39SF-HW | **RBR50** | Voxel .39 | 29765352+0+4000+512+2x2+2x2+4x4 | eMMC 4 GB | satellite | 2025-04-10 |
| LBR20-V9.2.5.2.57SF-HW | LBR20 | Voxel .57 | 29766182+0+256+512+2x2+2x2+2x2+1 | NAND 256 MB | router | 2026-10-15 |

The target mesh is an **RBR50v2 router on Voxel** and an **RBS50v2 satellite on Voxel**, plus an RBS20. The LBR20 Voxel image is reference material only.

## Image format (the same for all four)
- A 128-byte text header (`device:`, `version:`, `region:`, `hd_id:`), padded with zeros.
- A FIT image at 0x80 holding the kernel ("ARM OpenWrt Linux-3.14.77") and 9 IPQ40xx DTBs. The same DTB set appears in every image.
- The FIT is padded to a fixed size: the squashfs starts at **0x320080** on RBS20/RBR20 and at **0x3C0080** on RBS50/LBR20.
- The rootfs is squashfs xz with a 256 KiB block size: OpenWrt Chaos Calmer 15.05.1 (QSDK), uClibc 1.0.14.
- The **last byte is a checksum**: `0xFF - (sum of all preceding bytes & 0xFF)`. This holds for all four images.

## The "conversion" trick
- RBR20 and RBS20 have the **same board ID** (29765641), and so do RBR50 and RBS50 (29765352). The router/satellite role is fixed at build time: satellite images ship only `www.satellite`.
- `RBR20_to_RBS20-V2.7.4.24` is the stock RBS20 2.7.4.24 rootfs under an `device:RBR20` header. Its file list matches stock RBS20 apart from normal version churn.
- `RBR50_to_RBS50` is the Voxel RBS50 satellite build with the same header swap.
- **So the secondary goal comes almost for free.** Once a Voxel RBS20 image exists, the RBR20 version is the same image with `device:RBR20` in the header and a recomputed checksum.

## What's shared or different

| Component | Stock RBS20 2.7.6.6 | Voxel RBS50 .39 | Voxel LBR20 .57 |
|---|---|---|---|
| Kernel | 3.14.77 | 3.14.77 | 3.14.77 |
| uClibc | 1.0.14 | 1.0.14 | 1.0.14 |
| QCA WiFi driver source | qca-wifi_dni-10.4-g0.1.453.110 | same | same |
| Build tree | orbi-maintrunk-buildroot | orbi-maintrunk-buildroot | lbr20 mt-build |
| hyd / wsplcd / hostapd / wpa_supplicant | its own build | **identical to LBR20** | **identical to RBS50** |
| BusyBox | 1.31.1 | 1.24.1 | 1.24.1 |
| OpenSSL | 1.0.0 | 1.0.0 + 3 | 1.0.0 + 3 |
| Flash | NAND | eMMC | NAND |

- Both Voxel builds run byte-identical mesh/SON binaries (hyd, wsplcd, hostapd, wpa_supplicant). Stock RBS20 runs different ones. For interop with the two Voxel units, the RBS20 build should carry Voxel's set.
- Kernel modules have no vermagic or modversions, so the kernel won't refuse a foreign module. That also means it can't flag a mismatch, so `wireguard.ko` and other modules taken from another image must be tested on the device.

## Reusable Voxel additions (found in both Voxel builds, absent from stock RBS20)
- **Satellite-relevant:** dropbear (SSH, dbclient, scp), `wireguard.ko` + `wg` + `wg-client`, `openvpn-client`, dnscrypt-proxy-2, stubby, haveged, `https_cert_update`, procps-ng top/ps, nano, bash, iperf3, dig, OpenSSL 3, the `/mnt/circle/overlay` persistent overlay, plus nf/xt extras (`xt_TEE`, `ipt_rpfilter`, `ip6t_rpfilter`), l2tp, cifs/ext4/vfat/xfs/ntfs modules and `shortcut-fe-cm.ko`.
- **Router-only, skip on the satellite:** samba/proftpd, avahi, bluetopia, the LTE modem bits (`dnimobile`, `sms-tool`), `net-wall`, and the ReadyCLOUD/XAgent cloud agents.

## Most promising path
1. **Get a console and a backup first.** The stock inittab runs a shell on `ttyMSM0`. Dump every NAND partition before anything else, then confirm the bootloader's TFTP/NMRP recovery works.
2. **Make a first prototype by grafting a rootfs.** Keep the stock RBS20 2.7.6.6 kernel (FIT), its kernel modules and its WiFi firmware, since those match the board. Add Voxel's userland on top: the SON binaries above, dropbear, WireGuard tools, dnscrypt/stubby and the overlay scripts. LBR20 .57 is the best donor because it is the same Orbi-Micro NAND family and the newest build; RBS50 .39 is the reference for which services a satellite runs.
3. **Repack** with the RBS20 layout: xz squashfs with 256K blocks at 0x320080, the `device:RBS20` header and the checksum byte. Load it through TFTP recovery or the web UI with the serial console attached.
4. **For the RBR20-as-satellite,** reuse the same image with the `device:RBR20` header.
5. **Longer term,** rebuild the kernel from Netgear's RBK20 GPL source so modules like `wireguard.ko` are built for this exact kernel.
