# Container Migration Plan
## Ubuntu VM (NAS01) → Container Station (NAS01 native)

**Goal:** Eliminate the Ubuntu VM and run all containers directly in NAS01 Container Station, adding Plex as a container to unify management.

**Services being migrated:** agregarr, bazarr, duplicati, flaresolverr, organizr, prowlarr, radarr, radarr4k, seerr, sonarr, tautulli, transmissionvpn, uptimekuma, watchtower + new: plex

---

## Confirmed Values

| Setting | Value |
|---|---|
| PUID / PGID | 1000 / 1000 |
| TUN module | ✅ Loaded (`tun 49152 3 vhost_net`) |
| media_ds path (QTS) | `/share/external/.nd/1000/025963587-c551-4812-88b3-be2428d13593` |
| downloads_ds path (QTS) | `/share/external/.nd/1000/079e07625-9bc0-4b4e-8eda-7e3ae5f632f8` |
| backups path (QTS) | `/share/external/.nd/1000/0b35ef050-91ae-4ae9-95bb-2aa657a3b3fc` |
| Appdata path (QTS) | `/share/appdata` |
| NAS02 IP | 192.168.1.31 |
| NAS01 IP | 192.168.1.33 |

---

## Phase 0 — Prepare (do this before touching anything)

### 0.1 Add no_root_squash to TrueNAS exports

Currently only `media_ds` has `no_root_squash`. The other two shares will squash
UID 1000 to nobody, causing write failures for Transmission and Duplicati.

In TrueNAS UI → Shares → UNIX (NFS) Shares:
- Edit `downloads_ds` → Advanced → check **No Root Squash** → Save
- Edit `backups` → Advanced → check **No Root Squash** → Save

### 0.2 Prepare the Appdata share on NAS01

The `appdata` share already exists on `m2vol` (M.2 SSD) — no need to create one.
Just set permissions so containers (running as UID 1000) can write to it:

```bash
chmod -R 777 /share/appdata
```

### 0.3 Get a Plex claim token

Before starting the Plex container for the first time, visit:
https://www.plex.tv/claim

Copy the token and paste it into `.env` as `PLEX_CLAIM`. It's valid for 4 minutes —
have the container ready to start before you fetch it. After the first successful
start, clear the value in `.env` (leave it blank).

---

## Phase 1 — Migrate Appdata from VM to NAS01

Stop all running containers on the VM first:

```bash
cd ~/.docker/compose
docker compose down
```

Copy the appdata directory to the new NAS01 share. From your Mac (mount the NAS01
Appdata share first via Finder → Go → Connect to Server → `smb://192.168.1.33`):

```bash
scp -r owner@<vm-ip>:~/.config/appdata/ /Volumes/Appdata/
```

Or directly from the VM if you can reach the NAS01 share:

```bash
rsync -av /home/owner/.config/appdata/ /mnt/NAS01-appdata/
```

Verify the copy completed and all subdirectories are present before proceeding.

**Note on Duplicati backups:** Previously, backups were written to
`/home/owner/.config/appdata/backups`. The new compose writes them to the NAS02's
`backups` share instead (`/backups` in the container). After migration, update
your Duplicati backup jobs to point to `/backups` as the destination if they
aren't already configured that way.

---

## Phase 2 — Migrate Plex Library (optional but recommended)

The native NAS01 Plex app stores its data at:

```
/share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/
```

To preserve watch history, ratings, custom artwork, and playlists, copy that
directory to the new Plex container config location before first launch:

```bash
cp -r /share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/ /share/Appdata/plex/
```

If you don't care about preserving history, skip this — Plex will re-scan your
library fresh. Either way, **do not start the Plex container until the native
app is stopped.**

---

## Phase 3 — Deploy in Container Station

### 3.1 Create the project

Container Station → Projects → Create. Name it `homelab`. Upload or paste the
`docker-compose.yml` and `.env` from this folder.

### 3.2 Bring up non-VPN services first

Comment out `transmissionvpn` in the compose file initially and start everything
else. Verify each service is accessible and writing configs correctly to
`/share/Appdata`.

Check for permission errors on QTS:

```bash
ls -lan /share/Appdata/sonarr
ls -lan /share/Appdata/radarr
# Files should be owned by 1000:1000
```

### 3.3 Start TransmissionVPN

Uncomment transmissionvpn and bring it up:

```bash
docker compose up -d transmissionvpn
docker logs transmissionvpn --follow
```

Look for `Initialization Sequence Completed` — that confirms the VPN tunnel is up.

### 3.4 Cut over Plex

1. Stop the native NAS01 Plex app in App Center
2. Fetch a Plex claim token and add it to `.env`
3. Start the plex container
4. Browse to `http://192.168.1.33:32400/web`
5. Verify your library appears (or complete fresh setup if you skipped Phase 2)
6. Uninstall the native Plex app from App Center

---

## Phase 4 — Verify Internal Paths

The containers now use split volume mounts instead of one `/storage` root. Verify
these paths are correct inside each app's settings after first launch:

**Sonarr / Radarr / Radarr4K:**
- Root folder: `/storage/media_ds/tv` (Sonarr), `/storage/media_ds/movies` (Radarr)
- Download client completed path: `/storage/downloads_ds/completed`

**Transmission:**
- Download dir: `/storage/downloads_ds/completed` ✓ (set in compose env)
- Incomplete dir: `/storage/downloads_ds/incomplete` ✓
- Watch dir: `/storage/downloads_ds/watch` ✓

**Bazarr:**
- Media library path: `/storage/media_ds`

**Plex:**
- Library path: `/media` (mapped from media_ds)

**Tautulli:** Verify Plex server connection after Plex cutover.

**Seerr:** Verify Sonarr and Radarr connection settings — container IPs may differ
from the VM.

**Agregarr:** Update its config to point to the new Radarr/Radarr4K container
hostnames.

---

## Phase 5 — Cleanup

Once all services are confirmed stable for a few days:

1. **Stop and remove the Ubuntu VM** from NAS01 Virtualization Station — reclaims
   RAM and CPU
2. **Verify Duplicati** is backing up `/share/Appdata` to the NAS02 backups share
3. **Update bookmarks** if the NAS01 IP differs from the VM's IP for any services

---

## Fallback: If TransmissionVPN fails

TUN is confirmed loaded, so this is unlikely. But if it fails, replace
`haugene/transmission-openvpn` with plain Transmission + a Gluetun sidecar:

```yaml
  gluetun:
    container_name: gluetun
    image: qmcgaw/gluetun:latest
    cap_add:
      - NET_ADMIN
    environment:
      VPN_SERVICE_PROVIDER: private internet access
      VPN_TYPE: openvpn
      OPENVPN_USER: ${PIA_USER}
      OPENVPN_PASSWORD: ${PIA_PASS}
      SERVER_REGIONS: CA Montreal
    ports:
      - 9091:9091
    restart: unless-stopped

  transmission:
    container_name: transmission
    image: lscr.io/linuxserver/transmission:latest
    network_mode: service:gluetun   # routes all traffic through gluetun
    environment:
      PUID: ${PUID}
      PGID: ${PGID}
      TZ: ${TZ}
    restart: unless-stopped
    volumes:
      - ${APPDATA_PATH}/transmission:/config
      - ${DOWNLOADS_DS}:/storage/downloads_ds
```
