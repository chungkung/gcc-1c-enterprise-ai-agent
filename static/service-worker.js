// Basic Service Worker

// Install event - happens when the browser installs the service worker
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  // Optional: Pre-cache app shell assets here
  // event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache)));
  self.skipWaiting(); // Activate worker immediately
});

// Activate event - happens after installation
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  // Optional: Clean up old caches here
  event.waitUntil(clients.claim()); // Take control of pages immediately
});

// Fetch event - intercepts network requests
self.addEventListener('fetch', event => {
  // console.log('Service Worker: Fetching', event.request.url);
  // Basic strategy: Go to network first.
  // More advanced strategies (cache-first, offline fallback) can be added here.
  event.respondWith(fetch(event.request));
}); 