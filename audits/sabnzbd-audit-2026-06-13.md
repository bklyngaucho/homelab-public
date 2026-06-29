# Services Best Practice Audit — SABnzbd
2026-06-13

## Summary
7 findings: 0 🔴 critical · 4 🟡 warning · 3 🔵 info · 0 ⚪ flag

All findings are in-app UI settings. The compose definition is clean.

---

## SABnzbd

**Live state:** Up 27 minutes, healthy. All 20 connections to UsenetServer established over TLSv1.3. Logs clean.

**Compose:** ✅ linuxserver image, PUID/PGID/TZ set, LAN-only port binding, 1g mem_limit, healthcheck present, correct volume mounts, on homelab network.

---

### 🟡 Warning

- [x] **Categories not configured — cross-contamination risk**
  - **Why it matters:** Sonarr sends downloads tagged `tv`, Radarr sends `movies`, Radarr4K sends `movies4k`. Without matching categories in SABnzbd, all completed downloads land in the same folder. This means Sonarr can attempt to import a movie file, Radarr can grab a TV episode, and imports fail or go to the wrong library. Categories also let you set per-category post-processing paths.
  - **Source:** [TRaSH Guides — SABnzbd Paths and Categories](https://trash-guides.info/Downloaders/SABnzbd/Paths-and-Categories/)
  - **Current:** No categories defined (using default)
  - **Recommended:** Settings → Categories → add three categories:
    - Name: `tv` · Folder: `tv` (resolves to `/storage/downloads_ds/completed/tv`)
    - Name: `movies` · Folder: `movies`
    - Name: `movies4k` · Folder: `movies4k`

- [x] **Sorting must be disabled**
  - **Why it matters:** TRaSH explicitly requires Sorting to be entirely off. If SABnzbd's Sorting feature is enabled, it rearranges or renames downloaded files before Sonarr/Radarr see them. The ARR apps expect files in the exact structure SABnzbd produces — sorting mangles filenames and breaks imports.
  - **Source:** [TRaSH Guides — SABnzbd Basic Setup](https://trash-guides.info/Downloaders/SABnzbd/Basic-Setup/) ("MAKE SURE THAT SORTING IS ENTIRELY DISABLED")
  - **Current:** Unverified — fresh install may have sorting enabled
  - **Recommended:** Settings → Sorting → ensure all sorting options are OFF

- [x] **Abort incomplete downloads not verified**
  - **Why it matters:** When SABnzbd detects too many missing articles mid-download, it should abort and notify Sonarr/Radarr so they can search for an alternative release. Without this, a failed download sits in history as "completed with errors" and Sonarr/Radarr never look for a replacement.
  - **Source:** [TRaSH Guides — SABnzbd Basic Setup › Switches › Queue](https://trash-guides.info/Downloaders/SABnzbd/Basic-Setup/#queue)
  - **Current:** Unverified
  - **Recommended:** Settings → Switches → Queue → enable **"Abort jobs that cannot be completed"**

- [x] **Completed Download Handling not verified in ARR apps**
  - **Why it matters:** TRaSH requires specific checkboxes to be enabled in Sonarr/Radarr's SABnzbd download client config so they properly track completions and failures. Without these, the ARR apps can miss completed downloads still in queue/history, or fail to retry on failure.
  - **Source:** [TRaSH Guides — Recommended Sonarr/Radarr Settings](https://trash-guides.info/Downloaders/SABnzbd/Basic-Setup/#recommended-sonarrradarr-settings)
  - **Current:** Unverified — ARR apps were wired up but these specific checkboxes weren't confirmed
  - **Recommended:**
    - **Sonarr** → Settings → Download Clients → SABnzbd → scroll to bottom → check both boxes under **Completed Download Handling**
    - **Radarr / Radarr4K** → same, plus check both boxes under **Failed Download Handling**

---

### 🔵 Info

- [x] **Propagation delay not set**
  - **Why it matters:** When an NZB is grabbed immediately after posting, the articles may not yet have propagated to UsenetServer's servers, causing false missing-article errors. A 5-minute delay lets the post propagate before SABnzbd starts pulling.
  - **Source:** [TRaSH Guides — SABnzbd Basic Setup › Switches › Queue](https://trash-guides.info/Downloaders/SABnzbd/Basic-Setup/#queue)
  - **Current:** Default (0 minutes)
  - **Recommended:** Settings → Switches → Queue → **Propagation Delay: 5 minutes**

- [x] **Unwanted extensions blacklist not configured**
  - **Why it matters:** Malicious NZBs occasionally include executable files (.exe, .bat, .js, .ps1, etc.) alongside the media. Adding these to SABnzbd's unwanted extensions list and setting the action to "Fail job" prevents them from landing in your completed folder.
  - **Source:** [TRaSH Guides — Prevent unwanted extensions](https://trash-guides.info/Downloaders/SABnzbd/Basic-Setup/#prevent-unwanted-extensions)
  - **Current:** No unwanted extensions defined
  - **Recommended:** Settings → Switches → Queue → paste TRaSH's extension list → Mode: Blacklist → Action: Fail job (move to History). Full list at the TRaSH link above.

- [x] **No minimum free space threshold**
  - **Why it matters:** If `downloads_ds` fills up during a large download, SABnzbd fails mid-job and the partial download is wasted. A minimum free space threshold causes SABnzbd to pause the queue before the disk is full, giving you time to clean up.
  - **Source:** SABnzbd docs / community best practice
  - **Current:** No minimum set (default)
  - **Recommended:** Settings → Switches → Queue → **Minimum Free Space: 1024 MB** (1 GB)

---

## Remediation Log
2026-06-13

All findings were in-app UI settings — no compose changes required.

| Finding | Action | Commit | Verified |
|---|---|---|---|
| Categories not configured | Applied in SABnzbd UI — added movies, tv, movies4k with subfolder paths. movies4k folder created on NFS share via SSH before it appeared in the dropdown. | — | ✅ Categories saved |
| Sorting must be disabled | Verified disabled in SABnzbd → Settings → Sorting | — | ✅ Confirmed off |
| Abort incomplete downloads | Enabled in SABnzbd → Settings → Switches → Queue | — | ✅ Enabled |
| Completed Download Handling in ARR apps | Verified checkboxes in Sonarr, Radarr, Radarr4K download client config | — | ✅ Confirmed |
| Propagation delay | Set to 5 minutes in SABnzbd → Settings → Switches → Queue | — | ✅ Set |
| Unwanted extensions blacklist | Configured in SABnzbd → Settings → Switches — extensions pasted, action set to Fail | — | ✅ Set |
| Minimum free space | Set to 1G for both Temporary and Completed folders in SABnzbd → Settings → Folders (Advanced) | — | ✅ Set |
