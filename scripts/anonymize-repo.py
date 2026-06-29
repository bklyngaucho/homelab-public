#!/usr/bin/env python3
"""
anonymize-repo.py — Create a shareable, anonymized copy of the homelab repo.

Replaces personally identifying strings (username, domain, public IP, email,
API key placeholders) with generic equivalents so the repo can be shared
publicly without leaking private info.

Usage:
    python3 scripts/anonymize-repo.py [--output /path/to/output-dir]

Defaults to outputting to ../homelab-public/ relative to the repo root.
"""

import os
import re
import sys
import shutil
import argparse
from pathlib import Path

# ── Replacements ─────────────────────────────────────────────────────────────
# Order matters: more specific patterns first.
REPLACEMENTS = [
    # Public IP — must go before any 192.168 patterns
    (r"47\.16\.128\.234", "YOUR_PUBLIC_IP"),

    # Personal domain (all subdomains too)
    (r"yourusername\.com", "yourdomain.com"),
    (r"yourusername-appdata-backup", "yourusername-appdata-backup"),
    (r"yourusername", "yourusername"),

    # Personal email
    (r"owner\.phillippe@gmail\.com", "your.email@gmail.com"),
    # Email URL-encoded (watchtower SMTP URL)
    (r"owner\.phillippe%40gmail\.com", "your.email%40gmail.com"),

    # Cloudflare Zone ID
    (r"YOUR_CF_ZONE_ID", "YOUR_CF_ZONE_ID"),

    # Git remote
    (r"github\.com/yourusername/homelab", "github.com/yourusername/homelab"),

    # Hardware names
    (r"NAS01\s+NAS01", "NAS01"),           # "NAS01" → "NAS01"
    (r"NAS01", "NAS01"),                  # bare model number
    (r"NAS01", "NAS01"),                     # any remaining NAS01 reference
    (r"dell\s+poweredge\s+NAS02", "NAS02"),  # full NAS02 name → NAS02 for clarity
    (r"dell\s+NAS02", "NAS02"),
    (r"\bt440\b", "NAS02"),                 # bare NAS02

    # Personal name (whole-word match to avoid partial hits)
    (r"\btoby\b", "owner"),
]

# ── Files / dirs to skip entirely ────────────────────────────────────────────
SKIP_DIRS = {".git", "__pycache__", ".DS_Store"}
SKIP_FILES = {
    ".env", ".hl.env", ".homelab.secrets",
    "health_cache.json",          # runtime cache, not useful to share
}
SKIP_EXTENSIONS = {
    ".skill",   # binary zip archives
    ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf",
    ".pyc",
}

# Files to omit completely from the output (sensitive even when redacted)
OMIT_FILES = {
    "compose/.env",
    "scripts/.hl.env",
    ".claude/memory/user_hiphop.md",   # personal preference note
    ".claude/memory/project_cloudflare.md",  # contains zone ID
}


def should_skip(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    parts = rel.parts

    # Skip hidden dirs (except .claude which has useful memory structure)
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return True

    if path.is_file():
        if path.name in SKIP_FILES:
            return True
        if path.suffix.lower() in SKIP_EXTENSIONS:
            return True
        if str(rel) in OMIT_FILES:
            return True

    return False


def anonymize_text(text: str) -> str:
    for pattern, replacement in REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def copy_anonymized(repo_root: Path, output_dir: Path):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    skipped = []
    processed = []

    for src in sorted(repo_root.rglob("*")):
        if src.is_dir():
            continue
        if should_skip(src, repo_root):
            skipped.append(src.relative_to(repo_root))
            continue

        rel = src.relative_to(repo_root)
        dst = output_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Try to read as text; fall back to binary copy
        try:
            original = src.read_text(encoding="utf-8")
            anonymized = anonymize_text(original)
            dst.write_text(anonymized, encoding="utf-8")
            if original != anonymized:
                processed.append((rel, "anonymized"))
            else:
                processed.append((rel, "copied"))
        except (UnicodeDecodeError, PermissionError):
            shutil.copy2(src, dst)
            processed.append((rel, "binary copy"))

    print(f"\n✅  Output: {output_dir}")
    print(f"\nProcessed ({len(processed)} files):")
    for rel, action in processed:
        marker = "✏️ " if action == "anonymized" else "  "
        print(f"  {marker} {rel}")

    if skipped:
        print(f"\nSkipped ({len(skipped)} files):")
        for rel in skipped:
            print(f"    {rel}")

    print("\nDone. Review the output directory before publishing.")


def main():
    parser = argparse.ArgumentParser(description="Anonymize homelab repo for public sharing")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: ../homelab-public/ next to the repo)"
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent.resolve()
    output_dir = Path(args.output) if args.output else repo_root.parent / "homelab-public"

    print(f"Repo root : {repo_root}")
    print(f"Output dir: {output_dir}")
    print(f"\nApplying {len(REPLACEMENTS)} replacement(s)...")

    copy_anonymized(repo_root, output_dir)


if __name__ == "__main__":
    main()
