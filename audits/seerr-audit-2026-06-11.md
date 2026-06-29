# Services Best Practice Audit — Seerr
2026-06-11

## Summary
4 findings: 0 🔴 critical · 2 🟡 warning · 2 🔵 info

---

## Seerr

### 🟡 Warning

- [ ] **Sonarr queue sync failing every minute — `Unable to get queue from Sonarr server: sonaar`**
  - **Why it matters:** Seerr's Download Tracker uses the Sonarr queue to show request status (e.g. "Downloading", "Awaiting Import"). With this failing, all Sonarr-backed requests show stale or incorrect status in the UI. The error repeats every 60 seconds.
  - **Source:** Live logs — recurring since before this audit; confirmed at 01:45, 01:50, 01:51 UTC today
  - **Current:** `192.168.1.33:8989` set as Sonarr hostname. API key is valid (confirmed via direct API call — Sonarr v4.0.17 responds correctly, queue returns `totalRecords: 0`). Radarr uses the same host-IP pattern and works fine, which narrows the cause.
  - **Likely cause:** Seerr containers using the host IP (`192.168.1.33`) for inter-container calls creates a hairpin NAT path. For Sonarr specifically this appears to cause intermittent failures on the `/queue` endpoint. Switching to the container name avoids the hairpin entirely.
  - **Recommended:** Settings → Services → Sonarr → Edit: change hostname from `192.168.1.33` to `sonarr` (container name). Test connection, then save.
  - **Manual fix:** Seerr UI → Settings → Services → Sonarr

- [ ] **All service hostnames use host IP instead of container names**
  - **Why it matters:** Sonarr, Radarr, Radarr4K, and Plex are all configured with `192.168.1.33` as the hostname. All four containers are on the same `homelab` Docker network, so container-name DNS resolution is available and preferred — it's faster (no NAT hop), stays correct if the host IP ever changes, and is consistent with how other services in this stack communicate.
  - **Source:** `settings.json` — `sonarr: 192.168.1.33:8989`, `radarr: 192.168.1.33:7878`, `radarr4k: 192.168.1.33:7070`, `plex: 192.168.1.33:32400`
  - **Recommended:** Update all four in Seerr UI:
    - Sonarr → hostname: `sonarr`, port: `8989`
    - Radarr → hostname: `radarr`, port: `7878`
    - Radarr4K → hostname: `radarr4k`, port: `7878` (internal port — not 7070)
    - Plex → hostname: `plex`, port: `32400`
  - **Manual fix:** Seerr UI → Settings → Services (Sonarr, Radarr) and Settings → Plex

---

### 🔵 Info

- [ ] **No healthcheck defined**
  - **Why it matters:** If Seerr's Node.js process hangs, Docker keeps the container "Up" while the web UI and request API are dead. A healthcheck detects this and triggers a restart.
  - **Source:** [hotio/seerr image](https://hotio.dev/containers/overseerr/) — no built-in healthcheck
  - **Current:** `Health=null` confirmed via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:5055/api/v1/status"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [ ] **No memory limit**
  - **Why it matters:** Seerr (Overseerr) is a Node.js app — typical usage is 150–300 MB but it can spike during full library scans. Low practical risk on 62 GB.
  - **Current:** `Memory: 0`
  - **Recommended:** `mem_limit: 512m`

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Sonarr queue error | Manual fix — hostname changed from `192.168.1.33` to `sonarr` in Seerr UI | — | ✅ No more queue errors in logs post-restart |
| Service hostnames using host IP | Manual fix — Sonarr, Radarr, Radarr4K, Plex updated to container names in Seerr UI | — | ✅ Confirmed via logs |
| No healthcheck | Applied via compose | 04b3101 | ✅ `Health=healthy` |
| No memory limit | Applied via compose — `mem_limit: 512m` | 04b3101 | ✅ `Mem=536870912` |

---

## What's working well

- ✅ Container running (started 2026-06-11 08:02, clean startup)
- ✅ Plex connected — 3 libraries syncing: BKLYN_4K, BKLYN_Movies, BKLYN_TV ✅
- ✅ Radarr + Radarr4K both connected and reporting download progress ✅
- ✅ 4K detection active — `At least one 4K Radarr server was detected` ✅
- ✅ Plex Recently Added Scan running on schedule ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID: 1000 / PGID: 1000` set ✅
- ✅ Sonarr API key is correct (`52bfa27c...`) — connectivity issue only, not auth ✅
