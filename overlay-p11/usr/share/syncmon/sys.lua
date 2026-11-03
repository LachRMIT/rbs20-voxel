-- P11 dashboard: system, clients, mesh path, traffic and services as JSON.
-- Run by /www.syncmon/sys.cgi after the login check. The fast-changing backhaul
-- state comes from syncmon-watch (api.cgi); this covers what the page polls every 10 s.

local D = "/tmp/syncmon"

local function readf(p)
	local f = io.open(p, "r")
	if not f then return nil end
	local s = f:read("*a")
	f:close()
	return s
end

local function trim(s) return s and (s:gsub("^%s+", ""):gsub("%s+$", "")) or nil end

local function sh(cmd)
	local p = io.popen(cmd .. " 2>/dev/null")
	if not p then return "" end
	local s = p:read("*a") or ""
	p:close()
	return s
end

local function cfg(k)
	local v = trim(sh("/bin/config get " .. k))
	if v == "" then return nil end
	return v
end

-- Minimal JSON encoder (strings, numbers, booleans, arrays, objects).
local function enc(v)
	local t = type(v)
	if v == nil then return "null"
	elseif t == "boolean" then return tostring(v)
	elseif t == "number" then
		if v ~= v or v == math.huge or v == -math.huge then return "null" end
		if v == math.floor(v) then return string.format("%d", v) end
		return string.format("%.2f", v)
	elseif t == "string" then
		return '"' .. v:gsub('[%c"\\]', function(c)
			if c == '"' then return '\\"' elseif c == "\\" then return "\\\\"
			elseif c == "\n" then return "\\n" else return "" end
		end) .. '"'
	elseif t == "table" then
		if #v > 0 or next(v) == nil and getmetatable(v) == "array" then
			local o = {}
			for i = 1, #v do o[i] = enc(v[i]) end
			return "[" .. table.concat(o, ",") .. "]"
		end
		local o, keys = {}, {}
		for k in pairs(v) do keys[#keys + 1] = k end
		table.sort(keys)
		for _, k in ipairs(keys) do o[#o + 1] = enc(tostring(k)) .. ":" .. enc(v[k]) end
		return "{" .. table.concat(o, ",") .. "}"
	end
	return "null"
end

local function arr(t) return setmetatable(t or {}, { __metatable = "array" }) end

local out = { time = os.time() }

-- Identity -------------------------------------------------------------------
out.fw = trim(readf("/firmware_version"))
out.model = trim(readf("/tmp/board_model_id")) or "RBS20"
out.name = cfg("Device_name") or cfg("netbiosname") or trim(readf("/proc/sys/kernel/hostname"))
out.ip = sh("ifconfig br0"):match("inet addr:([%d%.]+)")
out.uptime = tonumber((readf("/proc/uptime") or ""):match("^(%d+)"))
out.time_synced = readf("/tmp/.rbs20_time_ok") ~= nil

-- CPU (difference from the previous call), memory, load, temperature ----------
do
	local l = (readf("/proc/stat") or ""):match("^cpu%s+([^\n]+)")
	if l then
		local n, total = {}, 0
		for x in l:gmatch("%d+") do n[#n + 1] = tonumber(x); total = total + tonumber(x) end
		local idle = (n[4] or 0) + (n[5] or 0)
		local prev = readf(D .. "/cpu.prev")
		local pt, pi = (prev or ""):match("(%d+) (%d+)")
		if pt and total > tonumber(pt) then
			out.cpu = math.floor(100 * (1 - (idle - tonumber(pi)) / (total - tonumber(pt))) + 0.5)
		end
		local f = io.open(D .. "/cpu.prev", "w")
		if f then f:write(total .. " " .. idle); f:close() end
	end
	local m = readf("/proc/meminfo") or ""
	local tot = tonumber(m:match("MemTotal:%s+(%d+)"))
	local avail = tonumber(m:match("MemAvailable:%s+(%d+)"))
	if not avail then
		avail = (tonumber(m:match("MemFree:%s+(%d+)")) or 0) + (tonumber(m:match("Buffers:%s+(%d+)")) or 0)
			+ (tonumber(m:match("\nCached:%s+(%d+)")) or 0)
	end
	if tot then out.mem = { total_kb = tot, used_kb = tot - avail } end
	out.load = (readf("/proc/loadavg") or ""):match("^(%S+ %S+ %S+)")
	-- Board sensor as read by NETGEAR's /sbin/thermal.sh: low byte in degrees C, bit 7 = invalid.
	local t = tonumber(trim(readf("/proc/simple_config/sensor_temp")) or "")
	if t and t % 256 < 128 then out.temp_c = t % 256 end
end

-- Backhaul and Wi-Fi interfaces ------------------------------------------------
local bh = { [cfg("wl5g_BACKHAUL_STA") or "ath11"] = "sta", [cfg("wl2g_BACKHAUL_STA") or "ath02"] = "sta" }
for _, k in ipairs({ "wl5g_BACKHAUL_AP", "wl2g_BACKHAUL_AP" }) do
	local v = cfg(k)
	if v then bh[v] = "ap" end
end

local clients = { g5 = 0, g24 = 0, total = 0 }
local downstream = 0
for ifc in sh("ls /sys/class/net"):gmatch("(ath%d+)") do
	if bh[ifc] ~= "sta" then
		local iw = sh("iwconfig " .. ifc)
		if iw:match("Mode:Master") then
			local freq = tonumber(iw:match("Frequency[:=]([%d%.]+)"))
			local n = 0
			for line in sh("wlanconfig " .. ifc .. " list sta"):gmatch("[^\n]+") do
				if line:match("^%x%x:%x%x:") then n = n + 1 end
			end
			if bh[ifc] == "ap" then
				downstream = downstream + n
			elseif freq and freq > 4 then
				clients.g5 = clients.g5 + n
			else
				clients.g24 = clients.g24 + n
			end
		end
	end
end
clients.total = clients.g5 + clients.g24
out.clients = clients
out.downstream = downstream

-- Path to the router: gateway from the routing table, compared with the
-- backhaul BSSID. Orbi radios use MACs a few steps from the unit's base MAC,
-- so a BSSID close to the gateway's MAC means a direct link to the router.
do
	local gw
	for line in (readf("/proc/net/route") or ""):gmatch("[^\n]+") do
		local dst, g = line:match("^%S+%s+(%x+)%s+(%x+)")
		if dst == "00000000" and g and g ~= "00000000" then
			local b = {}
			for i = 7, 1, -2 do b[#b + 1] = tonumber(g:sub(i, i + 1), 16) end
			gw = table.concat(b, ".")
			break
		end
	end
	local gwmac
	if gw then
		for line in (readf("/proc/net/arp") or ""):gmatch("[^\n]+") do
			local ip, mac = line:match("^(%S+)%s+%S+%s+%S+%s+(%x%x:%x%x:%x%x:%x%x:%x%x:%x%x)")
			if ip == gw then gwmac = mac:lower() end
		end
	end
	out.gateway = { ip = gw, mac = gwmac }
end

-- Traffic: vnstat hourly totals over the backhaul (all client traffic to the
-- router crosses it). vnstat keeps hourly data in KiB.
do
	local hours = {}
	local now = os.time()
	local ifs = {}
	for ifc, kind in pairs(bh) do if kind == "sta" then ifs[#ifs + 1] = ifc end end
	if trim(readf("/tmp/link_status_eth")) == "1" then
		for ifc in sh("ls /sys/class/net"):gmatch("(eth%d+)") do ifs[#ifs + 1] = ifc end
	end
	for _, ifc in ipairs(ifs) do
		for date, rx, tx in sh("vnstat --dumpdb -i " .. ifc):gmatch("\nh;%d+;(%d+);(%d+);(%d+)") do
			date = tonumber(date)
			if date > 0 and now - date < 24 * 3600 then
				local key = date - date % 3600
				local h = hours[key] or { 0, 0 }
				h[1] = h[1] + tonumber(rx); h[2] = h[2] + tonumber(tx)
				hours[key] = h
			end
		end
	end
	local list, rx, tx = arr(), 0, 0
	local cur = now - now % 3600
	for i = 23, 0, -1 do
		local key = cur - i * 3600
		local h = hours[key] or { 0, 0 }
		list[#list + 1] = arr({ key, h[1], h[2] })
		rx = rx + h[1]; tx = tx + h[2]
	end
	out.traffic = { ifaces = arr(ifs), hours = list, rx_kb = rx, tx_kb = tx }
end

-- Services ---------------------------------------------------------------------
do
	local function running(name) return sh("pidof " .. name) ~= "" end
	local function pidfile(p)
		local pid = trim(readf(p))
		return pid ~= nil and pid ~= "" and readf("/proc/" .. pid .. "/stat") ~= nil
	end
	local ps = sh("ps w")
	out.services = arr({
		{ name = "hyd", up = running("hyd"), what = "Mesh routing" },
		{ name = "wsplcd", up = running("wsplcd"), what = "Settings sync" },
		{ name = "repacd", up = ps:find("repacd%-run") ~= nil, what = "Placement" },
		{ name = "hostapd", up = running("hostapd"), what = "Wi-Fi access point" },
		{ name = "wpa_supplicant", up = running("wpa_supplicant"), what = "Backhaul link" },
		{ name = "lbd", up = running("lbd"), what = "Band steering" },
		{ name = "dropbear", up = running("dropbear"), what = "SSH on port 22" },
		{ name = "node exporter", up = pidfile("/var/run/node-exporter.pid"), what = "Metrics on port 9100" },
		{ name = "vnstatd", up = running("vnstatd"), what = "Traffic history" },
		{ name = "remote syslog", up = pidfile("/var/run/logread-remote.pid"), what = cfg("rbs20_syslog_host") or "Not set up" },
	})
end

-- Last tool action -------------------------------------------------------------
do
	local a = readf(D .. "/action")
	if a then
		local t, name, state, msg = a:match("^(%d+)|([^|]*)|([^|]*)|(.*)$")
		if t then out.action = { time = tonumber(t), name = name, state = state, msg = trim(msg) } end
	end
end

io.write(enc(out))
