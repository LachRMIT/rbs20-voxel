. /usr/share/syncmon/auth.sh
syncmon_auth
printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n'
mkdir -p /tmp/syncmon
lua /usr/share/syncmon/sys.lua || printf '{"error":"sys.lua failed"}'
