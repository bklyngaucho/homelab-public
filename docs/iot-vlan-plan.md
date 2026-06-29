# IoT VLAN Implementation Plan

## Overview

Segment IoT/smart home devices onto a dedicated VLAN to isolate them from trusted
infrastructure (NAS01, TrueNAS, personal computers). The UXG-Fiber handles routing and
enforcement between VLANs. All WiFi is served by UniFi APs (Orbi decommissioned).

---

## Design

| Parameter | Value |
|---|---|
| VLAN ID | 20 |
| Name | IoT |
| Subnet | 10.20.0.0/24 |
| Gateway | 10.20.0.1 (UXG-Fiber) |
| DHCP range | 10.20.0.100 – 10.20.0.200 |
| DNS (via DHCP) | 192.168.1.33 (Technitium) |

**Main LAN stays:** 192.168.1.0/24 — all trusted devices unchanged.

---

## Firewall Rules (3 rules, in order)

Create these in UniFi → Security → Traffic & Firewall Rules → LAN Firewall.
Apply to traffic **from** the IoT network.

| # | Action | Source | Destination | Port | Protocol | Purpose |
|---|---|---|---|---|---|---|
| 1 | Allow | IoT (10.20.0.0/24) | 192.168.1.33 | 32400 | TCP | Plex (Roku devices) |
| 2 | Allow | IoT (10.20.0.0/24) | 192.168.1.33 | 53 | TCP + UDP | Technitium DNS |
| 3 | Block | IoT (10.20.0.0/24) | 192.168.1.0/24 | Any | Any | Block all other LAN access |

Internet access from IoT is permitted by default — no rule needed.

---

## Implementation Steps

### 1. Create the IoT Network in UniFi

UniFi → Settings → Networks → Create New Network

- **Name:** IoT
- **Purpose:** Corporate (not Guest — Guest blocks inter-VLAN routing entirely)
- **VLAN ID:** 20
- **Subnet:** 10.20.0.1/24
- **DHCP:** Enabled, range 10.20.0.100–200
- **DHCP Name Server:** Manual → `192.168.1.33`
- **IGMP Snooping:** Enabled (helps Plex discovery if needed)

### 2. Add Firewall Rules

UniFi → Security → Traffic & Firewall Rules → LAN Firewall → Create

Add the 3 rules from the table above in order. Rule order matters — the Block rule
must come last.

### 3. Create IoT WiFi SSID

UniFi → Settings → WiFi → Create New WiFi Network

- **Name:** (e.g. `HomeIoT` or hide it entirely — Rokus can be configured by MAC)
- **Network:** IoT (VLAN 20)
- **Security:** WPA2
- **Band:** 2.4 GHz + 5 GHz (Rokus support both)
- Apply to all UniFi APs

### 2b. Set DHCP Reservations

After creating the IoT network, set fixed IPs for each device before migrating them.
In UniFi → Clients, find each device by MAC and set a fixed IP on the **IoT** network.

**Wired devices:**

| Device | MAC | Reserved IP | Notes |
|---|---|---|---|
| Echo Studio | `98:22:6e:f1:c1:bb` | 10.20.0.10 | Amazon smart speaker |
| Aura Frame | `04:c2:9b:e5:56:0c` | 10.20.0.11 | Digital photo frame |
| Nest-Connect-3C94 | `18:b4:30:fa:3c:94` | 10.20.0.12 | Nest smart home bridge |
| RoboPoopBox | `d8:1f:12:48:3a:35` | 10.20.0.13 | Robot litter box |
| Samsung-Dishwasher | `1c:e8:9e:3e:ce:ad` | 10.20.0.14 | Smart appliance |
| Smoke Alarm (Up) | `18:b4:30:3a:a1:42` | 10.20.0.15 | Smart smoke detector |
| Wyze Cam (Basement1) | `34:ce:00:d2:5a:3b` | 10.20.0.16 | Security camera |
| Wyzecam Pan | `a4:da:22:2e:3f:f4` | 10.20.0.17 | Security camera |
| LGE_AC2_open | `d4:8d:26:28:ea:77` | 10.20.0.18 | LG smart device |
| ESP_D82CFC | `08:3a:8d:d8:2c:fc` | 10.20.0.19 | DIY ESP microcontroller |

**WiFi devices:**

| Device | MAC | Reserved IP | Notes |
|---|---|---|---|
| 65TCLRokuTV | `10:3d:0a:42:9f:49` | 10.20.0.20 | Roku TV |
| RokuUltra | `60:92:c8:8b:3b:30` | 10.20.0.21 | Roku streaming stick |

### 4. Configure Wired Switch Ports

For each wired IoT device, find its switch port in UniFi → Devices → [switch] → Ports,
then set:

- **Port Profile:** Create a new profile named "IoT" with Native VLAN 20, no trunk

**Wired IoT devices to move:**

| Device | MAC | Reserved IP | Current IP |
|---|---|---|---|
| Echo Studio | `98:22:6e:f1:c1:bb` | 10.20.0.10 | 192.168.1.235 |
| Aura Frame | `04:c2:9b:e5:56:0c` | 10.20.0.11 | 192.168.1.166 |
| Nest-Connect-3C94 | `18:b4:30:fa:3c:94` | 10.20.0.12 | 192.168.1.200 |
| RoboPoopBox | `d8:1f:12:48:3a:35` | 10.20.0.13 | 192.168.1.201 |
| Samsung-Dishwasher | `1c:e8:9e:3e:ce:ad` | 10.20.0.14 | 192.168.1.153 |
| Smoke Alarm (Up) | `18:b4:30:3a:a1:42` | 10.20.0.15 | 192.168.1.163 |
| Wyze Cam (Basement1) | `34:ce:00:d2:5a:3b` | 10.20.0.16 | 192.168.1.152 |
| Wyzecam Pan | `a4:da:22:2e:3f:f4` | 10.20.0.17 | 192.168.1.165 |
| LGE_AC2_open | `d4:8d:26:28:ea:77` | 10.20.0.18 | 192.168.1.221 |
| ESP_D82CFC | `08:3a:8d:d8:2c:fc` | 10.20.0.19 | 192.168.1.176 |

### 5. Move WiFi IoT Devices

Connect the two Roku devices to the new IoT SSID:

| Device | MAC | Reserved IP | Current IP |
|---|---|---|---|
| 65TCLRokuTV | `10:3d:0a:42:9f:49` | 10.20.0.20 | 192.168.1.150 |
| RokuUltra | `60:92:c8:8b:3b:30` | 10.20.0.21 | 192.168.1.231 |

---

## Verification

After each device is moved, confirm:

- [ ] Device gets a `10.20.x.x` IP address
- [ ] Device can reach the internet (ping 8.8.8.8 or browse)
- [ ] Roku can launch Plex and play media
- [ ] Device cannot reach NAS01 admin UI (192.168.1.33:8443) — should time out
- [ ] Device cannot reach TrueNAS (192.168.1.31) — should time out
- [ ] DNS resolves correctly (nslookup google.com should return a valid IP)

---

## Notes

- Wyze cameras only need internet — no LAN access rule required
- If a device needs mDNS discovery across VLANs (e.g. Plex client discovery),
  enable **mDNS** in UniFi → Networks → IoT → Advanced. Direct IP connection
  on port 32400 will work without this.
- The ESP device (ESP_D82CFC) may need LAN access if it talks to a home automation
  hub on the main LAN — add a specific allow rule if needed when implementing
- UniFi switch port profiles are reusable — create "IoT Access" once and apply to
  all IoT switch ports
