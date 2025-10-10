# 🔔 Notification System Fixes for Vercel

## Issues Identified

### 1. **Task Notifications Not Being Sent**
- **Problem**: Tolerance window was too strict (±2.5 minutes)
- **Impact**: Notifications missed even when tasks were found
- **Example**: Task in 60 minutes with 60-min reminder wouldn't trigger if cron ran at 59.5 or 62.5 minutes

### 2. **Daily Summaries Not Working**
- **Problem**: Firestore query was too restrictive with double `.where()` clause
- **Impact**: No users matched the query criteria
- **Root cause**: Some users may not have `daily_summary` field set to `true` explicitly

### 3. **Sporadic Inspirations Failing**
- **Problem**: In-memory `sent_notifications` dict resets on serverless cold starts
- **Impact**: Same message could be sent multiple times per day

### 4. **Notification Tracking Lost Between Invocations**
- **Problem**: Vercel serverless functions don't persist memory between invocations
- **Impact**: Duplicate notifications sent because tracking state was lost

---

## Fixes Applied

### ✅ Fix 1: Wider Tolerance Window for Task Notifications

**Changed:**
```python
# OLD: Too strict
tolerance = 2.5
if abs(time_diff_minutes - reminder_minutes) <= tolerance:

# NEW: More forgiving
tolerance = 5.0
min_boundary = reminder_minutes - tolerance
max_boundary = reminder_minutes + tolerance
if min_boundary <= time_diff_minutes <= max_boundary:
```

**Impact:**
- For a 60-minute reminder, now triggers between 55-65 minutes before task
- Catches notifications even if cron runs slightly early or late
- More reliable with 5-minute cron intervals

---

### ✅ Fix 2: Better Daily Summary User Query

**Changed:**
```python
# OLD: Double where clause (too restrictive)
users = users_ref.where('notifications_enabled', '==', True).where('daily_summary', '==', True).stream()

# NEW: Single where clause, check daily_summary in loop
users = users_ref.where('notifications_enabled', '==', True).stream()
# Then check: if not user_data.get('daily_summary', False): continue
```

**Impact:**
- Works even if `daily_summary` field doesn't exist in Firestore
- Better error handling and logging
- Shows how many users were checked vs sent

---

### ✅ Fix 3: Firestore-Backed Notification Tracking

**Changed:**
```python
# OLD: In-memory only (resets on cold start)
if notification_key in sent_notifications:
    continue
sent_notifications[notification_key] = datetime.now().isoformat()

# NEW: Firestore persistence
if check_notification_sent(notification_key):  # Checks Firestore + memory
    continue
mark_notification_sent(notification_key)  # Saves to Firestore + memory
```

**Impact:**
- Notifications tracked in Firestore `notification_tracking` collection
- Survives serverless cold starts
- Automatic cleanup of entries older than 24 hours

---

### ✅ Fix 4: Enhanced Debug Logging

**Added:**
```python
# Shows why notifications weren't sent
if not notification_sent_for_this_task and len(user_reminder_times) > 0:
    closest_reminder = min(user_reminder_times, key=lambda x: abs(x - time_diff_minutes))
    diff_from_closest = abs(time_diff_minutes - closest_reminder)
    print(f"⏭️ No match. Closest: {closest_reminder} min (diff: {diff_from_closest:.1f} min)")
```

**Impact:**
- Clear visibility into why notifications aren't triggering
- Helps debug timing issues
- Shows distance from nearest reminder threshold

---

### ✅ Fix 5: Return Values for All Cron Functions

**Changed:**
```python
# OLD: No return value
send_daily_summary()

# NEW: Returns count
summaries_sent = send_daily_summary()
return jsonify({
    'summaries_sent': summaries_sent,
    'timestamp': datetime.now().isoformat()
})
```

**Impact:**
- API responses show actual results
- Better monitoring and debugging
- Can track success rates

---

## Expected Behavior After Fixes

### Task Notifications (Every 5 Minutes)
```
🔔 Cron job triggered: checking notifications
🔍 Checking notifications for user: user@example.com
📅 User's reminder times: [300, 60, 30] minutes before tasks
📬 Notification methods: ['email']
📋 Found 10 total tasks for user@example.com
⏰ Task: 'Important Meeting' at 14:00 (62.3 min from now)
   ✅ MATCH! Time diff 62.3 is within reminder window 55.0-65.0 min (target: 60 min)
   ✅ Email notification sent
🎯 Sent 1 task notifications
```

### Daily Summaries (8 PM Daily)
```
📊 Cron job triggered: sending daily summaries
📊 Generating daily summaries...
🔍 Checking notifications for user: user@example.com
📋 Generating summary for user: user@example.com
📋 Found 8 total tasks for today (5 completed)
✅ Daily summary sent to user@example.com
🎯 Sent 3 daily summaries (checked 7 users)
```

### Sporadic Inspirations (5 Times Daily)
```
✨ Cron job triggered: sending sporadic inspirations
💫 Checking for sporadic inspiration sending...
📊 User user@example.com: Found 12 tasks for today (7 completed)
💫 Sending sporadic inspiration to user@example.com (tasks: 12, completed: 58%)
✅ Sporadic inspiration email sent to user@example.com
🎯 Sent 2 sporadic inspiration messages
```

---

## Testing Recommendations

### 1. Test Task Notifications
```bash
# Create a task 65 minutes from now
# Wait for next 5-minute cron cycle
# Check logs for notification send confirmation
```

### 2. Test Daily Summary
```bash
# Manually trigger: https://your-app.vercel.app/api/cron/daily-summary
# Check email for daily summary
# Verify Firestore notification_tracking collection
```

### 3. Test Sporadic Inspiration
```bash
# Manually trigger: https://your-app.vercel.app/api/cron/sporadic-inspiration
# Check email for inspiration message
```

### 4. Check Firestore Tracking
```
Collection: notification_tracking
Documents should have:
- notification_key: "userId_type_date"
- sent_at: timestamp
- created_at: timestamp
```

---

## Vercel Cron Schedule

From `vercel.json`:
```json
{
  "crons": [
    {
      "path": "/api/cron/check-notifications",
      "schedule": "*/5 * * * *"  // Every 5 minutes
    },
    {
      "path": "/api/cron/daily-summary",
      "schedule": "0 20 * * *"  // 8 PM UTC daily
    },
    {
      "path": "/api/cron/sporadic-inspiration",
      "schedule": "30 9,11,14,16,18 * * *"  // 5 times daily
    }
  ]
}
```

**Note**: Times are in UTC. Adjust if needed for user timezone.

---

## Monitoring Tips

1. **Check Vercel Logs**: Go to Vercel dashboard → Deployments → Functions
2. **Check Firestore**: `notification_tracking` collection should have recent entries
3. **Test Endpoints Manually**: Use browser or curl to trigger cron endpoints
4. **Email Delivery**: Check spam folder if emails not appearing

---

## Common Issues & Solutions

### "No notifications needed at this time"
- **Cause**: No tasks within tolerance window of any reminder times
- **Solution**: Check user's `custom_reminder_times` and task schedules
- **Debug**: Look for log line showing time difference and closest reminder

### "Already sent this notification"
- **Cause**: Firestore tracking shows notification was sent recently
- **Solution**: Wait 24 hours or manually delete from `notification_tracking`

### Daily summary not received
- **Cause**: `daily_summary` field not set to `true` in user document
- **Solution**: Update user settings or check Firestore user document

### Duplicate notifications
- **Cause**: Firestore tracking not working properly
- **Solution**: Check Firestore permissions and error logs

---

## Files Modified

1. `planner.py`:
   - `check_and_send_notifications()` - Wider tolerance, better logging
   - `send_daily_summary()` - Better user query, Firestore tracking
   - `send_sporadic_inspiration()` - Firestore tracking
   - All cron endpoints - Return proper statistics

---

## Next Steps

1. ✅ **Deploy to Vercel** - Push changes to trigger deployment
2. ✅ **Monitor Logs** - Watch first few cron cycles
3. ✅ **Test Manually** - Hit cron endpoints directly
4. ✅ **Verify Firestore** - Check `notification_tracking` collection
5. ✅ **Check Emails** - Confirm emails arriving properly

---

**Status**: 🟢 All fixes applied and ready for deployment!
