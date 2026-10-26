#!/usr/bin/env python3
"""
build.py — rebuild the vault data for the static site.

Reads every Markdown file in content/notes/, pulls its YAML frontmatter, and
writes:

  vault-index.json      — 元数据清单（首屏只加载这个，约几十 KB）
  vault-notes/<slug>.json — 每篇正文，打开哪篇才取哪篇
  vault.json            — 兼容/回滚用的全量数据（前端不再使用）

2026-10-24: 数据拆分。之前整卷译文会把 vault.json 撑到 350 KB+，首屏全量下载
+ 解析；现在首屏只拿清单，正文按需请求。

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

Safety: every file is written atomically (tempfile + fsync + os.replace);
unchanged files are left untouched; the previous version is snapshotted to
.build-backups/ (last BACKUP_KEEP copies kept).
"""

import json
from html import escape as html_escape
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from html import escape as hesc
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"                        # nginx root：只放对外产物
NOTES_DIR = ROOT / "content" / "notes"
DATA_FILE = PUBLIC / "vault.json"               # legacy full payload (fallback)
INDEX_FILE = PUBLIC / "vault-index.json"        # manifest used by the SPA
NOTES_OUT = PUBLIC / "vault-notes"              # one JSON per note
SEARCH_FILE = PUBLIC / "search-index.json"      # full-text index, fetched on first Ctrl-K
FEED_FILE = PUBLIC / "feed.xml"                 # RSS 2.0
SITEMAP_FILE = PUBLIC / "sitemap.xml"
CONFIG = ROOT / "content" / "vault.json"

SITE = os.environ.get("SITE_URL", "https://eregion.cn")
TZ = timezone(timedelta(hours=8))

BACKUP_DIR = ROOT / ".build-backups"
BACKUP_KEEP = 10

WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


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


def split_chapters(body):
    """按 ## 切章（跳过 ``` 围栏），与前端 splitChapters 保持一致。"""
    lines = body.split("\n")
    secs = []
    cur = {"title": "", "md": []}
    fence = False
    for line in lines:
        if line.strip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if m:
            if cur["title"] or "\n".join(cur["md"]).strip():
                secs.append(cur)
            cur = {"title": m.group(1).strip(), "md": [line]}
        else:
            cur["md"].append(line)
    if cur["title"] or "\n".join(cur["md"]).strip():
        secs.append(cur)
    return secs


def _inline_html(s):
    s = html_escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
               lambda m: f'<img src="{abs_url(m.group(2))}" alt="{m.group(1)}" style="max-width:100%">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: f'<a href="{abs_url(m.group(2))}">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md_to_html(body):
    """够用的 Markdown→HTML：标题/段落/引用/列表/代码/图片/链接。"""
    out = []
    lines = body.split("\n")
    i = 0
    in_code = False
    code = []
    lang = ""
    para = []

    def flush_para():
        if para:
            out.append("<p>" + _inline_html(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                out.append(
                    '<pre><code class="language-%s">%s</code></pre>'
                    % (lang, html_escape("\n".join(code)))
                )
                code = []
                in_code = False
            else:
                flush_para()
                lang = line.strip()[3:].strip()
                in_code = True
            i += 1
            continue
        if in_code:
            code.append(line)
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline_html(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.startswith(">"):
            flush_para()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> ").rstrip())
                i += 1
            out.append("<blockquote><p>" + _inline_html(" ".join(quote)) + "</p></blockquote>")
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_para()
            out.append("<ul>")
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                out.append("<li>" + _inline_html(re.sub(r"^\s*[-*]\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("</ul>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            out.append("<ol>")
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                out.append("<li>" + _inline_html(re.sub(r"^\s*\d+\.\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("</ol>")
            continue
        if not line.strip():
            flush_para()
            i += 1
            continue
        para.append(line.strip())
        i += 1
    flush_para()
    return "\n".join(out)


def abs_url(u):
    if u.startswith("http") or u.startswith("mailto:"):
        return u
    if u.startswith("#"):
        return SITE + "/" + u
    return SITE + (u if u.startswith("/") else "/" + u)


def plain_text(body):
    """Markdown -> plain text, 与前端 MD.plain() 保持一致（避免字数对不上）。"""
    s = re.sub(r"```[\s\S]*?```", " ", body)
    s = re.sub(r"^\s*>\s?\[![^\]]+\]\s*", "", s, flags=re.M)
    s = re.sub(r"^\s*>\s?", "", s, flags=re.M)
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.M)
    s = re.sub(r"^\s*\|.*\|\s*$", " ", s, flags=re.M)
    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
               lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"</?[a-z][^>]*>", "", s, flags=re.I)
    s = re.sub(r"[*_~`$>#]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


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
            "epub": str(meta.get("epub") or ""),
            "source": str(meta.get("source") or "").strip(),
            "source_url": str(meta.get("source_url") or "").strip(),
            "license": str(meta.get("license") or "").strip(),
            "modified": str(meta.get("modified") or "").strip(),
            "summary": str(meta.get("summary") or "").strip(),
            "body": body.rstrip() + "\n",
        })

    for n in notes:
        for key in ("pdf", "epub"):
            path = n[key]
            if path and not path.startswith("http") and not (PUBLIC / path).exists():
                print(f"  ! {n['slug']}: {key.upper()} not found at {path}")

    # resolve [[wikilinks]] -> slugs, so the frontend doesn't need bodies at boot
    by_slug = {n["slug"]: n for n in notes}
    by_title = {n["title"].lower(): n for n in notes}

    def slugify(s):
        s = s.strip().lower()
        s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s)
        return s.strip("-")

    def resolve(key):
        k = key.strip().lower()
        n = by_slug.get(k) or by_title.get(k)
        if n:
            return n
        s = slugify(k)
        return next((x for x in notes if slugify(x["title"]) == s), None)

    for n in notes:
        links = []
        for m in WIKI.finditer(n["body"]):
            t = resolve(m.group(1))
            if t and t["slug"] != n["slug"] and t["slug"] not in links:
                links.append(t["slug"])
        n["links"] = links

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


def write_json(path, payload, label):
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    if path.exists():
        snapshot(path)
    atomic_write(path, text)
    print(f"  ({label} updated)")
    return True


def write_text(path, text, label):
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    if path.exists():
        snapshot(path)
    atomic_write(path, text)
    print(f"  ({label} updated)")
    return True


def rfc822(value):
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except Exception:
            dt = datetime.now(TZ)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def main():
    vault = collect()
    notes = vault["notes"]

    # 1) 全量（兼容旧前端 / 回滚用，保持 indent 便于人看）
    legacy = {"name": vault["name"], "tagline": vault["tagline"], "notes": notes}
    legacy_text = json.dumps(legacy, ensure_ascii=False, indent=1) + "\n"
    if not (DATA_FILE.exists() and DATA_FILE.read_text(encoding="utf-8") == legacy_text):
        if DATA_FILE.exists():
            snapshot(DATA_FILE)
        atomic_write(DATA_FILE, legacy_text)

    # 2) 清单：只留元数据 + 字数指标 + 链接
    index_notes = []
    plains = {}
    for n in notes:
        plain = plain_text(n["body"])
        plains[n["slug"]] = plain
        cjk = len(CJK_RE.findall(plain))
        latin = len([w for w in re.sub(CJK_RE, " ", plain).split() if w])
        index_notes.append({
            "slug": n["slug"],
            "title": n["title"],
            "folder": n["folder"],
            "tags": n["tags"],
            "created": n["created"],
            "updated": n["updated"],
            "pdf": n["pdf"],
            "epub": n["epub"],
            "source": n["source"],
            "source_url": n["source_url"],
            "license": n["license"],
            "modified": n["modified"],
            "split": len(n["body"]) > 150000,
            "chapters": len(split_chapters(n["body"])),
            "summary": n["summary"],
            "excerpt": plain[:200],
            "chars": len(plain),
            "cjk": cjk,
            "words": latin,
            "links": n["links"],
        })
    write_json(INDEX_FILE, {
        "name": vault["name"],
        "tagline": vault["tagline"],
        "notes": index_notes,
    }, "vault-index.json")

    # 3) 每篇正文单独一个文件
    NOTES_OUT.mkdir(exist_ok=True)
    live = set()
    for n in notes:
        dest = NOTES_OUT / f"{n['slug']}.json"
        live.add(dest.name)
        write_json(dest, {"slug": n["slug"], "body": n["body"]}, f"vault-notes/{dest.name}")

        # 重型笔记：额外输出目录 + 分章 JSON（前端只加载当前章）
        if len(n["body"]) > 150000:
            chs = split_chapters(n["body"])
            toc = NOTES_OUT / f"{n['slug']}.toc.json"
            live.add(toc.name)
            write_json(toc, {"slug": n["slug"], "title": n["title"],
                             "titles": [c["title"] for c in chs]}, f"vault-notes/{toc.name}")
            for i, c in enumerate(chs):
                cf = NOTES_OUT / f"{n['slug']}.c{i}.json"
                live.add(cf.name)
                write_json(cf, {"title": c["title"], "md": "\n".join(c["md"])},
                           f"vault-notes/{cf.name}")
    for stale in NOTES_OUT.glob("*.json"):
        if stale.name not in live:
            stale.unlink()
            print(f"  (removed stale vault-notes/{stale.name})")

    # 4) 全文搜索索引（前端第一次 Ctrl-K 才拉取）
    write_json(SEARCH_FILE, {
        "notes": [
            {
                "slug": n["slug"],
                "title": n["title"],
                "folder": n["folder"],
                "tags": n["tags"],
                "text": plains.get(n["slug"], ""),
            }
            for n in notes
        ],
    }, "search-index.json")

    # 5) RSS 2.0（订阅用；链接仍是 hash 路由，读者点开即可）
    recent = sorted(notes, key=lambda x: (x["updated"] or x["created"] or ""), reverse=True)
    items = []
    for n in recent:
        desc = n["summary"] or plains.get(n["slug"], "")[:200]
        body = n["body"]
        if len(body) <= 80000:
            html_body = md_to_html(body)
        else:
            titles = [c["title"] for c in split_chapters(body) if c["title"].strip()]
            html_body = (
                '<p><em>篇幅较长，全文请点标题阅读；章节目录：</em></p><ul>'
                + "".join(f"<li>{html_escape(t)}</li>" for t in titles)
                + "</ul>"
            )
        content_tag = (
            "      <content:encoded><![CDATA[" + html_body.replace("]]>", "]]&gt;") + "]]></content:encoded>"
        )
        items.append(
            f"""    <item>
      <title>{hesc(n['title'])}</title>
      <link>{SITE}/#/n/{n['slug']}</link>
      <guid isPermaLink="false">{SITE}/n/{n['slug']}</guid>
      <pubDate>{rfc822(n['updated'] or n['created'])}</pubDate>
      <category>{hesc(n['folder'])}</category>
      <description>{hesc(desc)}</description>
{content_tag}
    </item>"""
        )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{hesc(vault['name'])}</title>
    <link>{SITE}/</link>
    <description>{hesc(vault['tagline'] or '个人技术笔记')}</description>
    <language>zh-CN</language>
    <lastBuildDate>{rfc822(recent[0]["updated"] or recent[0]["created"]) if recent else rfc822(datetime.now(TZ))}</lastBuildDate>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    write_text(FEED_FILE, feed, "feed.xml")

    # 6) sitemap：hash 路由下每篇没有独立 URL，只能先给首页
    latest = (recent[0]["updated"] or recent[0]["created"])[:10] if recent else datetime.now(TZ).strftime("%Y-%m-%d")
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{SITE}/</loc>
    <lastmod>{latest}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{SITE}/feed.xml</loc>
    <changefreq>weekly</changefreq>
    <priority>0.4</priority>
  </url>
</urlset>
"""
    write_text(SITEMAP_FILE, sitemap, "sitemap.xml")

    # 7) 按站内实际用字裁剪字体（字符集不变时脚本会自己跳过）
    try:
        subprocess.run([sys.executable, "/usr/local/bin/subset-techsite-fonts.py"],
                       check=False, timeout=120)
    except Exception as e:  # 字体裁剪失败不影响页面，只是字号偏大
        print(f"  ! font subset skipped: {e}", file=sys.stderr)

    folders = sorted({n["folder"] for n in notes})
    pdfs = sum(1 for n in notes if n["pdf"])
    index_size = INDEX_FILE.stat().st_size
    print(f"Built {len(notes)} notes across {len(folders)} subjects ({pdfs} with PDFs).")
    print(f"  index: {index_size/1024:.1f} KB, per-note JSON in {NOTES_OUT.name}/")
    for n in notes:
        print(f"  · {n['slug']:<28} {n['folder']}")


if __name__ == "__main__":
    main()
