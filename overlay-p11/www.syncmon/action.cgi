. /usr/share/syncmon/auth.sh
syncmon_auth
# POST only, plus a custom header: a page on another site can't add one without a
# CORS preflight (which this server never answers), so it can't trigger a reboot
# through the browser's saved login.
if [ "$REQUEST_METHOD" != POST ] || [ "$HTTP_X_RBS20" != 1 ]; then
	printf 'Status: 403 Forbidden\r\nContent-Type: text/plain\r\n\r\nPOST with X-RBS20: 1 only.\n'
	exit 0
fi
what=${QUERY_STRING#do=}
case "$what" in
	speedtest|resync|wifi|reboot) ;;
	*) printf 'Status: 400 Bad Request\r\nContent-Type: text/plain\r\n\r\nUnknown action.\n'; exit 0 ;;
esac
if [ -d /tmp/syncmon/action.lock ]; then
	printf 'Status: 409 Conflict\r\nContent-Type: application/json\r\n\r\n{"ok":false,"msg":"Another tool is still running."}'
	exit 0
fi
start-stop-daemon -S -b -x /usr/sbin/rbs20-action -- "$what"
printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n{"ok":true}'
