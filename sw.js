// Service Worker — Health Dashboard PWA
const CACHE = 'hd-v3'
const ASSETS = ['./', './index.html', './manifest.json']

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)))
  self.skipWaiting()
})

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ))
  self.clients.claim()
})

self.addEventListener('fetch', e => {
  // Network first สำหรับ API calls, Cache first สำหรับ assets
  const url = new URL(e.request.url)
  const isAPI = url.hostname.includes('ouraring') ||
                url.hostname.includes('googleapis') ||
                url.hostname.includes('anthropic') ||
                url.hostname.includes('workers.dev')

  if (isAPI) {
    e.respondWith(fetch(e.request).catch(() => new Response('{"error":"offline"}', {
      headers: { 'Content-Type': 'application/json' }
    })))
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request))
    )
  }
})
