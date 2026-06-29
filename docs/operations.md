# Day-to-Day Operations

Quick reference for common homelab tasks. All SSH commands assume key auth
is already configured between your Mac and the NAS01 (it is by default).

**NAS01 IP:** 192.168.1.33  
**SSH:** `ssh admin@192.168.1.33`  
**Docker binary:** `/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker`  
**Compose stack path:** `/share/Container/container-station-data/application/homelab/`

> For one-off commands, define an alias: `alias qdocker='ssh admin@192.168.1.33 /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker'`

---

## Container Management

### Check container status
```bash
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose \
  -f /share/Container/container-station-data/application/homelab/docker-compose.yml ps'
```

### Restart a single service
```bash
ssh admin@192.168.1.33 \
  'cd /share/Container/container-station-data/application/homelab && \
   /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d <service>'
```
Use `up -d` (not `restart`) to pick up any env var changes.

### Restart all containers
```bash
ssh admin@192.168.1.33 \
  'cd /share/Container/container-station-data/application/homelab && \
   /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d'
```

### View live logs for a service
```bash
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs -f <service>'
# e.g. <service> = sonarr, radarr, plex, tdarr, npm ...
```

### Execute a command inside a container
```bash
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec -it <service> bash'
```

---

## Adding a New Service

1. **Edit the compose file** (in your local repo): `compose/docker-compose.yml`
2. **Commit and push** to GitHub (use the homelab-git-push skill or `git push`)
3. **Sync to NAS01:**
   ```bash
   scp compose/docker-compose.yml \
     admin@192.168.1.33:/share/Container/container-station-data/application/homelab/docker-compose.yml
   ```
4. **Start the new container:**
   ```bash
   ssh admin@192.168.1.33 \
     'cd /share/Container/container-station-data/application/homelab && \
      /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d <new-service>'
   ```
5. **Add any secrets** to `compose/.env` on the NAS01 (never commit `.env`)
6. **Add an NPM proxy host** if the service needs external access — see `docs/external-access.md`
7. **Update README.md** with the new service in the container table
8. **Update Duplicati** if the service has appdata that should be backed up (it will be
   automatically if it writes to `/share/appdata/<service>/`)

---

## Updating the Compose File / Config

If you edit `docker-compose.yml` or `recyclarr.yml` locally:

```bash
# Push to GitHub
git add . && git commit -m "describe change" && git push

# Sync compose file
scp compose/docker-compose.yml \
  admin@192.168.1.33:/share/Container/container-station-data/application/homelab/docker-compose.yml

# Sync Recyclarr config (if changed)
scp recyclarr/recyclarr.yml admin@192.168.1.33:/share/appdata/recyclarr/recyclarr.yml

# Restart affected service(s)
ssh admin@192.168.1.33 \
  'cd /share/Container/container-station-data/application/homelab && \
   /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d <service>'
```

Or just use the **homelab-git-push skill** in Claude — it does all of the above automatically.

---

## Checking Disk / NFS

```bash
# NAS01 disk usage overview
ssh admin@192.168.1.33 'df -h'

# Check NFS mounts are up
ssh admin@192.168.1.33 'mount | grep nfs'

# Check a specific NFS share is accessible
ssh admin@192.168.1.33 'ls /share/external/.nd/1000/ | head -5'
```

---

## Verifying the VPN

```bash
# TransmissionVPN should return a PIA IP, not your home IP (YOUR_PUBLIC_IP)
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec transmissionvpn curl -s ifconfig.me'
```

---

## Recyclarr (Quality Profile Sync)

Recyclarr syncs TRaSH Guides quality profiles to Sonarr/Radarr daily at midnight.

```bash
# Trigger a manual sync
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec recyclarr recyclarr sync'

# Check Recyclarr logs
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs recyclarr'
```

Recyclarr config: `recyclarr/recyclarr.yml` in this repo → `/share/appdata/recyclarr/recyclarr.yml` on NAS01.
API keys come from container environment (not hardcoded in the yml).

---

## Tdarr (Media Transcoding)

**UI:** http://192.168.1.33:8265  
**Flow docs:** `tdarr/FLOWS.md`

```bash
# Check Tdarr logs
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs tdarr'

# Reset stuck "Transcode error" files (run from inside container)
# See tdarr/FLOWS.md for the full reset script
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec tdarr \
   node /app/server/reset_errors.js'
```

> Tdarr DB is at `/share/appdata/tdarr/server/Tdarr/DB2/SQL/database.db` on the NAS01
> (maps to `/app/server/Tdarr/DB2/SQL/database.db` inside the container).

---

## Watchtower (Auto-Updates)

Watchtower checks for image updates nightly at 4am and sends an email report via Gmail.
It operates silently — check the logs if you think an update happened unexpectedly.

```bash
# Check what Watchtower did recently
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs watchtower --tail 50'
```

To exclude a container from auto-updates, add this label to its compose definition:
```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=false"
```

---

## Duplicati (Backups)

**UI:** http://192.168.1.33:8200  
**Schedule:** Daily at 2am  
**Destination:** NAS02 backups share → `homelab-appdata/`

```bash
# Run a manual backup (CLI, from inside the container)
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec duplicati \
   with-contenv /app/duplicati/duplicati-cli backup \
   file:///backups/homelab-appdata /share/appdata \
   --passphrase=$SETTINGS_ENCRYPTION_KEY'

# List recent backup versions
ssh admin@192.168.1.33 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker exec duplicati \
   with-contenv /app/duplicati/duplicati-cli list \
   file:///backups/homelab-appdata \
   --passphrase=$SETTINGS_ENCRYPTION_KEY'
```

> The `with-contenv` wrapper is required — the linuxserver Duplicati image loads
> `SETTINGS_ENCRYPTION_KEY` via s6 environment, which isn't available in a plain
> `docker exec` shell without it.

---

## Useful Tautulli Queries

Tautulli API base: `http://192.168.1.33:8181/api/v2?apikey=<key>&cmd=`

```bash
# Recent play history (last 100)
curl -s "http://192.168.1.33:8181/api/v2?apikey=<key>&cmd=get_history&length=100"

# Currently active streams
curl -s "http://192.168.1.33:8181/api/v2?apikey=<key>&cmd=get_activity"

# Play count by platform (last 30 days)
curl -s "http://192.168.1.33:8181/api/v2?apikey=<key>&cmd=get_plays_by_date&time_range=30"
```
