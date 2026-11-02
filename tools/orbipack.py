#!/usr/bin/env python3
"""Pack a NETGEAR Orbi (RBx20) firmware image.

Layout (decoded from stock RBS20 2.7.6.6 / RBR20_to_RBS20 2.7.4.24):
  [128B text header][kernel part: FIT, zero pad, 64B uImage hdr at end][rootfs region][1B checksum]
  rootfs region = squashfs + padjffs2-style 0xff padding with 0xdeadc0de markers.
  uImage hdr covers the whole rootfs region (size + CRC32).
  checksum = 0xff - (sum of all preceding bytes & 0xff).
"""
import argparse
import struct
import zlib

HDR_LEN = 0x80
UIMG_LEN = 64
UIMG_MAGIC = b'\x27\x05\x19\x56'
SQ_MAGIC = b'hsqs'
MARK = b'\xde\xad\xc0\xde'
DEFAULT_KERNEL_SIZE = 0x320000


def parse_header(img):
    """Return the text header of an Orbi image as a dict (device, version, region, hd_id)."""
    text = img[:HDR_LEN].rstrip(b'\0').decode()
    return dict(line.split(':', 1) for line in text.splitlines() if ':' in line)


def make_header(device, version, region, hd_id):
    hdr = f"device:{device}\nversion:{version}\nregion:{region}\nhd_id:{hd_id}\n".encode()
    if len(hdr) > HDR_LEN:
        raise ValueError(f'header is {len(hdr)} bytes, max {HDR_LEN}')
    return hdr + b'\0' * (HDR_LEN - len(hdr))


def pad_rootfs(sq):
    """Pad a squashfs the way stock firmware does: 4K, 8K, 64K markers, then a zero-filled 128K block."""
    out = bytearray(sq)
    for blk in (0x1000, 0x2000, 0x10000):
        tgt = -(-len(out) // blk) * blk
        out += b'\xff' * (tgt - len(out))
        out += MARK
    tgt = -(-len(out) // 0x20000) * 0x20000
    out += b'\xff' * (tgt - len(out))
    out += MARK + b'\x00' * (0x20000 - 4)
    return bytes(out)


def uimage_hdr(template, rootfs):
    """Rewrite a legacy uImage header so its data size and CRC cover `rootfs`."""
    h = bytearray(template)
    struct.pack_into('>I', h, 4, 0)
    struct.pack_into('>I', h, 12, len(rootfs))
    struct.pack_into('>I', h, 24, zlib.crc32(rootfs) & 0xffffffff)
    struct.pack_into('>I', h, 4, zlib.crc32(bytes(h)) & 0xffffffff)
    return bytes(h)


def checksum_byte(data):
    return (0xff - sum(data)) & 0xff


def verify(img):
    """True when the image's trailing checksum byte is valid."""
    return sum(img) & 0xff == 0xff


def pack(base, sq, device, version, hd_id=None, kernel_size=DEFAULT_KERNEL_SIZE, raw_rootfs=False):
    """Build an image from a base image's kernel partition and a squashfs rootfs."""
    fields = parse_header(base)
    hdr = make_header(device, version, fields.get('region', ''), hd_id or fields['hd_id'])

    kpart = base[HDR_LEN:HDR_LEN + kernel_size]
    if kpart[-UIMG_LEN:-UIMG_LEN + 4] != UIMG_MAGIC:
        raise ValueError('no uImage header at end of kernel part')
    if sq[:4] != SQ_MAGIC:
        raise ValueError('rootfs is not a squashfs')
    rootfs = sq if raw_rootfs else pad_rootfs(sq[:struct.unpack('<Q', sq[40:48])[0]])

    img = hdr + kpart[:-UIMG_LEN] + uimage_hdr(kpart[-UIMG_LEN:], rootfs) + rootfs
    return img + bytes([checksum_byte(img)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', required=True, help='stock image supplying the kernel partition')
    ap.add_argument('--kernel-size', type=lambda x: int(x, 0), default=DEFAULT_KERNEL_SIZE)
    ap.add_argument('--squashfs', required=True)
    ap.add_argument('--device', required=True)
    ap.add_argument('--version', required=True)
    ap.add_argument('--hd-id', help='defaults to the base image hd_id')
    ap.add_argument('--raw-rootfs', action='store_true', help='squashfs file already includes padding')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()

    with open(a.base, 'rb') as f:
        base = f.read()
    with open(a.squashfs, 'rb') as f:
        sq = f.read()
    img = pack(base, sq, a.device, a.version, a.hd_id, a.kernel_size, a.raw_rootfs)
    with open(a.out, 'wb') as f:
        f.write(img)
    print(f'{a.out}: {len(img)} bytes, squashfs {len(sq):#x}')


if __name__ == '__main__':
    main()
