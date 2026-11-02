# Security notes

These are known weaknesses in the P6 to P8 prototype builds. They come from my own static audit ([docs/security-audit.md](docs/security-audit.md)). They are written down here rather than hidden, because anyone building this should know about them before flashing.

The stock NETGEAR RBS20 2.7.6.6 image came out of that audit well: no hardcoded root password, no private keys in the image, and no unauthenticated path to a root shell. The issues below are ones the custom builds introduced.

| # | Issue | Affects | Status in this repo |
|---|---|---|---|
| 1 | **Shared SSH host private key.** P6 to P8 baked one dropbear ed25519 host key into the image, so every unit presented the same SSH identity, which makes impersonation and man-in-the-middle possible. | P6, P7, P8 images | **Fixed.** The key is not in this repo and `scripts/build.py` leaves it out. Dropbear's `-R` flag generates a key on the unit instead. (`--host-key` exists for testing only.) |
| 2 | **Root SSH on every interface, with a `password` fallback.** `overlay/etc/init.d/dropbear` runs `dropbear -p 22`, which binds 0.0.0.0. It sets root's password to the stored plaintext web admin password, or to the literal `password` if none is stored. Stock firmware often stores only the hashed password, so the fallback is likely to apply. | P6, P7, P8 and this repo | **Open.** Change the admin password and keep the unit off untrusted networks. Planned fix: bind to the LAN bridge only and refuse to start without a real password or key. |
| 3 | **Sync monitor on :8080, all interfaces, as root.** It requires HTTP Basic auth against the web admin password, and no request input reaches a shell (the CGIs only print a JSON file). It has the same `password` fallback as #2, though, and it shows mesh topology, BSSIDs and filtered logs. | P8 and this repo | **Open.** Planned fix: bind to the LAN and drop the fallback. |

Also note: the builds turn off NETGEAR's `sshenable` listener because dropbear takes port 22. The stock web UI (lighttpd plus `net-cgi`, as root) is unchanged from NETGEAR.

If you find something else, please open an issue.
