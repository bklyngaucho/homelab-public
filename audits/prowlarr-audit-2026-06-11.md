# Services Best Practice Audit — Prowlarr + FlareSolverr
2026-06-11

## Summary
3 findings: 0 🔴 critical · 2 🟡 warning · 1 🔵 info

---

## Prowlarr

### 🟡 Warning

- [ ] **No healthcheck defined**
  - **Why it matters:** If Prowlarr's web process hangs, Sonarr/Radarr/Radarr4K will silently fail all indexer searches — no releases get found, nothing gets grabbed. The ARR apps log "no results" rather than a connection error, so the failure isn't obvious until you notice nothing is being downloaded. A healthcheck catches the hang and triggers a restart.
  - **Source:** [linuxserver.io — prowlarr image](https://docs.linuxserver.io/images/docker-prowlarr/) — no built-in healthcheck
  - **Current:** No `healthcheck` block in compose; confirmed `null` via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:9696/ping"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

---

### 🔵 Info

- [ ] **No memory limit**
  - **Why it matters:** Prowlarr is lightweight (~100–200 MB typical), so the practical risk is low. Consistent with the `mem_limit: 1g` applied to Sonarr and both Radarr instances.
  - **Current:** `Memory: 0`
  - **Recommended:** `mem_limit: 512m` — Prowlarr is lighter than the ARR apps; 512 MB is a generous ceiling

---

## FlareSolverr

### 🟡 Warning

- [ ] **No memory limit — Chromium without a ceiling**
  - **Why it matters:** FlareSolverr runs a headless Chromium instance to solve Cloudflare challenges. Chromium is a known memory hog and can consume 500 MB–2+ GB on complex pages. Without a ceiling, a stuck or looping solve could spike RAM and impact other containers on the NAS01's 62 GB.
  - **Source:** [FlareSolverr GitHub](https://github.com/FlareSolverr/FlareSolverr) — community reports of multi-GB RAM usage under load; `shm_size: 1gb` (already set) helps with shared memory but doesn't cap total RAM
  - **Current:** `Memory: 0` (no limit), `ShmSize: 1 GB` (already configured ✅)
  - **Recommended:** `mem_limit: 1g` — caps total memory at 1 GB; combined with the existing 1 GB shm_size this gives Chromium plenty of headroom while preventing runaway growth

---

## What's working well

- ✅ 3 indexers active: EZTV, The Pirate Bay, YTS — all enabled, no errors
- ✅ All 3 ARR apps synced at `fullSync` level: Radarr, Radarr4K, Sonarr
- ✅ All app URLs use container names (`http://prowlarr:9696`, `http://radarr:7878`, `http://sonarr:8989`) — not host IPs
- ✅ Clean logs — active RSS searches, no errors, housekeeping running normally
- ✅ FlareSolverr: `Health=healthy`, version 3.5.0, Chrome 148 ✅
- ✅ FlareSolverr: `shm_size: 1gb` set (prevents Chromium shared memory crashes) ✅
- ✅ FlareSolverr: `DISABLE_MEDIA=true` (reduces resource use by blocking media downloads in the headless browser) ✅
- ✅ FlareSolverr: `CAPTCHA_SOLVER=none` (correct — no paid solver needed for current indexers)
- ✅ `analyticsEnabled = False`, `updateMechanism = docker` on Prowlarr ✅
- ✅ `restart: unless-stopped` on both ✅

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Prowlarr: no healthcheck | Applied via compose | ea7f07f | ✅ `Health=healthy` |
| Prowlarr: no memory limit | Applied via compose — `mem_limit: 512m` | ea7f07f | ✅ `Mem=536870912` |
| FlareSolverr: no memory limit | Applied via compose — `mem_limit: 1g` | ea7f07f | ✅ `Mem=1073741824` |
