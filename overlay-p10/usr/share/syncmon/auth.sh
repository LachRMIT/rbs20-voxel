# Sourced by the dashboard CGIs: HTTP Basic auth against the web admin password.
# P10: no fallback password. A successful login also sets root's SSH password to the
# password just typed, when the unit only stores the hashed admin password.
syncmon_auth() {
	local creds user pw want hashed mine ok=0
	case "$HTTP_AUTHORIZATION" in
		"Basic "*) creds=$(echo "${HTTP_AUTHORIZATION#Basic }" | base64 -d 2>/dev/null) ;;
	esac
	user=${creds%%:*}
	pw=${creds#*:}
	if [ -n "$creds" ] && [ -n "$pw" ] && { [ "$user" = admin ] || [ "$user" = root ]; }; then
		want=$(/bin/config get http_passwd)
		hashed=$(/bin/config get http_passwd_hashed)
		if [ -n "$want" ] && [ "$pw" = "$want" ]; then
			ok=1
		elif [ -n "$hashed" ]; then
			mine=$(printf '%s' "$pw" | sha256sum | cut -d' ' -f1 | tr a-f A-F)
			[ "$mine" = "$hashed" ] && ok=1
		fi
	fi
	if [ $ok = 1 ]; then
		mine=$(printf '%s' "$pw" | md5sum | cut -d' ' -f1)
		if [ "$(cat /tmp/.rootpw_synced 2>/dev/null)" != "$mine" ]; then
			printf '%s\n%s\n' "$pw" "$pw" | passwd -a md5 root >/dev/null 2>&1 && echo "$mine" > /tmp/.rootpw_synced
		fi
		return 0
	fi
	printf 'Status: 401 Unauthorized\r\nWWW-Authenticate: Basic realm="RBS20 dashboard (user admin, web admin password)"\r\nContent-Type: text/plain\r\n\r\nLogin required: user admin, your web admin password.\n'
	exit 0
}
