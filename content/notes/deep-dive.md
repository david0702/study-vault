---
title: 工作原理详解
folder: 00 Maps
tags: [tutorial, architecture]
created: 2026-08-13
updated: 2026-08-13
summary: "深入拆解完整工作链路：构建流水线、数据模型、路由、Markdown 引擎、力导向图。"
---

> [!note] 阅读建议
> 这是 [[how-it-works|工作原理概述]] 的深度版。先读那篇建立框架，再回来看这篇的细节。文中代码都摘自真实的 `index.html` 和 `build.py`。

## 一句话本质

**Markdown 文件当数据库，Python 脚本当编译器，浏览器里的原生 JS 当运行时。** 关键判断：这不是「渲染 Markdown 的网站」，而是「把 Markdown 编译进 HTML 的编译器 + 一个读取内嵌数据的 SPA」。

## 整体架构

```text
content/notes/*.md  ──┐
content/vault.json  ──┤
                      ├──► build.py ──► index.html（单文件，四合一）
                      │
（用户写 Markdown）    （Python 编译）   （浏览器运行）
```

`index.html` 内部四合一：

- `<style>` —— CSS 设计系统（CSS 变量管理主题）
- `<body>` —— HTML 骨架（四列 Grid 布局）
- `window.VAULT` —— 内嵌 JSON 数据（build.py 生成）
- `<script>` —— JS 应用（路由 + 渲染 + 图谱 + 交互）

**为什么单文件能成立**：数据在编译期就烧进了 HTML，浏览器打开时不用再发请求取笔记。所以双击就能跑、离线可用、托管零成本。

## 构建流水线（build.py）

`build.py` 只干三件事：`collect()` → `write()` →（可选）`serve()`。

### 收集：collect()

```python
for path in sorted(NOTES_DIR.glob("*.md")):
    if path.name.startswith("_"):
        continue              # _template.md、_draft-* 不发布
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    slug = path.stem          # 文件名就是 ID
```

**核心约定**：`slug` = 文件名去掉 `.md`。`bayes-theorem.md` 就是全站用 `[[bayes-theorem]]` 引用它的键。

### 解析 frontmatter

```python
try:
    import yaml
    meta = yaml.safe_load(raw) or {}
except Exception:
    meta = {}   # PyYAML 没装时的降级手写解析器
```

**渐进增强**：唯一的第三方依赖（PyYAML）也是可选的，没装就退回十几行手写解析器。

### 写入：write()

构建不是「生成新文件」，而是「在模板的固定插槽里替换数据」：`build.py` 定位到 `index.html` 里那段带 `id="vault-data"` 的 script 标签块，把里面的内容整体替换成新的 JSON。所以 `index.html` 既是源码又是产物，HTML/CSS/JS 永远不变，只有 JSON 数据在变。

> [!warning] 一个真实的脆弱点案例
> 早期版本用 `/*VAULT:START*/` 和 `/*VAULT:END*/` 两个注释做分隔符，靠 `split()` 定位。结果写这篇笔记时，正文里恰好出现了这两个字符串，`split()` 切错了位置，把 `window.VAULT` 写坏，整个站显示成「The vault is empty」。
>
> 教训：**「讲解代码机制的文档，其内容不能触发那个机制」**。后来把定位方式改成直接锚定 `id="vault-data"` 的 script 标签块，才彻底摆脱这个坑。

## 数据模型与索引

每条笔记的 JSON：

```json
{
  "slug": "deep-dive",
  "title": "工作原理详解",
  "folder": "00 Maps",
  "tags": ["tutorial", "architecture"],
  "summary": "一句话摘要",
  "body": "Markdown 正文原文（含 #tag 和 [[wikilink]]）"
}
```

注意 `body` 存的是**原始 Markdown**，渲染发生在浏览器运行时。

### 双向链接计算

每条笔记解析 `[[wikilink]]`，算出：

```text
n.out = 我链接出去的笔记
n.in  = 链接到我的笔记（自动算，不手写）
```

`in` 是「所有笔记 `out` 的逆」。这套数据同时喂给：反向链接计数、正文「引用自」列表、右侧「最多被引用」排名、首页力导向图。

## 路由系统

没有服务器，路由只能走 URL 的 hash 段：

| hash | 视图 |
| --- | --- |
| `#/` | 首页仪表盘 |
| `#/n/{slug}` | 笔记详情 |
| `#/tag/{name}` | 标签过滤页 |
| `#/n/{slug}?h={id}` | 笔记详情 + 定位到标题 |

```js
addEventListener("hashchange", route);

function route() {
  const h = location.hash || "#/";
  if (h.match(/^#\/n\/([^?]+)/))       renderNote(slug, frag);
  else if (h.match(/^#\/tag\/([^?]+)/)) renderTag(name);
  else                                  renderIndex();
}
```

**好处**：状态全在 URL，刷新不丢、链接可分享、前进后退可用。**代价**：hash 段被路由占用，和原生 `#锚点` 冲突——这就是本笔记标题锚点曾「点了跳首页」的原因（现已修复）。

## Markdown 渲染引擎（最核心）

约 200 行，纯手写零依赖。分两层：**块级解析** + **行内解析**。

### 块级：parse()

按行扫描，状态机识别块结构。标题会递归交给行内解析器：

```js
const h = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
const id = slugify(raw);
out.push(`<h${level} id="${id}">${inline(raw)}<a class="anchor" href="#${id}">#</a></h${level}>`);
```

### 行内：inline() 与「占位符技巧」

问题：`**加粗**` 的 `*` 不能和 `*斜体*` 混淆，`` `代码` `` 里的 `**` 不该被加粗。解法是**先藏起来再还原**：

```text
第 1 步：危险内容替换成占位符
  `code`       →  U+E000 C 0 U+E000    （codes[0] 存真实 HTML）
  $math$       →  U+E000 M 0 U+E000    （maths[0] 存）
  <font color> →  U+E000 H 0 U+E000    （htmlTags[0] 存）

第 2 步：放心处理剩余文字
  HTML 转义 → 图片 → 链接 → wikilink → 加粗/斜体/删除线/高亮 → #tag → 脚注

第 3 步：还原占位符
  U+E000 C 0 U+E000  →  <code>...</code>
```

占位符用 `U+E000`（Unicode 私用区字符），普通文本几乎不会出现，不会误伤。

> [!warning] 这里修过一个 bug
> 代码占位符的结尾分隔符原本写成了 `U+0000`（空字符），还原时找不到，漏到页面显示成「□C0」。数学公式的占位符就是对的，只有行内代码写错了。

### 渐进增强

- KaTeX 加载失败 → 公式退回原始 TeX，不报错
- JS 被禁用 → 数据仍内嵌，只是没交互
- 离线 → 系统字体兜底

## 链接图谱（Canvas 力导向图）

纯 Canvas 2D 手写物理模拟。节点 = 笔记，边 = wikilink。每帧四力叠加：

| 力 | 作用 |
| --- | --- |
| 斥力 | 节点两两排斥，防叠一起 |
| 引力 | 拉向画布中心，防散出画布 |
| 弹簧力 | 相连节点拉到目标距离 |
| 阻尼 | 每帧速度 ×0.84，让系统收敛 |

性能：跑约 420 帧后自动休眠，拖拽/hover 时唤醒，尊重 `prefers-reduced-motion`。

## 其他机制速览

- **命令面板（Ctrl+K）**：模糊搜索打分排序（标题前缀 100 分、正文包含 30 分…）
- **Peek 预览**：悬停 `[[wikilink]]` 340ms 弹浮动卡片
- **大纲 + Scrollspy**：右侧目录实时高亮 + 阅读进度条
- **持久化**：偏好存 localStorage（`sv:` 前缀），隐私模式静默降级

## 设计权衡

| 选择 | 换来 | 放弃 |
| --- | --- | --- |
| 单文件 + 内嵌数据 | 离线、双击即用 | 笔记多了文件变大 |
| 自研 200 行引擎 | 零依赖、可控 | 功能不如 CommonMark 全 |
| hash 路由 | 无需服务器 | 和原生锚点冲突 |
| 运行时算双向链接 | 无需维护索引 | 笔记极多时遍历成本上升 |

## 收尾

这个项目把「编译器」和「运行时」都压到极简：Python 只做一件事（Markdown → JSON 塞进插槽），JS 做剩下的一切，中间靠内嵌的 `window.VAULT` 连接。这就是「一个 HTML 文件 = 完整应用」的原因。

想从零上手，看 [[getting-started]]；想了解怎么改它，回到 [[how-it-works]]。

#tutorial #architecture
