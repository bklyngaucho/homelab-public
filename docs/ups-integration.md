# UPS Integration Plan

## Hardware

| Item | Detail |
|---|---|
| UPS | APC Back-UPS Pro BN1500M2 |
| Capacity | 1500 VA / 900W |
| Current load | ~317W (2 bars) |
| Interface | USB via proprietary APC cable |
| Replacement battery | APCRBC161 |

**Current state:** UPS provides power protection only — no communication cable connected,
no graceful shutdown coordination.

---

## Blocker

The BN1500M2 uses a **proprietary APC USB communication cable** (not a standard USB-B).
The UPS end looks like a small RJ11-style connector; the computer end is USB-A.
This cable should have come in the box — if lost, search Amazon for
"APC USB communication cable Back-UPS" (~$10–15).

**Do not proceed past this point until the cable is in hand.**

---

## Architecture

```
APC BN1500M2
    │
    │ APC USB cable
    ▼
NAS02 / TrueNAS SCALE  ← NUT master (server)
    │
    │ NUT network protocol (LAN)
    ▼
NAS01               ← NUT client
```

TrueNAS is the NUT master because it has first-class UPS support built into the SCALE UI.
NAS01 connects as a network client. **Shutdown order matters:** NAS01 must shut down first
(stops containers, unmounts NFS cleanly), then TrueNAS shuts down after a delay.

---

## Implementation Steps

### 1. Connect the cable

Plug the APC USB cable into the Back-UPS data port and into any USB port on the NAS02.

### 2. Configure TrueNAS SCALE (NUT master)

System → Services → UPS:

| Setting | Value |
|---|---|
| UPS Mode | Master |
| Identifier | `ups` |
| Driver | `usbhid-ups` |
| Port | `auto` |
| Monitor User | `upsmon` |
| Monitor Password | *(set a password — note it for NAS01)* |
| Remote Monitor | Enabled |
| Shutdown Mode | UPS reaches low battery |
| Shutdown Timer | 30 seconds |
| Send Email Status Updates | Enabled |

Enable the UPS service after saving.

Verify TrueNAS sees the UPS:
```bash
# From TrueNAS shell
upsc ups@localhost
```
Should return battery charge, runtime, input/output voltage, and load.

### 3. Configure NAS01 (NUT client)

Control Panel → External Device → UPS:

| Setting | Value |
|---|---|
| Enable | Yes |
| UPS Type | Network UPS (slave) |
| UPS Server IP | `192.168.1.31` |
| Username | `upsmon` |
| Password | *(match TrueNAS)* |
| Shutdown after | 60 seconds on UPS alert |

The 60-second delay gives Docker containers time to stop cleanly before NAS01 powers off.

### 4. Verify the shutdown sequence

With both devices configured, simulate a power event by unplugging the UPS from the wall
briefly (the UPS will switch to battery and signal both devices):

- [ ] TrueNAS detects "on battery" and logs it
- [ ] NAS01 receives the signal within a few seconds
- [ ] On low battery signal, NAS01 begins shutdown countdown
- [ ] TrueNAS waits for NAS01 then initiates its own shutdown

Plug the UPS back in before any shutdown actually occurs unless you want to do a full test.

---

## What This Protects Against

- **Power outage:** Both devices shut down gracefully before battery is exhausted
- **ZFS corruption:** TrueNAS shuts down cleanly — no mid-write pool corruption
- **NFS corruption:** NAS01 unmounts NFS shares before TrueNAS shuts down

## What It Does Not Cover

- **Extended outages:** At ~317W load, runtime is ~15–20 minutes. Beyond that, both
  devices will shut down (gracefully, via NUT). Media services will be unavailable until
  power is restored and devices are restarted manually.
- **Automatic restart:** NAS01 and TrueNAS will need to power back on when AC is restored.
  Check BIOS/QTS power-on settings if you want auto-restart after power restore.

---

## Notes

- The switch is also on the UPS battery — LAN stays up during a power event, which means
  NUT client communication between NAS01 and TrueNAS continues to work throughout
- NAS01 auto-restart on AC restore: QTS → System → Power → Power Recovery → "Last state"
- TrueNAS auto-restart: NAS02 BIOS → Power Management → AC Power Recovery → "Last State"
- Uptime Kuma will alert when services go down during a power event (once notifications
  are configured — see monitoring gap in backlog)
