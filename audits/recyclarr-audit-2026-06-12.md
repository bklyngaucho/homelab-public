# Services Best Practice Audit — Recyclarr
2026-06-12

## Summary
1 finding: 0 🔴 critical · 0 🟡 warning · 1 🔵 info · 0 ⚪ flag — all resolved ✅

---

## Recyclarr

### 🔵 Info

- [x] **No memory limit**
  - **Why it matters:** Recyclarr's daemon process runs continuously between its `@daily` cron invocations, then spikes briefly during a sync run when it fetches TRaSH Guide data and pushes quality profiles to Sonarr/Radarr. Live idle usage is only **6.7 MiB** — among the lightest containers in the stack — but consistent with the pattern applied to all services.
  - **Current:** `Memory=0` (unbounded); live usage 6.7 MiB / 62.72 GiB
  - **Fix applied:** `mem_limit: 256m`

---

## What's working well

- ✅ Runs as a persistent daemon with an internal `@daily` scheduler — correct for this image; no external cron needed ✅
- ✅ Last sync succeeded: `level=info msg="job succeeded" iteration=6 job.schedule=@daily` ✅
- ✅ All three ARR API keys sourced from env vars (`SONARR_API_KEY`, `RADARR_API_KEY`, `RADARR4K_API_KEY`) — not hardcoded in `recyclarr.yml` (uses `!env_var` YAML tags per CLAUDE.md) ✅
- ✅ `restart: unless-stopped` ✅
- ✅ Config volume at `${APPDATA_PATH}/recyclarr:/config` — config persists through updates ✅
- ✅ No ports exposed — correct, Recyclarr has no web UI ✅
- ✅ `ghcr.io/recyclarr/recyclarr:latest` — official image ✅

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| No mem_limit | Added `mem_limit: 256m` via compose | see below | ✅ |
