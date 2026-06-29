# Services Best Practice Audit — Organizr
2026-06-11

## Summary
2 findings: 0 🔴 critical · 0 🟡 warning · 2 🔵 info

---

## Organizr

### 🔵 Info

- [ ] **No memory limit**
  - **Why it matters:** Organizr is a lightweight PHP/Nginx app — typical usage well under 256 MB. No practical risk on the NAS01's 62 GB, but consistent with the stack.
  - **Current:** `Memory: 0`
  - **Recommended:** `mem_limit: 256m`

- [ ] **`idrac_t440` tab URL missing scheme — link will be broken**
  - **Why it matters:** The idrac_t440 tab is configured with URL `192.168.1.4` (bare IP, no `http://` or `https://` prefix). Browsers won't follow a bare IP as a hyperlink — clicking the tab will do nothing or show an error.
  - **Source:** DB inspection — `tabs.url = '192.168.1.4'`
  - **Current:** `192.168.1.4`
  - **Recommended:** Organizr UI → Edit Tab → URL: `https://192.168.1.4`
  - **Manual fix:** Organizr UI → Tabs → idrac_t440 → Edit → update URL to include scheme

---

## Remediation Log
2026-06-11

| Finding | Action | Commit | Verified |
|---|---|---|---|
| No memory limit | Applied via compose — `mem_limit: 256m` | 40a04b8 | ✅ `Mem=268435456` |
| `idrac_t440` tab missing URL scheme | Manual fix — user updated URL to `https://192.168.1.4` in Organizr UI | — | ✅ |

---

## What's working well

- ✅ Built-in healthcheck (checks `nginx_status` + `php_status`) — `Health=healthy` confirmed ✅
- ✅ Running on `homelab` Docker network ✅
- ✅ Auth enabled — 2 users (`tphillippe`/Admin, `admin`/Co-Admin), both using internal auth with bcrypt-hashed passwords ✅
- ✅ `branch: v2-master` — stable Organizr release channel; code is git-pulled on each container start (the Organizr Docker model is intentionally thin-image + startup git pull, not baked-in code) ✅
- ✅ Tab URLs use host IP (`192.168.1.33`) — correct for a browser dashboard; users' browsers need to reach service URLs, not the Organizr container ✅
- ✅ LAN-only — not NPM-proxied externally, auth still required; acceptable for homelab ✅
- ✅ `restart: unless-stopped` ✅
- ✅ `PUID: 1000 / PGID: 1000` consistent with stack ✅
- ✅ `fpm: "false"` — mod_php mode, fine for single-user homelab dashboard ✅
