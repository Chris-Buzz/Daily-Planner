/**
 * Push Notifications Module
 * 
 * Handles browser push notifications using Web Push API
 * Works with service worker (sw.js) for background notifications
 */

const PushNotifications = {
  // State
  subscription: null,
  vapidPublicKey: null,
  isSupported: false,
  isSubscribed: false,

  /**
   * Initialize push notifications
   */
  async init() {
    console.log('🔔 Initializing push notifications...');
    
    // Check if service workers and push are supported
    this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
    
    if (!this.isSupported) {
      console.warn('⚠️ Push notifications not supported in this browser');
      return false;
    }
    
    try {
      // Register service worker
      const registration = await this.registerServiceWorker();
      
      if (!registration) {
        console.error('❌ Failed to register service worker');
        return false;
      }
      
      // Get VAPID public key from server
      await this.getVapidPublicKey();
      
      if (!this.vapidPublicKey) {
        console.error('❌ Failed to get VAPID public key');
        return false;
      }
      
      // Check if already subscribed
      this.subscription = await registration.pushManager.getSubscription();
      this.isSubscribed = this.subscription !== null;
      
      console.log(`✅ Push notifications initialized (subscribed: ${this.isSubscribed})`);
      return true;
      
    } catch (error) {
      console.error('❌ Error initializing push notifications:', error);
      return false;
    }
  },

  /**
   * Register service worker
   */
  async registerServiceWorker() {
    try {
      const registration = await navigator.serviceWorker.register('/static/sw.js', {
        scope: '/'
      });
      
      console.log('✅ Service worker registered:', registration.scope);
      
      // Wait for service worker to be ready
      await navigator.serviceWorker.ready;
      
      return registration;
      
    } catch (error) {
      console.error('❌ Service worker registration failed:', error);
      return null;
    }
  },

  /**
   * Get VAPID public key from server
   */
  async getVapidPublicKey() {
    try {
      const response = await fetch('/api/vapid-public-key');
      
      if (!response.ok) {
        throw new Error('Failed to get VAPID public key');
      }
      
      const data = await response.json();
      this.vapidPublicKey = data.publicKey;
      
      console.log('✅ VAPID public key retrieved');
      return this.vapidPublicKey;
      
    } catch (error) {
      console.error('❌ Error getting VAPID public key:', error);
      return null;
    }
  },

  /**
   * Request notification permission and subscribe
   */
  async subscribe() {
    if (!this.isSupported) {
      console.warn('⚠️ Push notifications not supported');
      return false;
    }
    
    try {
      // Request permission
      const permission = await Notification.requestPermission();
      
      if (permission !== 'granted') {
        console.log('🚫 Notification permission denied');
        return false;
      }
      
      console.log('✅ Notification permission granted');
      
      // Get service worker registration
      const registration = await navigator.serviceWorker.ready;
      
      if (!this.vapidPublicKey) {
        await this.getVapidPublicKey();
      }
      
      if (!this.vapidPublicKey) {
        console.error('❌ No VAPID public key available');
        return false;
      }
      
      // Convert VAPID key to Uint8Array
      const applicationServerKey = this.urlBase64ToUint8Array(this.vapidPublicKey);
      
      // Subscribe to push notifications
      this.subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
      });
      
      console.log('✅ Subscribed to push notifications');
      
      // Send subscription to server
      const success = await this.sendSubscriptionToServer(this.subscription);
      
      if (success) {
        this.isSubscribed = true;
        console.log('✅ Subscription saved to server');
        return true;
      } else {
        console.error('❌ Failed to save subscription to server');
        return false;
      }
      
    } catch (error) {
      console.error('❌ Error subscribing to push notifications:', error);
      return false;
    }
  },

  /**
   * Unsubscribe from push notifications
   */
  async unsubscribe() {
    if (!this.subscription) {
      console.log('ℹ️ Not subscribed to push notifications');
      return true;
    }
    
    try {
      // Unsubscribe from push manager
      await this.subscription.unsubscribe();
      
      // Remove subscription from server
      await this.removeSubscriptionFromServer();
      
      this.subscription = null;
      this.isSubscribed = false;
      
      console.log('✅ Unsubscribed from push notifications');
      return true;
      
    } catch (error) {
      console.error('❌ Error unsubscribing:', error);
      return false;
    }
  },

  /**
   * Send subscription to server
   */
  async sendSubscriptionToServer(subscription) {
    try {
      const response = await fetch('/api/push-subscription', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          subscription: subscription.toJSON()
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to save subscription');
      }
      
      return true;
      
    } catch (error) {
      console.error('❌ Error sending subscription to server:', error);
      return false;
    }
  },

  /**
   * Remove subscription from server
   */
  async removeSubscriptionFromServer() {
    try {
      const response = await fetch('/api/push-subscription', {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        throw new Error('Failed to remove subscription');
      }
      
      return true;
      
    } catch (error) {
      console.error('❌ Error removing subscription from server:', error);
      return false;
    }
  },

  /**
   * Convert base64 URL to Uint8Array (for VAPID key)
   */
  urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/\-/g, '+')
      .replace(/_/g, '/');
    
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    
    return outputArray;
  },

  /**
   * Check if push notifications are enabled for this method
   */
  isPushEnabled(notificationMethods) {
    if (Array.isArray(notificationMethods)) {
      return notificationMethods.includes('push');
    }
    return notificationMethods === 'push';
  }
};

// Export for use in main script
window.PushNotifications = PushNotifications;
