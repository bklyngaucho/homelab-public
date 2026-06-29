---
name: project-NAS01-paths
description: Key file paths on the NAS01 for the homelab container stack
metadata: 
  node_type: memory
  type: project
  originSessionId: 5673a38f-2fbf-4500-9a6d-d50b12c3f378
---

The live Docker Compose stack on the NAS01 is deployed at:

**/share/Container/container-station-data/application/homelab**

This is where `docker-compose.yml` and `.env` live on the NAS01. Always use this path when telling the user where to make changes or run `docker compose` commands on the NAS01 — not `~/homelab/compose`.

**Why:** NAS01 Container Station deploys applications to this path, not the user's home directory.

**How to apply:** Any time instructions involve `cd ~/homelab/compose` or similar on the NAS01, use this path instead.

## Remote access via Desktop Commander

SSH key auth is set up from Mac → NAS01 (admin@192.168.1.33). Desktop Commander can run NAS01 commands without user copy-paste.

Docker binary path (not in default SSH PATH):
`/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker`

Example usage via Desktop Commander:
```
ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker ps'
```

docker compose is at the same location. Always use full path for docker commands over SSH.

## Workflow limitations

- The compose directory is managed by Container Station, not a git clone — `git pull` does not work here
- Changes committed to GitHub must be manually applied to the NAS01 by editing files directly
- `nano` is not available on the NAS01 — use `vi` for in-place edits, or edit via SSH from Mac
- To apply compose file changes: edit the file, then `docker compose up -d <service>`
