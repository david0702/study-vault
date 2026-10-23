# Study Vault 网站架构分析

> 这是 Claude 为我生成的单文件学习笔记网站，设计语言模仿 Claude 的配色 + Obsidian 的交互模式。

## 整体概览

这是一个**零依赖的单文件 SPA**（Single Page Application）。一个 `index.html` 包含了全部 CSS、HTML、嵌入式 JSON 数据和 JavaScript 应用逻辑。没有 React/Vue/框架，没有构建工具，打开即用。

核心设计理念：**笔记之间通过链接关联，而非文件夹分类。链接图谱才是真正的目录。**

```
index.html (1668 行)
├── <style>       CSS 设计系统 (~470 行)
├── <body>        HTML 布局 (~160 行)
│   ├── .ribbon   左侧图标栏
│   ├── .side-l   文件浏览器
│   ├── .main     主视图区域
│   └── .side-r   右侧大纲面板
├── <script id="vault-data">
│   └── window.VAULT  嵌入式 JSON 数据 (~380 行)
└── <script>      JavaScript 应用 (~680 行)
    ├── MD           Markdown → HTML 渲染引擎
    ├── 数据层        数据索引 + 链接图谱计算
    ├── 视图层        Index / Note / Tag 三种视图
    ├── 文件浏览器     可折叠树 + 过滤器
    ├── 快捷切换器     Command Palette (Ctrl+K)
    ├── 链接图谱       Canvas 力导向图
    ├── Peek 预览     悬停预览 wikilink
    ├── 大纲/Scrollspy 右侧边栏目录 + 阅读进度
    └── 持久化         localStorage 保存用户偏好
```

---

## 一、CSS 设计系统

### 1.1 设计令牌 (CSS Custom Properties)

所有颜色、间距、字体、阴影通过 `:root` 中的 CSS 变量集中管理，支持亮色/暗色一键切换。

```css
:root {
  --bg: #F0EEE6;         /* 底色 — 温暖米白 */
  --surface: #F5F3EC;    /* 侧边栏底色 */
  --card: #FBFAF7;       /* 卡片底色 */
  --ink: #141413;        /* 正文色 */
  --accent: #D97757;     /* 强调色 — 暖陶土橙 */
  --sans: "Inter";       /* UI 字体 */
  --serif: "Source Serif 4"; /* 阅读字体 */
  --mono: "JetBrains Mono";  /* 代码字体 */
}

[data-theme="dark"] {
  --bg: #1A1917;
  --accent: #E08A6B;
  /* ...全部覆盖... */
}
```

通过切换 `<html data-theme="dark">` 属性完成亮暗切换，无需额外 CSS。

### 1.2 布局系统

```
┌──────┬──────────┬───────────────────┬──────────┐
│      │          │                   │          │
│Ribbon│  左侧栏   │      主视图        │  右侧栏   │
│52px  │  266px   │     flex:1        │  250px   │
│      │          │                   │          │
└──────┴──────────┴───────────────────┴──────────┘
```

使用 CSS Grid 四列布局：
```css
.app {
  display: grid;
  grid-template-columns: 52px 266px 1fr 250px;
  height: 100dvh;
}
```

左右侧栏可通过 `body[data-left="off"]` / `body[data-right="off"]` 隐藏，列宽变为 0。小屏幕下左侧栏变为浮层抽屉。

### 1.3 响应式三级断点

| 宽度 | 行为 |
|------|------|
| > 1180px | 完整四列 |
| 860-1180px | 隐藏右侧栏 |
| 520-860px | 左侧栏变成浮层抽屉 |
| < 520px | 卡片单列、PDF 面板换行 |

### 1.4 阅读宽度

通过左上角按钮切换三种模式：
```css
body[data-width="normal"] { --read-w: 44rem; }
body[data-width="wide"]   { --read-w: 56rem; }
body[data-width="full"]   { --read-w: 100%; }
```

### 1.5 动画系统

全局使用 cubic-bezier 缓动，首页元素带入场动画：
```css
.rise  { animation: rise .42s cubic-bezier(.2,.8,.3,1) both; }
.d1 { animation-delay: .04s; }  /* 错开入场 */
.d2 { animation-delay: .09s; }
.d3 { animation-delay: .14s; }
```

---

## 二、HTML 布局结构

### Ribbon（左侧图标栏）

| 按钮 | 功能 | 快捷键 |
|------|------|--------|
| S 标 | 回到首页 | — |
| 📂 | 切换文件浏览器 | — |
| 🔍 | 打开快捷搜索 | Ctrl+K |
| 🔗 | 跳转到链接图谱 | — |
| 📏 | 切换阅读宽度（普通→宽→全宽） | — |
| ☀️ | 切换亮色/暗色 | — |

### 文件浏览器

- 按文件夹分组，每个文件夹可折叠
- 顶部搜索框支持实时筛选（匹配标题/slug/标签）
- 当前打开的笔记高亮显示
- 折叠状态持久化到 localStorage

### 主视图

- 顶栏：返回按钮 + 面包屑导航 + 快捷搜索入口（显示快捷键提示）
- 内容区：根据当前路由渲染 Index / Note / Tag 三种视图
- 阅读宽度由 `--read-w` 变量控制

### 右侧栏

动态切换内容：
- **首页模式**：科目统计、最多被引用、下载列表
- **笔记模式**：本页目录 + 笔记信息（阅读进度条、字数、反向链接、外链、标签）

---

## 三、数据架构

### 3.1 笔记数据结构

数据通过 `<script id="vault-data">` 嵌入，由 `build.py` 在两个标记 `/*VAULT:START*/` / `/*VAULT:END*/` 之间生成：

```json
{
  "name": "笔记库名称",
  "tagline": "一句话描述",
  "notes": [
    {
      "slug": "gradient-descent",
      "title": "笔记标题",
      "folder": "03 Machine Learning",
      "tags": ["deep-learning", "calculus"],
      "created": "2026-05-28",
      "updated": "2026-07-06",
      "pdf": "content/pdf/xxx.pdf",
      "summary": "一句话摘要，用于卡片和悬停预览",
      "body": "Markdown 正文 #tag\n\n## 标题\n...\n"
    }
  ]
}
```

### 3.2 数据索引

启动时从 `window.VAULT` 构建高效索引：

| 索引 | 类型 | 用途 |
|------|------|------|
| `bySlug` | `Map<slug, note>` | URL 路由查找 O(1) |
| `byTitle` | `Map<小写标题, note>` | wikilink 解析 O(1) |
| `resolve(key)` | 函数 | 先查 slug → 再查标题 → 最后模糊匹配 |

### 3.3 链接图谱

每条笔记解析 `[[wikilink]]` 语法，计算**出链**（out）和**入链**（in）：

```javascript
// 出链：body 中所有 [[xxx]] 的集合
n.out = new Set(["transformers-attention", "spaced-repetition"])

// 入链：所有笔记中指向本条笔记的链接
n.in  = new Set(["gradient-descent", "vault-home"])
```

这些数据同时用于：
- 卡片上的反向链接计数
- 笔记底部的"引用自"列表
- Canvas 力导向图的节点和边
- 右侧栏"最多被引用"排名

---

## 四、Markdown 渲染引擎

自研的纯函数 Markdown → HTML 解析器，约 200 行，零依赖。按行解析，状态机驱动。

### 4.1 支持的语法

| 语法 | 渲染 |
|------|------|
| `# ## ### ####` | 标题 + 自动 ID + hover 锚点链接 |
| `**粗体** *斜体* ~~删除线~~ ==高亮==` | 内联格式 |
| `` `code` `` | 行内代码 |
| ` ```lang\n...\n``` ` | 围栏代码块 + 语言标签 + 复制按钮 |
| `- [x] 已完成` / `- [ ] 未完成` | 任务列表（checkbox） |
| `> 引用` | 块引用 |
| `> [!note/tip/warning/info] 标题` | Callout 标注框（Obsidian 语法） |
| `| 表格 |` | GFM 表格 |
| `[[slug]]` / `[[slug\|标签]]` / `[[slug#标题]]` | Wikilink（有效蓝色、死链灰色虚线） |
| `#tag` | 内联标签（可点击跳转） |
| `[文本](url)` | 外部链接 |
| `![alt](url)` | 图片 |
| `$...$` / `$$...$$` | LaTeX 数学公式（可选 KaTeX 渲染） |
| `---` | 分隔线 |

### 4.2 特殊细节

- **死链处理**：指向不存在笔记的 `[[wikilink]]` 显示为灰色虚线，title 提示"No note named xxx yet"
- **代码复制**：hover 代码块时出现 Copy 按钮，用 `navigator.clipboard` API
- **Callout 图标**：四种类型（note/tip/warning/info）各有独立 SVG 图标和左边框颜色
- **KaTeX 降级**：KaTeX CDN 加载失败时，公式以原始 TeX 源码显示

---

## 五、路由系统

基于 `hashchange` 事件的简单路由：

| Hash | 视图 | 渲染函数 |
|------|------|----------|
| `#/` 或无 hash | 首页仪表盘 | `renderIndex()` |
| `#/n/slug` | 笔记详情 | `renderNote(slug, ?h=heading)` |
| `#/tag/name` | 标签过滤页 | `renderTag(name)` |
| 不存在的笔记 | 404 页面 | `renderMissing(slug)` |

关键代码：
```javascript
function route() {
  const h = location.hash || "#/";
  if (h.match(/^#\/n\/([^?]+)/)) renderNote(...);
  else if (h.match(/^#\/tag\/([^?]+)/)) renderTag(...);
  else renderIndex();
}
addEventListener("hashchange", route);
```

搭配 `?h=heading-slug` 查询参数实现锚点跳转（如 `#/n/gradient-descent?h=峡谷问题`）。

---

## 六、三种视图详解

### 6.1 首页仪表盘（`renderIndex`）

```
┌─────────────────────────────────────────┐
│  [●] 8 篇笔记 · 最后编辑于 2026-07-22    │  ← eyebrow
│  Study Vault                            │  ← h1
│  tagline 描述文字...                      │  ← p
│  8 Notes  5 Subjects  28 Links ...       │  ← stats
├─────────────────────────────────────────┤
│  按标签筛选                               │
│  [全部笔记] [#deep-learning] [#calculus]  │  ← chips
├─────────────────────────────────────────┤
│  全部笔记                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 笔记卡片1  │ │ 笔记卡片2  │ │ 笔记卡片3  │  │  ← cards grid
│  │ 摘要...   │ │ 摘要...   │ │ 摘要...   │  │
│  └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────┤
│  链接图谱                                 │
│  ┌───────────────────────────────────┐  │
│  │   Canvas 力导向图                  │  │
│  │   ● 高关联节点  ○ 普通节点         │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  最近编辑                                │
│  [笔记1] [笔记2] [笔记3] [笔记4]          │  ← backlinks
└─────────────────────────────────────────┘
```

**标签筛选**：点击标签 chip → `activeTag` 改变 → 卡片网格和"最近编辑"区域同时过滤。

**图表区域**：Canvas 元素，绘制节点（笔记）和边（wikilink）。高关联度节点用强调色填充。可拖拽节点、点击跳转。

### 6.2 笔记详情（`renderNote`）

```
┌─────────────────────────────────────────┐
│  folder / slug.md                        │  ← kicker
│  标题 (h1, serif)                        │
│  Updated · X min read · N words · out/in │  ← meta
│  [#tag1] [#tag2]                         │  ← tags
├─────────────────────────────────────────┤
│  [PDF 面板: 预览 | 下载]   (有 PDF 时)    │
├─────────────────────────────────────────┤
│  ## 渲染后的 Markdown 正文                │
│  ...                                     │
│  ...                                     │
├─────────────────────────────────────────┤
│  引用自 (N 篇笔记)                        │
│  [反向链接卡片1] [反向链接卡片2]           │  ← backlinks
├─────────────────────────────────────────┤
│  ← 较新  |  较旧 →                       │  ← pager
└─────────────────────────────────────────┘
```

**右侧栏**同步显示：
- 本页目录（可点击跳转，active 高亮）
- 阅读进度（百分比 + 进度条，scrollspy 实时更新）
- 笔记信息（创建时间、更新时间、字数、反向链接数）
- 外链列表（本笔记链接到哪些笔记）
- 标签列表

**PDF 面板**：预览按钮在 iframe 中加载 PDF，可切换显示/隐藏。

### 6.3 404 页面（`renderMissing`）

当 hash 中的 slug 在 `bySlug` 中找不到时显示，提示"找不到笔记"并引导返回首页。

---

## 七、链接图谱（Link Graph）

### 技术实现

纯 Canvas 2D，自研力导向布局：

```
节点 = 笔记（半径根据 in.size + out.size 动态计算）
边   = wikilink 关系
```

物理模拟：
1. **斥力**：所有节点对之间（O(n²)，但超出距离阈值后忽略）
2. **引力**：节点被拉向画布中心
3. **弹簧力**：有边相连的节点被拉向目标距离
4. **阻尼**：每帧速度衰减 0.84

高关联节点（deg ≥ 3）用强调色填充并显示标题文本。hover 节点时高亮相关边。

优化：
- 模拟运行约 420 帧后自动休眠（`requestAnimationFrame` 停止）
- 拖拽节点或 hover 时唤醒
- 配合 `prefers-reduced-motion` 媒体查询

---

## 八、快捷切换器（Command Palette）

按 `Ctrl+K`（Mac: `⌘K`）或 `/` 打开模态搜索面板。

```
┌──────────────────────────────────────┐
│  🔍 搜索标题、标签和笔记内容…         │
├──────────────────────────────────────┤
│  📄 笔记标题         科目 · #tag1 #tag2│
│  📄 笔记标题         科目 · #tag       │  ← 12 条结果
│  ...                                   │
├──────────────────────────────────────┤
│  ↑↓ 移动  ↵ 打开  Esc 关闭            │  ← 键盘提示
└──────────────────────────────────────┘
```

排序算法：
```
精确标题前缀匹配 → 100 分
标题包含 → 80 分
slug 包含 → 66 分
标签包含 → 54 分
正文包含 → 30 分
标题子序列匹配 → 20 分
```

结果上限 12 条，空输入显示最近编辑的前 8 条。

---

## 九、Peek 预览

hover `[[wikilink]]` 链接 340ms 后，在链接附近弹出浮动预览卡片：

```
┌─────────────────────────────┐
│  笔记标题                    │
│  一句话摘要...                │
│  folder · X min · N backlinks│
└─────────────────────────────┘
```

鼠标移出链接或主区域滚动时自动消失。移动端不显示。

---

## 十、持久化存储

所有用户偏好通过 `localStorage` 持久化，键名前缀 `sv:`：

| 键 | 值 | 默认 |
|----|----|------|
| `sv:theme` | `"light"` / `"dark"` | 跟随系统 |
| `sv:width` | `"normal"` / `"wide"` / `"full"` | `"normal"` |
| `sv:left` | `"on"` / `"off"` | `"on"` |
| `sv:right` | `"on"` / `"off"` | `"on"` |
| `sv:collapsed` | JSON 数组 `["folder1", ...]` | `[]` |

使用 try/catch 包裹，隐私模式下静默降级。

---

## 十一、构建流程

`build.py` 负责从 Markdown 源文件生成 `window.VAULT` 数据：

```
content/notes/*.md          content/vault.json
       │                          │
       ▼                          ▼
   YAML frontmatter 解析    { name, tagline }
       │                          │
       ▼                          ▼
  build.py ────────▶ 替换 index.html 中
                     /*VAULT:START*/ ... /*VAULT:END*/
                     之间的内容
```

Markdown 文件命名约定：
- 文件名 = slug（如 `gradient-descent.md` → `gradient-descent`）
- `_` 开头的文件被跳过（`_template.md`, `_draft-*.md`）
- `--serve` 参数可启动本地开发服务器

YAML frontmatter 字段：
```yaml
---
title:   笔记标题
folder:  01 Learning Systems
tags:    [method, memory]
created: 2026-02-11
updated: 2026-07-19
pdf:     content/pdf/spaced-repetition.pdf
summary: 一句话摘要
---
# 正文开始...
```

---

## 十二、设计亮点

1. **完全离线可用** — 无任何运行时外部依赖（KaTeX 可选），一个 HTML 文件拷到任何地方都能跑
2. **渐增强** — KaTeX 加载失败时原始 TeX 仍然可读，JS 被禁时数据仍然可查看
3. **零构建** — 不需要 npm/webpack/vite，不需要 CI/CD
4. **隐式数据索引** — wikilink 的关系在运行时自动计算，无需人工维护索引文件
5. **Claude 式配色** — 温暖米白底 + 陶土橙强调色，低对比度护眼
6. **Obsidian 式交互** — 链接图谱、Peek 预览、Command Palette、Callout 标注
7. **性能意识** — 力导图模拟自动休眠、事件被动监听、requestAnimationFrame 节流
8. **a11y 友好** — 完整的 aria-label、键盘导航、prefers-reduced-motion 尊重、focus-visible 样式
