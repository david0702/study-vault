---
title: Getting started
folder: 00 Maps
tags: [tutorial]
created: 2026-08-13
updated: 2026-08-13
summary: "How to add, edit, and organise notes in this vault."
---

Everything you write lives in `content/notes/`. The **filename is the note's ID**.

## Add a note

1. Drop a Markdown file into `content/notes/`.
2. Give it frontmatter:

```yaml
---
title: "Your note title"
folder: 01 Mathematics
tags: [calculus]
summary: "One sentence used on cards and hover previews."
---
```

3. Run `python3 build.py`.

Only `title` really matters; the rest have sensible defaults.

## Link notes together

Use `[[note-id]]` to link to another note. Links are **two-way**: when this note links to [[markdown-guide]], that note automatically grows a *Linked from* entry and a node in the graph.

## See the result

The graph on the home page draws a node per note and an edge per link. Try `Ctrl+K` to open the quick switcher.

#tutorial
