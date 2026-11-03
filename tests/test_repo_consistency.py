"""Checks that the build inputs stored in the repo are well formed."""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), '..')


def read(*p):
    with open(os.path.join(ROOT, *p)) as f:
        return f.read()


def manifest():
    for line in read('manifest', 'donor-files.txt').splitlines():
        if line.strip() and not line.startswith('#'):
            yield line.split()


def test_manifest_lines_are_well_formed():
    paths = set()
    for parts in manifest():
        kind, path = parts[0], parts[1]
        assert kind in ('F', 'L'), parts
        assert not path.startswith('/') and '..' not in path.split('/'), path
        assert path not in paths, f'duplicate {path}'
        paths.add(path)
        if kind == 'F':
            assert len(parts) == 4
            assert re.fullmatch(r'[0-9a-f]{32}', parts[2]), parts
            assert re.fullmatch(r'[0-7]{3}', parts[3]), parts
        else:
            assert len(parts) == 3


def test_symlinks_point_at_manifest_files():
    files = {p[1] for p in manifest() if p[0] == 'F'}
    links = {p[1]: p[2] for p in manifest() if p[0] == 'L'}
    for link, target in links.items():
        resolved = os.path.normpath(os.path.join(os.path.dirname(link), target))
        seen = set()
        while resolved in links and resolved not in seen:      # follow link chains
            seen.add(resolved)
            resolved = os.path.normpath(os.path.join(os.path.dirname(resolved), links[resolved]))
        assert resolved in files, f'{link} -> {target} has no target in the manifest'


def test_no_secrets_in_manifest_or_overlay():
    assert 'dropbear_ed25519_host_key' not in read('manifest', 'donor-files.txt')
    for d, _, names in os.walk(os.path.join(ROOT, 'overlay')):
        for n in names:
            with open(os.path.join(d, n), 'rb') as f:
                assert b'PRIVATE KEY' not in f.read(), n


def test_patches_are_unified_diffs_against_rootfs_paths():
    pdir = os.path.join(ROOT, 'patches')
    names = sorted(os.listdir(pdir))
    assert names, 'no patches'
    for n in names:
        text = read('patches', n)
        old = re.findall(r'^--- a/(\S+)', text, re.M)
        new = re.findall(r'^\+\+\+ b/(\S+)', text, re.M)
        assert old and old == new, n
        assert re.search(r'^@@ -\d+(,\d+)? \+\d+(,\d+)? @@', text, re.M), n


def test_init_scripts_referenced_by_build_exist():
    build = read('scripts', 'build.py')
    donor = {p[1] for p in manifest()}
    targets = re.findall(r"\('[SK]\d+\w+', '(\w+)'\)", build)
    assert sorted(set(targets)) == ['dropbear', 'haveged', 'syncmon']
    for target in targets:
        rel = f'etc/init.d/{target}'
        assert os.path.exists(os.path.join(ROOT, 'overlay', rel)) or rel in donor, rel


def test_overlay_cgis_require_auth():
    for cgi in ('api.cgi', 'index.cgi'):
        text = read('overlay', 'www.syncmon', cgi)
        assert text.splitlines()[:2] == ['. /usr/share/syncmon/auth.sh', 'syncmon_auth'], cgi


def p10_manifest(name):
    for line in read('manifest', name).splitlines():
        if line.strip() and not line.startswith('#'):
            yield line.split()


def test_p10_manifests_are_well_formed():
    for name in ('stock-closed-files.txt', 'p10-donor-files.txt'):
        for parts in p10_manifest(name):
            kind = parts[0]
            assert kind in ('F', 'L', 'D'), parts
            if kind == 'F':
                assert len(parts) == 4 and len(parts[2]) == 32 and parts[3].isdigit(), parts
            elif kind == 'L':
                assert len(parts) == 3, parts
            else:
                assert len(parts) == 2, parts


def test_p10_has_no_fallback_password():
    for rel in (('overlay-p10', 'etc', 'init.d', 'dropbear'), ('overlay-p10', 'usr', 'share', 'syncmon', 'auth.sh')):
        text = read(*rel)
        assert 'pw=password' not in text and '= password ]' not in text, rel


def test_p11_actions_need_post_and_header():
    text = read('overlay-p11', 'www.syncmon', 'action.cgi')
    assert 'REQUEST_METHOD" != POST' in text and 'HTTP_X_RBS20" != 1' in text
    assert 'syncmon_auth' in text.split('REQUEST_METHOD')[0], 'login check must come first'
    for name in ('sys.cgi', 'action.cgi'):
        assert read('overlay-p11', 'www.syncmon', name).startswith('. /usr/share/syncmon/auth.sh\nsyncmon_auth\n'), name


def test_busybox_timeout_is_portable():
    for rel in (('overlay', 'usr', 'sbin', 'syncmon-watch'), ('overlay-p11', 'usr', 'sbin', 'rbs20-action')):
        text = read(*rel)
        assert 'timeout -t 1 true' in text, rel
        assert not any(l.lstrip().startswith(('timeout ', 'st=$(timeout')) or '$(timeout ' in l for l in text.splitlines()), rel
