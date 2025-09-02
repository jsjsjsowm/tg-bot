# -*- coding: utf-8 -*-
"""
Flask app with Telegram Bot webhook
E-24 Schedule Bot - Complete implementation
"""

import os
import logging
import requests
import json
import sqlite3
import time as time_module
from datetime import datetime, time
from typing import Optional
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, jsonify, render_template_string, request
from dotenv import load_dotenv
from schedule_data import SCHEDULE, WEEKDAYS, WEEKDAYS_UA, BREAK_SCHEDULE

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
SEND_MESSAGE_URL = f"{BASE_URL}/sendMessage"
EDIT_MESSAGE_URL = f"{BASE_URL}/editMessageText"
ANSWER_CALLBACK_URL = f"{BASE_URL}/answerCallbackQuery"
SET_WEBHOOK_URL = f"{BASE_URL}/setWebhook"

# Ukraine timezone
UKRAINE_TZ = pytz.timezone('Europe/Kiev')

# Database setup
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_interaction TIMESTAMP,
            last_interaction TIMESTAMP,
            message_count INTEGER DEFAULT 0
        )
    ''')
    
    # Create bot_stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_stats (
            id INTEGER PRIMARY KEY,
            start_time TIMESTAMP,
            messages_processed INTEGER DEFAULT 0,
            last_activity TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Bot activity tracking
bot_stats = {
    'start_time': datetime.now(UKRAINE_TZ),
    'messages_processed': 0,
    'active_chats': set(),
    'last_activity': datetime.now(UKRAINE_TZ)
}

def update_user_stats(chat_id, username=None, first_name=None, last_name=None):
    """Update user statistics in database"""
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT message_count FROM users WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        
        current_time = datetime.now(UKRAINE_TZ)
        
        if result:
            # Update existing user
            cursor.execute('''
                UPDATE users 
                SET last_interaction = ?, message_count = message_count + 1,
                    username = COALESCE(?, username),
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name)
                WHERE chat_id = ?
            ''', (current_time, username, first_name, last_name, chat_id))
        else:
            # Insert new user
            cursor.execute('''
                INSERT INTO users (chat_id, username, first_name, last_name, 
                                 first_interaction, last_interaction, message_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (chat_id, username, first_name, last_name, current_time, current_time))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating user stats: {e}")

class ScheduleBot:
    def __init__(self):
        self.session = self.create_session()
        self.setup_webhook()
    
    def create_session(self):
        """Create requests session with retry strategy"""
        session = requests.Session()
        
        # Define retry strategy
        retry_strategy = Retry(
            total=5,  # Total number of retries
            backoff_factor=1,  # Wait 1, 2, 4, 8, 16 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry
            allowed_methods=["HEAD", "GET", "POST"]  # HTTP methods to retry
        )
        
        # Create adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set timeout for all requests
        session.timeout = 30
        
        # Remove proxy settings to avoid 503 errors
        session.trust_env = False
        
        return session
        
    def get_current_time_ukraine(self) -> datetime:
        """Get current time in Ukraine timezone"""
        return datetime.now(UKRAINE_TZ)
    
    def get_current_day(self) -> str:
        """Get current day of week"""
        current_time = self.get_current_time_ukraine()
        return WEEKDAYS.get(current_time.weekday(), 'sunday')
    
    def parse_time(self, time_str: str) -> tuple:
        """Parse time string like '8:30-9:50' to start and end time objects"""
        start_str, end_str = time_str.split('-')
        start_hour, start_min = map(int, start_str.split(':'))
        end_hour, end_min = map(int, end_str.split(':'))
        
        start_time = time(start_hour, start_min)
        end_time = time(end_hour, end_min)
        
        return start_time, end_time
    
    def get_current_pair(self) -> Optional[dict]:
        """Get currently active pair"""
        current_day = self.get_current_day()
        current_time = self.get_current_time_ukraine().time()
        
        if current_day not in SCHEDULE:
            return None
            
        for pair in SCHEDULE[current_day]:
            start_time, end_time = self.parse_time(pair['time'])
            if start_time <= current_time <= end_time:
                return pair
        
        return None
    
    def get_next_pair(self) -> Optional[dict]:
        """Get next upcoming pair"""
        current_day = self.get_current_day()
        current_time = self.get_current_time_ukraine().time()
        
        if current_day not in SCHEDULE:
            return None
            
        for pair in SCHEDULE[current_day]:
            start_time, _ = self.parse_time(pair['time'])
            if current_time < start_time:
                return pair
        
        return None
    
    def get_today_schedule(self) -> list:
        """Get today's full schedule"""
        current_day = self.get_current_day()
        return SCHEDULE.get(current_day, [])

    def setup_webhook(self):
        """Setup webhook for the bot"""
        if WEBHOOK_URL and WEBHOOK_URL != "https://your-domain.com":
            webhook_data = {
                'url': f"{WEBHOOK_URL}/webhook",
                'allowed_updates': ['message', 'callback_query']
            }
            try:
                response = self.session.post(SET_WEBHOOK_URL, data=webhook_data, timeout=30)
                if response.json().get('ok'):
                    print(f"✅ Webhook set to: {WEBHOOK_URL}/webhook")
                else:
                    print(f"❌ Failed to set webhook: {response.text}")
            except Exception as e:
                print(f"❌ Error setting webhook: {e}")
        else:
            print("❌ WEBHOOK_URL not configured properly")
    
    def send_message(self, chat_id, text, reply_markup=None):
        """Send message to chat with retry logic"""
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.session.post(SEND_MESSAGE_URL, data=data, timeout=30)
                response.raise_for_status()  # Raises an HTTPError for bad responses
                
                result = response.json()
                if result.get('ok'):
                    logger.info(f"Message sent successfully to {chat_id}")
                    return result
                else:
                    logger.error(f"Telegram API error: {result}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout sending message to {chat_id}, attempt {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)  # Exponential backoff
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error sending message to {chat_id}, attempt {attempt + 1}/{max_attempts}: {e}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
                    
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error sending message to {chat_id}: {e}")
                break  # Don't retry on HTTP errors like 4xx
                
            except Exception as e:
                logger.error(f"Unexpected error sending message to {chat_id}: {e}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
        
        logger.error(f"Failed to send message to {chat_id} after {max_attempts} attempts")
        return None
    
    def edit_message(self, chat_id, message_id, text, reply_markup=None):
        """Edit existing message with retry logic"""
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.session.post(EDIT_MESSAGE_URL, data=data, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    return result
                else:
                    logger.error(f"Telegram API error editing message: {result}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout editing message, attempt {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error editing message, attempt {attempt + 1}/{max_attempts}: {e}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
                    
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error editing message: {e}")
                break
                
            except Exception as e:
                logger.error(f"Unexpected error editing message: {e}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
        
        logger.error(f"Failed to edit message after {max_attempts} attempts")
        return None
    
    def answer_callback_query(self, callback_query_id, text=None):
        """Answer callback query with retry logic"""
        data = {'callback_query_id': callback_query_id}
        if text:
            data['text'] = text
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.session.post(ANSWER_CALLBACK_URL, data=data, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    return result
                else:
                    logger.error(f"Telegram API error answering callback: {result}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout answering callback, attempt {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error answering callback, attempt {attempt + 1}/{max_attempts}: {e}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
                    
            except Exception as e:
                logger.error(f"Unexpected error answering callback: {e}")
                if attempt < max_attempts - 1:
                    time_module.sleep(2 ** attempt)
        
        logger.error(f"Failed to answer callback query after {max_attempts} attempts")
        return None
    
    def handle_start(self, chat_id):
        """Handle /start command"""
        welcome_text = """

📚 **Доступные команды:**
/schedule - Показать полное расписание на неделю
/current - Какая пара сейчас идет
/next - Какая следующая пара
/today - Расписание на сегодня
/help - Показать это сообщение

        """
        self.send_message(chat_id, welcome_text)
    
    def create_schedule_keyboard(self):
        """Create inline keyboard for schedule navigation"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📅 Понедельник", "callback_data": "schedule_monday"},
                    {"text": "📅 Вторник", "callback_data": "schedule_tuesday"}
                ],
                [
                    {"text": "📅 Среда", "callback_data": "schedule_wednesday"},
                    {"text": "📅 Четверг", "callback_data": "schedule_thursday"}
                ],
                [
                    {"text": "📅 Пятница", "callback_data": "schedule_friday"},
                    {"text": "📊 Полное расписание", "callback_data": "schedule_full"}
                ]
            ]
        }
        return keyboard
    
    def handle_schedule(self, chat_id, message_id=None):
        """Handle /schedule command"""
        current_day = self.get_current_day()
        today_schedule = self.get_today_schedule()
        
        if today_schedule:
            result = f"📋 **Расписание на сегодня ({WEEKDAYS_UA[current_day]})**\n\n"
            result += self.format_schedule_day(current_day, today_schedule)
            result += "\n\n💡 *Выберите день для просмотра расписания:*"
        else:
            result = f"📋 **Расписание группы E-24**\n\n"
            result += f"🎉 Сегодня ({WEEKDAYS_UA[current_day]}) выходной день!\n\n"
            result += "💡 *Выберите день для просмотра расписания:*"
        
        keyboard = self.create_schedule_keyboard()
        
        if message_id:
            self.edit_message(chat_id, message_id, result, keyboard)
        else:
            self.send_message(chat_id, result, keyboard)
    
    def handle_schedule_day(self, chat_id, message_id, day):
        """Handle specific day schedule"""
        if day == 'full':
            result = "📋 **Полное расписание группы E-24 (2 курс, 1 семестр)**\n\n"
            for day_key, day_name in WEEKDAYS_UA.items():
                if day_key in SCHEDULE:
                    result += self.format_schedule_day(day_key, SCHEDULE[day_key]) + "\n\n"
        else:
            day_schedule = SCHEDULE.get(day, [])
            result = f"📅 **Расписание на {WEEKDAYS_UA[day]}**\n\n"
            
            if day_schedule:
                current_day = self.get_current_day()
                if day == current_day:
                    current_pair = self.get_current_pair()
                    current_time = self.get_current_time_ukraine().time()
                    
                    for pair in day_schedule:
                        start_time, end_time = self.parse_time(pair['time'])
                        
                        if current_pair and pair == current_pair:
                            status = "🔴 "
                        elif current_time < start_time:
                            status = "⏳ "
                        else:
                            status = "✅ "
                        
                        result += f"{status}{pair['time']} - {pair['subject']}\n"
                else:
                    for pair in day_schedule:
                        result += f"🕐 {pair['time']} - {pair['subject']}\n"
            else:
                result += "🎉 Выходной день!"
        
        result += "\n\n💡 *Выберите другой день:*"
        keyboard = self.create_schedule_keyboard()
        self.edit_message(chat_id, message_id, result, keyboard)
    
    def handle_current(self, chat_id):
        """Handle /current command"""
        current_pair = self.get_current_pair()
        current_time = self.get_current_time_ukraine()
        
        if current_pair:
            result = f"🔴 **Сейчас идет пара:**\n"
            result += f"📚 {current_pair['subject']}\n"
            result += f"🕐 {current_pair['time']}\n"
            result += f"📊 Пара #{current_pair['pair_number']}"
        else:
            result = f"✅ **Сейчас перерыв или выходной**\n"
            result += f"🕐 Текущее время: {current_time.strftime('%H:%M')}\n"
            
            next_pair = self.get_next_pair()
            if next_pair:
                result += f"⏭️ Следующая пара: {next_pair['subject']} в {next_pair['time'].split('-')[0]}"
        
        self.send_message(chat_id, result)
    
    def handle_next(self, chat_id):
        """Handle /next command"""
        next_pair = self.get_next_pair()
        
        if next_pair:
            result = f"⏭️ **Следующая пара:**\n"
            result += f"📚 {next_pair['subject']}\n"
            result += f"🕐 {next_pair['time']}\n"
            result += f"📊 Пара #{next_pair['pair_number']}"
        else:
            result = f"✅ **Сегодня больше пар нет**\n"
        
        self.send_message(chat_id, result)
    
    def handle_today(self, chat_id):
        """Handle /today command"""
        today_schedule = self.get_today_schedule()
        current_day = self.get_current_day()
        
        if not today_schedule:
            result = f"🎉 **Сегодня ({WEEKDAYS_UA[current_day]}) выходной день!**"
        else:
            result = f"📅 **Расписание на сегодня ({WEEKDAYS_UA[current_day]}):**\n\n"
            
            current_pair = self.get_current_pair()
            current_time = self.get_current_time_ukraine().time()
            
            for pair in today_schedule:
                start_time, end_time = self.parse_time(pair['time'])
                
                if current_pair and pair == current_pair:
                    status = "🔴 СЕЙЧАС"
                elif current_time < start_time:
                    status = "⏳ БУДЕТ"
                else:
                    status = "✅ БЫЛО"
                
                result += f"{status} {pair['time']} - {pair['subject']}\n"
        
        self.send_message(chat_id, result)
    
    def format_schedule_day(self, day, pairs):
        """Format schedule for a specific day"""
        if not pairs:
            return f"📅 **{WEEKDAYS_UA[day]}**: Выходной день"
        
        result = f"📅 **{WEEKDAYS_UA[day]}**:\n"
        for pair in pairs:
            result += f"🕐 {pair['time']} - {pair['subject']}\n"
        
        return result
    
    def handle_message(self, chat_id, text, user_data=None):
        """Handle incoming messages"""
        try:
            # Update statistics
            bot_stats['messages_processed'] += 1
            bot_stats['active_chats'].add(chat_id)
            bot_stats['last_activity'] = self.get_current_time_ukraine()
            
            # Update user statistics in database
            if user_data:
                update_user_stats(
                    chat_id, 
                    user_data.get('username'),
                    user_data.get('first_name'), 
                    user_data.get('last_name')
                )
            else:
                update_user_stats(chat_id)
            
            # Only respond to commands starting with /
            if not text.startswith('/'):
                return
            
            logger.info(f"Processing command: {text} from chat {chat_id}")
            
            if text.startswith('/start'):
                self.handle_start(chat_id)
            elif text.startswith('/schedule'):
                self.handle_schedule(chat_id)
            elif text.startswith('/current'):
                self.handle_current(chat_id)
            elif text.startswith('/next'):
                self.handle_next(chat_id)
            elif text.startswith('/today'):
                self.handle_today(chat_id)
            elif text.startswith('/help'):
                self.handle_start(chat_id)
            elif text.startswith('/stats') and str(chat_id) in ['-1002055203579']:  # Admin command
                self.handle_stats(chat_id)
            else:
                self.send_message(chat_id, "Неизвестная команда. Используйте /help для просмотра доступных команд 📚")
                
        except Exception as e:
            logger.error(f"Error handling message from {chat_id}: {e}")
            # Try to send error message to user
            try:
                self.send_message(chat_id, "Произошла ошибка при обработке команды. Попробуйте позже.")
            except:
                pass  # If we can't even send error message, just log it
    
    def handle_callback_query(self, callback_query):
        """Handle callback query from inline keyboard"""
        callback_data = callback_query.get('data')
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']
        callback_query_id = callback_query['id']
        
        if callback_data.startswith('schedule_'):
            day = callback_data.replace('schedule_', '')
            self.handle_schedule_day(chat_id, message_id, day)
            self.answer_callback_query(callback_query_id)
        else:
            self.answer_callback_query(callback_query_id, "Неизвестная команда")
    
    def handle_stats(self, chat_id):
        """Handle /stats admin command"""
        try:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            
            # Get user count and statistics
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(message_count) FROM users')
            total_messages = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE last_interaction > datetime("now", "-1 day")')
            active_today = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE last_interaction > datetime("now", "-7 days")')
            active_week = cursor.fetchone()[0]
            
            conn.close()
            
            current_time = self.get_current_time_ukraine()
            uptime = current_time - bot_stats['start_time']
            
            stats_text = f"""📊 **Статистика бота E-24**

👥 **Пользователи:**
• Всего пользователей: {user_count}
• Активны сегодня: {active_today}
• Активны за неделю: {active_week}

💬 **Сообщения:**
• Всего обработано: {total_messages}
• За эту сессию: {bot_stats['messages_processed']}
• Активных чатов: {len(bot_stats['active_chats'])}

⏱️ **Время работы:**
• Запущен: {bot_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
• Время работы: {str(uptime).split('.')[0]}
• Последняя активность: {bot_stats['last_activity'].strftime('%H:%M:%S')}

🕐 **Текущее время:** {current_time.strftime('%Y-%m-%d %H:%M:%S')}"""
            
            self.send_message(chat_id, stats_text)
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            self.send_message(chat_id, "Ошибка получения статистики")

# Initialize bot
schedule_bot = ScheduleBot()

# Flask app
app = Flask(__name__)

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        json_data = request.get_json()
        
        if json_data and 'message' in json_data:
            message = json_data['message']
            chat_id = message['chat']['id']
            
            # Extract user data for database tracking
            user_data = {
                'username': message['from'].get('username'),
                'first_name': message['from'].get('first_name'),
                'last_name': message['from'].get('last_name')
            }
            
            if 'text' in message:
                text = message['text']
                logger.info(f"Message from {chat_id}: {text}")
                schedule_bot.handle_message(chat_id, text, user_data)
        
        elif json_data and 'callback_query' in json_data:
            callback_query = json_data['callback_query']
            logger.info(f"Callback query: {callback_query.get('data')}")
            schedule_bot.handle_callback_query(callback_query)        
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/')
def status():
    """Bot status page"""
    current_time = schedule_bot.get_current_time_ukraine()
    uptime = current_time - bot_stats['start_time']
    current_pair = schedule_bot.get_current_pair()
    next_pair = schedule_bot.get_next_pair()
    today_schedule = schedule_bot.get_today_schedule()
    current_day = schedule_bot.get_current_day()
    
    status_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>E-24 Schedule Bot Status</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container { 
                max-width: 800px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 15px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #f0f0f0;
            }
            .status { 
                padding: 20px; 
                border-radius: 10px; 
                margin: 20px 0; 
                border-left: 5px solid #28a745;
            }
            .online { 
                background: #d4edda; 
                border-color: #28a745; 
                color: #155724; 
            }
            .current-pair {
                background: #fff3cd;
                border-left: 5px solid #ffc107;
                color: #856404;
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
            }
            .next-pair {
                background: #d1ecf1;
                border-left: 5px solid #17a2b8;
                color: #0c5460;
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
            }
            .stat { 
                margin: 15px 0; 
                padding: 15px; 
                background: #f8f9fa; 
                border-radius: 10px;
                border-left: 4px solid #6c757d;
            }
            .schedule-today {
                background: #e7f3ff;
                border-left: 5px solid #007bff;
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
            }
            h1 { 
                color: #333; 
                margin: 0;
                font-size: 2.2em;
            }
            h2 {
                margin-top: 0;
                font-size: 1.4em;
            }
            .emoji { 
                font-size: 1.2em; 
            }
            .time-info {
                font-size: 1.1em;
                font-weight: bold;
                color: #495057;
            }
            .pair-item {
                margin: 8px 0;
                padding: 8px;
                background: rgba(255,255,255,0.7);
                border-radius: 5px;
            }
        </style>
        <script>
            setTimeout(function(){ location.reload(); }, 30000);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎓 E-24 Schedule Bot</h1>
                <p style="color: #666; margin: 10px 0;">Расписание группы E-24 • 2 курс • 1 семестр</p>
            </div>
            
            <div class="status online">
                <h2>🟢 Bot is Online</h2>
                <p>Бот работает и готов помогать с расписанием!</p>
            </div>

            {% if current_pair %}
            <div class="current-pair">
                <h2>🔴 Сейчас идет пара:</h2>
                <div class="time-info">{{ current_pair.time }} - {{ current_pair.subject }}</div>
                <p>Пара #{{ current_pair.pair_number }}</p>
            </div>
            {% else %}
            <div class="current-pair">
                <h2>✅ Сейчас перерыв или выходной</h2>
                <p>Текущее время: {{ current_time_str }}</p>
            </div>
            {% endif %}

            {% if next_pair %}
            <div class="next-pair">
                <h2>⏭️ Следующая пара:</h2>
                <div class="time-info">{{ next_pair.time }} - {{ next_pair.subject }}</div>
                <p>Пара #{{ next_pair.pair_number }}</p>
            </div>
            {% endif %}

            {% if today_schedule %}
            <div class="schedule-today">
                <h2>📅 Расписание на сегодня ({{ current_day_ua }}):</h2>
                {% for pair in today_schedule %}
                <div class="pair-item">
                    {% if current_pair and pair.time == current_pair.time %}
                        🔴 {{ pair.time }} - {{ pair.subject }}
                    {% elif pair.time.split('-')[0] > current_time_str.split(':')[0] + ':' + current_time_str.split(':')[1] %}
                        ⏳ {{ pair.time }} - {{ pair.subject }}
                    {% else %}
                        ✅ {{ pair.time }} - {{ pair.subject }}
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="schedule-today">
                <h2>🎉 Сегодня ({{ current_day_ua }}) выходной день!</h2>
            </div>
            {% endif %}
            
            <div class="stat">
                <strong>📊 Статистика:</strong><br>
                🚀 Запущено: {{ start_time }}<br>
                ⏱️ Время работы: {{ uptime }}<br>
                💬 Обработано сообщений: {{ messages_processed }}<br>
                👥 Активные чаты: {{ active_chats }}<br>
                🕐 Последняя активность: {{ last_activity }}
            </div>
            
            <div class="stat">
                <strong>🇺🇦 Текущее время в Украине:</strong><br>
                <span class="time-info">{{ current_time_full }}</span>
            </div>
            
            <div class="stat">
                <strong>📚 Доступные команды:</strong><br>
                /start - Запустить бота<br>
                /schedule - Полное расписание на неделю<br>
                /current - Текущая пара<br>
                /next - Следующая пара<br>
                /today - Расписание на сегодня<br>
                /help - Показать помощь
            </div>
            
            <p style="text-align: center; color: #666; margin-top: 30px;">
                Страница обновляется автоматически каждые 30 секунд
            </p>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(status_html,
        start_time=bot_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
        uptime=str(uptime).split('.')[0],
        messages_processed=bot_stats['messages_processed'],
        active_chats=len(bot_stats['active_chats']),
        last_activity=bot_stats['last_activity'].strftime('%Y-%m-%d %H:%M:%S'),
        current_time_full=current_time.strftime('%Y-%m-%d %H:%M:%S'),
        current_time_str=current_time.strftime('%H:%M'),
        current_pair=current_pair,
        next_pair=next_pair,
        today_schedule=today_schedule,
        current_day_ua=WEEKDAYS_UA.get(current_day, 'Невідомо')
    )

@app.route('/api/status')
def api_status():
    """API endpoint for bot status"""
    current_time = schedule_manager.get_current_time_ukraine()
    uptime = current_time - bot_stats['start_time']
    current_pair = schedule_manager.get_current_pair()
    next_pair = schedule_manager.get_next_pair()
    
    return jsonify({
        'status': 'online',
        'start_time': bot_stats['start_time'].isoformat(),
        'uptime_seconds': int(uptime.total_seconds()),
        'messages_processed': bot_stats['messages_processed'],
        'active_chats': len(bot_stats['active_chats']),
        'last_activity': bot_stats['last_activity'].isoformat(),
        'current_time': current_time.isoformat(),
        'current_pair': current_pair,
        'next_pair': next_pair,
        'ukraine_time': current_time.strftime('%H:%M:%S')
    })

@app.route('/api/schedule')
def api_schedule():
    """API endpoint for full schedule"""
    return jsonify({
        'schedule': SCHEDULE,
        'current_day': schedule_bot.get_current_day(),
        'current_pair': schedule_bot.get_current_pair(),
        'next_pair': schedule_bot.get_next_pair(),
        'today_schedule': schedule_bot.get_today_schedule()
    })

if __name__ == '__main__':
    if not TOKEN:
        print("❌ BOT_TOKEN environment variable is required!")
        exit(1)
    
    print(f"🚀 Starting E-24 Schedule Bot")
    print(f"🤖 Bot token: {TOKEN[:10]}...")
    print(f"📡 Webhook URL: {WEBHOOK_URL}/webhook")
    
    # Railway использует переменную PORT, по умолчанию 5000
    port = int(os.getenv('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"🌐 Starting server on {host}:{port}")
    app.run(host=host, port=port, debug=False)
