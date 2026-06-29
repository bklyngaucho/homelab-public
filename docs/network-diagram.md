# Network Diagram

Visual topology of the homelab infrastructure showing network flow, services, and connectivity.

---

## Physical Network Topology

```
                                    Internet
                                       │
                                       │ 2 Gbps Fiber
                                       ▼
                            ┌──────────────────────┐
                            │  UniFi UXG-Fiber     │
                            │  192.168.1.1         │
                            │  Firewall / Router   │
                            └──────────┬───────────┘
                                       │ 1GbE uplink
                                       ▼
                            ┌──────────────────────┐
                            │  Zyxel XGS1210-12    │
                            │  192.168.1.2         │
                            │  2×10GbE 2×2.5GbE    │
                            │  8×1GbE              │
                            └──┬───────────────┬───┘
                               │ 2×1GbE LAG    │ 1GbE
                               │ (ports 7+8,   │ (eno1 mgmt)
                               │  Balance-XOR) │
                    ┌──────────┘          ┌────┘
                    │                     │
                    ▼                     ▼
         ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
         │ NAS01    │   │ NAS02       │   │ Lenovo P360     │
         │ Mgmt: 192.168.1.33  │ Mgmt: 192.168.1.31  │ (AI Workstation)│
         │ (bond0: Adap 1+2)   │ (eno1, 1GbE)    │   │ Ollama/WebUI    │
         │ Primary Compute │   │ TrueNAS SCALE   │   │ (Separate)      │
         │ Container Stn   │   │ ZFS Storage     │   └─────────────────┘
         └────────┬────────┘   └────────┬────────┘
                  │                     │
                  │ 10GbE direct cable  │
                  │ (Adapter 5 ↔ ens2f0)│
                  │ 10.10.10.33 ◄──────►10.10.10.31
                  │ MTU 9000            │ MTU 9000
                  └─────────────────────┘
                   Dedicated Storage LAN
                   ~780 MB/s read  ~1 GB/s write
```

---

## Container Network Architecture

```
                                External Traffic
                                       │
                                       │ Port Forwards:
                                       │ - 80/443 → NPM
                                       │ - 32400 → Plex
                                       ▼
                            ┌──────────────────────┐
                            │  Nginx Proxy Manager │
                            │  (npm container)     │
                            │  Wildcard SSL Cert   │
                            └──────────┬───────────┘
                                       │
                                       │ homelab Docker network (bridge mode)
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
         ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
         │ plex:32400      │ │ seerr:5055      │ │ stirling-pdf    │
         │ (reads NFS      │ │                 │ │ :8080           │
         │  filesystem)    │ │                 │ │                 │
         └─────────────────┘ └─────────────────┘ └─────────────────┘

  ARR Stack (inter-service communication via container names):

  ┌──────────┐  ┌──────────┐  ┌──────────┐    ┌──────────────┐
  │ sonarr   │  │ radarr   │  │ bazarr   │    │ prowlarr     │
  │ :8989    │  │ :7878    │  │ :6767    │    │ :9696        │
  │          │  │ radarr4k │  │          │    │   │          │
  └────┬─────┘  └────┬─────┘  └──────────┘    └───┼──────────┘
       │              │                            │
       │ API calls to indexers via Prowlarr        │
       └──────────────────────────────────────┐   │
                                              ▼   ▼
                                    ┌─────────────────┐
                                    │ transmissionvpn │
                                    │ :9091           │
                                    │ (PIA VPN)       │
                                    └─────────────────┘

  Note: Plex does NOT communicate with the ARR stack. It reads
  directly from the NFS media share. ARR apps move completed
  files into the media share; Plex scans and serves them.
```

---

## DNS Flow

```
                        LAN Client (192.168.1.x)
                                 │
                                 │ DNS Query
                                 ▼
                    ┌─────────────────────────┐
                    │  Technitium DNS         │
                    │  192.168.1.33:53        │
                    │  (Primary DNS)          │
                    └────────┬────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
    ┌───────────────────┐     ┌──────────────────┐
    │ Local Zone        │     │ Upstream         │
    │ *.yourdomain.com │     │ 1.1.1.1          │
    │ → 192.168.1.33    │     │ 8.8.8.8          │
    │ (No hairpinning)  │     │                  │
    └───────────────────┘     └──────────────────┘
                │
                │ Ad Blocking:
                │ - OISD Basic
                │ - AdGuard DNS
                │ (Auto-update daily)
                ▼
            Response to Client
```

---

## External Access Flow

```
    Internet Client
         │
         │ HTTPS Request
         │ https://plex.yourdomain.com
         ▼
┌─────────────────────┐
│  Cloudflare         │
│  DNS + Proxy        │
│  *.yourdomain.com  │
│  → YOUR_PUBLIC_IP    │
└──────────┬──────────┘
           │
           │ Proxied through Cloudflare
           │ (hides real home IP)
           ▼
┌─────────────────────┐
│  UniFi UXG-Fiber    │
│  Port Forward       │
│  443 → 192.168.1.33 │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Nginx Proxy Mgr    │
│  TLS Termination    │
│  Wildcard Cert      │
│  (Let's Encrypt)    │
└──────────┬──────────┘
           │
           │ HTTP (internal)
           ▼
┌─────────────────────┐
│  plex:32400         │
│  (container)        │
└─────────────────────┘
```

---

## Storage Architecture

```
┌─────────────────────────────────────────────────────────┐
│  NAS02 — TrueNAS SCALE                    │
│  192.168.1.31                                           │
│                                                         │
│  ZFS Pool: media (RAID 10 — 4× mirrored vdevs)         │
│  ┌───────────────────────────────────────────────┐     │
│  │  mirror-0  mirror-1  mirror-2  mirror-3       │     │
│  │  (2×10TB)  (2×10TB)  (2×10TB)  (2×10TB)       │     │
│  │                                                │     │
│  │  Capacity: 36.33 TB usable                    │     │
│  │  Used: ~17 TB  Free: ~19 TB                   │     │
│  └───────────────────────────────────────────────┘     │
│                                                         │
│  Datasets:                                              │
│  ├─ media/media_ds      (17.4TB) — Media library       │
│  ├─ media/downloads_ds  (73GB)   — Download staging    │
│  └─ media/backups       (67GB)   — Duplicati backups   │
│                                                         │
│  Boot drives: 2× SanDisk M.2 128GB SSDs (not SLOG/L2ARC)│
└─────────────────────────────────────────────────────────┘
                          │
                          │ NFS Exports (10.10.10.0/24 + 192.168.1.0/24)
                          │ - no_root_squash enabled
                          │ - maproot: root
                          │
                          │ 10GbE direct link (MTU 9000)
                          │ ens2f0: 10.10.10.31 ◄──────► 10.10.10.33
                          │ ~780 MB/s read / ~1 GB/s write
                          ▼
┌─────────────────────────────────────────────────────────┐
│  NAS01 — Container Station                      │
│  Mgmt:    192.168.1.33 (bond0: Adapter 1+2, 2×1GbE,   │
│           Balance-XOR, Zyxel LAG 3 ports 7+8)         │
│  Storage: 10.10.10.33  (Adapter 5, 10GbE direct)      │
│                                                         │
│  NFS Mounts (HybridMount, server: 10.10.10.31):        │
│  ├─ media_ds     → /mnt/media/media_ds                  │
│  ├─ downloads_ds → /mnt/media/downloads_ds              │
│  └─ backups      → /mnt/media/backups                   │
│  (Old 192.168.1.31 mounts retained as disabled fallback)│
│                                                         │
│  Local Storage:                                         │
│  ├─ /share/appdata/<service>/ — Container configs      │
│  └─ /share/CACHEDEV5_DATA/tdarr-temp/ — Transcode      │
│                                                         │
│  Containers (22):                                       │
│  └─ All mount NFS shares via Docker volumes            │
└─────────────────────────────────────────────────────────┘
```

---

## Planned IoT VLAN Topology

```
                    ┌──────────────────────┐
                    │  UniFi UXG-Fiber     │
                    │  192.168.1.1         │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
    ┌───────────────────┐         ┌───────────────────┐
    │  Main LAN         │         │  IoT VLAN         │
    │  192.168.1.0/24   │         │  10.20.0.0/24     │
    │  VLAN 1 (default) │         │  VLAN 20          │
    └───────────────────┘         └───────────────────┘
            │                              │
            │                              │
    ┌───────┴────────┐          ┌─────────┴──────────┐
    │ Trusted Devices│          │ IoT Devices (12)   │
    │ - NAS01         │          │ - Roku TVs (2)     │
    │ - TrueNAS      │          │ - Wyze Cams (2)    │
    │ - Workstations │          │ - Echo Studio      │
    │ - Phones       │          │ - Nest devices     │
    └────────────────┘          │ - Smart appliances │
                                └────────────────────┘

    Firewall Rules (IoT → LAN):
    ┌────────────────────────────────────────────┐
    │ 1. Allow → 192.168.1.33:32400 (Plex)      │
    │ 2. Allow → 192.168.1.33:53 (DNS)          │
    │ 3. Block → 192.168.1.0/24 (All other LAN) │
    └────────────────────────────────────────────┘
```

---

## Port Map Reference

### External Ports (Port Forwards)

| Port | Protocol | Destination | Service |
|------|----------|-------------|---------|
| 80 | TCP | 192.168.1.33 | NPM (Let's Encrypt challenges) |
| 443 | TCP | 192.168.1.33 | NPM (HTTPS traffic) |
| 32400 | TCP | 192.168.1.33 | Plex (direct access, bypasses NPM) |

### Internal Service Ports

| Service | Port | Access |
|---------|------|--------|
| Plex | 32400 | LAN + External (via NPM or direct) |
| Sonarr | 8989 | LAN only |
| Radarr | 7878 | LAN only |
| Radarr4K | 7070 | LAN only (mapped from 7878) |
| Bazarr | 6767 | LAN only |
| Prowlarr | 9696 | LAN only |
| FlareSolverr | 8191 | LAN only (internal to arr stack) |
| TransmissionVPN | 9091 | LAN only |
| Seerr | 5055 | LAN + External (via NPM) |
| Organizr | 8006 | LAN only |
| Agregarr | 7171 | LAN only |
| Tautulli | 8181 | LAN only |
| Tdarr | 8265 | LAN only (Web UI) |
| Tdarr Node | 8266 | LAN only (Node communication) |
| Duplicati | 8200 | LAN only |
| Uptime Kuma | 3001 | LAN only |
| NPM Admin | 81 | LAN only |
| Stirling PDF | 8585 | LAN + External (via NPM) |
| Technitium DNS | 53 | LAN only (bound to 192.168.1.33) |
| Technitium Web | 5380 | LAN only |
| TrueNAS | 443 | LAN only (https://192.168.1.31) |
| NAS01 Admin | 8443 | LAN only (moved from 443) |

---

## IP Address Allocation

### Infrastructure — Main LAN (192.168.1.0/24)

| Device | IP | Role |
|--------|-----|------|
| UniFi UXG-Fiber | 192.168.1.1 | Router/Firewall |
| Zyxel XGS1210-12 | 192.168.1.2 | Switch |
| NAS02 / TrueNAS | 192.168.1.31 | NAS (management, eno1) |
| NAS01 | 192.168.1.33 | Compute (management, bond0: Adapter 1+2, Balance-XOR, 2×1GbE, Zyxel LAG 3 ports 7+8) |

### Infrastructure — Storage LAN (10.10.10.0/24, direct 10GbE cable)

| Device | IP | Interface | Notes |
|--------|-----|-----------|-------|
| NAS02 / TrueNAS | 10.10.10.31 | ens2f0 (Chelsio) | MTU 9000 |
| NAS01 | 10.10.10.33 | Adapter 5 (Aquantia QM2-2P10G1TB) | MTU 9000 |

### Reserved for IoT VLAN (Planned)

| Device | Current IP | Future IP | Type |
|--------|------------|-----------|------|
| Echo Studio | 192.168.1.235 | 10.20.0.10 | Wired |
| Aura Frame | 192.168.1.166 | 10.20.0.11 | Wired |
| Nest Connect | 192.168.1.200 | 10.20.0.12 | Wired |
| RoboPoopBox | 192.168.1.201 | 10.20.0.13 | Wired |
| Samsung Dishwasher | 192.168.1.153 | 10.20.0.14 | Wired |
| Smoke Alarm | 192.168.1.163 | 10.20.0.15 | Wired |
| Wyze Cam (Basement) | 192.168.1.152 | 10.20.0.16 | Wired |
| Wyze Cam Pan | 192.168.1.165 | 10.20.0.17 | Wired |
| LG AC | 192.168.1.221 | 10.20.0.18 | Wired |
| ESP Device | 192.168.1.176 | 10.20.0.19 | Wired |
| 65" TCL Roku TV | 192.168.1.150 | 10.20.0.20 | WiFi |
| Roku Ultra | 192.168.1.231 | 10.20.0.21 | WiFi |

---

## Network Security Layers

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Cloudflare Proxy                              │
│  - Hides real home IP                                   │
│  - DDoS protection                                      │
│  - WAF (Web Application Firewall)                       │
└─────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: UniFi Firewall                                │
│  - Port forwards (80, 443, 32400 only)                  │
│  - IoT VLAN isolation (planned)                         │
│  - LAN-only access for admin interfaces                 │
└─────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Nginx Proxy Manager                           │
│  - TLS termination (wildcard cert)                      │
│  - Subdomain routing                                    │
│  - Force HTTPS                                          │
└─────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Application-Level Auth                        │
│  - Plex authentication                                  │
│  - Seerr user accounts                                  │
│  - Arr stack API keys                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Backup Flow

```
    ┌─────────────────────────────────────────┐
    │  Duplicati Container                    │
    │  Schedule: Daily @ 2:00 AM              │
    └──────────────┬──────────────────────────┘
                   │
                   │ Reads from:
                   ▼
    ┌─────────────────────────────────────────┐
    │  /share/appdata/<service>/              │
    │  (All container configs & databases)    │
    │                                         │
    │  Excludes:                              │
    │  - Plex cache/codecs/logs               │
    │  - Transmission torrents                │
    │  - NPM Let's Encrypt certs (regen)      │
    └──────────────┬──────────────────────────┘
                   │
                   │ Encrypts & compresses
                   │ (AES-256, passphrase from .env)
                   ▼
    ┌─────────────────────────────────────────┐
    │  NAS02 NFS Share: /mnt/media/backups     │
    │  Mounted at: /backups in container      │
    │                                         │
    │  Backup size: ~46 GB (156k files)       │
    │  Retention: 30 days                     │
    └─────────────────────────────────────────┘
```

---

## Disaster Recovery Flow

```
    ┌─────────────────────────────────────────┐
    │  Fresh x86_64 Debian/Ubuntu Host        │
    │  (Any machine with network access)      │
    └──────────────┬──────────────────────────┘
                   │
                   │ 1. Clone repo
                   │ 2. Run dr/restore.sh
                   ▼
    ┌─────────────────────────────────────────┐
    │  Automated Restore Process              │
    │  ├─ Install Docker                      │
    │  ├─ Mount NFS shares from NAS02          │
    │  ├─ Restore appdata from Duplicati      │
    │  ├─ Generate .env from secrets          │
    │  └─ Start all containers                │
    └──────────────┬──────────────────────────┘
                   │
                   │ Target RTO: ~30 minutes
                   │ Tested: 22 minutes actual
                   ▼
    ┌─────────────────────────────────────────┐
    │  Full Stack Running                     │
    │  - All 22 containers up                 │
    │  - Plex/Sonarr/Radarr history intact    │
    │  - Ready for traffic                    │
    └─────────────────────────────────────────┘
```

---

## Related Documentation

- [External Access Details](external-access.md) - DNS, NPM, port forwards
- [Storage Configuration](storage.md) - TrueNAS, NFS, ZFS details
- [Operations Guide](operations.md) - Day-to-day management commands
- [IoT VLAN Plan](iot-vlan-plan.md) - Network segmentation design
- [DR Playbook](../dr/playbook.html) - Interactive disaster recovery checklist