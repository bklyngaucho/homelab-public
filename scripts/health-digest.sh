#!/usr/bin/env bash
# health-digest.sh — collect homelab health data and output as JSON
# Used by the live artifact and the weekly markdown scheduled task

set -euo pipefail

NAS01="admin@192.168.1.33"
DOCKER="ssh $NAS01 /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker"

# ── Tdarr stats ─────────────────────────────────────────────────────────────
TDARR_RAW=$(curl -sf -X POST http://192.168.1.33:8265/api/v2/cruddb \
  -H "Content-Type: application/json" \
  -d '{"data":{"collection":"StatisticsJSONDB","mode":"getAll","obj":{}}}' 2>/dev/null || echo "[]")

TDARR=$(echo "$TDARR_RAW" | python3 -c "
import sys, json
d = json.load(sys.stdin)
s = d[0] if d else {}
print(json.dumps({
  'totalFiles':       s.get('totalFileCount', 0),
  'transcodeQueue':   s.get('table1Count', 0),
  'transcodeSuccess': s.get('table2Count', 0),
  'transcodeErrors':  s.get('table3Count', 0),
  'healthQueue':      s.get('table4Count', 0),
  'healthHealthy':    s.get('table5Count', 0),
  'healthErrors':     s.get('table6Count', 0),
  'spaceSavedGB':     round(abs(s.get('sizeDiff', 0)), 2),
  'tdarrScore':       s.get('tdarrScore', 'n/a'),
  'healthScore':      s.get('healthCheckScore', 'n/a'),
}))
" 2>/dev/null || echo '{}')

# ── Container status ─────────────────────────────────────────────────────────
CONTAINERS_RAW=$(ssh $NAS01 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker ps -a \
  --format "{{.Names}}|{{.Status}}"' 2>/dev/null || echo "")

CONTAINERS=$(echo "$CONTAINERS_RAW" | python3 -c "
import sys, json
rows = []
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    parts = line.split('|', 1)
    if len(parts) == 2:
        name, status = parts
        up = status.lower().startswith('up')
        rows.append({'name': name, 'status': status, 'up': up})
rows.sort(key=lambda x: x['name'])
print(json.dumps(rows))
" 2>/dev/null || echo '[]')

# ── Disk usage (key volumes only) ───────────────────────────────────────────
DISK_RAW=$(ssh $NAS01 'df -h 2>/dev/null' || echo "")

DISK=$(echo "$DISK_RAW" | python3 -c "
import sys, json, re
rows = []
keep = {
  '/share/CACHEDEV1_DATA': 'NAS01 Pool 1 (2TB)',
  '/share/CACHEDEV3_DATA': 'NAS01 Pool 3 (SSD)',
  '/share/CACHEDEV4_DATA': 'NAS01 Pool 4',
  '/share/CACHEDEV5_DATA': 'NAS01 Pool 5',
  '/mnt/ext':              'NAS01 Extensions (!)',
}
nfs = []
for line in sys.stdin:
    parts = line.split()
    if len(parts) < 6: continue
    fs, size, used, avail, pct, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
    if mount in keep:
        pct_int = int(pct.rstrip('%'))
        rows.append({'label': keep[mount], 'size': size, 'used': used, 'avail': avail, 'pct': pct_int})
    elif fs.startswith('192.168.1.31:'):
        nfs.append({'label': mount.split('/')[-1], 'size': size, 'used': used, 'avail': avail, 'pct': int(pct.rstrip('%'))})
print(json.dumps({'local': rows, 'nfs': nfs}))
" 2>/dev/null || echo '{"local":[],"nfs":[]}')

# ── Watchtower recent updates ────────────────────────────────────────────────
WATCHTOWER=$(ssh $NAS01 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker logs watchtower --tail 60 2>&1' | \
  grep -i "updated\|no updates\|session" | tail -20 | \
  python3 -c "
import sys, json
lines = [l.strip() for l in sys.stdin if l.strip()]
print(json.dumps(lines[-10:] if len(lines) > 10 else lines))
" 2>/dev/null || echo '[]')

# ── Assemble output ──────────────────────────────────────────────────────────
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

python3 << PYEOF
import json
out = {
  'timestamp':  '$TIMESTAMP',
  'tdarr':       json.loads('''$TDARR'''),
  'containers':  json.loads('''$CONTAINERS'''),
  'disk':        json.loads('''$DISK'''),
  'watchtower':  json.loads('''$WATCHTOWER'''),
}
print(json.dumps(out, indent=2))
PYEOF
