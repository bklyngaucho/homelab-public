---
name: feedback-keep-it-simple
description: "Before proposing a solution to a snag, pause and check if we're heading toward over-engineering or fragility"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5673a38f-2fbf-4500-9a6d-d50b12c3f378
---

When we hit a snag implementing something, or owner suggests a new approach, pause before proposing a solution and ask: "Are we about to over-engineer this, or is there a simpler path?"

**Why:** The Technitium MCP setup is the canonical example — we ended up with a Python proxy LaunchAgent + Node MCP server + wrapper script, three layers deep, just to make API calls that a single curl command via Desktop Commander handles fine. When we hit the EHOSTUNREACH wall, the right call was to ask "do we even need the MCP?" before adding more machinery.

**How to apply:** Any time a proposed fix involves adding a new service, a new layer of indirection, or more than ~2 moving parts, surface the complexity concern first. Phrase it like: "Before I go down this path — is this getting complicated enough that we should step back and ask if there's a simpler way?" owner's default preference is the simple, low-maintenance solution even if it's less elegant.
