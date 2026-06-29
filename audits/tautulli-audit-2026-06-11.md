# Services Best Practice Audit — Tautulli
2026-06-11

## Summary
4 findings: 0 🔴 critical · 2 🟡 warning · 2 🔵 info

---

## Tautulli

### 🟡 Warning

- [ ] **WebSocket ping-pong disabled — Tautulli cycles "Plex is down" every ~90 seconds**
  - **Why it matters:** Without WebSocket keepalive pings, Plex drops idle WebSocket connections after ~50 seconds. Tautulli reads the drop as "Plex server is down", waits 30 seconds, then reconnects — and the cycle repeats indefinitely. During the ~80 seconds per cycle that Tautulli thinks Plex is down, stream detection is blind: plays that start and finish within that window won't be logged, and "Plex down" notifications would fire if configured.
  - **Source:** Live logs — confirmed cycling at 21:57:06→21:57:55→21:58:27 UTC repeatedly; `websocket_monitor_ping_pong = 0` in config.ini
  - **Current:** `websocket_monitor_ping_pong = 0` — ping/pong disabled
  - **Recommended:** Enable in Tautulli UI → Settings → Tautulli → (Advanced tab) → "Monitor Plex WebSocket ping/pong" → On. Alternatively edit config.ini directly: `websocket_monitor_ping_pong = 1` (requires restart).
  - **Manual fix:** Tautulli UI → Settings → Tautulli → Advanced

- [ ] **Plex connected via container IP — will silently break on next Plex recreate**
  - **Why it matters:** `pms_ip = 172.29.0.8` and `pms_url = http://172.29.0.8:32400` are Docker-assigned IPs that change whenever the Plex container is recreated. Right now the IP happens to be correct — but the next `docker compose up -d plex` will assign a new IP and Tautulli will silently lose its Plex connection until manually reconfigured.
  - **Source:** config.ini — `pms_ip = 172.29.0.8` confirmed; Plex current IP also `172.29.0.8` (currently matching, but ephemeral)
  - **Current:** `pms_ip = 172.29.0.8`, `pms_url = http://172.29.0.8:32400`
  - **Recommended:** Tautulli UI → Settings → Tautulli → Plex Media Server → IP Address: change to `plex` (container name). Tautulli will resolve this via Docker DNS to the current container IP regardless of recreates.
  - **Manual fix:** Tautulli UI → Settings → Tautulli → Plex Media Server

---

### 🔵 Info

- [ ] **No healthcheck defined**
  - **Why it matters:** If Tautulli's web process hangs, Docker keeps it listed as "Up" while the UI and API are unresponsive.
  - **Source:** [linuxserver.io — tautulli image](https://docs.linuxserver.io/images/docker-tautulli/) — no built-in healthcheck
  - **Current:** `Health=null` confirmed via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8181/status"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [ ] **No memory limit**
  - **Why it matters:** Tautulli is lightweight in normal operation (~100–200 MB), but can spike during history imports or database maintenance. Low practical risk.
  - **Current:** `Memory: 0`
  - **Recommended:** `mem_limit: 512m`

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| WebSocket ping-pong disabled | Config fix — edited `config.ini` directly via SSH (stopped container first): `websocket_monitor_ping_pong = 0` → `1`; container restarted | — | ✅ Logs show "Scheduled background task: Websocket ping" — keepalive active, no more cycling |
| Plex connected via container IP | Config fix — UI save failed (known Tautulli quirk); applied directly to `config.ini` via SSH: `pms_ip = plex`, `pms_url = http://plex:32400` | — | ✅ Logs confirm `Selected server: gauchoflix (http://plex:32400)` |
| No healthcheck | Applied via compose — `healthcheck` with `/status` endpoint | 7791e94 | ✅ `Health=healthy` |
| No memory limit | Applied via compose — `mem_limit: 512m` | 7791e94 | ✅ `Mem=536870912` |

---

## What's working well

- ✅ Container running (6 days uptime since 2026-06-05) ✅
- ✅ Tautulli successfully connects to Plex on startup — WebSocket does reach "Ready" state ✅
- ✅ `pms_token` set — Plex authentication configured ✅
- ✅ `pms_identifier` set — Plex server identity pinned ✅
- ✅ `pms_ssl = 0` — correct for internal LAN access ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID: 1000 / PGID: 1000` set ✅
