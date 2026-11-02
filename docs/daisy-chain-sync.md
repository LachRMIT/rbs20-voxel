# Syncing a new satellite through another satellite (daisy chain)

Question: can a never-synced Orbi satellite be synced to a satellite that is already in the mesh, when the router is out of range?

**Answer: yes, over Wi-Fi, if you press the Sync button on the already-connected satellite, not on the router.** This is built into stock RBS20 2.7.6.6 and Voxel RBS50 9.2.5.2.39SF, and the logic is identical in both. Our P-builds keep the stock RBS20 Wi-Fi scripts and repacd, so they behave the same way.

## How it works (evidence from the firmware)

### 1. The Sync button picks a role from the unit's backhaul state
- `sbin/button_detect` handles a short press by calling `wlan wps --pbc_start`, and it also writes `wps_pbc` to `/var/run/repacd.pipe`.
- `lib/wifi/qcawifi.sh`, `get_optype_opmode_qcawifi()` (line 3141), decides the role:
  - **The backhaul STA is associated** (`/proc/sys/net/<sta>/status` shows RUN): the role is `BACKHAUL NORMAL` / `AP`, and the unit runs `hostapd_cli wps_pbc` on its **own backhaul AP** and its fronthaul APs. The satellite acts as the **WPS registrar**.
  - **The backhaul STA is not associated**: the role is `BACKHAUL` / `STA`, and the unit runs `wpa_cli wps_pbc` on the backhaul STA. The satellite acts as the **WPS enrollee**.
- `sbin/update-wifi` `generate_wps()` sets `wps_state` and `wps_pbc=1` on the `backhaul_ap` VAP, so the satellite's backhaul AP really does have WPS turned on.

### 2. Daisy chain is turned on by default
- `/etc/config/repacd`: `WiFiLink.DaisyChain '1'`.
- `lib/dni_platform/project/dni_project.sh` forces `repacd_Daisy_Chain_Enable=1` once at boot, and on a satellite it picks the daisy-chain operation modes (`wlg_operation_mode=8`, `wla_operation_mode=6`).
- `lib/wifi/wps-supplicant-update-uci`: after a WPS join with DaisyChain on, the new unit copies the SSID and PSK it received into its own backhaul AP's hostapd config, so it can serve as the next hop and as a registrar itself.
- `repacd-wifimon.sh` has hop-2+ logic (`__repacd_wifimon_is_serving_ap_daisy_son`, root-distance inheritance).

### 3. The full config (SSIDs, keys and so on) still comes from the router, relayed through the chain
- `/etc/init.d/wsplcd`: the default role is `ENROLLEE` on a satellite and `REGISTRAR` on a base. Only the router hands out the full config.
- wsplcd uses IEEE 1905.1 AP auto-configuration, which crosses the mesh (the binary has "relay bit" and "Forward Unicast (Response/WPS) packets from ALL interfaces"). So once WPS gives the new unit backhaul access through satellite A, its wsplcd enrollee reaches the router's registrar through A.
- SOAP registration with the router runs over IP, so it also works across hops.

### Voxel RBS50 vs stock RBS20
- `get_optype_opmode_qcawifi()` is byte-identical. `50-wps` is identical. DaisyChain is `'1'` and forced on in both. The only difference in `button_detect` is how `ping-netgear` is killed, which has nothing to do with sync.

## Procedure
1. Make sure satellite A (the one already in the mesh) is connected and solid.
2. Put the new unit (factory-reset or never synced) within good range of A.
3. Press Sync on **satellite A**, then press Sync on the new unit within 2 minutes.
4. **Don't** press Sync on the router at the same time. Two registrars running WPS PBC at once causes a "session overlap" and the enrollee gives up.
5. Wait for wsplcd to clone the config. The new unit's LED should go solid.

## Caveats
- **A satellite on Ethernet backhaul can't act as the registrar this way.** Its Wi-Fi backhaul STA isn't associated, so `get_optype_opmode_qcawifi()` puts it into STA/enrollee mode. Use a satellite that has a Wi-Fi backhaul link.
- If `disable_supplicant_after_connect_to_base=1` and `conn_base=1` are set, the STA-side WPS is skipped. This only affects a unit that is already linked to the base.
- Mixing models (an RBS20 joining through an RBS50v2) is less tested. The new unit has to hear A's backhaul radio well. Untested on our hardware.
- Each extra hop roughly halves the Wi-Fi backhaul throughput.

## Wired option
- Plugging the new satellite's Ethernet port into the router, or into any synced satellite's LAN port, is the most reliable option. wsplcd and hyd run on the HyFi bridge, which includes Ethernet, so the 1905 auto-config reaches the router's registrar over the cable. repacd's gateway monitor (`repacd-gwmon.sh`) detects that the gateway is reachable over Ethernet.
- Once the unit has synced, you can unplug it and move it. It keeps the backhaul credentials and reconnects over Wi-Fi.
