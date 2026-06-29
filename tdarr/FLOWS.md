# Tdarr Flows — BKLYN Homelab

Tdarr UI: http://192.168.1.33:8265

One consolidated flow handles the entire library. The canonical definition lives in
the JSON file alongside this document — import that rather than building from scratch.

---

## Flow Files (Source of Truth)

| File | Flow ID | Purpose |
|---|---|---|
| `normalize-mkv-h264-aac-stereo.json` | `-W-fcbKec` | Normalize to MKV + H.264 + loudness-normalized AAC stereo |

### Importing the flow

Tdarr UI → **Flows** → **Import flow** → select the JSON file.

---

## Step 0: Configure Libraries

Tdarr UI → **Libraries** → **Add Library**.

Create two libraries:

### Movies
| Field | Value |
|---|---|
| Library name | Movies |
| Source | /media/movies |
| Transcode cache | /temp |
| File types | mkv,mp4,avi,m4v,ts,wmv,divx,xvid,mpg,mpeg |

### TV
| Field | Value |
|---|---|
| Library name | TV |
| Source | /media/tv |
| Transcode cache | /temp |
| File types | mkv,mp4,avi,m4v,ts,wmv,divx,xvid,mpg,mpeg |

**Leave 4K alone** — don't add it as a library. Those files should stay untouched.

Under each library's **Options** tab:
- Set **Worker count** to `1`
- Enable **On-close health check** so Tdarr scans on startup

---

## The Flow — Normalize: MKV + H264 + AAC Stereo (`-W-fcbKec`)

**Purpose:** In one pass, every file ends up as MKV + H.264 video with a
loudness-normalized AAC 2.0 stereo track added alongside the original audio.
The original surround track (AC3, DTS, TrueHD, etc.) is always preserved.

**What the normalized track fixes:** Cinema masters target -23 LUFS — way too quiet
for home viewing. The normalized track targets **-14 LUFS** (streaming standard),
so clients that can't decode the surround track (Roku, mobile) get a properly loud
stereo mix without the user having to crank the TV volume.

**Idempotency:** Handled by Tdarr's `transcode_decision_maker` status. Once a file
is processed successfully it won't be touched again on future scans. The normalized
track is tagged `title=AAC_Stereo_Normalized` for identification in Plex.

### Plugin sequence

```
inputFile (start)
  └─→ checkVideoCodec (h264?)
        │
        ├─→ [YES, h264] → checkFileExtension (mkv?)
        │                   │
        │                   ├─→ BRANCH A — already H.264 MKV (remux + add AAC)
        │                   │   ffmpegCommandStart
        │                   │     └─→ ffmpegCommandCustomArguments (loudnorm AAC 2.0)
        │                   │           └─→ ffmpegCommandExecute
        │                   │                 └─→ replaceOriginalFile → done
        │                   │
        │                   └─→ BRANCH B — H.264 but not MKV (remux to MKV + add AAC)
        │                       ffmpegCommandStart
        │                         └─→ ffmpegCommandSetContainer (mkv)
        │                               └─→ ffmpegCommandCustomArguments (loudnorm AAC 2.0)
        │                                     └─→ ffmpegCommandExecute
        │                                           └─→ replaceOriginalFile → done
        │
        └─→ [NO, not h264] → BRANCH C — transcode to H.264 MKV + add AAC
                             ffmpegCommandStart
                               └─→ ffmpegCommandSetContainer (mkv)
                                     └─→ ffmpegCommandVideoEncode (h264, NVENC, QP 18)
                                           └─→ ffmpegCommandCustomArguments (pix_fmt yuv420p)
                                                 └─→ ffmpegCommandCustomArguments (loudnorm AAC 2.0)
                                                       └─→ ffmpegCommandExecute
                                                             └─→ replaceOriginalFile → done
```

### The loudnorm AAC step (all three branches)

Each branch uses `ffmpegCommandCustomArguments` with these output arguments:

```
-filter_complex [0:a:0]loudnorm=I=-14:LRA=11:TP=-1.5,aformat=channel_layouts=stereo[normaac]
-map [normaac]
-c:a:1 aac
-b:a:1 192k
-metadata:s:a:1 title=AAC_Stereo_Normalized
```

This adds the normalized stereo AAC as output audio stream 1 alongside the original
(audio stream 0, copied untouched). Files with 2+ original audio tracks (~4% of
library) are not supported — those will error in Tdarr and need to be cleared
manually from the error queue.

> **NVENC note (Branch C):** Re-encodes video with the GTX 1050 Ti on the NAS01.
> At 720p typically under a minute per file. The 1050 Ti does not support AV1;
> H.264 NVENC at QP 18 is the right call.

---

## Mandatory Flow Architecture Rules

These apply to **any** Tdarr v2 flow — violating either causes immediate W09 failures.

### 1. Every flow must start with `inputFile`

The `inputFile` plugin (`isStartPlugin: true`, `pType: 'start'`) is the mandatory
entry point. Without it, the flow engine fails instantly with "No last successful
plugin" before any work begins. It is not optional.

### 2. Every `ffmpegCommandExecute` must be followed by `replaceOriginalFile`

`ffmpegCommandExecute` writes its output to the transcode cache (`/temp`), not back
to the library. Tdarr won't accept a flow that leaves the working file in the cache.
`replaceOriginalFile` handles moving or copying the result to the source location.

> **EXDEV is normal:** The NAS01's `/temp` (Docker local volume) and `/media` (NFS)
> are different filesystems, so `rename()` fails with EXDEV (errno -18). Tdarr
> automatically falls back to `cp`, which succeeds. This appears in logs as a warning
> but is not an error.

---

## Assign the Flow to Libraries

After importing:

1. Tdarr UI → **Libraries** → **Movies** → **Flows** tab
2. Add the flow
3. Repeat for **TV**

---

## Resetting Files (Mac — Python)

The NAS01 has no sqlite3 CLI and running node scripts inside the container is
unreliable. Do all DB operations on the Mac after stopping tdarr:

```bash
# Stop tdarr
ssh admin@192.168.1.33 '/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker stop tdarr'

# Copy DB to Mac
scp admin@192.168.1.33:/share/appdata/tdarr/server/Tdarr/DB2/SQL/database.db /tmp/tdarr.db

# Edit with Python (example: reset all transcode decisions for video files)
python3 - <<'EOF'
import sqlite3
con = sqlite3.connect('/tmp/tdarr.db')
con.execute("UPDATE filejsondb SET transcode_decision_maker='' WHERE file_medium='video'")
con.commit(); con.close()
print("Done")
EOF

# Push back — delete WAL files first to avoid checksum conflicts
scp /tmp/tdarr.db admin@192.168.1.33:/share/appdata/tdarr/server/Tdarr/DB2/SQL/database.db
ssh admin@192.168.1.33 'rm -f /share/appdata/tdarr/server/Tdarr/DB2/SQL/database.db-wal \
  /share/appdata/tdarr/server/Tdarr/DB2/SQL/database.db-shm'

# Restart
ssh admin@192.168.1.33 'cd /share/Container/container-station-data/application/homelab && \
  /share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker compose up -d tdarr'
```

> **WAL warning:** Always delete the `-wal` and `-shm` files after pushing a
> modified DB back. If the WAL from the previous run is left in place, SQLite will
> try to apply those transactions on top of your new DB — page checksum mismatch
> causes tdarr to crash on startup with "DB initialization failed / VACUUM error".

---

## Multi-Node Setup

Two nodes process the queue in parallel:

| Node | Host | Workers | Role |
|---|---|---|---|
| NAS01-node | NAS01 (192.168.1.33) | 2 CPU + 1 GPU + 1 HC | Built into `tdarr` compose container |
| NAS02-node | NAS02 / TrueNAS (192.168.1.31) | 4 CPU + 1 HC | TrueNAS custom app — see CLAUDE.md |

Job assignment is first-come first-served. Workers request files via socket.io; whichever is idle first grabs the next queued file. The NAS02's 4 CPU slots dominate throughput at ~93% CPU utilisation under load (dual Xeon Silver 4214).

**Path translators** must be set on NAS02-node: `server: /media → node: /media`. Without this, the node receives file paths it can't access and every job fails with ENOENT.

### Node schedules

| Node | Schedule | Workers |
|---|---|---|
| NAS02-node | 24/7 (all 24 hourly slots active) | 4 CPU + 1 HC |
| NAS01-node | 8am–12pm only (08-09, 09-10, 10-11, 11-12) | 2 CPU + 1 GPU + 1 HC |

NAS01-node is restricted to morning hours to keep the machine quiet outside those times. NAS02 runs continuously.

**Changing node config:** The `update-node` REST API (`POST /api/v2/update-node`) works for in-memory state, but schedule changes must also be written to SQLite (`nodejsondb`) to survive restarts. The primary key is the node **name** (`NAS02-node`), not the runtime session ID.

**Critical: NAS02-node schedule format.** The schedule entries must use the same format as NAS01-node — embedding per-slot worker limits — or tdarr won't know how many workers to spin up. The `{hour, active}` format (simple boolean per hour) does NOT carry worker counts and results in no workers starting even though the node is connected and the schedule says active.

Correct format for all 24 slots:
```python
{"_id": "18-19", "healthcheckcpu": 1, "healthcheckgpu": 0, "transcodecpu": 4, "transcodegpu": 0}
```

To fix/reset NAS02-node schedule and worker limits:
```python
# docker exec tdarr python3 /tmp/script.py
import sqlite3, json
db = sqlite3.connect('/app/server/Tdarr/DB2/SQL/database.db')
cur = db.cursor()
cur.execute("SELECT json_data FROM nodejsondb WHERE id='NAS02-node'")
d = json.loads(cur.fetchone()[0])
# Replace schedule with per-slot worker counts (24/7, 4 CPU workers)
d['schedule'] = [
    {"_id": f"{h:02d}-{(h+1):02d}", "healthcheckcpu": 1, "healthcheckgpu": 0,
     "transcodecpu": 4, "transcodegpu": 0}
    for h in range(24)
]
d['workerLimits'] = {"healthcheckcpu": 1, "healthcheckgpu": 0, "transcodecpu": 4, "transcodegpu": 0}
d['config']['pathTranslators'] = [{"server": "/media", "node": "/media"}]
cur.execute("UPDATE nodejsondb SET json_data=? WHERE id='NAS02-node'", (json.dumps(d),))
db.commit(); db.close()
```

After writing SQLite, also push the schedule in-memory via `update-node` (no restart needed):
```bash
NODE_ID=$(curl -s http://192.168.1.33:8265/api/v2/get-nodes | python3 -c "
import sys,json; d=json.load(sys.stdin)
[print(k) for k,v in d.items() if 'NAS02' in v['nodeName']]")
curl -X POST http://192.168.1.33:8265/api/v2/update-node \
  -H "Content-Type: application/json" \
  -d "{\"data\":{\"nodeID\":\"$NODE_ID\",\"nodeUpdates\":{
    \"workerLimits\":{\"healthcheckcpu\":1,\"healthcheckgpu\":0,\"transcodecpu\":4,\"transcodegpu\":0},
    \"schedule\":[$(python3 -c \"import json; print(','.join(json.dumps({'_id':f'{h:02d}-{(h+1):02d}','healthcheckcpu':1,'healthcheckgpu':0,'transcodecpu':4,'transcodegpu':0}) for h in range(24)))\")],
    \"config\":{\"pathTranslators\":[{\"server\":\"/media\",\"node\":\"/media\"}]}}}}"
```

### Library schedules vs. node schedules

Two independent schedules control whether work happens:

1. **Node schedule** — stored in `nodejsondb`, controls when each node's workers are active and requesting jobs. NAS02-node is 24/7; NAS01-node is 8am–12pm.
2. **Library schedule** — stored in `librarysettingsjsondb`, controls when files from a library can be dispatched to *any* worker regardless of node. **Both must be open for the current hour.**

Both the Movies and TV libraries are set to **24/7** (all 168 weekly slots checked). If a library is accidentally restricted to certain hours, the NAS02's workers will sit idle outside those hours even though they're fully active.

To check/fix library schedules via SQLite:
```python
# docker exec tdarr python3 /tmp/script.py
import sqlite3, json
db = sqlite3.connect('/app/server/Tdarr/DB2/SQL/database.db')
cur = db.cursor()
cur.execute("SELECT id, json_data FROM librarysettingsjsondb")
for lib_id, raw in cur.fetchall():
    d = json.loads(raw)
    for slot in d['schedule']:
        slot['checked'] = True  # enable all 168 hourly slots
    cur.execute("UPDATE librarysettingsjsondb SET json_data=? WHERE id=?", (json.dumps(d), lib_id))
    print(f"{d['name']}: all slots enabled")
db.commit(); db.close()
# Then restart tdarr to pick up the change
```

### Post-restart checklist

After any `tdarr` server restart:

1. **Rebuild queue** — Tdarr UI → **Libraries** → **Scan All (find fresh)**. "Find new" won't help; "find fresh" re-evaluates the existing DB and rebuilds the active queue.
2. **Re-apply NAS02-node worker limits and schedule** — run `POST /api/v2/update-node` with `workerLimits`, `schedule` (in the per-slot `{_id, transcodecpu, ...}` format — see above), and `pathTranslators`. All are in-memory only and are lost on restart. The SQLite schedule survives restart but must still be pushed via `update-node` so the in-memory state matches. **If you only push `workerLimits` and omit `schedule`, tdarr will return the raw schedule entry as the limits and no workers start.**

---

## Monitoring

Watch progress at: http://192.168.1.33:8265

After a week of running, pull Tautulli stats to measure direct play rate improvement:
`http://192.168.1.33:8181`
