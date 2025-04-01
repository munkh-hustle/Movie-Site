import os
import logging
import json
import io
from PIL import Image
from datetime import datetime
from telegram import InputMediaPhoto
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
USER_ACTIVITY_FILE = 'user_activity.json'

BLOCKED_USERS_FILE = 'blocked_users.json'
MAX_VIDEOS_BEFORE_BLOCK = 5

USER_LIMITS_FILE = 'user_limits.json'

# Dictionary to store video IDs and names
video_db = {}
def load_video_db():
    """Load video database from JSON file"""
    global video_db
    try:
        with open('video_db.json', 'r', encoding='utf-8') as f:
            video_db = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        video_db = {}

def save_video_db():
    """Save video database to JSON file"""
    with open('video_db.json', 'w', encoding='utf-8') as f:
        json.dump(video_db, f, indent=2)

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
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'videos': []
        }
    
    activity_data[user_id_str]['videos'].append({
        'video_name': video_name,
        'timestamp': datetime.now().isoformat()
    })
    
    save_user_activity(activity_data)

def load_video_data():
    """Load video metadata from JSON file"""
    try:
        with open('video_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading video_data.json: {e}")
        return {}
def sync_video_data():
    """
    Synchronize video_db.json with video_data.json:
    - Adds any missing videos from video_data.json
    - Removes videos that no longer exist in video_data.json
    - Preserves existing file_ids
    """
    try:
        video_data = load_video_data()
        changes_made = False
        
        # Add new videos from video_data.json
        for name, data in video_data.items():
            if name not in video_db and 'file_id' in data:
                video_db[name] = data['file_id']
                logger.info(f"Added new video: {name}")
                changes_made = True
        
        # Remove videos that don't exist in video_data.json
        for name in list(video_db.keys()):
            if name not in video_data:
                del video_db[name]
                logger.info(f"Removed video: {name}")
                changes_made = True
        
        if changes_made:
            save_video_db()
            logger.info("Video database synchronized with video_data.json")
        return changes_made
    except Exception as e:
        logger.error(f"Error syncing video data: {e}")
        return False

def log_user_message(user_id, username, first_name, text, chat_type):
    """Save user messages to a separate log file"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'username': username,
        'first_name': first_name,
        'chat_type': chat_type,
        'text': text
    }
    
    try:
        os.makedirs('logs', exist_ok=True)
        with open('logs/message_logs.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry))  # No comma here
            f.write('\n')  # Ensure each entry is on a new line
    except Exception as e:
        logger.error(f"Failed to log message: {e}")

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
    """Log successfully sent videos with timestamp"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'video_name': video_name,
        'status': 'sent'
    }
    
    try:
        os.makedirs('logs', exist_ok=True)
        with open('logs/video_delivery_log.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry))
            f.write('\n')
    except Exception as e:
        logger.error(f"Failed to log video delivery: {e}")

def update_payment_status(user_id, status):
    """Update payment status in the database"""
    try:
        with open('payment_submissions.json', 'r+', encoding='utf-8') as f:
            data = json.load(f)
            
        # Find most recent submission from this user
        for submission in reversed(data):
            if submission['user_id'] == user_id:
                submission['status'] = status
                submission['processed_at'] = datetime.now().isoformat()
                break
                
        with open('payment_submissions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")

def save_payment_submission(payment_data):
    """Save payment submission to JSON file"""
    try:
        with open('payment_submissions.json', 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    except FileNotFoundError:
        data = []
    
    data.append(payment_data)
    
    with open('payment_submissions.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

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

async def edit_description(update: Update, context: CallbackContext) -> None:
    """Edit video description (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /editdescription <video_name> <new_description>")
        return
    
    video_name = ' '.join(context.args[:-1])
    new_description = context.args[-1]
    
    try:
        # Load current video data
        with open('video_data.json', 'r', encoding='utf-8') as f:
            video_data = json.load(f)
        
        if video_name in video_data:
            # Update description
            video_data[video_name]['description'] = new_description
            
            # Save back to file
            with open('video_data.json', 'w', encoding='utf-8') as f:
                json.dump(video_data, f, indent=2)
            
            await update.message.reply_text(f"✅ Description updated for '{video_name}'")
        else:
            await update.message.reply_text(f"❌ Video '{video_name}' not found.")
            
    except Exception as e:
        logger.error(f"Error editing description: {e}")
        await update.message.reply_text("❌ Error updating description. Check logs for details.")

async def edit_title(update: Update, context: CallbackContext) -> None:
    """Edit video title (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /edittitle <video_name> <new_title>")
        return
    
    video_name = ' '.join(context.args[:-1])
    new_title = context.args[-1]
    
    try:
        # Load current video data
        with open('video_data.json', 'r', encoding='utf-8') as f:
            video_data = json.load(f)
        
        if video_name in video_data:
            # Update title
            video_data[video_name]['title'] = new_title
            
            # Save back to file
            with open('video_data.json', 'w', encoding='utf-8') as f:
                json.dump(video_data, f, indent=2)
            
            await update.message.reply_text(f"✅ Title updated for '{video_name}'")
        else:
            await update.message.reply_text(f"❌ Video '{video_name}' not found.")
            
    except Exception as e:
        logger.error(f"Error editing title: {e}")
        await update.message.reply_text("❌ Error updating title. Check logs for details.")

async def reload_data(update: Update, context: CallbackContext) -> None:
    """Reload video data from disk (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    try:
        load_video_db()
        sync_video_data()
        await update.message.reply_text("Video data reloaded successfully!")
    except Exception as e:
        logger.error(f"Error reloading data: {e}")
        await update.message.reply_text("Error reloading data.")

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
            "Админ шалгах хүртэл түр хүлээнэ үү.\n\n"
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
            
    if video_name is not None:  # Only show this if we were actually looking for a video
        await update.message.reply_text(f"Хэрвээ кино аваагүй бол админтай холбогдоно уу. Үргэлжлүүлэн үзэх бол www.kino.com")
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

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text('Тусламж!')

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
        
        video_db[video_name] = video_file_id
        save_video_db()

        # Update video_data.json if this is a new video
        video_data = load_video_data()
        if video_name not in video_data:
            video_data[video_name] = {
                "title": video_name,
                "description": "No description available",
                "file_id": video_file_id
            }
            with open('video_data.json', 'w') as f:
                json.dump(video_data, f, indent=2)

        await update.message.reply_text(f"Video '{video_name}' added successfully!")
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
    """Show video delivery logs (admin only)"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ.")
        return
    
    try:
        if not os.path.exists('logs/video_delivery_log.json'):
            await update.message.reply_text("No video logs available yet.")
            return
        
        with open('logs/video_delivery_log.json', 'r', encoding='utf-8') as f:
            logs = [json.loads(line) for line in f if line.strip()]
            
        if not logs:
            await update.message.reply_text("No video delivery logs found.")
            return
            
        # Count unique videos sent
        video_counts = {}
        for log in logs:
            video_counts[log['video_name']] = video_counts.get(log['video_name'], 0) + 1
            
        message = ["📊 Video Delivery Statistics:"]
        message.append(f"\nTotal videos sent: {len(logs)}")
        message.append("\nUnique videos sent:")
        
        for video, count in sorted(video_counts.items(), key=lambda x: x[1], reverse=True):
            message.append(f"{video}: {count}")
            
        await update.message.reply_text('\n'.join(message))
        
    except Exception as e:
        logger.error(f"Error reading video logs: {e}")
        await update.message.reply_text("Error reading video logs.")

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
    
    if old_name in video_db:
        # Update video_db
        video_db[new_name] = video_db.pop(old_name)
        save_video_db()  # Save to JSON file

        # Update video_data
        video_data = load_video_data()
        if old_name in video_data:
            video_data[new_name] = video_data.pop(old_name)
            # Ensure title matches new name if it matched old name
            if video_data[new_name]['title'] == old_name:
                video_data[new_name]['title'] = new_name
            with open('video_data.json', 'w') as f:
                json.dump(video_data, f, indent=2)

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
    
    if video_name in video_db:
        del video_db[video_name]
        save_video_db()  # Save to JSON file

        video_data = load_video_data()
        if video_name in video_data:
            del video_data[video_name]
            with open('video_data.json', 'w') as f:
                json.dump(video_data, f, indent=2)

        await update.message.reply_text(f"Video '{video_name}' deleted successfully!")
    else:
        await update.message.reply_text(f"Video '{video_name}' not found.")

async def list_videos(update: Update, context: CallbackContext) -> None:
    """List all available videos"""
    if not is_admin(update):
        await update.message.reply_text("Зөвхөн админ")
        return
    
    if not video_db:
        await update.message.reply_text("Кино одсонгүй.")
        return
    
    keyboard = []
    for name in sorted(video_db.keys()):
        keyboard.append([InlineKeyboardButton(name, callback_data=f"video_{name}")])
    
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
    """Search through user messages for specific text"""
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

        if not os.path.exists('logs/message_logs.json'):
            await update.message.reply_text("No message logs available yet.")
            return
        
        with open('logs/message_logs.json', 'r', encoding='utf-8') as f:
            # Read all lines as individual JSON objects
            messages = [json.loads(line) for line in f if line.strip()]
        
        # Filter messages containing the search term (case insensitive)
        results = []
        for msg in messages:
            # Apply user filter if specified
            if user_filter:
                if 'user_id' in user_filter and msg.get('user_id') != user_filter['user_id']:
                    continue
                if 'username' in user_filter and msg.get('username', '').lower() != user_filter['username']:
                    continue
            
            # Apply simple text search
            if actual_search_term and actual_search_term.lower() not in msg.get('text', '').lower():
                continue
            
            results.append(msg)
        
        if not results:
            await update.message.reply_text(f"No messages found containing:")
            return
        
        # Format results with pagination
        response = [f"🔍 Search results for:\n"]
        if user_filter:
            response[0] += f"👤 Filtered by user: {user_filter}\n"

        for i, msg in enumerate(results[:15], 1):  # Show first 15 results
            timestamp = datetime.fromisoformat(msg['timestamp']).strftime('%Y-%m-%d %H:%M')
            response.append(
                f"\n{i}. {timestamp} - @{msg.get('username', '?')} "
                f"({msg.get('first_name', 'Unknown')}):\n"
                f"{msg['text']}"
            )
        
        if len(results) > 15:
            response.append(f"\n\nℹ️ Showing 10 of {len(results)} results.")
        
        # Split long messages to avoid Telegram's message length limit
        full_response = '\n'.join(response)
        for i in range(0, len(full_response), 4000):
            await update.message.reply_text(full_response[i:i+4000])
            
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        await update.message.reply_text("An error occurred while searching messages.")

async def handle_video(update: Update, context: CallbackContext) -> None:
    """Handle video messages"""
    if is_admin(update):
        await update.message.reply_text("To add this video, reply to it with /addvideo <name>")
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
        video_count = len(data['videos'])
        total_sends += video_count
        last_video = data['videos'][-1]['video_name'] if data['videos'] else 'none'
        
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
    application.add_handler(CommandHandler("sync", sync))  # Add this line
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
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
    application.add_handler(CommandHandler("reload", reload_data))
    application.add_handler(CommandHandler("editdescription", edit_description))
    application.add_handler(CommandHandler("edittitle", edit_title))
    application.add_handler(CommandHandler("userlimit", user_limits))


    
    # Handle button presses
    application.add_handler(CallbackQueryHandler(button))
    
    # on non command i.e video messages
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_screenshot))

    application.add_error_handler(error_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()