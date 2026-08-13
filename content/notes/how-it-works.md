---
title: 这个笔记站是怎么工作的
folder: 00 Maps
tags: [tutorial, architecture]
created: 2026-08-13
updated: 2026-08-13
summary: "拆解这个零依赖单文件笔记站的原理：数据流、路由、Markdown 引擎、链接图谱。"
---

> [!note] 这是「元笔记」
> 用这个笔记站，讲解这个笔记站自己。文中的所有语法（`[[链接]]`、标注框、代码块、表格）本身就是对原理的演示。

## 一句话总结

**Markdown 文件当数据库，Python 脚本当编译器，浏览器里的原生 JS 当运行时。** 没有框架、没有构建工具、没有服务端——一个 `index.html` 就是整个应用。

## 三个「零」的设计哲学

| 零 | 含义 | 代价 |
| --- | --- | --- |
| 零依赖 | 不引 React/Vue/webpack，纯手写 JS | 功能要自己造轮子 |
| 零构建 | 没有 npm/CI，`build.py` 一步完成 | 大型站点会慢 |
| 零服务端 | 纯静态，扔到任何主机都能跑 | 没有数据库、用户系统 |

## 数据流：从 .md 到网页

整个过程只有两步：

```text
content/notes/*.md          content/vault.json
        │                          │
        ▼                          ▼
    解析 frontmatter           { name, tagline }
        │                          │
        └──────────┬───────────────┘
                   ▼
              build.py
                   │  把结果写成 window.VAULT = {...}
                   ▼
     index.html 里 VAULT:START 和 VAULT:END 两个标记之间
```

核心约定：**文件名就是笔记的 ID**。`bayes-theorem.md` 会被别处用 `[[bayes-theorem]]` 引用，`_` 开头的文件（如 `_template.md`）不发布。

## 单文件里装了什么

`index.html` 四块内容，用内联 `<style>` 和 `<script>` 全塞在一个文件里：

- **CSS 设计系统** —— 所有颜色/字体/间距都是 `:root` 里的 CSS 变量，改 `--accent` 就能换主题色
- **HTML 布局** —— 左侧图标栏 + 文件浏览器 + 主视图 + 右侧大纲，CSS Grid 四列
- **内嵌 JSON** —— `window.VAULT`，就是 build.py 生成的全部笔记数据
- **JS 应用** —— 路由、Markdown 渲染、力导向图、命令面板

## 路由：hash 就是 URL

没有服务器，所以用 URL 里 `#` 后面的部分（hash）当路由，监听 `hashchange` 事件：

| hash | 视图 |
| --- | --- |
| `#/` | 首页仪表盘 |
| `#/n/how-it-works` | 本篇笔记 |
| `#/tag/tutorial` | 标签过滤页 |

所以这个站刷新、分享链接都不会丢状态——因为「页面状态」全在 URL 的 hash 里。

## Markdown 引擎：占位符技巧

自己写的解析器约 200 行，核心是一个「先藏起来，再还原」的技巧：

```text
原文      `content/notes/`
  │  第一步：把行内代码替换成占位符（防止后续处理破坏它）
  ▼
占位符    U+E000 · C · 0 · U+E000
  │  中间：正常处理加粗、链接、标签等
  ▼
  │  第二步：把占位符还原成 <code>content/notes/</code>
  ▼
结果      <code>content/notes/</code>
```

> [!warning] 这里刚修过一个 bug
> 代码占位符的结尾分隔符原本写成了 U+0000（空字符），但还原时去找的是 U+E000，对不上，导致占位符漏到页面（显示成「□C0」）。数学公式的占位符就是对的，只有行内代码写错了。

## 链接图谱：链接才是目录

笔记之间用 `[[wikilink]]` 关联。**链接是双向的**：当 [[getting-started]] 链接到 [[markdown-guide]]，后者的「引用自」列表和首页图谱里会自动多一条边——不需要手动维护索引。

图谱本身是 Canvas 2D 画的力导向图：

- **斥力** —— 节点两两排斥
- **引力** —— 拉向画布中心
- **弹簧力** —— 有边相连的节点被拉向目标距离
- **阻尼** —— 每帧速度衰减

跑约 420 帧后自动休眠省电，拖拽或 hover 时才唤醒。

## 你能改什么

- 站点名/介绍 → 编辑 `content/vault.json`
- 配色 → 改 `index.html` 顶部 `:root` 里的 `--accent`
- 加笔记 → 往 `content/notes/` 扔一个 `.md`，跑 `python3 build.py`

想继续探索，看 [[welcome]]、[[getting-started]]、[[markdown-guide]]；想看更深的原理拆解，读 [[deep-dive|工作原理详解]]。

#tutorial #architecture
