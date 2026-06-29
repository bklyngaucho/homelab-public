# Services Best Practice Audit — Radarr + Radarr4K
2026-06-11

## Summary
4 findings: 0 🔴 critical · 3 🟡 warning · 1 🔵 info

Applies to both `radarr` (port 7878) and `radarr4k` (port 7070) unless noted.

---

## Radarr / Radarr4K

### 🟡 Warning

- [ ] **No healthcheck defined** *(both instances)*
  - **Why it matters:** Radarr's web process can hang after a long RSS sync or database vacuum without exiting — Docker keeps the container "Up" and Uptime Kuma stays green while the UI and API are dead. A healthcheck detects this and triggers a restart automatically.
  - **Source:** [linuxserver.io — radarr image](https://docs.linuxserver.io/images/docker-radarr/) — no built-in healthcheck; must be defined in compose
  - **Current:** No `healthcheck` block on either service; confirmed `null` via inspect on both
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:7878/ping"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```
    Radarr4K uses port 7878 internally (mapped to 7070 on the host), so the healthcheck test URL is the same.

- [ ] **No `depends_on: prowlarr`** *(both instances)*
  - **Why it matters:** If the stack restarts, Radarr can come up before Prowlarr is ready. Indexer syncs during that window fail silently — Radarr logs "no results" rather than a connection error, so the problem isn't obvious. We added this fix to Sonarr in the last audit; Radarr should match.
  - **Source:** Docker Compose docs — `depends_on` for startup ordering; applied to Sonarr in commit `f57d0df`
  - **Current:** No `depends_on` on either radarr or radarr4k in compose
  - **Recommended:**
    ```yaml
    depends_on:
      - prowlarr
    ```

- [ ] **No recycle bin configured — accidental deletions are permanent** *(both instances)*
  - **Why it matters:** With `recycleBin` empty, if you remove a movie from Radarr and check "Delete Files", the file is gone immediately with no recovery window. A recycle bin stages deleted files for 7 days (your configured `recycleBinCleanupDays`) before permanent removal — enough time to catch a mistake.
  - **Source:** [TRaSH Guides — Radarr tips](https://trash-guides.info/Radarr/) — recycle bin is a recommended safety net
  - **Current:** `recycleBin = ""` (confirmed via API on both instances); `recycleBinCleanupDays = 7` is already set, just waiting for a path
  - **Recommended:** Set via Radarr UI → Settings → Media Management → Recycle Bin:
    - Radarr: `/storage/media_ds/recyclebin`
    - Radarr4K: `/storage/media_ds/recyclebin` (same path is fine — subdirectory per movie anyway)
    The path sits on the NAS02 NFS share so it persists independently of the NAS01.

---

### 🔵 Info

- [ ] **No memory limit** *(both instances)*
  - **Why it matters:** No ceiling on RAM usage. In practice Radarr is lightweight (~200–400 MB), but during large library scans it can spike. The NAS01 has 62 GB so this is low urgency.
  - **Source:** Docker best practices — resource limits as a safety rail
  - **Current:** `Memory: 0, NanoCpus: 0` on both containers
  - **Recommended:** `mem_limit: 1g` on both — same value applied to Sonarr

---

## What's working well

- ✅ Both containers up and healthy (41 hours uptime, clean logs)
- ✅ RSS sync active on both — processing 100+ releases per cycle
- ✅ Download client: `transmissionvpn:9091` via container name (not host IP) on both ✅
- ✅ Root folders accessible: `/storage/media_ds/movies` (19.5 TB free) and `/storage/media_ds/4k` ✅
- ✅ `copyUsingHardlinks = True` set (Radarr attempts hardlinks; falls back gracefully to copy+delete across NFS mounts)
- ✅ `updateMechanism = docker` — Watchtower handles image updates correctly
- ✅ `analyticsEnabled = False` on both
- ✅ `restart: unless-stopped` on both
- ✅ Indexers synced from Prowlarr (TPB + YTS visible on Radarr; Radarr4K synced separately)
- ✅ No errors in logs — "Movie folder does not exist" lines are normal (monitored/wanted movies not yet downloaded)

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| No healthcheck | Applied via compose (both instances) | c2927fa | ✅ `Health=healthy` on both |
| No `depends_on: prowlarr` | Applied via compose (both instances) | c2927fa | ✅ Prowlarr confirmed Running before recreate |
| No memory limit | Applied via compose (both instances) | c2927fa | ✅ `Mem=1073741824` (1 GB) on both |
| No recycle bin configured | Directory created on NFS; path set in both UIs | — | ✅ `/storage/media_ds/recyclebin` configured on both instances |

## Manual Follow-up Steps

- [ ] **Set recycle bin path**
  - Radarr: http://192.168.1.33:7878 → Settings → Media Management → Recycle Bin → `/storage/media_ds/recyclebin`
  - Radarr4K: http://192.168.1.33:7070 → Settings → Media Management → Recycle Bin → `/storage/media_ds/recyclebin`
