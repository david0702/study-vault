---
title: Markdown guide
folder: 00 Maps
tags: [tutorial, markdown]
created: 2026-08-13
updated: 2026-08-13
summary: "Every Markdown feature this site supports, in one note."
---

A single note demonstrating everything the renderer supports.

## Text

**bold**, *italic*, ~~strikethrough~~, ==highlight==, and `inline code`.

## Links

- Internal: [[getting-started|Getting started]]
- Internal to a heading: [[getting-started#Add a note]]
- External: [GitHub](https://github.com)

## Callouts

> [!note] Note
> Plain note callout.

> [!tip] Tip
> A helpful hint.

> [!warning] Warning
> Watch out for this.

> [!info] Info
> Additional context.

## Tasks

- [x] Done
- [ ] Not done yet

## Code

```python
def greet(name):
    return f"Hello, {name}"
```

## Math

Inline: $e^{i\pi} + 1 = 0$

Display:

$$
\int_{-\infty}^{\infty} e^{-x^2} \, dx = \sqrt{\pi}
$$

## Table

| Syntax | Result |
| --- | --- |
| `[[slug]]` | Internal link |

---

That's everything.

#tutorial #markdown
