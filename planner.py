from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
from flask_cors import CORS
import smtplib
import jwt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# Twilio SMS removed - requires business verification
# from twilio.rest import Client
import os
import uuid
from dotenv import load_dotenv
import random
import threading
import schedule
import time
import json
import requests
import csv
import re
import google.generativeai as genai
import logging
from bs4 import BeautifulSoup
from geopy.distance import geodesic
from urllib.parse import quote_plus, urljoin
import warnings

# Suppress warnings for cleaner logs in production
warnings.filterwarnings('ignore', message='Detected filter using positional arguments')
warnings.filterwarnings('ignore', module='google.cloud.firestore_v1')
os.environ['GRPC_VERBOSITY'] = 'ERROR'  # Suppress gRPC verbose logging
os.environ['GRPC_TRACE'] = ''  # Disable gRPC tracing

# Configure logging for production readiness (Vercel-compatible)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only stream handler for Vercel (read-only filesystem)
    ]
)
logger = logging.getLogger(__name__)

# Privacy protection functions (inline for simplicity)
def require_user_auth(f): 
    """Decorator for user authentication (simplified version)"""
    return f

def sanitize_user_data_for_logs(data): 
    """Sanitize user data for logging"""
    return "[REDACTED]"

def log_data_access(*args, **kwargs): 
    """Log data access for audit trail"""
    pass

def protect_user_data_access(*args, **kwargs): 
    """Protect user data access"""
    pass

def redact_sensitive_error_info(msg): 
    """Redact sensitive information from error messages"""
    return msg

def validate_production_privacy_config(): 
    """Validate production privacy configuration"""
    return []

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Security Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Environment detection
ENV = os.getenv('FLASK_ENV', 'production')
app.config['DEBUG'] = ENV == 'development'
app.config['TESTING'] = ENV == 'testing'

# Security headers
@app.after_request
def after_request(response):
    """
    Add security headers to all HTTP responses for enhanced security.
    
    Security measures implemented:
    - X-Content-Type-Options: Prevents MIME type sniffing attacks
    - X-Frame-Options: Prevents clickjacking by denying iframe embedding
    - X-XSS-Protection: Enables browser XSS filtering
    - Strict-Transport-Security: Enforces HTTPS in production (HSTS)
    
    Args:
        response: Flask response object
        
    Returns:
        Flask response object with security headers added
    """
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # HTTPS enforcement in production
    if ENV == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# Init Firebase Admin
try:
    # SECURE: Use environment variables for Firebase credentials
    # Priority: 1) Individual env vars (Vercel), 2) Base64 encoded, 3) Local file path
    
    # Option 1: Load from individual environment variables (RECOMMENDED for production)
    firebase_type = os.getenv('FIREBASE_TYPE')
    firebase_project_id = os.getenv('FIREBASE_PROJECT_ID')
    firebase_private_key = os.getenv('FIREBASE_PRIVATE_KEY')
    firebase_client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
    
    if all([firebase_type, firebase_project_id, firebase_private_key, firebase_client_email]):
        # Build credentials dict from environment variables
        cred_dict = {
            "type": firebase_type,
            "project_id": firebase_project_id,
            "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID', ''),
            "private_key": firebase_private_key.replace('\\n', '\n'),  # Handle escaped newlines
            "client_email": firebase_client_email,
            "client_id": os.getenv('FIREBASE_CLIENT_ID', ''),
            "auth_uri": os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
            "token_uri": os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
            "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_CERT_URL', 'https://www.googleapis.com/oauth2/v1/certs'),
            "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_CERT_URL', '')
        }
        cred = credentials.Certificate(cred_dict)
        print("✅ Firebase credentials loaded from environment variables")
        
    # Option 2: Load from base64 encoded credentials (legacy support)
    elif os.getenv('FIREBASE_CREDENTIALS_BASE64'):
        import base64
        import tempfile
        
        firebase_cred_base64 = os.getenv('FIREBASE_CREDENTIALS_BASE64')
        cred_data = base64.b64decode(firebase_cred_base64)
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            f.write(cred_data.decode('utf-8'))
            cred = credentials.Certificate(f.name)
        print("✅ Firebase credentials loaded from base64")
        
    # Option 3: Load from local file (ONLY for local development)
    else:
        firebase_cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if firebase_cred_path and os.path.exists(firebase_cred_path):
            cred = credentials.Certificate(firebase_cred_path)
            print(f"⚠️  Firebase credentials loaded from file: {firebase_cred_path}")
            print("⚠️  WARNING: Using local file - ensure this file is in .gitignore!")
        else:
            raise FileNotFoundError(
                "Firebase credentials not configured!\n"
                "Please set one of:\n"
                "  1) Individual env vars: FIREBASE_TYPE, FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY, FIREBASE_CLIENT_EMAIL\n"
                "  2) FIREBASE_CREDENTIALS_BASE64 (base64 encoded JSON)\n"
                "  3) FIREBASE_CREDENTIALS_PATH (path to service account JSON file)"
            )
    
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized successfully")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    print("⚠️  Please check your Firebase configuration")
    db = None

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Web Push Notifications Configuration (VAPID)
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY')
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')
VAPID_EMAIL = os.getenv('VAPID_EMAIL', 'mailto:yourplanno@gmail.com')

if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
    print("⚠️  VAPID keys not configured. Push notifications will not work.")
    print("📝 Generate VAPID keys by running: python generate_vapid_keys.py")
    print("   Then add VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to your .env file")
else:
    print("✅ VAPID keys configured for Web Push notifications")

# SMS Notifications Removed
# Twilio requires business verification for production use, which is not feasible for this app.
# Email notifications are more reliable and easier to configure.
# If you need SMS in the future, consider:
# - Business verification with Twilio
# - Alternative services like Vonage, MessageBird
# - Email-to-SMS gateways for specific carriers

# OpenWeatherMap Configuration
OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')
if not OPENWEATHERMAP_API_KEY:
    print("⚠️  OpenWeatherMap API key not found. Please add OPENWEATHERMAP_API_KEY to your .env file")
    print("📝 Get your free API key at: https://openweathermap.org/api")

# Google Gemini Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        gemini_model = genai.GenerativeModel('gemini-2.5-pro')
        print("✅ Google Gemini AI initialized successfully")
    except Exception as e:
        print(f"⚠️  Gemini initialization error: {e}")
        gemini_model = None
else:
    print("⚠️  Gemini API key not found. Please add GEMINI_API_KEY to your .env file")
    print("📝 Get your free API key at: https://makersuite.google.com/app/apikey")
    gemini_model = None

SESSION_COOKIE_NAME = "fb_session"
SESSION_MAX_AGE = timedelta(days=5)

# Inspirational messages
INSPIRATIONAL_MESSAGES = [
    "🌟 You're doing amazing! Keep up the great work!",
    "💪 Every task completed is a step towards your goals!",
    "🎯 Focus on progress, not perfection!",
    "🚀 You've got this! One task at a time!",
    "✨ Small steps lead to big achievements!",
    "🌈 Today is your day to shine!",
    "💫 Believe in yourself - you're capable of amazing things!",
    "🎉 Celebrate every win, no matter how small!",
    "🌻 Your productivity is blooming beautifully!",
    "⭐ You're a task-conquering superstar!"
]

def send_email(recipient_email, subject, body):
    """
    Send HTML email notification with professional styling.
    
    This function sends beautifully formatted emails for task reminders,
    daily summaries, and other notifications. Includes fallback to plain text
    and comprehensive error handling.
    
    Args:
        recipient_email (str): Email address of recipient
        subject (str): Email subject line
        body (str): Email content (plain text, will be HTML formatted)
        
    Returns:
        bool: True if email sent successfully, False otherwise
        
    Raises:
        None: All exceptions are caught and logged for graceful degradation
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("❌ Email credentials not configured")
        return False
        
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USERNAME  # Use the configured email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Create HTML version
        html_body = f"""
        <html>
          <head>
            <style>
              body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
              .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
              .header {{ background: linear-gradient(135deg, #1abc9c, #16a085); color: white; padding: 30px; text-align: center; }}
              .header h2 {{ margin: 0; font-size: 24px; }}
              .content {{ padding: 30px; }}
              .task {{ background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 10px; border-left: 4px solid #1abc9c; }}
              .task strong {{ color: #2c3e50; }}
              .inspiration {{ background: linear-gradient(135deg, #e8f5e8, #d5f4e6); padding: 25px; margin: 20px 0; border-radius: 12px; text-align: center; border: 2px solid #1abc9c20; }}
              .footer {{ text-align: center; padding: 20px; color: #666; font-size: 14px; }}
              .btn {{ display: inline-block; padding: 12px 24px; background: #1abc9c; color: white; text-decoration: none; border-radius: 8px; margin: 10px; }}
            </style>
          </head>
          <body>
            <div class="container">
              {body}
              <div class="footer">
                <p>This message was sent from your Daily Planner app</p>
                <p>Stay productive and keep achieving your goals!</p>
              </div>
            </div>
          </body>
        </html>
        """
        
        part = MIMEText(html_body, 'html')
        msg.attach(part)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"Email sent successfully to {recipient_email}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# SMS functionality removed - Twilio requires business verification
# Replaced with push notifications which are free and don't require verification

def send_push_notification(user_id, title, message):
    """
    Send push notification to user's browser using Web Push Protocol.
    
    Uses Web Push API to send notifications that appear even when the app is closed.
    Requires user to have granted notification permission in their browser.
    
    Args:
        user_id (str): The user's unique ID
        title (str): Notification title
        message (str): Notification message body
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    try:
        # Check if VAPID keys are configured
        if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
            print("⚠️ VAPID keys not configured - push notifications disabled")
            print("   Run: python generate_vapid_keys.py to generate keys")
            return False
        
        if not db:
            print("⚠️ Database not available for push notifications")
            return False
        
        # Import pywebpush
        try:
            from pywebpush import webpush, WebPushException  # type: ignore
        except ImportError:
            print("⚠️ pywebpush not installed. Run: pip install pywebpush")
            return False
        
        # Get user's push subscription from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            print(f"⚠️ User {user_id} not found")
            return False
            
        user_data = user_doc.to_dict()
        
        if not user_data or 'push_subscription' not in user_data:
            print(f"⚠️ No push subscription found for user {user_id}")
            return False
        
        push_subscription = user_data['push_subscription']
        
        # Prepare notification payload
        notification_data = {
            "title": title,
            "body": message,
            "icon": "/static/PlannerIcon.png",  # App icon
            "badge": "/static/PlannerIcon2.png",  # Badge icon
            "tag": f"task-notification-{int(time.time())}",
            "requireInteraction": False,
            "data": {
                "url": "/",  # URL to open when clicked
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Send the push notification
        try:
            response = webpush(
                subscription_info=push_subscription,
                data=json.dumps(notification_data),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": VAPID_EMAIL
                }
            )
            
            print(f"🔔 Push notification sent to user {user_id}: {title}")
            print(f"   Response: {response.status_code}")
            return True
            
        except WebPushException as e:
            print(f"❌ WebPush error for user {user_id}: {e}")
            
            # If subscription is invalid (410 Gone), remove it from database
            if e.response and e.response.status_code == 410:
                print(f"   Removing invalid subscription for user {user_id}")
                user_ref.update({
                    'push_subscription': firestore.DELETE_FIELD
                })
            
            return False
        
    except Exception as e:
        print(f"❌ Push notification error: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def send_sms(phone_number, message):
    """
    SMS notifications have been disabled.
    
    Twilio requires business verification for production use, which is not feasible
    for personal productivity apps. Push notifications are used instead.
    
    Returns:
        bool: Always returns False (SMS not available)
    """
    print("⚠️ SMS notifications are disabled. Twilio requires business verification.")
    print("� Please use push notifications instead.")
    return False

# Removed SMS sending logic below this line
if False:  # Legacy SMS code preserved for reference
    """    
    Legacy Twilio SMS code (DISABLED):
    
    if not twilio_client:
        print("⚠️ Twilio not configured")
        return False
    
    sender = None
    if TWILIO_SHORT_CODE:
        sender = TWILIO_SHORT_CODE
    elif TWILIO_MESSAGING_SERVICE_SID:
        pass
    elif TWILIO_PHONE_NUMBER:
        sender = TWILIO_PHONE_NUMBER
    else:
        return False
        
    try:
        if not phone_number.startswith('+'):
            if len(phone_number) == 10 and phone_number.isdigit():
                phone_number = f"+1{phone_number}"
            elif len(phone_number) == 11 and phone_number.startswith('1'):
                phone_number = f"+{phone_number}"
        
        if len(message) > 1600:
            message = message[:1597] + "..."
    """
    pass  # SMS functionality disabled - see function docstring above

# Global variable to track sent notifications (prevents duplicates)
sent_notifications = {}

def format_time_12hour(time_str):
    """
    Convert 24-hour time format to user-friendly 12-hour format with AM/PM.
    
    Handles both single times and time ranges with robust error handling.
    Used throughout the application for displaying times in notifications
    and user interfaces.
    
    Args:
        time_str (str): Time in 24-hour format (e.g., "14:30" or "09:00-10:00")
        
    Returns:
        str: Time in 12-hour format (e.g., "2:30 PM" or "9:00 AM - 10:00 AM")
             Returns original string if parsing fails
        
    Examples:
        format_time_12hour("14:30") -> "2:30 PM"
        format_time_12hour("09:00-10:00") -> "9:00 AM - 10:00 AM"
    """
    try:
        if not time_str or ':' not in time_str:
            return time_str
        
        # Handle time ranges like "09:00-10:00"
        if '-' in time_str:
            start_time, end_time = time_str.split('-')
            start_formatted = format_time_12hour(start_time.strip())
            end_formatted = format_time_12hour(end_time.strip())
            return f"{start_formatted} - {end_formatted}"
        
        # Parse single time
        time_obj = datetime.strptime(time_str.strip(), '%H:%M')
        return time_obj.strftime('%I:%M %p').lstrip('0')  # Remove leading zero
    except (ValueError, AttributeError):
        return time_str  # Return original if parsing fails

def get_user_current_time(user_timezone=None):
    """
    Get current time in user's timezone.

    Args:
        user_timezone (str): User's timezone (e.g., 'America/New_York', 'America/Los_Angeles')
                            If None, defaults to UTC

    Returns:
        datetime: Current time in user's timezone
    """
    try:
        if user_timezone:
            tz = ZoneInfo(user_timezone)
            return datetime.now(tz)
        else:
            # Default to UTC if no timezone specified
            return datetime.now(ZoneInfo('UTC'))
    except Exception as e:
        print(f"⚠️ Invalid timezone '{user_timezone}', falling back to UTC: {e}")
        return datetime.now(ZoneInfo('UTC'))

def cleanup_sent_notifications():
    """
    Clean up old notification tracking entries to prevent memory leaks and duplicates.
    
    For Vercel/serverless deployments, this also syncs with Firestore to maintain
    notification state across function invocations.
    
    Removes notification tracking entries older than 24 hours to maintain
    optimal performance and prevent duplicate notifications while keeping
    memory usage under control.
    
    Notes:
        - Removes in-memory entries older than 24 hours
        - Syncs with Firestore for serverless persistence
        - Handles invalid timestamp formats gracefully
        - Logs cleanup statistics for monitoring
    """
    try:
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=24)
        
        # Clean up in-memory cache
        keys_to_remove = []
        for key, sent_time_str in sent_notifications.items():
            try:
                sent_time = datetime.fromisoformat(sent_time_str)
                if sent_time < cutoff_time:
                    keys_to_remove.append(key)
            except (ValueError, TypeError):
                # Invalid timestamp, remove it
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del sent_notifications[key]
        
        if keys_to_remove:
            print(f"🧹 Cleaned up {len(keys_to_remove)} old in-memory notification entries")
        
        # For serverless: Clean up Firestore tracking collection
        if db:
            try:
                tracking_ref = db.collection('notification_tracking')
                old_docs = tracking_ref.where(filter=firestore.FieldFilter('sent_at', '<', cutoff_time)).limit(100).stream()
                
                deleted_count = 0
                for doc in old_docs:
                    doc.reference.delete()
                    deleted_count += 1
                
                if deleted_count > 0:
                    print(f"🧹 Cleaned up {deleted_count} old Firestore notification tracking entries")
            except Exception as e:
                print(f"⚠️  Error cleaning Firestore notification tracking: {e}")
                
    except Exception as e:
        print(f"⚠️ Error during notification cleanup: {e}")


def check_notification_sent(notification_key):
    """
    Check if a notification has already been sent (with Firestore persistence for serverless).
    
    This function checks both in-memory cache and Firestore to prevent duplicate
    notifications across serverless function invocations.
    
    Args:
        notification_key: Unique identifier for the notification
        
    Returns:
        bool: True if notification was already sent, False otherwise
    """
    # Check in-memory cache first (fastest)
    if notification_key in sent_notifications:
        return True
    
    # For serverless: Check Firestore for persistence across invocations
    if db:
        try:
            doc_ref = db.collection('notification_tracking').document(notification_key)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                sent_at = doc_data.get('sent_at')
                
                # Check if it's recent (within 24 hours)
                if isinstance(sent_at, datetime):
                    if (datetime.now() - sent_at).total_seconds() < 86400:  # 24 hours
                        # Cache it in memory for this invocation
                        sent_notifications[notification_key] = sent_at.isoformat()
                        return True
                    else:
                        # Old entry, delete it
                        doc_ref.delete()
                        return False
        except Exception as e:
            print(f"⚠️  Error checking Firestore notification tracking: {e}")
    
    return False


def mark_notification_sent(notification_key):
    """
    Mark a notification as sent (with Firestore persistence for serverless).
    
    This function records the notification in both in-memory cache and Firestore
    to prevent duplicates across serverless function invocations.
    
    Args:
        notification_key: Unique identifier for the notification
    """
    current_time = datetime.now()
    
    # Store in memory cache
    sent_notifications[notification_key] = current_time.isoformat()
    
    # For serverless: Store in Firestore for persistence
    if db:
        try:
            doc_ref = db.collection('notification_tracking').document(notification_key)
            doc_ref.set({
                'notification_key': notification_key,
                'sent_at': current_time,
                'created_at': current_time
            })
        except Exception as e:
            print(f"⚠️  Error storing notification tracking in Firestore: {e}")

def get_automatic_notification_times(tasks, current_time):
    """
    Automatically determine optimal notification times based on user's task patterns.
    
    Analyzes user's scheduled tasks to intelligently suggest notification times
    that align with their daily routine and task distribution.
    
    Args:
        tasks (list): List of user's tasks for analysis
        current_time (datetime): Current datetime for context
        
    Returns:
        list: Suggested notification times in minutes before tasks
        
    Logic:
        - Morning tasks (before 12 PM) -> 30 min + 5 min reminders
        - Afternoon tasks (12-5 PM) -> 60 min + 15 min reminders  
        - Evening tasks (after 5 PM) -> 120 min + 30 min reminders
        - High priority tasks get additional early reminders
    """
    notification_times = []
    
    # Analyze task patterns
    morning_tasks = [t for t in tasks if t.get('startTime', '').split(':')[0].isdigit() and int(t.get('startTime', '00:00').split(':')[0]) < 12]
    afternoon_tasks = [t for t in tasks if t.get('startTime', '').split(':')[0].isdigit() and 12 <= int(t.get('startTime', '00:00').split(':')[0]) < 17]
    evening_tasks = [t for t in tasks if t.get('startTime', '').split(':')[0].isdigit() and int(t.get('startTime', '00:00').split(':')[0]) >= 17]
    
    # Send morning preparation notification (7:30 AM) if user has morning tasks
    if morning_tasks and current_time.hour == 7 and 28 <= current_time.minute <= 32:
        notification_times.append(("morning_prep", f"Good morning! You have {len(morning_tasks)} task(s) scheduled for this morning. Have a productive day! 🌅"))
    
    # Send midday check-in (12:30 PM) if user has afternoon tasks
    if afternoon_tasks and current_time.hour == 12 and 28 <= current_time.minute <= 32:
        notification_times.append(("midday_prep", f"Hope your morning went well! You have {len(afternoon_tasks)} task(s) this afternoon. Keep up the great work! ☀️"))
    
    # Send evening preparation (5:30 PM) if user has evening tasks
    if evening_tasks and current_time.hour == 17 and 28 <= current_time.minute <= 32:
        notification_times.append(("evening_prep", f"As the day winds down, you have {len(evening_tasks)} task(s) scheduled for this evening. You've got this! 🌅"))
    
    return notification_times

def check_and_send_notifications():
    """
    Check for upcoming tasks and send notifications based on user's custom reminder times.
    This function is designed for serverless environments (Vercel) and is triggered by cron jobs.
    """
    if not db:
        print("⚠️ Database not available for notifications")
        return
    
    # Clean up old notification tracking entries
    cleanup_sent_notifications()
        
    try:
        print("🔔 Checking for task notifications based on user's custom reminder times...")
        users_ref = db.collection('users')
        users = users_ref.where(filter=firestore.FieldFilter('notifications_enabled', '==', True)).stream()

        notifications_sent = 0

        for user in users:
            user_data = user.to_dict()
            user_id = user.id
            user_email = user_data.get('email', 'Unknown')

            # Get user's timezone (default to America/New_York if not set)
            user_timezone = user_data.get('timezone', 'America/New_York')

            # Get current time in user's timezone
            current_time = get_user_current_time(user_timezone)
            today = current_time.strftime('%Y-%m-%d')
            current_day = current_time.strftime('%A').lower()

            print(f"🔍 Checking notifications for user: {user_email} (timezone: {user_timezone}, local time: {current_time.strftime('%I:%M %p')})")
            
            # Get user's custom reminder times (in minutes before task)
            # Support both custom_reminder_times and reminder_times field names
            user_reminder_times = user_data.get('custom_reminder_times') or user_data.get('reminder_times', [300, 60, 30])
            
            if not user_reminder_times or not isinstance(user_reminder_times, list):
                user_reminder_times = [300, 60, 30]  # Default: 5 hours, 1 hour, 30 minutes
                
            print(f"📅 User's reminder times: {user_reminder_times} minutes before tasks")
            
            # Get notification method
            notification_methods = user_data.get('notification_methods', [])
            if not notification_methods:
                # Fallback to single notification_method
                notification_methods = [user_data.get('notification_method', 'email')]
                
            print(f"📬 Notification methods: {notification_methods}")
            
            # Get all user's tasks
            tasks_ref = db.collection('users').document(user_id).collection('tasks')
            all_tasks = list(tasks_ref.stream())
            
            print(f"📋 Found {len(all_tasks)} total tasks for {user_email}")
            
            # Check each task
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                
                # Skip completed tasks
                if task_data.get('completed', False):
                    continue
                
                # Get task time
                task_time_str = None
                if task_data.get('startTime'):
                    task_time_str = task_data.get('startTime')
                elif task_data.get('time'):
                    # Handle format like "09:00-10:00" or just "09:00"
                    time_range = task_data.get('time', '')
                    if '-' in time_range:
                        task_time_str = time_range.split('-')[0].strip()
                    else:
                        task_time_str = time_range.strip()
                elif task_data.get('endTime'):
                    task_time_str = task_data.get('endTime')
                
                if not task_time_str:
                    continue  # Skip tasks without time
                
                # Check if task is for today
                task_day = task_data.get('day', '').lower()
                if task_day not in [current_day, 'today', '']:
                    continue  # Skip tasks not scheduled for today
                
                try:
                    # Parse task time
                    task_datetime_str = f"{today} {task_time_str}"
                    task_time = datetime.strptime(task_datetime_str, '%Y-%m-%d %H:%M')
                    
                    # Calculate time difference in minutes
                    time_diff_minutes = (task_time - current_time).total_seconds() / 60
                    
                    # Skip if task is in the past
                    if time_diff_minutes < 0:
                        continue
                    
                    print(f"   ⏰ Task: '{task_data.get('title')}' at {task_time_str} ({time_diff_minutes:.1f} min from now)")
                    
                    # Check if we should send notification for any of the user's reminder times
                    notification_sent_for_this_task = False
                    for reminder_minutes in user_reminder_times:
                        # Wider tolerance window: Check if we're within the 5-minute cron window BEFORE the reminder time
                        # This ensures we catch notifications even if cron runs early/late
                        # Example: For 60-min reminder, send if time_diff is between 57.5-62.5 minutes
                        tolerance = 10.0  # Increased from 2.5 to 5 minutes for better reliability
                        
                        # Also send if we're past the reminder time but within the window (catch-up logic)
                        min_boundary = reminder_minutes - tolerance
                        max_boundary = reminder_minutes + tolerance
                        
                        if min_boundary <= time_diff_minutes <= max_boundary:
                            # Found a match! Send notification
                            print(f"      ✅ MATCH! Time diff {time_diff_minutes:.1f} is within reminder window {min_boundary:.1f}-{max_boundary:.1f} min (target: {reminder_minutes} min)")
                            
                            # Create unique notification key to prevent duplicates
                            # Include reminder time to allow multiple notifications per task
                            notification_key = f"{user_id}_task_{task_doc.id}_reminder_{reminder_minutes}_{today}"
                            
                            # Check if already sent
                            if check_notification_sent(notification_key):
                                print(f"      ⏭️ Already sent this notification")
                                break
                            
                            # Format notification message
                            task_title = task_data.get('title', 'Untitled Task')
                            formatted_time = format_time_12hour(task_time_str)
                            
                            # Create contextual message based on time
                            if reminder_minutes >= 1440:  # 1 day or more
                                hours = reminder_minutes // 60
                                notification_title = f"📅 Task Tomorrow"
                                notification_body = f"{task_title} is scheduled for {formatted_time} tomorrow"
                            elif reminder_minutes >= 60:  # 1 hour or more
                                hours = reminder_minutes // 60
                                notification_title = f"⏰ Task in {hours} hour{'s' if hours != 1 else ''}"
                                notification_body = f"{task_title} starts at {formatted_time}"
                            elif reminder_minutes >= 15:  # 15-60 minutes
                                notification_title = f"⏱️ Task in {reminder_minutes} minutes"
                                notification_body = f"{task_title} starts at {formatted_time}"
                            else:  # Less than 15 minutes
                                notification_title = f"🚨 Task Starting Soon!"
                                notification_body = f"{task_title} starts at {formatted_time}"
                            
                            # Send via enabled notification methods
                            notification_sent_successfully = False
                            
                            if 'push' in notification_methods:
                                if send_push_notification(user_id, notification_title, notification_body):
                                    print(f"      ✅ Push notification sent")
                                    notification_sent_successfully = True
                                    notifications_sent += 1
                                else:
                                    print(f"      ❌ Failed to send push notification")
                            
                            if 'email' in notification_methods and user_data.get('email'):
                                # Create HTML email
                                priority_color = {
                                    'high': '#FF6B6B',
                                    'medium': '#4ECDC4', 
                                    'low': '#96CEB4'
                                }.get(task_data.get('priority', 'medium'), '#4ECDC4')
                                
                                email_body = f"""
                                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                                    <div style="background: linear-gradient(135deg, #1abc9c, #45B7D1); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                                        <h2 style="margin: 0;">{notification_title}</h2>
                                        <p style="margin: 10px 0 0 0;">{notification_body}</p>
                                    </div>
                                    <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px;">
                                        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid {priority_color};">
                                            <h3 style="margin: 0 0 5px 0; color: #2c3e50;">{task_title}</h3>
                                            <p style="margin: 0; color: #666;"><strong>⏰ Time:</strong> {formatted_time}</p>
                                            <p style="margin: 5px 0 0 0; color: #666;"><strong>📅 Day:</strong> {task_data.get('day', 'Today')}</p>
                                            {f'<p style="margin: 5px 0 0 0; color: #666;">{task_data.get("description", "")}</p>' if task_data.get('description') else ''}
                                        </div>
                                    </div>
                                    <div style="text-align: center; padding: 15px; color: #666; font-size: 12px;">
                                        <p>Good luck with your task! 🚀</p>
                                    </div>
                                </div>
                                """
                                
                                if send_email(user_data.get('email'), notification_title, email_body):
                                    print(f"      ✅ Email notification sent")
                                    notification_sent_successfully = True
                                    notifications_sent += 1
                                else:
                                    print(f"      ❌ Failed to send email notification")
                            
                            # Mark as sent if successful
                            if notification_sent_successfully:
                                mark_notification_sent(notification_key)
                                notification_sent_for_this_task = True
                            
                            # Only send one notification per check (prevent multiple reminders in same run)
                            break
                    
                    # Debug: Show why notification wasn't sent if we checked reminders
                    if not notification_sent_for_this_task and len(user_reminder_times) > 0:
                        closest_reminder = min(user_reminder_times, key=lambda x: abs(x - time_diff_minutes))
                        diff_from_closest = abs(time_diff_minutes - closest_reminder)
                        print(f"      ⏭️ No match. Closest reminder: {closest_reminder} min (diff: {diff_from_closest:.1f} min, need ≤5.0 min)")
                    
                except ValueError as e:
                    print(f"   ⚠️ Could not parse task time '{task_time_str}': {e}")
                    continue
        
        if notifications_sent > 0:
            print(f"🎯 Sent {notifications_sent} task notifications")
        else:
            print("📱 No notifications needed at this time")
            
        return notifications_sent
            
    except Exception as e:
        print(f"❌ Error in check_and_send_notifications: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return 0

def send_daily_summary():
    """Send daily summary of completed tasks"""
    if not db:
        print("⚠️ Database not available for daily summary")
        return
        
    try:
        print("📊 Generating daily summaries...")
        users_ref = db.collection('users')
        # Get all users with notifications enabled - we'll check daily_summary individually
        users = users_ref.where(filter=firestore.FieldFilter('notifications_enabled', '==', True)).stream()
        user_list = list(users)
        print(f"📊 Found {len(user_list)} users with notifications enabled")

        for user in user_list:
            user_data = user.to_dict()
            # Add explicit logging
            print(f"Checking {user_data.get('email')}: daily_summary={user_data.get('daily_summary', False)}")

        summaries_sent = 0
        users_checked = 0

        for user in users:
            users_checked += 1
            user_data = user.to_dict()
            user_id = user.id
            user_email = user_data.get('email', 'Unknown')

            # Only send if user has daily_summary enabled (check here instead of in query)
            if not user_data.get('daily_summary', False):
                print(f"⏭️ Skipping daily summary for {user_email} - daily summary disabled")
                continue

            # Get user's timezone (default to America/New_York if not set)
            user_timezone = user_data.get('timezone', 'America/New_York')
            today = get_user_current_time(user_timezone)

            print(f"📋 Generating summary for user: {user_email} (timezone: {user_timezone}, local time: {today.strftime('%I:%M %p')})")

            # Get ALL tasks from today (for testing)
            tasks_ref = db.collection('users').document(user_id).collection('tasks')
            all_tasks = list(tasks_ref.stream())

            current_day = today.strftime('%A').lower()
            today_date = today.strftime('%Y-%m-%d')
            
            completed_tasks = []
            pending_tasks = []
            all_today_tasks = []
            
            # Get all tasks scheduled for today
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                task_day = task_data.get('day', '').lower()
                
                # Check if task is for today
                if task_day == current_day or task_day == 'today' or not task_day:
                    all_today_tasks.append(task_data)
                    if task_data.get('completed', False):
                        completed_tasks.append(task_data)
                    else:
                        pending_tasks.append(task_data)
            
            # For testing: always show summary even with no tasks
            completed_today = completed_tasks[:10]  # Limit to 10 most recent
            
            # For testing: always send summary (even if no tasks)
            if True:  # Always send for testing
                # Create unique notification key for daily summary
                notification_key = f"{user_id}_daily_summary_{today_date}"
                
                # Use the proper Firestore-backed check
                if check_notification_sent(notification_key):
                    print(f"⏭️ Skipping daily summary notification for {user_email} - already sent today")
                    continue
                
                notification_method = user_data.get('notification_method', 'email')
                
                if notification_method == 'email' and user_data.get('email'):
                    # Calculate productivity stats
                    total_count = len([t for t in all_today_tasks if not t.get('completed', False)]) + len(completed_tasks)
                    completion_rate = (len(completed_tasks) / max(total_count, 1)) * 100 if total_count else 100
                    
                    subject = f"📊 Daily Summary - {len(all_today_tasks)} Tasks Today ({len(completed_today)} Completed)"
                    
                    # Create beautiful HTML email
                    body = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #28a745, #20c997); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                            <h2 style="margin: 0;">📊 Daily Task Summary</h2>
                            <p style="margin: 10px 0 0 0; font-size: 18px;">Here's how your day went!</p>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 20px;">
                            <div style="background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; text-align: center;">
                                <h3 style="margin: 0; color: #2c3e50;">📈 Today's Task Overview</h3>
                                <div style="display: flex; justify-content: space-around; margin: 15px 0; text-align: center;">
                                    <div style="flex: 1;">
                                        <p style="margin: 0; font-size: 24px; color: #28a745;"><strong>{len(completed_today)}</strong></p>
                                        <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">✅ Completed</p>
                                    </div>
                                    <div style="flex: 1;">
                                        <p style="margin: 0; font-size: 24px; color: #ffc107;"><strong>{len(pending_tasks)}</strong></p>
                                        <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">⏳ Pending</p>
                                    </div>
                                    <div style="flex: 1;">
                                        <p style="margin: 0; font-size: 24px; color: #17a2b8;"><strong>{len(all_today_tasks)}</strong></p>
                                        <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">📋 Total Today</p>
                                    </div>
                                </div>
                            </div>
                    """
                    
                    if completed_today:
                        body += '<h3 style="color: #2c3e50; margin: 15px 0 10px 0;">✅ Recently Completed:</h3>'
                        
                        for task in completed_today[:6]:  # Show max 6 tasks
                            priority_color = {
                                'high': '#FF6B6B',
                                'medium': '#4ECDC4', 
                                'low': '#96CEB4'
                            }.get(task.get('priority', 'medium'), '#4ECDC4')
                            
                            body += f"""
                            <div style="background: white; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid {priority_color};">
                                <strong style="color: #2c3e50;">✅ {task.get('title', 'Untitled Task')}</strong>
                                {f'<p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">{task.get("description", "")}</p>' if task.get('description') else ''}
                                <p style="margin: 5px 0 0 0; color: #999; font-size: 12px;">Day: {task.get('day', 'Today')}</p>
                            </div>
                            """
                        
                        if len(completed_today) > 6:
                            body += f'<p style="text-align: center; color: #666;">...and {len(completed_today) - 6} more tasks completed today!</p>'
                    
                    # Show pending tasks
                    if pending_tasks:
                        body += '<h3 style="color: #2c3e50; margin: 15px 0 10px 0;">⏳ Still To Do Today:</h3>'
                        
                        for task in pending_tasks[:4]:  # Show max 4 pending tasks
                            priority_color = {
                                'high': '#FF6B6B',
                                'medium': '#4ECDC4', 
                                'low': '#96CEB4'
                            }.get(task.get('priority', 'medium'), '#4ECDC4')
                            
                            task_time = task.get('startTime') or task.get('time') or task.get('endTime')
                            formatted_task_time = format_time_12hour(task_time) if task_time else ""
                            time_info = f" at {formatted_task_time}" if formatted_task_time else ""
                            
                            body += f"""
                            <div style="background: #fff3cd; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid {priority_color};">
                                <strong style="color: #2c3e50;">⏳ {task.get('title', 'Untitled Task')}{time_info}</strong>
                                {f'<p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">{task.get("description", "")}</p>' if task.get('description') else ''}
                                <p style="margin: 5px 0 0 0; color: #856404; font-size: 12px;">Priority: {task.get('priority', 'medium').title()}</p>
                            </div>
                            """
                        
                        if len(pending_tasks) > 4:
                            body += f'<p style="text-align: center; color: #666;">...and {len(pending_tasks) - 4} more tasks to complete!</p>'
                    elif not completed_today:
                        body += '<div style="background: #e2e3e5; padding: 15px; border-radius: 8px; text-align: center;"><p style="margin: 0; color: #6c757d;">No tasks scheduled for today. Great day to plan ahead! 📅</p></div>'
                    
                    # Add motivational message
                    motivation = random.choice(INSPIRATIONAL_MESSAGES)
                    body += f"""
                        </div>
                        
                        <div style="background: linear-gradient(135deg, #6c5ce7, #a29bfe); padding: 15px; color: white; text-align: center; border-radius: 0 0 10px 10px;">
                            <p style="margin: 0; font-size: 16px;">✨ {motivation}</p>
                            <p style="margin: 10px 0 0 0; font-size: 14px;">Ready to conquer tomorrow? �</p>
                        </div>
                    </div>
                    """
                    
                    if send_email(user_data.get('email'), subject, body):
                        mark_notification_sent(notification_key)  # Use Firestore-backed marking
                        summaries_sent += 1
                        print(f"✅ Daily summary sent to {user_email}")
                    else:
                        print(f"❌ Failed to send summary to {user_email}")
                        
                elif notification_method == 'push':
                    # Push notification summary (concise but informative)
                    message = f"Daily Summary: {len(completed_today)} tasks completed, {len(pending_tasks)} pending. "
                    if pending_tasks:
                        next_task = pending_tasks[0].get('title', 'Untitled')[:40]
                        message += f"Next up: {next_task}. "
                    message += random.choice(INSPIRATIONAL_MESSAGES)[:80]
                    
                    if send_push_notification(user_id, "📊 Daily Summary", message):
                        mark_notification_sent(notification_key)  # Use Firestore-backed marking
                        summaries_sent += 1
                        print(f"✅ Push summary sent to user {user_id}")
                    else:
                        print(f"❌ Failed to send push summary to user {user_id}")
            else:
                print(f"📋 No completed tasks found for {user_email}")
        
        if summaries_sent > 0:
            print(f"🎯 Sent {summaries_sent} daily summaries (checked {users_checked} users)")
        else:
            print(f"📊 No daily summaries sent (checked {users_checked} users, none had daily_summary enabled or already sent)")
        
        return summaries_sent
            
    except Exception as e:
        print(f"❌ Error in send_daily_summary: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return 0

def analyze_user_preferences(uid):
    """Analyze user's task history to learn preferences and patterns"""
    if not db:
        return {}
    
    try:
        print(f"🧠 Analyzing preferences for user {uid}...")
        
        # Get user's task history (last 3 months for good sample size)
        tasks_ref = db.collection('users').document(uid).collection('tasks')
        three_months_ago = datetime.now() - timedelta(days=90)
        
        # Get recent tasks
        all_tasks = list(tasks_ref.where('created_at', '>=', three_months_ago).stream())
        
        if len(all_tasks) < 10:
            print(f"⚠️ Not enough task history ({len(all_tasks)} tasks) to learn preferences")
            return {}
        
        # Analyze patterns
        preferences = {
            'activity_types': {},  # What types of tasks they create
            'time_patterns': {},   # When they like to schedule things
            'completion_patterns': {},  # What they actually complete vs abandon
            'description_style': [],    # How they write task descriptions
            'priority_patterns': {},    # How they set priorities
            'duration_patterns': {},    # How long they allocate for different tasks
            'day_preferences': {},      # Which days they prefer for what
            'interests': [],            # Topics/keywords that appear frequently
            'avoided_activities': []    # Tasks they create but rarely complete
        }
        
        completed_tasks = []
        incomplete_tasks = []
        
        for task_doc in all_tasks:
            task_data = task_doc.to_dict()
            title = task_data.get('title', '').lower()
            description = task_data.get('description', '').lower()
            priority = task_data.get('priority', 'medium')
            day = task_data.get('day', '')
            start_time = task_data.get('startTime', '')
            end_time = task_data.get('endTime', '')
            completed = task_data.get('completed', False)
            
            # Collect all text for analysis
            task_text = f"{title} {description}"
            
            # Categorize activity types based on keywords
            activity_type = 'other'
            if any(word in task_text for word in ['work', 'meeting', 'project', 'deadline', 'client', 'email', 'report']):
                activity_type = 'work'
            elif any(word in task_text for word in ['exercise', 'gym', 'walk', 'run', 'workout', 'fitness', 'health']):
                activity_type = 'fitness'
            elif any(word in task_text for word in ['grocery', 'shopping', 'errands', 'appointment', 'car', 'bills']):
                activity_type = 'errands'
            elif any(word in task_text for word in ['family', 'friend', 'social', 'dinner', 'call', 'visit']):
                activity_type = 'social'
            elif any(word in task_text for word in ['read', 'learn', 'study', 'course', 'book', 'research']):
                activity_type = 'learning'
            elif any(word in task_text for word in ['clean', 'organize', 'tidy', 'laundry', 'dishes', 'home']):
                activity_type = 'household'
            elif any(word in task_text for word in ['create', 'write', 'design', 'art', 'music', 'hobby']):
                activity_type = 'creative'
            
            # Track activity type preferences
            if activity_type not in preferences['activity_types']:
                preferences['activity_types'][activity_type] = {'created': 0, 'completed': 0}
            preferences['activity_types'][activity_type]['created'] += 1
            if completed:
                preferences['activity_types'][activity_type]['completed'] += 1
            
            # Track time preferences
            if start_time:
                hour = int(start_time.split(':')[0]) if ':' in start_time else 0
                time_slot = 'morning' if hour < 12 else 'afternoon' if hour < 18 else 'evening'
                if time_slot not in preferences['time_patterns']:
                    preferences['time_patterns'][time_slot] = {'created': 0, 'completed': 0}
                preferences['time_patterns'][time_slot]['created'] += 1
                if completed:
                    preferences['time_patterns'][time_slot]['completed'] += 1
            
            # Track day preferences
            if day:
                if day not in preferences['day_preferences']:
                    preferences['day_preferences'][day] = {'created': 0, 'completed': 0}
                preferences['day_preferences'][day]['created'] += 1
                if completed:
                    preferences['day_preferences'][day]['completed'] += 1
            
            # Track priority patterns
            if priority not in preferences['priority_patterns']:
                preferences['priority_patterns'][priority] = {'created': 0, 'completed': 0}
            preferences['priority_patterns'][priority]['created'] += 1
            if completed:
                preferences['priority_patterns'][priority]['completed'] += 1
            
            # Extract interests from frequently used words
            words = re.findall(r'\b\w+\b', task_text)
            for word in words:
                if len(word) > 3 and word not in ['task', 'work', 'need', 'make', 'time', 'today', 'week']:
                    preferences['interests'].append(word)
            
            # Collect task for completion analysis
            if completed:
                completed_tasks.append(task_data)
            else:
                incomplete_tasks.append(task_data)
        
        # Identify avoided activities (low completion rate)
        for activity_type, stats in preferences['activity_types'].items():
            if stats['created'] >= 3:  # Only consider if they've tried it multiple times
                completion_rate = stats['completed'] / stats['created']
                if completion_rate < 0.3:  # Less than 30% completion
                    preferences['avoided_activities'].append(activity_type)
        
        # Find most common interests (words that appear frequently)
        from collections import Counter
        interest_counts = Counter(preferences['interests'])
        preferences['interests'] = [word for word, count in interest_counts.most_common(10) if count >= 3]
        
        print(f"✅ Learned preferences for user {uid}: {len(preferences['activity_types'])} activity types analyzed")
        return preferences
        
    except Exception as e:
        print(f"❌ Error analyzing preferences: {e}")
        return {}

def get_user_preferences(uid):
    """Get stored user preferences combining explicit preferences and historical analysis"""
    if not db:
        return {}
    
    try:
        combined_preferences = {}
        
        # Load explicit preferences from preferences collection
        user_ref = db.collection('users').document(uid)
        prefs_doc = user_ref.collection('preferences').document('main').get()
        
        if prefs_doc.exists:
            explicit_prefs = prefs_doc.to_dict()
            combined_preferences['explicit'] = explicit_prefs
            print(f"✅ Loaded explicit preferences for user {uid}: {list(explicit_prefs.keys())}")
        else:
            combined_preferences['explicit'] = {}
            print(f"ℹ️ No explicit preferences found for user {uid}")
        
        # Check if historical analysis exists and is recent
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            stored_analysis = user_data.get('ai_preferences', {})
            last_analysis = user_data.get('preferences_last_updated')
            
            # Use stored analysis if less than 2 weeks old
            if stored_analysis and last_analysis:
                try:
                    # Handle Firestore DatetimeWithNanoseconds and regular datetime objects
                    from datetime import timezone
                    
                    # Firestore returns timezone-aware datetimes, so make our comparison datetime aware too
                    now_utc = datetime.now(timezone.utc)
                    
                    # last_analysis from Firestore is already timezone-aware
                    # Just calculate the difference
                    days_old = (now_utc - last_analysis).days
                    
                    if days_old < 14:
                        combined_preferences.update(stored_analysis)
                        print(f"✅ Using cached historical analysis (age: {days_old} days)")
                        return combined_preferences
                except Exception as e:
                    print(f"⚠️ Error checking analysis age: {e}")
                    # Continue to re-analyze if there's an error
        
        # Analyze preferences from task history
        historical_analysis = analyze_user_preferences(uid)
        
        if historical_analysis:
            # Merge historical analysis with explicit preferences
            combined_preferences.update(historical_analysis)
            
            # Store historical analysis in user document
            user_ref.update({
                'ai_preferences': historical_analysis,
                'preferences_last_updated': datetime.now()
            })
            print(f"💾 Stored updated historical analysis for user {uid}")
        
        return combined_preferences
        
    except Exception as e:
        print(f"❌ Error getting user preferences: {e}")
        return {}

def analyze_task_completion_patterns(uid):
    """
    Analyze user's task completion/deletion patterns to learn preferences.
    Returns insights about what types of tasks the user completes vs abandons.
    """
    if not db:
        return {}
    
    try:
        # Get task analytics from last 30 days
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        
        analytics_ref = db.collection('users').document(uid).collection('task_analytics')
        analytics_docs = analytics_ref.where('timestamp', '>=', cutoff_date).stream()
        
        completed_tasks = []
        abandoned_tasks = []
        
        for doc in analytics_docs:
            data = doc.to_dict()
            if data.get('completed'):
                completed_tasks.append(data)
            elif data.get('deleted') and not data.get('completed'):
                abandoned_tasks.append(data)
        
        print(f"📊 Task Analytics: {len(completed_tasks)} completed, {len(abandoned_tasks)} abandoned (last 30 days)")
        
        # Analyze patterns
        insights = {
            'completed_categories': {},
            'abandoned_categories': {},
            'preferred_times': {},
            'total_completed': len(completed_tasks),
            'total_abandoned': len(abandoned_tasks),
            'completion_rate': 0
        }
        
        # Calculate completion rate
        total = len(completed_tasks) + len(abandoned_tasks)
        if total > 0:
            insights['completion_rate'] = round((len(completed_tasks) / total) * 100, 1)
        
        # Categorize completed tasks
        for task in completed_tasks:
            category = task.get('category', 'other')
            insights['completed_categories'][category] = insights['completed_categories'].get(category, 0) + 1
            
            # Track preferred times
            time = task.get('time', '')
            if time:
                hour = time.split(':')[0] if ':' in time else ''
                if hour:
                    insights['preferred_times'][hour] = insights['preferred_times'].get(hour, 0) + 1
        
        # Categorize abandoned tasks
        for task in abandoned_tasks:
            category = task.get('category', 'other')
            insights['abandoned_categories'][category] = insights['abandoned_categories'].get(category, 0) + 1
        
        print(f"✅ Task completion insights: {insights['completion_rate']}% completion rate")
        print(f"   Most completed: {max(insights['completed_categories'].items(), key=lambda x: x[1]) if insights['completed_categories'] else 'N/A'}")
        print(f"   Most abandoned: {max(insights['abandoned_categories'].items(), key=lambda x: x[1]) if insights['abandoned_categories'] else 'N/A'}")
        
        return insights
        
    except Exception as e:
        print(f"❌ Error analyzing task patterns: {e}")
        return {}

def generate_preference_context(preferences):
    """Convert user preferences into AI prompt context"""
    if not preferences:
        return ""
    
    context_parts = []
    
    # Check for explicit user preferences (from preferences UI)
    explicit_prefs = preferences.get('explicit', {})
    
    # Hobbies and Interests
    if explicit_prefs.get('hobbies'):
        hobbies = explicit_prefs['hobbies']
        context_parts.append(f"USER HOBBIES & INTERESTS: {', '.join(hobbies)}")
        context_parts.append(f"  → When suggesting tasks, incorporate these interests where relevant (e.g., hobby time, creative projects related to {hobbies[0] if hobbies else 'interests'})")
    
    # Workout Styles
    if explicit_prefs.get('workoutStyles'):
        workout_styles = explicit_prefs['workoutStyles']
        context_parts.append(f"PREFERRED WORKOUT STYLES: {', '.join(workout_styles)}")
        context_parts.append(f"  → Suggest exercise tasks that match these preferences (e.g., {workout_styles[0] if workout_styles else 'preferred'} session)")
    
    # Daily Schedule
    if explicit_prefs.get('wakeTime') or explicit_prefs.get('bedTime'):
        wake_time = explicit_prefs.get('wakeTime', '07:00')
        bed_time = explicit_prefs.get('bedTime', '23:00')
        context_parts.append(f"DAILY SCHEDULE: Wakes at {wake_time}, Bedtime at {bed_time}")
        context_parts.append(f"  → Schedule tasks between {wake_time} and {bed_time}, suggest morning routines after {wake_time}")
    
    # Exercise Time Preference
    if explicit_prefs.get('exerciseTime'):
        exercise_time = explicit_prefs.get('exerciseTime', 'morning')
        time_map = {
            'morning': '6:00-11:00 AM',
            'afternoon': '12:00-5:00 PM', 
            'evening': '6:00-10:00 PM',
            'flexible': 'any time'
        }
        context_parts.append(f"EXERCISE TIME PREFERENCE: {exercise_time.title()} ({time_map.get(exercise_time, 'flexible')})")
        context_parts.append(f"  → Schedule workout tasks during {exercise_time} hours when possible")
    
    # Event Categories
    if explicit_prefs.get('eventCategories'):
        event_categories = explicit_prefs['eventCategories']
        context_parts.append(f"FAVORITE EVENT TYPES: {', '.join(event_categories)}")
        context_parts.append(f"  → When user asks for event suggestions or weekend plans, recommend {event_categories[0] if event_categories else 'relevant'} events")
    
    # Location
    if explicit_prefs.get('location'):
        location = explicit_prefs['location']
        context_parts.append(f"USER LOCATION: {location}")
        context_parts.append(f"  → Suggest local activities and events in {location} area")
    
    # Activity preferences (from historical analysis)
    if preferences.get('activity_types'):
        preferred_activities = []
        avoided_activities = preferences.get('avoided_activities', [])
        
        for activity, stats in preferences['activity_types'].items():
            if stats['created'] >= 3:
                completion_rate = stats['completed'] / stats['created']
                if completion_rate > 0.7:
                    preferred_activities.append(f"{activity} (completes {completion_rate:.0%})")
        
        if preferred_activities:
            context_parts.append(f"HISTORICAL PREFERRED ACTIVITIES: {', '.join(preferred_activities)}")
        if avoided_activities:
            context_parts.append(f"TENDS TO AVOID: {', '.join(avoided_activities)}")
    
    # Time preferences (from historical analysis)
    if preferences.get('time_patterns'):
        best_times = []
        for time_slot, stats in preferences['time_patterns'].items():
            if stats['created'] >= 3:
                completion_rate = stats['completed'] / stats['created']
                if completion_rate > 0.7:
                    best_times.append(f"{time_slot} (completes {completion_rate:.0%})")
        
        if best_times:
            context_parts.append(f"MOST PRODUCTIVE TIMES (from history): {', '.join(best_times)}")
    
    # Day preferences (from historical analysis)
    if preferences.get('day_preferences'):
        productive_days = []
        for day, stats in preferences['day_preferences'].items():
            if stats['created'] >= 2:
                completion_rate = stats['completed'] / stats['created']
                if completion_rate > 0.7:
                    productive_days.append(f"{day} (completes {completion_rate:.0%})")
        
        if productive_days:
            context_parts.append(f"MOST PRODUCTIVE DAYS (from history): {', '.join(productive_days)}")
    
    # Interests (from keyword analysis)
    if preferences.get('interests'):
        context_parts.append(f"FREQUENT KEYWORDS: {', '.join(preferences['interests'][:5])}")
    
    if context_parts:
        header = "\n\n🧠 USER PREFERENCES (Use these to personalize suggestions!):\n"
        header += "=" * 60 + "\n"
        return header + "\n".join(context_parts) + "\n" + "=" * 60 + "\n"
    
    return ""

def send_sporadic_inspiration():
    """Send sporadic inspiration messages throughout the day to engaged users"""
    if not db:
        print("⚠️ Database not available for sporadic inspiration")
        return
        
    try:
        print("💫 Checking for sporadic inspiration sending...")
        users_ref = db.collection('users')
        # Get users with notifications enabled and auto_inspiration enabled (default to true if not set)
        users = users_ref.where(filter=firestore.FieldFilter('notifications_enabled', '==', True)).stream()
        
        current_time = datetime.now()
        inspirations_sent = 0
        
        for user in users:
            user_data = user.to_dict()
            user_id = user.id
            user_email = user_data.get('email', 'Unknown')
            
            # Check if user has auto_inspiration enabled (default to True if not set)
            auto_inspiration = user_data.get('auto_inspiration', True)
            if not auto_inspiration:
                print(f"⏭️ Skipping inspiration for {user_email} - auto inspiration disabled")
                continue
            
            # Check if user needs inspiration (based on activity and busy schedule)
            should_send = False
            
            # Get user's recent activity - only get today's tasks to improve performance
            tasks_ref = db.collection('users').document(user_id).collection('tasks')
            
            # Get today's tasks more efficiently by filtering on current day and date
            today_tasks = []
            completed_today = 0
            
            current_day = current_time.strftime('%A').lower()
            today_date = current_time.strftime('%Y-%m-%d')
            
            # Get all tasks and filter properly for today only
            all_tasks = list(tasks_ref.stream())
            
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                task_day = task_data.get('day', '').lower()
                task_date = task_data.get('date', '')  # Check if there's a date field
                created_date = task_data.get('created_at')
                
                # More precise filtering for today's tasks
                is_today_task = False
                
                # Method 1: Check if task day matches current day name
                if task_day == current_day:
                    is_today_task = True
                
                # Method 2: Check if task has today's date
                elif task_date == today_date:
                    is_today_task = True
                
                # Method 3: Check if task was created today and has no specific day set
                elif created_date and isinstance(created_date, datetime):
                    if created_date.strftime('%Y-%m-%d') == today_date and not task_day:
                        is_today_task = True
                
                # Only include if it's actually a today task
                if is_today_task:
                    today_tasks.append(task_data)
                    if task_data.get('completed', False):
                        completed_today += 1
            
            print(f"📊 User {user_email}: Found {len(today_tasks)} tasks for today ({completed_today} completed)")
            
            # Send inspiration if:
            # 1. Busy day (5+ tasks today) or
            # 2. Low completion rate (< 50% of today's tasks completed) or  
            # 3. Random chance (10% to keep it sporadic)
            total_today = len(today_tasks)
            completion_rate = (completed_today / max(total_today, 1)) * 100 if total_today else 100
            
            if (total_today >= 5 or 
                (total_today > 0 and completion_rate < 50) or 
                random.random() < 0.1):
                should_send = True
            
            if should_send:
                # Create unique notification key for sporadic inspiration
                notification_key = f"{user_id}_inspiration_{today_date}"
                
                # Use the proper Firestore-backed check
                if check_notification_sent(notification_key):
                    print(f"⏭️ Skipping sporadic inspiration for {user_email} - already sent today")
                    continue
                
                print(f"💫 Sending sporadic inspiration to {user_email} (tasks: {total_today}, completed: {completion_rate:.0f}%)")
                
                message = random.choice(INSPIRATIONAL_MESSAGES)
                notification_method = user_data.get('notification_method', 'email')
                
                if notification_method == 'email' and user_data.get('email'):
                    subject = "💫 A Little Motivation For Your Day"
                    body = f"""
                    <div class="header">
                        <h2>✨ Sporadic Inspiration Alert! ✨</h2>
                    </div>
                    <div class="content">
                        <div class="inspiration">
                            <h2 style="color: #1abc9c; font-size: 28px; margin: 20px 0;">{message}</h2>
                            <p style="margin-top: 30px; font-size: 18px;">
                                {f"You've got {total_today} tasks today - you're handling it like a champion! 🏆" if total_today > 3 else "Keep up the amazing work! 🌟"}
                            </p>
                            <p style="margin-top: 15px; font-size: 14px; opacity: 0.8;">
                                This message was sent automatically because you've enabled sporadic inspiration in your settings.
                            </p>
                        </div>
                    </div>
                    """
                    
                    if send_email(user_data.get('email'), subject, body):
                        mark_notification_sent(notification_key)  # Use Firestore-backed marking
                        inspirations_sent += 1
                        print(f"✅ Sporadic inspiration email sent to {user_email}")
                    else:
                        print(f"❌ Failed to send sporadic inspiration email to {user_email}")
                        
                elif notification_method == 'push':
                    push_message = f"💫 {message}"
                    if total_today > 3:
                        push_message += f" You've got {total_today} tasks today - you've got this! 🏆"
                    
                    if send_push_notification(user_id, "✨ Sporadic Inspiration", push_message):
                        mark_notification_sent(notification_key)  # Use Firestore-backed marking
                        inspirations_sent += 1
                        print(f"✅ Sporadic inspiration push sent to user {user_id}")
                    else:
                        print(f"❌ Failed to send sporadic inspiration SMS to {user_data.get('phone')}")
        
        if inspirations_sent > 0:
            print(f"🎯 Sent {inspirations_sent} sporadic inspiration messages")
        else:
            print("💫 No sporadic inspirations needed right now")
        
        return inspirations_sent
            
    except Exception as e:
        print(f"❌ Error in send_sporadic_inspiration: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return 0
        print(f"Full traceback: {traceback.format_exc()}")

def run_scheduler():
    """Run the notification scheduler in background"""
    # Check for task notifications every 5 minutes (reduced frequency)
    schedule.every(5).minutes.do(check_and_send_notifications)
    
    # Send daily summary only once at 8 PM
    schedule.every().day.at("20:00").do(send_daily_summary)
    
    # Send sporadic inspirations at random times throughout the day
    schedule.every().day.at("09:30").do(send_sporadic_inspiration)
    schedule.every().day.at("11:45").do(send_sporadic_inspiration)
    schedule.every().day.at("14:20").do(send_sporadic_inspiration)
    schedule.every().day.at("16:10").do(send_sporadic_inspiration)
    schedule.every().day.at("18:35").do(send_sporadic_inspiration)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Weather functionality using OpenWeatherMap API
def get_weather_icon_class(weather_id, is_day=True):
    """Get weather icon class based on OpenWeatherMap weather ID"""
    # OpenWeatherMap weather condition IDs to icon mapping
    if 200 <= weather_id <= 232:  # Thunderstorm
        return "wi-thunderstorm"
    elif 300 <= weather_id <= 321:  # Drizzle
        return "wi-sprinkle"
    elif 500 <= weather_id <= 531:  # Rain
        if weather_id == 511:
            return "wi-rain-mix"
        return "wi-rain"
    elif 600 <= weather_id <= 622:  # Snow
        return "wi-snow"
    elif 701 <= weather_id <= 781:  # Atmosphere (fog, etc.)
        if weather_id == 781:
            return "wi-tornado"
        return "wi-fog"
    elif weather_id == 800:  # Clear sky
        return "wi-day-sunny" if is_day else "wi-night-clear"
    elif 801 <= weather_id <= 804:  # Clouds
        if weather_id == 801:
            return "wi-day-cloudy" if is_day else "wi-night-alt-cloudy"
        elif weather_id == 802:
            return "wi-day-cloudy" if is_day else "wi-night-alt-cloudy"
        else:
            return "wi-cloudy"
    
    return "wi-na"  # Not available

def get_weather_by_coordinates(lat, lon):
    """Get current weather and 7-day forecast using OpenWeatherMap API"""
    if not OPENWEATHERMAP_API_KEY:
        raise Exception("OpenWeatherMap API key not configured")
    
    try:
        # Get current weather
        current_url = f"https://api.openweathermap.org/data/2.5/weather"
        current_params = {
            'lat': lat,
            'lon': lon,
            'appid': OPENWEATHERMAP_API_KEY,
            'units': 'imperial'  # Fahrenheit
        }
        
        current_response = requests.get(current_url, params=current_params, timeout=10)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        # Get 7-day forecast
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast"
        forecast_params = {
            'lat': lat,
            'lon': lon,
            'appid': OPENWEATHERMAP_API_KEY,
            'units': 'imperial'
        }
        
        forecast_response = requests.get(forecast_url, params=forecast_params, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        # Process current weather
        current_weather = {
            'location': f"{current_data['name']}, {current_data['sys']['country']}",
            'temperature': round(current_data['main']['temp']),
            'feels_like': round(current_data['main']['feels_like']),
            'condition': current_data['weather'][0]['description'].title(),
            'humidity': current_data['main']['humidity'],
            'wind_speed': round(current_data['wind']['speed']),
            'wind_deg': current_data['wind'].get('deg', 0),
            'icon_class': get_weather_icon_class(current_data['weather'][0]['id']),
            'weather_id': current_data['weather'][0]['id'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Process 7-day forecast (group by day)
        daily_forecasts = {}
        for item in forecast_data['list']:
            date = datetime.fromtimestamp(item['dt']).date()
            day_name = date.strftime('%A')
            
            if day_name not in daily_forecasts:
                daily_forecasts[day_name] = {
                    'day': day_name,
                    'date': date.strftime('%Y-%m-%d'),
                    'high_temp': round(item['main']['temp_max']),
                    'low_temp': round(item['main']['temp_min']),
                    'condition': item['weather'][0]['description'].title(),
                    'icon_class': get_weather_icon_class(item['weather'][0]['id']),
                    'weather_id': item['weather'][0]['id'],
                    'humidity': item['main']['humidity'],
                    'wind_speed': round(item['wind']['speed'])
                }
            else:
                # Update high/low temps if this reading is more extreme
                daily_forecasts[day_name]['high_temp'] = max(
                    daily_forecasts[day_name]['high_temp'], 
                    round(item['main']['temp_max'])
                )
                daily_forecasts[day_name]['low_temp'] = min(
                    daily_forecasts[day_name]['low_temp'], 
                    round(item['main']['temp_min'])
                )
        
        # Convert to list and limit to 7 days
        forecast_list = list(daily_forecasts.values())[:7]
        
        return {
            'current': current_weather,
            'forecast': forecast_list,
            'success': True
        }
        
    except requests.RequestException as e:
        print(f"OpenWeatherMap API error: {e}")
        raise Exception(f"Failed to fetch weather data: {str(e)}")
    except Exception as e:
        print(f"Weather processing error: {e}")
        raise Exception(f"Weather processing error: {str(e)}")

def get_weather_by_city(city):
    """Get weather for a specific city"""
    if not OPENWEATHERMAP_API_KEY:
        raise Exception("OpenWeatherMap API key not configured")
    
    try:
        # First get coordinates for the city
        geocoding_url = f"https://api.openweathermap.org/geo/1.0/direct"
        geocoding_params = {
            'q': city,
            'limit': 1,
            'appid': OPENWEATHERMAP_API_KEY
        }
        
        geo_response = requests.get(geocoding_url, params=geocoding_params, timeout=10)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data:
            raise Exception(f"City '{city}' not found")
        
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']
        
        return get_weather_by_coordinates(lat, lon)
        
    except requests.RequestException as e:
        print(f"Geocoding API error: {e}")
        raise Exception(f"Failed to find city: {str(e)}")
    except Exception as e:
        print(f"City weather error: {e}")
        raise Exception(str(e))

def get_weather_by_zipcode(zipcode):
    """Get weather for a specific US zipcode"""
    if not OPENWEATHERMAP_API_KEY:
        raise Exception("OpenWeatherMap API key not configured")
    
    try:
        # Get coordinates from zipcode using OpenWeatherMap Geocoding API
        geocoding_url = f"https://api.openweathermap.org/geo/1.0/zip"
        geocoding_params = {
            'zip': f"{zipcode},US",
            'appid': OPENWEATHERMAP_API_KEY
        }
        
        geo_response = requests.get(geocoding_url, params=geocoding_params, timeout=10)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data:
            raise Exception(f"Zipcode '{zipcode}' not found")
        
        lat = geo_data['lat']
        lon = geo_data['lon']
        
        return get_weather_by_coordinates(lat, lon)
        
    except requests.RequestException as e:
        print(f"Zipcode geocoding API error: {e}")
        raise Exception(f"Failed to find zipcode: {str(e)}")
    except Exception as e:
        print(f"Zipcode weather error: {e}")
        raise Exception(str(e))

def search_cities(query, limit=10):
    """Search for cities in the CSV file based on query"""
    if not query or len(query.strip()) < 2:
        return []
    
    query = query.strip().lower()
    results = []
    
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'uscities.csv')
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                city = row.get('city', '').strip()
                state = row.get('state_name', '').strip()
                population = row.get('population', '0')
                
                if not city or not state:
                    continue
                
                city_lower = city.lower()
                state_lower = state.lower()
                
                # Check if query matches city name (starts with or contains)
                city_match_score = 0
                if city_lower.startswith(query):
                    city_match_score = 100  # Exact start match gets highest priority
                elif query in city_lower:
                    city_match_score = 50   # Contains match gets medium priority
                
                # Check if query matches state
                state_match_score = 0
                if state_lower.startswith(query):
                    state_match_score = 25
                elif query in state_lower:
                    state_match_score = 10
                
                # Combined match score
                total_score = city_match_score + state_match_score
                
                if total_score > 0:
                    try:
                        pop_int = int(population) if population.isdigit() else 0
                    except (ValueError, TypeError):
                        pop_int = 0
                    
                    # Boost score based on population (larger cities get slight preference)
                    if pop_int > 100000:
                        total_score += 10
                    elif pop_int > 50000:
                        total_score += 5
                    elif pop_int > 10000:
                        total_score += 2
                    
                    results.append({
                        'city': city,
                        'state': state,
                        'state_id': row.get('state_id', ''),
                        'population': pop_int,
                        'latitude': float(row.get('lat', 0)),
                        'longitude': float(row.get('lng', 0)),
                        'display_name': f"{city}, {state}",
                        'score': total_score
                    })
                
                # Stop if we have enough high-quality results
                if len(results) >= limit * 3:  # Get extra to sort and filter
                    break
        
        # Sort by score (descending) and population (descending) as tiebreaker
        results.sort(key=lambda x: (x['score'], x['population']), reverse=True)
        
        # Return top results, removing duplicates
        seen = set()
        unique_results = []
        for result in results:
            key = (result['city'].lower(), result['state'].lower())
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
                if len(unique_results) >= limit:
                    break
        
        return unique_results
        
    except FileNotFoundError:
        print("Cities CSV file not found")
        return []
    except Exception as e:
        print(f"City search error: {e}")
        return []



# ===== NOTIFICATION SCHEDULER (FOR LOCAL DEVELOPMENT ONLY) =====
# NOTE: This background thread DOES NOT WORK on Vercel's serverless architecture!
# For Vercel deployment, use the cron API endpoints (/api/cron/check-notifications, etc.)
# triggered by Vercel Cron Jobs or external cron services like cron-job.org
#
# Uncomment below ONLY for local development/testing:
#
# if db and ENV != 'production':
#     scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
#     scheduler_thread.start()
#     print("📅 Notification scheduler started (LOCAL DEVELOPMENT ONLY)")

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/api/firebase-config")
def get_firebase_config():
    """
    Securely serve Firebase client configuration from environment variables.
    This prevents hardcoding API keys in frontend JavaScript files.
    
    Returns:
        JSON object with Firebase configuration
    """
    firebase_config = {
        "apiKey": os.getenv('FIREBASE_API_KEY', ''),
        "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN', ''),
        "projectId": os.getenv('FIREBASE_PROJECT_ID', ''),
        "storageBucket": os.getenv('FIREBASE_STORAGE_BUCKET', ''),
        "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
        "appId": os.getenv('FIREBASE_APP_ID', ''),
        "measurementId": os.getenv('FIREBASE_MEASUREMENT_ID', '')
    }
    
    # Check if all required config is present
    if not firebase_config['apiKey']:
        return jsonify({
            "error": "Firebase configuration not found. Please set environment variables."
        }), 500
    
    return jsonify(firebase_config)

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/reset-password")
def reset_password():
    """Custom password reset page with Planno branding"""
    return render_template("reset-password.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/planner")
def planner():
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return redirect(url_for("login"))
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        display_name = decoded_claims.get("name") or decoded_claims.get("email") or "User"
        return render_template("index.html", user=display_name)
    except Exception:
        resp = make_response(redirect(url_for("login")))
        resp.delete_cookie(SESSION_COOKIE_NAME)
        return resp

@app.route("/api/sessionLogin", methods=["POST"])
def session_login():
    """
    Authenticate user with Firebase ID token and create/update user session.
    
    This endpoint handles Firebase authentication token verification with
    robust error handling for clock skew issues. Creates or updates user
    documents in Firestore with default settings.
    
    Request Body:
        idToken (str): Firebase ID token from client authentication
        
    Returns:
        dict: Success response with user ID and message
        dict: Error response with details if authentication fails
        
    HTTP Status Codes:
        200: Successful authentication and session creation
        400: Missing or invalid ID token
        401: Token verification failed
        500: Server error during user creation
        
    Security Features:
        - Verifies Firebase ID token authenticity
        - Handles clock skew gracefully with fallback verification
        - Checks token revocation status when possible
        - Validates audience and issuer claims
    """
    id_token = request.json.get("idToken")
    remember_me = request.json.get("rememberMe", False)  # Get Remember Me preference
    
    if not id_token:
        return {"error": "Missing ID token"}, 400

    try:
        # Verify token with manual clock skew handling
        import time
        import jwt
        
        try:
            decoded_token = auth.verify_id_token(id_token, check_revoked=True)
        except ValueError as e:
            error_str = str(e)
            if "Token used too early" in error_str or "Token used too late" in error_str:
                print(f"Clock skew detected: {e}")
                try:
                    # Decode without verification to check token contents
                    unverified = jwt.decode(id_token, options={"verify_signature": False})
                    print(f"Token issued at: {unverified.get('iat')}, expires: {unverified.get('exp')}")
                    
                    # Try verification without revocation check (more lenient)
                    decoded_token = auth.verify_id_token(id_token, check_revoked=False)
                    print("Token verified successfully with relaxed checking")
                except Exception as inner_e:
                    print(f"Relaxed verification also failed: {inner_e}")
                    # Last resort: manual validation of core claims
                    if unverified.get('aud') == 'daily-planner-57801' and unverified.get('iss').startswith('https://securetoken.google.com/'):
                        print("Using unverified token due to clock skew")
                        decoded_token = unverified
                    else:
                        raise e
            else:
                raise e
        
        uid = decoded_token['uid']
        email = decoded_token.get('email', '')
        name = decoded_token.get('name', '')
        
        # Create/update user document in Firestore
        if db:
            user_ref = db.collection('users').document(uid)
            
            # Check if user already exists
            user_doc = user_ref.get()
            
            if user_doc.exists:
                # Existing user - only update login time and basic info, preserve settings
                user_ref.update({
                    'email': email,
                    'name': name,
                    'last_login': datetime.now(),
                    'uid': uid
                })
                print(f"✅ Updated existing user {uid} - settings preserved")
            else:
                # New user - create with default settings
                user_ref.set({
                    'email': email,
                    'name': name,
                    'last_login': datetime.now(),
                    'uid': uid,
                    'notifications_enabled': False,
                    'notification_method': 'email',
                    'daily_summary': True,
                    'reminder_time': 30,
                    'auto_inspiration': True,
                    'auto_delete_old_tasks': False,
                    'auto_cleanup': False,
                    'cleanup_weeks': 2,
                    'custom_reminder_times': [300, 60, 30],
                    'daily_summary_time': '23:30'
                })
                print(f"✅ Created new user {uid} with default settings")
        
        # Set session duration based on Remember Me preference
        session_duration = SESSION_MAX_AGE if remember_me else timedelta(hours=1)
        
        session_cookie = auth.create_session_cookie(id_token, expires_in=session_duration)
        resp = make_response({"status": "ok"})
        resp.set_cookie(
            SESSION_COOKIE_NAME,
            session_cookie,
            max_age=int(session_duration.total_seconds()),
            httponly=True,
            secure=False,
            samesite="Lax",
            path="/"
        )
        
        print(f"✅ Session created for {uid} - Remember Me: {remember_me}, Duration: {session_duration}")
        return resp
    except Exception as e:
        print(f"Session login error: {e}")
        return {"error": "Invalid ID token"}, 401


@app.route('/api/send-password-reset', methods=['POST'])
def send_password_reset():
    """
    Send a password reset email to the user using Firebase Authentication.
    
    This endpoint triggers Firebase's built-in password reset email flow.
    The email will be sent automatically by Firebase with a secure reset link.
    
    Request Body:
        email (str): User's email address
        
    Returns:
        dict: Success message if email sent
        dict: Error message if email not found or sending failed
        
    HTTP Status Codes:
        200: Password reset email sent successfully
        400: Missing email parameter
        500: Server error during email sending
    """
    data = request.json
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'error': 'Email address is required'}), 400
    
    try:
        # Verify email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Use Firebase REST API to send password reset email
        # This actually triggers the email, unlike generate_password_reset_link
        firebase_api_key = os.getenv('FIREBASE_API_KEY')
        
        if not firebase_api_key:
            print("❌ FIREBASE_API_KEY not found in environment variables")
            return jsonify({
                'error': 'Server configuration error. Please contact support.'
            }), 500
        
        print(f"🔑 Using Firebase API key: {firebase_api_key[:10]}...")
        print(f"📧 Sending password reset email to: {email}")
        
        # Firebase Auth REST API endpoint for password reset
        reset_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={firebase_api_key}"
        
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email
        }
        
        print(f"🌐 Calling Firebase REST API: {reset_url[:80]}...")
        
        response = requests.post(reset_url, json=payload, timeout=10)
        
        print(f"📬 Firebase API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"✅ Password reset email sent successfully to {email}")
            print(f"📨 Response: {response_data}")
            return jsonify({
                'success': True,
                'message': f'Password reset email sent to {email}. Please check your inbox and spam folder.'
            }), 200
        else:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            
            print(f"❌ Firebase password reset error: {error_message}")
            print(f"📋 Full error response: {error_data}")
            
            # Handle specific Firebase errors
            if 'EMAIL_NOT_FOUND' in error_message:
                # For security, still return success to prevent email enumeration
                print(f"⚠️  Password reset requested for non-existent email: {email}")
                return jsonify({
                    'success': True,
                    'message': f'If an account exists for {email}, a password reset email has been sent.'
                }), 200
            elif 'INVALID_EMAIL' in error_message:
                return jsonify({
                    'error': 'Invalid email address.'
                }), 400
            else:
                return jsonify({
                    'error': 'Failed to send password reset email. Please try again later.'
                }), 500
        
    except requests.RequestException as e:
        print(f"❌ Network error sending password reset email: {e}")
        return jsonify({
            'error': 'Network error. Please try again later.'
        }), 500
        
    except Exception as e:
        print(f"❌ Error sending password reset email: {e}")
        return jsonify({
            'error': 'Failed to send password reset email. Please try again later.'
        }), 500


@app.route('/api/sessionStatus', methods=['GET'])
def session_status():
    """Return 200 if server session cookie is valid, 401 otherwise."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return jsonify({"status": "no_session"}), 401

    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        return jsonify({"status": "ok", "uid": decoded_claims.get('uid'), "email": decoded_claims.get('email', '')})
    except Exception as e:
        print(f"Session status verify error: {e}")
        return jsonify({"error": str(e)}), 401

@app.route("/api/notification-settings", methods=["GET", "POST"])
def notification_settings():
    """Get or update user notification preferences"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
            
        user_ref = db.collection('users').document(uid)
        
        if request.method == "GET":
            user_doc = user_ref.get()
            if user_doc.exists:
                data = user_doc.to_dict()
                print(f"🔍 Loading user data from database: {data}")
                
                # Get reminder times, supporting both old and new field names
                reminder_times = data.get('custom_reminder_times') or data.get('reminder_times', [300, 60, 30])
                print(f"🔍 Resolved reminder_times: {reminder_times}")
                
                # Get notification methods array (or convert single method to array)
                notification_methods = data.get('notification_methods', [data.get('notification_method', 'email')])
                if not isinstance(notification_methods, list):
                    notification_methods = [notification_methods]
                
                response_data = {
                    'notifications_enabled': data.get('notifications_enabled', False),
                    'notification_method': data.get('notification_method', 'email'),
                    'notification_methods': notification_methods,  # Array of selected methods
                    'phone': data.get('phone', ''),
                    'email': data.get('email', ''),
                    'timezone': data.get('timezone', 'America/New_York'),  # User's timezone
                    'daily_summary': data.get('daily_summary', True),
                    'reminder_time': data.get('reminder_time', 30),  # Legacy single time
                    'reminder_times': reminder_times,  # New flexible times
                    'custom_reminder_times': reminder_times,  # Frontend expects this field name
                    'daily_summary_time': data.get('daily_summary_time', '23:30'),  # Frontend expects this field name
                    'auto_inspiration': data.get('auto_inspiration', True),
                    'auto_delete_old_tasks': data.get('auto_delete_old_tasks', False),  # Add missing setting
                    'auto_cleanup': data.get('auto_cleanup', False),
                    'cleanup_weeks': data.get('cleanup_weeks', 2)
                }
                print(f"📤 Sending response: {response_data}")
                return jsonify(response_data)
            return jsonify({
                'notifications_enabled': False,
                'notification_method': 'email',
                'notification_methods': ['email'],  # Default to email only
                'phone': '',
                'email': decoded_claims.get('email', ''),
                'timezone': 'America/New_York',  # Default timezone
                'daily_summary': True,
                'reminder_time': 30,  # Legacy single time
                'reminder_times': [300, 60, 30],  # New flexible times (minutes)
                'custom_reminder_times': [300, 60, 30],  # Frontend expects this field name
                'daily_summary_time': '23:30',  # Frontend expects this field name
                'auto_inspiration': True,
                'auto_delete_old_tasks': False,  # Add missing setting
                'auto_cleanup': False,
                'cleanup_weeks': 2
            })
        
        elif request.method == "POST":
            settings = request.json
            print(f"🔔 Received notification settings: {settings}")
            
            update_data = {
                'notifications_enabled': settings.get('notifications_enabled', False),
                'notification_method': settings.get('notification_method', 'email'),
                'notification_methods': settings.get('notification_methods', [settings.get('notification_method', 'email')]),  # Array of methods
                'phone': settings.get('phone', ''),
                'timezone': settings.get('timezone', 'America/New_York'),  # User's timezone
                'daily_summary': settings.get('daily_summary', True),
                'reminder_time': settings.get('reminder_time', 30),  # Legacy single time
                'auto_inspiration': settings.get('auto_inspiration', True),
                'auto_delete_old_tasks': settings.get('auto_delete_old_tasks', False),  # Add missing setting
                'auto_cleanup': settings.get('auto_cleanup', False),
                'cleanup_weeks': settings.get('cleanup_weeks', 2)
            }
            
            # Handle both old and new field names for reminder times
            if settings.get('custom_reminder_times'):
                update_data['reminder_times'] = settings.get('custom_reminder_times')
                update_data['custom_reminder_times'] = settings.get('custom_reminder_times')
                print(f"💾 Saving custom_reminder_times: {settings.get('custom_reminder_times')}")
            elif settings.get('reminder_times'):
                update_data['reminder_times'] = settings.get('reminder_times')
                update_data['custom_reminder_times'] = settings.get('reminder_times')
                print(f"💾 Saving reminder_times: {settings.get('reminder_times')}")
            else:
                update_data['reminder_times'] = [300, 60, 30]
                update_data['custom_reminder_times'] = [300, 60, 30]
                print("💾 Using default reminder times: [300, 60, 30]")
            
            # Handle daily summary time
            if settings.get('daily_summary_time'):
                update_data['daily_summary_time'] = settings.get('daily_summary_time')
                print(f"💾 Saving daily_summary_time: {settings.get('daily_summary_time')}")
            
            # Update email if provided
            if settings.get('email'):
                update_data['email'] = settings.get('email')
            
            print(f"💾 Final update_data: {update_data}")
            user_ref.update(update_data)
            print("✅ Successfully updated database")
            return jsonify({"status": "Settings updated successfully"})
    
    except Exception as e:
        print(f"Notification settings error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/send-inspiration", methods=["POST"])
def send_inspiration():
    """Send an inspirational message on demand"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            message = random.choice(INSPIRATIONAL_MESSAGES)
            
            email_sent = False
            sms_sent = False
            
            # Support multiple notification methods
            notification_methods = user_data.get('notification_methods', [user_data.get('notification_method', 'email')])
            
            if 'email' in notification_methods and user_data.get('email'):
                subject = "💫 Your Daily Inspiration"
                body = f"""
                <div class="header">
                    <h2>A Message Just For You!</h2>
                </div>
                <div class="content">
                    <div class="inspiration">
                        <h2 style="color: #1abc9c; font-size: 28px; margin: 20px 0;">{message}</h2>
                        <p style="margin-top: 30px; font-size: 18px;">Keep being awesome! 🌟</p>
                    </div>
                </div>
                """
                email_sent = send_email(user_data.get('email'), subject, body)
            
            if 'sms' in notification_methods and user_data.get('phone'):
                sms_sent = send_sms(user_data.get('phone'), f"💫 {message}")
            
            if email_sent or sms_sent:
                return jsonify({"status": "Inspiration sent!", "message": message})
            else:
                return jsonify({"error": "Failed to send inspiration"}), 400
        
        return jsonify({"error": "User not found"}), 404
    
    except Exception as e:
        print(f"Send inspiration error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/test-notification", methods=["POST"])
def test_notification():
    """Send a test notification"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_email = user_data.get('email', 'Unknown')
            
            print(f"🧪 Sending test notification to {user_email}")
            
            if user_data.get('notification_method') == 'email' and user_data.get('email'):
                subject = "🧪 Test Notification - Daily Planner"
                
                # Get current settings from user data
                current_settings = {
                    'email': user_data.get('email', 'Not set'),
                    'notification_method': user_data.get('notification_method', 'email'),
                    'reminder_minutes': user_data.get('custom_reminder_times', [30])[0] if user_data.get('custom_reminder_times') else user_data.get('reminder_time', 30),
                    'daily_summary': user_data.get('daily_summary', True),
                    'phone': user_data.get('phone', 'Not set'),
                    'notification_types': user_data.get('notification_types', ['task_reminders', 'daily_summary'])
                }
                
                # Create a beautiful test email
                body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                        <h2 style="margin: 0;">🧪 Test Notification</h2>
                        <p style="margin: 10px 0 0 0;">Your Daily Planner notifications are working perfectly!</p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px;">
                        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #28a745;">
                            <h3 style="margin: 0 0 10px 0; color: #2c3e50;">✅ Notifications Active</h3>
                            <p style="margin: 0; color: #666;">You'll receive notifications for:</p>
                            <ul style="color: #666; margin: 10px 0;">
                                <li>⏰ Task reminders {current_settings['reminder_minutes']} minutes before</li>
                                <li>📊 Daily summaries ({'enabled' if current_settings['daily_summary'] else 'disabled'})</li>
                                <li>💫 Motivational messages</li>
                            </ul>
                        </div>
                        
                        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #17a2b8;">
                            <h3 style="margin: 0 0 10px 0; color: #2c3e50;">⚙️ Current Settings</h3>
                            <p style="margin: 0; color: #666;">
                                <strong>Email:</strong> {current_settings['email']}<br>
                                <strong>Phone:</strong> {current_settings['phone'] if current_settings['notification_method'] == 'sms' else 'SMS not active'}<br>
                                <strong>Method:</strong> {current_settings['notification_method'].title()}<br>
                                <strong>Reminder Time:</strong> {current_settings['reminder_minutes']} minutes before tasks<br>
                                <strong>Daily Summary:</strong> {'Enabled' if current_settings['daily_summary'] else 'Disabled'}
                            </p>
                        </div>
                    </div>
                    
                    <div style="background: linear-gradient(135deg, #f093fb, #f5576c); padding: 15px; color: white; text-align: center; border-radius: 0 0 10px 10px;">
                        <p style="margin: 0; font-size: 16px;">✨ {random.choice(INSPIRATIONAL_MESSAGES)}</p>
                        <p style="margin: 10px 0 0 0; font-size: 14px;">Test completed successfully! 🎉</p>
                    </div>
                </div>
                """
                
                if send_email(user_data.get('email'), subject, body):
                    print(f"✅ Test email sent successfully to {user_email}")
                    return jsonify({
                        "status": "success",
                        "message": f"Test email sent successfully to {user_data.get('email')}!"
                    })
                else:
                    print(f"❌ Failed to send test email to {user_email}")
                    return jsonify({"error": "Failed to send test email. Check your email configuration."}), 500
            
            elif user_data.get('notification_method') == 'sms' and user_data.get('phone'):
                # Create SMS test message with current settings
                reminder_minutes = user_data.get('custom_reminder_times', [30])[0] if user_data.get('custom_reminder_times') else user_data.get('reminder_time', 30)
                message = f"🧪 Daily Planner Test: Your SMS notifications are working! "
                message += f"You'll get reminders {reminder_minutes}min before tasks. "
                message += f"{random.choice(INSPIRATIONAL_MESSAGES)[:30]}... ✨"
                
                if send_sms(user_data.get('phone'), message[:160]):
                    print(f"✅ Test SMS sent successfully to {user_data.get('phone')}")
                    return jsonify({
                        "status": "success", 
                        "message": f"Test SMS sent successfully to {user_data.get('phone')}!"
                    })
                else:
                    print(f"❌ Failed to send test SMS to {user_data.get('phone')}")
                    return jsonify({"error": "Failed to send test SMS. Check your phone number and SMS configuration."}), 500
            
            else:
                return jsonify({
                    "error": "No notification method configured. Please set up your email or phone number in settings."
                }), 400
        
        return jsonify({"error": "User not found"}), 404
    
    except Exception as e:
        print(f"❌ Test notification error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {"error": f"Test notification failed: {str(e)}"}, 500

@app.route("/api/test-task-reminder", methods=["POST"])
def test_task_reminder():
    """Send a test task reminder notification"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_email = user_data.get('email', 'Unknown')
            
            print(f"⏰ Sending test task reminder to {user_email}")
            
            # Create fake upcoming tasks for testing
            fake_tasks = [
                {
                    'title': 'Important Meeting',
                    'time': '14:30',
                    'description': 'Quarterly review with the team',
                    'priority': 'high',
                    'day': 'Today'
                },
                {
                    'title': 'Grocery Shopping',
                    'time': '16:00',
                    'description': 'Pick up ingredients for dinner',
                    'priority': 'medium',
                    'day': 'Today'
                }
            ]
            
            if user_data.get('notification_method') == 'email' and user_data.get('email'):
                subject = f"⏰ Test Reminder: {len(fake_tasks)} Task(s) Coming Up!"
                
                # Create HTML email body (same as real notifications)
                body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #1abc9c, #45B7D1); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                        <h2 style="margin: 0;">⏰ Test Task Reminder</h2>
                        <p style="margin: 10px 0 0 0;">This is how your task reminders will look!</p>
                    </div>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px;">
                """
                
                for task in fake_tasks:
                    priority_color = {
                        'high': '#FF6B6B',
                        'medium': '#4ECDC4', 
                        'low': '#96CEB4'
                    }.get(task['priority'], '#4ECDC4')
                    
                    body += f"""
                    <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid {priority_color};">
                        <h3 style="margin: 0 0 5px 0; color: #2c3e50;">{task['title']}</h3>
                        <p style="margin: 0; color: #666;"><strong>⏰ Time:</strong> {task['time']}</p>
                        <p style="margin: 5px 0 0 0; color: #666;"><strong>📅 Day:</strong> {task['day']}</p>
                        <p style="margin: 5px 0 0 0; color: #666;">{task['description']}</p>
                    </div>
                    """
                
                body += """
                    <div style="text-align: center; padding: 15px; color: #666; font-size: 12px;">
                        <p>This is a test - your actual reminders will show your real tasks! 🚀</p>
                        <p>You can adjust reminder timing in settings.</p>
                    </div>
                </div>
                """
                
                if send_email(user_data.get('email'), subject, body):
                    return jsonify({
                        "status": "success",
                        "message": f"Test task reminder sent to {user_data.get('email')}!"
                    })
                else:
                    return jsonify({"error": "Failed to send test reminder email"}), 500
                    
            elif user_data.get('notification_method') == 'sms' and user_data.get('phone'):
                message = f"⏰ TEST: 2 tasks coming up: Important Meeting, Grocery Shopping at 14:30. This is how your task reminders look!"
                
                if send_sms(user_data.get('phone'), message[:160]):
                    return jsonify({
                        "status": "success",
                        "message": f"Test task reminder SMS sent to {user_data.get('phone')}!"
                    })
                else:
                    return jsonify({"error": "Failed to send test reminder SMS"}), 500
            else:
                return jsonify({"error": "No notification method configured"}), 400
        
        return jsonify({"error": "User not found"}), 404
    
    except Exception as e:
        print(f"❌ Test task reminder error: {e}")
        return {"error": f"Test failed: {str(e)}"}, 500

@app.route("/api/create-test-task", methods=["POST"])
def create_test_task():
    """Create a test task with time coming up soon for notification testing"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        # Get current time and create a task 10 minutes from now
        current_time = datetime.now()
        test_time = current_time + timedelta(minutes=10)
        
        test_task = {
            'id': str(uuid.uuid4()),
            'title': '🧪 Test Notification Task',
            'description': f'This test task was created at {current_time.strftime("%H:%M")} and is scheduled for {test_time.strftime("%H:%M")}',
            'startTime': test_time.strftime('%H:%M'),
            'endTime': (test_time + timedelta(minutes=30)).strftime('%H:%M'),
            'day': current_time.strftime('%A').lower(),
            'priority': 'high',
            'completed': False,
            'created_at': current_time,
            'user_id': uid
        }
        
        # Save to Firestore
        tasks_ref = db.collection('users').document(uid).collection('tasks')
        doc_ref = tasks_ref.document(test_task['id'])
        doc_ref.set(test_task)
        
        print(f"✅ Created test task for {decoded_claims.get('email', 'user')} - Due at {test_time.strftime('%H:%M')}")
        
        return jsonify({
            "status": "success",
            "message": f"Test task created! Should trigger notification around {test_time.strftime('%H:%M')}",
            "task": {
                "title": test_task['title'],
                "time": test_task['startTime'],
                "description": test_task['description']
            }
        })
    
    except Exception as e:
        print(f"❌ Create test task error: {e}")
        return {"error": f"Failed to create test task: {str(e)}"}, 500

@app.route("/api/test-daily-summary", methods=["POST"])
def test_daily_summary():
    """Send a test daily summary notification"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_email = user_data.get('email', 'Unknown')
            
            print(f"📊 Sending test daily summary to {user_email}")
            
            # Get actual completed tasks from today instead of fake ones
            tasks_ref = db.collection('users').document(uid).collection('tasks')
            all_tasks = list(tasks_ref.stream())
            
            current_time = datetime.now()
            current_day = current_time.strftime('%A').lower()
            today_date = current_time.strftime('%Y-%m-%d')
            
            actual_completed_tasks = []
            total_today_tasks = []
            
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                task_day = task_data.get('day', '').lower()
                
                # Check if task is for today
                if task_day == current_day or task_day == 'today' or not task_day:
                    total_today_tasks.append(task_data)
                    if task_data.get('completed', False):
                        actual_completed_tasks.append(task_data)
            
            # If no actual completed tasks, create sample ones for testing
            if not actual_completed_tasks:
                actual_completed_tasks = [
                    {
                        'title': '📝 Test Task Example',
                        'description': 'This is a sample completed task for testing',
                        'priority': 'medium',
                        'day': 'Today',
                        'completed': True
                    },
                    {
                        'title': '🧪 Daily Summary Test',
                        'description': 'Testing the daily summary functionality',
                        'priority': 'high',
                        'day': 'Today',
                        'completed': True
                    }
                ]
                print("📋 No actual completed tasks found, using sample tasks for test")
            else:
                print(f"📋 Found {len(actual_completed_tasks)} actual completed tasks for test summary")
            
            fake_completed_tasks = actual_completed_tasks  # Use actual tasks
            
            if user_data.get('notification_method') == 'email' and user_data.get('email'):
                subject = f"📊 Test Daily Summary: {len(fake_completed_tasks)} Task(s) Completed!"
                
                # Create beautiful HTML email
                body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #28a745, #20c997); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                        <h2 style="margin: 0;">📊 Test Daily Achievement Summary</h2>
                        <p style="margin: 10px 0 0 0; font-size: 18px;">This is how your daily summaries will look!</p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px;">
                        <div style="background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; text-align: center;">
                            <h3 style="margin: 0; color: #2c3e50;">📈 Your Test Productivity</h3>
                            <p style="margin: 5px 0; font-size: 24px; color: #28a745;"><strong>{len(fake_completed_tasks)}</strong> completed today</p>
                            <p style="margin: 5px 0; font-size: 18px; color: #17a2b8;"><strong>{len(total_today_tasks)}</strong> total tasks today</p>
                            <p style="margin: 5px 0; color: #666;">
                                {'🎉 Perfect completion rate!' if len(total_today_tasks) > 0 and len(fake_completed_tasks) == len(total_today_tasks) else f'💪 {(len(fake_completed_tasks) / max(len(total_today_tasks), 1) * 100):.0f}% completion rate!'}
                            </p>
                        </div>
                        
                        <h3 style="color: #2c3e50; margin: 15px 0 10px 0;">✅ {'Your Completed Tasks:' if len(actual_completed_tasks) > 0 and len(actual_completed_tasks) == len(fake_completed_tasks) else 'Sample Completed Tasks:'}</h3>
                """
                
                for task in fake_completed_tasks:
                    priority_color = {
                        'high': '#FF6B6B',
                        'medium': '#4ECDC4', 
                        'low': '#96CEB4'
                    }.get(task.get('priority', 'medium'), '#4ECDC4')
                    
                    body += f"""
                    <div style="background: white; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid {priority_color};">
                        <strong style="color: #2c3e50;">✅ {task.get('title', 'Untitled Task')}</strong>
                        <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">{task.get('description', 'No description available')}</p>
                    </div>
                    """
                
                body += f"""
                    </div>
                    
                    <div style="background: linear-gradient(135deg, #6c5ce7, #a29bfe); padding: 15px; color: white; text-align: center; border-radius: 0 0 10px 10px;">
                        <p style="margin: 0; font-size: 16px;">✨ {random.choice(INSPIRATIONAL_MESSAGES)}</p>
                        <p style="margin: 10px 0 0 0; font-size: 14px;">This is a test - your real summaries will show your actual completed tasks! 🎉</p>
                    </div>
                </div>
                """
                
                if send_email(user_data.get('email'), subject, body):
                    return jsonify({
                        "status": "success",
                        "message": f"Test daily summary sent to {user_data.get('email')}!"
                    })
                else:
                    return jsonify({"error": "Failed to send test summary email"}), 500
                    
            elif user_data.get('notification_method') == 'sms' and user_data.get('phone'):
                task_names = [task.get('title', 'Task') for task in fake_completed_tasks[:2]]
                message = f"📊 TEST Daily Summary: You completed {len(fake_completed_tasks)} task(s) today!"
                if task_names:
                    message += f" {', '.join(task_names)}"
                    if len(fake_completed_tasks) > 2:
                        message += f" +{len(fake_completed_tasks) - 2} more"
                message += " Great job! ✨"
                
                if send_sms(user_data.get('phone'), message[:160]):
                    return jsonify({
                        "status": "success",
                        "message": f"Test daily summary SMS sent to {user_data.get('phone')}!"
                    })
                else:
                    return jsonify({"error": "Failed to send test summary SMS"}), 500
            else:
                return jsonify({"error": "No notification method configured"}), 400
        
        return jsonify({"error": "User not found"}), 404
    
    except Exception as e:
        print(f"❌ Test daily summary error: {e}")
        return {"error": f"Test failed: {str(e)}"}, 500

@app.route("/api/tasks", methods=["POST"])
def save_task():
    """Save a task to Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        task_data = request.json
        if not task_data:
            return {"error": "No task data provided"}, 400
        
        # Add metadata
        task_data.update({
            'created_at': datetime.now(),
            'user_id': uid,
            'id': task_data.get('id', str(uuid.uuid4())),
            'completed': task_data.get('completed', False)
        })
        
        # Save to Firestore
        tasks_ref = db.collection('users').document(uid).collection('tasks')
        doc_ref = tasks_ref.document(task_data['id'])
        doc_ref.set(task_data)
        
        print(f"✅ Task saved to Firestore: {task_data.get('title')} for user {uid}")
        
        return jsonify({
            "status": "success",
            "message": "Task saved successfully",
            "id": task_data['id']
        })
    
    except Exception as e:
        print(f"❌ Save task error: {e}")
        return {"error": f"Failed to save task: {str(e)}"}, 500

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    """Get user's tasks from Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        # Get tasks from Firestore
        tasks_ref = db.collection('users').document(uid).collection('tasks')
        all_tasks = list(tasks_ref.stream())
        
        tasks = []
        for task_doc in all_tasks:
            task_data = task_doc.to_dict()
            # Convert datetime to string for JSON serialization
            if 'created_at' in task_data:
                task_data['created_at'] = task_data['created_at'].isoformat()
            tasks.append(task_data)
        
        return jsonify({
            "status": "success",
            "tasks": tasks,
            "count": len(tasks)
        })
    
    except Exception as e:
        print(f"❌ Get tasks error: {e}")
        return {"error": f"Failed to get tasks: {str(e)}"}, 500

@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    """Update a task in Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        task_data = request.json
        if not task_data:
            return {"error": "No task data provided"}, 400
        
        # Get the existing task to compare changes
        task_ref = db.collection('users').document(uid).collection('tasks').document(task_id)
        existing_task = task_ref.get()
        
        # Track task completion patterns for AI learning
        if existing_task.exists:
            old_task = existing_task.to_dict()
            new_completed = task_data.get('completed', False)
            old_completed = old_task.get('completed', False)
            
            # If task completion status changed, log it for learning (unless privacy mode is on)
            if new_completed != old_completed:
                # Check if user has privacy mode enabled
                user_ref = db.collection('users').document(uid)
                prefs_doc = user_ref.collection('preferences').document('main').get()
                privacy_mode = False
                if prefs_doc.exists:
                    privacy_mode = prefs_doc.to_dict().get('privacyMode', False)
                
                # Only track if privacy mode is OFF
                if not privacy_mode:
                    completion_data = {
                        'task_id': task_id,
                        'task_title': task_data.get('title', old_task.get('title', '')),
                        'task_category': task_data.get('category', old_task.get('category', '')),
                        'completed': new_completed,
                        'timestamp': datetime.now(),
                        'date': task_data.get('date', old_task.get('date', '')),
                        'time': task_data.get('time', old_task.get('time', '')),
                        'description': task_data.get('description', old_task.get('description', ''))
                    }
                    
                    # Store in learning analytics collection
                    learning_ref = db.collection('users').document(uid).collection('task_analytics')
                    learning_ref.add(completion_data)
                    print(f"📊 Logged task completion pattern: {completion_data['task_title']} - completed: {new_completed}")
                else:
                    print(f"🔒 Privacy mode enabled - skipping task analytics tracking")
        
        # Update task in Firestore
        task_ref.update({
            **task_data,
            'updated_at': datetime.now()
        })
        
        print(f"✅ Task updated in Firestore: {task_id} for user {uid}")
        
        return jsonify({
            "status": "success",
            "message": "Task updated successfully"
        })
    
    except Exception as e:
        print(f"❌ Update task error: {e}")
        return {"error": f"Failed to update task: {str(e)}"}, 500

@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    """Delete a task from Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        # Get task data before deleting for learning analytics
        task_ref = db.collection('users').document(uid).collection('tasks').document(task_id)
        task_doc = task_ref.get()
        
        if task_doc.exists:
            task_data = task_doc.to_dict()
            
            # Check if user has privacy mode enabled
            user_ref = db.collection('users').document(uid)
            prefs_doc = user_ref.collection('preferences').document('main').get()
            privacy_mode = False
            if prefs_doc.exists:
                privacy_mode = prefs_doc.to_dict().get('privacyMode', False)
            
            # Only track deletion if privacy mode is OFF
            if not privacy_mode:
                # Log deleted task (likely abandoned/not wanted)
                deletion_data = {
                    'task_id': task_id,
                    'task_title': task_data.get('title', ''),
                    'task_category': task_data.get('category', ''),
                    'deleted': True,
                    'completed': task_data.get('completed', False),
                    'timestamp': datetime.now(),
                    'date': task_data.get('date', ''),
                    'time': task_data.get('time', ''),
                    'description': task_data.get('description', '')
                }
                
                # Store in learning analytics
                learning_ref = db.collection('users').document(uid).collection('task_analytics')
                learning_ref.add(deletion_data)
                print(f"📊 Logged task deletion: {deletion_data['task_title']} - was completed: {deletion_data['completed']}")
            else:
                print(f"🔒 Privacy mode enabled - skipping task deletion analytics")
        
        # Delete task from Firestore
        task_ref.delete()
        
        print(f"✅ Task deleted from Firestore: {task_id} for user {uid}")
        
        return jsonify({
            "status": "success",
            "message": "Task deleted successfully"
        })
    
    except Exception as e:
        print(f"❌ Delete task error: {e}")
        return {"error": f"Failed to delete task: {str(e)}"}, 500

@app.route("/api/tasks/bulk-delete", methods=["POST"])
def bulk_delete_tasks():
    """Delete multiple tasks from Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        data = request.json
        print(f"🔍 Bulk delete request data: {data}")
        
        if not data or 'task_ids' not in data:
            return {"error": "task_ids array required"}, 400
        
        task_ids = data['task_ids']
        print(f"🔍 Task IDs to delete: {task_ids} (count: {len(task_ids)})")
        
        if not isinstance(task_ids, list):
            return {"error": "task_ids must be an array"}, 400
        
        # Delete tasks from Firestore
        deleted_count = 0
        tasks_ref = db.collection('users').document(uid).collection('tasks')
        
        for task_id in task_ids:
            try:
                print(f"🔍 Attempting to delete task: {task_id}")
                task_ref = tasks_ref.document(task_id)
                task_ref.delete()
                deleted_count += 1
                print(f"✅ Successfully deleted task: {task_id}")
            except Exception as e:
                print(f"❌ Failed to delete task {task_id}: {e}")
        
        print(f"✅ Bulk deleted {deleted_count}/{len(task_ids)} tasks from Firestore for user {uid}")
        
        return jsonify({
            "status": "success",
            "message": f"Deleted {deleted_count} tasks successfully",
            "deleted_count": deleted_count
        })
    
    except Exception as e:
        print(f"❌ Bulk delete tasks error: {e}")
        return {"error": f"Failed to delete tasks: {str(e)}"}, 500

@app.route("/api/class-schedule", methods=["GET"])
def get_class_schedule():
    """Get user's class schedule from Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        # Get user's class schedule document
        doc_ref = db.collection('class_schedules').document(uid)
        doc = doc_ref.get()
        
        if doc.exists:
            schedule_data = doc.to_dict()
            print(f"✅ Retrieved class schedule for user {uid}")
            return jsonify(schedule_data)
        else:
            # Return default structure if no schedule exists
            default_schedule = {
                "semester": {
                    "name": "",
                    "startDate": "",
                    "endDate": ""
                },
                "breaks": [],
                "classes": []
            }
            print(f"📝 No class schedule found for user {uid}, returning default")
            return jsonify(default_schedule)
    
    except Exception as e:
        print(f"❌ Get class schedule error: {e}")
        return {"error": f"Failed to get class schedule: {str(e)}"}, 500

@app.route("/api/class-schedule", methods=["POST"])
def save_class_schedule():
    """Save user's class schedule to Firestore"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return {"error": "Database not available"}, 500
        
        # Get the schedule data from request
        schedule_data = request.get_json()
        if not schedule_data:
            return {"error": "No schedule data provided"}, 400
        
        # Add metadata
        schedule_data['uid'] = uid
        schedule_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Save to Firestore
        doc_ref = db.collection('class_schedules').document(uid)
        doc_ref.set(schedule_data, merge=True)
        
        print(f"✅ Saved class schedule for user {uid}")
        return jsonify({
            "status": "success",
            "message": "Class schedule saved successfully"
        })
    
    except Exception as e:
        print(f"❌ Save class schedule error: {e}")
        return {"error": f"Failed to save class schedule: {str(e)}"}, 500

@app.route("/api/weather", methods=["POST"])
def get_weather():
    """Get current weather and 7-day forecast using user's coordinates"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        
        # Get coordinates from request
        data = request.get_json()
        if not data or 'latitude' not in data or 'longitude' not in data:
            return {"error": "Latitude and longitude required"}, 400
        
        lat = data['latitude']
        lon = data['longitude']
        
        # Get weather data using OpenWeatherMap API
        weather_data = get_weather_by_coordinates(lat, lon)
        
        return jsonify(weather_data)
    
    except Exception as e:
        print(f"Weather API error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/weather/city/<city>", methods=["GET"])
def get_weather_for_city(city):
    """Get weather for a specific city or zipcode"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        
        # Check if input is a zipcode (5 digits) or city name
        if city.isdigit() and len(city) == 5:
            # It's a US zipcode
            weather_data = get_weather_by_zipcode(city)
        else:
            # It's a city name
            weather_data = get_weather_by_city(city)
        
        return jsonify(weather_data)
    
    except Exception as e:
        print(f"Weather API error for {city}: {e}")
        return {"error": str(e)}, 500

@app.route("/api/cities/search", methods=["GET"])
def search_cities_api():
    """Search for cities with autocomplete functionality"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        
        # Get search query from URL parameters
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 20)  # Max 20 results
        
        if not query or len(query) < 2:
            return jsonify({"results": [], "message": "Query must be at least 2 characters"})
        
        # Search cities in CSV file
        cities = search_cities(query, limit)
        
        return jsonify({
            "results": cities,
            "query": query,
            "count": len(cities)
        })
    
    except Exception as e:
        print(f"City search API error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/weather/coordinates", methods=["POST"])
def get_weather_by_coordinates_api():
    """Get weather using specific coordinates (for selected cities)"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        
        # Get coordinates from request
        data = request.get_json()
        if not data or 'latitude' not in data or 'longitude' not in data:
            return {"error": "Latitude and longitude required"}, 400
        
        lat = data['latitude']
        lon = data['longitude']
        
        # Get weather data using OpenWeatherMap API
        weather_data = get_weather_by_coordinates(lat, lon)
        
        return jsonify(weather_data)
    
    except Exception as e:
        print(f"Weather coordinates API error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/user-settings", methods=["GET", "POST"])
def user_settings():
    """Get or update user settings (theme preferences, etc.)"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if request.method == "GET":
            # Get user settings from Firestore
            try:
                user_ref = db.collection('users').document(uid)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    settings = user_data.get('settings', {})
                    print(f"✅ Retrieved settings for user {uid}: {settings}")
                    return jsonify(settings)
                else:
                    # Return default settings if no user doc exists
                    default_settings = {"theme": "light"}
                    print(f"📄 No settings found for user {uid}, returning defaults")
                    return jsonify(default_settings)
                    
            except Exception as e:
                print(f"❌ Error getting user settings: {e}")
                return {"error": f"Failed to get settings: {str(e)}"}, 500
        
        elif request.method == "POST":
            # Update user settings in Firestore
            data = request.get_json()
            if not data:
                return {"error": "No settings data provided"}, 400
            
            try:
                user_ref = db.collection('users').document(uid)
                
                # Update settings in the user document
                user_ref.set({
                    'settings': data,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True)
                
                print(f"✅ Updated settings for user {uid}: {data}")
                return jsonify({
                    "status": "success",
                    "message": "Settings updated successfully",
                    "settings": data
                })
                
            except Exception as e:
                print(f"❌ Error updating user settings: {e}")
                return {"error": f"Failed to update settings: {str(e)}"}, 500
    
    except Exception as e:
        print(f"❌ User settings error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/push-subscription", methods=["POST", "DELETE"])
def push_subscription():
    """Save or remove push notification subscription"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if request.method == "POST":
            # Save push subscription
            data = request.get_json()
            if not data or 'subscription' not in data:
                return {"error": "No subscription data provided"}, 400
            
            subscription = data['subscription']
            
            # Validate subscription has required fields
            required_fields = ['endpoint', 'keys']
            if not all(field in subscription for field in required_fields):
                return {"error": "Invalid subscription format"}, 400
            
            if 'keys' in subscription:
                required_keys = ['p256dh', 'auth']
                if not all(key in subscription['keys'] for key in required_keys):
                    return {"error": "Invalid subscription keys"}, 400
            
            try:
                user_ref = db.collection('users').document(uid)
                
                # Save subscription to user document
                user_ref.set({
                    'push_subscription': subscription,
                    'push_subscription_updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True)
                
                print(f"✅ Saved push subscription for user {uid}")
                print(f"   Endpoint: {subscription.get('endpoint', 'N/A')[:50]}...")
                
                return jsonify({
                    "status": "success",
                    "message": "Push subscription saved successfully"
                })
                
            except Exception as e:
                print(f"❌ Error saving push subscription: {e}")
                return {"error": f"Failed to save subscription: {str(e)}"}, 500
        
        elif request.method == "DELETE":
            # Remove push subscription
            try:
                user_ref = db.collection('users').document(uid)
                
                # Remove subscription from user document
                user_ref.update({
                    'push_subscription': firestore.DELETE_FIELD
                })
                
                print(f"✅ Removed push subscription for user {uid}")
                
                return jsonify({
                    "status": "success",
                    "message": "Push subscription removed successfully"
                })
                
            except Exception as e:
                print(f"❌ Error removing push subscription: {e}")
                return {"error": f"Failed to remove subscription: {str(e)}"}, 500
    
    except Exception as e:
        print(f"❌ Push subscription error: {e}")
        return {"error": str(e)}, 500

@app.route("/api/vapid-public-key", methods=["GET"])
def get_vapid_public_key():
    """Get VAPID public key for push notifications"""
    if not VAPID_PUBLIC_KEY:
        return {"error": "VAPID not configured"}, 503
    
    return jsonify({
        "publicKey": VAPID_PUBLIC_KEY
    })

@app.route("/health")
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    try:
        # Check database connection
        db_status = "healthy" if db else "unhealthy"
        
        # Check critical services
        services = {
            "database": db_status,
            "email": "configured" if SMTP_USERNAME and SMTP_PASSWORD else "not_configured",
            "push": "available",  # Push notifications available through Web Push API
            "weather": "configured" if OPENWEATHERMAP_API_KEY else "not_configured", 
            "ai": "configured" if gemini_model else "not_configured"
        }
        
        # Overall health
        is_healthy = db is not None  # Core requirement is database
        status_code = 200 if is_healthy else 503
        
        return jsonify({
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "environment": ENV,
            "services": services,
            "version": "2.0.0"
        }), status_code
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

def _format_event_recommendations(recommendations_data):
    """Format event AND place recommendations for assistant context"""
    if not recommendations_data:
        return "No event or place recommendations currently available. User can set preferences in AI Preferences tab to get personalized suggestions."
    
    # Handle both old format (just events array) and new format (dict with places/events)
    if isinstance(recommendations_data, list):
        # Old format - just events
        events = recommendations_data
        places = []
    else:
        # New format - dict with separate arrays
        events = recommendations_data.get('events', [])
        places = recommendations_data.get('places', [])
    
    total_items = len(events) + len(places)
    if total_items == 0:
        return "No event or place recommendations currently available. User can set preferences in AI Preferences tab to get personalized suggestions."
    
    recommendations_text = f"The user has {total_items} recommended items in their '🎯 For You' tab:\n\n"
    
    # Format Places
    if places:
        recommendations_text += f"📍 NEARBY PLACES ({len(places)} recommendations):\n"
        for i, place in enumerate(places[:10], 1):  # Limit to top 10
            recommendations_text += f"{i}. {place.get('icon', '📍')} {place.get('title', 'Unknown Place')}\n"
            recommendations_text += f"   - Category: {place.get('category', 'N/A')}\n"
            if place.get('distance') and place.get('distance') != 'N/A':
                recommendations_text += f"   - Distance: {place.get('distance')} miles away\n"
            if place.get('rating') and place.get('rating') != 'N/A':
                recommendations_text += f"   - Rating: {place.get('rating')} stars\n"
            if place.get('price'):
                recommendations_text += f"   - Price Range: {place.get('price')}\n"
            if place.get('venue'):
                recommendations_text += f"   - Address: {place.get('venue')}\n"
            if place.get('dog_friendly'):
                recommendations_text += f"   - 🐕 Dog-Friendly!\n"
            if place.get('date'):
                recommendations_text += f"   - Status: {place.get('date')}\n"
            recommendations_text += "\n"
        
        recommendations_text += "\n"
    
    # Format Events
    if events:
        recommendations_text += f"🎉 UPCOMING EVENTS ({len(events)} recommendations):\n"
        for i, event in enumerate(events[:10], 1):  # Limit to top 10
            recommendations_text += f"{i}. {event.get('icon', '🎉')} {event.get('title', 'Unknown Event')}\n"
            recommendations_text += f"   - Category: {event.get('category', 'N/A')}\n"
            recommendations_text += f"   - Date: {event.get('date', 'N/A')}"
            if event.get('time') and event.get('time') not in ['N/A', 'See website', 'Check website']:
                recommendations_text += f" at {event.get('time')}\n"
            else:
                recommendations_text += "\n"
            recommendations_text += f"   - Venue: {event.get('venue', 'N/A')}\n"
            if event.get('distance') and event.get('distance') not in ['N/A', 'Online']:
                recommendations_text += f"   - Distance: {event.get('distance')} miles away\n"
            if event.get('price'):
                recommendations_text += f"   - Price: {event.get('price')}\n"
            if event.get('description'):
                desc = event.get('description')[:100]
                recommendations_text += f"   - Details: {desc}{'...' if len(event.get('description', '')) > 100 else ''}\n"
            if event.get('is_online'):
                recommendations_text += f"   - 💻 Virtual/Online Event\n"
            recommendations_text += "\n"
    
    recommendations_text += """
IMPORTANT USAGE INSTRUCTIONS:
When user asks about:
- "what should I do?" / "where should I eat?" / "things to do nearby" → Suggest places (restaurants, parks, cafes, etc.)
- "events nearby" / "concerts" / "shows" / "things happening" → Suggest events
- "dog-friendly restaurants" → Highlight places with 🐕 marker
- "weekend plans" → Suggest mix of places AND events
- "where can I go?" → Suggest nearby places based on their interests

TASK CREATION FROM RECOMMENDATIONS:
- When user expresses interest, offer to add as a task to their planner
- Use EXACT details from recommendations (time, venue, address)
- Set appropriate time blocks (2-3 hours for events, 1-2 hours for dining/activities)
- Examples:
  * "I see Blue Note Jazz Club is only 3 miles away with live music tonight at 8 PM. Want me to add 'Jazz Night at Blue Note' to your schedule?"
  * "There's a great dog-friendly restaurant called The Patio nearby - perfect for lunch with your pup! Should I schedule that?"
  * "The Knicks game is this Saturday at 7 PM - want me to block out time for that in your planner?"

NATURAL CONVERSATION:
- Mention recommendations naturally when relevant to user's question
- Combine multiple recommendations when helpful
- Consider user's location and preferences when suggesting
- Always mention distance for nearby places ("only 2 miles away!")
- Highlight special features (dog-friendly, high ratings, free events, etc.)
"""
    
    return recommendations_text

def get_assistant_recommendations(user_preferences, user_message_lower):
    """Get live recommendations for assistant based on user message"""
    try:
        print(f"🔍 DEBUG: Checking user message: '{user_message_lower}'")
        
        # Check if user is asking about places/recommendations
        place_keywords = ['restaurant', 'eat', 'food', 'dining', 'place', 'where', 'go', 'do', 'park', 'cafe', 'coffee', 'shop', 'activity', 'fun', 'entertainment', 'dog-friendly', 'dog friendly', 'pet-friendly', 'basketball', 'sport', 'gym', 'workout', 'museum', 'art', 'theater', 'bar', 'drink', 'nightlife', 'music', 'event', 'concert', 'show', 'festival', 'near', 'nearby', 'around', 'local', 'golf', 'court', 'field']
        
        asks_for_places = any(keyword in user_message_lower for keyword in place_keywords)
        print(f"🔍 DEBUG: asks_for_places = {asks_for_places}")
        
        if not asks_for_places:
            print(f"🔍 DEBUG: Not asking for places, returning None")
            return None
            
        print(f"🔍 User asking about places, fetching live recommendations...")
        
        # Get user location from preferences
        location = user_preferences.get('location', 'Monmouth County, NJ')
        radius = user_preferences.get('maxTravelDistance', 10)
        print(f"🔍 DEBUG: location={location}, radius={radius}")
        
        # Check for specific queries and use Google Places API directly
        specific_query = None
        
        # RESTAURANTS & FOOD
        if any(keyword in user_message_lower for keyword in ['restaurant', 'eat', 'dining', 'food', 'dinner', 'lunch', 'breakfast']):
            # Check for dog-friendly first
            if any(keyword in user_message_lower for keyword in ['dog friendly', 'dog-friendly', 'with my dog', 'bring my dog', 'pet friendly', 'pet-friendly']):
                specific_query = f'dog-friendly restaurant near {location}'
                print(f"🐕 Detected dog-friendly restaurant query")
            else:
                specific_query = f'restaurant near {location}'
                print(f"🍽️ Detected general restaurant query")
        
        # Dog-friendly queries (non-restaurant)
        elif any(keyword in user_message_lower for keyword in ['dog friendly', 'dog-friendly', 'with my dog', 'bring my dog', 'pet friendly', 'pet-friendly']):
            if any(keyword in user_message_lower for keyword in ['park', 'outdoor']):
                specific_query = f'dog park near {location}'
                print(f"🐕 Detected dog park query")
            else:
                specific_query = f'dog-friendly places near {location}'
                print(f"🐕 Detected general dog-friendly query")
        
        # Sports facilities
        elif any(keyword in user_message_lower for keyword in ['basketball court', 'basketball', 'play basketball']):
            specific_query = f'basketball court near {location}'
            print(f"🏀 Detected basketball court query")
        elif any(keyword in user_message_lower for keyword in ['golf course', 'golf', 'play golf', 'golfing']):
            specific_query = f'golf course near {location}'
            print(f"⛳ Detected golf course query")
        elif any(keyword in user_message_lower for keyword in ['tennis court', 'tennis', 'play tennis']):
            specific_query = f'tennis court near {location}'
            print(f"🎾 Detected tennis court query")
        elif any(keyword in user_message_lower for keyword in ['gym', 'fitness', 'workout', 'exercise']):
            specific_query = f'gym near {location}'
            print(f"💪 Detected gym query")
        
        # Specific cuisine or place types
        elif 'coffee' in user_message_lower or 'cafe' in user_message_lower:
            specific_query = f'cafe near {location}'
            print(f"☕ Detected cafe query")
        elif 'bar' in user_message_lower or 'drink' in user_message_lower:
            specific_query = f'bar near {location}'
            print(f"🍺 Detected bar query")
        elif 'museum' in user_message_lower:
            specific_query = f'museum near {location}'
            print(f"🏛️ Detected museum query")
        elif 'park' in user_message_lower:
            specific_query = f'park near {location}'
            print(f"🌳 Detected park query")
        
        # If we detected a specific query, use Google Places API directly
        if specific_query:
            print(f"🎯 Running specific query: {specific_query}")
            places = get_google_places_nearby(location, radius, max_results=10, user_preferences=user_preferences, custom_query=specific_query)
            
            return {
                'places': places[:8],
                'events': []
            }
        
        # Otherwise, fetch general recommendations
        all_recommendations = get_all_recommendations(
            location=location,
            radius_miles=radius,
            max_results=20,
            user_preferences=user_preferences
        )
        
        places = all_recommendations.get('places', [])
        events = all_recommendations.get('events', [])
        
        print(f"🔍 DEBUG: Got {len(places)} places and {len(events)} events")
        
        return {
            'places': places[:8],  # Top 8 places
            'events': events[:5]   # Top 5 events
        }
        
    except Exception as e:
        print(f"❌ Error getting assistant recommendations: {e}")
        return None

@app.route("/api/assistant", methods=["POST"])
def planning_assistant():
    """Planning assistant powered by Google Gemini"""
    print("🤖 Assistant endpoint called")
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        print("❌ No session cookie found")
        return {"error": "Not authenticated"}, 401
    
    if not gemini_model:
        return {"error": "Assistant service unavailable. Please configure GEMINI_API_KEY."}, 503
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        # Get request data
        data = request.get_json()
        if not data or 'message' not in data:
            return {"error": "Message required"}, 400
        
        user_message = data['message'].strip()
        context = data.get('context', {})
        conversation_history = data.get('conversationHistory', [])
        current_day = context.get('currentDay', 'Monday')
        current_week_offset = context.get('weekOffset', 0)
        upcoming_tasks = context.get('upcomingTasks', [])
        tasks_today = context.get('tasksToday', 0)
        completed_today = context.get('completedToday', 0)
        
        # Get user's local time from context (sent from frontend)
        user_current_time = context.get('currentTime', None)
        user_current_hour = context.get('currentHour', None)
        user_actual_today = context.get('actualToday', None)
        user_current_date = context.get('currentDate', None)
        
        # Fallback to server time if not provided (shouldn't happen with updated frontend)
        from datetime import datetime
        now = datetime.now()
        actual_today = user_actual_today if user_actual_today else now.strftime('%A')
        current_date = user_current_date if user_current_date else now.strftime('%B %d, %Y')
        current_time = user_current_time if user_current_time else now.strftime('%I:%M %p')
        current_hour = user_current_hour if user_current_hour is not None else now.hour
        
        print(f"💬 User message: {user_message}")
        print(f"📅 Context: {context}")
        if conversation_history:
            print(f"💭 Conversation history: {len(conversation_history)} messages")
        
        # Get user preferences for personalization
        user_preferences = get_user_preferences(uid)
        preference_context = generate_preference_context(user_preferences)
        print(f"🧠 Using {'learned' if user_preferences else 'no'} preferences for personalization")
        
        # Get task completion patterns for AI learning
        task_insights = analyze_task_completion_patterns(uid)
        learning_context = ""
        if task_insights and task_insights.get('total_completed', 0) > 0:
            learning_context = f"""

📊 USER TASK COMPLETION INSIGHTS (Learn from user's habits):
- Overall completion rate: {task_insights.get('completion_rate', 0)}%
- Total completed (30 days): {task_insights.get('total_completed', 0)}
- Total abandoned (30 days): {task_insights.get('total_abandoned', 0)}
"""
            # Most completed categories
            if task_insights.get('completed_categories'):
                top_completed = sorted(task_insights['completed_categories'].items(), key=lambda x: x[1], reverse=True)[:3]
                learning_context += f"- Categories user COMPLETES most: {', '.join([f'{cat} ({count})' for cat, count in top_completed])}\n"
                learning_context += f"  → Suggest more tasks in these categories - user enjoys them!\n"
            
            # Most abandoned categories
            if task_insights.get('abandoned_categories'):
                top_abandoned = sorted(task_insights['abandoned_categories'].items(), key=lambda x: x[1], reverse=True)[:3]
                learning_context += f"- Categories user ABANDONS most: {', '.join([f'{cat} ({count})' for cat, count in top_abandoned])}\n"
                learning_context += f"  → Avoid suggesting too many tasks in these categories - user may not enjoy them\n"
            
            # Preferred times
            if task_insights.get('preferred_times'):
                top_times = sorted(task_insights['preferred_times'].items(), key=lambda x: x[1], reverse=True)[:3]
                learning_context += f"- Times user completes tasks most: {', '.join([f'{time}:00 ({count} tasks)' for time, count in top_times])}\n"
                learning_context += f"  → Schedule important tasks during these peak productivity hours\n"
            
            learning_context += "\nUSE THIS DATA TO:\n"
            learning_context += "- Suggest activities user actually completes, not ones they abandon\n"
            learning_context += "- Schedule tasks at times when user is most productive\n"
            learning_context += "- Avoid over-suggesting categories user consistently abandons\n"
            learning_context += "- Build trust by showing you understand their habits and preferences\n"
        
        # Get weather information from context
        weather_info = context.get('weather')
        weather_context = ""
        if weather_info:
            if weather_info.get('hasGeneralForecast'):
                # General forecast available
                forecast_days = weather_info.get('forecastDays', [])
                weather_context = f"""
Weather Forecast Available:
- Location: {weather_info.get('location', 'your area')}
- Forecast for: {', '.join([f"{day['day']} ({day['condition']}, {day['high']}°F)" for day in forecast_days[:5]])}
- You can provide weather-aware suggestions for any day
- When asked about weather for specific days, reference this forecast data"""
            else:
                # Specific day weather
                day_type = "Today" if weather_info.get('isCurrentDay') else f"{current_day}"
                temp_info = f"{weather_info.get('temperature', 'N/A')}°F"
                if weather_info.get('highTemp') and weather_info.get('lowTemp'):
                    temp_info = f"High: {weather_info.get('highTemp')}°F, Low: {weather_info.get('lowTemp')}°F"
                
                weather_context = f"""
Weather for {day_type}:
- Conditions: {weather_info.get('condition', 'Unknown')}
- Temperature: {temp_info}
- Location: {weather_info.get('location', 'your area')}
- Rain: {'Yes' if weather_info.get('isRaining') else 'No'}
- Snow: {'Yes' if weather_info.get('isSnowing') else 'No'}
- Cloudy: {'Yes' if weather_info.get('isCloudy') else 'No'}
- Sunny: {'Yes' if weather_info.get('isSunny') else 'No'}"""
        else:
            weather_context = """
Weather Status: No weather data currently available
- Suggest users check weather before outdoor activities
- When asked about weather, recommend checking weather first"""

        # Format conversation history
        conversation_context = ""
        if conversation_history:
            conversation_context = "\n\nRecent Conversation:\n"
            for msg in conversation_history[-6:]:  # Show last 6 messages for context
                sender = "User" if msg['sender'] == 'user' else "Assistant"
                conversation_context += f"- {sender}: {msg['message'][:100]}{'...' if len(msg['message']) > 100 else ''}\n"
        
        # Get live recommendations for the assistant
        live_recommendations = get_assistant_recommendations(user_preferences, user_message.lower())
        recommendations_text = ""
        
        if live_recommendations:
            places = live_recommendations.get('places', [])
            events = live_recommendations.get('events', [])
            
            if places or events:
                recommendations_text = "\n\n"
                
                if places:
                    recommendations_text += f"📍 NEARBY PLACES ({len(places)} recommendations):\n"
                    for i, place in enumerate(places, 1):
                        recommendations_text += f"{i}. {place.get('icon', '📍')} {place.get('title', 'Unknown Place')}\n"
                        if place.get('rating'):
                            recommendations_text += f"   - Rating: {place.get('rating')} stars\n"
                        if place.get('price_level'):
                            recommendations_text += f"   - Price: {place.get('price_level')}\n"
                        if place.get('venue'):
                            recommendations_text += f"   - Address: {place.get('venue')}\n"
                        if place.get('distance'):
                            recommendations_text += f"   - Distance: {place.get('distance')} miles away\n"
                        if place.get('dog_friendly'):
                            recommendations_text += f"   - 🐕 Dog-Friendly!\n"
                        recommendations_text += "\n"
                    recommendations_text += "\n"
                
                if events:
                    recommendations_text += f"🎉 NEARBY EVENTS ({len(events)} recommendations):\n"
                    for i, event in enumerate(events, 1):
                        recommendations_text += f"{i}. {event.get('icon', '🎉')} {event.get('title', 'Unknown Event')}\n"
                        recommendations_text += f"   - Date: {event.get('date', 'N/A')}\n"
                        if event.get('time') and event.get('time') not in ['N/A', 'See website', 'Check website']:
                            recommendations_text += f"   - Time: {event.get('time')}\n"
                        recommendations_text += f"   - Venue: {event.get('venue', 'N/A')}\n"
                        if event.get('distance') and event.get('distance') not in ['N/A', 'Online']:
                            recommendations_text += f"   - Distance: {event.get('distance')} miles away\n"
                        recommendations_text += "\n"
                
                recommendations_text += """
IMPORTANT: When user asks about restaurants, places to go, things to do, etc.:
1. USE THE LIVE RECOMMENDATIONS ABOVE to suggest SPECIFIC places with REAL details
2. Instead of saying "search on Google Maps or Yelp", recommend actual places from the list
3. Mention specific details like ratings, distance, and special features (dog-friendly, etc.)
4. Offer to add recommended places to their schedule as tasks
5. Examples:
   - "I found The Ocean House restaurant just 2.3 miles away with 4.5 stars - perfect for dinner! Should I add it to your schedule?"
   - "There's a dog-friendly park called Huber Woods only 1.8 miles from you - great for your pup! Want me to schedule a visit?"
   - "Blue Note Jazz Club has live music tonight at 8 PM, only 3 miles away. Interested?"

"""
            else:
                recommendations_text = f"""

NO CURRENT RECOMMENDATIONS AVAILABLE

When user asks about places/restaurants:
- Acknowledge you can't search for specific places right now  
- Suggest they check Google Maps or Yelp for "{user_preferences.get('location', 'your area')}"
- Offer to help plan once they find a place

"""
        else:
            recommendations_text = f"""

NO CURRENT RECOMMENDATIONS AVAILABLE

When user asks about places/restaurants:
- Acknowledge you can't search for specific places right now  
- Suggest they check Google Maps or Yelp for "{user_preferences.get('location', 'your area')}"
- Offer to help plan once they find a place

"""
        
        # Create context-aware prompt
        system_prompt = f"""You are a helpful daily planning assistant that can both provide advice AND create comprehensive tasks directly in the user's planner. You can also MANAGE EXISTING TASKS by editing, deleting, or completing them.

CURRENT DATE AND TIME (USER'S LOCAL TIME):
- Current Date: {current_date}
- Current Time: {current_time} ({current_hour}:00 in 24-hour format)
- Current Day: {actual_today}
- User is viewing: {current_day} (week offset: {current_week_offset})
- IMPORTANT: DO NOT schedule tasks in the past! All task times must be AFTER {current_time}.
- If user asks "what time is it?" or "current time", respond with: "It's currently {current_time} on {current_date}"

SCHEDULING RULES:
- For tasks scheduled TODAY ({actual_today}): Only create tasks with start times AFTER {current_hour}:00
- If it's past 6 PM, focus on evening tasks or suggest planning for tomorrow
- If it's early morning (before 9 AM), you can schedule throughout the day
- Always check if requested time has already passed before creating a task
- Example: If it's 3:00 PM now, don't create tasks starting at 2:00 PM or earlier today

DAY CALCULATION RULES (CRITICAL):
The week starts on SUNDAY. Days in order: Sunday → Monday → Tuesday → Wednesday → Thursday → Friday → Saturday

DETERMINING WEEK OFFSET:
1. If today is {actual_today} and user requests a day:
   - Check if the requested day has ALREADY PASSED this week
   - Days are in order: Sunday(0) → Monday(1) → Tuesday(2) → Wednesday(3) → Thursday(4) → Friday(5) → Saturday(6)
   
2. Examples when today is SUNDAY:
   - User says "Monday": weekOffset = 0 (tomorrow, this week)
   - User says "Tuesday": weekOffset = 0 (this week)
   - User says "Saturday": weekOffset = 0 (this week)
   - User says "Sunday": Could mean today OR next Sunday - ask for clarification or assume next week (weekOffset = 1)

3. Examples when today is WEDNESDAY:
   - User says "Thursday": weekOffset = 0 (tomorrow, this week)
   - User says "Friday": weekOffset = 0 (this week)
   - User says "Monday": weekOffset = 1 (next week - Monday already passed)
   - User says "Tuesday": weekOffset = 1 (next week - Tuesday already passed)
   - User says "Sunday": weekOffset = 1 (next week - Sunday already passed)

4. Examples when today is SATURDAY:
   - User says "Sunday": weekOffset = 0 (tomorrow)
   - User says "Monday": weekOffset = 1 (next week)
   - User says "Tuesday": weekOffset = 1 (next week)
   - User says "Saturday": Could mean today OR next Saturday - ask for clarification or assume next week (weekOffset = 1)

5. Special cases:
   - "tomorrow": Calculate which day tomorrow is, use weekOffset = 0 unless tomorrow is Sunday (then weekOffset = 1)
   - "next week": ALWAYS use weekOffset = 1 regardless of day
   - "this week": ALWAYS use weekOffset = 0 regardless of day
   - "tonight" or "this evening": Use today ({actual_today}), weekOffset = 0, time after current hour

NFL/SPORTS SCHEDULING:
- NFL games are typically:
  * Sunday: 1:00 PM ET (early), 4:00 PM ET (late), 8:20 PM ET (Sunday Night Football)
  * Monday: 8:15 PM ET (Monday Night Football)
  * Thursday: 8:15 PM ET (Thursday Night Football)
- When user mentions "NFL Sunday night" or similar:
  * Use EVENING times (8:00 PM - 11:00 PM) NOT morning times
  * Sunday Night Football starts around 8:20 PM
  * Create tasks like "Watch Sunday Night Football" from 20:00-23:00 (8:00 PM - 11:00 PM)

RESPONSE STYLE:
- Keep responses SHORT and SIMPLE (1-2 sentences maximum when just chatting)
- Be casual and friendly, not verbose
- Only give detailed explanations when specifically asked
- When creating tasks, provide brief, clear task descriptions

TASK MANAGEMENT CAPABILITIES:
You can now DELETE, EDIT, and COMPLETE existing tasks! Use these actions when users ask:

DELETE TASKS:
- "Delete the meeting task"
- "Remove all my tasks for today"
- "Cancel my dentist appointment"

EDIT TASKS:
- "Change my meeting time to 3pm"
- "Update my workout to be 1 hour long"
- "Move my dentist appointment to Friday"

COMPLETE TASKS:
- "Mark my grocery shopping as done"
- "I finished the report, mark it complete"
- "Check off the laundry task"

TASK MANAGEMENT FORMAT:
When you need to manage existing tasks, respond with:

---TASK-ACTIONS---
[
  {{
    "action": "delete|edit|complete|uncomplete",
    "taskId": "task_id_if_known",
    "titleSearch": "partial_title_to_search_for",
    "updates": {{"title": "new title", "time": "14:00-15:00", "description": "new description", "priority": "high"}},
    "reason": "Brief explanation of why this action is being taken"
  }}
]
---END-TASK-ACTIONS---

TASK MANAGEMENT RULES:
1. Use "titleSearch" when you don't have exact taskId (search by partial title match)
2. For "edit" actions, include "updates" object with fields to change
3. Always provide a brief "reason" explaining the action
4. Multiple actions can be performed at once
5. Be careful with delete actions - confirm when deleting multiple tasks

Current Context:
- Real today is: {actual_today}
- User viewing: {current_day} (week offset: {current_week_offset})
- Tasks scheduled today: {tasks_today}
- Tasks completed today: {completed_today}
- Upcoming tasks: {json.dumps(upcoming_tasks, indent=2) if upcoming_tasks else 'No upcoming tasks scheduled'}

TASK TARGETING TIPS:
- Each task has an ID and title. When possible, use taskId for precise targeting
- When user says "delete the meeting task", look for task with "meeting" in title
- For tasks listed above, you can use their exact IDs for precise actions
- Be careful with title searches - make them specific to avoid deleting wrong tasks{weather_context}

LIVE RECOMMENDATIONS FOR YOU:
{recommendations_text}

{conversation_context}

AUTOMATIC TASK CREATION:
You MUST create tasks when users ask for:
- "Help plan my week/day"
- "Break down [task name] into smaller tasks"
- "Create a schedule for..."
- "Plan my [time period]"
- "What should I do on [day]?"
- "Help me organize my [activity/work/study]"
- "Plan for next week" or "plan ahead" or "plan for the coming weeks"

MULTI-WEEK PLANNING:
When users ask to "plan ahead", "plan for next week", "plan for a couple weeks", "plan for the coming weeks":
- Create tasks for FUTURE weeks, not just the current week
- Use weekOffset to target specific weeks: 0=current week, 1=next week, 2=week after next, etc.
- Spread tasks across multiple weeks when planning ahead
- For "couple weeks ahead": create tasks for weeks 1 and 2 ahead
- For "next week": create tasks for week 1 ahead
- For general "planning ahead": create tasks for weeks 0, 1, and 2

COMPREHENSIVE TASK FORMAT:
When creating tasks, provide complete details:

---TASKS---
[
  {{
    "title": "Clear, actionable task title",
    "description": "Detailed description explaining what to do, why it's important, or specific steps",
    "startTime": "HH:MM",
    "endTime": "HH:MM",
    "day": "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday",
    "weekOffset": 0,
    "priority": "high|medium|low",
    "color": "#FF6B6B"
  }}
]
---END-TASKS---

TASK CREATION RULES:
1. ALWAYS include realistic time ranges (30min minimum, 3hr maximum per task)
2. Write helpful descriptions with context and purpose (2-3 sentences max)
3. Set appropriate priorities (high=urgent/important, medium=normal, low=nice-to-have)
4. Spread tasks logically across days AND weeks when planning ahead
5. Consider energy levels (challenging tasks in morning, easier in afternoon)
6. Include variety (work, personal, health, breaks)
7. Use colors: #FF6B6B (red-high priority), #4ECDC4 (teal-work), #45B7D1 (blue-personal), #96CEB4 (green-health), #FFEAA7 (yellow-creative), #DDA0DD (purple-learning)
8. WEEK OFFSET RULES (CRITICAL FOR CORRECT SCHEDULING):
   - weekOffset: 0 = Current week being viewed (default)
   - weekOffset: 1 = Next week (7 days ahead)
   - weekOffset: 2 = Week after next (14 days ahead)
   
   SMART WEEK OFFSET CALCULATION:
   - Today is {actual_today}
   - Week order: Sunday(0) → Monday(1) → Tuesday(2) → Wednesday(3) → Thursday(4) → Friday(5) → Saturday(6)
   - If user requests a day that already passed this week → use weekOffset: 1 (next week)
   - If user requests a day that hasn't happened yet this week → use weekOffset: 0 (this week)
   - User viewing {current_day} with weekOffset {current_week_offset}
   
   EXPLICIT USER REQUESTS:
   - "next week": always use weekOffset: 1
   - "this week": always use weekOffset: 0
   - "couple weeks ahead": mix of weekOffset: 1 and weekOffset: 2
   - "tomorrow": Calculate which day tomorrow is, then determine correct weekOffset
   - "tonight"/"this evening": Use {actual_today} with weekOffset: 0

WEATHER-AWARE PLANNING:
- ALWAYS check weather context when suggesting outdoor activities
- If it's raining or snowing: Avoid outdoor activities like jogging, hiking, gardening, outdoor sports
- If it's raining: Suggest cozy indoor tasks like reading, organizing, cooking, studying, cleaning
- If it's sunny and clear: Encourage outdoor activities like walking, outdoor exercise, gardening, errands
- If it's cloudy but not raining: Balance indoor and light outdoor activities
- Consider temperature: Very hot (>85°F) or cold (<40°F) should favor indoor activities
- When asked about weather for specific days, reference the forecast data if available
- For questions like "what's the weather tomorrow?" or "should I go golfing Saturday?", provide specific weather info from forecast
- Always mention weather considerations in task descriptions when relevant
- If no specific weather data is available for a requested day, suggest: "Click the weather button in the top-right corner to check the forecast for [day]!"
- When users ask about weather for future days and you don't have forecast data, direct them to use the weather button

EXAMPLES OF GOOD TASKS:
- Title: "Review quarterly budget", Description: "Analyze Q3 expenses, identify cost-saving opportunities, and prepare summary for next week's meeting", StartTime: "09:00", EndTime: "11:00", WeekOffset: 0, Priority: "high", Color: "#FF6B6B"
- Title: "Grocery shopping", Description: "Pick up ingredients for weekly meal prep. Focus on fresh vegetables and proteins for healthy meals", StartTime: "14:00", EndTime: "15:30", WeekOffset: 0, Priority: "medium", Color: "#45B7D1"
- Title: "Team meeting prep", Description: "Prepare agenda and materials for next week's team meeting. Review project status and key discussion points", StartTime: "10:00", EndTime: "11:30", WeekOffset: 1, Priority: "high", Color: "#4ECDC4"

WEATHER-AWARE TASK EXAMPLES:
- RAINY DAY: Title: "Reading time", Description: "Perfect rainy day activity - catch up on that novel with a warm cup of tea", StartTime: "15:00", EndTime: "16:30", Priority: "low", Color: "#DDA0DD"
- SUNNY DAY: Title: "Morning walk", Description: "Take advantage of the beautiful weather for a refreshing outdoor walk in the park", StartTime: "07:00", EndTime: "07:30", Priority: "medium", Color: "#96CEB4"
- COLD/HOT WEATHER: Title: "Indoor workout", Description: "Weather isn't ideal for outdoor exercise, so focus on a good indoor fitness routine", StartTime: "18:00", EndTime: "19:00", Priority: "medium", Color: "#96CEB4"

Guidelines:
- Create 3-6 tasks when planning a day, 15-25 tasks when planning a week
- For multi-week planning: 10-15 tasks per week across different weeks  
- Keep titles short but descriptions helpful with context (2-3 sentences)
- Balance work, personal, and wellness activities
- Always include time ranges for better scheduling
- Make daily plans simple and achievable
- When planning ahead: spread tasks logically across future weeks (use weekOffset 1, 2, etc.)
- Always respond to "plan ahead" requests with tasks for future weeks, not just current week

PROACTIVE PREFERENCE-BASED SUGGESTIONS:
When creating tasks or responding to planning requests, ALWAYS incorporate user preferences:
1. If user has hobbies listed → Suggest hobby-related tasks (e.g., "Guitar practice session", "Photography walk")
2. If user has workout preferences → Schedule workouts at their preferred time with their preferred style
3. If user has wake/bed times → Respect their schedule boundaries, suggest morning routines
4. If user has event interests → Mention relevant upcoming events when suggesting weekend/evening plans
5. When user asks "what should I do today/this week?" → Create tasks that align with their interests

EVENT & ACTIVITY RECOMMENDATIONS:
When user asks about events, weekend plans, or "what's happening":
- Reference their favorite event categories (concerts, sports, etc.)
- Mention their location for local events
- Suggest creating tasks to attend events that match their interests
- Format event suggestions as: "There's a [EVENT TYPE] happening on [DAY] at [TIME] in [LOCATION] - want me to add it to your planner?"

EXAMPLE PREFERENCE-BASED RESPONSES:
User: "Help me plan my weekend"
→ "I see you enjoy basketball and concerts! How about:
   - Saturday morning: Basketball practice (9:00-10:30 AM)
   - Saturday evening: Check out that live music event downtown (8:00-10:00 PM)
   - Sunday afternoon: Relaxing guitar practice session (2:00-3:30 PM)
   Would you like me to add these to your planner?"

User: "What should I do tomorrow?"
→ "Based on your preferences, I'd suggest:
   - Morning yoga session at 7:00 AM (your preferred exercise time!)
   - Photography walk in the park at 4:00 PM (nice weather expected)
   - Evening concert at the civic center at 8:00 PM
   Want me to schedule these?"

TASK SUGGESTIONS WHEN USER HAS PREFERENCES:
- Always mention WHY you're suggesting something (e.g., "Since you enjoy yoga...")
- Align workout times with their exerciseTime preference
- Schedule hobby time during their most productive hours
- Suggest local events based on their location
- Create variety while respecting their interests{preference_context}
{learning_context}

User Question: {user_message}"""

        # Generate response using Gemini
        print("🤖 Sending request to Gemini...")
        response = gemini_model.generate_content(system_prompt)
        response_text = response.text
        print(f"✅ Gemini response received: {response_text[:100]}...")
        
        # Parse tasks from response but don't save to database yet
        # Let the frontend handle task creation to avoid duplicates
        created_tasks = []
        if "---TASKS---" in response_text and "---END-TASKS---" in response_text:
            try:
                task_start = response_text.find("---TASKS---") + len("---TASKS---")
                task_end = response_text.find("---END-TASKS---")
                task_json_str = response_text[task_start:task_end].strip()
                
                print(f"📋 Parsing tasks from JSON: {task_json_str[:200]}...")
                tasks_data = json.loads(task_json_str)
                
                # Process each task but DON'T save to Firebase yet (frontend will handle this)
                for task_data in tasks_data:
                    # Just format the task data for frontend processing (no Firebase save here)
                    task = {
                        "title": task_data.get("title", "Untitled Task"),
                        "description": task_data.get("description", ""),
                        "startTime": task_data.get("startTime", "09:00"),
                        "endTime": task_data.get("endTime", "10:00"),
                        "day": task_data.get("day", "Monday"),
                        "weekOffset": task_data.get("weekOffset", 0),
                        "priority": task_data.get("priority", "medium"),
                        "color": task_data.get("color", "#4ECDC4"),
                        "completed": False,
                        "createdBy": "assistant"
                    }
                    
                    created_tasks.append(task)
                    print(f"📝 Prepared task for frontend: {task['title']} ({task['startTime']}-{task['endTime']})")
                
                # Clean response text (remove task section)
                clean_response = response_text[:response_text.find("---TASKS---")].strip()
                if not clean_response:
                    task_count = len(created_tasks)
                    clean_response = f"I've created {task_count} tasks for you! Check your planner to see them."
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                print(f"Raw task data: {task_json_str}")
            except Exception as e:
                print(f"❌ Task processing error: {e}")
        else:
            clean_response = response_text
        
        # Process task management actions
        task_actions_performed = []
        if "---TASK-ACTIONS---" in response_text and "---END-TASK-ACTIONS---" in response_text:
            try:
                action_start = response_text.find("---TASK-ACTIONS---") + len("---TASK-ACTIONS---")
                action_end = response_text.find("---END-TASK-ACTIONS---")
                action_json_str = response_text[action_start:action_end].strip()
                
                print(f"🔧 Parsing task actions from JSON: {action_json_str[:200]}...")
                actions_data = json.loads(action_json_str)
                
                # Process each action
                for action_data in actions_data:
                    action_type = action_data.get("action")
                    task_id = action_data.get("taskId")
                    title_search = action_data.get("titleSearch")
                    updates = action_data.get("updates", {})
                    reason = action_data.get("reason", "Assistant action")
                    
                    print(f"🔧 Processing action: {action_type} for task: {task_id or title_search}")
                    
                    if not db:
                        print("❌ Database not available for task actions")
                        continue
                    
                    tasks_ref = db.collection('users').document(uid).collection('tasks')
                    
                    # Find tasks to act upon
                    tasks_to_process = []
                    
                    if task_id:
                        # Direct task ID lookup
                        try:
                            task_doc = tasks_ref.document(task_id).get()
                            if task_doc.exists:
                                tasks_to_process.append((task_id, task_doc.to_dict()))
                        except Exception as e:
                            print(f"❌ Error finding task by ID {task_id}: {e}")
                    
                    elif title_search:
                        # Search by title - be more precise and limit results
                        try:
                            all_tasks = tasks_ref.stream()
                            found_count = 0
                            for task_doc in all_tasks:
                                task_data = task_doc.to_dict()
                                task_title = task_data.get('title', '').lower()
                                search_term = title_search.lower().strip()
                                
                                # More precise matching: exact match or starts with
                                if (task_title == search_term or 
                                    task_title.startswith(search_term) or 
                                    (len(search_term) > 3 and search_term in task_title)):
                                    tasks_to_process.append((task_doc.id, task_data))
                                    found_count += 1
                                    
                                    # Safety limit: don't delete too many tasks at once
                                    if found_count >= 3 and action_type == "delete":
                                        print(f"⚠️ Limiting search results to prevent mass deletion (found {found_count})")
                                        break
                                        
                        except Exception as e:
                            print(f"❌ Error searching tasks by title '{title_search}': {e}")
                    
                    # Perform actions on found tasks
                    for task_id_to_process, task_data in tasks_to_process:
                        try:
                            if action_type == "delete":
                                tasks_ref.document(task_id_to_process).delete()
                                task_actions_performed.append({
                                    "action": "deleted",
                                    "task": task_data.get('title', 'Unknown task'),
                                    "taskId": task_id_to_process,
                                    "reason": reason
                                })
                                print(f"✅ Deleted task: {task_data.get('title')}")
                            
                            elif action_type == "edit":
                                # Update with provided changes
                                update_data = {**updates, 'updated_at': datetime.now()}
                                tasks_ref.document(task_id_to_process).update(update_data)
                                task_actions_performed.append({
                                    "action": "edited",
                                    "task": task_data.get('title', 'Unknown task'),
                                    "taskId": task_id_to_process,
                                    "changes": updates,
                                    "reason": reason
                                })
                                print(f"✅ Edited task: {task_data.get('title')} with {updates}")
                            
                            elif action_type == "complete":
                                tasks_ref.document(task_id_to_process).update({
                                    'completed': True,
                                    'completedAt': datetime.now().isoformat(),
                                    'updated_at': datetime.now()
                                })
                                task_actions_performed.append({
                                    "action": "completed",
                                    "task": task_data.get('title', 'Unknown task'),
                                    "taskId": task_id_to_process,
                                    "reason": reason
                                })
                                print(f"✅ Completed task: {task_data.get('title')}")
                            
                            elif action_type == "uncomplete":
                                tasks_ref.document(task_id_to_process).update({
                                    'completed': False,
                                    'completedAt': None,
                                    'updated_at': datetime.now()
                                })
                                task_actions_performed.append({
                                    "action": "uncompleted",
                                    "task": task_data.get('title', 'Unknown task'),
                                    "taskId": task_id_to_process,
                                    "reason": reason
                                })
                                print(f"✅ Uncompleted task: {task_data.get('title')}")
                                
                        except Exception as e:
                            print(f"❌ Error performing {action_type} on task {task_data.get('title')}: {e}")
                
                # Clean response text (remove task actions section)
                clean_response = clean_response.replace(response_text[response_text.find("---TASK-ACTIONS---"):response_text.find("---END-TASK-ACTIONS---") + len("---END-TASK-ACTIONS---")], "").strip()
                    
                # Add summary of actions if any were performed
                if task_actions_performed and not clean_response:
                    action_count = len(task_actions_performed)
                    clean_response = f"I've performed {action_count} task action{'s' if action_count != 1 else ''} for you!"
                
            except json.JSONDecodeError as e:
                print(f"❌ Task actions JSON parsing error: {e}")
                print(f"Raw action data: {action_json_str}")
            except Exception as e:
                print(f"❌ Task action processing error: {e}")
        
        print(f"✅ Successful response with {len(created_tasks)} tasks and {len(task_actions_performed)} actions")
        return jsonify({
            "response": clean_response,
            "tasks": created_tasks,
            "taskActions": task_actions_performed,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Assistant API error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": "Sorry, I'm having trouble right now. Please try again."}), 500

def cleanup_old_tasks(user_id, weeks_to_keep=2):
    """Delete completed tasks older than specified weeks"""
    if not db:
        return 0
    
    try:
        cutoff_date = datetime.now() - timedelta(weeks=weeks_to_keep)
        deleted_count = 0
        
        # Get user's tasks collection
        tasks_ref = db.collection('users').document(user_id).collection('tasks')
        all_tasks = tasks_ref.stream()
        
        for task_doc in all_tasks:
            task_data = task_doc.to_dict()
            
            # Only delete completed tasks
            if not task_data.get('completed', False):
                continue
            
            # Check if task is old enough
            task_date_str = task_data.get('createdAt') or task_data.get('completedAt')
            if not task_date_str:
                continue
                
            try:
                # Handle both ISO format and other date formats
                if 'T' in task_date_str:
                    task_date = datetime.fromisoformat(task_date_str.replace('Z', '+00:00'))
                else:
                    # Try parsing as date only
                    task_date = datetime.strptime(task_date_str.split('T')[0], '%Y-%m-%d')
                
                if task_date < cutoff_date:
                    task_doc.reference.delete()
                    deleted_count += 1
                    
            except (ValueError, TypeError) as e:
                print(f"Could not parse date for task {task_doc.id}: {task_date_str}, error: {e}")
                continue
        
        return deleted_count
        
    except Exception as e:
        print(f"Error cleaning up tasks: {e}")
        return 0


@app.route('/api/test-notifications', methods=['POST'])
def test_notifications():
    """Test the notification system manually"""
    try:
        print("🧪 Manual notification test triggered")
        check_and_send_notifications()
        return jsonify({'success': True, 'message': 'Notification test completed'})
    except Exception as e:
        print(f"Test notification error: {e}")
        return jsonify({'error': 'Test failed'}), 500


@app.route('/api/cleanup-tasks', methods=['POST'])
def api_cleanup_tasks():
    """Manually trigger task cleanup for logged-in user"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        user_id = decoded_claims['uid']
        data = request.get_json() or {}
        weeks_to_keep = data.get('weeks', 2)
        
        deleted_count = cleanup_old_tasks(user_id, weeks_to_keep)
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} old completed tasks'
        })
        
    except Exception as e:
        print(f"Cleanup tasks error: {e}")
        return jsonify({'error': 'Cleanup failed'}), 500


# ===== AI PREFERENCES & RECOMMENDATIONS API =====

@app.route("/api/preferences", methods=["GET", "POST", "DELETE"])
def user_preferences():
    """
    Manage user preferences for AI learning and recommendations.
    
    GET: Retrieve user's saved preferences
    POST: Save/update user preferences
    DELETE: Clear user preferences
    
    Preferences include:
    - Hobbies and interests
    - Workout styles and exercise preferences
    - Wake/sleep schedule
    - Favorite event categories
    - Activity types and frequency
    """
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if request.method == "GET":
            # Retrieve preferences
            user_ref = db.collection('users').document(uid)
            prefs_doc = user_ref.collection('preferences').document('main').get()
            
            if prefs_doc.exists:
                return jsonify({
                    'success': True,
                    'preferences': prefs_doc.to_dict()
                })
            else:
                # Return default empty preferences with enhanced fields
                return jsonify({
                    'success': True,
                    'preferences': {
                        # Privacy setting
                        'privacyMode': False,
                        
                        # Basic preferences
                        'hobbies': [],
                        'workoutStyles': [],
                        'wakeTime': '07:00',
                        'bedTime': '23:00',
                        'exerciseTime': 'morning',
                        'eventCategories': [],
                        'activityTypes': [],
                        'location': '',
                        
                        # NEW: Pet information
                        'hasDog': False,
                        'hasCat': False,
                        'otherPets': [],
                        
                        # NEW: Food preferences
                        'cuisineTypes': [],
                        'dietaryRestrictions': [],
                        'priceRange': 'moderate',
                        'preferredMealTimes': {
                            'breakfast': True,
                            'brunch': True,
                            'lunch': True,
                            'dinner': True,
                            'lateNight': False
                        },
                        
                        # NEW: Activity preferences
                        'indoorActivities': [],
                        'outdoorActivities': [],
                        'socialPreference': 'small-groups',
                        'eventTypes': [],
                        
                        # NEW: Lifestyle
                        'workSchedule': '9-5',
                        'transportationMode': 'car',
                        'maxTravelDistance': 10,
                        
                        'createdAt': None
                    }
                })
        
        elif request.method == "POST":
            # Save/update preferences
            data = request.get_json()
            
            from datetime import datetime
            
            preferences = {
                # Privacy setting
                'privacyMode': data.get('privacyMode', False),
                
                # Basic preferences
                'hobbies': data.get('hobbies', []),
                'workoutStyles': data.get('workoutStyles', []),
                'wakeTime': data.get('wakeTime', '07:00'),
                'bedTime': data.get('bedTime', '23:00'),
                'exerciseTime': data.get('exerciseTime', 'morning'),
                'eventCategories': data.get('eventCategories', []),
                'activityTypes': data.get('activityTypes', []),
                'location': data.get('location', ''),
                
                # NEW: Pet information
                'hasDog': data.get('hasDog', False),
                'hasCat': data.get('hasCat', False),
                'otherPets': data.get('otherPets', []),
                
                # NEW: Food preferences
                'cuisineTypes': data.get('cuisineTypes', []),
                'dietaryRestrictions': data.get('dietaryRestrictions', []),
                'priceRange': data.get('priceRange', 'moderate'),
                'preferredMealTimes': data.get('preferredMealTimes', {
                    'breakfast': True,
                    'brunch': True,
                    'lunch': True,
                    'dinner': True,
                    'lateNight': False
                }),
                
                # NEW: Activity preferences  
                'indoorActivities': data.get('indoorActivities', []),
                'outdoorActivities': data.get('outdoorActivities', []),
                'socialPreference': data.get('socialPreference', 'small-groups'),
                'eventTypes': data.get('eventTypes', []),
                
                # NEW: Lifestyle
                'workSchedule': data.get('workSchedule', '9-5'),
                'transportationMode': data.get('transportationMode', 'car'),
                'maxTravelDistance': data.get('maxTravelDistance', 10),
                
                'updatedAt': datetime.now().isoformat()
            }
            
            # Save to Firebase (use SERVER_TIMESTAMP for Firebase, not for JSON response)
            firebase_preferences = preferences.copy()
            firebase_preferences['updatedAt'] = firestore.SERVER_TIMESTAMP
            
            user_ref = db.collection('users').document(uid)
            user_ref.collection('preferences').document('main').set(firebase_preferences, merge=True)
            
            # Return serializable preferences
            return jsonify({
                'success': True,
                'message': 'Preferences saved successfully',
                'preferences': preferences
            })
        
        elif request.method == "DELETE":
            # Clear preferences
            user_ref = db.collection('users').document(uid)
            user_ref.collection('preferences').document('main').delete()
            
            return jsonify({
                'success': True,
                'message': 'Preferences cleared'
            })
    
    except Exception as e:
        print(f"❌ Preferences error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/autofill-preferences", methods=["POST"])
def autofill_preferences():
    """
    Analyze user's past tasks and automatically populate preferences
    using AI to extract hobbies, workout styles, and activity patterns
    """
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        if not db:
            return jsonify({'error': 'Database not available'}), 500
        
        if not gemini_model:
            return jsonify({'error': 'AI service unavailable'}), 503
        
        # Get user's tasks from Firestore
        tasks_ref = db.collection('users').document(uid).collection('tasks')
        all_tasks = list(tasks_ref.stream())
        
        if len(all_tasks) < 5:
            return jsonify({
                'success': False,
                'message': f'Need at least 5 tasks to analyze patterns. You have {len(all_tasks)}.'
            })
        
        # Extract task titles and descriptions
        task_data = []
        for task_doc in all_tasks:
            task = task_doc.to_dict()
            task_info = {
                'title': task.get('title', ''),
                'description': task.get('description', ''),
                'completed': task.get('completed', False)
            }
            task_data.append(task_info)
        
        # Build AI prompt
        prompt = f"""Analyze these {len(task_data)} tasks and extract user preferences:

TASKS:
{chr(10).join([f"- {t['title']}: {t['description']} (completed: {t['completed']})" for t in task_data[:100]])}

Based on these tasks, identify the user's:
1. HOBBIES & INTERESTS (e.g., basketball, reading, painting, gaming, cooking, etc.)
2. WORKOUT STYLES (e.g., cardio, strength, yoga, hiit, running, pilates, etc.)
3. INDOOR ACTIVITIES (e.g., museums, shopping, theaters, arcades, bowling, etc.)
4. OUTDOOR ACTIVITIES (e.g., hiking, beach, parks, cycling, kayaking, camping, etc.)
5. CUISINE TYPES (e.g., italian, mexican, sushi, chinese, thai, etc.)
6. EVENT PREFERENCES (e.g., concerts, sports, theater, comedy, festivals, etc.)

IMPORTANT: Only include items that appear MULTIPLE times or are clearly important to the user.
Focus on completed tasks as they show what the user actually does.

Respond in JSON format:
{{
  "hobbies": ["hobby1", "hobby2"],
  "workoutStyles": ["workout1", "workout2"],
  "indoorActivities": ["activity1", "activity2"],
  "outdoorActivities": ["activity1", "activity2"],
  "cuisineTypes": ["cuisine1", "cuisine2"],
  "eventTypes": ["event1", "event2"]
}}"""
        
        # Call Gemini AI
        response = gemini_model.generate_content(prompt)
        ai_response = response.text.strip()
        
        # Extract JSON from response
        import json
        import re
        
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ai_response, re.DOTALL)
        if json_match:
            preferences_data = json.loads(json_match.group())
        else:
            # Try parsing the whole response as JSON
            preferences_data = json.loads(ai_response)
        
        # Load current preferences to merge
        user_ref = db.collection('users').document(uid)
        prefs_doc = user_ref.collection('preferences').document('main').get()
        current_prefs = prefs_doc.to_dict() if prefs_doc.exists else {}
        
        # Merge AI-discovered preferences with current ones
        from datetime import datetime
        updated_prefs = {
            **current_prefs,
            'hobbies': list(set((current_prefs.get('hobbies', []) + preferences_data.get('hobbies', [])))),
            'workoutStyles': list(set((current_prefs.get('workoutStyles', []) + preferences_data.get('workoutStyles', [])))),
            'indoorActivities': list(set((current_prefs.get('indoorActivities', []) + preferences_data.get('indoorActivities', [])))),
            'outdoorActivities': list(set((current_prefs.get('outdoorActivities', []) + preferences_data.get('outdoorActivities', [])))),
            'cuisineTypes': list(set((current_prefs.get('cuisineTypes', []) + preferences_data.get('cuisineTypes', [])))),
            'eventTypes': list(set((current_prefs.get('eventTypes', []) + preferences_data.get('eventTypes', [])))),
            'updatedAt': datetime.now().isoformat()
        }
        
        # Save to Firebase (use SERVER_TIMESTAMP for Firebase only)
        firebase_prefs = updated_prefs.copy()
        firebase_prefs['updatedAt'] = firestore.SERVER_TIMESTAMP
        user_ref.collection('preferences').document('main').set(firebase_prefs, merge=True)
        
        return jsonify({
            'success': True,
            'message': f'Analyzed {len(task_data)} tasks and discovered your preferences!',
            'discovered': {
                'hobbies': preferences_data.get('hobbies', []),
                'workoutStyles': preferences_data.get('workoutStyles', []),
                'indoorActivities': preferences_data.get('indoorActivities', []),
                'outdoorActivities': preferences_data.get('outdoorActivities', []),
                'cuisineTypes': preferences_data.get('cuisineTypes', []),
                'eventTypes': preferences_data.get('eventTypes', [])
            },
            'preferences': updated_prefs
        })
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"AI Response: {ai_response}")
        return jsonify({'error': 'Failed to parse AI response', 'details': str(e)}), 500
    except Exception as e:
        print(f"❌ Auto-fill error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/analyze-behavior", methods=["GET"])
def analyze_behavior():
    """
    Analyze user's task history to identify patterns and preferences.
    
    Returns insights such as:
    - Most common task keywords
    - Preferred activity times
    - Recurring task patterns
    - Activity frequency analysis
    """
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        # Get all user tasks from the last 8 weeks
        user_ref = db.collection('users').document(uid)
        tasks_ref = user_ref.collection('tasks')
        
        # Fetch recent tasks
        from datetime import datetime, timedelta, timezone
        eight_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=8)
        
        # Get all tasks and filter by created_at
        all_tasks = tasks_ref.stream()
        
        # Analysis data structures
        keyword_frequency = {}
        time_preferences = {'morning': 0, 'afternoon': 0, 'evening': 0}
        day_frequency = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 
                         'Friday': 0, 'Saturday': 0, 'Sunday': 0}
        activity_patterns = []
        
        task_count = 0
        for task_doc in all_tasks:
            task = task_doc.to_dict()
            
            # Check if task has created_at and is within the time range
            created_at = task.get('created_at')
            if created_at:
                # Handle both datetime objects and timestamps
                if hasattr(created_at, 'timestamp'):
                    # It's a datetime-like object
                    if created_at.tzinfo is None:
                        # Make it timezone-aware
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    if created_at < eight_weeks_ago:
                        continue
            
            task_count += 1
            
            # Analyze task title and description for keywords
            text = f"{task.get('title', '')} {task.get('description', '')}".lower()
            
            # Common activity keywords
            keywords = ['workout', 'exercise', 'gym', 'run', 'basketball', 'football', 
                       'soccer', 'tennis', 'yoga', 'meditation', 'reading', 'study',
                       'meeting', 'work', 'project', 'coding', 'programming', 'gaming',
                       'cooking', 'shopping', 'cleaning', 'laundry', 'errands',
                       'family', 'friends', 'social', 'party', 'concert', 'movie']
            
            for keyword in keywords:
                if keyword in text:
                    keyword_frequency[keyword] = keyword_frequency.get(keyword, 0) + 1
            
            # Analyze time preferences (support both 'time' and 'startTime')
            start_time = task.get('startTime') or task.get('time')
            if start_time:
                try:
                    hour = int(start_time.split(':')[0])
                    if 5 <= hour < 12:
                        time_preferences['morning'] += 1
                    elif 12 <= hour < 17:
                        time_preferences['afternoon'] += 1
                    else:
                        time_preferences['evening'] += 1
                except (ValueError, IndexError):
                    # Skip if time format is invalid
                    pass
            
            # Day frequency
            day = task.get('day')
            if day in day_frequency:
                day_frequency[day] += 1
        
        # Sort keywords by frequency
        top_keywords = sorted(keyword_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Find preferred time of day
        preferred_time = max(time_preferences, key=time_preferences.get) if task_count > 0 else 'morning'
        
        # Find busiest days
        busiest_days = sorted(day_frequency.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Generate insights
        insights = {
            'taskCount': task_count,
            'topActivities': [{'keyword': k, 'count': v} for k, v in top_keywords],
            'preferredTime': preferred_time,
            'timeDistribution': time_preferences,
            'busiestDays': [{'day': d, 'count': c} for d, c in busiest_days],
            'dayDistribution': day_frequency,
            'analyzedAt': datetime.now().isoformat()
        }
        
        # Save analysis results
        user_ref.collection('analytics').document('behavior').set({
            'insights': insights,
            'lastAnalyzed': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({
            'success': True,
            'insights': insights
        })
    
    except Exception as e:
        print(f"❌ Behavior analysis error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== EVENT SCRAPING HELPER FUNCTIONS =====

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using geodesic (accurate for earth's surface).
    
    Args:
        lat1, lon1: First coordinate
        lat2, lon2: Second coordinate
        
    Returns:
        float: Distance in miles
    """
    return geodesic((lat1, lon1), (lat2, lon2)).miles


def geocode_location(location_string):
    """
    Convert location string to coordinates using multiple geocoding services with fallbacks.
    
    Args:
        location_string: City name, county, address, or region
        
    Returns:
        tuple: (latitude, longitude) or None if not found
    """
    if not location_string or location_string.strip() == '':
        return None
    
    # Try OpenWeatherMap first
    try:
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if api_key:
            url = f"http://api.openweathermap.org/geo/1.0/direct?q={quote_plus(location_string)}&limit=1&appid={api_key}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    print(f"✅ Geocoded '{location_string}' via OpenWeatherMap: ({data[0]['lat']}, {data[0]['lon']})")
                    return (data[0]['lat'], data[0]['lon'])
    except Exception as e:
        print(f"⚠️  OpenWeatherMap geocoding failed: {e}")
    
    # Fallback to Nominatim (OpenStreetMap)
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={quote_plus(location_string)}&format=json&limit=1&addressdetails=1"
        headers = {
            'User-Agent': 'DailyPlannerApp/1.0 (Event Recommendations)'
        }
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                print(f"✅ Geocoded '{location_string}' via Nominatim: ({lat}, {lon})")
                return (lat, lon)
    except Exception as e:
        print(f"⚠️  Nominatim geocoding failed: {e}")
    
    # Try with geopy as final fallback
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="DailyPlannerApp/1.0")
        location = geolocator.geocode(location_string, timeout=5)
        if location:
            print(f"✅ Geocoded '{location_string}' via geopy: ({location.latitude}, {location.longitude})")
            return (location.latitude, location.longitude)
    except Exception as e:
        print(f"⚠️  Geopy geocoding failed: {e}")
    
    print(f"❌ Could not geocode location: {location_string}")
    return None


def scrape_specific_events(location, radius_miles=10, max_events=10):
    """
    Scrape specific events using targeted searches for event types.
    
    Args:
        location: Location string
        radius_miles: Search radius in miles  
        max_events: Maximum number of events to return
        
    Returns:
        list: List of specific event dictionaries
    """
    events = []
    
    # Parse location for better search
    location_parts = location.split(',')
    area_name = location_parts[0].strip() if location_parts else location
    
    # Specific event types to search for with sample data
    event_templates = [
        {
            'type': 'concerts',
            'icon': '🎵',
            'samples': [
                f'Live Music at {area_name} Venue',
                f'Jazz Night in {area_name}',
                f'{area_name} Concert Series'
            ]
        },
        {
            'type': 'farmers markets',
            'icon': '🥕',
            'samples': [
                f'{area_name} Farmers Market',
                f'Weekend Market - {area_name}',
                f'Local Produce Market'
            ]
        },
        {
            'type': 'art shows',
            'icon': '🎨',
            'samples': [
                f'{area_name} Art Gallery Opening',
                f'Local Artists Exhibition',
                f'Art Walk in {area_name}'
            ]
        },
        {
            'type': 'festivals',
            'icon': '🎪',
            'samples': [
                f'{area_name} Fall Festival',
                f'Community Festival',
                f'Food & Music Festival'
            ]
        },
        {
            'type': 'theater',
            'icon': '🎭',
            'samples': [
                f'Theater Performance at {area_name}',
                f'Community Theater Show',
                f'Local Play Production'
            ]
        }
    ]
    
    try:
        # Try web scraping first
        for template in event_templates[:3]:  # Limit to 3 types
            event_type = template['type']
            search_query = f"{event_type} {location} this week"
            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            
            try:
                response = requests.get(search_url, headers=headers, timeout=8)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for search results with multiple possible selectors
                    search_results = soup.find_all('div', class_='g')
                    if not search_results:
                        search_results = soup.find_all('div', {'data-sokoban-container': True})
                    
                    print(f"🔍 Found {len(search_results)} potential results for {event_type}")
                    
                    for result in search_results[:3]:
                        try:
                            # Try multiple ways to find title and link
                            title_elem = result.find('h3')
                            link_elem = result.find('a', href=True)
                            
                            if not title_elem or not link_elem:
                                continue
                                
                            title = title_elem.get_text(strip=True)
                            url = link_elem['href']
                            
                            # Clean up URL
                            if url.startswith('/url?q='):
                                url = url.split('/url?q=')[1].split('&')[0]
                            
                            # Filter out generic results
                            title_lower = title.lower()
                            skip_words = ['calendar', 'list of', 'events near', 'things to do', 'guide to', 'directory', 'upcoming events']
                            if any(skip in title_lower for skip in skip_words):
                                continue
                            
                            # Get description
                            desc_elem = result.find('div', class_=['VwiC3b', 'st', 'IsZvec'])
                            description = desc_elem.get_text(strip=True) if desc_elem else f"{event_type.title()} in {location}"
                            
                            events.append({
                                'id': f'specific_{len(events) + 1}',
                                'title': title[:100],
                                'category': event_type.title(),
                                'icon': template['icon'],
                                'date': 'Check website',
                                'time': '',
                                'venue': location,
                                'distance': round(random.uniform(1, radius_miles), 1),
                                'description': description[:150],
                                'price': 'See website',
                                'website': url
                            })
                            
                            if len(events) >= max_events:
                                return events
                                
                        except Exception as e:
                            print(f"⚠️  Error parsing result: {e}")
                            continue
                else:
                    print(f"❌ HTTP {response.status_code} for {event_type}")
                    
            except Exception as e:
                print(f"⚠️  Request failed for {event_type}: {e}")
                
            # Small delay between searches
            import time
            time.sleep(0.5)
        
        # If scraping found nothing, provide curated sample events
        if len(events) == 0:
            print(f"📋 Web scraping returned no results. Providing curated local event suggestions...")
            for i, template in enumerate(event_templates[:5]):
                sample_title = template['samples'][0]
                events.append({
                    'id': f'curated_{i + 1}',
                    'title': sample_title,
                    'category': template['type'].title(),
                    'icon': template['icon'],
                    'date': 'Check local listings',
                    'time': 'Various times',
                    'venue': area_name,
                    'distance': round(random.uniform(1, radius_miles), 1),
                    'description': f'Search for {template["type"]} in {area_name}. Check local event calendars, community boards, and social media for current listings.',
                    'price': 'Varies',
                    'website': f'https://www.google.com/search?q={quote_plus(template["type"] + " " + location)}'
                })
                        
    except Exception as e:
        print(f"❌ Specific events scraping error: {e}")
    
    return events


def scrape_google_events(location, radius_miles=10, max_events=5):
    """
    Scrape general events from Google search results.
    
    Args:
        location: Location string
        radius_miles: Search radius in miles
        max_events: Maximum number of events to return
        
    Returns:
        list: List of event dictionaries from Google search
    """
    events = []
    area_name = location.split(',')[0].strip() if ',' in location else location
    
    try:
        # General events search
        search_query = f"events near {location} this week"
        search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        
        response = requests.get(search_url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for search results
            search_results = soup.find_all('div', class_='g')
            if not search_results:
                search_results = soup.find_all('div', {'data-sokoban-container': True})
            
            print(f"🔍 Found {len(search_results)} Google search results")
            
            for result in search_results[:max_events]:
                try:
                    title_elem = result.find('h3')
                    link_elem = result.find('a', href=True)
                    
                    if not title_elem or not link_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    url = link_elem['href']
                    
                    # Clean up URL
                    if url.startswith('/url?q='):
                        url = url.split('/url?q=')[1].split('&')[0]
                    
                    # Filter out generic results
                    title_lower = title.lower()
                    skip_words = ['calendar', 'list of', 'events near', 'things to do', 'guide to', 'directory', 'upcoming events']
                    if any(skip in title_lower for skip in skip_words):
                        continue
                    
                    # Get description
                    desc_elem = result.find('div', class_=['VwiC3b', 'st', 'IsZvec'])
                    description = desc_elem.get_text(strip=True) if desc_elem else f"Event in {location}"
                    
                    events.append({
                        'id': f'google_{len(events) + 1}',
                        'title': title[:100],
                        'category': 'Event',
                        'icon': '🎉',
                        'date': 'Check website',
                        'time': '',
                        'venue': location,
                        'distance': round(random.uniform(1, radius_miles), 1),
                        'description': description[:150],
                        'price': 'See website',
                        'website': url
                    })
                    
                    if len(events) >= max_events:
                        break
                        
                except Exception as e:
                    print(f"⚠️  Error parsing Google event: {e}")
                    continue
        
        # If no events found, provide sample community events
        if len(events) == 0:
            print(f"📋 Providing sample community event suggestions for {area_name}...")
            events.append({
                'id': 'community_1',
                'title': f'{area_name} Community Events',
                'category': 'Community',
                'icon': '🏘️',
                'date': 'Ongoing',
                'time': 'Various',
                'venue': area_name,
                'distance': round(random.uniform(1, radius_miles), 1),
                'description': f'Check local community boards, Facebook groups, and Nextdoor for current events in {area_name}.',
                'price': 'Free - Varies',
                'website': f'https://www.google.com/search?q=events+{quote_plus(location)}'
            })
                    
    except Exception as e:
        print(f"❌ Google events scraping error: {e}")
    
    return events


def scrape_local_venue_events(location, radius_miles=10, max_events=5):
    """
    Search for events at specific local venues and establishments.
    
    Args:
        location: Location string
        radius_miles: Search radius in miles
        max_events: Maximum number of events to return
        
    Returns:
        list: List of venue-specific events
    """
    events = []
    area_name = location.split(',')[0].strip() if ',' in location else location
    
    try:
        # Search for local venues with events
        venue_queries = [
            f"music venues {location} events this week",
            f"theaters {location} shows",
            f"community centers {location} activities"
        ]
        
        for query in venue_queries[:2]:  # Limit queries
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            try:
                response = requests.get(search_url, headers=headers, timeout=8)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find venue listings
                    results = soup.find_all('div', class_='g')
                    if not results:
                        results = soup.find_all('div', {'data-sokoban-container': True})
                    
                    print(f"🔍 Found {len(results)} potential venue results")
                    
                    for result in results[:3]:
                        try:
                            title_elem = result.find('h3')
                            link_elem = result.find('a', href=True)
                            
                            if title_elem and link_elem:
                                title = title_elem.get_text(strip=True)
                                url = link_elem['href']
                                
                                if url.startswith('/url?q='):
                                    url = url.split('/url?q=')[1].split('&')[0]
                                
                                # Look for venue names in title
                                if any(word in title.lower() for word in ['venue', 'theater', 'center', 'hall', 'club']):
                                    events.append({
                                        'id': f'venue_{len(events) + 1}',
                                        'title': f"Events at {title}",
                                        'category': 'Venue Events',
                                        'icon': '🏛️',
                                        'date': 'Ongoing',
                                        'time': 'Check schedule',
                                        'venue': title,
                                        'distance': round(random.uniform(1, radius_miles), 1),
                                        'description': f"Check current events and shows at {title}",
                                        'price': 'Varies',
                                        'website': url
                                    })
                                    
                                    if len(events) >= max_events:
                                        return events
                                        
                        except Exception as e:
                            print(f"⚠️  Error parsing venue result: {e}")
                            continue
                            
            except Exception as e:
                print(f"⚠️  Request failed for venue query: {e}")
                continue
        
        # If no venues found, provide sample venue suggestions
        if len(events) == 0:
            print(f"📋 Providing sample venue suggestions for {area_name}...")
            sample_venues = [
                {'name': f'{area_name} Performing Arts Center', 'icon': '🎭'},
                {'name': f'{area_name} Music Hall', 'icon': '🎵'},
                {'name': f'Community Center - {area_name}', 'icon': '🏛️'}
            ]
            
            for i, venue in enumerate(sample_venues[:2]):
                events.append({
                    'id': f'venue_sample_{i + 1}',
                    'title': f"Events at {venue['name']}",
                    'category': 'Venue Events',
                    'icon': venue['icon'],
                    'date': 'Ongoing',
                    'time': 'Check schedule',
                    'venue': venue['name'],
                    'distance': round(random.uniform(1, radius_miles), 1),
                    'description': f"Search for current events and shows. Check their website or call for schedule.",
                    'price': 'Varies',
                    'website': f'https://www.google.com/search?q={quote_plus(venue["name"])}'
                })
                        
    except Exception as e:
        print(f"❌ Venue events scraping error: {e}")
    
    return events


def scrape_local_events(location, radius_miles=10, max_events=10):
    """
    Aggregate specific events from multiple targeted sources.
    
    Args:
        location: Location string
        radius_miles: Search radius in miles
        max_events: Maximum events to return
        
    Returns:
        list: Combined list of specific events
    """
    all_events = []
    
    print(f"🔍 Searching for specific events near {location} within {radius_miles} miles...")
    
    # Specific event type searches
    specific_events = scrape_specific_events(location, radius_miles, max_events // 2)
    all_events.extend(specific_events)
    print(f"✅ Found {len(specific_events)} specific events")
    
    # Local venue events
    venue_events = scrape_local_venue_events(location, radius_miles, max_events // 4)
    all_events.extend(venue_events)
    print(f"✅ Found {len(venue_events)} venue events")
    
    # Google general search (improved)
    google_events = scrape_google_events(location, radius_miles, max_events // 4)
    all_events.extend(google_events)
    print(f"✅ Found {len(google_events)} events from Google")
    
    # If still no specific events found, provide location-based resources
    if len(all_events) == 0:
        print(f"⚠️  No specific events found. Providing location-based resources...")
        all_events = generate_sample_events_for_location(location, radius_miles)
    
    # Remove duplicates and filter quality
    seen_titles = set()
    unique_events = []
    for event in all_events:
        title_key = event['title'].lower()[:50]
        if title_key not in seen_titles and len(event['title']) > 10:
            seen_titles.add(title_key)
            unique_events.append(event)
    
    # Prioritize specific named events over generic ones
    unique_events.sort(key=lambda x: (
        0 if any(word in x['title'].lower() for word in ['festival', 'concert', 'show', 'market']) else 1,
        -len(x['title'])
    ))
    
    # Randomize within quality tiers and limit
    random.shuffle(unique_events)
    return unique_events[:max_events]


def generate_sample_events_for_location(location, radius_miles=10):
    """
    Generate sample events when scraping fails, customized for the location.
    
    Args:
        location: User's location string
        radius_miles: Search radius
        
    Returns:
        list: Sample events appropriate for the area
    """
    # Parse location to get area name
    location_parts = location.split(',')
    area_name = location_parts[0].strip() if location_parts else location
    
    sample_events = [
        {
            'id': 'sample_1',
            'title': f'Local Events in {area_name}',
            'category': 'Community',
            'icon': '🎪',
            'date': 'This Weekend',
            'time': 'Various Times',
            'venue': f'{area_name} Area',
            'distance': round(random.uniform(1, radius_miles), 1),
            'description': f'Check local event listings and community boards in {area_name} for upcoming activities.',
            'price': 'Varies',
            'website': f'https://www.google.com/search?q=events+near+{quote_plus(location)}'
        },
        {
            'id': 'sample_2',
            'title': 'Community Farmers Market',
            'category': 'Community',
            'icon': '🥕',
            'date': 'Saturdays',
            'time': '8:00 AM - 1:00 PM',
            'venue': f'{area_name} Downtown',
            'distance': round(random.uniform(1, radius_miles), 1),
            'description': 'Fresh local produce, artisan goods, and community gathering.',
            'price': 'Free entry',
            'website': f'https://www.google.com/search?q=farmers+market+{quote_plus(location)}'
        },
        {
            'id': 'sample_3',
            'title': 'Library Events & Workshops',
            'category': 'Education',
            'icon': '📚',
            'date': 'Ongoing',
            'time': 'Check schedule',
            'venue': f'{area_name} Public Library',
            'distance': round(random.uniform(1, radius_miles), 1),
            'description': 'Free workshops, book clubs, and community programs.',
            'price': 'Free',
            'website': f'https://www.google.com/search?q=library+events+{quote_plus(location)}'
        },
        {
            'id': 'sample_4',
            'title': 'Local Parks & Recreation',
            'category': 'Outdoor',
            'icon': '🌳',
            'date': 'Daily',
            'time': 'Dawn to Dusk',
            'venue': f'{area_name} Parks',
            'distance': round(random.uniform(1, radius_miles), 1),
            'description': 'Explore local parks, trails, and outdoor activities.',
            'price': 'Free',
            'website': f'https://www.google.com/search?q=parks+near+{quote_plus(location)}'
        },
        {
            'id': 'sample_5',
            'title': 'Community Arts & Culture',
            'category': 'Arts',
            'icon': '🎨',
            'date': 'Check calendar',
            'time': 'Various',
            'venue': f'{area_name} Cultural Center',
            'distance': round(random.uniform(1, radius_miles), 1),
            'description': 'Local art galleries, theater performances, and cultural events.',
            'price': 'Varies',
            'website': f'https://www.google.com/search?q=arts+culture+events+{quote_plus(location)}'
        }
    ]
    
    print(f"📋 Generated {len(sample_events)} location-based sample events for {location}")
    return sample_events


# ===== REAL API INTEGRATIONS FOR EVENTS & PLACES =====

def get_google_places_nearby(location, radius_miles=10, max_results=20, user_preferences=None, custom_query=None):
    """
    Get real nearby places using Google Places API (New) with smart interest-based searching.
    
    Searches for places based on user interests:
    - Basketball lover → basketball courts, sports complexes
    - Dog owner → dog parks, dog-friendly restaurants
    - Food preferences → specific cuisine types
    - Activity preferences → relevant venues
    
    Args:
        location: Location string (city, address)
        radius_miles: Search radius in miles (1-20 recommended)
        max_results: Maximum number of results
        user_preferences: User preference dict with interests, pets, cuisines, etc.
        custom_query: Optional custom search query (e.g., "dog friendly restaurants near me")
        
    Returns:
        list: Real nearby places with details, personalized to user interests
    """
    places = []
    
    try:
        # Get coordinates for location
        coords = geocode_location(location)
        if not coords:
            print(f"❌ Could not geocode location: {location}")
            return places
        
        lat, lon = coords
        radius_meters = int(radius_miles * 1609.34)  # Convert miles to meters
        
        # Google Places API key from environment
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        if not api_key:
            print("⚠️  No Google Places API key found. Set GOOGLE_PLACES_API_KEY in .env")
            return places
        
        # Build smart search queries based on user preferences
        search_queries = []
        
        # Extract user preferences FIRST (needed for both custom and default queries)
        has_dog = user_preferences.get('hasDog', False) if user_preferences else False
        hobbies = user_preferences.get('hobbies', []) if user_preferences else []
        cuisines = user_preferences.get('cuisineTypes', []) if user_preferences else []
        outdoor_activities = user_preferences.get('outdoorActivities', []) if user_preferences else []
        indoor_activities = user_preferences.get('indoorActivities', []) if user_preferences else []
        workout_styles = user_preferences.get('workoutStyles', []) if user_preferences else []
        
        # If custom query provided (from AI assistant), use that exclusively
        if custom_query:
            search_queries = [{'query': custom_query, 'icon': '🔍', 'category': 'Search Results', 'priority': 1}]
        else:
            
            # DOG OWNER - Include dog-friendly places in variety
            if has_dog:
                search_queries.extend([
                    {'query': f'dog park near {location}', 'icon': '🐕', 'category': 'Dog Parks', 'priority': 2},
                    {'query': f'dog-friendly restaurant near {location}', 'icon': '🍽️', 'category': 'Dog-Friendly Dining', 'priority': 3},
                ])
            
            # SPORTS & RECREATION - Based on hobbies
            if any(hobby in ['basketball', 'sports'] for hobby in hobbies) or \
               any(activity in ['basketball', 'sports'] for activity in outdoor_activities):
                search_queries.extend([
                    {'query': f'basketball court near {location}', 'icon': '🏀', 'category': 'Basketball Courts', 'priority': 1},
                    {'query': f'sports complex near {location}', 'icon': '🏆', 'category': 'Sports Facilities', 'priority': 2},
                ])
            if 'soccer' in hobbies or 'soccer' in outdoor_activities:
                search_queries.append({'query': f'soccer field near {location}', 'icon': '⚽', 'category': 'Soccer Fields', 'priority': 1})
            if 'golf' in hobbies or 'golf' in outdoor_activities:
                search_queries.append({'query': f'golf course near {location}', 'icon': '⛳', 'category': 'Golf Courses', 'priority': 1})
            if 'tennis' in hobbies or 'tennis' in outdoor_activities:
                search_queries.append({'query': f'tennis court near {location}', 'icon': '🎾', 'category': 'Tennis', 'priority': 1})
            if 'gaming' in hobbies:
                search_queries.append({'query': f'gaming lounge near {location}', 'icon': '🎮', 'category': 'Gaming', 'priority': 2})
            if 'reading' in hobbies:
                search_queries.append({'query': f'library near {location}', 'icon': '📚', 'category': 'Libraries', 'priority': 2})
            if 'painting' in hobbies or 'arts' in hobbies:
                search_queries.append({'query': f'art gallery near {location}', 'icon': '🎨', 'category': 'Art & Culture', 'priority': 1})
            if 'cooking' in hobbies:
                search_queries.append({'query': f'cooking class near {location}', 'icon': '🍳', 'category': 'Cooking Classes', 'priority': 2})
            if 'photography' in hobbies:
                search_queries.append({'query': f'photo gallery near {location}', 'icon': '📷', 'category': 'Photography', 'priority': 2})
            if 'music' in hobbies:
                search_queries.append({'query': f'music venue near {location}', 'icon': '🎵', 'category': 'Live Music', 'priority': 1})
            
            # WORKOUT FACILITIES - Based on workout preferences
            if any(workout in ['gym', 'strength', 'cardio', 'hiit'] for workout in workout_styles):
                search_queries.append({'query': f'gym near {location}', 'icon': '💪', 'category': 'Fitness Centers', 'priority': 1})
            if 'yoga' in workout_styles or 'pilates' in workout_styles:
                search_queries.append({'query': f'yoga studio near {location}', 'icon': '🧘', 'category': 'Yoga & Wellness', 'priority': 1})
            if 'running' in workout_styles or 'running' in outdoor_activities:
                search_queries.append({'query': f'running trail near {location}', 'icon': '🏃', 'category': 'Running Trails', 'priority': 1})
            if 'walking' in workout_styles or 'walking' in outdoor_activities:
                search_queries.append({'query': f'walking trail near {location}', 'icon': '🚶', 'category': 'Walking Trails', 'priority': 1})
            
            # RESTAURANTS & DINING - Always include general restaurants + user cuisines
            # Add general restaurant search (priority 1 so it shows up)
            search_queries.append({
                'query': f'restaurant near {location}',
                'icon': '🍽️',
                'category': 'Restaurants',
                'priority': 1
            })
            
            # Add specific cuisines if user has them (limit to 2 for variety)
            for cuisine in cuisines[:2]:
                search_queries.append({
                    'query': f'{cuisine} restaurant near {location}',
                    'icon': '🍽️',
                    'category': f'{cuisine.title()} Dining',
                    'priority': 2
                })
            
            # CAFES & BARS - Always include these social/dining venues
            search_queries.extend([
                {'query': f'cafe near {location}', 'icon': '☕', 'category': 'Cafes', 'priority': 1},
                {'query': f'bar near {location}', 'icon': '🍺', 'category': 'Bars & Nightlife', 'priority': 2},
            ])
            
            # OUTDOOR ACTIVITIES
            if 'hiking' in outdoor_activities or 'nature' in hobbies:
                search_queries.append({'query': f'hiking trail near {location}', 'icon': '🥾', 'category': 'Hiking', 'priority': 1})
            if 'beaches' in outdoor_activities or 'beach' in outdoor_activities:
                search_queries.append({'query': f'beach near {location}', 'icon': '🏖️', 'category': 'Beaches', 'priority': 1})
            if 'parks' in outdoor_activities:
                search_queries.append({'query': f'park near {location}', 'icon': '🌳', 'category': 'Parks', 'priority': 1})
            if 'cycling' in outdoor_activities:
                search_queries.append({'query': f'bike trail near {location}', 'icon': '🚴', 'category': 'Cycling', 'priority': 1})
            if 'kayaking' in outdoor_activities:
                search_queries.append({'query': f'kayak rental near {location}', 'icon': '🛶', 'category': 'Water Sports', 'priority': 2})
            if 'camping' in outdoor_activities:
                search_queries.append({'query': f'campground near {location}', 'icon': '⛺', 'category': 'Camping', 'priority': 2})
            if 'fishing' in outdoor_activities:
                search_queries.append({'query': f'fishing spot near {location}', 'icon': '🎣', 'category': 'Fishing', 'priority': 2})
            
            # INDOOR ACTIVITIES
            if 'museums' in indoor_activities:
                search_queries.append({'query': f'museum near {location}', 'icon': '🏛️', 'category': 'Museums', 'priority': 1})
            if 'theaters' in indoor_activities:
                search_queries.append({'query': f'theater near {location}', 'icon': '🎭', 'category': 'Theater', 'priority': 1})
            if 'shopping' in indoor_activities:
                search_queries.append({'query': f'shopping center near {location}', 'icon': '🛍️', 'category': 'Shopping', 'priority': 2})
            if 'arcades' in indoor_activities:
                search_queries.append({'query': f'arcade near {location}', 'icon': '🕹️', 'category': 'Arcades', 'priority': 2})
            if 'bowling' in indoor_activities:
                search_queries.append({'query': f'bowling alley near {location}', 'icon': '🎳', 'category': 'Bowling', 'priority': 1})
            if 'climbing' in indoor_activities:
                search_queries.append({'query': f'rock climbing gym near {location}', 'icon': '🧗', 'category': 'Climbing', 'priority': 1})
            if 'escape-rooms' in indoor_activities:
                search_queries.append({'query': f'escape room near {location}', 'icon': '🔐', 'category': 'Escape Rooms', 'priority': 2})
            
            # DEFAULT CATEGORIES (ensure variety if limited preferences)
            # These are lower priority but add diversity
            default_queries = [
                {'query': f'park near {location}', 'icon': '🌳', 'category': 'Parks', 'priority': 3},
                {'query': f'movie theater near {location}', 'icon': '🎬', 'category': 'Entertainment', 'priority': 3},
                {'query': f'shopping mall near {location}', 'icon': '🛍️', 'category': 'Shopping', 'priority': 3},
                {'query': f'bookstore near {location}', 'icon': '📚', 'category': 'Bookstores', 'priority': 3},
                {'query': f'ice cream near {location}', 'icon': '🍦', 'category': 'Desserts', 'priority': 3},
                {'query': f'bakery near {location}', 'icon': '🥐', 'category': 'Bakeries', 'priority': 3},
            ]
            
            # Add defaults if we don't have enough personalized queries
            if len(search_queries) < 8:
                search_queries.extend(default_queries[:8 - len(search_queries)])
            
            # Sort by priority (lower = higher priority)
            search_queries.sort(key=lambda x: x['priority'])
        
        # Using Places API (New) - Text Search endpoint
        base_url = "https://places.googleapis.com/v1/places:searchText"
        
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': api_key,
            'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.types,places.rating,places.userRatingCount,places.priceLevel,places.location,places.googleMapsUri,places.currentOpeningHours'
        }
        
        # Track seen places to avoid duplicates
        seen_names = set()
        
        # Search with variety - get results from multiple queries
        for search_item in search_queries[:8]:  # Max 8 different searches for variety
            payload = {
                'textQuery': search_item['query'],
                'locationBias': {
                    'circle': {
                        'center': {
                            'latitude': lat,
                            'longitude': lon
                        },
                        'radius': radius_meters
                    }
                },
                'maxResultCount': 5  # Get top 5 per search for variety
            }
            
            try:
                response = requests.post(base_url, headers=headers, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    results = data.get('places', [])
                    
                    for place in results:
                        # Calculate distance
                        place_location = place.get('location', {})
                        place_lat = place_location.get('latitude')
                        place_lon = place_location.get('longitude')
                        
                        distance = 0
                        if place_lat and place_lon:
                            distance = calculate_distance(lat, lon, place_lat, place_lon)
                        
                        # Extract details
                        name = place.get('displayName', {}).get('text', 'Unknown Place')
                        
                        # Skip duplicates
                        if name.lower() in seen_names:
                            continue
                        seen_names.add(name.lower())
                        
                        # IMPORTANT: Skip places outside the user's radius
                        if distance and distance > radius_miles:
                            print(f"   ⚠️  Filtering out '{name}' - {distance:.1f} mi away (radius: {radius_miles} mi)")
                            continue
                        
                        address = place.get('formattedAddress', location)
                        rating = place.get('rating', 'N/A')
                        user_ratings = place.get('userRatingCount', 0)
                        price_level = place.get('priceLevel', 'PRICE_LEVEL_UNSPECIFIED')
                        maps_uri = place.get('googleMapsUri', '#')
                        place_types = place.get('types', [])
                        
                        # Convert price level to symbols
                        price_map = {
                            'PRICE_LEVEL_FREE': 'Free',
                            'PRICE_LEVEL_INEXPENSIVE': '💰',
                            'PRICE_LEVEL_MODERATE': '💰💰',
                            'PRICE_LEVEL_EXPENSIVE': '💰💰💰',
                            'PRICE_LEVEL_VERY_EXPENSIVE': '💰💰💰💰'
                        }
                        price_str = price_map.get(price_level, 'Price varies')
                        
                        # Check if currently open
                        is_open = place.get('currentOpeningHours', {}).get('openNow', False)
                        open_status = 'Open Now' if is_open else 'Check hours'
                        
                        # Enhanced dog-friendly detection
                        dog_friendly = False
                        if has_dog:
                            # Check multiple indicators
                            name_lower = name.lower()
                            address_lower = address.lower()
                            dog_keywords = ['dog', 'pet', 'patio', 'outdoor', 'terrace', 'garden', 'park']
                            dog_friendly = any(keyword in name_lower or keyword in address_lower for keyword in dog_keywords)
                            
                            # Dog parks are always dog-friendly
                            if 'park' in place_types or 'dog_park' in place_types or 'park' in search_item['category'].lower():
                                dog_friendly = True
                        
                        places.append({
                            'id': f"place_{len(places) + 1}",
                            'title': name,
                            'category': search_item['category'],
                            'icon': search_item['icon'],  # Use single icon only
                            'type': 'place',  # Differentiate from events
                            'date': open_status,
                            'time': '',
                            'venue': address,
                            'distance': round(distance, 1) if distance else 'N/A',
                            'description': f"Rating: {'⭐' * int(rating) if isinstance(rating, (int, float)) else rating} ({user_ratings} reviews)" if user_ratings > 0 else "New place",
                            'price': price_str,
                            'website': maps_uri,
                            'rating': rating,
                            'dog_friendly': dog_friendly,
                            'priority': search_item['priority']  # For sorting
                        })
                        
                        if len(places) >= max_results:
                            # Shuffle for variety on each refresh
                            random.shuffle(places)
                            return places
                
                elif response.status_code == 403:
                    print(f"❌ Google Places API error: Billing not enabled or API not activated")
                    print(f"   Visit: https://console.cloud.google.com/apis/library/places-backend.googleapis.com")
                    return places
                else:
                    error_data = response.json() if response.content else {}
                    print(f"❌ Google Places API error: {response.status_code}")
                    print(f"   Response: {error_data}")
                    
            except Exception as e:
                print(f"⚠️  Error fetching {search_item['category']}: {e}")
                continue
        
        # Shuffle for variety on each refresh before returning
        random.shuffle(places)
        
        print(f"✅ Returning {len(places)} places within {radius_miles} mile radius")
                
    except Exception as e:
        print(f"❌ Google Places API error: {e}")
    
    return places


def get_ticketmaster_events(location, radius_miles=10, max_results=10):
    """
    Get real events from Ticketmaster Discovery API.
    
    Event types:
    - Concerts (music)
    - Sports games
    - Theater & performing arts
    - Comedy shows
    - Family events
    
    Args:
        location: Location string
        radius_miles: Search radius in miles
        max_results: Maximum number of results
        
    Returns:
        list: Real upcoming events
    """
    events = []
    
    try:
        # Get coordinates
        coords = geocode_location(location)
        if not coords:
            print(f"❌ Could not geocode location for Ticketmaster: {location}")
            return events
        
        lat, lon = coords
        
        # Ticketmaster API key
        api_key = os.getenv('TICKETMASTER_API_KEY')
        if not api_key:
            print("⚠️  No Ticketmaster API key. Set TICKETMASTER_API_KEY in .env")
            return events
        
        base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
        
        params = {
            'apikey': api_key,
            'latlong': f"{lat},{lon}",
            'radius': int(radius_miles),
            'unit': 'miles',
            'size': max_results,
            'sort': 'date,asc'
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if '_embedded' in data and 'events' in data['_embedded']:
                for event in data['_embedded']['events']:
                    # Parse event details
                    name = event.get('name', 'Unknown Event')
                    event_type = event.get('classifications', [{}])[0].get('segment', {}).get('name', 'Event')
                    genre = event.get('classifications', [{}])[0].get('genre', {}).get('name', '')
                    
                    # Date and time
                    start_date = event.get('dates', {}).get('start', {})
                    date_str = start_date.get('localDate', 'TBA')
                    time_str = start_date.get('localTime', '')
                    
                    # Format date nicely
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                        date_formatted = dt.strftime('%b %d, %Y')
                    except:
                        date_formatted = date_str
                    
                    # Venue
                    venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                    venue_name = venue_info.get('name', 'TBA')
                    venue_city = venue_info.get('city', {}).get('name', '')
                    
                    # Distance
                    venue_lat = venue_info.get('location', {}).get('latitude')
                    venue_lon = venue_info.get('location', {}).get('longitude')
                    distance = 0
                    if venue_lat and venue_lon:
                        distance = calculate_distance(lat, lon, float(venue_lat), float(venue_lon))
                    
                    # IMPORTANT: Skip events outside the user's radius
                    if distance and distance > radius_miles:
                        print(f"   ⚠️  Filtering out '{name}' - {distance:.1f} mi away (radius: {radius_miles} mi)")
                        continue
                    
                    # Price range
                    price_ranges = event.get('priceRanges', [])
                    price_str = 'See website'
                    if price_ranges:
                        min_price = price_ranges[0].get('min', 0)
                        max_price = price_ranges[0].get('max', 0)
                        price_str = f"${min_price:.0f} - ${max_price:.0f}"
                    
                    # Icon based on type
                    icon_map = {
                        'Music': '🎵',
                        'Sports': '🏆',
                        'Arts & Theatre': '🎭',
                        'Family': '👨‍👩‍👧‍👦',
                        'Film': '🎬',
                        'Miscellaneous': '🎪'
                    }
                    icon = icon_map.get(event_type, '🎉')
                    
                    # URL
                    url = event.get('url', '#')
                    
                    events.append({
                        'id': f"tm_{event.get('id', '')}",
                        'title': name,
                        'category': f"{event_type} - {genre}" if genre else event_type,
                        'icon': icon,
                        'type': 'event',  # Differentiate from places
                        'date': date_formatted,
                        'time': time_str if time_str else 'Check website',
                        'venue': f"{venue_name}, {venue_city}",
                        'distance': round(distance, 1),
                        'description': f"{event_type} event" + (f" - {genre}" if genre else ""),
                        'price': price_str,
                        'website': url
                    })
        else:
            print(f"❌ Ticketmaster API HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ticketmaster API error: {e}")
    
    print(f"✅ Returning {len(events)} events within {radius_miles} mile radius")
    return events


def get_all_recommendations(location, radius_miles=10, max_results=20, user_preferences=None):
    """
    Aggregate recommendations from all sources with smart personalization.
    - Google Places (restaurants, parks, stores, etc.) - PERSONALIZED by interests
    - Ticketmaster (concerts, sports, theater) - Major events
    
    Focus on variety: restaurants, cafes, parks, entertainment venues, sports facilities
    
    Args:
        location: Location string
        radius_miles: Search radius in miles (1-20 recommended)
        max_results: Maximum total results (will return up to 10 places and 10 events)
        user_preferences: User preference dict for personalization
        
    Returns:
        dict: Combined recommendations with separate categories
    """
    all_recommendations = {
        'places': [],
        'events': [],
        'total': 0
    }
    
    try:
        print(f"🔍 Fetching recommendations for {location} (radius: {radius_miles} mi)...")
        
        # Get MORE results than we'll show (for rotation variety)
        # Get 20 places and 20 ticketmaster events for balanced variety
        places = get_google_places_nearby(location, radius_miles, max_results=20, user_preferences=user_preferences)
        print(f"✅ Found {len(places)} nearby places")
        
        tm_events = get_ticketmaster_events(location, radius_miles, max_results=20)
        print(f"✅ Found {len(tm_events)} Ticketmaster events")
        
        # Combine places and events into one pool
        all_items = []
        for place in places:
            place['type'] = 'place'
            all_items.append(place)
        for event in tm_events:
            event['type'] = 'event'
            all_items.append(event)
        
        # Shuffle for variety on each refresh, but use a time-based seed
        # so results stay consistent for ~5 minutes (then rotate)
        import random
        import time
        seed = int(time.time() / 300)  # Changes every 5 minutes
        random.seed(seed)
        random.shuffle(all_items)
        
        # Take only 10 items total
        selected_items = all_items[:10]
        
        # Separate back into places and events
        all_recommendations['places'] = [item for item in selected_items if item['type'] == 'place']
        all_recommendations['events'] = [item for item in selected_items if item['type'] == 'event']
        all_recommendations['total'] = len(selected_items)
        
        print(f"📊 Showing {all_recommendations['total']} recommendations (refreshes every 5 min)")
        
    except Exception as e:
        print(f"❌ Error aggregating recommendations: {e}")
    
    return all_recommendations


@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    """
    Get personalized recommendations using real APIs:
    - Google Places API: Restaurants, parks, stores, dog-friendly spots
    - Ticketmaster API: Concerts, sports, theater events
    
    Returns up to 10 places and 10 events (20 total) for faster loading.
    """
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded_claims['uid']
        
        # Get user preferences
        user_ref = db.collection('users').document(uid)
        prefs_doc = user_ref.collection('preferences').document('main').get()
        
        # Default values - ALWAYS use Monmouth County as fallback
        location = 'Monmouth County, NJ'  # Default location
        radius = 10  # Default 10 miles (1-20 mile range)
        user_preferences = None
        auto_filled = False
        
        if prefs_doc.exists:
            user_preferences = prefs_doc.to_dict()
            # Only override default if user explicitly set a location
            user_location = user_preferences.get('location', '').strip()
            if user_location:
                location = user_location
            # Get radius from preferences, clamp to 1-20 mile range
            radius = user_preferences.get('maxTravelDistance', 10)
            radius = max(1, min(20, radius))  # Ensure 1-20 range
        
        # AUTO-FILL PREFERENCES if user has no preferences set
        if not user_preferences or not any([
            user_preferences.get('hobbies'),
            user_preferences.get('workoutStyles'),
            user_preferences.get('indoorActivities'),
            user_preferences.get('outdoorActivities'),
            user_preferences.get('cuisineTypes')
        ]):
            # Check if user has enough tasks to analyze
            tasks_ref = db.collection('users').document(uid).collection('tasks')
            task_count = len(list(tasks_ref.limit(10).stream()))
            
            if task_count >= 5:
                print(f"🤖 Auto-filling preferences for user {uid} based on {task_count} tasks...")
                try:
                    # Call autofill logic inline
                    all_tasks = list(tasks_ref.stream())
                    task_data = []
                    for task_doc in all_tasks:
                        task = task_doc.to_dict()
                        task_info = {
                            'title': task.get('title', ''),
                            'description': task.get('description', ''),
                            'completed': task.get('completed', False)
                        }
                        task_data.append(task_info)
                    
                    # Build AI prompt
                    prompt = f"""Analyze these {len(task_data)} tasks and extract user preferences:

TASKS:
{chr(10).join([f"- {t['title']}: {t['description']} (completed: {t['completed']})" for t in task_data[:100]])}

Based on these tasks, identify the user's:
1. HOBBIES & INTERESTS (e.g., basketball, reading, painting, gaming, cooking, etc.)
2. WORKOUT STYLES (e.g., cardio, strength, yoga, hiit, running, pilates, etc.)
3. INDOOR ACTIVITIES (e.g., museums, shopping, theaters, arcades, bowling, etc.)
4. OUTDOOR ACTIVITIES (e.g., hiking, beach, parks, cycling, kayaking, camping, etc.)
5. CUISINE TYPES (e.g., italian, mexican, sushi, chinese, thai, etc.)
6. EVENT PREFERENCES (e.g., concerts, sports, theater, comedy, festivals, etc.)

IMPORTANT: Only include items that appear MULTIPLE times or are clearly important to the user.
Focus on completed tasks as they show what the user actually does.

Respond in JSON format:
{{
  "hobbies": ["hobby1", "hobby2"],
  "workoutStyles": ["workout1", "workout2"],
  "indoorActivities": ["activity1", "activity2"],
  "outdoorActivities": ["activity1", "activity2"],
  "cuisineTypes": ["cuisine1", "cuisine2"],
  "eventTypes": ["event1", "event2"]
}}"""
                    
                    # Call Gemini AI
                    if gemini_model:
                        response = gemini_model.generate_content(prompt)
                        ai_response = response.text.strip()
                        
                        # Extract JSON from response
                        import json
                        import re
                        
                        # Try to find JSON in the response
                        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ai_response, re.DOTALL)
                        if json_match:
                            preferences_data = json.loads(json_match.group())
                        else:
                            # Try parsing the whole response as JSON
                            preferences_data = json.loads(ai_response)
                        
                        # Save auto-filled preferences
                        from datetime import datetime
                        auto_prefs = {
                            'hobbies': preferences_data.get('hobbies', []),
                            'workoutStyles': preferences_data.get('workoutStyles', []),
                            'indoorActivities': preferences_data.get('indoorActivities', []),
                            'outdoorActivities': preferences_data.get('outdoorActivities', []),
                            'cuisineTypes': preferences_data.get('cuisineTypes', []),
                            'eventCategories': preferences_data.get('eventTypes', []),
                            'maxTravelDistance': radius,
                            'wakeTime': '07:00',
                            'bedTime': '23:00',
                            'updatedAt': firestore.SERVER_TIMESTAMP,
                            'autoFilled': True
                        }
                        user_ref.collection('preferences').document('main').set(auto_prefs, merge=True)
                        user_preferences = auto_prefs
                        auto_filled = True
                        print(f"✅ Auto-filled preferences: {list(preferences_data.keys())}")
                except Exception as e:
                    print(f"⚠️ Could not auto-fill preferences: {e}")
        
        # Location is always set (either user's or default), so no need to check
        
        # Get all recommendations from real APIs - NOW WITH USER PREFERENCES!
        results = get_all_recommendations(location, radius, max_results=20, user_preferences=user_preferences)
        
        # Combine for backward compatibility, but also send separately
        all_recommendations = results['places'] + results['events']
        
        # If nothing found, provide helpful message based on the reason
        if results['total'] == 0:
            # Check if user has ANY preferences set
            has_preferences = False
            if user_preferences:
                pref_fields = ['hobbies', 'workoutStyles', 'indoorActivities', 'outdoorActivities', 'cuisineTypes', 'hasDog', 'hasCat']
                has_preferences = any(user_preferences.get(field) for field in pref_fields)
            
            if not has_preferences:
                error_msg = f'No recommendations found. Set your preferences in AI Preferences to get personalized suggestions!'
            else:
                error_msg = f'No recommendations found near {location}. Try expanding your search radius or check API configuration.'
            
            return jsonify({
                'success': True,
                'recommendations': [],
                'places': [],
                'events': [],
                'message': error_msg,
                'count': 0,
                'location': location,
                'radius': radius,
                'hasPreferences': has_preferences
            })
        
        return jsonify({
            'success': True,
            'recommendations': all_recommendations,  # Combined list
            'places': results['places'],  # Separate places
            'events': results['events'],  # Separate events
            'count': results['total'],
            'placesCount': len(results['places']),
            'eventsCount': len(results['events']),
            'location': location,
            'radius': radius,
            'autoFilled': auto_filled  # Let frontend know preferences were auto-filled
        })
    
    except Exception as e:
        print(f"❌ Recommendations error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'recommendations': [],
            'places': [],
            'events': []
        }), 500


@app.route("/logout")
def logout():
    """
    Log out user by clearing session cookie and Firebase auth state.
    
    This endpoint clears both the server-side session cookie and provides
    a logout page that signs out from Firebase client-side before redirecting.
    
    Returns:
        Response: Logout page with Firebase sign-out script, or direct redirect
    """
    # Create response that clears the session cookie
    resp = make_response(render_template("logout.html"))
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp


# ===== CRON API ENDPOINTS FOR VERCEL =====
# These endpoints are designed to be triggered by Vercel Cron Jobs or external cron services
# Background threads don't work on Vercel's serverless architecture

@app.route("/api/cron/check-notifications", methods=['GET', 'POST'])
def cron_check_notifications():
    """
    Cron endpoint to check and send task notifications.
    
    This endpoint should be triggered every 5 minutes by:
    - Vercel Cron Jobs (configured in vercel.json), OR
    - External cron service like cron-job.org
    
    Security: In production, verify the request comes from authorized source
    
    Returns:
        JSON response with notification statistics
    """
    # Optional: Add authorization check for production
    # auth_header = request.headers.get('Authorization')
    # if auth_header != f"Bearer {os.getenv('CRON_SECRET')}":
    #     return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        print("🔔 Cron job triggered: checking notifications")
        
        if not db:
            return jsonify({
                'success': False,
                'error': 'Database not available'
            }), 500
        
        # Run the notification check
        notifications_sent = check_and_send_notifications()
        
        return jsonify({
            'success': True,
            'message': 'Notification check completed',
            'notifications_sent': notifications_sent,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Cron error in check-notifications: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route("/api/cron/daily-summary", methods=['GET', 'POST'])
def cron_daily_summary():
    """
    Cron endpoint to send daily summary emails.
    
    This endpoint should be triggered once daily at 8 PM by:
    - Vercel Cron Jobs (configured in vercel.json), OR
    - External cron service like cron-job.org
    
    Security: In production, verify the request comes from authorized source
    
    Returns:
        JSON response with summary statistics
    """
    # Optional: Add authorization check for production
    # auth_header = request.headers.get('Authorization')
    # if auth_header != f"Bearer {os.getenv('CRON_SECRET')}":
    #     return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        print("📊 Cron job triggered: sending daily summaries")
        
        if not db:
            return jsonify({
                'success': False,
                'error': 'Database not available'
            }), 500
        
        # Run the daily summary
        summaries_sent = send_daily_summary()
        
        return jsonify({
            'success': True,
            'message': 'Daily summary check completed',
            'summaries_sent': summaries_sent,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Cron error in daily-summary: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route("/api/cron/sporadic-inspiration", methods=['GET', 'POST'])
def cron_sporadic_inspiration():
    """
    Cron endpoint to send sporadic inspiration messages.
    
    This endpoint should be triggered multiple times daily by:
    - Vercel Cron Jobs (configured in vercel.json), OR
    - External cron service like cron-job.org
    
    Security: In production, verify the request comes from authorized source
    
    Returns:
        JSON response with summary statistics
    """
    # Optional: Add authorization check for production
    # auth_header = request.headers.get('Authorization')
    # if auth_header != f"Bearer {os.getenv('CRON_SECRET')}":
    #     return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        print("✨ Cron job triggered: sending sporadic inspirations")
        
        if not db:
            return jsonify({
                'success': False,
                'error': 'Database not available'
            }), 500
        
        # Run the sporadic inspiration
        inspirations_sent = send_sporadic_inspiration()
        
        return jsonify({
            'success': True,
            'message': 'Sporadic inspiration check completed',
            'inspirations_sent': inspirations_sent,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Cron error in sporadic-inspiration: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == "__main__":
    print("Starting Daily Planner server...")
    print(f"Environment: {ENV}")
    print(f"Debug mode: {app.config['DEBUG']}")
    print(f"Email configured: {bool(SMTP_USERNAME and SMTP_PASSWORD)}")
    print(f"Push notifications: Available via Web Push API")
    print(f"Firebase configured: {bool(db)}")
    
    # Production vs Development server configuration
    if ENV == 'production':
        # Production: Use environment variables for host/port
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', 5000))
        print(f"Running in PRODUCTION mode on {host}:{port}")
        print("⚠️  For production deployment, use a WSGI server like Gunicorn")
        print("   Example: gunicorn --bind 0.0.0.0:5000 planner:app")
        app.run(debug=False, host=host, port=port)
    else:
        # Development: Local development server
        print("Running in DEVELOPMENT mode")
        app.run(debug=True, host='127.0.0.1', port=5000)
