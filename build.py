#!/usr/bin/env python3
"""
build.py — rebuild the vault data for the static site.

Reads every Markdown file in content/notes/, pulls its YAML frontmatter, and
writes the result to vault.json (the SPA fetches it at runtime). index.html is
no longer rewritten: it is a static shell.

2026-10-24: data externalised (was: inline <script id="vault-data"> block) so
the HTML shell stays small and the JSON can be cached/revalidated separately.

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

Files whose name starts with an underscore are skipped.

Safety: vault.json is written atomically (tempfile + fsync + os.replace);
when content is unchanged nothing is written; before a change the previous
file is copied to .build-backups/ (last BACKUP_KEEP copies kept).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_DIR = ROOT / "content" / "notes"
DATA_FILE = ROOT / "vault.json"
CONFIG = ROOT / "content" / "vault.json"

BACKUP_DIR = ROOT / ".build-backups"
BACKUP_KEEP = 10


def parse_frontmatter(text):
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
            continue
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


def atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def snapshot(path):
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = BACKUP_DIR / f"{path.name}.{stamp}"
    dest.write_bytes(path.read_bytes())
    keep = sorted(BACKUP_DIR.glob(f"{path.name}.*"), key=lambda p: p.name)[-BACKUP_KEEP:]
    for old in BACKUP_DIR.glob(f"{path.name}.*"):
        if old not in keep:
            old.unlink(missing_ok=True)


def write(vault):
    payload = json.dumps(vault, ensure_ascii=False, indent=1) + "\n"
    if DATA_FILE.exists() and DATA_FILE.read_text(encoding="utf-8") == payload:
        print("  (no change, vault.json untouched)")
        return
    if DATA_FILE.exists():
        snapshot(DATA_FILE)
    atomic_write(DATA_FILE, payload)
    print("  (vault.json updated atomically, previous copy in .build-backups/)")


def main():
    vault = collect()
    write(vault)
    # 按站内实际用字裁剪字体（字符集不变时脚本会自己跳过）
    try:
        subprocess.run([sys.executable, "/usr/local/bin/subset-techsite-fonts.py"],
                       check=False, timeout=120)
    except Exception as e:  # 字体裁剪失败不影响页面，只是字号偏大
        print(f"  ! font subset skipped: {e}", file=sys.stderr)
    folders = sorted({n["folder"] for n in vault["notes"]})
    pdfs = sum(1 for n in vault["notes"] if n["pdf"])
    print(f"Built {len(vault['notes'])} notes across {len(folders)} subjects ({pdfs} with PDFs).")
    for n in vault["notes"]:
        print(f"  · {n['slug']:<28} {n['folder']}")


if __name__ == "__main__":
    main()
