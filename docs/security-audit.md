# Stock RBS20 2.7.6.6 firmware — security / hardening audit

Static analysis of `RBS20-V2.7.6.6.img` (squashfs rootfs @ 0x320080, OpenWrt CC
15.05.1 / QSDK, kernel 3.14.77). Method: hunt embedded secrets, debug/diagnostic
interfaces, default-on services, and unauthenticated command/update paths, then
apply kill criteria (public keys, non-shipping code, loopback-only, auth-gated,
factory-only). This is a hardening check of hardware I own. No device was touched; everything
below comes from reading the image.

**Headline:** the stock image ships **no hardcoded root password, no embedded
private key, and no unauthenticated root shell**. Every privileged path I found is
gated by the user's web-admin password or a NETGEAR factory key that is not in the
image. The real new exposure lives in the **custom P6/P8 builds**, not in stock —
see the last section.

---

## Confirmed exposures (shipped and reachable, but all authenticated)

### C1 — `sshenable` UDP magic-packet listener runs at boot
- **Where:** `etc/init.d/sshenable.init` (linked `S98sshenable.init`, starts at boot),
  binary `usr/sbin/sshenable`.
- **What:** When `factory_mode != 1` and `ssh_enabled != 1` (the shipped default),
  boot starts `sshenable`, a UDP listener. On a packet of the form
  `AMBIT_SSH_ENABLE+<mac>+<password>` it checks the password against the datalib
  `http_passwd` / `http_passwd_hashed` (admin GUI password, SHA-256), and only on a
  match touches `/etc/init.d/sshd start`. Evidence: `AMBIT_SSH_ENABLE+%.64s+%.64s`,
  `http_passwd`, `http_passwd_hashed`, `EVP_sha256` in the binary.
- **Why it matters:** a network-reachable listener is on by default and will turn on
  the SSH server, but only for someone who already knows the admin password and the
  unit's MAC. It is an *enable* path, not a shell, and it is authenticated.
- **Rating:** attack surface / `low`. Authenticated by the user's own password.
  Hardening: leave `factory_mode=0`; set a strong web-admin password (that password
  *is* the key here).

### C2 — `telnetenable` daemon + `utelnetd` ship (same AMBIT scheme)
- **Where:** `etc/init.d/telnet`, `etc/init.d/done`, `usr/sbin/telnetenable`,
  `usr/sbin/utelnetd`, `sbin/reset_to_default`, `usr/share/udhcpc/default.script-ext`.
- **What:** The classic NETGEAR telnet backdoor daemon. `AMBIT_TELNET_ENABLE+<mac>`
  plus the admin password (`http_passwd`/`http_passwd_hashed`) starts
  `utelnetd -d -i br0`. **It has no `S*` boot link** — in normal mode nothing starts
  it. It only runs unconditionally in `factory_mode=1` (`etc/init.d/telnet start`,
  `done`), or on the authenticated magic packet, or when `/tmp/enable_telnet` is set.
- **Why it matters:** telnet is plaintext and lands on `br0` (LAN). But it is **not
  default-on** on a production unit and is admin-password-gated.
- **Rating:** informational / `low`. Not enabled by default; authenticated when it is.
  Hardening: nothing required unless someone sets `factory_mode`.

### C3 — Web admin stack (lighttpd + `net-cgi`) runs as **root** on all interfaces
- **Where:** `etc/init.d/lighttpd`, `etc/lighttpd/lighttpd_satellite.conf`,
  `etc/lighttpd/conf.d/30-cgi.conf`, `usr/sbin/net-cgi` (850 KB), `usr/sbin/soap-api`.
- **What:** On the satellite, lighttpd serves `/www.satellite` with
  `server.username = "root"`, port 80 (and 443), with no `$SERVER["socket"]` bind
  restriction (all interfaces). Every non-static request is handed to `net-cgi` as
  root; `soap/server_sa*` is routed to `soap-api`. This is the SOAP/mesh + admin
  control plane and it executes as root.
- **Why it matters:** this is the single largest root-privileged input surface on the
  box. `net-cgi`/`soap-api` are stripped 650–850 KB binaries; I could not prove the
  absence of an auth-bypass or injection in them by static strings alone (they do
  their own session/auth checks internally, and call `system`/`popen`). This is
  *normal* for Orbi and not a specific confirmed bug — it is the thing to keep patched
  and off the WAN.
- **Rating:** privilege note / `medium` (surface, not a proven defect). Hardening: keep
  the admin UI LAN-only (it already serves the satellite page; satellites aren't meant
  to be WAN-exposed), use HTTPS (`force_https=1`), strong admin password.

### C4 — `tftpd-hpa` starts at boot on all interfaces
- **Where:** `etc/init.d/tftpd-hpa` (`S50tftpd-hpa`).
- **What:** `tftpd-hpa -l -s /var/tftpd-hpa` — chrooted to an empty dir, started at
  boot, bound to all interfaces. Read/limited surface, used by the recovery/NMRP flow.
- **Rating:** `low`. Chrooted, empty root. Hardening: none needed; keep off WAN.

---

## Killed leads (looked like findings, aren't)

- **No embedded private keys in stock.** Grepping the whole rootfs for
  `BEGIN ... PRIVATE KEY` matches only inside `sshd`, `hostapd`, `libwolfssl`,
  `libmbedtls` — those are PEM **format strings** compiled into the libraries, not
  key material. No `.key`/`.pem` private key file ships. **Kill.**
- **`etc/ssh/rbr50-id_rsa.pub` is a PUBLIC key.** sshd ships
  `AuthorizedKeysFile /etc/ssh/rbr50-id_rsa.pub`, `PubkeyAuthentication yes`,
  `PasswordAuthentication no`, `PermitRootLogin yes`, **but** `ForceCommand
  /bin/ssh_login`. So whoever holds the matching **RBR50 private key** (the router /
  NETGEAR, not in this image) can connect, and even then `ssh_login` demands the two
  GUI security-question answers before `exec /bin/ash`. The key in the image is public;
  the private half is not shipped. **Kill** (fleet-wide *public* key), with a note:
  this is the mesh trust anchor — a rogue/compromised RBR50 that holds the private key
  reaches a security-question-gated root shell. Worth being aware of, not a shipped
  secret.
- **No hardcoded root/backdoor credential.** `etc/init.d/boot` seeds
  `root:!:0:0:...` (password *locked*). `usr/sbin/user-manager.sh` (`update_user`)
  then sets root's and admin's password to the user's **web-admin password**
  (`http_passwd`). There is no literal password compared in a binary, no extra hidden
  account (`guest`/`nobody`/`daemon` are `*`-locked). **Kill.**
- **HTTPS server key is generated at runtime, not shipped.** `ssl.pemfile` points at
  `/tmp/secure/etc/lighttpd/certs/server.pem`, created by `https_cert.sh` /
  `https_cert_update` with `openssl req -x509 ... rsa:2048` at first boot.
  `etc/lighttpd/certs/dhparam.pem` is DH parameters (public, not a secret). **Kill**
  (embedded TLS key).
- **`/etc/ssl/certs/*` incl. `auto-ca.crt`, `dni_st_ca2.crt`, `manual-ca.crt`** are CA
  **certificates** (public). **Kill.**
- **`sshd` itself is not started by default.** `sshenable.init` only runs `sshd start`
  when `ssh_enabled=1`; the shipped default leaves SSH off (only the C1 enable-listener
  runs). `sshd_config` is otherwise hardened: `PasswordAuthentication no`,
  `PermitEmptyPasswords no`, `UsePrivilegeSeparation sandbox`, `ForceCommand ssh_login`.
  **Kill** (default-on remote shell).
- **`__rd_debug_only/`** contains only read-only procps tools (`top`, `ps`, `free`,
  `vmstat`, `pgrep`, …) — no shell, no privileged hook. **Kill.**
- **`dni-debug.init`** only captures a console crash log, and only when
  `debug_boot_up=1` (not default). **Kill.**
- **Factory-mode paths** (unconditional telnet + sshd) depend on `factory_mode=1`,
  which is off on a shipped unit. **Kill** (not shipping-default).

---

## Findings that carry into the custom P6 / P8 builds

The P6 rootfs is stock plus Voxel dropbear + haveged; P8 adds the `:8080` sync
monitor. Three stock behaviours change, **all in the direction of more exposure**, and
these are the items actually worth fixing in the custom builds:

### P1 — P6/P8 ship a **fixed, shared dropbear host private key**  ⚠ top priority
- `etc/dropbear/dropbear_ed25519_host_key` is present in **both** P6 and P8 and is
  **byte-identical** (md5 `7028ef9a3311b8169f4223c3cb9f02f5`). It is a **private** host
  key baked into the image, so every unit flashed with P6/P8 presents the same SSH
  host identity.
- **Impact:** defeats SSH host-key verification — an attacker on the backhaul/LAN can
  impersonate the satellite or MITM the SSH session without a key mismatch warning.
  It is a shared secret that is the same on every device (a host key, not a login credential, so it is impersonation/MITM rather than direct
  login).
- **Fix:** don't ship the key. Generate it on first boot (dropbear already supports
  this — drop the committed key and let `-R` create one per unit, as stock sshd does).
  This contradicts the P1 build notes, which say keys are generated per unit; by P6 a
  fixed key was committed.

### P2 — P6/P8 root SSH listens on **all interfaces** with a **"password" fallback**
- `etc/init.d/dropbear` runs `dropbear -p 22` (no bind address → **0.0.0.0:22**,
  unlike stock sshd which pins `ListenAddress` to the `br0` LAN IP) with password auth,
  and sets root's password to `http_passwd` **or, if that isn't stored, the literal
  `password`** (`pw=$($CONFIG get http_passwd); [ -n "$pw" ] || pw=password`).
- **Impact:** if the unit has no *plaintext* admin password stored (stock keeps only
  the SHA-256 `http_passwd_hashed`, so `http_passwd` is frequently empty), root is
  reachable as **`root` / `password`** on every interface the satellite has. That is a
  predictable credential on an all-interfaces listener — the closest thing to a real
  finding in the whole project, and it is in the custom build, not NETGEAR's.
- **Fix:** bind dropbear to the LAN bridge (`-p <br0-ip>:22` or firewall it); never
  fall back to a static password — if no password can be derived, refuse to start SSH
  or require a key. Prefer deriving from `http_passwd_hashed` instead of inventing one.

### P3 — P8 sync monitor: root CGI on **:8080, all interfaces**
- `etc/lighttpd/lighttpd_syncmon.conf`: second lighttpd, `server.port = 8080`, no
  socket bind restriction (**all interfaces**), `server.username = "root"`,
  `cgi.assign ".cgi" => "/bin/sh"`.
- **Auth is present and sound in intent:** `usr/share/syncmon/auth.sh` does HTTP Basic
  against `http_passwd` / `http_passwd_hashed`, and `index.cgi`/`api.cgi` call it before
  emitting anything. `api.cgi` only `cat`s `/tmp/syncmon/state.json`; **no HTTP input
  reaches a shell** (no command injection). Good.
- **But** it inherits the same **`password` fallback** (`[ -z "$want" ] && [ -z
  "$hashed" ] && [ "$pw" = password ]`) and binds to all interfaces, exposing mesh
  topology, BSSIDs and logs to anyone who can reach :8080 with that fallback. The
  string compare is also non-constant-time (minor timing leak).
- **Fix:** bind :8080 to the LAN/loopback, and drop the `password` fallback here too.

### Carried through unchanged from stock
- C1 `sshenable` listener, C2 `telnetenable` binaries, C3 root web stack, C4 `tftpd`
  are all still present in P6/P8 (the Voxel changes are additive). Same ratings apply.
  Note P6/P8 **disable** `sshenable.init` (`K98`/removed `S98`) because dropbear takes
  port 22 — so C1's enable-listener is actually *off* in the custom builds, replaced by the
  always-on dropbear of P2.

---

## Summary

Stock RBS20 2.7.6.6 is clean in the sense that matters: no baked-in root password, no
private keys in the image, and no unauthenticated way to a root shell — the telnet/SSH
"enable" daemons and the RBR50 authorized key all require the admin password or a key
NETGEAR never ships inside the firmware. The things to actually fix are in the custom
P6/P8 builds: a **shared dropbear host key** committed into the image, and a **root/SSH
(and P8 :8080) login that falls back to the literal password `password` and listens on
every interface**. Pin those listeners to the LAN and remove the static-password
fallback, and the custom builds are as tight as stock.
