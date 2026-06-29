# Runbook Index

Quick reference index for all homelab operational procedures, troubleshooting guides, and maintenance tasks.

---

## 🚀 Quick Start

| Task | Document | Section |
|------|----------|---------|
| **Deploy the stack** | [README.md](../README.md) | Getting Started |
| **Day-to-day operations** | [operations.md](operations.md) | All sections |
| **Disaster recovery** | [playbook.html](../dr/playbook.html) | Interactive checklist |
| **Network topology** | [network-diagram.md](network-diagram.md) | All diagrams |

---

## 📋 Container Management

### Starting & Stopping Services

| Operation | Command | Reference |
|-----------|---------|-----------|
| Check all container status | `ssh admin@192.168.1.33 'cd /share/Container/container-station-data/application/homelab && /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose ps'` | [operations.md](operations.md#check-container-status) |
| Restart single service | `ssh admin@192.168.1.33 'cd /share/Container/container-station-data/application/homelab && /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d <service>'` | [operations.md](operations.md#restart-a-single-service) |
| Restart all containers | `ssh admin@192.168.1.33 'cd /share/Container/container-station-data/application/homelab && /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d'` | [operations.md](operations.md#restart-all-containers) |
| View live logs | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs -f <service>'` | [operations.md](operations.md#view-live-logs-for-a-service) |
| Execute command in container | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec -it <service> bash'` | [operations.md](operations.md#execute-a-command-inside-a-container) |

### Adding New Services

| Step | Action | Reference |
|------|--------|-----------|
| 1. Edit compose file | Edit `compose/docker-compose.yml` locally | [operations.md](operations.md#adding-a-new-service) |
| 2. Commit & push | `git add . && git commit -m "..." && git push` | [operations.md](operations.md#adding-a-new-service) |
| 3. Sync to NAS01 | `scp compose/docker-compose.yml admin@192.168.1.33:/share/Container/container-station-data/application/homelab/` | [operations.md](operations.md#adding-a-new-service) |
| 4. Start container | Use compose up command | [operations.md](operations.md#adding-a-new-service) |
| 5. Add NPM proxy host | If external access needed | [external-access.md](external-access.md#adding-a-new-proxy-host) |
| 6. Update README | Add to container table | [operations.md](operations.md#adding-a-new-service) |

---

## 🌐 Network & DNS

### DNS Management

| Task | Tool | Reference |
|------|------|-----------|
| **LAN DNS (Technitium)** | Web UI: http://192.168.1.33:5380 | [CLAUDE.md](../CLAUDE.md#dns-management) |
| Add local DNS record | Technitium Web UI → Zones | [external-access.md](external-access.md) |
| **External DNS (Cloudflare)** | API via curl | [CLAUDE.md](../CLAUDE.md#dns-management) |
| List Cloudflare DNS records | `curl -s "https://api.cloudflare.com/client/v4/zones/YOUR_CF_ZONE_ID/dns_records" -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"` | [external-access.md](external-access.md#managing-dns-via-api) |
| Add Cloudflare DNS record | See curl POST command | [external-access.md](external-access.md#managing-dns-via-api) |

### Nginx Proxy Manager

| Task | Location | Reference |
|------|----------|-----------|
| Access NPM admin UI | http://192.168.1.33:81 | [external-access.md](external-access.md#nginx-proxy-manager) |
| Add new proxy host | NPM UI → Proxy Hosts → Add | [external-access.md](external-access.md#adding-a-new-proxy-host) |
| Renew wildcard cert | NPM UI → SSL Certificates → Renew | [external-access.md](external-access.md#wildcard-certificate) |
| Current proxy hosts | See table | [external-access.md](external-access.md#current-proxy-hosts) |

### Port Forwards

| Task | Location | Reference |
|------|----------|-----------|
| Manage port forwards | UniFi OS → Firewall & Security → Port Forwarding | [external-access.md](external-access.md#unifi-port-forwards) |
| Current forwards | See table (80, 443, 32400) | [external-access.md](external-access.md#unifi-port-forwards) |

---

## 💾 Storage & Backups

### TrueNAS Management

| Task | Method | Reference |
|------|--------|-----------|
| Access TrueNAS UI | https://192.168.1.31 | [storage.md](storage.md) |
| Check pool health | `ssh homelab-svc@192.168.1.31 'midclt call pool.query'` | [storage.md](storage.md#querying-truenas-via-ssh) |
| Check NFS shares | `ssh homelab-svc@192.168.1.31 'midclt call sharing.nfs.query'` | [storage.md](storage.md#querying-truenas-via-ssh) |
| Check dataset usage | `ssh homelab-svc@192.168.1.31 'midclt call pool.dataset.query'` | [storage.md](storage.md#querying-truenas-via-ssh) |
| ZFS scrub status | `ssh homelab-svc@192.168.1.31 'zpool status media'` | [storage.md](storage.md#querying-truenas-via-ssh) |

### NFS Mounts

| Task | Command | Reference |
|------|---------|-----------|
| Check NFS mounts | `ssh admin@192.168.1.33 'mount \| grep nfs'` | [operations.md](operations.md#checking-disk--nfs) |
| Verify NFS access | `ssh admin@192.168.1.33 'ls /share/external/.nd/1000/ \| head -5'` | [operations.md](operations.md#checking-disk--nfs) |
| NFS share paths | See table | [storage.md](storage.md#nfs-shares) |

### Duplicati Backups

| Task | Method | Reference |
|------|--------|-----------|
| Access Duplicati UI | http://192.168.1.33:8200 | [operations.md](operations.md#duplicati-backups) |
| Run manual backup | See docker exec command | [operations.md](operations.md#duplicati-backups) |
| List backup versions | See docker exec command | [operations.md](operations.md#duplicati-backups) |
| Backup schedule | Daily @ 2:00 AM | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |
| Backup destination | NAS02 `/mnt/media/backups` | [storage.md](storage.md#zfs-datasets) |
| Import backup job | Use `duplicati/homelab-appdata-backup.json` | [README.md](../README.md#repository-structure) |

---

## 🔧 Service-Specific Operations

### Plex

| Task | Location | Reference |
|------|----------|-----------|
| Access Plex | http://192.168.1.33:32400/web | [README.md](../README.md#container-stack) |
| External access | https://plex.yourdomain.com | [external-access.md](external-access.md#current-proxy-hosts) |
| Library path | `/media` (mapped from media_ds) | [migration-plan.md](migration-plan.md#phase-4--verify-internal-paths) |

### Sonarr / Radarr / Radarr4K

| Task | Port | Reference |
|------|------|-----------|
| Sonarr UI | http://192.168.1.33:8989 | [README.md](../README.md#container-stack) |
| Radarr UI | http://192.168.1.33:7878 | [README.md](../README.md#container-stack) |
| Radarr4K UI | http://192.168.1.33:7070 | [README.md](../README.md#container-stack) |
| Root folders | `/storage/media_ds/tv` (Sonarr), `/storage/media_ds/movies` (Radarr) | [migration-plan.md](migration-plan.md#phase-4--verify-internal-paths) |
| Download path | `/storage/downloads_ds/completed` | [migration-plan.md](migration-plan.md#phase-4--verify-internal-paths) |

### Recyclarr (Quality Profile Sync)

| Task | Command | Reference |
|------|---------|-----------|
| Manual sync | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec recyclarr recyclarr sync'` | [operations.md](operations.md#recyclarr-quality-profile-sync) |
| Check logs | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs recyclarr'` | [operations.md](operations.md#recyclarr-quality-profile-sync) |
| Config file | `recyclarr/recyclarr.yml` → `/share/appdata/recyclarr/recyclarr.yml` | [operations.md](operations.md#recyclarr-quality-profile-sync) |
| Schedule | Daily @ midnight | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |

### Tdarr (Media Transcoding)

| Task | Location | Reference |
|------|----------|-----------|
| Access Tdarr UI | http://192.168.1.33:8265 | [operations.md](operations.md#tdarr-media-transcoding) |
| Flow documentation | [tdarr/FLOWS.md](../tdarr/FLOWS.md) | Complete flow architecture |
| Check logs | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs tdarr'` | [operations.md](operations.md#tdarr-media-transcoding) |
| Reset stuck files | See reset script | [operations.md](operations.md#tdarr-media-transcoding) |
| Import flows | Tdarr UI → Flows → Import | [tdarr/FLOWS.md](../tdarr/FLOWS.md#importing-flows) |
| Flow files | `flows/normalize-mkv-h264-aac-stereo.json` | [tdarr/FLOWS.md](../tdarr/FLOWS.md#flow-files-source-of-truth) |

### TransmissionVPN

| Task | Command | Reference |
|------|---------|-----------|
| Access Transmission UI | http://192.168.1.33:9091 | [README.md](../README.md#container-stack) |
| Verify VPN connection | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec transmissionvpn curl -s ifconfig.me'` | [operations.md](operations.md#verifying-the-vpn) |
| Expected result | PIA IP (not YOUR_PUBLIC_IP) | [operations.md](operations.md#verifying-the-vpn) |

### Watchtower (Auto-Updates)

| Task | Command | Reference |
|------|---------|-----------|
| Check recent updates | `ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs watchtower --tail 50'` | [operations.md](operations.md#watchtower-auto-updates) |
| Update schedule | Nightly @ 4:00 AM | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |
| Exclude from updates | Add label: `com.centurylinklabs.watchtower.enable=false` | [operations.md](operations.md#watchtower-auto-updates) |

### Uptime Kuma (Monitoring)

| Task | Location | Reference |
|------|----------|-----------|
| Access Uptime Kuma | http://192.168.1.33:3001 | [README.md](../README.md#container-stack) |
| Monitor configuration | Max retries: 3 (prevents false alarms) | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |

### Tautulli (Plex Analytics)

| Task | Location | Reference |
|------|----------|-----------|
| Access Tautulli | http://192.168.1.33:8181 | [README.md](../README.md#container-stack) |
| API queries | See curl examples | [operations.md](operations.md#useful-tautulli-queries) |

---

## 🚨 Disaster Recovery

### Full Stack Recovery

| Step | Action | Reference |
|------|--------|-----------|
| **Prerequisites** | Fresh x86_64 Debian/Ubuntu host, network access to NAS02, GitHub SSH key | [restore.sh](../dr/restore.sh) |
| **Secrets file** | Copy `dr/.secrets.template` to `~/.homelab.secrets` and fill in | [README.md](../README.md#disaster-recovery) |
| **Run restore** | `./dr/restore.sh` | [README.md](../README.md#disaster-recovery) |
| **Interactive checklist** | Open `dr/playbook.html` in browser | [README.md](../README.md#disaster-recovery) |
| **Target RTO** | ~30 minutes | [README.md](../README.md#disaster-recovery) |
| **Last tested** | May 2026 (22 min actual) | [README.md](../README.md#disaster-recovery) |

### Post-DR Tasks

| Task | Action | Reference |
|------|--------|-----------|
| Update port forwards | Point to new host IP in UniFi | [external-access.md](external-access.md#after-dr-restore) |
| Verify NPM config | Check proxy hosts restored | [external-access.md](external-access.md#after-dr-restore) |
| Check wildcard cert | Renew if needed | [external-access.md](external-access.md#after-dr-restore) |
| Test subdomains | `curl -I https://plex.yourdomain.com` | [external-access.md](external-access.md#after-dr-restore) |

---

## 🔄 Configuration Updates

### Updating Compose File

| Step | Command | Reference |
|------|---------|-----------|
| 1. Edit locally | Edit `compose/docker-compose.yml` | [operations.md](operations.md#updating-the-compose-file--config) |
| 2. Commit & push | `git add . && git commit -m "..." && git push` | [operations.md](operations.md#updating-the-compose-file--config) |
| 3. Sync to NAS01 | `scp compose/docker-compose.yml admin@192.168.1.33:/share/Container/container-station-data/application/homelab/` | [operations.md](operations.md#updating-the-compose-file--config) |
| 4. Restart services | Use compose up command | [operations.md](operations.md#updating-the-compose-file--config) |

### Updating Recyclarr Config

| Step | Command | Reference |
|------|---------|-----------|
| 1. Edit locally | Edit `recyclarr/recyclarr.yml` | [operations.md](operations.md#updating-the-compose-file--config) |
| 2. Sync to NAS01 | `scp recyclarr/recyclarr.yml admin@192.168.1.33:/share/appdata/recyclarr/recyclarr.yml` | [operations.md](operations.md#updating-the-compose-file--config) |
| 3. Restart Recyclarr | `docker compose up -d recyclarr` | [operations.md](operations.md#updating-the-compose-file--config) |

---

## 🔐 Security & Access

### Secrets Management

| File | Location | Purpose | Committed? |
|------|----------|---------|------------|
| `.env` | NAS01: `/share/Container/container-station-data/application/homelab/.env` | Live container secrets | ❌ Never |
| `.env.template` | Repo: `compose/.env.template` | Template showing required vars | ✅ Yes |
| `.homelab.secrets` | `~/.homelab.secrets` | DR restore secrets | ❌ Never |
| `.secrets.template` | Repo: `dr/.secrets.template` | DR secrets template | ✅ Yes |

### Access Points

| Service | URL | Auth Required |
|---------|-----|---------------|
| **External (via NPM)** | | |
| Plex | https://plex.yourdomain.com | Plex account |
| Seerr | https://seerr.yourdomain.com | Seerr account |
| Stirling PDF | https://pdf.yourdomain.com | None |
| **LAN Only** | | |
| NAS01 Admin | https://192.168.1.33:8443 | QTS credentials |
| TrueNAS | https://192.168.1.31 | TrueNAS credentials |
| NPM Admin | http://192.168.1.33:81 | NPM credentials |
| All other services | See port map | Various |

---

## 📊 Monitoring & Maintenance

### Regular Maintenance Tasks

| Frequency | Task | Reference |
|-----------|------|-----------|
| **Daily** | Automated backups (2 AM) | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |
| **Daily** | Watchtower updates (4 AM) | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |
| **Daily** | Recyclarr sync (midnight) | [CLAUDE.md](../CLAUDE.md#container-stack-overview) |
| **Weekly** | Check Uptime Kuma for alerts | [README.md](../README.md#container-stack) |
| **Weekly** | Review Duplicati backup logs | [operations.md](operations.md#duplicati-backups) |
| **Monthly** | ZFS scrub (automatic) | [storage.md](storage.md#maintenance) |
| **Monthly** | SMART tests (automatic) | [storage.md](storage.md#maintenance) |
| **Quarterly** | Test DR restore procedure | [README.md](../README.md#disaster-recovery) |
| **As needed** | Review Tautulli stats | [operations.md](operations.md#useful-tautulli-queries) |

### Health Checks

| Check | Command | Expected Result |
|-------|---------|-----------------|
| All containers running | `docker compose ps` | All "Up" status |
| NFS mounts accessible | `mount \| grep nfs` | 3 mounts shown |
| VPN connected | `docker exec transmissionvpn curl -s ifconfig.me` | PIA IP (not home IP) |
| DNS resolving | `nslookup google.com 192.168.1.33` | Valid response |
| Backups current | Check Duplicati UI | Last run < 24h ago |
| Disk space | `df -h` | Sufficient free space |

---

## 🚧 Planned Implementations

### IoT VLAN Migration

| Task | Status | Reference |
|------|--------|-----------|
| Create IoT network in UniFi | Planned | [iot-vlan-plan.md](iot-vlan-plan.md#implementation-steps) |
| Configure firewall rules | Planned | [iot-vlan-plan.md](iot-vlan-plan.md#firewall-rules-3-rules-in-order) |
| Create IoT WiFi SSID | Planned | [iot-vlan-plan.md](iot-vlan-plan.md#implementation-steps) |
| Set DHCP reservations | Planned | [iot-vlan-plan.md](iot-vlan-plan.md#implementation-steps) |
| Migrate wired devices (10) | Planned | [iot-vlan-plan.md](iot-vlan-plan.md#configure-wired-switch-ports) |
| Migrate WiFi devices (2) | Planned | [iot-vlan-plan.md](iot-vlan-plan.md#move-wifi-iot-devices) |

### UPS Integration

| Task | Status | Reference |
|------|--------|-----------|
| Obtain APC USB cable | **Blocked** | [ups-integration.md](ups-integration.md#blocker) |
| Connect cable to NAS02 | Pending | [ups-integration.md](ups-integration.md#implementation-steps) |
| Configure TrueNAS NUT master | Pending | [ups-integration.md](ups-integration.md#implementation-steps) |
| Configure NAS01 NUT client | Pending | [ups-integration.md](ups-integration.md#implementation-steps) |
| Test shutdown sequence | Pending | [ups-integration.md](ups-integration.md#implementation-steps) |

---

## 📚 Complete Documentation Index

### Core Documentation

- [README.md](../README.md) - Repository overview, hardware, container stack
- [CLAUDE.md](../CLAUDE.md) - AI assistant context and operational notes
- [CHANGELOG.md](../CHANGELOG.md) - Infrastructure change history
- [change-checklist.md](change-checklist.md) - ✅ What to update for every type of change

### Operations

- [operations.md](operations.md) - Day-to-day operations and commands
- [external-access.md](external-access.md) - DNS, NPM, port forwarding
- [storage.md](storage.md) - TrueNAS, NFS, ZFS configuration
- [network-diagram.md](network-diagram.md) - Visual network topology

### Planning & Migration

- [migration-plan.md](migration-plan.md) - VM to Container Station migration
- [iot-vlan-plan.md](iot-vlan-plan.md) - IoT network segmentation
- [ups-integration.md](ups-integration.md) - UPS/NUT integration plan

### Disaster Recovery

- [dr/restore.sh](../dr/restore.sh) - Automated DR restore script
- [dr/playbook.html](../dr/playbook.html) - Interactive DR checklist
- [dr/.secrets.template](../dr/.secrets.template) - DR secrets template

### Service-Specific

- [tdarr/FLOWS.md](../tdarr/FLOWS.md) - Tdarr transcoding flow architecture
- [tdarr/flows/normalize-mkv-h264-aac-stereo.json](../tdarr/flows/normalize-mkv-h264-aac-stereo.json) - Consolidated flow: H.264 MKV + loudnorm AAC stereo (-W-fcbKec)

### Configuration

- [compose/docker-compose.yml](../compose/docker-compose.yml) - Container stack definition
- [compose/.env.template](../compose/.env.template) - Environment variable template
- [recyclarr/recyclarr.yml](../recyclarr/recyclarr.yml) - Quality profile sync config
- [duplicati/homelab-appdata-backup.json](../duplicati/homelab-appdata-backup.json) - Backup job config

---

## 🔗 Quick Links

### Web Interfaces (LAN)

```
NAS01:           https://192.168.1.33:8443
TrueNAS:        https://192.168.1.31
NPM Admin:      http://192.168.1.33:81
Plex:           http://192.168.1.33:32400/web
Sonarr:         http://192.168.1.33:8989
Radarr:         http://192.168.1.33:7878
Radarr4K:       http://192.168.1.33:7070
Prowlarr:       http://192.168.1.33:9696
Transmission:   http://192.168.1.33:9091
Seerr:          http://192.168.1.33:5055
Tdarr:          http://192.168.1.33:8265
Tautulli:       http://192.168.1.33:8181
Duplicati:      http://192.168.1.33:8200
Uptime Kuma:    http://192.168.1.33:3001
Technitium:     http://192.168.1.33:5380
Organizr:       http://192.168.1.33:8006
```

### External Access

```
Plex:           https://plex.yourdomain.com
Seerr:          https://seerr.yourdomain.com
Stirling PDF:   https://pdf.yourdomain.com
```

---

## 📞 Support Resources

- **GitHub Repository**: https://github.com/yourusername/homelab
- **Cloudflare Dashboard**: https://dash.cloudflare.com
- **UniFi Network**: https://unifi.ui.com
- **TRaSH Guides**: https://trash-guides.info

---

*Last Updated: 2026-06-21*