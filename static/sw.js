/**
 * Service Worker for Push Notifications
 * 
 * This service worker handles:
 * - Push notification events from the server
 * - Notification click events
 * - Background sync for offline support
 */

// Service worker version for cache management
const CACHE_VERSION = 'v1';
const CACHE_NAME = `planner-cache-${CACHE_VERSION}`;

// Install event - cache essential files
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching essential files');
      return cache.addAll([
        '/',
        '/static/styles.css',
        '/static/script.js',
        '/static/manifest.json'
      ]).catch(err => {
        console.warn('[Service Worker] Cache failed for some files:', err);
      });
    })
  );
  
  // Activate immediately
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== CACHE_NAME)
          .map((cacheName) => {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          })
      );
    })
  );
  
  // Take control of all clients immediately
  return self.clients.claim();
});

// Push event - handle incoming push notifications
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received');
  
  let notificationData = {
    title: 'Daily Planner',
    body: 'You have a new notification',
    icon: '/static/PlannerIcon.png',
    badge: '/static/PlannerIcon2.png',
    tag: 'default',
    requireInteraction: false,
    data: {
      url: '/'
    }
  };
  
  // Parse the push notification data
  if (event.data) {
    try {
      const data = event.data.json();
      notificationData = {
        ...notificationData,
        ...data
      };
    } catch (e) {
      console.error('[Service Worker] Error parsing push data:', e);
      notificationData.body = event.data.text();
    }
  }
  
  console.log('[Service Worker] Showing notification:', notificationData.title);
  
  // Show the notification
  event.waitUntil(
    self.registration.showNotification(notificationData.title, {
      body: notificationData.body,
      icon: notificationData.icon,
      badge: notificationData.badge,
      tag: notificationData.tag,
      requireInteraction: notificationData.requireInteraction,
      data: notificationData.data,
      vibrate: [200, 100, 200], // Vibration pattern for mobile
      actions: [
        {
          action: 'open',
          title: 'Open App',
          icon: '/static/PlannerIcon.png'
        },
        {
          action: 'dismiss',
          title: 'Dismiss',
          icon: '/static/PlannerIcon2.png'
        }
      ]
    })
  );
});

// Notification click event - handle user interaction
self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notification clicked:', event.action);
  
  event.notification.close();
  
  // Don't open app if user clicked dismiss
  if (event.action === 'dismiss') {
    return;
  }
  
  // Get the URL to open from notification data
  const urlToOpen = event.notification.data?.url || '/';
  
  // Open the app or focus existing window
  event.waitUntil(
    clients.matchAll({
      type: 'window',
      includeUncontrolled: true
    }).then((clientList) => {
      // Check if there's already a window open
      for (const client of clientList) {
        if (client.url.includes(self.registration.scope) && 'focus' in client) {
          console.log('[Service Worker] Focusing existing window');
          return client.focus().then(client => {
            // Navigate to the notification URL
            if (client.navigate) {
              return client.navigate(urlToOpen);
            }
            return client;
          });
        }
      }
      
      // No window open, open a new one
      if (clients.openWindow) {
        console.log('[Service Worker] Opening new window');
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

// Fetch event - serve from cache when offline (optional)
self.addEventListener('fetch', (event) => {
  // Only cache GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then((response) => {
      // Return cached version if available, otherwise fetch from network
      return response || fetch(event.request).then((fetchResponse) => {
        // Don't cache API calls or POST requests
        if (event.request.url.includes('/api/')) {
          return fetchResponse;
        }
        
        // Cache the new response for future use
        return caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, fetchResponse.clone());
          return fetchResponse;
        });
      });
    }).catch(() => {
      // If both cache and network fail, show offline page
      console.log('[Service Worker] Network and cache failed');
      return new Response('Offline - Please check your connection', {
        status: 503,
        statusText: 'Service Unavailable'
      });
    })
  );
});

// Handle background sync (optional - for offline task creation)
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync:', event.tag);
  
  if (event.tag === 'sync-tasks') {
    event.waitUntil(
      // Implement sync logic here if needed
      Promise.resolve()
    );
  }
});

console.log('[Service Worker] Loaded and ready');
