"""Tests for tools/orbipack.py using synthetic images (no NETGEAR or Voxel data needed)."""
import os
import struct
import sys
import zlib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import orbipack as op  # noqa: E402

KSIZE = 0x1000  # small kernel partition for tests


def fake_base(device='RBS20', hd_id='29765641+0+128+512+2x2+2x2+2x2'):
    kpart = bytearray(b'\xd0\x0d\xfe\xed' + bytes(KSIZE - 4))     # FIT magic, then zeros
    kpart[-op.UIMG_LEN:-op.UIMG_LEN + 4] = op.UIMG_MAGIC
    body = op.make_header(device, '2.7.6.6', '', hd_id) + bytes(kpart) + b'rootfs'
    return body + bytes([op.checksum_byte(body)])


def fake_squashfs(size=5000):
    sq = bytearray(b'hsqs' + bytes(size - 4))
    struct.pack_into('<Q', sq, 40, size)                            # bytes_used
    for i in range(48, size):
        sq[i] = i * 7 & 0xff
    return bytes(sq)


def pack(**kw):
    return op.pack(fake_base(), fake_squashfs(), kernel_size=KSIZE, **kw)


def test_header_roundtrip():
    img = pack(device='RBR20', version='9.2.7.6.6SF-P8', hd_id='29765641+0+256+512+2x2+2x2+2x2')
    assert op.parse_header(img) == {
        'device': 'RBR20', 'version': '9.2.7.6.6SF-P8', 'region': '',
        'hd_id': '29765641+0+256+512+2x2+2x2+2x2'}


def test_hd_id_defaults_to_base():
    assert op.parse_header(pack(device='RBS20', version='x'))['hd_id'] == '29765641+0+128+512+2x2+2x2+2x2'


def test_checksum_byte_makes_sum_ff():
    img = pack(device='RBS20', version='x')
    assert op.verify(img)
    assert not op.verify(img[:-1] + bytes([(img[-1] + 1) & 0xff]))


def test_uimage_header_covers_rootfs():
    img = pack(device='RBS20', version='x')
    hdr = img[op.HDR_LEN + KSIZE - op.UIMG_LEN:op.HDR_LEN + KSIZE]
    rootfs = img[op.HDR_LEN + KSIZE:-1]
    assert hdr[:4] == op.UIMG_MAGIC
    size, dcrc = struct.unpack('>I', hdr[12:16])[0], struct.unpack('>I', hdr[24:28])[0]
    assert size == len(rootfs)
    assert dcrc == zlib.crc32(rootfs) & 0xffffffff
    blank = bytearray(hdr)
    struct.pack_into('>I', blank, 4, 0)
    assert struct.unpack('>I', hdr[4:8])[0] == zlib.crc32(bytes(blank)) & 0xffffffff


def test_kernel_partition_is_copied_unchanged():
    base, img = fake_base(), pack(device='RBS20', version='x')
    start, end = op.HDR_LEN, op.HDR_LEN + KSIZE - op.UIMG_LEN
    assert img[start:end] == base[start:end]


def test_rootfs_padding_layout():
    sq = fake_squashfs(5000)
    out = op.pad_rootfs(sq)
    assert out.startswith(sq)
    assert len(out) == 0x40000                               # ends on a 128K boundary
    # 0xff fill up to each 4K / 8K / 64K / 128K boundary, then a 0xdeadc0de marker
    for at in (0x2000, 0x4000, 0x10000, 0x20000):
        assert out[at:at + 4] == op.MARK
    assert set(out[len(sq):0x2000]) == {0xff}
    assert out[0x20004:] == bytes(0x20000 - 4)               # final block is zero-filled


def test_squashfs_trailing_garbage_is_trimmed():
    sq = fake_squashfs(5000)
    assert pack(device='RBS20', version='x') == op.pack(fake_base(), sq + b'junk' * 100,
                                                        'RBS20', 'x', kernel_size=KSIZE)


def test_raw_rootfs_repack_is_byte_identical():
    """Unpacking an image and repacking it with --raw-rootfs gives the same bytes (how stock was verified)."""
    img = pack(device='RBS20', version='2.7.6.6')
    rootfs = img[op.HDR_LEN + KSIZE:-1]
    again = op.pack(img, rootfs, 'RBS20', '2.7.6.6', kernel_size=KSIZE, raw_rootfs=True)
    assert again == img


def test_rejects_non_squashfs():
    with pytest.raises(ValueError, match='squashfs'):
        op.pack(fake_base(), b'not a squashfs' * 10, 'RBS20', 'x', kernel_size=KSIZE)


def test_rejects_base_without_uimage_header():
    base = bytearray(fake_base())
    base[op.HDR_LEN + KSIZE - op.UIMG_LEN] = 0
    with pytest.raises(ValueError, match='uImage'):
        op.pack(bytes(base), fake_squashfs(), 'RBS20', 'x', kernel_size=KSIZE)


def test_header_too_long():
    with pytest.raises(ValueError):
        op.make_header('RBS20', 'v' * 200, '', 'x')
