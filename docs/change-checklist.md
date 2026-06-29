# Change Checklist

When you make a change to the homelab, use this guide to figure out what else needs updating.
Not every item applies to every change — scan the relevant section and check off what applies.

---

## Adding a New Container Service

- [ ] **compose/docker-compose.yml** — add the service definition
- [ ] **compose/.env.template** — add any new `${VAR_NAME}` placeholders
- [ ] **compose/.env on NAS01** — add the real values (never commit this)
- [ ] **NAS01 appdata dir** — `mkdir -p /share/appdata/<service>` on the NAS01
- [ ] **README.md** — add a row to the Container Stack table; update total container count in comment on `docker-compose.yml` line
- [ ] **CLAUDE.md** — update container count ("22 containers") and add a Notable configuration bullet if the service has quirks
- [ ] **network-diagram.md** — update "Containers (N):" in the Storage Architecture diagram and "All N containers up" in the DR flow
- [ ] **docs/network-diagram.md** — add to Internal Service Ports table if it has a notable port
- [ ] **docs/RUNBOOK-INDEX.md** — add a row to the Service-Specific Operations section; update Last Updated date
- [ ] **docs/operations.md** — add a service-specific ops section if it needs non-obvious commands
- [ ] **Uptime Kuma** — add an HTTP/keyword monitor; add it to the `homelab` status page group
- [ ] **NPM** — add a proxy host if external access is needed (no new DNS record required — wildcard covers it)
- [ ] **Technitium** — local DNS record only needed if the service uses a custom subdomain that can't hit the wildcard
- [ ] **Duplicati** — add exclusions to both BackupID=4 and BackupID=5 if the service writes large/ephemeral data that shouldn't be backed up (cache, logs, media)
- [ ] **Git commit** — run the homelab-git-push skill

---

## Removing a Container Service

- [ ] **compose/docker-compose.yml** — remove the service block
- [ ] **compose/.env.template** — remove orphaned variable placeholders
- [ ] **README.md** — remove from Container Stack table; update container count
- [ ] **CLAUDE.md** — remove Notable configuration bullet; update container count
- [ ] **network-diagram.md** — update container count; remove from port table if listed
- [ ] **docs/RUNBOOK-INDEX.md** — remove service row; update Last Updated date
- [ ] **Uptime Kuma** — delete the monitor and remove from status page
- [ ] **NPM** — delete proxy host if one existed
- [ ] **NAS01 appdata** — optionally archive or delete `/share/appdata/<service>/`
- [ ] **Git commit**

---

## Adding a New Physical Host / Hardware

- [ ] **CLAUDE.md** — add to Hardware context table; add any notable config details
- [ ] **README.md** — add to Hardware table
- [ ] **docs/network-diagram.md** — add to Physical Network Topology diagram, Storage Architecture if relevant, and IP Address Allocation tables
- [ ] **docs/network-diagram.mermaid** — add node and connections
- [ ] **docs/storage.md** — update if the host adds or changes storage
- [ ] **Uptime Kuma** — add a ping or HTTP monitor; add to the Infrastructure group on the status page
- [ ] **docs/RUNBOOK-INDEX.md** — update Last Updated date
- [ ] **Git commit**

---

## Network / IP / DNS Changes

- [ ] **CLAUDE.md** — update Hardware context table IPs; update DNS management section if Cloudflare zone or token changes
- [ ] **README.md** — update Hardware table
- [ ] **docs/network-diagram.md** — update Physical Network Topology, IP Address Allocation table, and any affected diagrams
- [ ] **docs/network-diagram.mermaid** — update node labels with new IPs
- [ ] **docs/external-access.md** — update if port forwards, proxy hosts, or wildcard cert changes
- [ ] **Technitium** — update local DNS records if service IPs changed
- [ ] **Cloudflare** — update A records if home IP changed
- [ ] **NPM** — update proxy host targets if internal IPs changed
- [ ] **Git commit**

---

## Tdarr Node Changes (adding/removing/reconfiguring a node)

- [ ] **CLAUDE.md** — update Tdarr bullet: node count, worker limits, schedule, any persistence quirks
- [ ] **tdarr/FLOWS.md** — update Multi-Node Setup table and Node Schedules section
- [ ] **README.md** — update NAS02 row in Hardware table if its role changes
- [ ] **Uptime Kuma** — add/update keyword monitor on `/api/v2/get-nodes` for the node name
- [ ] **docs/RUNBOOK-INDEX.md** — update Last Updated date
- [ ] **Git commit**
- [ ] **After any tdarr server restart** — run Tdarr UI → Libraries → **Scan All (find fresh)** to rebuild the transcode queue

---

## Storage Changes (new dataset, NFS export, capacity change)

- [ ] **docs/storage.md** — update ZFS Datasets table, capacity numbers, NFS Shares table
- [ ] **CLAUDE.md** — update NAS02/TrueNAS hardware section (pool stats)
- [ ] **docs/network-diagram.md** — update Storage Architecture diagram (capacity, datasets)
- [ ] **compose/.env.template** — add new `$VAR` if a new NFS path is needed
- [ ] **DR restore.sh** — add mount step if a new NFS share needs to be mounted during DR
- [ ] **dr/.secrets.template** — add new path vars if needed
- [ ] **Git commit**

---

## External Access Changes (new subdomain, new port forward)

- [ ] **NPM** — add or update proxy host
- [ ] **UniFi** — add port forward if a new external port is needed (80, 443, 32400 already exist)
- [ ] **Cloudflare** — individual DNS record only if the subdomain shouldn't go through the wildcard
- [ ] **docs/external-access.md** — update Current Proxy Hosts table and Port Forwards table
- [ ] **docs/network-diagram.md** — update External Ports table and External Access Flow diagram if needed
- [ ] **docs/RUNBOOK-INDEX.md** — update Last Updated date
- [ ] **Git commit**

---

## Backup Changes (new exclusion, new job, schedule change)

- [ ] **CLAUDE.md** — update Duplicati bullets (schedule, exclusions, B2 bucket)
- [ ] **docs/storage.md** — update Appdata section if backup destinations change
- [ ] **duplicati/homelab-appdata-backup.json** — re-export the job config from Duplicati UI (Settings → Export job) and commit the updated file
- [ ] **Git commit**

---

## Credential / Secret Rotation

- [ ] **compose/.env on NAS01** — update the real value
- [ ] **~/.homelab.secrets on Mac** — update if it's a DR-relevant secret
- [ ] **dr/.secrets.template** — update placeholder description if the variable name changed
- [ ] **compose/.env.template** — update placeholder if the variable name changed
- [ ] **scripts/.hl.env on Mac** — update if it's an API key used by hl.py
- [ ] **Restart the affected container** — `docker compose up -d <service>`
- [ ] **Git commit** (only template changes — never commit real values)

---

## Container Image / Software Upgrades (beyond Watchtower)

- [ ] **Verify after upgrade** — check container logs for deprecation warnings, config format changes, or broken health checks
- [ ] **tdarr specifically** — check if `nodejsondb` schema changed; re-verify NAS02-node config persists
- [ ] **CLAUDE.md** — update version references if pinned (e.g., tdarr_node image tag in the NAS02 section)
- [ ] **tdarr/FLOWS.md** — update image tag in the TrueNAS custom app YAML if the tdarr_node image was pinned
- [ ] **Git commit** if any config files changed

---

## After Any Tdarr Server Restart

This is worth its own section because it bites every time:

1. Both nodes will reconnect automatically within ~30 seconds
2. **Workers will sit idle** — the in-memory transcode queue is empty after restart
3. Fix: Tdarr UI → Libraries → **Scan All (find fresh)** on every library
4. Workers start picking up jobs within seconds of the scan completing

"Find new" does **not** fix this — it only finds files not yet in the DB. "Find fresh" re-evaluates existing DB entries and rebuilds the active queue.

---

*Keep this checklist updated whenever a new class of change reveals a new doc/system that needs touching.*

*Last Updated: 2026-06-21*
