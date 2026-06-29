# Services Best Practice Audit — Stirling PDF
2026-06-12

## Summary
1 finding: 0 🔴 critical · 1 🟡 warning · 0 🔵 info · 0 ⚪ flag — all resolved ✅

---

## Stirling PDF

### 🟡 Warning

- [x] **No memory limit — service already using ~888 MiB at idle**
  - **Why it matters:** Stirling PDF is a Spring Boot application that bundles LibreOffice, Ghostscript, and Tesseract. At idle (no active jobs), it's already using **887.6 MiB**. During actual processing — Office → PDF conversion, OCR on large scanned documents, multi-page merges — memory can spike substantially beyond the idle baseline. With no limit, a memory spike during a large job competes directly with the rest of the 20-container stack for the NAS01's RAM.
  - **Current:** `Memory=0` (unbounded); live usage 887.6 MiB / 62.72 GiB (1.38%)
  - **Fix applied:** `mem_limit: 2g` — ~2× idle headroom to accommodate processing spikes without putting the stack at risk

- [x] **`DOCKER_ENABLE_SECURITY: "false"` — service is publicly accessible without authentication** *(finding invalidated — see note)*
  - **Why it matters:** With security disabled, Stirling PDF has no login page. The service is proxied publicly via `pdf.yourdomain.com` through NPM/Cloudflare — meaning anyone on the internet can visit that URL and use all PDF features with no credentials. For a personal homelab this is likely intentional and low-risk, but it means anyone could use your server as a free PDF processing endpoint, and any document processed through it transits your infrastructure.
  - **Current:** `DOCKER_ENABLE_SECURITY: "false"` — intentionally set (per CLAUDE.md)
  - **Recommended options:**
    - Enable security (`DOCKER_ENABLE_SECURITY: "true"`) and set up a login — adds a basic auth gate
    - Add NPM Access List (IP allowlist or basic auth) to the `pdf.yourdomain.com` proxy host — restricts public access without changing Stirling PDF config
    - Leave as-is if the convenience of unauthenticated access is worth the trade-off
  - **Finding invalidated:** `pdf.yourdomain.com` shows Stirling PDF's own login page — the security/auth system is active regardless of this flag. `DOCKER_ENABLE_SECURITY: "false"` likely disables a specific sub-feature (e.g. certificate handling or a particular auth mode) rather than the login gate itself. No action needed.

---

## What's working well

- ✅ Built-in healthcheck provided by image — container shows `Health=healthy` ✅
- ✅ Logs clean — only scheduled temp file cleanup messages, no errors ✅
- ✅ Proxied via NPM at `pdf.yourdomain.com` — external access goes through Cloudflare, not directly to the host ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID`/`PGID` set — correct file permission handling ✅
- ✅ Volumes for `/configs` and `/logs` — settings persist through updates ✅

---

## Manual Follow-up Steps

- [ ] **Authentication for public PDF access**
  If you want to gate access without enabling Stirling PDF's login system, add an NPM Access List to the `pdf.yourdomain.com` proxy host:
  - Navigate to: `http://192.168.1.33:81` → Proxy Hosts → `pdf.yourdomain.com` → Edit → Access Lists tab
  - Options: IP allowlist (LAN subnet only) or Basic Auth (username/password)
  - Alternatively, set `DOCKER_ENABLE_SECURITY: "true"` in compose to enable Stirling PDF's native login

---

## Remediation Log
2026-06-12

| Finding | Action | Commit | Verified |
|---|---|---|---|
| No mem_limit (887.6 MiB idle) | Added `mem_limit: 2g` via compose | see below | ✅ |
| DOCKER_ENABLE_SECURITY: false | Finding invalidated — Stirling PDF login page is active at pdf.yourdomain.com; auth system is working | — | ✅ Confirmed by user |
