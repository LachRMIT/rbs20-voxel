. /usr/share/syncmon/auth.sh
syncmon_auth
printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n'
cat /tmp/syncmon/state.json 2>/dev/null || printf '{"error":"monitor starting"}'
