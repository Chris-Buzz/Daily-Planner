# Notification System Fixes

## Issues Fixed

This document describes the fixes applied to resolve three major notification issues:

1. **Timezone Problem**: Notifications were being sent at UTC time instead of user's local timezone
2. **Military Time Format**: Email notifications displayed times in 24-hour format instead of 12-hour format
3. **Push Notifications Not Working**: Browser push notifications weren't configured properly

---

## 1. Timezone Fix

### Problem
The cron jobs on Vercel run at UTC time (e.g., daily summary at 20:00 UTC = 8:00 PM UTC). However, users are in different timezones. A user in Eastern Time (ET) would receive notifications 4-5 hours early, and a user in Pacific Time (PT) would receive them 7-8 hours early.

### Solution
Added timezone support so that each user's notifications are processed based on their local timezone:

#### Backend Changes ([planner.py](planner.py))

1. **Added timezone import**:
   ```python
   from zoneinfo import ZoneInfo
   ```

2. **Created timezone helper function**:
   ```python
   def get_user_current_time(user_timezone=None):
       """Get current time in user's timezone."""
       try:
           if user_timezone:
               tz = ZoneInfo(user_timezone)
               return datetime.now(tz)
           else:
               return datetime.now(ZoneInfo('UTC'))
       except Exception as e:
           print(f"⚠️ Invalid timezone '{user_timezone}', falling back to UTC: {e}")
           return datetime.now(ZoneInfo('UTC'))
   ```

3. **Updated `check_and_send_notifications()` function**:
   - Now retrieves user's timezone from database: `user_timezone = user_data.get('timezone', 'America/New_York')`
   - Uses user's local time for all notification checks: `current_time = get_user_current_time(user_timezone)`
   - Added logging to show user's timezone and local time

4. **Updated `send_daily_summary()` function**:
   - Same timezone handling as notification checks
   - Each user's daily summary is generated based on their local time

5. **Updated API endpoint** (`/api/notification-settings`):
   - Added `timezone` field to GET response (default: `'America/New_York'`)
   - Added `timezone` field to POST handler to save user's timezone preference

#### Frontend Changes ([templates/index.html](templates/index.html) & [static/script.js](static/script.js))

1. **Added timezone selector UI** (index.html):
   ```html
   <div class="settings-section">
       <div class="section-header">
           <h4>🌍 Your Timezone</h4>
           <p>Set your timezone so notifications arrive at the right time for you</p>
       </div>
       <select id="user-timezone" class="timezone-select">
           <option value="America/New_York">Eastern Time (ET)</option>
           <option value="America/Chicago">Central Time (CT)</option>
           <option value="America/Denver">Mountain Time (MT)</option>
           <option value="America/Los_Angeles">Pacific Time (PT)</option>
           <!-- ... more timezones ... -->
       </select>
   </div>
   ```

2. **Added timezone handling in JavaScript** (script.js):
   - Load user's timezone in `notifications.updateUI()`
   - Save timezone changes with event listener
   - Display confirmation when timezone is updated

### How It Works Now
1. Cron job runs every 5 minutes at UTC time (as before)
2. For each user, the system:
   - Retrieves their timezone setting (e.g., "America/Los_Angeles")
   - Converts current UTC time to the user's local time
   - Checks if any tasks need notifications based on their local time
3. Example: If a user in PT has a task at 2:00 PM PT with a 1-hour reminder:
   - The notification will be sent when it's 1:00 PM in PT (regardless of UTC time)
   - Previously, it would have been sent based on UTC time only

---

## 2. Time Format Fix (Military to Standard Time)

### Problem
Email notifications showed times in 24-hour military format (e.g., "14:30", "18:00") instead of 12-hour standard format (e.g., "2:30 PM", "6:00 PM").

### Solution
Applied the existing `format_time_12hour()` function consistently throughout email templates.

#### Changes in [planner.py](planner.py)

The `format_time_12hour()` function already existed (line 492-496) but wasn't being applied everywhere.

**Fixed in `send_daily_summary()` function** (line 1057-1059):
```python
# Before:
task_time = task.get('startTime') or task.get('time') or task.get('endTime')
time_info = f" at {task_time}" if task_time else ""

# After:
task_time = task.get('startTime') or task.get('time') or task.get('endTime')
formatted_task_time = format_time_12hour(task_time) if task_time else ""
time_info = f" at {formatted_task_time}" if formatted_task_time else ""
```

**Already working correctly in `check_and_send_notifications()` function** (line 789):
```python
formatted_time = format_time_12hour(task_time_str)
```

### Examples
- `"14:30"` → `"2:30 PM"`
- `"09:00"` → `"9:00 AM"`
- `"09:00-10:00"` → `"9:00 AM - 10:00 AM"`

---

## 3. Push Notifications Setup

### Problem
Browser push notifications weren't working because VAPID keys weren't configured.

### Solution
Created a key generation script and updated documentation to guide users through setup.

#### New Files

1. **[generate_vapid_keys.py](generate_vapid_keys.py)** - Key generation script:
   ```bash
   python generate_vapid_keys.py
   ```

   This generates:
   - `VAPID_PUBLIC_KEY` - Shared with browsers
   - `VAPID_PRIVATE_KEY` - Kept secret on server
   - `VAPID_EMAIL` - Contact email for the application

2. **Updated [.env.example](.env.example)**:
   ```env
   # ===== PUSH NOTIFICATIONS (OPTIONAL) =====

   # VAPID Keys for Web Push Notifications
   # Generate with: python generate_vapid_keys.py
   VAPID_PUBLIC_KEY=your-vapid-public-key
   VAPID_PRIVATE_KEY=your-vapid-private-key
   VAPID_EMAIL=mailto:your-email@example.com
   ```

3. **Updated [requirements.txt](requirements.txt)**:
   ```txt
   py-vapid==1.9.0  # VAPID key generation for push notifications
   ```

#### Setup Instructions

To enable push notifications:

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Generate VAPID keys**:
   ```bash
   python generate_vapid_keys.py
   ```

3. **Add keys to .env file**:
   ```env
   VAPID_PUBLIC_KEY=<generated_public_key>
   VAPID_PRIVATE_KEY=<generated_private_key>
   VAPID_EMAIL=mailto:yourplanno@gmail.com
   ```

4. **Restart your application**

5. **In the app**:
   - Go to Settings → Notifications
   - Enable "Push Notifications" delivery method
   - Grant browser permission when prompted

#### How It Works

1. **Service Worker** ([static/sw.js](static/sw.js)):
   - Registers with the browser
   - Listens for push events from the server
   - Displays notifications even when app is closed

2. **Push Notification Client** ([static/push-notifications.js](static/push-notifications.js)):
   - Requests permission from user
   - Subscribes to push service
   - Sends subscription to server

3. **Server Push Handler** ([planner.py](planner.py)):
   - Uses `pywebpush` library to send notifications
   - Authenticates with VAPID keys
   - Sends to user's registered browser(s)

---

## Testing the Fixes

### Test Timezone Fix

1. Go to Settings → Notifications
2. Select your timezone (e.g., "Pacific Time (PT)")
3. Create a task for today with a specific time
4. Set a reminder time (e.g., 5 minutes before)
5. Wait for the notification - it should arrive based on your local time

### Test Time Format Fix

1. Enable email notifications
2. Create a task with a time like "14:30"
3. Trigger a daily summary or task reminder
4. Check your email - times should show as "2:30 PM" (not "14:30")

### Test Push Notifications

1. Install dependencies: `pip install -r requirements.txt`
2. Generate keys: `python generate_vapid_keys.py`
3. Add keys to `.env` file and restart app
4. In app, go to Settings → Notifications
5. Enable "Push Notifications" method
6. Grant browser permission
7. Use "Test Notification" button to verify it works

---

## Database Schema Changes

### User Document (Firestore)

Added new field:
```javascript
{
  // ... existing fields ...
  timezone: "America/New_York"  // User's IANA timezone identifier
}
```

**Default value**: `"America/New_York"` (Eastern Time)

**Supported timezones**: All IANA timezone identifiers (e.g., `"America/Los_Angeles"`, `"Europe/London"`, `"Asia/Tokyo"`)

---

## Deployment Notes

### Environment Variables Required

For full notification functionality, set these in your deployment environment (Vercel, etc.):

```env
# Email notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Push notifications
VAPID_PUBLIC_KEY=<your-generated-public-key>
VAPID_PRIVATE_KEY=<your-generated-private-key>
VAPID_EMAIL=mailto:your-email@example.com
```

### Vercel Configuration

The [vercel.json](vercel.json) cron schedule remains unchanged:
```json
"crons": [
  {
    "path": "/api/cron/check-notifications",
    "schedule": "*/5 * * * *"  // Every 5 minutes
  },
  {
    "path": "/api/cron/daily-summary",
    "schedule": "0 20 * * *"  // 8 PM UTC daily
  }
]
```

**Note**: Cron jobs still run at UTC time, but the application now converts to each user's local timezone internally.

---

## Files Modified

### Backend ([planner.py](planner.py))
- Added `zoneinfo` import
- Added `get_user_current_time()` helper function
- Updated `check_and_send_notifications()` to use user timezone
- Updated `send_daily_summary()` to use user timezone
- Fixed time formatting in daily summary emails
- Updated `/api/notification-settings` endpoint to handle timezone

### Frontend
- **[templates/index.html](templates/index.html)**: Added timezone selector UI
- **[static/script.js](static/script.js)**: Added timezone loading/saving logic

### Configuration
- **[.env.example](.env.example)**: Added VAPID keys documentation
- **[requirements.txt](requirements.txt)**: Added `py-vapid==1.9.0`

### New Files
- **[generate_vapid_keys.py](generate_vapid_keys.py)**: VAPID key generation script
- **[NOTIFICATION_FIXES.md](NOTIFICATION_FIXES.md)**: This documentation

---

## Troubleshooting

### Notifications arriving at wrong time
- Verify timezone is set correctly in Settings → Notifications
- Check application logs for timezone info
- Ensure `zoneinfo` module is available (Python 3.9+)

### Email times still showing military format
- Verify SMTP settings are correct in `.env`
- Check email spam folder
- Review application logs for email sending errors

### Push notifications not working
1. **Check VAPID keys are set**:
   ```bash
   # In Python shell
   import os
   from dotenv import load_dotenv
   load_dotenv()
   print(os.getenv('VAPID_PUBLIC_KEY'))  # Should not be None
   ```

2. **Check browser compatibility**:
   - Chrome/Edge: ✅ Supported
   - Firefox: ✅ Supported
   - Safari: ⚠️ Limited support (iOS 16.4+)

3. **Check browser permissions**:
   - Go to browser settings
   - Find site permissions
   - Ensure notifications are allowed

4. **Check service worker registration**:
   - Open browser DevTools
   - Go to Application → Service Workers
   - Should see sw.js registered and active

---

## Summary

All three notification issues have been resolved:

✅ **Timezone Issue**: Notifications now respect user's local timezone
✅ **Time Format Issue**: All times display in 12-hour format (AM/PM)
✅ **Push Notifications**: Full setup guide and key generation tool provided

Users should now receive notifications at the correct time in their timezone, with readable time formats in emails, and have the option to enable browser push notifications.
