// Service worker: makes the app installable, keeps the page shell available on a
// weak connection, and receives screenshots/text shared from WhatsApp (Android).
const SHELL = "satark-shell-v3";
const SHARE = "satark-share";
const FILES = ["/", "/index.html", "/styles.css", "/app.js", "/i18n.js", "/manifest.webmanifest", "/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== SHELL && k !== SHARE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;

  // Something was shared into the app: stash it, then open the page to check it.
  if (e.request.method === "POST" && url.pathname === "/share") {
    e.respondWith(handleShare(e.request));
    return;
  }
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return; // never cache API answers

  // Network first (so a new deploy shows up at once), cached shell as fallback.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)); }
        return res;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/index.html")))
  );
});

async function handleShare(request) {
  try {
    const form = await request.formData();
    const text = [form.get("title"), form.get("text"), form.get("url")].filter(Boolean).join("\n");
    const images = [];
    for (const f of form.getAll("images").slice(0, 3)) {
      if (f && f.type && f.type.startsWith("image/")) {
        images.push({ type: f.type, data: await toDataUrl(f) });
      }
    }
    const cache = await caches.open(SHARE);
    await cache.put("/shared-data", new Response(JSON.stringify({ text, images, at: Date.now() }), {
      headers: { "content-type": "application/json" },
    }));
  } catch (_) { /* fall through to the page */ }
  return Response.redirect("/?shared=1", 303);
}

async function toDataUrl(file) {
  const buf = new Uint8Array(await file.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return `data:${file.type};base64,${btoa(bin)}`;
}
