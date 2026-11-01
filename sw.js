// 쭈갑 물때 오프라인 지원: 앱 화면은 인터넷이 되면 새로 받고, 안 되면 저장해 둔 것으로 연다
const CACHE = 'jjugap-eb86c689';
const CORE = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './icon-180.png', './sc-save.png', './sc-map.png', './badge-96.png', './data/basemap.json', './data/spots.json', './data/ports.json'];
const FIXED = ['/data/basemap.json', '/data/spots.json', '/data/ports.json', '/data/coast.json'];   // 앱과 함께 바뀌는 고정 자료 (바다 지도, 이 자리 계산 자료)
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE && k.startsWith('jjugap-')).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// 알림줄 바로가기를 누르면: 열려 있는 앱 화면으로 가서 지도(또는 포인트 저장)를, 없으면 새로 연다
self.addEventListener('notificationclick', e => {
  const act = e.action || (e.notification.data && e.notification.data.act) || 'map'; e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
    const c = cs.find(x => x.url.startsWith(self.registration.scope));
    if (c) { c.postMessage({ jjugap: act }); return c.focus(); }
    return self.clients.openWindow('./?act=' + act);
  }));
});
self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const fixed = url.origin === location.origin && FIXED.find(f => url.pathname.endsWith(f));
  if (fixed) {
    // 해안선·이 자리 계산 자료는 앱을 새로 받을 때만 바뀌니 저장해 둔 것을 먼저 (바다 위에서 인터넷이 없어도 보이게)
    const key = '.' + fixed;
    e.respondWith(caches.match(key).then(hit => hit || fetch(req).then(r => { if (r.ok) { const cp = r.clone(); caches.open(CACHE).then(c => c.put(key, cp)); } return r; })));
    return;
  }
  if (url.origin === location.origin && url.pathname.includes('/data/')) {
    // 바다 날씨 자료는 늘 새로 받고, 인터넷이 안 되거나 6초 넘게 걸리면(바다 위 약한 신호) 저장해 둔 것으로
    const net = fetch(req).then(r => { if (r.ok) { const cp = r.clone(); caches.open(CACHE).then(c => c.put(url.pathname, cp)); } return r; });
    e.respondWith(new Promise(res => {
      let done = false; const fin = r => { if (!done && r) { done = true; res(r); } };
      const t = setTimeout(() => caches.match(url.pathname).then(fin), 6000);
      net.then(r => { clearTimeout(t); fin(r); }).catch(() => { clearTimeout(t); caches.match(url.pathname).then(hit => { if (hit) fin(hit); else if (!done) { done = true; res(Response.error()); } }); });
    }));
    return;
  }
  if (req.mode === 'navigate') {
    // 브라우저가 묵혀 둔 옛 화면(최대 10분)을 쓰지 않도록 늘 서버에 새것인지 물어본다
    e.respondWith(fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' }).then(r => (r.redirected ? fetch(req) : r))
      .then(r => { if (r.ok) { const cp = r.clone(); caches.open(CACHE).then(c => c.put('./index.html', cp)); } return r; })
      .catch(() => caches.match('./index.html')));
    return;
  }
  if (url.origin === location.origin || url.host.endsWith('fonts.googleapis.com') || url.host.endsWith('fonts.gstatic.com')) {
    e.respondWith(caches.match(req).then(hit => {
      const net = fetch(req).then(r => { if (r.ok || r.type === 'opaque') { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); } return r; }).catch(() => hit);
      return hit || net;
    }));
  }
});
