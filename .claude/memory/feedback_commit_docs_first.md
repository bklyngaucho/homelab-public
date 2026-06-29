---
name: feedback-commit-docs-first
description: "Before committing to the homelab repo, check that README and relevant docs are updated to reflect the change"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5673a38f-2fbf-4500-9a6d-d50b12c3f378
---

Before running git add/commit on the homelab repo, pause and check whether any documentation needs updating:

- **README.md** — container count, container table, DNS/networking section, repo structure listing
- **CLAUDE.md** — notable config details, key paths, tooling notes
- **docs/*.md** — whichever doc covers the area being changed (storage, external-access, operations, etc.)

**Why:** We committed the IoT VLAN plan and DNS changes without updating the README, and only caught it afterward. The README had a stale container count (19 vs 20), Technitium missing from the stack table, and no mention of LAN DNS. Keeping docs in sync at commit time is less work than a follow-up pass later.

**How to apply:** As part of the homelab-git-push skill workflow, after checking `git diff --stat`, ask: "Does the README or any doc in `docs/` need updating to reflect what changed?" If yes, update before staging.
