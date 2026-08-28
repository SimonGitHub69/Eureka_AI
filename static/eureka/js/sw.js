/* Service worker Eureka: shell offline + fallback navigazione. */
const CACHE = "eureka-offline-v4";
const OFFLINE_URL = "/offline/";

const PRECACHE = [
    OFFLINE_URL,
    "/static/eureka/js/offline-db.js",
    "/static/eureka/js/offline-app.js",
    "/static/eureka/js/app.js",
    "/static/vendor/sqljs/sql-wasm.js",
    "/static/vendor/sqljs/sql-wasm.wasm",
    "/static/vendor/tabler/css/tabler.min.css",
    "/static/vendor/tabler-icons/tabler-icons.min.css",
    "/static/vendor/tabler/js/tabler.min.js",
    "/static/eureka/css/variables.css",
    "/static/eureka/css/sidebar.css",
    "/static/eureka/css/navbar.css",
    "/static/eureka/css/style.css",
    "/static/eureka/icons/icon-192.png",
    "/static/eureka/icons/icon-512.png",
    "/static/eureka/manifest.webmanifest",
];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE).then(function (cache) {
            return Promise.all(
                PRECACHE.map(function (url) {
                    return cache.add(new Request(url, { credentials: "same-origin" })).catch(
                        function () {
                            return undefined;
                        }
                    );
                })
            );
        }).then(function () {
            return self.skipWaiting();
        })
    );
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys
                    .filter(function (k) {
                        return k !== CACHE;
                    })
                    .map(function (k) {
                        return caches.delete(k);
                    })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

function isNavigationRequest(request) {
    return (
        request.mode === "navigate"
        || (request.method === "GET"
            && request.headers.get("accept")
            && request.headers.get("accept").indexOf("text/html") !== -1)
    );
}

self.addEventListener("fetch", function (event) {
    const req = event.request;
    if (req.method !== "GET") return;

    let url;
    try {
        url = new URL(req.url);
    } catch (e) {
        return;
    }
    if (url.origin !== self.location.origin) return;

    // Sync API: solo rete (fallisce offline → ok)
    if (url.pathname.indexOf("/api/offline/") === 0) {
        return;
    }

    const isStatic = url.pathname.indexOf("/static/") === 0;
    const isOfflinePage =
        url.pathname === "/offline/" || url.pathname.indexOf("/offline") === 0;

    // Navigazione: rete, se fallisce → pagina Dati offline in cache
    if (isNavigationRequest(req)) {
        event.respondWith(
            fetch(req)
                .then(function (res) {
                    if (res && res.ok && isOfflinePage) {
                        const copy = res.clone();
                        caches.open(CACHE).then(function (cache) {
                            cache.put(OFFLINE_URL, copy);
                        });
                    }
                    return res;
                })
                .catch(function () {
                    return caches.match(OFFLINE_URL).then(function (cached) {
                        return (
                            cached
                            || new Response(
                                "<!doctype html><meta charset=utf-8>"
                                + "<title>Offline</title>"
                                + "<body style='font-family:sans-serif;padding:2rem'>"
                                + "<h1>Sei offline</h1>"
                                + "<p>Apri Eureka con Wi‑Fi, vai su <strong>Dati offline</strong> "
                                + "e tocca Scarica dati. Poi riprova senza rete.</p>"
                                + "</body>",
                                { headers: { "Content-Type": "text/html; charset=utf-8" } }
                            )
                        );
                    });
                })
        );
        return;
    }

    // Static / offline assets: cache-first
    if (!isStatic && !isOfflinePage) {
        return;
    }

    event.respondWith(
        caches.match(req).then(function (cached) {
            const network = fetch(req)
                .then(function (res) {
                    if (res && res.ok) {
                        const copy = res.clone();
                        caches.open(CACHE).then(function (cache) {
                            cache.put(req, copy);
                        });
                    }
                    return res;
                })
                .catch(function () {
                    return cached || Response.error();
                });
            return cached || network;
        })
    );
});
