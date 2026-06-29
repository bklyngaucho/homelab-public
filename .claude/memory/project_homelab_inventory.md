---
name: homelab-inventory
description: "Full hardware and software inventory of owner's homelab as of June 2026"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5673a38f-2fbf-4500-9a6d-d50b12c3f378
---

# Homelab Inventory (June 2026)

## Network
- **UniFi UXG-Fiber** — router, firewall, DHCP, DNS resolver, IDS/IPS (192.168.1.1)
- **UniFi managed switch(es)** — LAN backbone, VLAN-capable but not yet segmented
- **WAN**: 2 Gbps fiber connection
- **External access**: Cloudflare (yourdomain.com) + Nginx Proxy Manager; wildcard *.yourdomain.com → home IP

## Storage — NAS02 (192.168.1.31)
- OS: TrueNAS SCALE 26.0.0
- ZFS pool `media`: 8× 10TB HDDs in 4× mirrored vdevs (~40TB usable, ~17.5TB used)
  - 6× Seagate Ironwolf 10TB + 2× HGST Ultrastar 10TB
  - 2× SanDisk M.2 128GB SSDs as SLOG/L2ARC
- Datasets: media_ds (17.4TB), downloads_ds (73GB), backups (67GB)
- NFS shares exported to NAS01, LAN-restricted to 192.168.1.0/24
- Service account: homelab-svc (read-only admin, SSH key auth)
- REST API blocked externally; use SSH + midclt for automation

## Compute — NAS01 (192.168.1.33)
- CPU: Intel Core **i7-7700T** (Kaby Lake, 4C/8T, 2.9GHz base / 3.8GHz boost, 35W — upgraded from stock i5)
- GPU: **GTX 1050 Ti** (PCIe) — used by Tdarr for NVENC transcoding
- OS: QTS (web UI on port 8443)
- Runs 19 containers via Container Station (Docker Compose)
- Appdata at /share/appdata/<service>/; Tdarr transcode scratch on NVMe at /share/CACHEDEV5_DATA/tdarr-temp/
- Mounts NAS02 NFS shares as QTS Network Drives (UUID paths)

## Container Stack (21 containers during transition, all on `homelab` Docker network)
- **Media**: Plex (32400), Sonarr (8989), Radarr (7878), Radarr4K (7070 host → 7878 internal), Bazarr (6767)
- **Acquisition**: Prowlarr (9696), Flaresolverr (8191)
  - **TransmissionVPN (9091)** — LEGACY, kept running until queue drains, then remove
  - **gluetun** (VPN container, PIA Montreal, AES-128/port 1198 "normal" preset) + **qbittorrent** (WebUI 9092→8080, API key: qbt_sJZIhzWvrnnvDMNgkkqVX8cb5vkX, password: xoom1234!) — NEW download client; ratio=0 set in qbittorrent so torrents pause immediately for arr import; arr apps point to `gluetun:8080`. After Transmission queue drains: remove transmissionvpn, change gluetun port to 9091:8080.
- **Requests**: Seerr/Overseerr (5055)
- **Transcoding**: Tdarr (8265) — NVENC via GTX 1050 Ti
- **DNS**: Technitium (53/tcp+udp, web UI 5380) — LAN resolver + ad block; bound to 192.168.1.33:53 only
- **Maintenance**: Recyclarr (no UI), Watchtower, Duplicati (8200)
- **Utilities**: Organizr (80→8006), Agregarr (7171), Tautulli (8181), Uptime Kuma (3001), Nginx Proxy Manager (81/443), Stirling PDF (8585)

## AI Workstation — Lenovo ThinkStation P360
- CPU: Intel Core i9-12900 (16 cores)
- GPU: NVIDIA RTX A4500 (20GB VRAM)
- RAM: 128GB DDR5
- Storage: 1TB NVMe
- OS: Windows (bare metal)
- Running: Ollama + Open WebUI
- Not yet a Tdarr node — RTX A4500 NVENC is the obvious upgrade path for more transcode throughput
- Candidate host for IBM Instana Standard Edition single-node (RAM and CPU meet requirements; storage is sufficient for demo mode; would need Linux partition or VM)

## External Access
- Domain: yourdomain.com (Cloudflare, Zone ID: YOUR_CF_ZONE_ID)
- Wildcard A record → home IP (YOUR_PUBLIC_IP), proxied
- NPM proxies: plex.yourdomain.com, seerr.yourdomain.com, pdf.yourdomain.com
- Port forwards: TCP 80/443 → NAS01 (NPM), TCP 32400 → NAS01 (Plex direct)

**Why:** Baseline captured for planning and future conversations.
**How to apply:** Use when suggesting improvements, additions, or architectural changes.
