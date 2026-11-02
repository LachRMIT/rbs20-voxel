#!/usr/bin/env python3
"""Build the RBS20 Voxel-graft firmware from user-supplied images.

No firmware is stored in this repository. You provide:
  --stock   NETGEAR RBS20-V2.7.6.6.img                (base: kernel, drivers, scripts)
  --donor   Voxel RBR50_to_RBS50-V9.2.5.2.39SF-HW.img  (mesh stack, web assets)
  --donor   Voxel LBR20-V9.2.5.2.57SF-HW.img           (dropbear, haveged, iperf3, nano)

Steps: unpack both rootfs -> copy the donor files listed in manifest/donor-files.txt
(verified by MD5) -> apply patches/ -> copy overlay/ -> fix rc.d links -> mksquashfs ->
pack three images (real RBS20, RBR20 on router firmware, RBR20 already a satellite).

Run as root or under fakeroot (unsquashfs has to create /dev nodes):
  fakeroot python3 scripts/build.py --stock ... --donor ... --donor ... -o out/
Needs: squashfs-tools (unsquashfs, mksquashfs with xz), patch, python3.
"""
import argparse, hashlib, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_MD5 = 'b0c6bf4a4fe9afd405b5a639ed466f82'   # RBS20-V2.7.6.6.img, 20,709,505 bytes
HD_RBS20 = '29765641+0+128+512+2x2+2x2+2x2'
HD_RBR20 = '29765641+0+256+512+2x2+2x2+2x2'
SQ_OFFSETS = (0x320080, 0x3C0080)                  # RBx20 / RBx50 and LBR20

# (file prefix, header device, header hd_id)
VARIANTS = [
    ('RBS20', 'RBS20', HD_RBS20),                        # a real RBS20
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


def unpack(img, dest, work):
    data = open(img, 'rb').read()
    for off in SQ_OFFSETS:
        if data[off:off + 4] == b'hsqs':
            sq = os.path.join(work, os.path.basename(dest) + '.sqfs')
            open(sq, 'wb').write(data[off:])
            run('unsquashfs', '-q', '-n', '-d', dest, sq)
            return
    sys.exit(f'{img}: no squashfs at a known offset')


def index_donors(roots):
    by_md5 = {}
    for root in roots:
        for d, _, files in os.walk(root):
            for n in files:
                p = os.path.join(d, n)
                if os.path.isfile(p) and not os.path.islink(p):
                    by_md5.setdefault(md5(p), p)
    return by_md5


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stock', required=True)
    ap.add_argument('--donor', action='append', required=True, help='Voxel image (repeat for each)')
    ap.add_argument('--version', default='9.2.7.6.6SF-P8')
    ap.add_argument('--host-key', help='optional dropbear host key to bake in (NOT recommended, see SECURITY.md)')
    ap.add_argument('-o', '--out', default='out')
    ap.add_argument('--skip-stock-check', action='store_true')
    a = ap.parse_args()

    if not a.skip_stock_check and md5(a.stock) != STOCK_MD5:
        sys.exit(f'{a.stock}: MD5 is not stock RBS20 2.7.6.6 ({STOCK_MD5}); use --skip-stock-check to override')

    os.makedirs(a.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix='rbs20-build-')
    root = os.path.join(work, 'root')
    unpack(a.stock, root, work)
    donors = []
    for i, img in enumerate(a.donor):
        d = os.path.join(work, f'donor{i}')
        unpack(img, d, work)
        donors.append(d)
    by_md5 = index_donors(donors)

    # 1. Donor files, verified by MD5
    missing = []
    for line in open(os.path.join(REPO, 'manifest', 'donor-files.txt')):
        if not line.strip() or line.startswith('#'):
            continue
        kind, rel, *rest = line.split()
        dst = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.lexists(dst):
            os.remove(dst)
        if kind == 'L':
            os.symlink(rest[0], dst)
            continue
        want, mode = rest
        src = next((os.path.join(d, rel) for d in donors
                    if os.path.isfile(os.path.join(d, rel)) and md5(os.path.join(d, rel)) == want), None)
        src = src or by_md5.get(want)
        if not src:
            missing.append(rel)
            continue
        shutil.copyfile(src, dst)
        os.chmod(dst, int(mode, 8))
    if missing:
        sys.exit('donor files not found in the given images (wrong Voxel versions?):\n  ' + '\n  '.join(missing))

    # 2. Patches to stock scripts
    for p in sorted(os.listdir(os.path.join(REPO, 'patches'))):
        run('patch', '-p1', '--no-backup-if-mismatch', '-d', root, '-i', os.path.join(REPO, 'patches', p))

    # 3. Our own files
    ov = os.path.join(REPO, 'overlay')
    for d, _, files in os.walk(ov):
        for n in files:
            src = os.path.join(d, n)
            dst = os.path.join(root, os.path.relpath(src, ov))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    if a.host_key:
        os.makedirs(os.path.join(root, 'etc/dropbear'), exist_ok=True)
        shutil.copyfile(a.host_key, os.path.join(root, 'etc/dropbear/dropbear_ed25519_host_key'))
        os.chmod(os.path.join(root, 'etc/dropbear/dropbear_ed25519_host_key'), 0o600)

    # 4. Boot links: dropbear owns port 22, so NETGEAR's sshenable listener is disabled
    rcd = os.path.join(root, 'etc/rc.d')
    for n in ('S98sshenable.init', 'K98sshenable.init'):
        if os.path.lexists(os.path.join(rcd, n)):
            os.remove(os.path.join(rcd, n))
    for link, target in (('S13haveged', 'haveged'), ('S98dropbear', 'dropbear'),
                         ('K30dropbear', 'dropbear'), ('S99syncmon', 'syncmon')):
        p = os.path.join(rcd, link)
        if os.path.lexists(p):
            os.remove(p)
        os.symlink('../init.d/' + target, p)
    open(os.path.join(root, 'firmware_version'), 'w').write(f'V{a.version}\n')

    # 5. Rootfs + images
    sq = os.path.join(work, 'rootfs.sqfs')
    run('mksquashfs', root, sq, '-noappend', '-comp', 'xz', '-b', '262144', '-no-xattrs', '-all-root', '-quiet')
    for prefix, device, hd in VARIANTS:
        out = os.path.join(a.out, f'{prefix}-V{a.version}.img')
        run(sys.executable, os.path.join(REPO, 'tools', 'orbipack.py'), '--base', a.stock, '--squashfs', sq,
            '--device', device, '--hd-id', hd, '--version', a.version, '-o', out)
        print(f'  md5 {md5(out)}')
    shutil.rmtree(work)


if __name__ == '__main__':
    main()
