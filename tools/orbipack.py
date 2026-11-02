#!/usr/bin/env python3
"""Pack a NETGEAR Orbi (RBx20) firmware image.

Layout (decoded from stock RBS20 2.7.6.6 / RBR20_to_RBS20 2.7.4.24):
  [128B text header][kernel part: FIT, zero pad, 64B uImage hdr at end][rootfs region][1B checksum]
  rootfs region = squashfs + padjffs2-style 0xff padding with 0xdeadc0de markers.
  uImage hdr covers the whole rootfs region (size + CRC32).
  checksum = 0xff - (sum of all preceding bytes & 0xff).
"""
import argparse, struct, zlib

HDR_LEN = 0x80
UIMG_LEN = 64
MARK = b'\xde\xad\xc0\xde'


def pad_rootfs(sq):
    out = bytearray(sq)
    # marker boundaries as seen in stock 2.7.6.6: 4K, 8K, 64K, then a final zero-filled 128K block
    for blk in (0x1000, 0x2000, 0x10000):
        tgt = -(-len(out) // blk) * blk
        out += b'\xff' * (tgt - len(out))
        out += MARK
    tgt = -(-len(out) // 0x20000) * 0x20000
    out += b'\xff' * (tgt - len(out))
    out += MARK + b'\x00' * (0x20000 - 4)
    return bytes(out)


def uimage_hdr(template, rootfs):
    h = bytearray(template)
    struct.pack_into('>I', h, 4, 0)
    struct.pack_into('>I', h, 12, len(rootfs))
    struct.pack_into('>I', h, 24, zlib.crc32(rootfs) & 0xffffffff)
    struct.pack_into('>I', h, 4, zlib.crc32(bytes(h)) & 0xffffffff)
    return bytes(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='stock image supplying the kernel partition')
    ap.add_argument('--kernel-size', type=lambda x: int(x, 0), default=0x320000)
    ap.add_argument('--squashfs', required=True)
    ap.add_argument('--device', required=True)
    ap.add_argument('--version', required=True)
    ap.add_argument('--hd-id', help='defaults to the base image hd_id')
    ap.add_argument('--raw-rootfs', action='store_true', help='squashfs file already includes padding')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()

    base = open(a.base, 'rb').read()
    fields = dict(l.split(':', 1) for l in base[:HDR_LEN].rstrip(b'\0').decode().splitlines())
    hd_id = a.hd_id or fields['hd_id']
    hdr = f"device:{a.device}\nversion:{a.version}\nregion:{fields.get('region', '')}\nhd_id:{hd_id}\n".encode()
    assert len(hdr) <= HDR_LEN
    hdr += b'\0' * (HDR_LEN - len(hdr))

    kpart = base[HDR_LEN:HDR_LEN + a.kernel_size]
    assert kpart[-UIMG_LEN:-UIMG_LEN + 4] == b'\x27\x05\x19\x56', 'no uImage header at end of kernel part'

    sq = open(a.squashfs, 'rb').read()
    assert sq[:4] == b'hsqs'
    rootfs = sq if a.raw_rootfs else pad_rootfs(sq[:struct.unpack('<Q', sq[40:48])[0]])

    img = hdr + kpart[:-UIMG_LEN] + uimage_hdr(kpart[-UIMG_LEN:], rootfs) + rootfs
    img += bytes([(0xff - sum(img)) & 0xff])
    open(a.out, 'wb').write(img)
    print(f'{a.out}: {len(img)} bytes, rootfs {len(rootfs):#x}, squashfs {len(sq):#x}')


if __name__ == '__main__':
    main()
