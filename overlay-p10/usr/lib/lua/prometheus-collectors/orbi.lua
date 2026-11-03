-- Orbi satellite metrics for prometheus-node-exporter-lua (P10).
-- Backhaul signal/rate per band, associated clients per radio, mesh daemons up.

local function sh(cmd)
  local f = io.popen(cmd .. " 2>/dev/null")
  if not f then return "" end
  local out = f:read("*a") or ""
  f:close()
  return out
end

local function trim(s) return (s or ""):gsub("^%s+", ""):gsub("%s+$", "") end

local function scrape()
  local bh = {
    ["5g"] = trim(sh("/bin/config get wl5g_BACKHAUL_STA")),
    ["2g"] = trim(sh("/bin/config get wl2g_BACKHAUL_STA")),
  }
  if bh["5g"] == "" then bh["5g"] = "ath11" end
  if bh["2g"] == "" then bh["2g"] = "ath02" end

  local rssi = metric("orbi_backhaul_signal_dbm", "gauge")
  local rate = metric("orbi_backhaul_bitrate_mbps", "gauge")
  for band, ifc in pairs(bh) do
    local iw = sh("iwconfig " .. ifc)
    local sig = iw:match("Signal level[=:](%-?%d+)")
    local br, unit = iw:match("Bit Rate[=:]([%d%.]+)%s*([GMk])b/s")
    if sig then rssi({band = band, interface = ifc}, tonumber(sig)) end
    if br then
      local mbps = tonumber(br)
      if unit == "G" then mbps = mbps * 1000 elseif unit == "k" then mbps = mbps / 1000 end
      rate({band = band, interface = ifc}, mbps)
    end
  end

  local clients = metric("orbi_wifi_clients", "gauge")
  for ifc in sh("ls /sys/class/net"):gmatch("ath%d+") do
    if ifc ~= bh["5g"] and ifc ~= bh["2g"] then
      local n = 0
      for line in sh("wlanconfig " .. ifc .. " list sta"):gmatch("[^\n]+") do
        if line:match("^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x") then n = n + 1 end
      end
      clients({interface = ifc}, n)
    end
  end

  local up = metric("orbi_daemon_up", "gauge")
  for _, d in ipairs({"hyd", "wsplcd", "lbd", "hostapd", "wpa_supplicant"}) do
    up({daemon = d}, (sh("pidof " .. d) ~= "") and 1 or 0)
  end
end

return { scrape = scrape }
