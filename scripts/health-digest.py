#!/usr/bin/env python3
"""
health-digest.py — collect homelab health data and output as JSON
Used by the live artifact and the weekly markdown scheduled task.
"""

import json
import subprocess
import urllib.request
import datetime
import sys
import os

NAS01 = "admin@192.168.1.33"
DOCKER_BIN = "/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/.libs/docker"

def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def NAS01(remote_cmd, timeout=20):
    """Run a command on NAS01 via SSH, properly quoted."""
    return run(f"ssh {NAS01} {repr(remote_cmd)}", timeout=timeout)

def curl_post(url, data, timeout=10):
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body,
              headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

# ── Tdarr ────────────────────────────────────────────────────────────────────
def get_tdarr():
    raw = curl_post("http://192.168.1.33:8265/api/v2/cruddb",
                    {"data": {"collection": "StatisticsJSONDB", "mode": "getAll", "obj": {}}})
    if not raw:
        return {"error": "unavailable"}
    s = raw[0] if raw else {}
    return {
        "totalFiles":       s.get("totalFileCount", 0),
        "transcodeQueue":   s.get("table1Count", 0),
        "transcodeSuccess": s.get("table2Count", 0),
        "transcodeErrors":  s.get("table3Count", 0),
        "healthQueue":      s.get("table4Count", 0),
        "healthHealthy":    s.get("table5Count", 0),
        "healthErrors":     s.get("table6Count", 0),
        "spaceSavedGB":     round(abs(s.get("sizeDiff", 0)), 2),
        "tdarrScore":       s.get("tdarrScore", "n/a"),
        "healthScore":      s.get("healthCheckScore", "n/a"),
    }

# ── Containers ───────────────────────────────────────────────────────────────
def get_containers():
    raw = NAS01(f'{DOCKER_BIN} ps -a --format "{{{{.Names}}}}|{{{{.Status}}}}"')
    rows = []
    for line in raw.splitlines():
        parts = line.strip().split("|", 1)
        if len(parts) == 2:
            name, status = parts
            rows.append({
                "name": name,
                "status": status,
                "up": status.lower().startswith("up")
            })
    rows.sort(key=lambda x: x["name"])
    return rows

# ── Disk ─────────────────────────────────────────────────────────────────────
def get_disk():
    # -P: POSIX output (no line wrapping for long paths)
    raw = NAS01("df -Ph 2>/dev/null")
    label_map = {
        "/share/CACHEDEV1_DATA": "NAS01 Pool 1 (2TB)",
        "/share/CACHEDEV3_DATA": "NAS01 Pool 3 (SSD)",
        "/share/CACHEDEV4_DATA": "NAS01 Pool 4",
        "/share/CACHEDEV5_DATA": "NAS01 Pool 5",
        "/mnt/ext":              "NAS01 Extensions",
    }
    local, nfs = [], []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        fs, size, used, avail, pct, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        try:
            pct_int = int(pct.rstrip("%"))
        except ValueError:
            continue
        entry = {"size": size, "used": used, "avail": avail, "pct": pct_int}
        if mount in label_map:
            entry["label"] = label_map[mount]
            entry["warning"] = pct_int >= 85
            local.append(entry)
        elif fs.startswith("192.168.1.31:"):
            # Map NFS source tail to friendly name
            nfs_names = {
                "media_ds":     "NAS Media",
                "downloads_ds": "NAS Downloads",
                "backups":      "NAS Backups",
            }
            tail = fs.split("/")[-1]
            entry["label"] = nfs_names.get(tail, tail)
            entry["warning"] = pct_int >= 85
            nfs.append(entry)
    return {"local": local, "nfs": nfs}

# ── Duplicati ────────────────────────────────────────────────────────────────
def get_duplicati():
    """Query Duplicati server SQLite DB via docker exec stdin — no API auth, no quoting hell."""
    # Pipe the script via stdin to 'python3 -' to avoid all shell-quoting issues
    script = """\
import sqlite3, json
conn = sqlite3.connect('/config/Duplicati-server.sqlite')
cur = conn.cursor()
cur.execute('SELECT b.Name, m.Name, m.Value FROM Backup b JOIN Metadata m ON b.ID=m.BackupID')
d = {}
for r in cur.fetchall():
    d.setdefault(r[0], {})[r[1]] = r[2]
conn.close()
print(json.dumps(d))
"""
    try:
        r = subprocess.run(
            f"ssh {NAS01} '{DOCKER_BIN} exec -i duplicati python3 -'",
            shell=True, input=script, capture_output=True, text=True, timeout=20
        )
        raw = r.stdout.strip()
    except Exception:
        return {"error": "unavailable"}

    if not raw:
        return {"error": "unavailable"}

    try:
        jobs = json.loads(raw)
    except Exception:
        return {"error": "parse failed"}

    result = []
    for name, meta in jobs.items():
        last_ok   = meta.get("LastBackupDate", "")
        duration  = meta.get("LastBackupDuration", "")
        err_date  = meta.get("LastErrorDate", "")
        err_msg   = meta.get("LastErrorMessage", "")
        src_files = meta.get("SourceFilesCount", "")
        src_size  = meta.get("SourceSizeString", "")
        versions  = meta.get("BackupListCount", "")
        free      = meta.get("FreeQuotaSpace", "")

        # Shorten duration: strip sub-seconds
        if "." in duration:
            duration = duration.split(".")[0]

        # Convert free bytes to GiB
        try:
            free_gib = round(int(free) / 1024**3, 1)
        except Exception:
            free_gib = None

        # Flag if last error is more recent than last OK backup
        has_error = bool(err_date and err_msg and err_date > last_ok)

        result.append({
            "name":        name,
            "lastBackup":  last_ok,
            "duration":    duration,
            "sourceFiles": src_files,
            "sourceSize":  src_size,
            "versions":    versions,
            "freeGiB":     free_gib,
            "error":       err_msg if has_error else None,
        })
    return result


# ── Watchtower ───────────────────────────────────────────────────────────────
def get_watchtower():
    raw = NAS01(f"{DOCKER_BIN} logs watchtower --tail 80 2>&1")
    lines = []
    for line in raw.splitlines():
        ll = line.lower()
        if any(k in ll for k in ["updated", "no updates", "session", "found"]):
            # Strip ANSI codes
            import re
            clean = re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
            if clean:
                lines.append(clean)
    return lines[-15:] if len(lines) > 15 else lines

# ── Markdown formatter ───────────────────────────────────────────────────────
def format_markdown(data):
    ts   = data["timestamp"]
    t    = data["tdarr"]
    disk = data["disk"]
    ctrs = data["containers"]
    wt   = data["watchtower"]

    down = [c for c in ctrs if not c["up"]]

    lines = [
        f"# Homelab Health Report — {ts[:10]}",
        "",
        f"*Generated: {ts}*",
        "",
        "## Tdarr",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total files | {t.get('totalFiles', '?'):,} |",
        f"| Transcode queue | {t.get('transcodeQueue', '?'):,} |",
        f"| Transcode success | {t.get('transcodeSuccess', '?'):,} |",
        f"| Transcode errors | {t.get('transcodeErrors', '?')} |",
        f"| Space saved | {t.get('spaceSavedGB', '?')} GB |",
        f"| Tdarr score | {t.get('tdarrScore', '?')} |",
        f"| Health score | {t.get('healthScore', '?')} |",
        "",
        "## Containers",
        "",
        f"**{len(ctrs)} total** · {len(ctrs) - len(down)} up · {len(down)} down",
        "",
    ]
    if down:
        lines.append("⚠️ **Down:**")
        for c in down:
            lines.append(f"- `{c['name']}` — {c['status']}")
        lines.append("")

    lines += [
        "## Disk",
        "",
        "### NAS01 Local",
        "",
        "| Volume | Used | Avail | % |",
        "|--------|------|-------|---|",
    ]
    for v in disk["local"]:
        warn = " ⚠️" if v.get("warning") else ""
        lines.append(f"| {v['label']} | {v['used']} | {v['avail']} | {v['pct']}%{warn} |")

    lines += [
        "",
        "### NAS (NFS)",
        "",
        "| Share | Used | Avail | % |",
        "|-------|------|-------|---|",
    ]
    for v in disk["nfs"]:
        warn = " ⚠️" if v.get("warning") else ""
        lines.append(f"| {v['label']} | {v['used']} | {v['avail']} | {v['pct']}%{warn} |")

    lines += ["", "## Watchtower (recent updates)", ""]
    if wt:
        for line in wt:
            lines.append(f"```")
            lines.append(line)
            lines.append(f"```")
    else:
        lines.append("*No recent update activity.*")

    lines.append("")
    return "\n".join(lines)


# ── Assemble ─────────────────────────────────────────────────────────────────
def main():
    markdown_mode = "--markdown" in sys.argv
    output = {
        "timestamp":  datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tdarr":      get_tdarr(),
        "containers": get_containers(),
        "disk":       get_disk(),
        "duplicati":  get_duplicati(),
        "watchtower": get_watchtower(),
    }
    payload = json.dumps(output, indent=2)

    if markdown_mode:
        print(format_markdown(output))
    else:
        print(payload)

    # Always write cache file so the Cowork artifact can read it
    cache_path = os.path.join(os.path.dirname(__file__), "health_cache.json")
    try:
        with open(cache_path, "w") as f:
            f.write(payload)
    except Exception as e:
        print(f"Warning: could not write cache: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
