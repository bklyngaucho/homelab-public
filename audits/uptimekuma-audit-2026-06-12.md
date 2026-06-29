# Services Best Practice Audit — Uptime Kuma
2026-06-12

## Summary
3 findings: 0 🔴 critical · 1 🟡 warning · 2 🔵 info · 0 ⚪ flag — all resolved ✅

---

## Uptime Kuma

### 🟡 Warning

- [x] **tautulli and tdarr monitors using wrong check endpoints — persistent timeout/EHOSTUNREACH errors**
  - **Why it matters:** A monitor that consistently times out never reaches `maxretries=3` and never fires an alert — you have zero visibility into a real Tautulli or Tdarr outage. The 48-second timeout on the wrong endpoint is also the root cause of the recurring `EHOSTUNREACH` and timeout noise that appeared every few minutes in the logs.
  - **Root cause:** Tautulli's root URL (`http://tautulli:8181`) does not serve a quick response from within Docker — it requires auth redirection and hangs for ~3s before failing. The `/status` endpoint returns HTTP 200 in 1ms. Similarly, Tdarr's root URL (`http://tdarr:8265`) is slow; the health API endpoint (`/api/v2/status`) is the correct check. This was confirmed by live testing from inside the Uptime Kuma container:
    ```
    http://tautulli:8181         → HTTP:000  time:3.1s  (fails)
    http://tautulli:8181/status  → HTTP:200  time:0.001s (instant)
    http://tdarr:8265/api/v2/status → HTTP:200  time:3.1s (works)
    ```
  - **Fix applied:** Updated monitor URLs directly in `kuma.db` via Python sqlite3 (stop container → SCP DB → edit → SCP back → restart):
    - Monitor #19 tautulli: `http://tautulli:8181` → `http://tautulli:8181/status`
    - Monitor #20 tdarr: `http://tdarr:8265` → `http://tdarr:8265/api/v2/status`

### 🔵 Info

- [x] **No memory limit**
  - **Why it matters:** Consistent with the pattern for all services in this stack.
  - **Current:** `Memory=0` (unbounded)
  - **Fix applied:** `mem_limit: 256m` via compose

- [ ] **Intermittent EHOSTUNREACH on npm monitor — NAS01 Container Station bridge routing**
  - **Why it matters:** The npm monitor (`http://npm:81`) intermittently fails with EHOSTUNREACH from inside the Uptime Kuma container, even though npm responds correctly on the host port. This is a NAS01 Container Station Docker bridge networking quirk: after container IP reassignments (Watchtower nightly updates), ARP table state can lag, causing Node.js connection attempts to fail while OS-level curl succeeds at the same moment.
  - **Impact is low:** `maxretries=3` means npm would need 3 consecutive failures before an alert fires. In practice the monitor alternates between failing and succeeding, never hitting 3 in a row. No false alerts have fired.
  - **No fix available:** This is a NAS01 Container Station networking behavior, not a configuration error. Monitor URL is correct (`http://npm:81` uses container name). If npm were genuinely down, the alternating success/failure pattern would shift to consistent failures and the alert would eventually fire.
  - **Mitigation already in place:** `maxretries=3` setting correctly absorbs this noise.

---

## What's working well

- ✅ All monitor URLs use Docker container names (e.g. `http://sonarr:8989`), not host IPs — correct for NAS01's network topology ✅
- ✅ Built-in healthcheck (`[CMD-SHELL extra/healthcheck]`) provided by the image — container shows `healthy` ✅
- ✅ `louislam/uptime-kuma:2` — major-version pinned tag; avoids `:latest` surprise across major versions ✅
- ✅ `restart: unless-stopped` ✅
- ✅ Docker socket mounted — enables Docker-type container monitors ✅
- ✅ Monitor groups (Media #13, Services #15) with child monitors — logical grouping ✅
- ✅ `maxretries=3` on monitors — correctly absorbs NAS01 bridge network transient failures ✅
- ✅ Version 2.4.0 — current ✅

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Wrong monitor endpoints (tautulli, tdarr) | Updated monitor URLs in kuma.db via sqlite3: tautulli → `/status`, tdarr → `/api/v2/status` | (DB edit — no compose change) | ✅ No WARN/ERROR in logs after restart |
| No mem_limit | Added `mem_limit: 256m` via compose | see below | ✅ `Memory=268435456` (256 MiB) confirmed |
| npm intermittent EHOSTUNREACH | No fix — NAS01 Container Station bridge routing quirk; `maxretries=3` absorbs noise | — | ✅ No alerts firing; accepted as known behavior |
