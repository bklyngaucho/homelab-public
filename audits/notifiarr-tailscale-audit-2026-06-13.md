# Services Best Practice Audit — Notifiarr + Tailscale
2026-06-13

## Summary
5 findings: 0 🔴 critical · 1 🟡 warning · 3 🔵 info · 1 ⚪ flag

---

## Notifiarr

✅ **No findings.** Notifiarr's compose definition is clean across all check categories.

| Check | Result |
|---|---|
| Healthcheck | ✅ Present (`wget -qO- http://localhost:5454/`) |
| mem_limit | ✅ 256m — reasonable for this service |
| Port binding | ✅ LAN-only (`192.168.1.33:5454:5454`) |
| Secrets | ✅ `DN_API_KEY` via `${NOTIFIARR_API_KEY}` — never hardcoded |
| Config volume | ✅ `${APPDATA_PATH}/notifiarr:/config` |
| Restart policy | ✅ `unless-stopped` |
| Image tag | ✅ `:latest` is expected for golift images; Watchtower handles updates nightly |
| PUID/PGID | ✅ Not needed — golift images don't use the linuxserver uid/gid pattern |
| Live state | ✅ Up 3 hours (healthy) — clean logs, actively polling ARR apps and Plex |

---

## Tailscale

### 🟡 Warning

- [ ] **Subnet routing will silently fail without kernel networking + host network mode**
  - **Why it matters:** The whole point of running Tailscale here is subnet routing — remote access to the full 192.168.1.0/24 from anywhere. Two defaults are working against that goal:
    1. `TS_USERSPACE` defaults to `true` (userspace/SOCKS5 networking). With userspace networking, Tailscale can reach the container itself but can't forward packets to other LAN hosts. Kernel networking (`TS_USERSPACE=false`) is required for the OS-level packet forwarding that subnet routing depends on.
    2. Without `network_mode: host`, the container sits on Docker's bridge network. Even with kernel networking enabled, packets routed to 192.168.1.31 (TrueNAS), 192.168.1.1 (UniFi), or any non-NAS01 host arrive at the bridge and have nowhere to go. Host networking makes the container share the NAS01's network stack so Tailscale can route to any device the NAS01 can reach.
  - **Note:** The prerequisites for kernel networking are already in the compose definition (`CAP_NET_ADMIN`, `CAP_SYS_MODULE`, `/dev/net/tun`) — so `TS_USERSPACE=false` is safe to add without any other changes.
  - **Source:** [Tailscale Docker docs — TS_USERSPACE](https://tailscale.com/docs/features/containers/docker/docker-params#ts_userspace); [Subnet routers in Docker](https://tailscale.com/docs/features/subnet-routers)
  - **Current:** `TS_USERSPACE` unset (defaults to `true`); no `network_mode`
  - **Recommended:**
    ```yaml
    tailscale:
      network_mode: host        # shares NAS01 network stack — required for subnet routing
      environment:
        TS_USERSPACE: "false"   # kernel networking — prerequisites already present
        # remove TS_EXTRA_ARGS --advertise-routes; use TS_ROUTES instead (see 🔵 below)
        TS_ROUTES: "192.168.1.0/24"
        TS_AUTH_ONCE: "true"
        TS_ENABLE_HEALTH_CHECK: "true"
    ```

### 🔵 Info

- [ ] **`TS_AUTH_ONCE` not set — re-authenticates on every restart**
  - **Why it matters:** Without `TS_AUTH_ONCE=true`, Tailscale attempts a full authentication handshake every time the container starts. This works fine as long as the authkey is valid, but if the key expires or is rotated, the container won't come back up after a Watchtower update. State is already persisted via volume, so authentication should only happen once.
  - **Source:** [Tailscale Docker params — TS_AUTH_ONCE](https://tailscale.com/docs/features/containers/docker/docker-params#ts_auth_once)
  - **Current:** Not set
  - **Recommended:** `TS_AUTH_ONCE: "true"`

- [ ] **Use `TS_ROUTES` instead of `--advertise-routes` in `TS_EXTRA_ARGS`**
  - **Why it matters:** `TS_ROUTES` is the official first-class env var for advertising subnet routes (as of the current Tailscale Docker image). Using `TS_EXTRA_ARGS` works but couples the config to CLI flag syntax, which can break if the flag name changes. `TS_ROUTES` is stable and documented.
  - **Source:** [Tailscale Docker params — TS_ROUTES](https://tailscale.com/docs/features/containers/docker/docker-params#ts_routes)
  - **Current:** `TS_EXTRA_ARGS: "--advertise-routes=192.168.1.0/24 --accept-dns=false"`
  - **Recommended:** Split into `TS_ROUTES: "192.168.1.0/24"` and `TS_ACCEPT_DNS: "false"` as separate env vars; remove `TS_EXTRA_ARGS` entirely (or keep only if there are other flags to pass)

- [ ] **No healthcheck — VPN drop goes undetected**
  - **Why it matters:** If the Tailscale tunnel drops (network issue, control plane unreachable), Docker has no way to know. The container stays `running` even though VPN access is gone. Since Tailscale v1.78, a built-in `/healthz` endpoint is available with no external dependencies.
  - **Source:** [Tailscale Docker params — TS_ENABLE_HEALTH_CHECK](https://tailscale.com/docs/features/containers/docker/docker-params#ts_enable_health_check)
  - **Current:** No healthcheck defined
  - **Recommended:**
    ```yaml
    environment:
      TS_ENABLE_HEALTH_CHECK: "true"
      TS_LOCAL_ADDR_PORT: "127.0.0.1:9002"   # or leave default [::]:9002
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:9002/healthz"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

### ⚪ Flag — Needs manual review

- [ ] **Subnet routing approval is still pending at the Tailscale admin console**
  - **Why:** Advertising a route via `TS_ROUTES` (or `--advertise-routes`) is only half the job. The route won't actually be usable by other tailnet clients until it's approved in the admin console. Current Tailscale status shows `NAS01-homelab` connected with no active routes.
  - **Action required:** Go to [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) → find `NAS01-homelab` → `…` → **Edit route settings** → enable `192.168.1.0/24`.
  - **Note:** Apply the 🟡 fix above first, then approve — approving a userspace route that can't forward packets just makes it look broken.

---

## Recommended fix order

1. Apply the 🟡 compose changes (kernel networking + host network mode + `TS_AUTH_ONCE` + `TS_ROUTES` cleanup + healthcheck) — these are all one compose edit + redeploy.
2. Approve the subnet route at the Tailscale admin console (⚪).
3. Test from a remote device on the tailnet: ping 192.168.1.31 (TrueNAS) and verify it responds.

---

## Remediation Log
2026-06-13

### Tailscale

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Subnet routing silently failing (kernel networking + host mode) | Applied via compose — added `network_mode: host`, `TS_USERSPACE: "false"`, `TS_ROUTES`, `TS_AUTH_ONCE`, `TS_ENABLE_HEALTH_CHECK`, healthcheck endpoint | e05ba15 | ✅ Container healthy; `tailscale debug prefs` shows `AdvertiseRoutes: ["192.168.1.0/24"]`; route was already approved at admin console from initial setup |
| `TS_AUTH_ONCE` not set | Applied via compose (see above) | e05ba15 | ✅ `TS_AUTH_ONCE=true` confirmed in container env |
| Use `TS_ROUTES` instead of `TS_EXTRA_ARGS` | Applied via compose — removed `TS_EXTRA_ARGS`, added `TS_ROUTES` and `TS_ACCEPT_DNS` as discrete env vars | e05ba15 | ✅ |
| No healthcheck | Applied via compose — `TS_ENABLE_HEALTH_CHECK: "true"` + `TS_LOCAL_ADDR_PORT: "127.0.0.1:9002"` + wget healthcheck | e05ba15 | ✅ Container reports healthy |
| Subnet routing approval pending | No action needed — route was already approved at admin console from initial setup; appeared unrouted only because userspace networking was preventing packet forwarding | — | ✅ Route active after compose fix |

### Notifiarr

No compose findings. Two configuration issues discovered during post-audit debugging:

| Issue | Action | Verified |
|---|---|---|
| Plex URL set to `http://plex:32400` — Discord can't fetch artwork from internal URLs | Changed to `https://plex.yourdomain.com` in Notifiarr local client (Media Apps → Plex → URL) | ✅ Discord notifications now show album/poster art |
| Tautulli URL set to `http://tautulli.server.tv:8181` (placeholder default) | Changed to `http://tautulli:8181` in Notifiarr local client | ✅ |
| Sessions toggle ON — caused burst API calls exceeding free-tier rate limit (5 req/sec), silently dropping play notifications | Disabled Sessions on notifiarr.com Plex Integration Settings | ✅ Play notifications now reach Discord consistently; no new 429 errors |
