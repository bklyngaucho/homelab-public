# Services Best Practice Audit — Agregarr
2026-06-12

## Summary
3 findings: 0 🔴 critical · 0 🟡 warning · 3 🔵 info · 0 ⚪ flag — all resolved ✅

---

## Agregarr

### 🔵 Info

- [x] **Port 7171 bound to all interfaces — should be LAN-only**
  - **Why it matters:** Port 7171 is the Agregarr web UI — a dashboard/management console for Plex collections and overlays. There's no reason for it to be reachable beyond the LAN. Binding to `192.168.1.33` only is consistent with the pattern applied to all management UIs in this stack (NPM :81, Technitium :5380, etc.).
  - **Current:** `"7171/tcp":[{"HostIp":"","HostPort":"7171"}]` — all interfaces
  - **Fix applied:** Changed to `192.168.1.33:7171:7171` via compose

- [x] **No healthcheck**
  - **Why it matters:** Without a healthcheck, Docker only restarts Agregarr on process exit. If the Node.js process hangs (common in Next.js apps under memory pressure or connection pool exhaustion), the container stays "Up" while actually serving nothing.
  - **Verified:** Port 7171 responds with HTTP 307 (redirect to login) — server is up and routing correctly.
  - **Tool availability:** No curl in image; `wget` available at `/usr/bin/wget`. wget follows the 307 redirect to the login page (HTTP 200) and exits 0 on success.
  - **Fix applied:**
    ```yaml
    healthcheck:
      test: ["CMD", "wget", "-qO/dev/null", "http://localhost:7171"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [x] **No memory limit**
  - **Why it matters:** Agregarr is a Next.js application running collection/overlay sync jobs against Plex. Live usage is **192.5 MiB** at idle with sync jobs running. Consistent with the pattern for all services in this stack.
  - **Current:** `Memory=0` (unbounded); live usage 192.5 MiB / 62.72 GiB
  - **Fix applied:** `mem_limit: 512m`

---

## What's working well

- ✅ Running cleanly — collection sync completing successfully every 30 minutes ✅
- ✅ Auth 401 errors in logs (`cookie 'agregarr.sid' required`) are normal — health checks or browser pre-flight requests hitting the API without a session cookie; expected behavior ✅
- ✅ `restart: unless-stopped` ✅
- ✅ Config volume at `${APPDATA_PATH}/agregarr:/app/config` ✅
- ✅ Connecting to Plex libraries correctly (BKLYN_4K, BKLYN_Movies, BKLYN_TV) ✅
- ✅ Large page data warning (284 kB) is a Next.js build-time advisory, not a runtime problem ✅

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Port 7171 on all interfaces | Changed to `192.168.1.33:7171:7171` via compose | see below | ✅ |
| No healthcheck | Added `wget -qO/dev/null http://localhost:7171` via compose | see below | ✅ |
| No mem_limit | Added `mem_limit: 512m` via compose | see below | ✅ |
