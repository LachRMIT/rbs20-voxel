#!/usr/bin/env python3
"""Assemble the P10 RBS20 firmware: NETGEAR GPL source build + only the closed Qualcomm parts.

Inputs (none are stored in this repo):
  --gpl     RBS20-V2.7.3.22.img that YOU compiled from NETGEAR's GPL source with gpl/build-gpl.sh
            (kernel, libc, busybox, dropbear, iperf3, vnstat, htop, mtr, bmon, Lua, node exporter...)
  --stock   NETGEAR RBS20-V2.7.6.6.img: Qualcomm Wi-Fi driver + firmware and other closed binaries
            (manifest/stock-closed-files.txt, verified by MD5)
  --donor   Voxel RBR50_to_RBS50-V9.2.5.2.39SF-HW.img: Wi-Fi SON mesh stack (hyd, wsplcd, lbd,
            hostapd, wpa_supplicant + libs; manifest/p10-donor-files.txt, verified by MD5)

Steps: unpack the GPL rootfs -> remove router-only parts (manifest/p10-remove.txt) -> add stock
closed files -> add Voxel mesh files -> apply patches/ -> copy overlay/ then overlay-p10/ ->
boot links -> check every ELF's libraries resolve -> mksquashfs -> pack the image variants.

P11 (new dashboard on :8080): add --overlay overlay-p11 --version 9.2.7.3.22SF-P11.

Run as root or under fakeroot. Needs: unsquashfs, mksquashfs (xz), patch, readelf, python3.
  fakeroot python3 scripts/build_p10.py --gpl RBS20-V2.7.3.22.img --stock RBS20-V2.7.6.6.img \\
      --donor RBR50_to_RBS50-V9.2.5.2.39SF-HW.img -o out/
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))

STOCK_MD5 = 'b0c6bf4a4fe9afd405b5a639ed466f82'   # RBS20-V2.7.6.6.img
HD_RBS20 = '29765641+0+128+512+2x2+2x2+2x2'
HD_RBR20 = '29765641+0+256+512+2x2+2x2+2x2'
SQ_OFFSETS = (0x320080, 0x3C0080)

VARIANTS = [
    ('RBS20', 'RBS20', HD_RBS20),                        # a real RBS20 (the target)
    ('RBR20_to_RBS20', 'RBR20', HD_RBR20),               # RBR20 still on router firmware
    ('RBR20_as_RBS20-satupgrade', 'RBS20', HD_RBR20),    # RBR20 already running a satellite build
]


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def run(*cmd):
    print('+', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def unpack(img, dest, work, tools):
    data = open(img, 'rb').read()
    for off in SQ_OFFSETS:
        if data[off:off + 4] == b'hsqs':
            sq = os.path.join(work, os.path.basename(dest) + '.sqfs')
            open(sq, 'wb').write(data[off:])
            run(tools['unsquashfs'], '-n', '-d', dest, sq)
            return
    sys.exit(f'{img}: no squashfs at a known offset')


def manifest(name):
    for line in open(os.path.join(REPO, 'manifest', name)):
        line = line.strip()
        if line and not line.startswith('#'):
            yield line.split()


def rm(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def copy_manifest(name, root, sources):
    """F <path> <md5> <mode> | L <path> <target> | D <path>; F files are taken from the first source with that MD5."""
    missing = []
    for kind, rel, *rest in manifest(name):
        dst = os.path.join(root, rel)
        if kind == 'D':
            os.makedirs(dst, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.lexists(dst) and not os.path.isdir(dst):
            os.remove(dst)
        if kind == 'L':
            os.symlink(rest[0], dst)
            continue
        want, mode = rest
        src = next((os.path.join(s, rel) for s in sources
                    if os.path.isfile(os.path.join(s, rel)) and md5(os.path.join(s, rel)) == want), None)
        if not src:
            missing.append(rel)
            continue
        shutil.copyfile(src, dst)
        os.chmod(dst, int(mode, 8))
    if missing:
        sys.exit(f'{name}: files not found with the expected MD5 (wrong input image?):\n  ' + '\n  '.join(missing))


def copy_tree(src_root, root):
    for d, _, files in os.walk(src_root):
        for n in files:
            src = os.path.join(d, n)
            dst = os.path.join(root, os.path.relpath(src, src_root))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.lexists(dst):
                os.remove(dst)
            shutil.copy2(src, dst)


def check_libs(root, readelf):
    """Every dynamically linked ELF must find all its NEEDED libraries in /lib, /usr/lib or its RPATH."""
    def listing(rel):
        p = os.path.join(root, rel.lstrip('/'))
        return set(os.listdir(p)) if os.path.isdir(p) else set()
    have = listing('lib') | listing('usr/lib')
    bad = []
    for d, _, files in os.walk(root):
        for n in files:
            p = os.path.join(d, n)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            with open(p, 'rb') as f:
                if f.read(4) != b'\x7fELF':
                    continue
            out = subprocess.run([readelf, '-d', p], capture_output=True, text=True).stdout
            extra = set()
            for line in out.splitlines():
                if '(RPATH)' in line or '(RUNPATH)' in line:
                    for rp in line.split('[')[1].rstrip(']').split(':'):
                        extra |= listing(rp)
            for line in out.splitlines():
                if '(NEEDED)' in line:
                    lib = line.split('[')[1].rstrip(']')
                    if lib not in have and lib not in extra:
                        bad.append(f'{os.path.relpath(p, root)} needs {lib}')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--gpl', required=True, help='RBS20 image built from NETGEAR GPL source (gpl/build-gpl.sh)')
    ap.add_argument('--stock', required=True)
    ap.add_argument('--donor', required=True, help='Voxel RBR50_to_RBS50 .39 image')
    ap.add_argument('--version', default='9.2.7.3.22SF-P10')
    ap.add_argument('--unsquashfs', default='unsquashfs')
    ap.add_argument('--mksquashfs', default='mksquashfs')
    ap.add_argument('--readelf', default='readelf')
    ap.add_argument('-o', '--out', default='out')
    ap.add_argument('--skip-stock-check', action='store_true')
    ap.add_argument('--overlay', action='append', default=[], metavar='DIR',
                    help='extra overlay copied after overlay-p10/ (repeatable), e.g. overlay-p11 for the P11 dashboard')
    ap.add_argument('--keep-root', metavar='DIR', help='also copy the finished root filesystem here (for testing)')
    a = ap.parse_args()
    tools = {'unsquashfs': a.unsquashfs}

    if not a.skip_stock_check and md5(a.stock) != STOCK_MD5:
        sys.exit(f'{a.stock}: MD5 is not stock RBS20 2.7.6.6 ({STOCK_MD5})')

    os.makedirs(a.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix='rbs20-p10-')
    root, stock, donor = (os.path.join(work, n) for n in ('root', 'stock', 'donor'))
    unpack(a.gpl, root, work, tools)
    unpack(a.stock, stock, work, tools)
    unpack(a.donor, donor, work, tools)

    # 1. Router-only parts out
    for (rel,) in manifest('p10-remove.txt'):
        rm(os.path.join(root, rel))

    # 2. Closed parts: Qualcomm Wi-Fi from stock, SON mesh from Voxel
    copy_manifest('stock-closed-files.txt', root, [stock])
    copy_manifest('p10-donor-files.txt', root, [donor])

    # 3. Patches to NETGEAR scripts (satellite role, user manager, repacd, wsplcd)
    for d in ('patches', 'patches-p10'):
        pd = os.path.join(REPO, d)
        if os.path.isdir(pd):
            for p in sorted(os.listdir(pd)):
                run('patch', '-p1', '--no-backup-if-mismatch', '-d', root, '-i', os.path.join(pd, p))

    # 4. Our files: sync monitor (overlay/), then P10 changes on top (overlay-p10/)
    copy_tree(os.path.join(REPO, 'overlay'), root)
    copy_tree(os.path.join(REPO, 'overlay-p10'), root)
    for extra in a.overlay:
        copy_tree(extra if os.path.isabs(extra) else os.path.join(REPO, extra), root)

    # 5. Boot links. dropbear owns port 22, so NETGEAR's sshenable listener stays off.
    rcd = os.path.join(root, 'etc/rc.d')
    for n in ('S98sshenable.init', 'K98sshenable.init', 'S50dropbear', 'K50dropbear'):
        rm(os.path.join(rcd, n))
    for link, target in (('S98dropbear', 'dropbear'), ('K30dropbear', 'dropbear'),
                         ('S99syncmon', 'syncmon'), ('S99rbs20-extras', 'rbs20-extras')):
        p = os.path.join(rcd, link)
        rm(p)
        os.symlink('../init.d/' + target, p)
    open(os.path.join(root, 'firmware_version'), 'w').write(f'V{a.version}\n')

    # 6. Sanity: all shared libraries resolve
    bad = check_libs(root, a.readelf)
    if bad:
        sys.exit('unresolved libraries:\n  ' + '\n  '.join(bad))
    print('library check: OK')
    if a.keep_root:
        run('cp', '-a', root + '/.', a.keep_root)

    # 7. Rootfs + images (kernel partition comes from the GPL-built image)
    import orbipack
    sq = os.path.join(work, 'rootfs.sqfs')
    run(a.mksquashfs, root, sq, '-noappend', '-comp', 'xz', '-b', '262144', '-no-xattrs', '-all-root')
    base = open(a.gpl, 'rb').read()
    sqd = open(sq, 'rb').read()
    for prefix, device, hd in VARIANTS:
        out = os.path.join(a.out, f'{prefix}-V{a.version}.img')
        img = orbipack.pack(base, sqd, device, a.version, hd)
        open(out, 'wb').write(img)
        print(f'{out}  {len(img):,} bytes  md5 {md5(out)}')
    shutil.rmtree(work)


if __name__ == '__main__':
    main()
