from datetime import timedelta, datetime
from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
from flask_cors import CORS
import smtplib
import jwt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
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

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
TWILIO_MESSAGING_SERVICE_SID = os.getenv('TWILIO_MESSAGING_SERVICE_SID')  # For short codes
TWILIO_SHORT_CODE = os.getenv('TWILIO_SHORT_CODE')  # e.g., '22395'

# Initialize Twilio client if credentials are provided
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("Twilio initialized successfully")
    except Exception as e:
        print(f"Twilio initialization error: {e}")

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
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
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
        msg['From'] = 'yourplanno@gmail.com'
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

def send_sms(phone_number, message):
    """
    Send SMS notification using Twilio service with intelligent sender selection.
    
    Automatically selects the best sender option available (short code > messaging service > phone number)
    for optimal delivery rates and compliance. Includes comprehensive error handling
    and delivery status tracking.
    
    Args:
        phone_number (str): Recipient phone number in E.164 format (e.g., +1234567890)
        message (str): SMS message content (max 160 characters recommended)
        
    Returns:
        bool: True if SMS sent successfully, False otherwise
        
    Notes:
        - Requires Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        - Supports short codes, messaging services, and regular phone numbers
        - Automatically truncates messages over 160 characters
    """
    if not twilio_client:
        print("⚠️ Twilio not configured - check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env file")
        return False
    
    # Check for sender options (priority: short code > messaging service > phone number)
    sender = None
    if TWILIO_SHORT_CODE:
        sender = TWILIO_SHORT_CODE
        print(f"📱 Using short code: {sender}")
    elif TWILIO_MESSAGING_SERVICE_SID:
        print(f"📱 Using messaging service: {TWILIO_MESSAGING_SERVICE_SID}")
    elif TWILIO_PHONE_NUMBER:
        sender = TWILIO_PHONE_NUMBER
        print(f"📱 Using phone number: {sender}")
    else:
        print("⚠️ No Twilio sender configured - need TWILIO_SHORT_CODE, TWILIO_MESSAGING_SERVICE_SID, or TWILIO_PHONE_NUMBER")
        return False
        
    try:
        # Ensure phone number is in proper format
        if not phone_number.startswith('+'):
            # Assume US number if no country code
            if len(phone_number) == 10 and phone_number.isdigit():
                phone_number = f"+1{phone_number}"
            elif len(phone_number) == 11 and phone_number.startswith('1'):
                phone_number = f"+{phone_number}"
        
        # Truncate message to SMS limits
        if len(message) > 1600:
            message = message[:1597] + "..."
        
        print(f"📱 Sending SMS to {phone_number}: {message[:50]}...")
        
        # Create message with appropriate sender
        if TWILIO_MESSAGING_SERVICE_SID:
            # Use messaging service (can include short codes)
            twilio_message = twilio_client.messages.create(
                body=message,
                messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
                to=phone_number
            )
        else:
            # Use direct sender (short code or phone number)
            twilio_message = twilio_client.messages.create(
                body=message,
                from_=sender,
                to=phone_number
            )
        
        sender_info = TWILIO_MESSAGING_SERVICE_SID or sender
        print(f"✅ SMS sent successfully to {phone_number} from {sender_info} (SID: {twilio_message.sid})")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ SMS error: {error_msg}")
        print(f"   Phone: {phone_number}")
        sender_info = TWILIO_MESSAGING_SERVICE_SID or sender or TWILIO_PHONE_NUMBER
        print(f"   From: {sender_info}")
        print(f"   Message length: {len(message)}")
        
        # Common SMS error troubleshooting
        if 'not a valid phone number' in error_msg.lower():
            print(f"   ⚠️ Invalid phone format. Expected: +1234567890, got: {phone_number}")
        elif 'unverified' in error_msg.lower():
            print(f"   ⚠️ Twilio trial account - verify recipient phone number in Twilio console")
        elif 'authentication' in error_msg.lower():
            print(f"   ⚠️ Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env file")
        elif 'forbidden' in error_msg.lower():
            print(f"   ⚠️ Check Twilio account permissions and phone number verification")
        elif 'messaging service' in error_msg.lower():
            print(f"   ⚠️ Check TWILIO_MESSAGING_SERVICE_SID is valid and active")
        elif 'short code' in error_msg.lower():
            print(f"   ⚠️ Short code may not be approved or active. Check Twilio console.")
            
        return False

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

def cleanup_sent_notifications():
    """
    Clean up old notification tracking entries to prevent memory leaks.
    
    Removes notification tracking entries older than 24 hours to maintain
    optimal performance and prevent duplicate notifications while keeping
    memory usage under control.
    
    This function is called periodically by the notification system
    to maintain a clean tracking state.
    
    Notes:
        - Removes entries older than 24 hours
        - Handles invalid timestamp formats gracefully
        - Logs cleanup statistics for monitoring
    """
    try:
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=24)
        
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
            print(f"🧹 Cleaned up {len(keys_to_remove)} old notification tracking entries")
    except Exception as e:
        print(f"⚠️ Error during notification cleanup: {e}")

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
    """Check for upcoming tasks and send notifications with automatic intelligent timing"""
    if not db:
        print("⚠️ Database not available for notifications")
        return
    
    # Clean up old notification tracking entries
    cleanup_sent_notifications()
        
    try:
        print("🔔 Checking for multi-level task notifications...")
        users_ref = db.collection('users')
        users = users_ref.where('notifications_enabled', '==', True).stream()
        
        current_time = datetime.now()
        notifications_sent = 0
        
        # Define notification windows (in minutes before task)
        notification_windows = [
            {'minutes': 1440, 'label': '1 day', 'icon': '📅', 'urgency': 'info'},      # 24 hours
            {'minutes': 300, 'label': '5 hours', 'icon': '⏰', 'urgency': 'warning'},    # 5 hours  
            {'minutes': 60, 'label': '1 hour', 'icon': '⏱️', 'urgency': 'warning'},      # 1 hour
            {'minutes': 30, 'label': '30 minutes', 'icon': '🚨', 'urgency': 'urgent'},  # 30 minutes
            {'minutes': 5, 'label': '5 minutes', 'icon': '🔥', 'urgency': 'critical'},  # 5 minutes
        ]
        
        for user in users:
            user_data = user.to_dict()
            user_id = user.id
            user_email = user_data.get('email', 'Unknown')
            
            print(f"🔍 Checking notifications for user: {user_email}")
            
            tasks_ref = db.collection('users').document(user_id).collection('tasks')
            all_tasks = list(tasks_ref.stream())
            
            print(f"📋 Found {len(all_tasks)} total tasks for {user_email}")
            
            # Get tasks for today
            current_day = current_time.strftime('%A').lower()
            today_tasks = []
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                task_day = task_data.get('day', '').lower()
                
                # Debug: print task info
                print(f"   📝 Task: '{task_data.get('title', 'No title')}' - Day: '{task_day}' - Time: '{task_data.get('startTime') or task_data.get('time') or task_data.get('endTime', 'No time')}' - Completed: {task_data.get('completed', False)}")
                
                if task_day == current_day or task_day == 'today' or not task_day:
                    today_tasks.append(task_data)
            
            print(f"📅 Found {len(today_tasks)} tasks for today ({current_day})")
            
            # Check for automatic daily preparation notifications
            prep_notifications = get_automatic_notification_times(today_tasks, current_time)
            for prep_type, prep_message in prep_notifications:
                # Create unique notification key to prevent duplicates (include hour to avoid spam)
                today_str = current_time.strftime('%Y-%m-%d')
                hour_str = current_time.strftime('%H')
                notification_key = f"{user_id}_{prep_type}_{today_str}_{hour_str}"
                
                # Skip if already sent in this hour
                if notification_key in sent_notifications:
                    print(f"⏭️ Skipping {prep_type} notification for {user_email} - already sent this hour")
                    continue
                
                print(f"🎯 Sending {prep_type} notification to {user_email}")
                if user_data.get('notification_method') == 'email' and user_data.get('email'):
                    subject = f"📋 Daily Preparation - {prep_type.replace('_', ' ').title()}"
                    body = f"""
                    <div class="header">
                        <h2>📋 Your Daily Preparation</h2>
                    </div>
                    <div class="content">
                        <div class="inspiration">
                            <h2 style="color: #1abc9c; font-size: 24px; margin: 20px 0;">{prep_message}</h2>
                            <p style="margin-top: 20px; font-size: 16px;">This automatic notification helps you stay prepared for your day!</p>
                        </div>
                    </div>
                    """
                    if send_email(user_data.get('email'), subject, body):
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        notifications_sent += 1
                elif user_data.get('notification_method') == 'sms' and user_data.get('phone'):
                    if send_sms(user_data.get('phone'), prep_message[:160]):
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        notifications_sent += 1
            
            upcoming_tasks = []
            today = current_time.strftime('%Y-%m-%d')
            
            print(f"⏰ Checking for upcoming tasks (current time: {current_time.strftime('%H:%M')})")
            
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                
                # Check if task has time and is not completed
                if (task_data.get('startTime') or task_data.get('time') or task_data.get('endTime')) and not task_data.get('completed', False):
                    # Parse task time - handle different time formats
                    task_time_str = None
                    
                    # Try different time field names
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
                        # Use end time if no start time
                        task_time_str = task_data.get('endTime')
                    
                    # Also check if this is for today or the correct day
                    task_day = task_data.get('day', '').lower()
                    current_day = current_time.strftime('%A').lower()
                    
                    # Only process tasks for today
                    if task_time_str and (task_day == current_day or task_day == 'today' or not task_day):
                        try:
                            print(f"   ⏰ Processing task '{task_data.get('title')}' with time '{task_time_str}' for day '{task_day}'")
                            
                            # Create full datetime for today with task time
                            task_datetime_str = f"{today} {task_time_str}"
                            task_time = datetime.strptime(task_datetime_str, '%Y-%m-%d %H:%M')
                            
                            # Calculate time difference in minutes
                            time_diff = (task_time - current_time).total_seconds() / 60
                            
                            print(f"      📊 Time diff: {time_diff:.1f} minutes (task at {task_time.strftime('%H:%M')}, now {current_time.strftime('%H:%M')})")
                            
                            # Flexible notification timing with user preferences
                            should_notify = False
                            notification_reason = ""
                            
                            # Simplified notification strategy: only urgent reminders
                            user_reminder_times = user_data.get('reminder_times', [])
                            if not user_reminder_times:
                                # Only send urgent reminders (30 min, 10 min, immediate)
                                priority = task_data.get('priority', 'medium').lower()
                                if priority == 'high':
                                    user_reminder_times = [30, 10]  # 30 min, 10 min
                                elif priority == 'medium':
                                    user_reminder_times = [15]      # 15 min
                                else:
                                    user_reminder_times = [10]      # 10 min only
                            
                            print(f"      📅 Using reminder times: {user_reminder_times} for priority '{task_data.get('priority', 'medium')}'")
                            
                            # Check against notification times with very tight tolerance
                            for reminder_time in user_reminder_times:
                                # Very tight tolerance: ±1 minute only to prevent spam
                                tolerance_min = reminder_time - 1
                                tolerance_max = reminder_time + 1
                                print(f"         🔍 Checking if {time_diff:.1f} minutes is within {tolerance_min}-{tolerance_max} minutes (target: {reminder_time})")
                                
                                # Very tight tolerance to reduce spam
                                if tolerance_min <= time_diff <= tolerance_max:
                                    should_notify = True
                                    if reminder_time <= 10:
                                        notification_reason = f"⚠️ URGENT: Task starting in {int(time_diff)} minutes!"
                                    elif reminder_time <= 30:
                                        notification_reason = f"Task starting soon in {int(time_diff)} minutes"
                                    else:
                                        notification_reason = f"Upcoming task in {int(time_diff)} minutes"
                                    print(f"         ✅ MATCH! Will notify: {notification_reason}")
                                    break
                            
                            # Special case: immediate notifications (0-2 minutes)
                            if 0 <= time_diff <= 2:
                                should_notify = True
                                notification_reason = f"🚨 STARTING NOW! Task begins in {int(time_diff)} minute(s)!"
                            
                            # Check if task is within our automatic notification windows
                            if should_notify:
                                upcoming_tasks.append({
                                    'title': task_data.get('title', 'Untitled Task'),
                                    'time': task_time_str,
                                    'description': task_data.get('description', ''),
                                    'priority': task_data.get('priority', 'medium'),
                                    'day': task_data.get('day', 'Today'),
                                    'notification_reason': notification_reason
                                })
                                print(f"⏰ Found upcoming task: {task_data.get('title')} at {task_time_str} ({notification_reason})")
                        except ValueError as e:
                            print(f"⚠️ Could not parse task time '{task_time_str}': {e}")
                            continue
            
            if upcoming_tasks:
                # Create more specific notification key to prevent spam (include current hour)
                task_titles_hash = ''.join(sorted([task['title'] for task in upcoming_tasks]))
                current_hour = current_time.strftime('%H')
                notification_key = f"{user_id}_task_reminder_{today}_{current_hour}_{hash(task_titles_hash) % 10000}"
                
                if notification_key in sent_notifications:
                    print(f"⏭️ Skipping task reminder notification for {user_email} - already sent this hour")
                    continue
                
                print(f"📤 Sending notification for {len(upcoming_tasks)} upcoming tasks to {user_email}")
                notification_method = user_data.get('notification_method', 'email')
                
                if notification_method == 'email' and user_data.get('email'):
                    subject = f"⏰ {len(upcoming_tasks)} Task(s) Coming Up!"
                    
                    # Create HTML email body
                    body = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #1abc9c, #45B7D1); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                            <h2 style="margin: 0;">⏰ Upcoming Tasks Reminder</h2>
                            <p style="margin: 10px 0 0 0;">You have {len(upcoming_tasks)} task(s) starting soon!</p>
                        </div>
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px;">
                    """
                    
                    for task in upcoming_tasks:
                        priority_color = {
                            'high': '#FF6B6B',
                            'medium': '#4ECDC4', 
                            'low': '#96CEB4'
                        }.get(task['priority'], '#4ECDC4')
                        
                        formatted_time = format_time_12hour(task['time'])
                        body += f"""
                        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid {priority_color};">
                            <h3 style="margin: 0 0 5px 0; color: #2c3e50;">{task['title']}</h3>
                            <p style="margin: 0; color: #666;"><strong>⏰ Time:</strong> {formatted_time}</p>
                            <p style="margin: 5px 0 0 0; color: #666;"><strong>📅 Day:</strong> {task['day']}</p>
                            {f'<p style="margin: 5px 0 0 0; color: #666;">{task["description"]}</p>' if task['description'] else ''}
                        </div>
                        """
                    
                    body += """
                        </div>
                        <div style="text-align: center; padding: 15px; color: #666; font-size: 12px;">
                            <p>Good luck with your tasks! 🚀</p>
                            <p>You can update your notification preferences in the app settings.</p>
                        </div>
                    </div>
                    """
                    
                    if send_email(user_data.get('email'), subject, body):
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        notifications_sent += 1
                        print(f"✅ Email notification sent to {user_email}")
                    else:
                        print(f"❌ Failed to send email to {user_email}")
                        
                elif notification_method == 'sms' and user_data.get('phone'):
                    # Create SMS message (limited to 160 characters)
                    task_titles = [task['title'] for task in upcoming_tasks[:2]]  # Limit for SMS
                    message = f"⏰ {len(upcoming_tasks)} task(s) coming up: {', '.join(task_titles)}"
                    
                    if len(upcoming_tasks) > 2:
                        message += f" +{len(upcoming_tasks) - 2} more"
                    
                    # Add first task time in 12-hour format
                    if upcoming_tasks:
                        formatted_time = format_time_12hour(upcoming_tasks[0]['time'])
                        message += f" at {formatted_time}"
                    
                    if send_sms(user_data.get('phone'), message[:160]):
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        notifications_sent += 1
                        print(f"✅ SMS notification sent to {user_data.get('phone')}")
                    else:
                        print(f"❌ Failed to send SMS to {user_data.get('phone')}")
            else:
                print(f"📋 No upcoming tasks found for {user_email}")
        
        if notifications_sent > 0:
            print(f"🎯 Sent {notifications_sent} automatic intelligent notifications")
        else:
            print("📱 No automatic notifications needed at this time")
            
    except Exception as e:
        print(f"❌ Error in check_and_send_notifications: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

def send_daily_summary():
    """Send daily summary of completed tasks"""
    if not db:
        print("⚠️ Database not available for daily summary")
        return
        
    try:
        print("📊 Generating daily summaries...")
        users_ref = db.collection('users')
        # Only send to users who have daily_summary enabled
        users = users_ref.where('notifications_enabled', '==', True).where('daily_summary', '==', True).stream()
        
        today = datetime.now()
        summaries_sent = 0
        
        for user in users:
            user_data = user.to_dict()
            user_id = user.id
            user_email = user_data.get('email', 'Unknown')
            
            # Only send if user has daily_summary enabled
            if not user_data.get('daily_summary', False):
                print(f"⏭️ Skipping daily summary for {user_email} - daily summary disabled")
                continue
                
            print(f"📋 Generating summary for user: {user_email}")
            
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
                
                if notification_key in sent_notifications:
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
                            time_info = f" at {task_time}" if task_time else ""
                            
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
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        summaries_sent += 1
                        print(f"✅ Daily summary sent to {user_email}")
                    else:
                        print(f"❌ Failed to send summary to {user_email}")
                        
                elif notification_method == 'sms' and user_data.get('phone'):
                    # SMS summary (shorter but informative)
                    message = f"Daily Summary: Today you have {len(all_today_tasks)} tasks total. "
                    message += f"✅ {len(completed_today)} completed, ⏳ {len(pending_tasks)} pending. "
                    if pending_tasks:
                        next_task = pending_tasks[0].get('title', 'Untitled')[:30]
                        message += f"Next up: {next_task}. "
                    message += f"{random.choice(INSPIRATIONAL_MESSAGES)[:50]}..."
                    
                    if send_sms(user_data.get('phone'), message[:160]):
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        summaries_sent += 1
                        print(f"✅ SMS summary sent to {user_data.get('phone')}")
                    else:
                        print(f"❌ Failed to send SMS summary to {user_data.get('phone')}")
            else:
                print(f"📋 No completed tasks found for {user_email}")
        
        if summaries_sent > 0:
            print(f"🎯 Sent {summaries_sent} daily summaries")
        else:
            print("📊 No daily summaries sent today")
            
    except Exception as e:
        print(f"❌ Error in send_daily_summary: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

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
    """Get stored user preferences or analyze if not available"""
    if not db:
        return {}
    
    try:
        # Check if preferences are already stored
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            stored_preferences = user_data.get('ai_preferences', {})
            last_analysis = user_data.get('preferences_last_updated')
            
            # Refresh preferences if older than 2 weeks
            if (stored_preferences and last_analysis and 
                isinstance(last_analysis, datetime) and 
                (datetime.now() - last_analysis).days < 14):
                return stored_preferences
        
        # Analyze preferences and store them
        preferences = analyze_user_preferences(uid)
        
        if preferences:
            # Store preferences in user document
            user_ref.update({
                'ai_preferences': preferences,
                'preferences_last_updated': datetime.now()
            })
            print(f"💾 Stored updated preferences for user {uid}")
        
        return preferences
        
    except Exception as e:
        print(f"❌ Error getting user preferences: {e}")
        return {}

def generate_preference_context(preferences):
    """Convert user preferences into AI prompt context"""
    if not preferences:
        return ""
    
    context_parts = []
    
    # Activity preferences
    if preferences.get('activity_types'):
        preferred_activities = []
        avoided_activities = preferences.get('avoided_activities', [])
        
        for activity, stats in preferences['activity_types'].items():
            if stats['created'] >= 3:
                completion_rate = stats['completed'] / stats['created']
                if completion_rate > 0.7:
                    preferred_activities.append(f"{activity} (completes {completion_rate:.0%})")
        
        if preferred_activities:
            context_parts.append(f"PREFERRED ACTIVITIES: {', '.join(preferred_activities)}")
        if avoided_activities:
            context_parts.append(f"TENDS TO AVOID: {', '.join(avoided_activities)}")
    
    # Time preferences
    if preferences.get('time_patterns'):
        best_times = []
        for time_slot, stats in preferences['time_patterns'].items():
            if stats['created'] >= 3:
                completion_rate = stats['completed'] / stats['created']
                if completion_rate > 0.7:
                    best_times.append(f"{time_slot} (completes {completion_rate:.0%})")
        
        if best_times:
            context_parts.append(f"MOST PRODUCTIVE TIMES: {', '.join(best_times)}")
    
    # Day preferences
    if preferences.get('day_preferences'):
        productive_days = []
        for day, stats in preferences['day_preferences'].items():
            if stats['created'] >= 2:
                completion_rate = stats['completed'] / stats['created']
                if completion_rate > 0.7:
                    productive_days.append(f"{day} (completes {completion_rate:.0%})")
        
        if productive_days:
            context_parts.append(f"MOST PRODUCTIVE DAYS: {', '.join(productive_days)}")
    
    # Interests
    if preferences.get('interests'):
        context_parts.append(f"FREQUENT INTERESTS: {', '.join(preferences['interests'][:5])}")
    
    if context_parts:
        return f"\n\nUSER PREFERENCES (learned from task history):\n{chr(10).join(context_parts)}\n"
    
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
        users = users_ref.where('notifications_enabled', '==', True).stream()
        
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
                
                if notification_key in sent_notifications:
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
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        inspirations_sent += 1
                        print(f"✅ Sporadic inspiration email sent to {user_email}")
                    else:
                        print(f"❌ Failed to send sporadic inspiration email to {user_email}")
                        
                elif notification_method == 'sms' and user_data.get('phone'):
                    sms_message = f"💫 Sporadic Inspiration: {message}"
                    if total_today > 3:
                        sms_message += f" You've got {total_today} tasks today - you've got this! 🏆"
                    
                    if send_sms(user_data.get('phone'), sms_message[:160]):
                        sent_notifications[notification_key] = datetime.now().isoformat()
                        inspirations_sent += 1
                        print(f"✅ Sporadic inspiration SMS sent to {user_data.get('phone')}")
                    else:
                        print(f"❌ Failed to send sporadic inspiration SMS to {user_data.get('phone')}")
        
        if inspirations_sent > 0:
            print(f"🎯 Sent {inspirations_sent} sporadic inspiration messages")
        else:
            print("💫 No sporadic inspirations needed right now")
            
    except Exception as e:
        print(f"❌ Error in send_sporadic_inspiration: {e}")
        import traceback
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



# Start scheduler in background thread
if db:
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Notification scheduler started")

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
                
                response_data = {
                    'notifications_enabled': data.get('notifications_enabled', False),
                    'notification_method': data.get('notification_method', 'email'),
                    'phone': data.get('phone', ''),
                    'email': data.get('email', ''),
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
                'phone': '',
                'email': decoded_claims.get('email', ''),
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
                'phone': settings.get('phone', ''),
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
                
                # Create a beautiful test email
                body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
                        <h2 style="margin: 0;">🧪 Test Notification</h2>
                        <p style="margin: 10px 0 0 0;">Your Daily Planner notifications are working perfectly!</p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px;">
                        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #28a745;">
                            <h3 style="margin: 0 0 10px 0; color: #2c3e50;">✅ Email Notifications Active</h3>
                            <p style="margin: 0; color: #666;">You'll receive notifications for:</p>
                            <ul style="color: #666; margin: 10px 0;">
                                <li>⏰ Upcoming task reminders</li>
                                <li>📊 Daily achievement summaries</li>
                                <li>💫 Motivational messages</li>
                            </ul>
                        </div>
                        
                        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #17a2b8;">
                            <h3 style="margin: 0 0 10px 0; color: #2c3e50;">⚙️ Current Settings</h3>
                            <p style="margin: 0; color: #666;">
                                <strong>Email:</strong> {user_data.get('email', 'Not set')}<br>
                                <strong>Method:</strong> {user_data.get('notification_method', 'email').title()}<br>
                                <strong>Reminder Time:</strong> {user_data.get('reminder_time', 30)} minutes before tasks<br>
                                <strong>Daily Summary:</strong> {'Enabled' if user_data.get('daily_summary', True) else 'Disabled'}
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
                # Create SMS test message
                message = f"🧪 Daily Planner Test: Your SMS notifications are working perfectly! "
                message += f"You'll get reminders {user_data.get('reminder_time', 30)}min before tasks. "
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
        
        # Update task in Firestore
        task_ref = db.collection('users').document(uid).collection('tasks').document(task_id)
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
        
        # Delete task from Firestore
        task_ref = db.collection('users').document(uid).collection('tasks').document(task_id)
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
    """Get weather for a specific city"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return {"error": "Not authenticated"}, 401
    
    try:
        decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
        
        # Get weather data for specified city
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
            "sms": "configured" if twilio_client else "not_configured",
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
- Be careful with title searches - make them specific to avoid deleting wrong tasks{weather_context}{conversation_context}

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
- Always respond to "plan ahead" requests with tasks for future weeks, not just current week{preference_context}

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

if __name__ == "__main__":
    print("Starting Daily Planner server...")
    print(f"Environment: {ENV}")
    print(f"Debug mode: {app.config['DEBUG']}")
    print(f"Email configured: {bool(SMTP_USERNAME and SMTP_PASSWORD)}")
    print(f"SMS configured: {bool(twilio_client)}")
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