# Services Best Practice Audit — Watchtower
2026-06-12

## Summary
4 findings: 0 🔴 critical · 1 🟡 warning · 2 🔵 info · 0 ⚪ flag — 3 resolved, 1 dismissed ✅

---

## Watchtower

### 🟡 Warning

- [ ] **SMTP notification timed out — nightly update report not delivered**
  - **Why it matters:** Watchtower is your only visibility into what updated overnight. If notifications are silently failing, you won't know when containers change versions, which matters most when a breaking update gets pulled.
  - **Source:** Live logs — `level=error msg="Failed to send shoutrrr notification" error="failed to send: timed out: using smtp" ... url="smtp://smtp.gmail.com:587"` at 2026-06-12 04:02 AM. `auth_failures=0` — this is a connection timeout, not a credentials issue. The NAS01 couldn't reach `smtp.gmail.com:587` at all.
  - **Current:** `WATCHTOWER_NOTIFICATIONS: shoutrrr` + `WATCHTOWER_NOTIFICATION_URL: smtp://...@smtp.gmail.com:587/...` → timed out, 0 successes, 1 failure.
  - **How to diagnose:** From the NAS01, test outbound SMTP connectivity: `ssh admin@192.168.1.33 'nc -zv smtp.gmail.com 587'`. If that times out, the NAS01's outbound SMTP is being blocked (ISP, UniFi firewall rule, or Gmail rate-limiting). If it connects, the issue is the shoutrrr URL format or Gmail credentials. Also check whether previous nights' notifications went through — if this is the first failure, it may be a transient network blip.
  - **Fix options:** (a) Test connectivity and fix if blocked. (b) Switch to a more reliable shoutrrr transport (e.g. Discord webhook, Gotify, ntfy) — these use HTTPS on port 443 which is never blocked.

- [ ] **Watchtower self-update wipes restart policy — container won't auto-start if Docker daemon restarts**
  - **Why it matters:** At 4:01 AM today Watchtower updated itself and replaced its own container. The new container has `RestartPolicy=no` (confirmed via `docker inspect`). If the Docker daemon restarts without a full NAS01 reboot — for example after a Container Station update — Watchtower won't come back up automatically. All other containers will keep running, but Watchtower won't be there to update them.
  - **Source:** `docker inspect watchtower --format "RestartPolicy={{.HostConfig.RestartPolicy.Name}}"` → `no`. Compose specifies `restart: unless-stopped`, but the self-updated container doesn't inherit it.
  - **Current:** Running container has `RestartPolicy=no`. Container Station re-deploys from compose on full stack restarts, which would restore it — but not on daemon-only restarts.
  - **Recommended:** Add `WATCHTOWER_DISABLE_CONTAINERS: watchtower` to the Watchtower environment. This tells Watchtower to skip updating itself. Watchtower's own image stays pinned to `:latest` and gets updated when you next redeploy the stack via Container Station (which also correctly applies the restart policy). This is the standard self-hosted recommendation.
    ```yaml
    environment:
      WATCHTOWER_DISABLE_CONTAINERS: watchtower
    ```

### 🔵 Info

- [ ] **Using unofficial fork image (`nickfedor/watchtower`) instead of canonical (`containrrr/watchtower`)**
  - **Why it matters:** The canonical Watchtower project is maintained at `containrrr/watchtower`. The `nickfedor/watchtower` fork (by Nicholas Fedor) is actively maintained with its own docs at `watchtower.nickfedor.com`, CI, and 1M+ pulls — it's not abandoned. But it's a single-maintainer divergence from the upstream project. Over time it may drift in behavior, miss upstream security fixes, or go quiet.
  - **Source:** [containrrr/watchtower](https://containrrr.dev/watchtower/) is the canonical project. [nickfedor/watchtower](https://hub.docker.com/r/nickfedor/watchtower) is an actively maintained fork — last updated ~1 month ago, running v1.18.1.
  - **Current:** `image: nickfedor/watchtower:latest`
  - **Recommended:** `image: containrrr/watchtower:latest` — functionally equivalent, same environment variables, directly maintained by the original project. Low-risk swap.

- [ ] **No memory limit**
  - **Why it matters:** Watchtower is very lightweight in normal operation (~30–50 MB), but during its nightly run it pulls new images for all 20 containers. Peak memory during a run with many simultaneous pulls could be higher. Consistent with the pattern for other services in this stack.
  - **Current:** `Memory=0` (unbounded)
  - **Recommended:** `mem_limit: 256m` — generous headroom for image pulls with no practical risk of hitting it.

---

## What's working well

- ✅ `WATCHTOWER_CLEANUP: "true"` — old images removed after updates, no disk accumulation ✅
- ✅ Schedule `0 0 4 * * *` — runs at 4:00 AM, safely after the 2 AM Duplicati backup ✅
- ✅ Built-in healthcheck (`/watchtower --health-check`) — container shows `healthy` ✅
- ✅ `WATCHTOWER_INCLUDE_STOPPED: "false"` — won't attempt to update stopped containers ✅
- ✅ `WATCHTOWER_NOTIFICATION_REPORT: "true"` — sends consolidated report rather than per-container noise ✅
- ✅ `WATCHTOWER_NOTIFICATIONS_LEVEL: info` — appropriate verbosity ✅
- ✅ `restart: unless-stopped` in compose (applied correctly on stack deploy) ✅
- ✅ Docker socket mounted correctly for container management ✅

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| SMTP notification timed out | Dismissed — user confirmed email received at 4:01 AM. Failure was startup notification from newly self-updated container, not the nightly report. Transient race on network init. | — | ✅ Not a real issue |
| Self-update wipes restart policy | Added `WATCHTOWER_DISABLE_CONTAINERS: watchtower` via compose | 6019819 | ✅ `RestartPolicy=unless-stopped` confirmed; logs show "Only checking containers not named one of 'watchtower'" |
| Non-canonical image | Changed `nickfedor/watchtower` → `containrrr/watchtower` via compose | 6019819 | ✅ `Image=containrrr/watchtower:latest` confirmed |
| No mem_limit | Added `mem_limit: 256m` via compose | 6019819 | ✅ `Memory=268435456` (256 MiB) confirmed |
