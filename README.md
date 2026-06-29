# Homelab

Infrastructure as code, documentation, and configuration for my homelab.

## Hardware

| Machine | Role | Connectivity |
|---|---|---|
| UniFi UXG-Fiber | Firewall, router, DHCP (DNS via Technitium) | 192.168.1.1 |
| Zyxel XGS1210-12 | LAN switch — 2×10GbE, 2×2.5GbE, 8×1GbE | 192.168.1.2 |
| NAS02 | TrueNAS — primary ZFS storage (36 TB usable) + Tdarr transcode node (4 CPU workers) | 192.168.1.31 (mgmt) · 10.10.10.31 (storage) |
| NAS01 | Primary compute — Container Station | 192.168.1.33 (bond0: 2×1GbE) · 10.10.10.33 (storage) |
| Lenovo ThinkStation P360 | AI workstation — Ollama + Open WebUI | — separate stack — |

**WAN:** 2 Gbps fiber · **LAN:** 192.168.1.0/24

**Storage network:** Dedicated 10GbE direct link between NAS01 (Aquantia QM2-2P10G1TB) and NAS02
(Chelsio dual-port), MTU 9000. Measured ~780 MB/s read / ~1 GB/s write. NFS mounts use
`10.10.10.31` as the server address.

**NAS01 management network:** `bond0` — Adapter 1 + Adapter 2 in Balance-XOR (Linux mode 2)
via Zyxel LAG 3 (ports 7+8, static LAG, MAC SA+DA hashing). 2×1GbE bonded.

## Repository Structure

```
homelab/
├── compose/
│   ├── docker-compose.yml      # Full 22-container stack
│   └── .env.template           # Environment variable template (copy to .env, never commit .env)
├── scripts/
│   ├── hl.py                   # Homelab API helper — parallel health checks + service commands
│   ├── .hl.env.template        # API credential template (copy to .hl.env, never commit .hl.env)
│   └── .hl.env                 # Real API keys — gitignored
├── dr/
│   ├── restore.sh              # DR restore script — full stack recovery in ~30 min
│   ├── playbook.html           # Interactive DR playbook with checklist
│   └── .secrets.template       # Secrets file template (copy to ~/.homelab.secrets)
├── duplicati/
│   └── homelab-appdata-backup.json  # Duplicati backup job import file
├── skills/
│   ├── homelab-add-service.skill    # Add a new Docker service end-to-end
│   ├── homelab-git-push.skill       # Commit and push changes to GitHub
│   ├── homelab-health-check.skill   # Full stack health check report
│   ├── homelab-service-audit.skill  # Best practice audit for containers
│   └── homelab-update-review.skill  # Review post-Watchtower update results
├── tdarr/
│   ├── FLOWS.md                # Flow architecture docs and mandatory rules
│   └── flows/
│       └── normalize-mkv-h264-aac-stereo.json  # Flow: H.264 MKV + loudnorm AAC stereo (-W-fcbKec)
├── recyclarr/
│   └── recyclarr.yml           # TRaSH Guides quality profile sync config
├── docs/
│   ├── RUNBOOK-INDEX.md        # 📚 Master index of all operational procedures
│   ├── network-diagram.md      # 🌐 Visual network topology and architecture
│   ├── homelab-baseline.html   # Architecture diagram
│   ├── external-access.md      # DNS, NPM proxy hosts, port forwards
│   ├── storage.md              # TrueNAS NFS configuration reference
│   ├── operations.md           # Day-to-day ops cheat sheet
│   ├── migration-plan.md       # VM → Container Station migration notes
│   ├── iot-vlan-plan.md        # IoT VLAN design + implementation plan (VLAN 20)
│   └── ups-integration.md      # UPS (APC BN1500M2) NUT integration plan
├── .claude/
│   └── memory/                 # Claude memory files — load into a fresh Cowork session to restore context
├── CHANGELOG.md                # 📝 Infrastructure change history
├── CLAUDE.md                   # 🤖 AI assistant context file
└── ansible/                    # Configuration management (coming soon)
```

## Container Stack

All containers run in NAS01 Container Station. See [`compose/docker-compose.yml`](compose/docker-compose.yml).

| Service | Purpose | Port |
|---|---|---|
| Plex | Media server | 32400 |
| Sonarr | TV show management | 8989 |
| Radarr | Movie management | 7878 |
| Radarr4K | 4K movie management | 7070 |
| Bazarr | Subtitle management | 6767 |
| Prowlarr | Indexer management | 9696 |
| FlareSolverr | Cloudflare bypass | 8191 |
| SABnzbd | Usenet download client | 8787 |
| TransmissionVPN | Torrent download client (PIA VPN) | 9091 |
| Seerr | Media requests | 5055 |
| Organizr | Dashboard | 8006 |
| Agregarr | Multi-Radarr management | 7171 |
| Tautulli | Plex analytics | 8181 |
| Tdarr | Media transcoding — H.264 MKV + loudnorm AAC stereo (-14 LUFS) | 8265 |
| Recyclarr | TRaSH Guides quality profile sync | — |
| Nginx Proxy Manager | Reverse proxy + SSL (wildcard cert) | 81 / 443 |
| Stirling PDF | PDF tools | 8585 |
| Duplicati | Backup | 8200 |
| Uptime Kuma | Uptime monitoring | 3001 |
| Technitium DNS | LAN DNS with ad blocking | 5380 |
| Watchtower | Auto-updates + email reports | — |
| Tailscale | WireGuard VPN — remote LAN access | — |

Inter-service communication uses container names (e.g. `http://sonarr:8989`), not IPs.
All containers are on the `homelab` Docker network.

**External access:** `*.yourdomain.com` — wildcard A record on Cloudflare points to the
home IP. NPM handles subdomain routing and terminates TLS (wildcard cert via Cloudflare
DNS challenge). New services only need an NPM proxy host entry, not a new DNS record.

**LAN DNS:** Technitium (`192.168.1.33:53`) is the primary DNS server for all LAN clients
(configured in UniFi DHCP). It runs a local zone for `*.yourdomain.com → 192.168.1.33`
to eliminate Cloudflare hairpinning for internal traffic. Ad blocking via OISD Basic +
AdGuard DNS filter lists (auto-updating daily). Upstream forwarders: `1.1.1.1` + `8.8.8.8`.

## Disaster Recovery

**Target RTO: ~30 minutes** to any x86_64 Debian/Ubuntu host.

1. Copy `dr/.secrets.template` to `~/.homelab.secrets` and fill in all values
2. Store a copy in your password manager alongside your GitHub SSH key
3. Run `dr/restore.sh` — handles Docker install, NFS mounts, Duplicati restore, and stack startup

See [`dr/playbook.html`](dr/playbook.html) for the full step-by-step checklist.

> DR tested May 2026 — 156k files / 46 GB restored in 22 min, all 22 containers up, Plex/Sonarr/Radarr history intact.

## Getting Started

1. Copy `compose/.env.template` to `compose/.env`
2. Fill in all values (credentials, NFS paths, PIA credentials)
3. Deploy via NAS01 Container Station → Applications → Create

## Storage

| Path (in containers) | Source |
|---|---|
| `/storage/media_ds` | NAS02 NFS — media library |
| `/storage/downloads_ds` | NAS02 NFS — downloads |
| `/backups` | NAS02 NFS — backup destination |
| `/config` | NAS01 `/share/appdata/<service>` |

## Documentation

### Quick Reference

- **[📚 Runbook Index](docs/RUNBOOK-INDEX.md)** — Master index of all operational procedures, commands, and troubleshooting guides
- **[✅ Change Checklist](docs/change-checklist.md)** — What to update for every type of change (new service, new host, network change, etc.)
- **[🌐 Network Diagram](docs/network-diagram.md)** — Visual topology showing network flow, services, and connectivity
- **[📝 Changelog](CHANGELOG.md)** — Infrastructure change history and version tracking

### Operational Guides

- **[🔧 Operations](docs/operations.md)** — Day-to-day management commands and procedures
- **[🌍 External Access](docs/external-access.md)** — DNS, Nginx Proxy Manager, and port forwarding
- **[💾 Storage](docs/storage.md)** — TrueNAS configuration, NFS shares, and ZFS details

### Planning & Implementation

- **[🔀 Migration Plan](docs/migration-plan.md)** — VM to Container Station migration notes
- **[🏠 IoT VLAN Plan](docs/iot-vlan-plan.md)** — Network segmentation design (VLAN 20)
- **[⚡ UPS Integration](docs/ups-integration.md)** — UPS/NUT integration plan

### Disaster Recovery

- **[🚨 DR Restore Script](dr/restore.sh)** — Automated full stack recovery (~30 min RTO)
- **[📋 DR Playbook](dr/playbook.html)** — Interactive disaster recovery checklist

### Service-Specific

- **[🎬 Tdarr Flows](tdarr/FLOWS.md)** — Media transcoding flow architecture and rules
- **[🤖 Claude Context](CLAUDE.md)** — AI assistant operational context

## Scripts

### `scripts/hl.py` — Homelab API helper

A single Mac-side Python script (no dependencies beyond stdlib) that reaches all homelab
HTTP endpoints directly. Designed to be called from Desktop Commander so Claude can check
or control services in one invocation instead of one-per-service.

```bash
# Full parallel health check of all services
python3 scripts/hl.py health

# Single service status
python3 scripts/hl.py sonarr status

# ARR health issues
python3 scripts/hl.py radarr health

# Trigger a Radarr movie refresh
python3 scripts/hl.py radarr refresh 8579

# Fix a movie's stored path, then rescan
python3 scripts/hl.py radarr setpath 8579 "/storage/media_ds/Movies/The Movie (2021)"

# Recent log entries (default 20)
python3 scripts/hl.py sonarr logs 30

# iDRAC hardware sensors (temps, fans, PSU watts)
python3 scripts/hl.py idrac sensors

# iDRAC System Event Log
python3 scripts/hl.py idrac sel

# Technitium DNS records
python3 scripts/hl.py technitium records

# Add a DNS A record
python3 scripts/hl.py technitium addrecord myservice.yourdomain.com 192.168.1.33

# Active Plex sessions
python3 scripts/hl.py plex sessions
```

**Setup:** copy `scripts/.hl.env.template` to `scripts/.hl.env` and fill in credentials.
Find API keys at each service's Settings → General page. `.hl.env` is gitignored.

## Claude Skills

Installable `.skill` files live in [`skills/`](skills/). Each encodes a complete
workflow for a common homelab task — install via Claude Desktop → Settings → Skills.

| Skill | Trigger phrases | What it does |
|---|---|---|
| `homelab-add-service` | "add X to the homelab", "set up Y", "what if I wanted to add Z" | End-to-end workflow: research the service, write the compose entry, update `.env.template`, check port conflicts, deploy to NAS01, optionally add NPM proxy host and Uptime Kuma monitor. Detects exploratory vs. deploy intent — stops at planning if you're just exploring. |
| `homelab-git-push` | "save", "commit", "push my changes" | Checks what changed, proposes a commit message, stages, commits, and pushes to GitHub. |
| `homelab-health-check` | "how's the stack looking", "health check", "is everything ok" | Full stack check: Docker container status and memory, TrueNAS pool health, iDRAC hardware sensors, last Duplicati backup result, Technitium DNS resolution. Produces a ✅/⚠️/❌ summary report. |
| `homelab-service-audit` | "audit X", "is my Y config correct", "run a best practice check" | Audits one or more services against official docs and community best practices. Produces a prioritised findings checklist (🔴/🟡/🔵). Can apply compose-level fixes on request. |
| `homelab-update-review` | "what updated last night", "morning review", "did anything break" | Reads Watchtower logs, checks health and recent logs of every updated container, and reports anything that looks wrong. |
