# Study Vault

A personal notes site: Obsidian's three-pane reading layout, in a warm cream-and-clay palette. Write notes as plain Markdown files, run one command, get a static site you can host anywhere.

No build tooling, no dependencies, no framework. `index.html` is the entire application.

> **Attribution**
>
> This is a cleaned-up fork of the `Notes/` project in [Sulcop5/Sulcop5.github.io](https://github.com/Sulcop5/Sulcop5.github.io) by [@Sulcop5](https://github.com/Sulcop5) — his personal notes and PDFs were removed, and the bundled fonts were kept. The original repository has **no license**, so this copy is provided for **learning and personal use with attribution**, not for commercial reuse without the author's permission.
>
> The bundled fonts carry their own licenses: Sarasa Gothic (更沙黑体) is under the SIL Open Font License; the Shanggu Serif (上古明朝体) license should be verified before redistributing.

---

## Run it

```bash
python3 build.py --serve      # rebuild and open http://localhost:8000
```

Or rebuild only:

```bash
python3 build.py
```

You can also just double-click `index.html` — everything is embedded, so it works straight off the filesystem. PDF previews behave better over `http://` than `file://`, so the local server is worth using while you write.

## Add a note

1. Drop a Markdown file into `content/notes/`. **The filename is the note's ID** — `bayes-theorem.md` is linked elsewhere as `[[bayes-theorem]]`.
2. Give it frontmatter:

```markdown
---
title: "Bayes' theorem is bookkeeping for belief"
folder: 02 Mathematics
tags: [statistics, inference]
created: 2026-07-24
updated: 2026-07-26
pdf: content/pdf/bayes.pdf
summary: "One or two sentences. Used on cards, in search, and in hover previews."
---

Your note starts here.
```

Only `title` really matters; everything else has a sensible default. Filenames starting with `_` are skipped, so `_template.md` and any `_draft-…` files stay unpublished. `folder` groups notes in the sidebar and creates the subject list.

### Attaching a PDF

Put the file in `content/pdf/` and point `pdf:` at it. The note then gets a download button and an inline preview. Notes without a `pdf:` field simply don't show the panel.

## What the Markdown supports

Standard Markdown, plus the Obsidian pieces that matter for study notes:

| Syntax | Result |
| --- | --- |
| `[[note-id]]` / `[[note-id\|Custom text]]` | Internal link, with hover preview |
| `[[note-id#Heading]]` | Link that jumps to a section |
| `#tag` | Clickable tag, also collected into the filter bar |
| `> [!note]` `> [!tip]` `> [!warning]` `> [!info]` | Coloured callouts |
| `- [ ]` / `- [x]` | Task lists |
| `==highlight==` | Highlighted text |
| `$inline$` and `$$display$$` | Math, rendered with KaTeX |
| ` ```lang ` | Code block with a language label and copy button |

Links are two-way: whenever note A links to note B, B automatically grows a **Linked from** entry and a node in the graph. Nothing to maintain by hand.

Math uses KaTeX from a CDN. If you're offline or the CDN is blocked, the raw TeX shows instead — nothing breaks.

## Getting around

| Key | Action |
| --- | --- |
| `Ctrl`/`⌘` + `K`, or `/` | Quick switcher — searches titles, tags, and full text |
| `↑` `↓` `↵` | Move and open in the switcher |
| `Esc` | Close |

The ribbon down the left edge toggles the file explorer, opens search, jumps to the graph, cycles reading width (normal → wide → full), and switches light/dark. Your choices persist between visits.

## Make it yours

**Name and intro** — edit `content/vault.json`. The `tagline` accepts inline HTML.

**Colours** — every colour is a CSS variable at the top of `index.html`. The light theme lives in `:root`, dark in `[data-theme="dark"]`. To shift the accent, change `--accent` and `--accent-ink`; everything else follows.

**Type** — `--serif` sets note body text and headings, `--sans` the interface, `--mono` code. Bundled fonts load from `fonts/`, with system fallbacks if they're blocked.

**Reading measure** — `--read-w` (default `44rem`) is the base column width the width toggle multiplies.

## Publish it

The site is static, so anywhere works. Push the folder to a repo and turn on GitHub Pages, drag it into Netlify, or copy it to any web host. Keep the `content/` folder alongside `index.html` — the note text is embedded in the HTML, but the PDFs are fetched from disk.

## Layout

```
study-vault/
├── index.html          the whole site: markup, styles, app, and note data
├── build.py            reads content/notes/*.md → refreshes the data block
├── ARCHITECTURE.md     full technical breakdown of the app
├── content/
│   ├── vault.json      site name and intro line
│   ├── notes/          your Markdown files (one per note)
│   │   └── _template.md
│   └── pdf/            attachments (optional)
└── fonts/              bundled UI/reading fonts
```

## Credits

Original project and design by [@Sulcop5](https://github.com/Sulcop5) — [Sulcop5/Sulcop5.github.io](https://github.com/Sulcop5/Sulcop5.github.io). Site design mimics Claude's colour palette and Obsidian's interaction model. `ARCHITECTURE.md` is the original author's technical write-up, preserved here.
