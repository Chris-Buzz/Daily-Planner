// firebase.js - Secure Firebase Configuration
// Configuration is now loaded from server-side environment variables
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.3/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.12.3/firebase-auth.js";

let app, auth;

// Fetch Firebase configuration from secure API endpoint
async function initializeFirebase() {
  try {
    const response = await fetch('/api/firebase-config');
    
    if (!response.ok) {
      throw new Error('Failed to load Firebase configuration');
    }
    
    const firebaseConfig = await response.json();
    
    if (firebaseConfig.error) {
      throw new Error(firebaseConfig.error);
    }
    
    // Initialize Firebase with configuration from server
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    
    console.log('✅ Firebase initialized successfully');
    return { app, auth };
  } catch (error) {
    console.error('❌ Firebase initialization failed:', error);
    throw error;
  }
}

// Initialize Firebase immediately
await initializeFirebase();

export { auth };
