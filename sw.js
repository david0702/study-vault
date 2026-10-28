/* 个人技术笔记 · Service Worker
 *
 * 目标：断网能读已访问过的笔记、弱网秒开；数据仍以网络为准（stale-while-revalidate）。
 * 只处理同源 GET；跨域请求、POST 一律放过。
 *
 * 更新方式：内容变化浏览器就会重装；VERSION 用于清理旧缓存。
 */
const VERSION = "v1";
const SHELL = ["/", "/index.html", "/favicon.svg?v=2", "/site.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then((c) => c.addAll(SHELL))
      .catch(() => {})
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

const DATA = [
  /\/vault-index\.json$/,
  /\/vault-notes\//,
  /\/search-index\.json$/,
  /\/feed\.xml$/,
  /\/sitemap\.xml$/,
];
const ASSETS = [
  /\/fonts\//,
  /\/vendor\//,
  /\/media\//,
  /\/favicon/,
  /\/site\.webmanifest$/,
];

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // 页面导航：网络优先；断网回退到缓存的壳
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() =>
        caches.match("/index.html").then((r) => r || caches.match("/")),
      ),
    );
    return;
  }

  // 静态资源：缓存优先（字体/图片/vendor 都是 immutable）
  if (ASSETS.some((re) => re.test(url.pathname))) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
            }
            return res;
          }),
      ),
    );
    return;
  }

  // 数据：先给缓存（有就秒开），同时后台更新
  if (DATA.some((re) => re.test(url.pathname))) {
    event.respondWith(
      caches.match(req).then((hit) => {
        const net = fetch(req)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
            }
            return res;
          })
          .catch(() => hit);
        return hit || net;
      }),
    );
  }
});
