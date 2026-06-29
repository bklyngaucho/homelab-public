# Services Best Practice Audit — Sonarr
2026-06-09

## Summary
6 findings: 2 🔴 critical · 2 🟡 warning · 2 🔵 info · 0 ⚪ flag

---

## Sonarr

### 🔴 Critical

- [ ] **Stale qBittorrent download client pointing to `gluetun:8080`**
  - **Why it matters:** Sonarr has a second download client configured (qBittorrent at `gluetun:8080`) pointing to a container that doesn't exist in the stack. Every few minutes, `DownloadMonitoringService` tries to poll it for queue status and throws a `Connection refused` error. This means Sonarr's download queue monitoring is partially broken — it can't report the full picture of in-progress downloads, and the constant error noise makes real issues harder to spot.
  - **Source:** Live container logs (confirmed today — repeating every ~2 minutes)
  - **Current:** Second download client `qBittorrent` → `gluetun:8080` active in Settings → Download Clients (container `gluetun` does not exist in the stack)
  - **Recommended:** Remove the qBittorrent entry. Settings → Download Clients → click the trash icon on the qBittorrent client. This is a manual fix — navigate to `http://192.168.1.33:8989/settings/downloadclients`.

- [ ] **Hardlinks broken — media and downloads on separate NFS mounts**
  - **Why it matters:** Sonarr mounts `/storage/media_ds` and `/storage/downloads_ds` as two separate NFS volumes. Since they're different filesystems inside the container, hardlinks across them are impossible. Every completed download is **copied** then **deleted** instead of atomically moved. On a large TV library this means double NFS I/O during every import, files are temporarily duplicated (risking partial imports if interrupted), and import times are much longer than necessary.
  - **Source:** [TRaSH Guides — How to set up Docker](https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Docker/) · [Servarr Wiki — Docker Guide](https://wiki.servarr.com/docker-guide#consistent-and-well-planned-paths)
  - **Current:** `${MEDIA_DS}:/storage/media_ds` + `${DOWNLOADS_DS}:/storage/downloads_ds` (two separate NFS mounts = two separate filesystem roots)
  - **Recommended:** Mount a single top-level NFS share containing both `media` and `downloads` subdirectories, e.g. `${DATA_DS}:/storage/data`. Both folders then share a filesystem root and hardlinks work. Requires: (1) creating a combined share on TrueNAS, (2) updating the compose volume mounts for Sonarr, Radarr, Radarr4K, and TransmissionVPN, (3) adjusting root folder and download path settings inside each app.

---

### 🟡 Warning

- [ ] **No healthcheck defined**
  - **Why it matters:** Without a healthcheck, Docker's `restart: unless-stopped` only fires when the Sonarr process exits. If the web server hangs (which happens during heavy DB operations or after long RSS syncs), the container stays "Up" and Uptime Kuma shows it green — but it's silently dead. No automatic recovery happens.
  - **Source:** [linuxserver.io — sonarr image docs](https://docs.linuxserver.io/images/docker-sonarr/) · check-categories.md §3
  - **Current:** No `healthcheck` in compose; image ships none internally
  - **Recommended:** Add to the `sonarr` service in compose:
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8989/ping"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [ ] **Active indexer degradation — TPB disabled, EZTV timing out**
  - **Why it matters:** The health API is reporting The Pirate Bay disabled for >6 hours due to rate-limit failures. Logs also show EZTV timing out on searches. With only 3 indexers total (TPB, EZTV, YTS), losing two of them cuts Sonarr's search coverage significantly — missed episodes and failed searches become more likely.
  - **Source:** Live health API + container logs (confirmed today)
  - **Current:** TPB: `Indexer disabled till 06/09/2026 13:38:35 due to recent failures` · EZTV: `Http request timed out`
  - **Recommended:** In Prowlarr, lower TPB's priority or disable it temporarily. Consider adding a more reliable public tracker (e.g. 1337x, TorrentLeech). EZTV timeouts are usually transient — check again in a few hours. If persistent, test the indexer manually in Prowlarr.

---

### 🔵 Info

- [ ] **No `depends_on: prowlarr` declared**
  - **Why it matters:** On a stack restart, Docker starts services in parallel. Sonarr may boot and attempt indexer syncs before Prowlarr is ready, causing silent failures during the startup window.
  - **Source:** [Servarr Wiki — Docker Guide](https://wiki.servarr.com/docker-guide)
  - **Current:** No `depends_on` block in the sonarr service
  - **Recommended:** Add `depends_on: [prowlarr]` to the sonarr service definition. Once Prowlarr has a healthcheck (see ARR stack audit), upgrade to `condition: service_healthy`.

- [ ] **No memory or CPU limits**
  - **Why it matters:** Sonarr is currently using 205 MB — well within budget. But during a full library rescan or DB vacuum it can spike higher. Without limits, a runaway Sonarr process could starve the other 19 containers on the NAS01.
  - **Source:** check-categories.md §4 Resource Limits
  - **Current:** `Memory: 0`, `NanoCpus: 0` (unlimited)
  - **Recommended:** Add `mem_limit: 1g` to the sonarr service definition. Conservative ceiling that still gives plenty of headroom above the 205 MB baseline.

---

## What's working well

- ✅ Download client: `transmissionvpn:9091` — using container-name URL, correct port, category `tv` set
- ✅ Root folder: `/storage/media_ds/tv` — accessible, 19 TB free
- ✅ Network: on `homelab` bridge, DNS aliases correct
- ✅ Auth: Forms-based, disabled for local addresses (standard homelab posture)
- ✅ UpdateMechanism: Docker — won't try to self-update inside the container
- ✅ Analytics: disabled
- ✅ Image: `lscr.io/linuxserver/sonarr:latest` — correct source, Watchtower keeps it current
- ✅ Appdata backed up: `/share/appdata/sonarr` is in Duplicati scope

---

## Remediation Log
2026-06-09

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Stale qBittorrent client (gluetun:8080) | No fix needed — historical log noise from a previously deleted client; 0 errors after container restart | — | ✅ Confirmed 0 gluetun errors post-restart |
| Hardlinks broken (separate NFS mounts) | Deferred — requires TrueNAS export change + path updates across 4 services | — | ⏳ Pending |
| No healthcheck | Applied via compose | f57d0df | ✅ Container shows `healthy`, polling `/ping` every 60s |
| No memory limit | Applied via compose | f57d0df | ✅ 1 GB limit confirmed via `docker inspect` |
| No `depends_on: prowlarr` | Applied via compose | f57d0df | ✅ Prowlarr started before Sonarr on recreate |
| Active indexer degradation (TPB/EZTV) | Skipped — transient issue, monitor in Prowlarr | — | — |
