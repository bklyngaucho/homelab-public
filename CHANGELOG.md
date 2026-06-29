# Changelog

All notable changes to the homelab infrastructure will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for infrastructure releases.

---

## [Unreleased]

### Planned
- IoT VLAN implementation (VLAN 20, 10.20.0.0/24) - 12 devices ready to migrate
- UPS integration with NUT (blocked on APC USB cable)
- TrueNAS periodic snapshots for media_ds dataset

---

## [2.12.0] - 2026-06-25

### Fixed
- **Tdarr batch "Transcode error" on node auto-update** — root cause: `enableDockerAutoUpdater=true` on NAS02-node would restart its binary whenever the NAS01 tdarr server image updated (via Watchtower), stomping all in-progress files as errors. Fix: pin both `tdarr` and `tdarr_node` to `2.80.01`, add `com.centurylinklabs.watchtower.enable: "false"` label to the NAS01 tdarr container, and set `enableDockerAutoUpdater=false` on NAS02-node. Both containers must now be updated manually and together.
- **1003 files re-queued** — files batch-stamped "Transcode error" by the June 24 NAS02-node auto-update restart were reset to "Queued" via live `docker exec` Python script (no container stop required).

### Changed
- **CLAUDE.md**: updated NAS02-node section to reflect pinned version, `enableDockerAutoUpdater=false`, and coordinated upgrade procedure.

---

## [2.11.0] - 2026-06-22

### Fixed
- **NAS02-node version mismatch resolved** — `ghcr.io/haveagitgat/tdarr_node:latest` lags behind the server image pushed by Watchtower. Added `enableDockerAutoUpdater=true` env var to the TrueNAS custom app compose; the node now detects the version mismatch on connect, self-downloads the correct binary, and reconnects automatically. No manual intervention needed for future Watchtower server updates.

### Changed
- **NAS02-node: custom app over catalog app** — migrated back from TrueNAS catalog app to custom app. Catalog app pins to a specific image version and doesn't support arbitrary env vars, making it incompatible with `enableDockerAutoUpdater`. Custom app with `:latest` + the auto-updater flag is the correct long-term approach.
- **CLAUDE.md**: updated NAS02-node section with `enableDockerAutoUpdater=true` in compose YAML, explanation of why it's needed, and corrected `app.delete` call to include `remove_images: True`.

---

## [2.10.0] - 2026-06-21

### Fixed
- **NAS02-node schedule format corrected** — node schedule entries must embed per-slot worker limits in the format `{"_id": "HH-HH", "transcodecpu": 4, ...}`, matching NAS01-node's format. The simpler `{"hour": N, "active": bool}` format does not carry worker counts; tdarr returns that entry verbatim as the node's `workerLimits`, resulting in 0 workers starting even though the node is connected and the schedule says active. Fixed SQLite and pushed new schedule in-memory via `update-node` (no restart required). NAS02 is now running 5 workers (4 transcode + 1 healthcheck) as intended.

### Changed
- **CLAUDE.md / tdarr/FLOWS.md**: documented the schedule format requirement, the complete fix script, and updated the post-restart checklist to include pushing both `workerLimits` and `schedule` via `update-node`

---

## [2.9.0] - 2026-06-21

### Fixed
- **Tdarr library schedules set to 24/7** — both Movies and TV libraries were gated to 8am–12pm only (matching the NAS01-node's schedule), preventing the NAS02-node from doing any work outside those hours. Updated both library schedules to all 168 weekly slots so the NAS02 can run continuously as intended.

### Changed
- **CLAUDE.md / tdarr/FLOWS.md**: documented the two-schedule model (node schedule + library schedule) and the post-restart checklist (Scan All + re-apply worker limits via update-node)

---

## [2.8.0] - 2026-06-21

### Changed
- **NAS02 tdarr-node image unpinned** — changed from `ghcr.io/haveagitgat/tdarr_node:2.78.01` to `:latest`
  - Allows TrueNAS Apps UI to detect and apply updates (Upgrade button)
  - Watchtower covers only NAS01; NAS02-node must be updated manually via TrueNAS UI after tdarr server updates
  - homelab-update-review skill updated to flag NAS02-node version check when tdarr server is updated by Watchtower
- **nodejsondb SQLite column names corrected** — actual schema is `id` / `json_data` (not `_id` / `data`)
  - Schedule structure is a list of `{hour, active}` dicts (not a key/value dict)
  - `update-node` REST API does persist workerLimits and pathTranslators to SQLite; only the schedule field requires direct SQLite write

---

## [2.7.0] - 2026-06-21

### Added
- **NAS02 Tdarr transcode node** — NAS02 now runs a second Tdarr worker node (TrueNAS custom app)
  - 4 CPU workers active 24/7 — offloads the bulk of the 7,300+ file queue from the NAS01
  - Deployed as TrueNAS custom app (not community app — community schema silently drops volume mounts)
  - Mounts `/mnt/media/media_ds:/media:ro` for path parity with NAS01-node (`server: /media → node: /media`)
  - Node config persisted directly to `nodejsondb` SQLite table via `docker exec -i tdarr python3 -`
  - `update-node` REST API updates in-memory state only; does not persist for NAS02-node
- **Tdarr node schedules configured**
  - NAS01-node: 8am–12pm only (2 CPU + 1 GPU workers)
  - NAS02-node: 24/7 (4 CPU workers)
- **Uptime Kuma: tdarr-NAS02-node monitor** — keyword check on `/api/v2/get-nodes` for "NAS02-node"; added to Media group on homelab status page
- **docs/change-checklist.md** — new document listing every system and doc file to update for each type of infrastructure change

### Fixed
- **network-diagram.md**: corrected ZFS pool capacity (40TB → 36.33 TB), free space (22.4TB → ~19 TB), SanDisk M.2 role (SLOG/L2ARC → boot drives), container counts (20 → 22)
- **CLAUDE.md / README.md**: container count corrected from 21 to 22; DR test note corrected from "15 containers" to "22"
- **homelab-baseline.html**: container count 21 → 22; NAS02 node card updated with tdarr-node and correct pool capacity

### Changed
- **CLAUDE.md** Tdarr bullet: added schedule info, clarified NAS02-node DB persistence behavior, documented `nodejsondb` primary key is node name (not session ID)
- **tdarr/FLOWS.md**: added Node Schedules section with per-node schedule table and NAS02 SQLite update pattern

---

## [2.6.0] - 2026-06-20

### Added
- **Backblaze B2 offsite backup** — closes the offsite leg of the 3-2-1 rule
  - New Duplicati job "Homelab AppData → B2" (BackupID=5), daily at 3:30 AM
  - Bucket: `yourusername-appdata-backup` (private, SSE-B2 enabled, Object Lock disabled)
  - AES-256 client-side encryption; passphrase in password manager
  - Smart retention: 7 daily / 4 weekly / 12 monthly — keeps B2 costs ~$0.22/month at 46 GB
  - Exclusion filters mirror the NAS02 job exactly (Plex cache, torrents, letsencrypt certs, tailscale)

### Fixed
- **Duplicati `*/tailscale*` exclusion** added to both backup jobs (BackupID=4 and 5)
  - Tailscale appdata is root-owned; Duplicati (UID 1000) couldn't read it, producing nightly `PermissionDenied` warnings since 2026-06-14
  - Exclusion is safe: Tailscale re-auth during DR requires only the auth key from Tailscale admin panel

---

## [2.5.0] - 2026-06-19

### Changed
- **Tdarr flow consolidated and loudness-normalized**
  - Replaced two-flow architecture (bklynAAC01 + bklynCOD02) with a single flow:
    `normalize-mkv-h264-aac-stereo.json` (ID: `-W-fcbKec`)
  - AAC stereo track now uses EBU R128 loudnorm at **-14 LUFS / LRA 11 / TP -1.5**
    instead of plain passthrough — addresses chronic low-volume issue on all clients
  - Three branches handle all input types: H.264 MKV (remux), H.264 non-MKV (remux
    to MKV), non-H.264 (NVENC transcode to H.264 MKV). Original audio always preserved.
  - Normalized track tagged `title=AAC_Stereo_Normalized` for identification in Plex
  - All 9,863 video files reset and re-queued for processing (1 GPU worker)
  - FLOWS.md rewritten; flow JSON saved under `tdarr/flows/`

---

## [2.4.0] - 2026-06-19

### Changed
- **NAS01 management network upgraded from single 1GbE to 2×1GbE LAG bond**
  - `bond0`: Adapter 1 + Adapter 2, Balance-XOR / Linux mode 2
  - Zyxel XGS1210-12: LAG 3 on ports 7+8, static LAG (not LACP), MAC SA+DA hashing
  - Always configure NAS01 QTS Port Trunking side before applying the Zyxel LAG
  - Network diagrams, CLAUDE.md, and README updated to reflect bond0

---

## [2.3.0] - 2026-06-13

### Added
- **SABnzbd** — Usenet download client (`lscr.io/linuxserver/sabnzbd`, port 8787)
  - Provider: UsenetServer (`news.usenetserver.com:563`, SSL, 20 connections)
  - Indexers: NZBgeek + Althub via Prowlarr
  - Download paths share `downloads_ds` NFS mount with TransmissionVPN
  - Wired into Sonarr, Radarr, Radarr4K as priority 1 download client; Transmission is fallback

### Changed
- Container count: 21 → 22

---

## [2.2.0] - 2026-06-13

### Removed
- **Notifiarr** — decommissioned (rate limiting fragility, complex setup, low return)
  - Too easy to silently drop notifications: free tier 5 req/sec limit, Sessions toggle footgun, notifiarr.com cloud as single point of failure
  - Watchtower reverts to Gmail SMTP only; Starr app and Plex webhook connections cleaned up
  - Appdata deleted from NAS01

### Changed
- Watchtower notifications: Gmail SMTP only (removed Notifiarr/Discord shoutrrr URL)
- Container count: 22 → 21

---

## [2.1.0] - 2026-06-13

### Added
- **Tailscale** — WireGuard mesh VPN for remote LAN access (`tailscale/tailscale`)
  - Hostname: `NAS01-homelab`; advertises `192.168.1.0/24` subnet route
  - Kernel networking (`TS_USERSPACE=false`) + `network_mode: host` required for subnet routing to non-NAS01 LAN hosts
  - `TS_ACCEPT_DNS=false` preserves Technitium as LAN DNS resolver
  - Healthcheck via built-in `/healthz` endpoint (`TS_ENABLE_HEALTH_CHECK=true`)
- **Notifiarr** — Discord notifications hub (`golift/notifiarr`, port 5454) *(removed in 2.2.0)*

### Changed
- Container count: 20 → 22

---

## [2.0.0] - 2026-06-09

### Added
- **Documentation improvements**
  - Network topology diagrams with ASCII art visualization
  - Comprehensive runbook index for all operational procedures
  - This changelog for tracking infrastructure changes
  - Complete port mapping and IP allocation tables

### Changed
- Documentation structure enhanced for better navigation and maintenance

---

## [1.5.0] - 2026-05-XX

### Added
- **Disaster Recovery testing**
  - Full DR restore tested successfully
  - Actual RTO: 22 minutes (target: 30 minutes)
  - Restored 156k files / 46 GB from Duplicati backup
  - All 19 containers operational with history intact (Technitium not yet added at time of test)

### Changed
- DR documentation updated with actual test results

---

## [1.4.0] - 2026-04-XX

### Added
- **Technitium DNS Server**
  - LAN DNS with ad blocking (OISD Basic + AdGuard DNS filters)
  - Local zone for `*.yourdomain.com` to eliminate Cloudflare hairpinning
  - Upstream forwarders: 1.1.1.1 + 8.8.8.8
  - Bound to 192.168.1.33:53 to avoid QTS dnsmasq conflict
  - Auto-updating filter lists (daily)

### Changed
- UniFi DHCP configured with Technitium as primary DNS (192.168.1.33)
- Cloudflare (1.1.1.1) set as secondary DNS for fallback

---

## [1.3.0] - 2026-03-XX

### Added
- **Tdarr media transcoding**
  - NVIDIA NVENC transcoding with GTX 1050 Ti
  - Two flows: AAC stereo track addition and old codec remediation
  - Flow architecture documentation with mandatory rules
  - Transcode cache on local NVMe for performance

### Changed
- Media library now processed through Tdarr flows
- Improved Roku direct-play compatibility with AAC audio tracks

---

## [1.2.0] - 2026-02-XX

### Added
- **Recyclarr integration**
  - TRaSH Guides quality profile sync for Sonarr/Radarr/Radarr4K
  - Daily automated sync at midnight
  - API keys managed via environment variables

### Changed
- Quality profiles now automatically maintained via TRaSH Guides standards

---

## [1.1.0] - 2026-01-XX

### Added
- **Watchtower auto-updates**
  - Nightly container updates at 4:00 AM
  - Email reports via Gmail SMTP (shoutrrr format)
  - Configurable per-container exclusions via labels

### Changed
- Container update process automated (previously manual)

---

## [1.0.0] - 2025-12-XX

### Added
- **Complete container migration from Ubuntu VM to NAS01 Container Station**
  - 20-container Docker Compose stack
  - Plex migrated from native NAS01 app to container
  - All services on unified `homelab` Docker network
  - Inter-service communication via container names

### Infrastructure
- **Hardware**
  - NAS01 (primary compute)
  - NAS02 with TrueNAS SCALE (storage)
  - UniFi UXG-Fiber (router/firewall)
  - 2 Gbps fiber WAN, 192.168.1.0/24 LAN

- **Storage**
  - ZFS pool: 8×10TB HDDs in RAID 10 (~40TB usable)
  - 2× SanDisk M.2 128GB SSDs for SLOG/L2ARC
  - NFS shares: media_ds (17.4TB), downloads_ds (73GB), backups (67GB)

- **Container Stack**
  - Media: Plex, Tdarr
  - Arr Stack: Sonarr, Radarr, Radarr4K, Bazarr, Prowlarr, FlareSolverr
  - Download: TransmissionVPN (PIA)
  - Request: Seerr (Jellyseerr)
  - Infrastructure: Nginx Proxy Manager, Duplicati, Uptime Kuma
  - Tools: Stirling PDF, Organizr, Agregarr, Tautulli

- **Network**
  - Nginx Proxy Manager with wildcard Let's Encrypt cert (Cloudflare DNS challenge)
  - Cloudflare DNS with wildcard `*.yourdomain.com` → home IP
  - UniFi port forwards: 80, 443 (NPM), 32400 (Plex direct)

- **Backup & DR**
  - Duplicati nightly backups to TrueNAS (2:00 AM)
  - Automated DR restore script with ~30 min RTO
  - Interactive DR playbook (HTML checklist)

### Changed
- Migrated from Ubuntu VM to native Container Station
- Consolidated all services under single compose stack
- Unified storage backend via NFS from TrueNAS

### Removed
- Ubuntu VM (decommissioned after successful migration)
- Native NAS01 Plex app (replaced with containerized version)

---

## [0.9.0] - 2025-11-XX (Pre-Migration)

### Added
- Initial Ubuntu VM setup on NAS01 Virtualization Station
- Basic arr stack (Sonarr, Radarr, Prowlarr)
- Transmission with PIA VPN
- Native NAS01 Plex app

### Infrastructure
- NAS01 with Virtualization Station
- Ubuntu 22.04 LTS VM running Docker
- Basic Docker Compose setup
- Manual backup procedures

---

## Infrastructure Version History

### Version Numbering Scheme

- **Major version (X.0.0)**: Significant infrastructure changes (hardware, major service migrations)
- **Minor version (0.X.0)**: New services, features, or substantial configuration changes
- **Patch version (0.0.X)**: Bug fixes, minor config updates, documentation improvements

### Current Infrastructure State

**Version**: 2.5.0  
**Last Major Change**: Tdarr loudnorm normalization + NAS01 2×1GbE LAG bond (2026-06-19)  
**Stability**: Production  
**Uptime Target**: 99.5% (excluding planned maintenance)

---

## Change Categories

Changes are categorized as follows:

- **Added**: New features, services, or capabilities
- **Changed**: Changes to existing functionality or configuration
- **Deprecated**: Features or services marked for removal
- **Removed**: Features or services that have been removed
- **Fixed**: Bug fixes or corrections
- **Security**: Security-related changes or updates

---

## Maintenance Windows

Regular maintenance windows for infrastructure changes:

- **Preferred**: Sunday 2:00 AM - 4:00 AM EST (overlaps with backup window)
- **Emergency**: As needed with notification
- **Automated**: Daily backups (2:00 AM), Watchtower updates (4:00 AM), Recyclarr sync (midnight)

---

## Rollback Procedures

In case a change causes issues:

1. **Container changes**: Revert compose file and restart affected services
2. **Configuration changes**: Restore from Duplicati backup (last 30 days retained)
3. **Full stack failure**: Execute DR restore procedure (~30 min RTO)

---

## Testing Requirements

Before marking a change as complete:

- [ ] All affected containers start successfully
- [ ] Health checks pass for affected services
- [ ] Inter-service communication verified
- [ ] External access tested (if applicable)
- [ ] Backup job completes successfully
- [ ] Documentation updated

---

## Future Roadmap

### Q3 2026
- [ ] Implement IoT VLAN (VLAN 20)
- [ ] Complete UPS integration with NUT
- [ ] Configure Uptime Kuma notifications
- [ ] Enable TrueNAS snapshots for media_ds

### Q4 2026
- [ ] Evaluate container resource limits and optimization
- [ ] Review and update backup retention policies
- [ ] Implement automated health reporting
- [ ] Consider adding monitoring dashboards (Grafana/Prometheus)

### 2027
- [ ] Evaluate storage expansion (additional vdev or larger drives)
- [x] ~~Consider 10GbE upgrade for NAS01-TrueNAS link~~ — done (direct 10GbE cable, ~780 MB/s read)
- [ ] Explore additional automation opportunities
- [ ] Review and update DR procedures

---

## Related Documentation

- [README.md](README.md) - Repository overview and getting started
- [CLAUDE.md](CLAUDE.md) - AI assistant context and operational notes
- [docs/operations.md](docs/operations.md) - Day-to-day operations
- [docs/RUNBOOK-INDEX.md](docs/RUNBOOK-INDEX.md) - Complete operational procedures index
- [docs/network-diagram.md](docs/network-diagram.md) - Network topology diagrams
- [dr/playbook.html](dr/playbook.html) - Disaster recovery checklist

---

## Contributing

When making infrastructure changes:

1. Document the change in this CHANGELOG under `[Unreleased]`
2. Update relevant documentation files
3. Test thoroughly in the homelab environment
4. Commit with descriptive message following conventional commits format
5. After deployment, move the change from `[Unreleased]` to a new version section

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: feat, fix, docs, style, refactor, perf, test, chore  
**Scopes**: container, network, storage, backup, dr, docs, etc.

**Examples**:
```
feat(container): add Technitium DNS server with ad blocking

- Configured LAN DNS on 192.168.1.33:53
- Added OISD Basic and AdGuard DNS filters
- Created local zone for *.yourdomain.com
- Updated UniFi DHCP to use Technitium as primary DNS

Closes #42
```

```
fix(network): resolve NPM wildcard cert renewal issue

- Updated Cloudflare API token permissions
- Verified DNS challenge completes successfully
- Cert now renews automatically at 60 days

Fixes #38
```

---

*This changelog is maintained manually. All dates are approximate based on git history and deployment records.*