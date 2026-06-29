# Services Best Practice Audit — Plex
2026-06-11

## Summary
3 findings: 0 🔴 critical · 0 🟡 warning · 3 🔵 info

---

## Plex

### 🟡 Warning

- [ ] **Hardware transcoding not confirmed active — Intel QSV device passed through but setting not enabled in Plex UI**
  - **Why it matters:** `/dev/dri` is correctly passed through to the container and Plex detects the Intel QSV device, but `HardwareAcceleratedCodecs` and `HardwareAcceleratedEncoders` are absent from `Preferences.xml` — these keys are written by Plex when the setting is turned on. Without them, all transcoding is done in software (CPU), burning NAS01 CPU cycles and limiting concurrent stream capacity. With Intel QSV enabled, Plex offloads H.264/H.265 encode/decode to the integrated GPU, essentially making transcoding free.
  - **Source:** [LinuxServer.io Plex docs](https://docs.linuxserver.io/images/docker-plex/) — hardware transcoding requires both (1) passing `/dev/dri` into the container ✅ already done, and (2) enabling "Use hardware acceleration when available" in Plex UI. Requires Plex Pass.
  - **Current:** `HardwareAcceleratedCodecs` / `HardwareAcceleratedEncoders` not set in `Preferences.xml`
  - **Recommended:** Plex UI → Settings → Transcoder → "Use hardware acceleration when available" → On
  - **Manual fix:** Plex UI → Settings (wrench icon) → Transcoder → toggle on

---

### 🔵 Info

- [ ] **No healthcheck defined**
  - **Why it matters:** If the Plex web process hangs, Docker keeps the container listed as "Up" while the UI and streaming API are unresponsive.
  - **Source:** LinuxServer.io Plex image — no built-in healthcheck. The `/identity` endpoint returns server info without authentication.
  - **Current:** `Health=null` confirmed via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:32400/identity"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 60s
    ```
    Note: `start_period: 60s` — Plex takes longer to initialise than the ARR apps.

- [ ] **No memory limit**
  - **Why it matters:** Plex officially discourages hard memory limits (large DB operations and library analysis can spike usage), but with a 39 GB appdata directory containing extensive chapter thumbnails and metadata, Plex can balloon to 2–4 GB during maintenance windows. A generous ceiling prevents runaway consumption on the shared NAS01 while staying well above Plex's operational needs.
  - **Current:** `Memory=0`
  - **Recommended:** `mem_limit: 4g` — generous enough that normal operation is never affected, tight enough to cap a runaway process.

- [ ] **Stale `PLEX_CLAIM` token still set in environment**
  - **Why it matters:** `PLEX_CLAIM` is a one-time-use token that expires 4 minutes after generation. It's only needed for the initial server claim. The server is already claimed (`PlexOnlineToken` set, server registered as `gauchoflix`). The stale token is harmless but is unnecessary env noise and could cause confusion if someone reads the `.env` thinking the server needs reclaiming.
  - **Source:** [LinuxServer.io Plex docs](https://docs.linuxserver.io/images/docker-plex/) — "required only on first run"
  - **Current:** `PLEX_CLAIM=claim-Xax7UaGNFPYY4736MaWJ` (expired token, server already claimed)
  - **Recommended:** Remove `PLEX_CLAIM` from `compose/.env` and from the compose env block. No restart needed for this change since the key is only read at first-run.

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Hardware transcoding not confirmed | False alarm — setting IS enabled in Plex UI (checked). Preferences.xml grep used old key names from pre-1.40 Plex. | — | ✅ Confirmed via screenshot |
| No healthcheck | Applied via compose — `/identity` endpoint, `start_period: 60s` | e83fc48 | ✅ `Health=healthy` |
| No memory limit | Applied via compose — `mem_limit: 4g` | e83fc48 | ✅ `Mem=4294967296` |
| Stale PLEX_CLAIM token | Removed from compose env block and `.env.template` | e83fc48 | ✅ |

---

## What's working well

- ✅ Running and streaming — active transcode session confirmed in appdata ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID: 1000 / PGID: 1000` set ✅
- ✅ `VERSION: docker` — correct for linuxserver; uses image-bundled Plex version ✅
- ✅ `customConnections="https://plex.yourdomain.com:443"` — NPM reverse proxy correctly wired ✅
- ✅ `LanNetworksBandwidth="192.168.1.0/24"` — Plex knows the LAN subnet; direct-plays LAN clients at full speed ✅
- ✅ `RelayEnabled="0"` — no Plex relay; all connections go direct or through NPM ✅
- ✅ `/dev/dri` passed through — Intel QSV device available to the container ✅
- ✅ Transcode sessions write to local NAS01 appdata (`/share/appdata/plex`) — not NFS; no latency impact ✅
- ✅ `DlnaEnabled="0"` — DLNA off; no unnecessary service exposure ✅
- ✅ Bridge networking (intentional — host mode not needed with NPM proxy) ✅
