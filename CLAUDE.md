# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Restoring a Cowork session

If starting a fresh Cowork project from this repo, load the memory files from
`.claude/memory/` into your session's memory directory to restore accumulated
context about the stack, preferences, and working style. The `MEMORY.md` index
lists what each file contains. Also reinstall the skills from `skills/` via
Claude Desktop → Settings → Skills.

The following scheduled tasks should be recreated manually:
- **Nightly update review** — runs after Watchtower (4 AM). Prompt: "Review last
  night's Watchtower update run and report anything that looks wrong."

## What this repo is

Infrastructure-as-code for a home media server stack. The primary artefacts are a Docker Compose file and supporting DR/backup tooling. There is no application code to build, test, or lint.

## Hardware context

| Host | Role | IP |
|---|---|---|
| NAS01 | Primary compute — runs all 22 containers via Container Station | 192.168.1.33 |
| NAS02 / TrueNAS | NAS — all persistent data lives here via NFS | 192.168.1.31 |
| NAS02 iDRAC | Hardware management (Redfish API) | 192.168.1.4 |
| UniFi UXG-Fiber | Router / firewall | 192.168.1.1 |
| Lenovo P360 | AI workstation (Ollama / Open WebUI) — unrelated to this stack | — |

### Storage network (10GbE dedicated)

A direct 10GbE link connects the NAS01 and NAS02 on a separate storage subnet, bypassing the main LAN switch for NFS traffic:

| Host | Interface | IP | Notes |
|---|---|---|---|
| NAS01 | Adapter 5 (QM2-2P10G1TB, Aquantia) | 10.10.10.33/24 | MTU 9000, direct cable to NAS02 |
| NAS02 / TrueNAS | ens2f0 (Chelsio dual-port 10GbE) | 10.10.10.31/24 | MTU 9000, labeled "storage" in TrueNAS UI |

NFS mounts use `10.10.10.31` as the server address (configured in HybridMount on NAS01). The old `192.168.1.31` mounts remain in HybridMount in disabled state as a fallback. NAS01 management traffic (192.168.1.33) runs on **bond0** (Adapter 1 + Adapter 2, Balance-XOR / Linux mode 2) via Zyxel LAG 3 (ports 7+8, MAC SA+DA). This is a 2×1GbE bond — the Zyxel must be configured with a static LAG (not LACP) using MAC SA+DA hashing to match. Always configure the NAS01 side (QTS Port Trunking → Managed Switch → Balance-XOR) before applying the Zyxel LAG.

**Measured throughput:** ~780 MB/s read, ~1.0 GB/s buffered write (6× improvement over previous 1GbE path).

## Key paths

| What | Where |
|---|---|
| Running compose stack on NAS01 | `/share/Container/container-station-data/application/homelab/` |
| Container appdata on NAS01 | `/share/appdata/<service>/` |
| Recyclarr config on NAS01 | `/share/appdata/recyclarr/recyclarr.yml` |
| Secrets file (never committed) | `~/.homelab.secrets` |

## Applying changes

The NAS01 does **not** run a git clone — Container Station manages its own copy of the compose file. After editing files in this repo:

```bash
# Push to GitHub
git add . && git commit -m "..." && git push

# Sync compose file to NAS01 (if changed)
scp compose/docker-compose.yml admin@192.168.1.33:/share/Container/container-station-data/application/homelab/docker-compose.yml

# Sync Recyclarr config to NAS01 (if changed)
scp recyclarr/recyclarr.yml admin@192.168.1.33:/share/appdata/recyclarr/recyclarr.yml

# Restart affected service on NAS01
ssh admin@192.168.1.33 'cd /share/Container/container-station-data/application/homelab && \
  /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d <service>'
```

SSH key auth is configured between Mac and NAS01 — no password needed. Docker is not in the NAS01's default SSH PATH; always use the full binary path above.

## Secrets and environment variables

- `compose/.env` — live secrets on the NAS01, **never committed**
- `compose/.env.template` — committed placeholder showing all required variables
- `dr/.secrets.template` — DR-specific secrets template (committed with REPLACE placeholders, no real values)
- `~/.homelab.secrets` — used exclusively by `dr/restore.sh`

The `.gitignore` excludes `*.env`, `*.secrets`, `.homelab.secrets`. Never use `git add -f` on these files.

## Container stack overview

22 containers in `compose/docker-compose.yml`, all on the `homelab` Docker network. Inter-service communication uses container names (e.g. `http://sonarr:8989`), not IPs.

NFS mounts from the NAS02 are referenced via env vars: `$MEDIA_DS`, `$DOWNLOADS_DS`, `$BACKUPS`. On the NAS01 these resolve to NAS01 network drive UUIDs; on a DR host they map to `/mnt/homelab/{media_ds,downloads_ds,backups}`.

**Notable configuration details:**
- Plex uses `lscr.io/linuxserver/plex` (not the official image) — stays on bridge networking, not host mode
- Plex hardware transcoding: both Intel QuickSync (VAAPI via `/dev/dri`) and NVIDIA NVENC (GTX 1050 Ti via `/dev/nvidia*`) are wired in. NVENC requires a curated lib directory at `/share/CACHEDEV1_DATA/.qpkg/NVIDIA_GPU_DRV/nvenc-libs/` (symlinks to only `libcuda`, `libnvcuvid`, `libnvidia-encode`, `libnvidia-ptxjitcompiler` — **no libdrm**). Mounting the full NVIDIA lib directory crashes Plex because the NAS01 NVIDIA driver package ships `libdrm.so.2.4.0` (circa 2010) which is missing `drmGetDevices2` that Plex's binary requires. In AUTO mode Plex prefers VAAPI (full HW pipeline, very efficient); NVENC is available for overflow or when explicitly selected. To verify an active transcode session, check `transcodeHwEncodingTitle` and `transcodeHwDecodingTitle` attributes on the TranscodeSession XML element — not `hwEncoding` (that field doesn't exist).
- TransmissionVPN requires the TUN device (`/dev/net/tun`); on modern kernels TUN is built-in so `modprobe tun` returning nothing is normal
- Duplicati's linuxserver image requires `SETTINGS_ENCRYPTION_KEY` env var even for CLI operations; the CLI binary is at `/app/duplicati/duplicati-cli` inside the container and must be invoked with `with-contenv`
- Duplicati backup job "Homelab AppData → NAS02" (BackupID=4) runs daily at **2:00 AM**; Watchtower runs at **4:00 AM** — no schedule conflict. Backup completes well within the 2-hour window.
- Duplicati backup job "Homelab AppData → B2" (BackupID=5) runs daily at **3:30 AM** → Backblaze B2 bucket `yourusername-appdata-backup`. AES-256 client-side encryption; passphrase in password manager. Smart retention: 7 daily / 4 weekly / 12 monthly. Closes the offsite leg of the 3-2-1 rule. ~$0.22/month at 46 GB.
- Duplicati backup exclusions (stored in the SQLite DB filter table, same set on both BackupID=4 and BackupID=5): Plex cache/codecs/crash reports/logs/media/updates, transmissionvpn/torrents, `*/npm/letsencrypt*` (certs are root-owned and regeneratable via NPM in ~2 min during DR), and `*/tailscale*` (root-owned state files — re-auth is trivial during DR)
- Uptime Kuma monitors are set to `maxretries=3` — requires 3 consecutive failures before alerting. This prevents false alarms from transient network blips during the 2 AM Duplicati backup run.
- **sqlite3 is not available** in the Duplicati container. To modify the Duplicati DB: stop the container, SCP the DB to the Mac, edit with Python's built-in `sqlite3`, SCP back, restart.
- **Python on NAS01 SSH**: Two versions available:
  - **Python 2.7** at `/usr/local/bin/python`, symlinked to `/usr/bin/python`. Includes working `sqlite3` (v3.26.0). Use this for direct DB edits on the NAS01.
  - **Python 3.13.9** installed via Entware offline (packages extracted manually from .ipk files and copied to `/opt/`). Available as `python3` (symlinked to `/usr/bin/python3`). Includes working `sqlite3` (v3.51.2, via `libsqlite3` from Entware). Use for modern scripting and DB edits on the NAS01.
- QTS web UI runs on port **8443** (moved from 443 to free port 443 for Nginx Proxy Manager)
- Nginx Proxy Manager proxies `plex.yourdomain.com` → `plex:32400`, `seerr.yourdomain.com` → `seerr:5055`, `pdf.yourdomain.com` → `stirling-pdf:8080`, and `status.yourdomain.com` → `uptimekuma:3001` (root `/` redirects to `/status/homelab` via advanced_config) using a wildcard Let's Encrypt cert via Cloudflare DNS challenge
- Recyclarr syncs TRaSH Guides quality profiles daily (`@daily` cron); config uses `!env_var` YAML tags so API keys come from container environment, not the config file
- RSS sync intervals are staggered to prevent all three ARR apps hitting Prowlarr/YTS simultaneously: **Sonarr 15 min → Radarr 20 min → Radarr4K 25 min**. Configured via `PUT /api/v3/config/indexer` on each app (not in compose — stored in each app's SQLite DB). Symptom of collision: 429 from YTS/indexers during manual grabs.
- Watchtower sends notifications after each nightly update run via Gmail SMTP. URL format: `smtp://your.email%40gmail.com:APP_PASSWORD@smtp.gmail.com:587/?from=...&to=...` in `WATCHTOWER_NOTIFICATION_URL` in the live `.env` on the NAS01. Requires a Gmail App Password (not your account password).
- SABnzbd runs on internal port 8080, mapped to host port 8787 (LAN-only). Usenet provider: UsenetServer (`news.usenetserver.com:563`, SSL, 20 connections). Fill server: theCubeNet (`news.thecubenet.com:563`, SSL, 5 connections, priority 2, Optional) — UsenetExpress backbone complements UsenetServer's Highwinds backbone. **theCubeNet issues new credentials per block purchase** — update SABnzbd → Servers → cubenet whenever a new block is bought. Indexers: NZBgeek + Althub, both wired via Prowlarr. Download paths: `/storage/downloads_ds/incomplete` and `/storage/downloads_ds/completed` — same NFS mount as TransmissionVPN. Categories configured: `movies`, `tv`, `movies4k` (subfolder paths under completed). SABnzbd is set as **priority 1** download client in Sonarr, Radarr, and Radarr4K; TransmissionVPN is fallback. API key in `scripts/.hl.env` (`SABNZBD_API_KEY`).
- Tailscale runs with `CAP_NET_ADMIN` + `CAP_SYS_MODULE` + `/dev/net/tun`. Hostname: `NAS01-homelab`. Advertises routes `192.168.1.0/24` — subnet routing must be approved at login.tailscale.com/admin/machines. `TS_ACCEPT_DNS=false` to avoid overriding Technitium.
- Stirling PDF runs on internal port 8080, mapped to host port 8585. API access: `X-API-Key` header or HTTP Basic Auth. Credentials in `~/.homelab.secrets` (`STIRLING_USER`, `STIRLING_PASS`, `STIRLING_API_KEY`). Example: `curl -s http://192.168.1.33:8585/api/v1/info/status -H "X-API-Key: $STIRLING_API_KEY"`
- Technitium DNS binds port 53 to `192.168.1.33` specifically (not `0.0.0.0`) to avoid conflict with QTS dnsmasq which runs on Docker bridge addresses only. Web UI on port 5380. Admin password set via `TECHNITIUM_ADMIN_PASSWORD` env var. UniFi DHCP is configured with primary DNS `192.168.1.33` and secondary `1.1.1.1` — devices fall back to Cloudflare if Technitium is unavailable. Upstream forwarders set to `1.1.1.1` + `8.8.8.8` (configured via API, not in compose). Ad blocking active: OISD Basic + AdGuard DNS filter, auto-updating daily. Local zone `yourdomain.com` with wildcard `*.yourdomain.com → 192.168.1.33` eliminates Cloudflare hairpinning for LAN clients. API token at `~/.technitium-token` — manage DNS via Desktop Commander curl calls, no MCP needed.
- Tdarr runs two nodes: **NAS01-node** (built into the `tdarr` container — 2 CPU + 1 GPU worker, schedule: **8am–12pm**) and **NAS02-node** (separate container on TrueNAS — 4 CPU workers, schedule: **24/7**). Node job assignment is first-come first-served: idle workers request files via socket.io and whichever requests first gets the next queued file. Path translators (`server: /media, node: /media`) ensure the NAS02 node can resolve file paths assigned by the NAS01 server. **After any tdarr server restart**, the in-memory transcode queue must be rebuilt manually: Tdarr UI → Libraries → **Scan All (find fresh)**. Without this, all workers sit idle even though 7,000+ files are queued in the DB. After restart, in-memory worker limits also reset — re-run `POST /api/v2/update-node` to restore them. **Two independent schedules gate processing:** (1) the *node* schedule (stored in `nodejsondb`, controls when node workers are active) and (2) the *library* schedule (stored in `librarysettingsjsondb`, controls when files from a library can be dispatched to any worker). Both must be open for the current hour or no work happens. Library schedules are set to 24/7 (all 168 weekly slots checked) so the NAS02-node can run outside the NAS01-node's 8am–12pm window. The `update-node` REST API (`POST /api/v2/update-node`) persists workerLimits and pathTranslators to SQLite but does **not** persist the schedule — for schedule changes, write directly to the `nodejsondb` table. To do this: write a Python script to `/tmp/` on the Mac, `scp` it to the NAS01 at `/tmp/`, `docker cp` it into the tdarr container, then `docker exec tdarr python3 /tmp/script.py`. SQLite schema: `nodejsondb(id TEXT, timestamp TEXT, json_data TEXT)` — the `id` column is the node **name** (e.g. `NAS02-node`), not the runtime session ID. **NAS02-node schedule format is critical:** each slot must embed per-slot worker limits using the same format as NAS01-node: `{"_id": "HH-HH", "healthcheckcpu": 1, "healthcheckgpu": 0, "transcodecpu": 4, "transcodegpu": 0}`. The simpler `{"hour": N, "active": bool}` format does NOT carry worker counts — tdarr returns that entry verbatim as the current `workerLimits`, meaning it thinks the node has 0 workers and nothing starts. After fixing SQLite, also push the schedule in-memory via `update-node` (no restart needed). Library schedule in `librarysettingsjsondb` uses `{"_id": "Day:HH-HH", "checked": bool}` format (168 entries covering all day/hour combos). NAS01-node persists correctly via the REST API. Tdarr's SQLite DB lives at `/app/server/Tdarr/DB2/SQL/database.db`.

## NAS02 tdarr-node (TrueNAS custom app)

The NAS02 runs a `tdarr_node` container deployed as a **TrueNAS custom app** (not the community catalog app — the catalog pins to a specific version and doesn't support arbitrary env vars, so it can't get the `enableDockerAutoUpdater` flag needed for self-healing). The compose YAML stored in TrueNAS:

```yaml
services:
  tdarr-node:
    image: ghcr.io/haveagitgat/tdarr_node:2.80.01
    container_name: tdarr-node
    environment:
      - TZ=America/New_York
      - PUID=1000
      - PGID=1000
      - nodeName=NAS02-node
      - serverIP=192.168.1.33
      - serverPort=8266
      - enableDockerAutoUpdater=false
    volumes:
      - /mnt/.ix-apps/app_mounts/tdarr-node/tdarr-node-configs:/app/configs
      - /mnt/.ix-apps/app_mounts/tdarr-node/tdarr-node-logs:/app/logs
      - /mnt/.ix-apps/app_mounts/tdarr-node/transcodes:/temp
      - /mnt/media/media_ds:/media
    restart: unless-stopped
```

**Both tdarr and tdarr_node are pinned to `2.80.01`.** The NAS01 tdarr container has `com.centurylinklabs.watchtower.enable: "false"` so Watchtower skips it. `enableDockerAutoUpdater=false` on the NAS02-node prevents the binary self-update that previously caused batch "Transcode error" stamping whenever the server updated. To upgrade: update the image tag in both compose files, recreate the NAS02-node via TrueNAS, and restart tdarr on the NAS01. Both must move to the same version at the same time.

To update via TrueNAS WebSocket API (Python, `wss://192.168.1.31/api/current`, JSON-RPC 2.0):
- Query app: `app.query` with filter `[["name", "=", "tdarr-node"]]` (field is `name`, not `app_name`)
- Delete: `app.delete` with `{"remove_images": True}` → returns job ID → poll with `core.get_jobs`
- Recreate: `app.create` with `{"custom_app": True, "app_name": "tdarr-node", "custom_compose_config_string": "<yaml>"}`

After recreating, run `POST /api/v2/update-node` to set worker limits and path translators for the new node ID:
```bash
NODE_ID=$(curl -s http://192.168.1.33:8265/api/v2/get-nodes | python3 -c "import sys,json; d=json.load(sys.stdin); [print(k) for k,v in d.items() if 'NAS02' in v['nodeName']]")
curl -X POST http://192.168.1.33:8265/api/v2/update-node \
  -H "Content-Type: application/json" \
  -d "{\"data\":{\"nodeID\":\"$NODE_ID\",\"nodeUpdates\":{\"workerLimits\":{\"healthcheckcpu\":1,\"healthcheckgpu\":0,\"transcodecpu\":4,\"transcodegpu\":0},\"config\":{\"pathTranslators\":[{\"server\":\"/media\",\"node\":\"/media\"}]}}}}"
```

## NAS02 / TrueNAS hardware

**Specs:** NAS02 · 2× Intel Xeon Silver 4214 (2.2 GHz) · 48 GiB RAM · PERC H730P RAID controller · 8× 10 TB SATA HDD (mixed HGST/Seagate) · 2× 128 GB SanDisk X400 M.2 2280 (boot drives) · Dual redundant PSUs (PS1 active ~128W, PS2 standby)

**TrueNAS pool `media`:** 4× mirror vdevs (RAID-10 equivalent) — `sda/sdh`, `sdb/sdf`, `sdc/sdd`, `sde/sdg`. 36.33 TB usable, ~17 TB used, ~19 TB free. TrueNAS version 26.0.0 (SCALE). Last scrub: clean (0 errors).

**iDRAC (Redfish API):** `https://192.168.1.4` — credentials in `~/.homelab.secrets` (`IDRAC_T440_USER`/`IDRAC_T440_PASS`). Use for hardware health: temps, fan RPMs, PSU state, SEL event log.
```bash
# Example: system summary
curl -sk https://192.168.1.4/redfish/v1/Systems/System.Embedded.1 \
  -u "$IDRAC_T440_USER:$IDRAC_T440_PASS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['Model'], d['PowerState'], d['MemorySummary'])"
```

**SEL note:** Two recurring "fatal error on bus 4 device 0" entries (2026-04-17, 2026-05-22) — caused by the BCM5720 dual-port NIC. Current Health=OK; transient PCIe link training events during reboots, not an active failure.

**TrueNAS API (WebSocket):** TrueNAS SCALE 24.10+ — REST API removed, WebSocket only at `wss://192.168.1.31/api/current`. Credentials in `~/.homelab.secrets` (`TRUENAS_API_USER=owner`, `TRUENAS_API_KEY`). Auth method: `auth.login_with_api_key`. Requires `websockets` Python package. **IMPORTANT:** Must use `wss://` (TLS) — TrueNAS auto-revokes API keys used over plain `ws://`. **TrueNAS 26.0.0 uses JSON-RPC 2.0** — messages must include `"jsonrpc":"2.0"` or TrueNAS returns `{"error":{"code":-32600,"message":"Missing 'jsonrpc' member"}}`. Example call pattern:
```python
async def call(ws, method, params=None, id=1):
    await ws.send(json.dumps({"jsonrpc":"2.0","method":method,"params":params or [],"id":id}))
    r = json.loads(await ws.recv())
    if "error" in r: raise Exception(f"{method} error: {r['error']}")
    return r.get("result")
# Auth: await call(ws, "auth.login_with_api_key", [API_KEY])
# ZFS:  await call(ws, "pool.dataset.update", ["media/media_ds", {"recordsize": "1M"}])
```

## DNS management

**LAN DNS:** Technitium runs on `192.168.1.33:53`. Set it as the primary DNS server in UniFi DHCP (Networks → LAN → DHCP → DNS Servers), with `1.1.1.1` as secondary fallback. Local A records (e.g. `*.yourdomain.com → 192.168.1.33`) eliminate Cloudflare hairpinning for internal traffic. Technitium web UI: `http://192.168.1.33:5380`.

**External DNS:** Domain `yourdomain.com` is on Cloudflare. Zone ID: `YOUR_CF_ZONE_ID`.

A wildcard `*.yourdomain.com` A record points to the home IP — **new services never need individual DNS records**, only an NPM proxy host entry.

Manage DNS via the Cloudflare API using the token in `~/.homelab.secrets` (`CLOUDFLARE_API_TOKEN`):

```bash
# List DNS records
curl -s "https://api.cloudflare.com/client/v4/zones/YOUR_CF_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"

# Add a record
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/YOUR_CF_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"subdomain.yourdomain.com","content":"YOUR_PUBLIC_IP","proxied":true}'
```

## Tooling

- **Desktop Commander** — runs shell commands on the Mac and NAS01 via SSH without user copy-paste
- **UniFi MCP** (`unifi-network`) — connected to UXG-Fiber at 192.168.1.1; use `unifi_tool_index` to discover tools then `unifi_execute` to run them
- Git operations and NAS01 syncs are handled automatically via the homelab-git-push skill using Desktop Commander

## scripts/hl.py — API helper

`scripts/hl.py` is a Python helper (stdlib only, no pip) that calls homelab HTTP endpoints
directly from the Mac. Credentials live in `scripts/.hl.env` (gitignored). Call it via
Desktop Commander `start_process` instead of issuing N separate SSH or curl commands.

```bash
# One call to check the whole stack
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py health

# Individual service check
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py radarr status
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py radarr health   # ARR health issues
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py radarr logs 30

# Trigger refresh commands
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py radarr refresh <movieId>
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py radarr setpath <movieId> "/new/path"
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py sonarr refresh <seriesId>

# iDRAC hardware sensors and event log
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py idrac sensors
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py idrac sel

# Technitium DNS
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py technitium records
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py technitium addrecord <domain> <ip>

# Active Plex sessions
python3 /Users/owner/Documents/Claude/Projects/Homelab/scripts/hl.py plex sessions
```

Services supported: sonarr, radarr, radarr4k, bazarr, prowlarr, tautulli, plex, stirling-pdf, technitium, idrac, seerr.
SSH is still required for: `docker compose up/down`, `docker logs`, Duplicati CLI, Recyclarr, Watchtower.

## DR restore

`dr/restore.sh` performs a full stack recovery to any x86_64 Debian/Ubuntu host in ~30 minutes. It handles Docker install, NFS mounts, Duplicati appdata restore (~46 GB), `.env` generation, and container startup. Targets Debian/Ubuntu and RHEL/Fedora only — Arch is not supported.

The script requires `~/.homelab.secrets` to be populated (copy from `dr/.secrets.template`). It strips BOM and CRLF from the secrets file automatically on load.

See `dr/playbook.html` for the interactive step-by-step checklist.
