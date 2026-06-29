# Storage — TrueNAS NAS02 Configuration

All persistent data (media library, container appdata, backups) lives on the
NAS02 running TrueNAS. The NAS01 is compute-only — losing it doesn't lose data.

---

## Hardware

| Component | Detail |
|---|---|
| Machine | NAS02 |
| OS | TrueNAS SCALE 26.0.0 |
| LAN IP | 192.168.1.31 |
| TrueNAS admin UI | https://192.168.1.31 |
| SSH | `ssh homelab-svc@192.168.1.31` |

---

## ZFS Pool

| Field | Value |
|---|---|
| Pool name | `media` |
| Mount point | `/mnt/media` |
| Status | ONLINE |
| Raw capacity | 8 × 10TB HDDs |
| Usable capacity | 36.33 TB |
| Currently used | ~17 TB |
| Currently free | ~19 TB |

### Topology

4 × mirrored vdevs (striped mirror — equivalent to RAID 10):

```
media
├── mirror-0  (Seagate Ironwolf 10TB × 2)
├── mirror-1  (Seagate Ironwolf 10TB × 2)
├── mirror-2  (Seagate Ironwolf 10TB × 2)
└── mirror-3  (HGST Ultrastar 10TB × 2)
```

Additionally: 2 × SanDisk M.2 128GB SSDs — used as **boot drives** (not SLOG/L2ARC).

### Disk inventory

| Model | Count | Role |
|---|---|---|
| Seagate Ironwolf ST10000VN0004 10TB | 6 | ZFS data (3 mirrors) |
| HGST Ultrastar HUH721010ALE601 10TB | 2 | ZFS data (1 mirror) |
| SanDisk X400 M.2 128GB | 2 | Boot drives |

---

## ZFS Datasets

| Dataset | Used | Purpose |
|---|---|---|
| `media` | 17.5TB | Pool root |
| `media/media_ds` | 17.4TB | Media library (movies, TV, 4K, music) |
| `media/downloads_ds` | 73GB | Download staging (Transmission) |
| `media/backups` | 67GB | Duplicati backup destination |

---

## NFS Shares

Three shares are exported from TrueNAS and mounted by containers.

| Share | TrueNAS path | Purpose | Mounted at (containers) |
|---|---|---|---|
| media_ds | `/mnt/media/media_ds` | Media library | `/media` |
| downloads_ds | `/mnt/media/downloads_ds` | Download staging | `/downloads` |
| backups | `/mnt/media/backups` | Duplicati backup destination | `/backups` |

### NFS export settings

| Setting | Current value | Notes |
|---|---|---|
| Maproot User | `root` | Required so containers can write |
| Networks | *(unrestricted)* | No NFS-level filter — security relies on network topology (10GbE direct cable + no external exposure) |
| Enabled | Yes | All three shares active |

---

## How the NAS01 mounts these shares

In normal operation, the NAS01 mounts NFS shares as Network Drives through QTS
HybridMount, using the **10GbE storage network address `10.10.10.31`** (not the
LAN address). The old `192.168.1.31` mounts remain in HybridMount in disabled
state as a fallback.

These appear at UUID-based paths in the filesystem:

```
/share/external/.nd/1000/025963587-c551-4812-88b3-be2428d13593  → media_ds
/share/external/.nd/1000/079e07625-9bc0-4b4e-8eda-7e3ae5f632f8  → downloads_ds
/share/external/.nd/1000/0b35ef050-91ae-4ae9-95bb-2aa657a3b3fc  → backups
```

These UUID paths are stable and are referenced in `compose/.env` as `MEDIA_DS`,
`DOWNLOADS_DS`, and `BACKUPS`.

### On a DR host

On a fresh Linux host, the restore script mounts them at:

```
/mnt/homelab/media_ds    → 10.10.10.31:/mnt/media/media_ds
/mnt/homelab/downloads_ds → 10.10.10.31:/mnt/media/downloads_ds
/mnt/homelab/backups     → 10.10.10.31:/mnt/media/backups
```

These paths are set in `~/.homelab.secrets` (`T440_MEDIA_SHARE`, etc.).

---

## Media Library Layout

```
media_ds/
├── movies/          # Radarr library root
├── movies_4k/       # Radarr4K library root
├── tv/              # Sonarr library root
└── music/           # Music library
```

```
downloads_ds/
├── complete/        # Completed downloads (arr apps pick up from here)
└── incomplete/      # In-progress torrents (excluded from Duplicati backup)
```

---

## Appdata (container configs)

Container configuration and databases live on the **NAS01 local storage**, not on
the NAS02. Two Duplicati jobs back these up nightly:

- **"Homelab AppData → NAS02"** (BackupID=4) — 2:00 AM → NAS02 `backups` NFS share
- **"Homelab AppData → B2"** (BackupID=5) — 3:30 AM → Backblaze B2 (`yourusername-appdata-backup`), AES-256 encrypted

Together these satisfy the 3-2-1 rule: live NAS01 copy + local NAS copy + offsite B2 copy.

| Location | What |
|---|---|
| `/share/appdata/<service>/` | All container config and databases |
| `/share/CACHEDEV5_DATA/tdarr-temp/` | Tdarr transcode scratch (NVMe — local only, not backed up) |

---

## Querying TrueNAS

TrueNAS SCALE 24.10+ removed the REST API entirely. The current interface is a
**WebSocket API** at `wss://192.168.1.31/api/current` using JSON-RPC 2.0.
Credentials: `TRUENAS_API_USER` / `TRUENAS_API_KEY` from `~/.homelab.secrets`.

> **Important:** Always use `wss://` (TLS). TrueNAS auto-revokes API keys used over
> plain `ws://`. Messages must include `"jsonrpc":"2.0"` or the server returns
> `{"error":{"code":-32600,"message":"Missing 'jsonrpc' member"}}`.

```python
import asyncio, json, websockets

async def truenas_query(method, params=None):
    url = "wss://192.168.1.31/api/current"
    async with websockets.connect(url, ssl=True) as ws:
        # Auth
        await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"auth.login_with_api_key","params":[API_KEY]}))
        await ws.recv()
        # Query
        await ws.send(json.dumps({"jsonrpc":"2.0","id":2,"method":method,"params":params or []}))
        r = json.loads(await ws.recv())
        return r.get("result")

# Examples:
# asyncio.run(truenas_query("pool.query"))
# asyncio.run(truenas_query("pool.dataset.query"))
# asyncio.run(truenas_query("sharing.nfs.query"))
# asyncio.run(truenas_query("disk.query"))
```

For quick pool status, SSH still works:

```bash
ssh homelab-svc@192.168.1.31 'zpool status media'
```

---

## Maintenance

- **Scrub:** TrueNAS runs a ZFS scrub automatically (default: monthly). Verify in
  TrueNAS → Data Protection → Scrub Tasks.
- **SMART tests:** Short test weekly, long test monthly — configure in
  TrueNAS → Data Protection → S.M.A.R.T. Tests.
- **Snapshots:** Consider enabling TrueNAS periodic snapshots on `media/media_ds`
  for accidental-deletion protection (7 daily, 4 weekly).
- **Email alerts:** Configure TrueNAS → System → Alert Services so pool
  degradation and disk errors are reported immediately.
