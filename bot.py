import os
import logging
import json
import io
import asyncio
from telegram.error import RetryAfter
from PIL import Image
from datetime import datetime
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
USER_ACTIVITY_FILE = 'db/user_activity.json'

BLOCKED_USERS_FILE = 'db/blocked_users.json'
MAX_VIDEOS_BEFORE_BLOCK = 5

USER_LIMITS_FILE = 'db/user_limits.json'

# Dictionary to store video IDs and names
video_db = {}
def load_video_db():
    """Load video database from movie-details.json file"""
    global video_db
    try:
        with open('movie-details.json', 'r', encoding='utf-8') as f:
            video_data = json.load(f)
            # Create a simplified mapping of title to file_id for backward compatibility
            video_db = {title: data['file_id'] for title, data in video_data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        video_db = {}
        # Initialize with empty movie-details.json if it doesn't exist
        with open('movie-details.json', 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)

def save_video_db():
    """This function is kept for backward compatibility but won't do anything"""
    pass

load_video_db()

def load_user_limits():
    """Load user video limits from JSON file"""
    try:
        with open(USER_LIMITS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_limits(limits):
    """Save user video limits to JSON file"""
    with open(USER_LIMITS_FILE, 'w', encoding='utf-8') as f:
        json.dump(limits, f, indent=2)

def set_user_video_limit(user_id, limit):
    """Set a custom video limit for a user"""
    limits = load_user_limits()
    limits[str(user_id)] = limit
    save_user_limits(limits)

def get_user_video_limit(user_id):
    """Get a user's video limit (defaults to MAX_VIDEOS_BEFORE_BLOCK if not set)"""
    limits = load_user_limits()
    return limits.get(str(user_id), MAX_VIDEOS_BEFORE_BLOCK)

def load_user_activity():
    """Load user activity data from file"""
    try:
        with open(USER_ACTIVITY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def save_user_activity(activity_data):
    """Save user activity data to file"""
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
    """Record that a video was sent to a user"""
    activity_data = load_user_activity()
    user_id_str = str(user_id)
    
    if user_id_str not in activity_data:
        activity_data[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'videos': [],
            'chat_log': [],
            'photo_logs': [],
            'video_delivery_log': []
        }
    
    # Keep the videos array for backward compatibility - for unique video
    activity_data[user_id_str]['videos'].append({
        'video_name': video_name,
        'timestamp': datetime.now().isoformat()
    })
    
    # Also log in video_delivery_log / making it comment because it overwrites on user_activity.json
    # activity_data[user_id_str]['video_delivery_log'].append({
    #     'video_name': video_name,
    #     'timestamp': datetime.now().isoformat(),
    #     'status': 'sent'
    # })
    
    save_user_activity(activity_data)

def load_video_data():
    """Load video metadata from movie-details.json file"""
    try:
        with open('movie-details.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading movie-details.json: {e}")
        return {}
    
def save_video_data(video_data):
    """Save video metadata to movie-details.json file"""
    with open('movie-details.json', 'w', encoding='utf-8') as f:
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
    """Save user messages to user_activity.json"""
    activity_data = load_user_activity()
    user_id_str = str(user_id)
    
    if user_id_str not in activity_data:
        activity_data[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'last_name': '',
            'videos': [],
            'chat_log': [],
            'photo_logs': []
        }
    
    # Add message to chat log
    activity_data[user_id_str].setdefault('chat_log', []).append({
        'timestamp': datetime.now().isoformat(),
        'text': text,
        'chat_type': chat_type
    })
    
    save_user_activity(activity_data)

def reset_user_video_count(user_id):
    """Reset a user's video count"""
    activity_data = load_user_activity()
    if str(user_id) in activity_data:
        activity_data[str(user_id)]['videos'] = []
        save_user_activity(activity_data)
        return True
    return False

def unblock_user(user_id):
    """Unblock a user and reset their video count"""
    blocked_users = load_blocked_users()
    if str(user_id) in blocked_users:
        blocked_users[str(user_id)]['unblocked'] = True
        blocked_users[str(user_id)]['unblocked_at'] = datetime.now().isoformat()
        save_blocked_users(blocked_users)
        reset_user_video_count(user_id)  # Reset their video count
        return True
    return False

def log_sent_video(user_id, video_name):
    """Log successfully sent videos in user_activity.json"""
    activity_data = load_user_activity()
    user_id_str = str(user_id)
    
    if user_id_str not in activity_data:
        activity_data[user_id_str] = {
            'username': '',
            'first_name': '',
            'last_name': '',
            'videos': [],
            'chat_log': [],
            'photo_logs': []
        }
    
    # Add video delivery log
    activity_data[user_id_str].setdefault('video_delivery_log', []).append({
        'timestamp': datetime.now().isoformat(),
        'video_name': video_name,
        'status': 'sent'
    })
    
    save_user_activity(activity_data)

def update_payment_status(user_id, status):
    """Update payment status in the database"""
    try:
        with open('lgbtlex/db/payment_submissions.json', 'r+', encoding='utf-8') as f:
            data = json.load(f)
            
        # Find most recent submission from this user
        for submission in reversed(data):
            if submission['user_id'] == user_id:
                submission['status'] = status
                submission['processed_at'] = datetime.now().isoformat()
                break
                
        with open('lgbtlex/db/payment_submissions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")

def save_payment_submission(payment_data):
    """Save payment submission to JSON file"""
    try:
        with open('lgbtlex/db/payment_submissions.json', 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    except FileNotFoundError:
        data = []
    
    data.append(payment_data)
    
    with open('db/payment_submissions.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def log_user_photo(user_id, username, first_name, photo_file_id, caption=None):
    """Save user photo submissions to user_activity.json"""
    activity_data = load_user_activity()
    user_id_str = str(user_id)
    
    if user_id_str not in activity_data:
        activity_data[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'last_name': '',
            'videos': [],
            'chat_log': [],
            'photo_logs': []
        }
    
    # Add photo to photo_logs
    activity_data[user_id_str]['photo_logs'].append({
        'timestamp': datetime.now().isoformat(),
        'photo_file_id': photo_file_id,
        'caption': caption
    })
    
    save_user_activity(activity_data)

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

async def user_limits(update: Update, context: CallbackContext) -> None:
    """View or set user limits (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ болно.")
        return
    
    if len(context.args) >= 2:
        # Setting a new limit
        try:
            user_id = int(context.args[0])
            new_limit = int(context.args[1])
            
            set_user_video_limit(user_id, new_limit)
            await update.message.reply_text(
                f"✅ {user_id} дугаартай хэрэглэгч таныг {new_limit} удаа өөр кино үзэхээр сунгалаа."
            )
        except ValueError:
            await update.message.reply_text("Хэрэглээ: /userlimit <user_id> <limit>")
    else:
        # Viewing limits
        limits = load_user_limits()
        if not limits:
            await update.message.reply_text("No custom limits set.")
            return
            
        message = ["📊 Custom User Limits:"]
        for user_id, limit in limits.items():
            message.append(f"\n👤 User ID: {user_id} - Limit: {limit} videos")
        
        await update.message.reply_text('\n'.join(message))

async def notify_admin_payment_submission(context: CallbackContext, user, file_path):
    """Notify admin about new payment submission"""
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open(file_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo,
                caption=f"🆕 Payment from @{user.username or user.first_name} (ID: {user.id})",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error sending payment notification: {e}")

async def handle_screenshot(update: Update, context: CallbackContext) -> None:
    """Handle payment screenshot submissions"""
    user = update.effective_user

    try:
        # Record the photo submission
        log_user_photo(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            photo_file_id=update.message.photo[-1].file_id,  # Get the highest resolution photo
            caption=update.message.caption
        )

        # Record the submission
        payment_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }

        save_payment_submission(payment_data)

        # Notify user
        await update.message.reply_text(
            "Дэлгэцний зураг хүлээг авлаа!\n"
            "Админ шалгах хүртэл түр хүлээнэ үү.\n"
            f"Таны дугаар: {user.id}"
        )
                
        # Forward to admin with approval buttons
        keyboard = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Create caption for admin
        caption = (f"🆕 Payment from @{user.username or user.first_name} (ID: {user.id})\n"
                  f"Status: {'BLOCKED (reached limit)' if is_user_blocked(user.id) else 'Active'}\n"
                  f"User message: {update.message.caption or 'No caption'}")
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error handling screenshot: {e}")
        await update.message.reply_text(
            "❌ Error processing your screenshot. Please try again."
        )

async def reset_user(update: Update, context: CallbackContext) -> None:
    """Reset a user's video count (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /resetuser <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        if reset_user_video_count(user_id):
            await update.message.reply_text(f"User {user_id}'s video count has been reset.")
        else:
            await update.message.reply_text(f"User {user_id} not found or already has no videos.")
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")

async def send_video_with_limit_check(update: Update, context: CallbackContext, user, video_name):
    """Handle video sending with limit checks"""
    # First check if user is blocked
    if is_user_blocked(user.id):  # This stays the same
        blocked_users = load_blocked_users()
        user_data = blocked_users.get(str(user.id), {})
        if not user_data.get('unblocked'):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Таны үзэх эрх дууссан байна. Хэрвээ төлбөр шилжүүлсэн бол админ мэдээлэл өгтөл түр хүлээнэ үү."
            )
            return False
    
    # Record the activity first
    record_user_activity(
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        video_name
    )
    
    # Check if user reached limit (using their custom limit if set)
    user_limit = get_user_video_limit(user.id)
    activity_data = load_user_activity()
    user_videos = activity_data.get(str(user.id), {}).get('videos', [])
    unique_videos = len({v['video_name'] for v in user_videos})
    
    if unique_videos >= user_limit:
        # Send the video first (with protect_content)
        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=video_db[video_name],
            protect_content=True,
            caption="Таны үзэхгийг хүссэн кино. Энэ байна."
        )
        log_sent_video(user.id, video_name)

        # Then block them and send payment instructions
        block_user(user.id, user.username, user.first_name)
        payment_message = (
            f"⚠️ Та {user_limit} удаа үзэх эрх дууссан байна.\n\n"
            "Үргэлжлүүлэн үзэхийг хүсвэл хэдэн кино үзмээр байна:\n"
            "Тэр тоогоороо төлбөр төлнө үү:\n"
            "1 кино = 1000 төгрөг:\n"
            "🏦 Хаан банк: 5926271236\n\n"
            "Гүйлгээний утга өөрийнхөө утасны дугаар бичнэ:\n"
            "Шилжүүлснийхээ дараа төлбөр төлсөн дэлгэцийн зургаа дарж ийшээ явуулна уу.\n"
            "Админ шалгаж үзээд баталгаажуулах болно. 1 хоногийн дотор хийх болно\n"
            f"{user.id}\n\n"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=payment_message
        )

        await notify_admin_limit_reached(context, user)
        return False
    
    # Send video if under limit (with protected content)
    await context.bot.send_video(
        chat_id=update.effective_chat.id,
        video=video_db[video_name],
        protect_content=True,
        caption="Таны үзэхгийг хүссэн кино. Энэ байна."
    )
    log_sent_video(user.id, video_name)
    return True

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
                 f"has reached the 5 video limit.\n\n"
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
                text="🎉Таны зөвшөөрсөн байна. www.kino.com киногоо үргэлжлүүлэн үзнэ үү"
            )
        else:
            await update.message.reply_text(f"User {user_id} wasn't blocked.")
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Log all user messages"""
    user = update.effective_user
    message = update.effective_message
    
    # Check if admin is setting a limit for a user
    if is_admin(update) and 'awaiting_limit' in context.user_data:
        try:
            new_limit = int(message.text)
            user_id = context.user_data['awaiting_limit']
            
            # Update payment status (again in case it wasn't saved)
            update_payment_status(user_id, 'approved')

            # Unblock user
            unblock_user(user_id)
            reset_user_video_count(user_id)
            
            # Store the custom limit
            set_user_video_limit(user_id, new_limit)

            await update.message.reply_text(
                f"✅ User {user_id} approved with new limit: {new_limit} videos."
            )
            
            # Notify the user
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Таны хүсэлт баталгаажлаа! Та одоо {new_limit} удаа кино үзэх эрхтэй боллоо."
            )
            
            # Clear the awaiting state
            del context.user_data['awaiting_limit']
            return
            
        except ValueError:
            await update.message.reply_text("Please enter a valid number for the limit.")
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
            await update.message.reply_text("Кино илгээж байна...")
            success = await send_video_with_limit_check(update, context, user, video_name)
            if not success:
                return
    elif context.args and context.args[0].startswith('trailer_'):
        video_name = context.args[0][8:]
        video_data = load_video_data()
        
        if video_name not in video_data:
            await update.message.reply_text("Кино олдсонгүй.")
            return
            
        trailers = video_data[video_name].get('trailer_ids', [])
        
        if not trailers:
            await update.message.reply_text("Энэ кинонд трейлер олдсонгүй.")
            return
            
        await update.message.reply_text("Трейлерүүд илгээж байна...")
        
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
        await update.message.reply_text(f"Өшөө олон кино үзэх бол www.kino.com")
    else:
        await update.message.reply_text(f'Сайн байна уу? {user.first_name}!. www.kino.mn руу орж киногоо сонгоно уу.')

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
        await update.message.reply_text("Usage: /addvideo <name> (reply to a video)")
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.video:
        video_name = ' '.join(context.args)
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
                "date_added": datetime.now().isoformat()
            }
        else:
            # Just update the file_id if video exists
            video_data[video_name]['file_id'] = video_file_id

        # Save the updated data
        save_video_data(video_data)
        
        # Update the video_db mapping
        video_db[video_name] = video_file_id

        await update.message.reply_text(f"Video '{video_name}' added successfully!")
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
    """Show video delivery logs (admin only) from user_activity.json"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    activity_data = load_user_activity()
    
    # Collect all video delivery logs
    video_counts = {}
    total_sends = 0
    
    for user_id, data in activity_data.items():
        if 'video_delivery_log' in data:
            for log in data['video_delivery_log']:
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
        
        # Update user activity logs
        activity_data = load_user_activity()
        for user_data in activity_data.values():
            for video in user_data['videos']:
                if video['video_name'] == old_name:
                    video['video_name'] = new_name
        save_user_activity(activity_data)
        
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
        display_name = data.get('title_name', name)
        keyboard.append([InlineKeyboardButton(display_name, callback_data=f"video_{name}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Available videos:', reply_markup=reply_markup)

async def button(update: Update, context: CallbackContext) -> None:
    """Handle button presses"""
    query = update.callback_query

    try:
        await query.answer()

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
                    reset_user_video_count(user_id)
                    
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
                            text="🎉 Та үргэлжлүүлэн кино үзэх боломжтой боллоо. www.kino.com орно уу"
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
        elif query.data.startswith('approve_'):
            user_id = int(query.data[8:])
            if is_admin(update):
                try:
                    # Update payment status
                    update_payment_status(user_id, 'approved')

                    # Unblock user
                    unblock_user(user_id)
                    reset_user_video_count(user_id)

                    # Store user_id in context to use in the next message
                    context.user_data['awaiting_limit'] = user_id

                    try:
                        # Try to edit the original message
                        await query.edit_message_text(
                            text=f"✅ Payment from user ID {user_id} approved.\n"
                                 "Please send the new video limit for this user (e.g., '10')."
                        )
                    except Exception as edit_error:
                        # If editing fails, send a new message
                        logger.error(f"Error editing approval message: {edit_error}")
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"✅ Payment from user ID {user_id} approved.\n"
                                 "Please send the new video limit for this user (e.g., '10')."
                        )


                    # Notify user
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🎉 Таны хүсэлт баталгаажлаа."
                    )

                except Exception as e:
                    logger.error(f"Error approving payment: {e}")
                    try:
                        await query.edit_message_text(
                            text=f"❌ Error approving payment: {str(e)}"
                        )
                    except:
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"❌ Error approving payment: {str(e)}"
                        )


        elif query.data.startswith('reject_'):
            user_id = int(query.data[7:])
            if is_admin(update):
                try:
                    # Update payment status
                    update_payment_status(user_id, 'rejected')

                    # Notify user
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="❌ Таны хүсэлт баталгаажсангүй. Гүйлгээ хийсэн зургаа явуулж баталгаажуулна уу."
                    )

                    try:
                        # Try to edit the original message
                        await query.edit_message_text(
                            text=f"❌ Payment from user ID {user_id} rejected."
                        )
                    except Exception as edit_error:
                        # If editing fails, send a new message
                        logger.warning(f"Couldn't edit message, sending new one: {edit_error}")
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"❌ Payment from user ID {user_id} rejected."
                        )
                except Exception as e:
                    logger.error(f"Error rejecting payment: {e}")
                    try:
                        await query.edit_message_text(
                            text=f"❌ Error rejecting payment: {str(e)}"
                        )
                    except:
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"❌ Error rejecting payment: {str(e)}"
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

    activity_data = load_user_activity()
    
    if not activity_data:
        await update.message.reply_text("No user activity recorded yet.")
        return
    
    message = ["📊 User Activity Report:"]
    total_sends = 0
    
    for user_id, data in activity_data.items():
        username = data.get('username', 'unknown')
        video_count = len(data.get('video_delivery_log', []))
        total_sends += video_count
        last_video = data['video_delivery_log'][-1]['video_name'] if data.get('video_delivery_log') else 'none'
        
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
async def verify_payment(update: Update, context: CallbackContext) -> None:
    """Verify a payment manually (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /verifypayment <user_id> <approve/reject>")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Please specify both user_id and action (approve/reject)")
        return
    
    try:
        user_id = int(context.args[0])
        action = context.args[1].lower()
        
        if action not in ['approve', 'reject']:
            await update.message.reply_text("Action must be either 'approve' or 'reject'")
            return
            
        # Update payment status
        update_payment_status(user_id, 'approved' if action == 'approve' else 'rejected')
        
        if action == 'approve':
            # Unblock user if approved
            unblock_user(user_id)
            reset_user_video_count(user_id)
            await update.message.reply_text(f"✅ Payment from user {user_id} approved and user unblocked.")
            # Notify the user
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 Таны хүсэлт баталгаажлаа. Үргэлжлүүлэн www.kino.com үзэх боломжтой"
            )
        else:
            await update.message.reply_text(f"❌ Payment from user {user_id} rejected.")
            # Notify the user
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Таны хүсэлт баталгаажсангүй. Алдаа гэж үзэж байвал админтай холбогдоно уу."
            )
            
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")
        
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
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("sync", sync))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addvideo", addvideo))
    application.add_handler(CommandHandler("rename", rename))
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(CommandHandler("list", list_videos))
    application.add_handler(CommandHandler("stats", user_stats))
    application.add_handler(CommandHandler("blocked", blocked_users))
    application.add_handler(CommandHandler("unblock", unblock_command))
    application.add_handler(CommandHandler("resetuser", reset_user))
    application.add_handler(CommandHandler("videologs", video_logs))
    application.add_handler(CommandHandler("verifypayment", verify_payment))
    application.add_handler(CommandHandler("userlimit", user_limits))
    application.add_handler(CommandHandler("updatemeta", update_metadata))
    application.add_handler(CommandHandler("sendmessage", send_message_to_user))
    application.add_handler(CommandHandler("schedulebroadcast", schedule_broadcast))
    application.add_handler(CommandHandler("sendvideo", send_video_to_user))
    application.add_handler(CommandHandler("addtrailer", addtrailer))


    # Handle button presses
    application.add_handler(CallbackQueryHandler(button))
    
    # on non command i.e video messages
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_screenshot))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))

    application.add_error_handler(error_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()