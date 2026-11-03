#!/bin/sh
# Build NETGEAR's RBR20/RBS20 firmware (Orbi-Micro 2.7.3.22) from its GPL source, plus the
# extra packages this project adds. Output: <work>/src/bin/ipq806x/RBS20-V2.7.3.22.img, which
# scripts/build_p10.py then turns into the P10 satellite firmware.
#
# Needs: docker, curl, unzip, ~15 GB free disk, about 45 minutes on 4 cores.
# Usage: sh gpl/build-gpl.sh [work-dir]      (default: ./gpl-work)
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${1:-gpl-work}
SRC_ZIP_URL=https://archive.org/download/netgearfirmwaresgpl/orbi-micro-V2.7.3.22_gpl_src.tar.bz2.zip
SRC_ZIP_MD5=8683882caf9933201c5f0cbaa8338a95
MIRROR=https://sources.openwrt.org

mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)
cd "$WORK"

# 1. NETGEAR GPL source (archive.org mirror of NETGEAR's release)
if [ ! -d src ]; then
	[ -f src.zip ] || curl -fL -o src.zip "$SRC_ZIP_URL"
	echo "$SRC_ZIP_MD5  src.zip" | md5sum -c -
	unzip -o src.zip
	tar -xjf orbi-micro-V2.7.3.22_gpl_src.tar.bz2
	mv orbi-micro-V2.7.3.22_gpl_src src
	rm -f orbi-micro-V2.7.3.22_gpl_src.tar.bz2
fi

# 2. Our package recipes and config
mkdir -p src/package/rbs20-extra
cp -r "$HERE"/packages/* src/package/rbs20-extra/
cp src/config/defconfig-orbi-micro src/.config
grep -v '^#' "$HERE"/config-additions.txt | grep . >> src/.config
grep 'is not set' "$HERE"/config-additions.txt >> src/.config

# 3. Prefetch the extra packages' source tarballs (their original hosts are mostly gone)
for f in bmon-3.5.tar.gz confuse-2.7.tar.gz dropbear-2017.75.tar.bz2 haveged-1.9.1.tar.gz \
         htop-1.0.3.tar.gz iperf-3.0.11.tar.gz mtr-0.86.tar.gz nano-2.5.3.tar.gz \
         vnstat-1.12.tar.gz luasocket-3.0-rc1-20130909.tar.bz2; do
	[ -f src/dl/$f ] || curl -fL -o src/dl/$f "$MIRROR/$f"
done

# 4. Build in Ubuntu 16.04, the host NETGEAR used (see gpl/Dockerfile for the fixes it needs)
docker build -t orbi-build "$HERE"
chown -R 1000:1000 src
docker run --rm -u builder -v "$WORK/src":/src -w /src orbi-build sh -c '
	make defconfig >/dev/null
	# -j4 hits a race in base-files once; the -j1 pass finishes it
	make -j4 V=s > build.log 2>&1 || make -j1 V=s >> build.log 2>&1'

ls -la "$WORK"/src/bin/ipq806x/RBS20-V2.7.3.22.img
