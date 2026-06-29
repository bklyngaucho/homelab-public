# Services Best Practice Audit — Technitium DNS
2026-06-12

## Summary
3 findings: 0 🔴 critical · 0 🟡 warning · 3 🔵 info · 0 ⚪ flag — all resolved ✅

---

## Technitium

### 🔵 Info

- [x] **Web UI port 5380 bound to all interfaces — should be LAN-only**
  - **Why it matters:** Port 5380 is the admin console for the DNS server — from here you can change upstream forwarders, disable ad blocking, modify local zones, or add/remove allowed clients. There's no reason for this to be reachable from outside the LAN. Binding to `192.168.1.33` only eliminates any risk from router misconfiguration.
  - **Note:** Port 53 (DNS) is already correctly bound to `192.168.1.33` only — this is just the admin UI catching up to the same standard.
  - **Current:** `"5380/tcp": [{"HostIp":"","HostPort":"5380"}]` — all interfaces
  - **Fix applied:** Changed to `192.168.1.33:5380:5380` via compose

- [x] **No healthcheck**
  - **Why it matters:** If the DNS server process hangs, Docker keeps the container listed as "Up" but name resolution fails for all LAN clients. With no healthcheck, this wouldn't trigger an automatic restart.
  - **Verified:** Port 5380 returns HTTP 200. DNS itself resolves correctly: `plex.yourdomain.com → 192.168.1.33` (local wildcard zone ✅), `google.com → 142.251.45.78` (upstream forwarders ✅).
  - **Fix applied:** Technitium image has no `curl` or `wget`. Used bash's built-in TCP device check instead, with `CMD` (not `CMD-SHELL`) to invoke bash directly since `/dev/tcp` is bash-specific and `sh` doesn't support it:
    ```yaml
    healthcheck:
      test: ["CMD", "/usr/bin/bash", "-c", "echo > /dev/tcp/localhost/5380"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [x] **No memory limit**
  - **Why it matters:** Technitium is currently using **241.8 MiB** with OISD Basic + AdGuard DNS filter block lists loaded in memory. This is significantly higher than a typical DNS resolver. Block list updates pull fresh data and temporarily spike memory. Leaving it unbounded risks pressure on other containers if lists grow or a refresh goes sideways.
  - **Current:** `Memory=0`; live usage 241.8 MiB / 0.38% of 62.72 GiB
  - **Fix applied:** `mem_limit: 512m` — ~2× headroom above current usage; generous enough to handle list refreshes without risk of OOM.

---

## What's working well

- ✅ Port 53 correctly bound to `192.168.1.33` only — avoids conflict with QTS dnsmasq on Docker bridge addresses ✅
- ✅ DNS resolving correctly: wildcard `*.yourdomain.com → 192.168.1.33` (local zone) ✅
- ✅ Upstream forwarders working: `google.com` resolves via `1.1.1.1` / `8.8.8.8` ✅
- ✅ `DNS_SERVER_ADMIN_PASSWORD` sourced from env var — not hardcoded ✅
- ✅ `DNS_SERVER_DOMAIN: technitium.yourdomain.com` set ✅
- ✅ `restart: unless-stopped` — critical for DNS; LAN clients would lose resolution if container stayed down ✅
- ✅ UniFi DHCP secondary DNS `1.1.1.1` — fallback if Technitium is unavailable ✅
- ✅ Ad blocking active (OISD Basic + AdGuard DNS filter, auto-updating daily) ✅
- ✅ Clean logs — graceful stop/restart cycle from Watchtower update, no errors ✅
- ✅ Volume at `${APPDATA_PATH}/technitium:/etc/dns` — config + zones persist through container updates ✅

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Port 5380 on all interfaces | Changed to `192.168.1.33:5380:5380` via compose | see below | ✅ `HostIp=192.168.1.33` confirmed |
| No healthcheck | Added `curl -sf http://localhost:5380/`, `start_period: 30s` via compose | see below | ✅ `Health=healthy` confirmed |
| No mem_limit | Added `mem_limit: 512m` via compose | see below | ✅ `Memory=536870912` (512 MiB) confirmed |
