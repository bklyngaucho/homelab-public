# Services Best Practice Audit — Bazarr
2026-06-11

## Summary
5 findings: 1 🔴 critical · 2 🟡 warning · 2 🔵 info

---

## Bazarr

### 🔴 Critical

- [ ] **Wrong IP for Sonarr and Radarr — subtitle downloading is completely broken**
  - **Why it matters:** Bazarr polls Sonarr and Radarr to discover new media and know where files live. With the wrong IP, it can't reach either service — no new movies or episodes are ever synced, and no subtitles are downloaded. The live status confirms this: `sonarr_version: "unknown"`, `radarr_version: "unknown"`. The logs show continuous Connection Errors every hour going back days.
  - **Source:** Bazarr logs (live, recurring every 60 min): `ERROR (rootfolder:24) - BAZARR Error trying to get rootfolder from Sonarr. Connection Error.` — confirmed ongoing as of 2026-06-11 20:59
  - **Current:** `sonarr.ip: 192.168.1.5` and `radarr.ip: 192.168.1.5` in config.yaml — this IP does not exist on the network (NAS01 is `.33`, TrueNAS is `.31`, router is `.1`)
  - **Recommended:** Change both IPs to the container name so Bazarr communicates within the Docker network:
    - Settings → Sonarr: IP field → `sonarr` (or `192.168.1.33` + port 8989)
    - Settings → Radarr: IP field → `radarr` (or `192.168.1.33` + port 7878)
    - Container names are preferred since they keep traffic on the Docker network and don't depend on the host IP
  - **Manual fix:** Bazarr UI → Settings → Sonarr and Settings → Radarr

---

### 🟡 Warning

- [ ] **No healthcheck defined**
  - **Why it matters:** Bazarr's web process can hang without the container dying — Docker keeps it listed as "Up" while it's actually unresponsive. Given that Bazarr is already silently failing (see above), having a healthcheck would at least give Docker (and Uptime Kuma) visibility into actual process health.
  - **Source:** [linuxserver.io — bazarr image](https://docs.linuxserver.io/images/docker-bazarr/) — no built-in healthcheck
  - **Current:** No `healthcheck` block in compose; confirmed `null` via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:6767/"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [ ] **Radarr4K not covered — 4K movies get no subtitles**
  - **Why it matters:** Bazarr only supports a single Radarr instance ([upstream limitation — bazarr#404](https://github.com/morpheus65535/bazarr/issues/404)). With only `radarr` (7878) wired up, Bazarr has no visibility into the Radarr4K library at `/storage/media_ds/4k`. Those movies will never receive downloaded subtitles.
  - **Source:** [bazarr/issues/404](https://github.com/morpheus65535/bazarr/issues/404) — multiple Radarr instances not supported
  - **Current:** Single Radarr instance only; no workaround within Bazarr itself
  - **Workaround options:** (a) Run a second Bazarr container wired to Radarr4K — adds maintenance overhead; (b) Accept that 4K releases typically include English SDH subtitles embedded and rely on `use_embedded_subs: true` (already set ✅); (c) No action if 4K content is watched without external subs
  - **Recommended:** No action unless embedded subs prove insufficient — the operational cost of a second Bazarr instance likely outweighs the benefit for a homelab

---

### 🔵 Info

- [ ] **No memory limit**
  - **Why it matters:** No ceiling on RAM usage. Bazarr is typically lightweight (~100–200 MB), but subtitle searches and database operations can spike. Low practical risk on the NAS01's 62 GB.
  - **Current:** `Memory: 0`
  - **Recommended:** `mem_limit: 512m` — conservative ceiling consistent with Prowlarr

- [ ] **`auto_update: true` may conflict with Watchtower**
  - **Why it matters:** Bazarr's `auto_update` config flag tells the application to check for and apply its own in-process updates. Watchtower already handles image-level updates nightly. For linuxserver.io images the two approaches can step on each other: the container startup script pins a specific Bazarr version in the image, while `auto_update` tries to upgrade past it at runtime. This can produce a "works until the next image pull" scenario where a Watchtower update silently rolls back the in-process upgrade.
  - **Source:** [linuxserver.io — bazarr image notes](https://docs.linuxserver.io/images/docker-bazarr/) — image manages Bazarr version; `auto_update` intended for bare-metal installs
  - **Current:** `general.auto_update: true` in config.yaml
  - **Recommended:** Disable in Bazarr UI → Settings → General → "Update Bazarr Automatically" → Off. Let Watchtower handle it via image pulls.
  - **Manual fix:** Bazarr UI → Settings → General

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Wrong IP for Sonarr + Radarr | Manual fix — updated IPs to container names in Bazarr UI | — | ✅ `sonarr_version: 4.0.17.2952`, `radarr_version: 6.2.1.10461` via API |
| No healthcheck | Applied via compose | 96f68f2 | ✅ `Health=healthy` |
| Radarr4K not covered | No action — upstream limitation, single Radarr instance only ([bazarr#404](https://github.com/morpheus65535/bazarr/issues/404)); 4K content relies on embedded subs | — | — |
| No memory limit | Applied via compose — `mem_limit: 512m` | 96f68f2 | ✅ `Mem=536870912` |
| `auto_update: true` | Manual fix — user disabling in Bazarr UI → Settings → General | — | ⏳ Pending user action |

---

## Manual Follow-up Steps

- [ ] **Fix wrong Sonarr IP**
  Navigate to: http://192.168.1.33:6767 → Settings → Sonarr
  Change: IP field from `192.168.1.5` → `sonarr` — then click Test + Save

- [ ] **Fix wrong Radarr IP**
  Navigate to: http://192.168.1.33:6767 → Settings → Radarr
  Change: IP field from `192.168.1.5` → `radarr` — then click Test + Save

- [ ] **Disable auto_update**
  Navigate to: http://192.168.1.33:6767 → Settings → General
  Change: "Update Bazarr Automatically" → Off — then Save

---

## What's working well

- ✅ Container running (6 days uptime since 2026-06-05)
- ✅ `analytics.enabled: false` ✅
- ✅ 5 subtitle providers configured: yifysubtitles, supersubtitles, tvsubtitles, wizdom, opensubtitlescom ✅
- ✅ OpenSubtitlescom credentials configured (`yourusername`) ✅
- ✅ `use_embedded_subs: true` — checks for embedded tracks before downloading (avoids redundant subs) ✅
- ✅ `upgrade_subs: true` — replaces lower-quality subs if a better match appears later ✅
- ✅ `minimum_score: 90` (series) / `minimum_score_movie: 70` — reasonable quality floor ✅
- ✅ Volume mount `/storage/media_ds` matches Sonarr/Radarr conventions — no path mappings needed ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID: 1000 / PGID: 1000` consistent with stack ✅
- ✅ `path_mappings: []` / `path_mappings_movie: []` — correct, no cross-host path translation needed in Docker ✅
- ✅ No auth on Bazarr UI (`auth.type: null`) — intentional for LAN-only access ✅
