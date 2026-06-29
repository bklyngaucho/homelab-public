# External Access — DNS, NPM, and Port Forwards

This document covers how external traffic reaches the homelab: Cloudflare DNS,
UniFi port forwards, and Nginx Proxy Manager proxy hosts.

---

## Architecture Overview

```
Internet
  │
  ▼
Cloudflare (DNS + proxying)
  │  *.yourdomain.com → YOUR_PUBLIC_IP (home WAN IP)
  ▼
UniFi UXG-Fiber (port forwards)
  │  TCP 80, 443 → NAS01 (NPM)
  │  TCP 32400   → NAS01 (Plex direct)
  ▼
Nginx Proxy Manager (npm container, port 81 admin)
  │  plex.yourdomain.com    → plex:32400
  │  seerr.yourdomain.com   → seerr:5055
  │  pdf.yourdomain.com     → stirling-pdf:8080
  ▼
Containers on homelab Docker network
```

**Key principle:** A wildcard `*.yourdomain.com` A record points to the home IP.
New services never need a DNS record — just an NPM proxy host entry.

---

## Cloudflare DNS

**Domain:** `yourdomain.com`  
**Zone ID:** `YOUR_CF_ZONE_ID`  
**API Token:** In `~/.homelab.secrets` as `CLOUDFLARE_API_TOKEN`

### Current DNS records

| Type | Name | Value | Proxied |
|---|---|---|---|
| A | `*.yourdomain.com` | `YOUR_PUBLIC_IP` | Yes |
| A | `yourdomain.com` | `YOUR_PUBLIC_IP` | Yes |

The wildcard covers all subdomains. With Cloudflare proxying enabled, actual
home IP is hidden from clients — they see Cloudflare IPs.

### Managing DNS via API

```bash
# Load token
source ~/.homelab.secrets

# List all DNS records
curl -s "https://api.cloudflare.com/client/v4/zones/YOUR_CF_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" | jq '.result[] | {name, type, content}'

# Add a new A record (only needed if wildcard doesn't cover it for some reason)
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/YOUR_CF_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"newservice.yourdomain.com","content":"YOUR_PUBLIC_IP","proxied":true}'
```

> The wildcard means you almost never need to add DNS records manually.
> Adding an NPM proxy host is sufficient for any new service.

---

## UniFi Port Forwards

Configure in UniFi OS → Firewall & Security → Port Forwarding.

| Rule | Protocol | External Port | Forward To | Internal Port | Purpose |
|---|---|---|---|---|---|
| Plex Direct | TCP | 32400 | 192.168.1.33 | 32400 | Plex (bypasses NPM) |
| NPM HTTP | TCP | 80 | 192.168.1.33 | 80 | NPM / Let's Encrypt challenges |
| NPM HTTPS | TCP | 443 | 192.168.1.33 | 443 | NPM HTTPS traffic |

> **During DR:** Update the forward destination IPs to the DR host's IP.
> The port numbers stay the same.

> **QTS note:** NAS01's admin UI moved to port 8443 to free up 443 for NPM.

---

## Nginx Proxy Manager

**Admin UI:** http://192.168.1.33:81  
**Container:** `npm`  
**Appdata:** `/share/appdata/npm/`

NPM handles TLS termination using a wildcard Let's Encrypt cert issued via
Cloudflare DNS challenge (no need to open port 80 for ACME challenges — the
`CLOUDFLARE_API_TOKEN` env var handles it automatically).

### Wildcard certificate

| Field | Value |
|---|---|
| Domain | `*.yourdomain.com` |
| DNS Provider | Cloudflare |
| Renewal | Automatic (90-day Let's Encrypt, renews at 60 days) |
| API Token | From `CLOUDFLARE_API_TOKEN` in `.env` |

### Current proxy hosts

| Subdomain | Forward To | Notes |
|---|---|---|
| `plex.yourdomain.com` | `http://plex:32400` | Plex Web UI via proxy |
| `seerr.yourdomain.com` | `http://seerr:5055` | Jellyseerr media requests |
| `pdf.yourdomain.com` | `http://stirling-pdf:8080` | Stirling PDF tools |

All three use the `*.yourdomain.com` wildcard cert. WebSockets are enabled
for Plex. Access lists are not configured (public, relies on app-level auth).

### Adding a new proxy host

1. NPM admin UI → Proxy Hosts → Add Proxy Host
2. **Domain Names:** `newservice.yourdomain.com`
3. **Scheme:** `http`
4. **Forward Hostname/IP:** container name (e.g. `organizr`)
5. **Forward Port:** container's internal port (e.g. `8006`)
6. **SSL tab:** Select `*.yourdomain.com` cert → Enable Force SSL
7. Save. Done — no DNS record needed.

---

## After DR Restore

1. Update UniFi port forwards to point at the DR host IP (not 192.168.1.33)
2. NPM config is restored from Duplicati — proxy hosts should come up automatically
3. Verify the wildcard cert is still valid (check NPM → SSL Certificates tab)
4. If the cert needs renewal, trigger it manually: NPM → SSL Certificates → Renew
5. Test each subdomain: `curl -I https://plex.yourdomain.com`
