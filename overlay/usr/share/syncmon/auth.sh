# Sourced by the sync monitor CGIs: HTTP Basic auth against the web admin password.
syncmon_auth() {
	local creds user pw want hashed mine
	case "$HTTP_AUTHORIZATION" in
		"Basic "*) creds=$(echo "${HTTP_AUTHORIZATION#Basic }" | base64 -d 2>/dev/null) ;;
	esac
	user=${creds%%:*}
	pw=${creds#*:}
	if [ -n "$creds" ] && { [ "$user" = admin ] || [ "$user" = root ]; }; then
		want=$(/bin/config get http_passwd)
		hashed=$(/bin/config get http_passwd_hashed)
		[ -n "$want" ] && [ "$pw" = "$want" ] && return 0
		if [ -n "$hashed" ]; then
			mine=$(printf '%s' "$pw" | sha256sum | cut -d' ' -f1 | tr a-f A-F)
			[ "$mine" = "$hashed" ] && return 0
		fi
		[ -z "$want" ] && [ -z "$hashed" ] && [ "$pw" = password ] && return 0
	fi
	printf 'Status: 401 Unauthorized\r\nWWW-Authenticate: Basic realm="Orbi sync monitor (user admin, web admin password)"\r\nContent-Type: text/plain\r\n\r\nLogin required: user admin, your web admin password.\n'
	exit 0
}
