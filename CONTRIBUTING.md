# Contributing

Thanks for your interest. This is a personal project, but help is welcome, especially hardware testing.

## Most useful contributions
1. **Hardware test reports.** A real RBS20, or an RBR20 used as a satellite, synced to any Voxel router. Use the *Hardware test report* issue template.
2. **The SOAP "Config Sync" issue.** If you know how NETGEAR's SOAP sync between router and satellite works, see the roadmap in the README.
3. **Security fixes** for the open items in [SECURITY.md](SECURITY.md).

## Ground rules
- **Never commit firmware images, extracted rootfs files or binaries** from NETGEAR or Voxel, in issues, pull requests or attachments. Reference them by name, version and MD5 instead. `.gitignore` blocks the common file types.
- **Don't post personal network details** such as Wi-Fi keys, SSIDs, MAC addresses or public IPs. Mask them in logs and screenshots.
- Keep changes small and explain why in the pull request.

## Development
```sh
pip install pytest ruff
python3 -m pytest          # tests use synthetic images, no firmware needed
ruff check .               # Python lint
shellcheck -s sh -S error overlay/usr/sbin/syncmon-watch overlay/usr/share/syncmon/auth.sh overlay/www.syncmon/*.cgi
```

Shell scripts in `overlay/` run under BusyBox ash on the device, so keep them POSIX `sh` and avoid bash-only features.

If you change `manifest/donor-files.txt`, `patches/` or `overlay/`, rebuild with `scripts/build.py` and say in the pull request whether you flashed the result.
