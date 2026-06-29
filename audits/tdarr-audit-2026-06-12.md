# Services Best Practice Audit — Tdarr
2026-06-12

## Summary
4 findings: 0 🔴 critical · 0 🟡 warning · 3 🔵 info · 0 ⚪ flag — all resolved ✅

---

## Tdarr

### 🔵 Info

- [ ] **No healthcheck defined**
  - **Why it matters:** If the Tdarr web process hangs, Docker keeps the container listed as "Up" while the UI and API are unresponsive and no transcoding jobs will run.
  - **Source:** Tdarr image has no built-in healthcheck. `/api/v2/status` returns HTTP 200 when the server is healthy (confirmed via exec test).
  - **Current:** `Health=null` confirmed via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8265/api/v2/status"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 60s
    ```

- [ ] **No memory limit**
  - **Why it matters:** Tdarr maintains a 1.8 GB server database for 9,700+ tracked files and grows in memory during active transcoding and library scans. Leaving it unbounded on a shared host risks starving other containers.
  - **Current:** `Memory=0`; server DB on disk is 1.8 GB
  - **Recommended:** `mem_limit: 4g` — headroom for active jobs and DB operations without risking host memory pressure.

- [ ] **`serverIP` set to host IP — internal node traffic routes through host network unnecessarily**
  - **Why it matters:** The internal node connects to the Tdarr server at `192.168.1.33:8266`, which routes container → Docker bridge → NAS01 host NIC → back into the container via the published port. Using `localhost` keeps the connection inside the container, eliminates the unnecessary round-trip, and avoids a dependency on the NAS01's LAN IP (which would break in a DR scenario on a different host).
  - **Source:** Tdarr docs — `serverIP` should be the address the node uses to reach the server; for an internal node in the same container, `localhost` is correct.
  - **Current:** `serverIP: 192.168.1.33`
  - **Recommended:** `serverIP: localhost`

### ✅ Resolved — HEVC → NVENC flow wiring fixed

- [x] **HEVC files were not being re-encoded to H.264 — flow edge `e_265_yes` wired to wrong target**
  - **Root cause:** The `checkVideoCodec` node for HEVC (id: `chk_265`) had its YES output (`sourceHandle: "1"`) wired to `chk_mkv` (the MKV container check) instead of `beg_c` (the NVENC transcode path). HEVC files were therefore treated identically to H.264 files — only getting AAC added, video untouched.
  - **Fix applied:** Changed `e_265_yes` target from `chk_mkv` → `beg_c`. HEVC now routes directly to: Begin FFmpeg → Set container MKV → **NVENC QP18 p5 encode** → check AAC → execute → replace original.
  - **Flow saved to:** `tdarr/flows/normalize-mkv-h264-aac-stereo.json` and re-imported into Tdarr UI.

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| No healthcheck | Applied via compose — `/api/v2/status` endpoint, `start_period: 60s` | e1519d9 | ✅ `Health=healthy` |
| No memory limit | Applied via compose — `mem_limit: 4g` | e1519d9 | ✅ `Mem=4294967296` |
| serverIP using host IP | Changed `serverIP: 192.168.1.33` → `serverIP: localhost` | e1519d9 | ✅ `Node NAS01-node connected:true` confirmed in logs |
| NVENC flow logic skipping HEVC | Root cause: `e_265_yes` edge wired to `chk_mkv` instead of `beg_c`. Fixed by changing target to `beg_c` — HEVC now routes to NVENC transcode path. Flow JSON saved to `tdarr/flows/` and re-imported into Tdarr UI. | 84a532d / see flow commit | ✅ Flow corrected and imported |

---

## What's working well

- ✅ All 4 NVIDIA devices present on host and passed through correctly (world-readable `crw-rw-rw-`) ✅
- ✅ NVIDIA driver libs mounted at `/usr/local/nvidia/lib` from NAS01's NVIDIA_GPU_DRV package ✅
- ✅ NVENC hardware confirmed working — direct container test: `ffmpeg -init_hw_device cuda=cu:0 -c:v h264_nvenc` encoded at **46.3× speed**; health check log shows `nvenc: version 13.0 is available` ✅
- ✅ Internal node connected — `Node NAS01-node connected:true` in logs ✅
- ✅ Libraries scanning correctly — 7,393 + 2,348 files across 2 libraries ✅
- ✅ Transcode scratch space (`/temp`) on local NAS01 NVMe storage — fast, not NFS ✅
- ✅ Media mounted read/write for in-place transcoding ✅
- ✅ Job history within limits — 1,281 MiB of 10,240 MiB ✅
- ✅ Node port 8267 correctly not published externally (internal node only — no external nodes) ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID: 1000 / PGID: 1000` set ✅
- ✅ Watchtower handles image updates — Tdarr's own Docker auto-updater log warning is expected and harmless ✅
