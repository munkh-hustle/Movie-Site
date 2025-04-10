import os
import logging
import json
import io
import asyncio
from telegram.error import RetryAfter
from PIL import Image
from datetime import datetime, timedelta
from telegram import InputMediaPhoto
from telegram import Message, Chat, User
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin ID - replace with your actual admin ID
ADMIN_ID = 7905267896

# User activity log file
SUBSCRIPTIONS_FILE = 'db/subscriptions.json'  # Active subscriptions
SUBSCRIPTION_LOGS_FILE = 'db/subscription_logs.json'  # Historical logs
USER_ACTIVITY_FILE = 'db/user_activity.json'  # store basic user info
CHAT_LOG_FILE = 'db/chat_logs.json'          # For chat logs
PHOTO_LOG_FILE = 'db/photo_logs.json'        # For photo logs
VIDEO_LOG_FILE = 'db/video_logs.json'        # For video delivery logs
BLOCKED_USERS_FILE = 'db/blocked_users.json'
USER_BALANCES_FILE = 'db/user_balances.json'
MOVIE_DETAILS = 'movie-details.json'
LINK = 'https://munkh-hustle.github.io/Movie-Site/'

# Subscription prices
SUBSCRIPTION_PRICES = {
    '1_month': {
        'single': 5000,
        'all': 10000
    },
    '3_months': {
        'single': 10000,
        'all': 25000
    },
    '6_months': {
        'single': 25000,
        'all': 75000
    }
}

CATEGORIES = ['movielex', 'animelex', 'bl', 'gl', 'seriallex']

# Dictionary to store video IDs and names
video_db = {}

def load_video_db():
    """Load video database from movie-details.json file"""
    global video_db
    try:
        with open(MOVIE_DETAILS, 'r', encoding='utf-8') as f:
            video_data = json.load(f)
            # Create a simplified mapping of title to file_id for backward compatibility
            video_db = {title: data['file_id'] for title, data in video_data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        video_db = {}
        # Initialize with empty movie-details.json if it doesn't exist
        with open(MOVIE_DETAILS, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)

load_video_db()

def load_user_balances():
    """Load user balances from JSON file"""
    try:
        with open(USER_BALANCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert old format to new format if needed
            for user_id, value in data.items():
                if isinstance(value, int):
                    data[user_id] = {'balance': value, 'subscription': None}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_balances(balances):
    """Save user balances to JSON file"""
    with open(USER_BALANCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(balances, f, indent=2)

def get_user_balance(user_id):
    """Get a user's current balance"""
    balances = load_user_balances()
    return balances.get(str(user_id), {}).get('balance', 5000)  # Default balance is 5000

def deduct_user_balance(user_id, amount):
    """Deduct from user's balance"""
    balances = load_user_balances()
    user_id_str = str(user_id)
    user_data = balances.setdefault(user_id_str, {'balance': 5000, 'subscription': None})
    if user_data['balance'] >= amount:
        user_data['balance'] -= amount
        save_user_balances(balances)
        return True
    return False

def add_user_balance(user_id, amount):
    """Add to user's balance"""
    balances = load_user_balances()
    user_id_str = str(user_id)
    user_data = balances.setdefault(user_id_str, {'balance': 5000, 'subscription': None})
    user_data['balance'] += amount
    save_user_balances(balances)

def load_user_activity():
    """Load basic user info from file"""
    try:
        with open(USER_ACTIVITY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def save_user_activity(activity_data):
    """Save basic user info to file"""
    with open(USER_ACTIVITY_FILE, 'w', encoding='utf-8') as f:
        json.dump(activity_data, f, indent=2)

def load_blocked_users():
    """Load blocked users from JSON file"""
    try:
        with open(BLOCKED_USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_blocked_users(blocked_users):
    """Save blocked users to JSON file"""
    with open(BLOCKED_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(blocked_users, f, indent=2)

def is_user_blocked(user_id):
    """Check if user is blocked"""
    blocked_users = load_blocked_users()
    user_blocked = str(user_id) in blocked_users
    
    if user_blocked:
        user_data = blocked_users.get(str(user_id), {})
        return not user_data.get('unblocked')
    return False

def block_user(user_id, username, first_name):
    """Block a user from receiving more videos"""
    blocked_users = load_blocked_users()
    blocked_users[str(user_id)] = {
        'username': username,
        'first_name': first_name,
        'blocked_at': datetime.now().isoformat(),
        'unblocked': False
    }
    save_blocked_users(blocked_users)

def record_user_activity(user_id, username, first_name, last_name, video_name):
    """Update basic user info and log video delivery"""
    # Update basic user info
    activity_data = load_user_activity()
    user_id_str = str(user_id)
    
    if user_id_str not in activity_data:
        activity_data[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name
        }
        save_user_activity(activity_data)
    
    # Log the video delivery (this will create the user entry in video logs if needed)
    log_sent_video(user_id, video_name)

def load_video_data():
    """Load video metadata from movie-details.json file"""
    try:
        with open(MOVIE_DETAILS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading movie-details.json: {e}")
        return {}
    
def save_video_data(video_data):
    """Save video metadata to movie-details.json file"""
    with open(MOVIE_DETAILS, 'w', encoding='utf-8') as f:
        json.dump(video_data, f, indent=2)

def sync_video_data():
    """
    This function is simplified since we're only using one file now
    Just ensures the video_db mapping is up to date
    """
    try:
        video_data = load_video_data()
        # Update video_db with current file_ids
        global video_db
        video_db = {title: data['file_id'] for title, data in video_data.items()}
        return True
    except Exception as e:
        logger.error(f"Error syncing video data: {e}")
        return False

def log_user_message(user_id, username, first_name, text, chat_type):
    """Save user messages to chat_logs.json"""
    logs = load_chat_logs()
    user_id_str = str(user_id)
    
    if user_id_str not in logs:
        logs[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'messages': []
        }
    
    logs[user_id_str]['messages'].append({
        'timestamp': datetime.now().isoformat(),
        'text': text,
        'chat_type': chat_type
    })
    
    save_chat_logs(logs)

def unblock_user(user_id):
    """Unblock a user and reset their video count"""
    blocked_users = load_blocked_users()
    if str(user_id) in blocked_users:
        blocked_users[str(user_id)]['unblocked'] = True
        blocked_users[str(user_id)]['unblocked_at'] = datetime.now().isoformat()
        save_blocked_users(blocked_users)
        return True
    return False

def log_sent_video(user_id, video_name):
    """Log successfully sent videos in video_logs.json"""
    logs = load_video_logs()
    user_id_str = str(user_id)
    
    if user_id_str not in logs:
        # Get user info from user_activity if available
        activity_data = load_user_activity()
        user_data = activity_data.get(user_id_str, {})
        
        logs[user_id_str] = {
            'username': user_data.get('username', ''),
            'first_name': user_data.get('first_name', ''),
            'deliveries': []
        }
    
    logs[user_id_str]['deliveries'].append({
        'timestamp': datetime.now().isoformat(),
        'video_name': video_name,
        'status': 'sent'
    })
    
    save_video_logs(logs)

def log_user_photo(user_id, username, first_name, photo_file_id, caption=None):
    """Save user photo submissions to photo_logs.json"""
    logs = load_photo_logs()
    user_id_str = str(user_id)
    
    if user_id_str not in logs:
        logs[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'photos': []
        }
    
    logs[user_id_str]['photos'].append({
        'timestamp': datetime.now().isoformat(),
        'photo_file_id': photo_file_id,
        'caption': caption
    })
    
    save_photo_logs(logs)

def load_chat_logs():
    """Load chat logs from file"""
    try:
        with open(CHAT_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_chat_logs(logs):
    """Save chat logs to file"""
    with open(CHAT_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2)

def load_photo_logs():
    """Load photo logs from file"""
    try:
        with open(PHOTO_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_photo_logs(logs):
    """Save photo logs to file"""
    with open(PHOTO_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2)

def load_video_logs():
    """Load video delivery logs from file"""
    try:
        with open(VIDEO_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_video_logs(logs):
    """Save video delivery logs to file"""
    with open(VIDEO_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2)

def has_user_paid_for_video(user_id, video_name):
    """Check if user has already paid for this video"""
    video_logs = load_video_logs()
    user_id_str = str(user_id)
    
    if user_id_str not in video_logs:
        return False
    
    # Check if this video has already been delivered to the user
    for delivery in video_logs[user_id_str].get('deliveries', []):
        if delivery['video_name'] == video_name:
            return True
    return False

def get_user_subscription(user_id):
    """Get user's active subscription"""
    subscriptions = load_subscriptions()
    user_id_str = str(user_id)
    
    if user_id_str not in subscriptions:
        return None
        
    subscription = subscriptions[user_id_str]
    end_date = datetime.fromisoformat(subscription['end_date'])
    
    # Check if subscription is still active
    if datetime.now() < end_date:
        return subscription
    else:
        # Subscription expired, remove it
        del subscriptions[user_id_str]
        save_subscriptions(subscriptions)
        return None

def activate_subscription(user_id, category, duration, bypass_balance_check=False):
    """Activate a subscription for user"""
    balances = load_user_balances()
    subscriptions = load_subscriptions()
    user_id_str = str(user_id)
    
    if duration not in ['1_month', '3_months', '6_months']:
        return False
        
    if category == 'all':
        price = SUBSCRIPTION_PRICES[duration]['all']
    else:
        price = SUBSCRIPTION_PRICES[duration]['single']
    
    # Get user balance (initialize if doesn't exist)
    user_balance = balances.setdefault(user_id_str, {'balance': 5000}).get('balance', 5000)
    
    # Only check balance if not bypassing (for admin commands)
    if not bypass_balance_check and user_balance < price:
        return False
    
    # Calculate start and end dates
    start_date = datetime.now()
    months = int(duration.split('_')[0])
    end_date = start_date + timedelta(days=30*months)
    
    # Create subscription record
    subscription_data = {
        'category': category,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'duration': duration,
        'price': price,
        'activated_by_admin': bypass_balance_check
    }
    
    # Store subscription
    subscriptions[user_id_str] = subscription_data
    save_subscriptions(subscriptions)
    
    # Log the action
    log_subscription_action(
        user_id,
        'activated',
        {
            'category': category,
            'duration': duration,
            'price': price,
            'end_date': end_date.isoformat()
        }
    )
    
    # Only deduct balance if not bypassing
    if not bypass_balance_check:
        balances[user_id_str]['balance'] = user_balance - price
        save_user_balances(balances)
    
    return True

def load_subscriptions():
    """Load active subscriptions from file"""
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_subscriptions(subscriptions):
    """Save active subscriptions to file"""
    with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(subscriptions, f, indent=2)

def load_subscription_logs():
    """Load subscription history logs"""
    try:
        with open(SUBSCRIPTION_LOGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_subscription_logs(logs):
    """Save subscription history logs"""
    with open(SUBSCRIPTION_LOGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2)

def log_subscription_action(user_id, action, details):
    """Record a subscription action in the logs"""
    logs = load_subscription_logs()
    user_id_str = str(user_id)
    
    if user_id_str not in logs:
        logs[user_id_str] = []
    
    logs[user_id_str].append({
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'details': details
    })
    
    save_subscription_logs(logs)

async def subscription_history(update: Update, context: CallbackContext) -> None:
    """View subscription history for a user (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /subhistory <user_id>")
        return
    
    try:
        user_id = context.args[0]
        logs = load_subscription_logs()
        
        if user_id not in logs or not logs[user_id]:
            await update.message.reply_text(f"No subscription history found for user {user_id}")
            return
            
        # Get user info
        activity_data = load_user_activity()
        user_info = activity_data.get(user_id, {})
        
        message = [
            f"📜 Subscription history for {user_info.get('first_name', 'Unknown')} "
            f"(@{user_info.get('username', 'N/A')}, ID: {user_id}):"
        ]
        
        for log in logs[user_id]:
            timestamp = datetime.fromisoformat(log['timestamp']).strftime('%Y-%m-%d %H:%M')
            message.append(
                f"\n🕒 {timestamp} - {log['action'].upper()}\n"
                f"Details: {json.dumps(log['details'], indent=2, ensure_ascii=False)}"
            )
        
        await update.message.reply_text('\n'.join(message))
        
    except Exception as e:
        logger.error(f"Error viewing subscription history: {e}")
        await update.message.reply_text("An error occurred while fetching history.")

async def view_subscriptions(update: Update, context: CallbackContext) -> None:
    """View all active subscriptions (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    subscriptions = load_subscriptions()
    now = datetime.now()
    active_subs = []
    
    for user_id, sub_data in subscriptions.items():
        end_date = datetime.fromisoformat(sub_data['end_date'])
        if now < end_date:  # Only show active subscriptions
            # Get user info from activity logs
            activity_data = load_user_activity()
            user_info = activity_data.get(user_id, {})
            
            active_subs.append({
                'user_id': user_id,
                'username': user_info.get('username', 'N/A'),
                'first_name': user_info.get('first_name', 'N/A'),
                'subscription': sub_data,
                'days_left': (end_date - now).days
            })
    
    if not active_subs:
        await update.message.reply_text("No active subscriptions found.")
        return
    
    # Sort by days remaining
    active_subs.sort(key=lambda x: x['days_left'])
    
    message = ["📋 Active Subscriptions:"]
    for sub in active_subs:
        message.append(
            f"\n👤 User: {sub['first_name']} (@{sub['username']}, ID: {sub['user_id']})\n"
            f"📌 Category: {sub['subscription']['category']}\n"
            f"⏳ Duration: {sub['subscription']['duration']}\n"
            f"💰 Price: {sub['subscription']['price']}\n"
            f"📅 Start: {datetime.fromisoformat(sub['subscription']['start_date']).strftime('%Y-%m-%d')}\n"
            f"📅 End: {datetime.fromisoformat(sub['subscription']['end_date']).strftime('%Y-%m-%d')}\n"
            f"⏱️ Days left: {sub['days_left']}\n"
            f"🛠️ Activated by admin: {'Yes' if sub['subscription'].get('activated_by_admin') else 'No'}"
        )
    
    await update.message.reply_text('\n'.join(message))

async def set_subscription(update: Update, context: CallbackContext) -> None:
    """Set subscription for a user (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /subscription <user_id> <months> <category>\n\n"
            "Example: /subscription 12345678 1 gl\n\n"
            "Categories: movielex, animelex, bl, gl, seriallex, all\n"
            "Months: 1, 3, or 6"
        )
        return
    
    try:
        user_id = int(context.args[0])
        months = int(context.args[1])
        category = context.args[2].lower()
        
        # Validate months
        if months not in [1, 3, 6]:
            await update.message.reply_text("Invalid duration. Must be 1, 3, or 6 months.")
            return
            
        # Validate category
        if category not in CATEGORIES and category != 'all':
            await update.message.reply_text(
                f"Invalid category. Valid categories are: {', '.join(CATEGORIES)}, all"
            )
            return
            
        duration = f"{months}_month{'s' if months > 1 else ''}"
        
        # Activate subscription with balance check bypass for admin
        if activate_subscription(user_id, category, duration, bypass_balance_check=True):
            await update.message.reply_text(
                f"✅ Subscription activated for user {user_id}:\n"
                f"Category: {category}\n"
                f"Duration: {months} month{'s' if months > 1 else ''}\n\n"
                f"New balance: {get_user_balance(user_id)}"
            )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 Таны төлбөр баталгаажлаа!\n\n"
                         f"Таны захиалга: {category} ({months} month{'s' if months > 1 else ''})\n\n"
                         f"{LINK} хаягаар кино үзэх боломжтой."
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")
        else:
            await update.message.reply_text(
                "❌ Failed to activate subscription. Please check the parameters."
            )
            
    except ValueError:
        await update.message.reply_text("Invalid user ID or months. Must be numbers.")

async def add_balance(update: Update, context: CallbackContext) -> None:
    """Add balance to a user (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Admin only.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addbalance <user_id> <amount>")
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        
        add_user_balance(user_id, amount)
        
        await update.message.reply_text(
            f"✅ Added {amount} to user {user_id}. New balance: {get_user_balance(user_id)}"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Таны баланс шинэчлэгдлээ! Шинэ үлдэгдэл: {get_user_balance(user_id)}\n\n"
                     f"{LINK} хаягаар кино үзэх боломжтой."
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id}: {e}")
            await update.message.reply_text(f"Added balance but couldn't notify user: {e}")
        
    except ValueError:
        await update.message.reply_text("Invalid user ID or amount. Must be numbers.")

async def user_photos(update: Update, context: CallbackContext) -> None:
    """Show photos sent by a specific user (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /userphotos <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        photo_logs = load_photo_logs()
        user_id_str = str(user_id)
        
        if user_id_str not in photo_logs:
            await update.message.reply_text(f"No photos found for user {user_id}.")
            return
        
        photos = photo_logs[user_id_str].get('photos', [])
        if not photos:
            await update.message.reply_text(f"No photos found for user {user_id}.")
            return
        
        await update.message.reply_text(f"📸 Photos sent by user {user_id}:")
        
        for photo in photos:
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo['photo_file_id'],
                    caption=f"Timestamp: {photo['timestamp']}\nCaption: {photo.get('caption', 'None')}"
                )
                await asyncio.sleep(1)  # Small delay to avoid rate limits
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                await update.message.reply_text(f"Failed to send one of the photos. Error: {str(e)}")
        
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")
    except Exception as e:
        logger.error(f"Error in user_photos: {e}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

async def balance(update: Update, context: CallbackContext) -> None:
    """Check user balance"""
    user = update.effective_user
    balance = get_user_balance(user.id)
    
    await update.message.reply_text(
        f"Таны үлдэгдэл: {balance}\n\n"
        "Цэнэглэх: Хаан банк О.МӨНХ-ЭРДЭНЭ 5926271236\n"
        "Гүйлгээний утга: утасны дугаар\n"
        "Шилжүүлснийхээ дараа төлбөр төлсөн дэлгэцийн зургаа дарж ийшээ явуулна уу."
    )

async def _send_broadcast(context: CallbackContext):
    job = context.job
    message = job.data['message']
    activity_data = load_user_activity()

    success = 0
    failed = 0

    for user_id_str in activity_data:
        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=message
            )
            success += 1
        except RetryAfter as e:
            # Handle flood limits
            await asyncio.sleep(e.retry_after)
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=message
            )
            success += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {user_id_str}: {e}")

    # Notify admin of results
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📢 Broadcast results:\n✅ Success: {success}\n❌ Failed: {failed}"
    )

async def schedule_broadcast(update: Update, context: CallbackContext):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /schedulebroadcast <YYYY-MM-DD> <HH:MM> <message>\n"
            "Example: /schedulebroadcast 2023-12-25 10:00 'Merry Christmas!'"
        )
        return

    try:
        # Parse datetime
        date_str = context.args[0]
        time_str = context.args[1]
        message = ' '.join(context.args[2:])
        scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        # Schedule the job
        context.job_queue.run_once(
            callback=_send_broadcast,
            when=scheduled_time,
            data={'message': message},
            name=f"broadcast_{scheduled_time}"
        )

        await update.message.reply_text(
            f"✅ Broadcast scheduled for {scheduled_time}!\n"
            f"Message: {message}"
        )

    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid date/time format. Use YYYY-MM-DD HH:MM.\nError: {e}")

async def send_message_to_user(update: Update, context: CallbackContext) -> None:
    """Send a message to a specific user (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /sendmessage <user_id> <message>\n\n"
            "Example: /sendmessage 12345678 Hello, this is a test message"
        )
        return
    
    try:
        user_id = int(context.args[0])
        message = ' '.join(context.args[1:])
        
        # Try to send the message
        await context.bot.send_message(
            chat_id=user_id,
            text=message
        )
        
        await update.message.reply_text(f"Message sent to user {user_id}")
        
        # Log this action
        log_user_message(
            user_id=update.effective_user.id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            text=f"Admin sent message to {user_id}: {message}",
            chat_type=update.effective_chat.type
        )
        
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")
    except Exception as e:
        logger.error(f"Error sending message to user: {e}")
        await update.message.reply_text(
            f"Failed to send message to user. Error: {str(e)}"
        )

async def handle_photo(update: Update, context: CallbackContext) -> None:
    """Handle general photo submissions"""
    user = update.effective_user
    log_user_photo(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        photo_file_id=update.message.photo[-1].file_id,
        caption=update.message.caption
    )
    await update.message.reply_text("Photo received and logged!")

async def update_metadata(update: Update, context: CallbackContext) -> None:
    """Update video metadata (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /updatemeta <video_name> <field> <value>\n\n"
            "Example: /updatemeta brokeback-mountain-2005 description \"A story about...\"\n"
            "Available fields: title_name, year, genre, duration, rating, description, "
            "director, cast, release, poster, category"
        )
        return
    
    video_name = context.args[0]
    field = context.args[1].lower()
    value = ' '.join(context.args[2:])
    
    # Load video data
    video_data = load_video_data()
    
    if video_name not in video_data:
        await update.message.reply_text(f"Video '{video_name}' not found.")
        return
    
    # Validate field
    valid_fields = {
        'title_name', 'year', 'genre', 'duration', 'rating', 
        'description', 'director', 'cast', 'release', 'poster', 'category'
    }
    
    if field not in valid_fields:
        await update.message.reply_text(
            f"Invalid field '{field}'. Valid fields are: {', '.join(valid_fields)}"
        )
        return
    
    # Special handling for numeric fields
    if field == 'year':
        try:
            value = int(value)
        except ValueError:
            await update.message.reply_text("Year must be a number.")
            return
    elif field == 'rating':
        try:
            value = float(value)
        except ValueError:
            await update.message.reply_text("Rating must be a number.")
            return
    
    # Update the field
    video_data[video_name][field] = value
    save_video_data(video_data)
    
    await update.message.reply_text(
        f"✅ Updated {field} for '{video_name}':\n\n{value}"
    )

async def handle_screenshot(update: Update, context: CallbackContext) -> None:
    """Handle payment screenshot submissions"""
    user = update.effective_user

    try:
        # Record the photo submission
        log_user_photo(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            photo_file_id=update.message.photo[-1].file_id,
            caption=update.message.caption
        )

        # Notify user
        await update.message.reply_text(
            "Дэлгэцний зураг хүлээг авлаа!\n"
            "Админ шалгах хүртэл түр хүлээнэ үү.\n"
            f"Таны дугаар: {user.id}\n\n"
            f"Баланс нэмэгдсэний дараа {LINK} хаягаар кино үзэх боломжтой болно."
        )
                
        # Forward to admin with instructions
        caption = (f"🆕 Payment screenshot from @{user.username or user.first_name} (ID: {user.id})\n"
                  f"Current balance: {get_user_balance(user.id)}\n"
                  f"User message: {update.message.caption or 'No caption'}\n\n"
                  f"Use /subscription {user.id} <months> <category> to set subscription\n"
                  f"Or /addbalance {user.id} <amount> to add funds")
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption
        )

    except Exception as e:
        logger.error(f"Error handling screenshot: {e}")
        await update.message.reply_text(
            "❌ Error processing your screenshot. Please try again."
        )

async def send_video_with_limit_check(update: Update, context: CallbackContext, user, video_name):
    """Handle video sending with balance checks"""
    # Get video price
    video_data = load_video_data()
    if video_name not in video_data:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Кино олдсонгүй."
        )
        return False
    
    # Check if user has active subscription
    subscription = get_user_subscription(user.id)
    if subscription:
        now = datetime.now()
        expires = datetime.fromisoformat(subscription['expires'])
        video_category = video_data[video_name].get('category', 'other')
        
        if now < expires and (subscription['category'] == 'all' or 
                            subscription['category'] == video_category):
            # Subscription covers this video
            try:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_db[video_name],
                    protect_content=True,
                    caption=f"Таны үзэхгийг хүссэн кино энэ байна. (Subscription active)"
                )
                log_sent_video(user.id, video_name)
                return True
            except Exception as e:
                logger.error(f"Error sending video: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Кино илгээхэд алдаа гарлаа."
                )
                return False

    video_price = video_data[video_name].get('price', 0)
    
    # Check if user has already paid for this video
    if has_user_paid_for_video(user.id, video_name):
        # User has already paid, just send the video without deducting balance
        try:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_db[video_name],
                protect_content=True,
                caption=f"Таны үзэхгийг хүссэн кино энэ байна. Үлдэгдэл: {get_user_balance(user.id)}"
            )
            log_sent_video(user.id, video_name)
            return True
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Кино илгээхэд алдаа гарлаа."
            )
            return False
    
    # First time watching this video - check balance and deduct
    user_balance = get_user_balance(user.id)

    if user_balance < video_price:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Таны үлдэгдэл хүрэлцэхгүй байна. Киноны үнэ: {video_price}, Таны үлдэгдэл: {user_balance}\n\n"
            "Үргэлжлүүлэн үзэхийг хүсвэл хэдэн кино үзмээр байна:\n"
            "Тэр тоогоороо төлбөр төлнө үү:\n\n"
            "1 кино = 1500 төгрөг (Movielex)\n"
            "1 кино = 1000 төгрөг (Seriallex)\n"
            "1 аниме = 500 төгрөг (Animelex)\n\n"
            "🏦Данс Хаан банк:\nО.МӨНХ-ЭРДЭНЭ 5926271236\n\n"
            "👀Гүйлгээний утга:\nөөрийнхөө утасны дугаар\n\n"
            "📍📍Шилжүүлснийхээ дараа төлбөр төлсөн дэлгэцийн зургаа дарж ийшээ явуулна уу.\n\n"
            "🫡🤗Хэрвээ зураг явуулсан бол 1 хоногийн дотор баталгаажих болноо. Та түр хүлээнэ үү🫡🤗\n\n"
            "⚠️⚠️Зураг явуулаагүй бол шалгах гэж нэлээн удаж магадгүй. Анхаарна уу.\n"
        )
        return False
    
    # Deduct balance only if this is the first time watching
    if not deduct_user_balance(user.id, video_price):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Алдаа гарлаа. Төлбөр хасагдаагүй байна."
        )
        return False
    
    # Send the video
    try:
        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=video_db[video_name],
            protect_content=True,
            caption=f"Таны үзэхгийг хүссэн кино энэ байна. Үлдэгдэл: {get_user_balance(user.id)}"
        )
        log_sent_video(user.id, video_name)
        
        # Record the transaction
        record_user_activity(
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            video_name
        )
        
        return True
    except Exception as e:
        # Refund if sending failed
        add_user_balance(user.id, video_price)
        logger.error(f"Error sending video: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Кино илгээхэд алдаа гарлаа. Төлбөр буцаагдлаа."
        )
        return False
    
async def notify_admin_limit_reached(context: CallbackContext, user):
    """Notify admin when a user reaches the limit"""
    keyboard = [
        [InlineKeyboardButton("✅ Unblock User", callback_data=f"unblock_{user.id}")],
        [InlineKeyboardButton("❌ Keep Blocked", callback_data=f"keep_blocked_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚨 User @{user.username or user.first_name} (ID: {user.id}) "
                 f"has reached video limit.\n\n"
                 f"Please wait for their payment screenshot or manually verify.\n"
                 f"Username: @{user.username}\n"
                 f"First Name: {user.first_name}\n"
                 f"User ID: {user.id}",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

async def unblock_command(update: Update, context: CallbackContext) -> None:
    """Unblock a user by ID (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unblock <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        if unblock_user(user_id):
            await update.message.reply_text(f"User {user_id} has been unblocked.")
            # Notify the user
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉Таны зөвшөөрсөн байна. {LINK} киногоо үргэлжлүүлэн үзнэ үү"
            )
        else:
            await update.message.reply_text(f"User {user_id} wasn't blocked.")
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Log all user messages"""
    user = update.effective_user
    message = update.effective_message
    
    # Check if admin is setting a balance for a user
    if is_admin(update) and 'awaiting_payment_approval' in context.user_data:
        try:
            amount = int(message.text)
            user_id = context.user_data['awaiting_payment_approval']
            
            # Add balance
            add_user_balance(user_id, amount)
            
            await update.message.reply_text(
                f"✅ {amount} added to user {user_id}'s balance. New balance: {get_user_balance(user_id)}"
            )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 Таны баланс шинэчлэгдлээ! Шинэ үлдэгдэл: {get_user_balance(user_id)}\n\n"
                         f"{LINK} хаягаар кино үзэх боломжтой."
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")
            
            # Clear the awaiting state
            del context.user_data['awaiting_payment_approval']
            return
            
        except ValueError:
            await update.message.reply_text("Please enter a valid number for the amount.")
            return
    
    # Existing message logging functionality
    if message.text and not message.text.startswith('/'):
        log_user_message(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            text=message.text,
            chat_type=update.effective_chat.type
        )

async def start(update: Update, context: CallbackContext) -> None:
    """Handle /start command with video requests"""
    user = update.effective_user
    video_name = None 
    
    if context.args and context.args[0].startswith('video_'):
        video_name = context.args[0][6:]
        if video_name in video_db:
            await update.message.reply_text("Кино илгээж байна...хүлээнэ үү🫡")
            success = await send_video_with_limit_check(update, context, user, video_name)
            if not success:
                return
    elif context.args and context.args[0].startswith('trailer_'):
        video_name = context.args[0][8:]
        video_data = load_video_data()
        
        if video_name not in video_data:
            await update.message.reply_text(f"Кино олдсонгүй ээ 😣😖😭😵‍💫 {LINK}")
            return
            
        trailers = video_data[video_name].get('trailer_ids', [])
        
        if not trailers:
            await update.message.reply_text(f"Энэ кинонд трейлер олдсонгүй. 😣😖😭😵‍💫 {LINK}")
            return
            
        await update.message.reply_text("Трейлерүүд илгээж байна...хүлээнэ үү 🫡")
        
        # Send all trailers
        for trailer_id in trailers[:5]:  # Limit to 5 trailers
            try:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=trailer_id,
                    protect_content=True
                )
                await asyncio.sleep(1)  # Small delay between trailers
            except Exception as e:
                logger.error(f"Error sending trailer: {e}")
                continue
                
        # Ask if they want to watch the full movie
        keyboard = [
            [InlineKeyboardButton("Тийм", callback_data=f"video_{video_name}")],
            [InlineKeyboardButton("Үгүй", callback_data="trailer_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Киног бүрэн үзэх үү?",
            reply_markup=reply_markup
        )
        return

            
    if video_name is not None:  # Only show this if we were actually looking for a video
        await update.message.reply_text(f"Өшөө олон кино үзэх бол {LINK}")
    else:
        await update.message.reply_text(f'Сайн байна уу? {user.first_name}!. {LINK} руу орж киногоо сонгоно уу.')

async def blocked_users(update: Update, context: CallbackContext) -> None:
    """Show list of blocked users (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    blocked_users = load_blocked_users()
    if not blocked_users:
        await update.message.reply_text("No users are currently blocked.")
        return
    
    message = ["🚫 Blocked Users:"]
    keyboard = []

    for user_id, data in blocked_users.items():
        if data.get('unblocked'):
            status = "✅ Unblocked"
        else:
            status = "❌ Blocked"
            # Add unblock button for blocked users
            keyboard.append([
                InlineKeyboardButton(
                    f"Unblock {data.get('first_name', 'User')} (ID: {user_id})",
                    callback_data=f"unblock_{user_id}"
                )
            ])
        
        message.append(
            f"\n👤 {data.get('first_name', 'Unknown')} "
            f"(ID: {user_id}) - @{data.get('username', 'no_username')}\n"
            f"Blocked at: {data.get('blocked_at')}\n"
            f"Status: {status}"
        )

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        '\n'.join(message),
        reply_markup=reply_markup
    )

def is_admin(update: Update):
    """Check if user is admin"""
    return update.effective_user.id == ADMIN_ID

async def addvideo(update: Update, context: CallbackContext) -> None:
    """Add video to database (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /addvideo <name> <price> (reply to a video)")
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.video:
        try:
            video_name = ' '.join(context.args[:-1])
            price = int(context.args[-1])
        except (IndexError, ValueError):
            await update.message.reply_text("Please specify a valid price as the last argument")
            return
        
        video_file_id = update.message.reply_to_message.video.file_id
        
        # Load existing data
        video_data = load_video_data()

        # Create or update the video entry
        if video_name not in video_data:
            video_data[video_name] = {
                "title": video_name,
                "title_name": video_name,  # Default title_name same as title
                "year": datetime.now().year,
                "genre": "Unknown",
                "duration": "Unknown",
                "rating": 0.0,
                "description": "No description available",
                "director": "Unknown",
                "cast": "Unknown",
                "release": datetime.now().strftime('%B %Y'),
                "poster": "",
                "category": "other",
                "file_id": video_file_id,
                "trailer_ids": [],
                "date_added": datetime.now().isoformat(),
                "price": price
            }
        else:
            # Just update the file_id if video exists
            video_data[video_name]['file_id'] = video_file_id
            video_data[video_name]['price'] = price

        # Save the updated data
        save_video_data(video_data)
        
        # Update the video_db mapping
        video_db[video_name] = video_file_id

        await update.message.reply_text(f"Video '{video_name}' added successfully with price {price}!")
    else:
        await update.message.reply_text("Please reply to a video message with this command.")

async def addtrailer(update: Update, context: CallbackContext) -> None:
    """Add trailer to a video (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /addtrailer <video_name> (reply to a video)")
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.video:
        video_name = ' '.join(context.args)
        trailer_file_id = update.message.reply_to_message.video.file_id
        
        video_data = load_video_data()
        
        if video_name not in video_data:
            await update.message.reply_text(f"Video '{video_name}' not found. Add it first with /addvideo")
            return
            
        # Initialize trailers array if not exists
        if 'trailer_ids' not in video_data[video_name]:
            video_data[video_name]['trailer_ids'] = []
            
        # Add the trailer
        video_data[video_name]['trailer_ids'].append(trailer_file_id)
        save_video_data(video_data)
        
        await update.message.reply_text(
            f"✅ Trailer added to '{video_name}'!\n"
            f"Total trailers: {len(video_data[video_name]['trailer_ids'])}"
        )
    else:
        await update.message.reply_text("Please reply to a video message with this command.")


async def sync(update: Update, context: CallbackContext) -> None:
    """Manually sync video data (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if sync_video_data():
        await update.message.reply_text("Video database synchronized successfully!")
    else:
        await update.message.reply_text("No changes needed - databases are already in sync.")

async def video_logs(update: Update, context: CallbackContext) -> None:
    """Show video delivery logs (admin only) from video_logs.json"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    logs = load_video_logs()
    
    # Collect all video delivery logs
    video_counts = {}
    total_sends = 0
    
    for user_id, data in logs.items():
        if 'deliveries' in data:
            for log in data['deliveries']:
                video_name = log['video_name']
                video_counts[video_name] = video_counts.get(video_name, 0) + 1
                total_sends += 1
    
    if not video_counts:
        await update.message.reply_text("No video delivery logs found.")
        return
        
    message = ["📊 Video Delivery Statistics:"]
    message.append(f"\nTotal videos sent: {total_sends}")
    message.append("\nUnique videos sent:")
    
    for video, count in sorted(video_counts.items(), key=lambda x: x[1], reverse=True):
        message.append(f"{video}: {count}")
        
    await update.message.reply_text('\n'.join(message))

async def rename(update: Update, context: CallbackContext) -> None:
    """Rename video in database (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /rename <old_name> <new_name>")
        return
    
    old_name = ' '.join(context.args[:-1])
    new_name = context.args[-1]

    # Load video data
    video_data = load_video_data()
    
    if old_name in video_data:
        # Update video_data
        video_data[new_name] = video_data.pop(old_name)
        # Update title if it matches old name
        if video_data[new_name]['title'] == old_name:
            video_data[new_name]['title'] = new_name
        save_video_data(video_data)
        
        # Update video_db
        video_db[new_name] = video_db.pop(old_name)
        
        # Update video logs
        video_logs = load_video_logs()
        for user_data in video_logs.values():
            for delivery in user_data.get('deliveries', []):
                if delivery['video_name'] == old_name:
                    delivery['video_name'] = new_name
        save_video_logs(video_logs)
        
        await update.message.reply_text(f"Video renamed from '{old_name}' to '{new_name}'")
    else:
        await update.message.reply_text(f"Video '{old_name}' not found.")

async def delete(update: Update, context: CallbackContext) -> None:
    """Delete video from database (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /delete <name>")
        return
    
    video_name = ' '.join(context.args)
    
    # Load video data
    video_data = load_video_data()
    
    if video_name in video_data:
        # Remove from video_data
        del video_data[video_name]
        save_video_data(video_data)
        
        # Remove from video_db
        if video_name in video_db:
            del video_db[video_name]
        
        await update.message.reply_text(f"Video '{video_name}' deleted successfully!")
    else:
        await update.message.reply_text(f"Video '{video_name}' not found.")

async def list_videos(update: Update, context: CallbackContext) -> None:
    """List all available videos with details"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ")
        return
    
    video_data = load_video_data()
    if not video_data:
        await update.message.reply_text("Кино одсонгүй.")
        return
    
    # Group by category if requested
    if context.args and context.args[0] == 'bycategory':
        categories = {}
        for name, data in video_data.items():
            category = data.get('category', 'other')
            if category not in categories:
                categories[category] = []
            categories[category].append(name)
        
        message = ["📺 Videos by Category:"]
        for category, videos in categories.items():
            message.append(f"\n\n🎬 {category.upper()}:")
            for video in sorted(videos):
                message.append(f"- {video}")
        
        await update.message.reply_text('\n'.join(message))
        return
    
    # Default listing
    keyboard = []
    for name, data in sorted(video_data.items()):
        # Show title_name if available, otherwise title
        display_name = data.get('title', name)
        keyboard.append([InlineKeyboardButton(display_name, callback_data=f"video_{name}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Available videos:', reply_markup=reply_markup)

async def button(update: Update, context: CallbackContext) -> None:
    """Handle button presses"""
    query = update.callback_query
    await query.answer()

    try:
        # Keep only the video and unblock button handling
        if query.data.startswith('video_'):
            video_name = query.data[6:]
            if video_name in video_db:
                user = query.from_user
                try:
                    success = await send_video_with_limit_check(update, context, user, video_name)
                    if not success:
                        await query.edit_message_text(text="Кино үзэх эрх дууслаа.")
                except Exception as e:
                    logger.error(f"Error sending video: {e}")
                    await context.bot.send_message(
                        chat_id=user.id,
                        text="An error occurred while processing your request."
                    )

        elif query.data == 'trailer_no':
            await query.edit_message_text(text="За, дараа үзнэ үү!")   

        elif query.data.startswith('unblock_'):
            user_id = int(query.data[8:])
            if is_admin(update):
                # Remove from blocked_users.json completely
                blocked_users = load_blocked_users()
                if str(user_id) in blocked_users:
                    user_data = blocked_users.pop(str(user_id))
                    save_blocked_users(blocked_users)
                    
                    try:
                        await query.edit_message_text(
                            text=f"✅ User {user_data.get('first_name', 'Unknown')} "
                                 f"(ID: {user_id}) has been unblocked."
                        )
                    except Exception as e:
                        logger.error(f"Error editing message: {e}")
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"✅ User {user_data.get('first_name', 'Unknown')} "
                                 f"(ID: {user_id}) has been unblocked."
                        )
                    
                    # Notify the unblocked user
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🎉 Та үргэлжлүүлэн кино үзэх боломжтой боллоо. {LINK} орно уу"
                        )
                    except Exception as e:
                        logger.error(f"Error notifying unblocked user: {e}")
                
        elif query.data.startswith('keep_blocked_'):
            user_id = int(query.data[12:])
            if is_admin(update):
                try:
                    await query.edit_message_text(
                        text=f"User (ID: {user_id}) remains blocked."
                    )
                except Exception as e:
                    logger.error(f"Error editing message: {e}")
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"User (ID: {user_id}) remains blocked."
                    )
    except Exception as e:
        logger.error(f"Error handling button press: {e}")
        try:
            if query.message:
                await query.edit_message_text(
                    text="Sorry, an error occurred while processing your request."
                )
        except Exception as edit_error:
            logger.warning(f"Couldn't edit error message, sending new one: {edit_error}")
            if update.effective_user:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="Sorry, an error occurred while processing your request."
                )

async def search_user_messages(update: Update, context: CallbackContext, search_term: str) -> None:
    """Search through user messages in user_activity.json"""
    try:
        # Parse user filter syntax: "user:1234" or "user:@username"
        user_filter = None
        actual_search_term = search_term

        # Check for user: prefix
        if 'user:' in search_term.lower():
            parts = search_term.split('user:', 1)
            user_part = parts[1].split()[0]  # Get the user specifier
            actual_search_term = ' '.join(parts[1].split()[1:]) if len(parts[1].split()) > 1 else ''
            
            # Check if user is ID or username
            if user_part.startswith('@'):
                user_filter = {'username': user_part[1:].lower()}
            else:
                try:
                    user_filter = {'user_id': int(user_part)}
                except ValueError:
                    await update.message.reply_text("Invalid user ID. Use @username or numeric ID")
                    return
            
        if not actual_search_term and not user_filter:
            await update.message.reply_text("Please provide a search term or user filter")
            return

        activity_data = load_user_activity()
        
        # Filter messages containing the search term (case insensitive)
        results = []
        for user_id, data in activity_data.items():
            # Skip if no chat logs
            if 'chat_log' not in data:
                continue
                
            # Apply user filter if specified
            if user_filter:
                if 'user_id' in user_filter and int(user_id) != user_filter['user_id']:
                    continue
                if 'username' in user_filter and data.get('username', '').lower() != user_filter['username']:
                    continue
            
            # Search through chat logs
            for msg in data['chat_log']:
                if actual_search_term and actual_search_term.lower() not in msg.get('text', '').lower():
                    continue
                
                # Add matching messages to results
                results.append({
                    'timestamp': msg['timestamp'],
                    'user_id': user_id,
                    'username': data.get('username'),
                    'first_name': data.get('first_name'),
                    'text': msg['text']
                })
        
        if not results:
            await update.message.reply_text("No matching messages found.")
            return
        
        # Format results with pagination
        response = ["🔍 Search results:"]
        if user_filter:
            response[0] += f" (filtered by user: {user_filter})"
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        
        for i, msg in enumerate(results[:15], 1):  # Show first 15 results
            timestamp = datetime.fromisoformat(msg['timestamp']).strftime('%Y-%m-%d %H:%M')
            response.append(
                f"\n{i}. {timestamp} - @{msg.get('username', '?')} "
                f"({msg.get('first_name', 'Unknown')}):\n"
                f"{msg['text']}"
            )
        
        if len(results) > 15:
            response.append(f"\n\nℹ️ Showing 15 of {len(results)} results.")
        
        # Split long messages to avoid Telegram's message length limit
        full_response = '\n'.join(response)
        for i in range(0, len(full_response), 4000):
            await update.message.reply_text(full_response[i:i+4000])
            
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        await update.message.reply_text("An error occurred while searching messages.")

async def handle_video(update: Update, context: CallbackContext) -> None:
    """Handle video messages"""
    if update.effective_user is None:
        return  # Skip processing if there's no associated user
    
    if is_admin(update):
        await update.message.reply_text(
            "To add this video to the database, reply to it with /addvideo <name>"
        )

async def user_stats(update: Update, context: CallbackContext) -> None:
    """Show user activity statistics (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    # Check if this is a search request
    if context.args and context.args[0].startswith('search:'):
        search_term = ' '.join(context.args)[7:]  # Remove 'search:' prefix
        return await search_user_messages(update, context, search_term)

    video_logs = load_video_logs()
    
    if not video_logs:
        await update.message.reply_text("No user activity recorded yet.")
        return
    
    message = ["📊 User Activity Report:"]
    total_sends = 0
    
    for user_id, data in video_logs.items():
        username = data.get('username', 'unknown')
        video_count = len(data.get('deliveries', []))
        total_sends += video_count
        last_video = data['deliveries'][-1]['video_name'] if data.get('deliveries') else 'none'
        
        message.append(
            f"\n👤 User: {username} (ID: {user_id})\n"
            f"📹 Videos sent: {video_count}\n"
            f"🎬 Last video: {last_video}"
        )
    
    message.append(f"\n\n📈 Total videos sent: {total_sends}")
    message.append("\n\n🔍 Search user messages with: /stats search:<query>")
    
    await update.message.reply_text('\n'.join(message))

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors and send a message to the user"""
    logger.error(msg="Exception while handling update:", exc_info=context.error)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Sorry, an error occurred while processing your request."
        )

async def send_video_to_user(update: Update, context: CallbackContext) -> None:
    """Send a video to a specific user (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /sendvideo <user_id> <video_name>\n\n"
            "Example: /sendvideo 12345678 secret-relationship-1-1"
        )
        return
    
    try:
        user_id = int(context.args[0])
        video_name = ' '.join(context.args[1:])
        
        if video_name not in video_db:
            await update.message.reply_text(f"Video '{video_name}' not found.")
            return
            
        # Send the video directly without using send_video_with_limit_check
        try:
            await context.bot.send_video(
                chat_id=user_id,
                video=video_db[video_name],
                protect_content=True,
                caption="Админаас илгээсэн кино"
            )
            await update.message.reply_text(f"✅ Video '{video_name}' sent to user {user_id}")
            
            # Log this action
            log_user_message(
                user_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                text=f"Admin sent video {video_name} to {user_id}",
                chat_type=update.effective_chat.type
            )
            
        except Exception as e:
            await update.message.reply_text(f"Failed to send to user {user_id}. Error: {str(e)}")
            
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")
    except Exception as e:
        logger.error(f"Error in send_video_to_user: {e}")
        await update.message.reply_text(f"Error: {str(e)}")
            
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")
    except Exception as e:
        logger.error(f"Error sending video to user: {e}")
        await update.message.reply_text(
            f"Failed to send video to user. Error: {str(e)}"
        )

def main() -> None:
    """Start the bot."""
    load_dotenv()
    
    # Load and sync video database at startup
    load_video_db()
    sync_video_data()

    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logger.error("Telegram bot token not found in environment variables")
        return
    
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("sync", sync))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addvideo", addvideo))
    application.add_handler(CommandHandler("rename", rename))
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(CommandHandler("list", list_videos))
    application.add_handler(CommandHandler("stats", user_stats))
    application.add_handler(CommandHandler("blocked", blocked_users))
    application.add_handler(CommandHandler("unblock", unblock_command))
    application.add_handler(CommandHandler("videologs", video_logs))
    application.add_handler(CommandHandler("updatemeta", update_metadata))
    application.add_handler(CommandHandler("sendmessage", send_message_to_user))
    application.add_handler(CommandHandler("schedulebroadcast", schedule_broadcast))
    application.add_handler(CommandHandler("sendvideo", send_video_to_user))
    application.add_handler(CommandHandler("addtrailer", addtrailer))
    application.add_handler(CommandHandler("userphotos", user_photos))
    application.add_handler(CommandHandler("addbalance", add_balance))
    application.add_handler(CommandHandler("balance", balance))    
    application.add_handler(CommandHandler("subscription", set_subscription))
    application.add_handler(CommandHandler("subscriptions", view_subscriptions))
    application.add_handler(CommandHandler("subhistory", subscription_history))

    # Other handlers
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_screenshot))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))

    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()