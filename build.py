#!/usr/bin/env python3
"""
build.py — refresh the vault index inside index.html.

Reads every Markdown file in content/notes/, pulls its YAML frontmatter,
and writes the result into the data block of index.html.

Usage:
    python3 build.py            # rebuild
    python3 build.py --serve    # rebuild, then serve on http://localhost:8000

Frontmatter fields (all optional except title):

    ---
    title:   Attention is a soft dictionary lookup
    folder:  03 Machine Learning
    tags:    [deep-learning, nlp]
    created: 2026-05-16
    updated: 2026-07-22
    pdf:     content/pdf/transformers.pdf
    summary: One or two sentences used on cards and hover previews.
    ---

The filename becomes the note's slug, so `transformers-attention.md`
is linked from other notes as [[transformers-attention]].
Files whose name starts with an underscore are skipped, so `_template.md`
and `_draft-*.md` stay out of the published site.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_DIR = ROOT / "content" / "notes"
INDEX = ROOT / "index.html"
CONFIG = ROOT / "content" / "vault.json"
START, END = "/*VAULT:START*/", "/*VAULT:END*/"


def parse_frontmatter(text):
    """Return (metadata dict, body). Falls back to a tiny parser if PyYAML is absent."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return {}, text
    raw, body = parts[0][3:].strip("\n"), parts[1].lstrip("\n")
    try:
        import yaml
        meta = yaml.safe_load(raw) or {}
    except Exception:
        meta = {}
        for line in raw.splitlines():
            if ":" not in line or line.strip().startswith("#"):
                continue
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def normalise_tags(value):
    if isinstance(value, list):
        return [str(t).strip().lstrip("#").lower() for t in value if str(t).strip()]
    if isinstance(value, str):
        return [t.strip().lstrip("#").lower()
                for t in re.split(r"[,\s]+", value.strip("[]")) if t.strip()]
    return []


def collect():
    if not NOTES_DIR.is_dir():
        sys.exit(f"No notes directory at {NOTES_DIR}")

    notes = []
    for path in sorted(NOTES_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue  # drafts and templates stay out of the build
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        slug = path.stem
        notes.append({
            "slug": slug,
            "title": str(meta.get("title") or slug.replace("-", " ").title()),
            "folder": str(meta.get("folder") or "Notes"),
            "tags": normalise_tags(meta.get("tags")),
            "created": str(meta.get("created") or ""),
            "updated": str(meta.get("updated") or meta.get("created") or ""),
            "pdf": str(meta.get("pdf") or ""),
            "summary": str(meta.get("summary") or "").strip(),
            "body": body.rstrip() + "\n",
        })

    for n in notes:
        if n["pdf"] and not (ROOT / n["pdf"]).exists():
            print(f"  ! {n['slug']}: PDF not found at {n['pdf']}")

    config = {"name": "Study Vault", "tagline": ""}
    if CONFIG.exists():
        try:
            config.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            print(f"  ! Ignoring {CONFIG.name}: {e}")

    return {"name": config["name"], "tagline": config["tagline"], "notes": notes}


def write(vault):
    html = INDEX.read_text(encoding="utf-8")
    payload = "window.VAULT = " + json.dumps(vault, ensure_ascii=False, indent=1) + ";"
    # Replace the content of the <script id="vault-data"> block. Anchoring on
    # the script element (rather than the /*VAULT:START*/ comment markers) is
    # robust even when a note body happens to contain marker-like text.
    new_html, n = re.subn(
        r'(<script id="vault-data">)[\s\S]*?(</script>)',
        lambda m: m.group(1) + "\n" + payload + "\n" + m.group(2),
        html,
        count=1,
    )
    if n == 0:
        sys.exit('index.html is missing the <script id="vault-data"> block.')
    INDEX.write_text(new_html, encoding="utf-8")


def main():
    vault = collect()
    write(vault)
    folders = sorted({n["folder"] for n in vault["notes"]})
    pdfs = sum(1 for n in vault["notes"] if n["pdf"])
    print(f"Built {len(vault['notes'])} notes across {len(folders)} subjects ({pdfs} with PDFs).")
    for n in vault["notes"]:
        print(f"  · {n['slug']:<28} {n['folder']}")

    if "--serve" in sys.argv:
        import http.server, socketserver, functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print("\nServing at http://localhost:8000  (Ctrl+C to stop)")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print()


if __name__ == "__main__":
    main()
