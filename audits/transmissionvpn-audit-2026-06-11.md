# Services Best Practice Audit — TransmissionVPN
2026-06-11

## Summary
4 findings: 0 🔴 critical · 1 🟡 warning · 3 🔵 info

---

## TransmissionVPN

### 🟡 Warning

- [ ] **RPC has no authentication — any LAN device can control Transmission**
  - **Why it matters:** The Transmission web UI and RPC API (port 9091) require no credentials. Any device on the LAN — or malicious code running on a LAN device — can add/remove torrents, change settings, or reconfigure download paths without logging in. It's not externally exposed (not proxied via NPM), which limits the blast radius, but defence in depth is still worth it.
  - **Source:** [Transmission docs — RPC authentication](https://github.com/transmission/transmission/blob/main/docs/Editing-Configuration-Files.md) — `rpc-authentication-required`, `rpc-username`, `rpc-password`
  - **Current:** Confirmed no credentials required — API returns session data without auth
  - **Recommended:** Enable via env vars in compose:
    ```yaml
    TRANSMISSION_RPC_AUTHENTICATION_REQUIRED: "true"
    TRANSMISSION_RPC_USERNAME: ${TRANSMISSION_RPC_USER}
    TRANSMISSION_RPC_PASSWORD: ${TRANSMISSION_RPC_PASS}
    ```
    Add `TRANSMISSION_RPC_USER` and `TRANSMISSION_RPC_PASS` to `.env` and `.env.template`. The ARR apps (Sonarr/Radarr) will need the credentials added to their download client config.

---

### 🔵 Info

- [ ] **`encryption: preferred` — unencrypted peers can connect**
  - **Why it matters:** Transmission's peer encryption is set to `preferred`, meaning it will use BitTorrent-level encryption with peers that support it but will fall back to unencrypted connections. With a VPN all traffic is tunneled anyway, so the practical privacy risk is low — but setting `required` costs nothing and eliminates the fallback entirely.
  - **Source:** [Transmission docs](https://github.com/transmission/transmission/blob/main/docs/Editing-Configuration-Files.md) — encryption: 0=prefer unencrypted, 1=prefer encrypted, 2=require encrypted
  - **Current:** `encryption: preferred` (value 1)
  - **Recommended:** Add to compose env:
    ```yaml
    TRANSMISSION_ENCRYPTION: "2"
    ```

- [ ] **No memory limit**
  - **Why it matters:** Transmission is lightweight at idle but can spike during large batch imports or intensive seeding. No practical risk on the NAS01's 62 GB, but consistent with the stack.
  - **Current:** `Memory: 0`
  - **Recommended:** `mem_limit: 1g`

- [ ] **healthcheck has no `start_period` — may log false positives on startup**
  - **Why it matters:** The built-in healthcheck (`/etc/scripts/healthcheck.sh`) starts running immediately when the container starts. OpenVPN negotiation + Transmission daemon startup takes 15–30 seconds, during which the healthcheck will fail and Docker logs the container as `unhealthy`. This clears on its own once the VPN connects, but it makes Uptime Kuma alerts noisy on restarts. A `start_period` suppresses checks during the init window.
  - **Source:** haugene/transmission-openvpn healthcheck built into image — no `start_period` set
  - **Current:** `Interval=60s`, no `Timeout`, no `Retries`, no `StartPeriod` (Docker defaults: timeout=30s, retries=3, start_period=0s)
  - **Recommended:** Override in compose to add a grace period:
    ```yaml
    healthcheck:
      test: ["CMD-SHELL", "/etc/scripts/healthcheck.sh"]
      interval: 60s
      timeout: 20s
      retries: 3
      start_period: 30s
    ```

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| No RPC authentication | Skipped by user | — | — |
| `encryption: preferred` | Applied via compose — `TRANSMISSION_ENCRYPTION: "2"` | 4ed61f4 | ✅ Setting active |
| No memory limit | Applied via compose — `mem_limit: 1g` | 4ed61f4 | ✅ `Mem=1073741824` |
| healthcheck missing start_period | Applied via compose — `start_period: 30s`, `timeout: 20s` | 4ed61f4 | ✅ Healthcheck override active |
| WireGuard (bonus investigation) | `VPN_TYPE=wireguard` tried — haugene v5.4.1 does not bundle `wg-quick`; env var silently ignored, container ran OpenVPN. Reverted. Staying on OpenVPN. | ce72696 | — |

---

## What's working well

- ✅ VPN confirmed active — external IP `140.228.21.125` (not the home IP) ✅
- ✅ PIA port forwarding working — port `53571` reserved via PIA API every 15 min, set as Transmission peer port ✅
- ✅ `port-forwarding-enabled: False` — correct for PIA; UPnP/NAT-PMP would fail through the VPN tunnel anyway; PIA handles forwarding at the VPN endpoint ✅
- ✅ Built-in healthcheck: checks DNS resolution, ping, OpenVPN process, and Transmission process ✅
- ✅ `incomplete-dir: /storage/downloads_ds/incomplete` enabled — in-progress downloads staged separately ✅
- ✅ `download-dir: /storage/downloads_ds/completed` — correct final destination ✅
- ✅ `rename-partial-files: True` — `.part` suffix on in-progress files ✅
- ✅ `peer-port-random-on-start: False` — stable port ✅
- ✅ `NET_ADMIN` cap correctly set — required for VPN tunnel management ✅
- ✅ `LOCAL_NETWORK: 192.168.1.0/24` — LAN clients can reach the web UI without routing through the VPN ✅
- ✅ No `/dev/net/tun` device entry needed — TUN is built into the NAS01 kernel ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `TRANSMISSION_HOME: /config` — settings persist in appdata ✅
- ✅ `utp-enabled: False` — µTP disabled, reasonable choice for VPN to avoid tunnel overhead ✅
