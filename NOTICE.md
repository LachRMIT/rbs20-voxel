# Notices and third-party material

## What this repository contains
- **Original work (MIT, see [LICENSE](LICENSE)):** the build script, `tools/orbipack.py`, the sync monitor (`overlay/`), the init scripts in `overlay/etc/init.d/`, the analysis documents in `docs/` and the patch files' added lines.
- **Small excerpts of NETGEAR firmware scripts** appear as context lines in `patches/*.patch`. They are included only so the patches can be applied to a stock image you supply. NETGEAR retains its rights to that material.
- **Kernel configuration files and package lists** in `docs/raw/` were extracted from NETGEAR and Voxel images for comparison. Linux kernel configurations are part of a GPL-2.0 work.

## What this repository does not contain
No firmware image, rootfs, binary, library or web asset from NETGEAR or Voxel is included. In particular:
- **NETGEAR Orbi firmware** (stock RBS20/RBR20) is NETGEAR's proprietary software, apart from the open-source components NETGEAR publishes as GPL source.
- **Voxel's custom firmware** for Orbi is distributed by its author on their own terms. The build uses about 35 files from Voxel's RBS50 and LBR20 images (listed with MD5s in [manifest/donor-files.txt](manifest/donor-files.txt)); you must supply those images yourself.
- The images built from this repository combine both, so they are for personal use on hardware you own. Please don't redistribute them.

## Upstream sources referenced
- NETGEAR GPL source for Orbi-Micro (RBR20/RBS20) V2.5.1.26, used for the P7 kernel experiment: published by NETGEAR, mirrored in the Internet Archive's `netgear-gpl-source` collection.
- OpenWrt Chaos Calmer 15.05.1 / Qualcomm QSDK, which the stock firmware is built on (GPL-2.0 and others).
- Dropbear SSH (MIT-style licence), haveged (GPL-3.0), iperf3 (BSD), GNU nano (GPL-3.0), ncurses (MIT-style): these binaries come from the Voxel images you supply. Their source code is available from their upstream projects.

NETGEAR and Orbi are trademarks of NETGEAR, Inc. This project is not affiliated with or endorsed by NETGEAR or by Voxel.
