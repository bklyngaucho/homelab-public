# Services Best Practice Audit — Duplicati
2026-06-09

## Summary
5 findings: 1 🔴 critical · 3 🟡 warning · 1 🔵 info · 0 ⚪ flag

---

## Duplicati

### 🔴 Critical

- [ ] **Plaintext secrets visible in `docker inspect`**
  - **Why it matters:** `SETTINGS_ENCRYPTION_KEY` is set as a plain environment variable, which means anyone who can run `docker inspect duplicati` — via SSH, Container Station, or any container with access to the Docker socket — can read it in cleartext. This key encrypts the Duplicati settings database, which itself contains the backup passphrase for your 46 GB backup. Compromising it is a short path to being able to decrypt your backups. `DUPLICATI__WEBSERVICE_PASSWORD` has the same exposure.
  - **Source:** [linuxserver.io — docker-duplicati docs](https://docs.linuxserver.io/general/understanding-puid-and-pgid/) — the image supports `FILE__` prefix to load secret values from bind-mounted files instead of passing them as env vars directly
  - **Current:** `SETTINGS_ENCRYPTION_KEY=<value>` and `DUPLICATI__WEBSERVICE_PASSWORD=<value>` as plain env vars in compose
  - **Recommended:** Use the `FILE__` prefix pattern — mount a secrets file and reference it:
    ```yaml
    environment:
      FILE__SETTINGS_ENCRYPTION_KEY: /run/secrets/duplicati_key
      FILE__DUPLICATI__WEBSERVICE_PASSWORD: /run/secrets/duplicati_webpass
    volumes:
      - ~/.homelab.secrets:/run/secrets/duplicati_key:ro
    ```
    Alternatively, ensure the `.env` file is `chmod 600` and that Docker socket access is restricted to admin-only processes.

---

### 🟡 Warning

- [ ] **`SETTINGS_ENCRYPTION_KEY` and `DUPLICATI__WEBSERVICE_PASSWORD` are the same value**
  - **Why it matters:** These serve completely different purposes. The encryption key protects the settings DB (and through it, the backup passphrase). The web password protects UI access. Using the same value for both means a single credential exposure compromises both your UI and your backup encryption. They should be distinct.
  - **Source:** Defense-in-depth principle; noted in r/selfhosted Duplicati hardening discussions
  - **Current:** Both env vars set to the same value
  - **Recommended:** Set `DUPLICATI__WEBSERVICE_PASSWORD` to a different value in your `.env` file. The encryption key should stay stable (changing it requires re-encrypting the DB); the web password can be rotated freely.

- [ ] **No healthcheck defined**
  - **Why it matters:** After long backup runs, Duplicati's web server can hang due to memory pressure. Docker's `restart: unless-stopped` only fires on process exit — a hung container stays "Up" and Uptime Kuma shows it green while backup jobs silently stop running.
  - **Source:** [linuxserver.io — duplicati image](https://docs.linuxserver.io/images/docker-duplicati/) — image ships no built-in healthcheck; must be defined in compose
  - **Current:** No `healthcheck` block in compose; confirmed `null` via inspect
  - **Recommended:**
    ```yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8200/"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    ```

- [ ] **Source volume mounted read-write — Duplicati only needs read access**
  - **Why it matters:** `/source` (→ `/share/appdata`, all container appdata) is mounted `rw`. Duplicati only reads from this directory to create backups — it never needs to write to it. An unnecessary write mount means a Duplicati bug, misconfiguration, or compromise could modify or delete the very appdata it's supposed to be protecting.
  - **Source:** Docker volume mount best practices — principle of least privilege; [linuxserver.io compose examples](https://docs.linuxserver.io/images/docker-duplicati/) show source mounts with `:ro`
  - **Current:** `${APPDATA_PATH}:/source` (read-write, no `:ro` flag)
  - **Recommended:** `${APPDATA_PATH}:/source:ro` — the `:ro` flag has no impact on backup performance and eliminates the write risk entirely.

---

### 🔵 Info

- [ ] **6 stale SQLite snapshot files in appdata (~83 MB)**
  - **Why it matters:** Old DB snapshots from past repair/migration operations are sitting in `/share/appdata/duplicati/`. They serve no ongoing purpose and add 83 MB of clutter that Duplicati backs up as part of its own appdata. Not urgent, but safe to clean up.
  - **Source:** Confirmed via `ls` — files named `backup *.sqlite`, oldest from Oct 2025
  - **Current:** 6 orphaned files: `backup BQAZJQKNVG`, `backup Duplicati-server`, `backup TNPRREQWUL` (two versions each)
  - **Recommended:** Delete them directly on the NAS01:
    ```bash
    ssh admin@192.168.1.33 'rm /share/appdata/duplicati/backup\ *.sqlite'
    ```
    The active job databases are `ETMYWAURXR.sqlite` (350 MB, current) and `Duplicati-server.sqlite` (184 KB) — do not touch those.

---

## What's working well

- ✅ Backup ran successfully today at 02:43 — daily schedule intact
- ✅ 5 consecutive daily filesets confirmed on NAS02 (Jun 5–9)
- ✅ Destination free space: 19.1 TB available — no capacity concerns
- ✅ Backup data encrypted at rest (`.aes` files on NAS02)
- ✅ All expected exclusion filters present (Plex cache, torrents, npm/letsencrypt)
- ✅ `restart: unless-stopped` set
- ✅ `SETTINGS_ENCRYPTION_KEY` required (`DUPLICATI__REQUIRE_DB_ENCRYPTION_KEY=true`)
- ✅ PUID/PGID 1000/1000 consistent with stack
- ✅ Config appdata is in Duplicati's own backup scope

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Plaintext secrets in docker inspect | Deferred — requires FILE__ secret mount setup | — | ⏳ Pending |
| Same value for encryption key and web password | Deferred — update `.env` manually | — | ⏳ Pending |
| No healthcheck | Applied via compose | 657a372 | ✅ `Health: healthy` confirmed via docker inspect |
| Source volume mounted read-write | Applied via compose — added `:ro` | 732e647 | ✅ `rw=false` confirmed via docker inspect; UI returns HTTP 200 |
| 6 stale SQLite snapshot files | Deleted via SSH | — | ✅ Only `ETMYWAURXR.sqlite` + `Duplicati-server.sqlite` remain (active DBs) |
