# -*- coding: utf-8 -*-
"""
Webhook-only bot for PythonAnywhere free tier
Receives messages but responds via web interface
"""

import os
import logging
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import pytz
from schedule_data import SCHEDULE, WEEKDAYS, WEEKDAYS_UA

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UKRAINE_TZ = pytz.timezone('Europe/Kiev')

def init_db():
    """Initialize database for message queue"""
    conn = sqlite3.connect('message_queue.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            command TEXT,
            response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent BOOLEAN DEFAULT FALSE
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class ScheduleManager:
    def get_current_time_ukraine(self):
        return datetime.now(UKRAINE_TZ)
    
    def get_current_day(self):
        current_time = self.get_current_time_ukraine()
        return WEEKDAYS.get(current_time.weekday(), 'sunday')
    
    def get_current_pair(self):
        current_day = self.get_current_day()
        current_time = self.get_current_time_ukraine().time()
        
        if current_day not in SCHEDULE:
            return None
            
        for pair in SCHEDULE[current_day]:
            start_str, end_str = pair['time'].split('-')
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            from datetime import time
            start_time = time(start_hour, start_min)
            end_time = time(end_hour, end_min)
            
            if start_time <= current_time <= end_time:
                return pair
        return None
    
    def get_next_pair(self):
        current_day = self.get_current_day()
        current_time = self.get_current_time_ukraine().time()
        
        if current_day not in SCHEDULE:
            return None
            
        for pair in SCHEDULE[current_day]:
            start_str = pair['time'].split('-')[0]
            start_hour, start_min = map(int, start_str.split(':'))
            
            from datetime import time
            start_time = time(start_hour, start_min)
            
            if current_time < start_time:
                return pair
        return None

schedule_manager = ScheduleManager()

def generate_response(command):
    """Generate response for command"""
    if command.startswith('/start') or command.startswith('/help'):
        return """🎓 **Бот расписания E-24**

📚 **Доступные команды:**
/schedule - Полное расписание на неделю  
/current - Текущая пара
/next - Следующая пара
/today - Расписание на сегодня

⚠️ *Из-за ограничений хостинга ответы отображаются на веб-странице*"""

    elif command.startswith('/current'):
        current_pair = schedule_manager.get_current_pair()
        if current_pair:
            return f"🔴 **Сейчас идет пара:**\n📚 {current_pair['subject']}\n🕐 {current_pair['time']}\n📊 Пара #{current_pair['pair_number']}"
        else:
            current_time = schedule_manager.get_current_time_ukraine()
            next_pair = schedule_manager.get_next_pair()
            result = f"✅ **Сейчас перерыв или выходной**\n🕐 Текущее время: {current_time.strftime('%H:%M')}"
            if next_pair:
                result += f"\n⏭️ Следующая пара: {next_pair['subject']} в {next_pair['time'].split('-')[0]}"
            return result

    elif command.startswith('/next'):
        next_pair = schedule_manager.get_next_pair()
        if next_pair:
            return f"⏭️ **Следующая пара:**\n📚 {next_pair['subject']}\n🕐 {next_pair['time']}\n📊 Пара #{next_pair['pair_number']}"
        else:
            return "✅ **Сегодня больше пар нет**"

    elif command.startswith('/today'):
        current_day = schedule_manager.get_current_day()
        today_schedule = SCHEDULE.get(current_day, [])
        
        if not today_schedule:
            return f"🎉 **Сегодня ({WEEKDAYS_UA[current_day]}) выходной день!**"
        
        result = f"📅 **Расписание на сегодня ({WEEKDAYS_UA[current_day]}):**\n\n"
        current_pair = schedule_manager.get_current_pair()
        current_time = schedule_manager.get_current_time_ukraine().time()
        
        for pair in today_schedule:
            start_str = pair['time'].split('-')[0]
            start_hour, start_min = map(int, start_str.split(':'))
            
            from datetime import time
            start_time = time(start_hour, start_min)
            
            if current_pair and pair == current_pair:
                status = "🔴 СЕЙЧАС"
            elif current_time < start_time:
                status = "⏳ БУДЕТ"
            else:
                status = "✅ БЫЛО"
            
            result += f"{status} {pair['time']} - {pair['subject']}\n"
        
        return result

    elif command.startswith('/schedule'):
        result = "📋 **Полное расписание группы E-24**\n\n"
        for day_key, day_name in WEEKDAYS_UA.items():
            if day_key in SCHEDULE:
                result += f"📅 **{day_name}**:\n"
                for pair in SCHEDULE[day_key]:
                    result += f"🕐 {pair['time']} - {pair['subject']}\n"
                result += "\n"
        return result

    return "❓ Неизвестная команда. Используйте /help для списка команд."

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive webhook and queue response"""
    try:
        json_data = request.get_json()
        
        if json_data and 'message' in json_data:
            message = json_data['message']
            chat_id = message['chat']['id']
            
            if 'text' in message:
                text = message['text']
                logger.info(f"Received command: {text} from {chat_id}")
                
                # Generate response
                response = generate_response(text)
                
                # Store in database
                conn = sqlite3.connect('message_queue.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO message_queue (chat_id, command, response)
                    VALUES (?, ?, ?)
                ''', (chat_id, text, response))
                conn.commit()
                conn.close()
                
                logger.info(f"Queued response for {chat_id}")
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/')
def dashboard():
    """Show responses dashboard"""
    conn = sqlite3.connect('message_queue.db')
    cursor = conn.cursor()
    
    # Get recent messages
    cursor.execute('''
        SELECT chat_id, command, response, timestamp 
        FROM message_queue 
        ORDER BY timestamp DESC 
        LIMIT 20
    ''')
    messages = cursor.fetchall()
    
    conn.close()
    
    current_time = schedule_manager.get_current_time_ukraine()
    current_pair = schedule_manager.get_current_pair()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>E-24 Bot Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .status { padding: 15px; border-radius: 8px; margin: 15px 0; }
            .online { background: #d4edda; color: #155724; border-left: 4px solid #28a745; }
            .current-pair { background: #fff3cd; color: #856404; border-left: 4px solid #ffc107; }
            .message { background: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .command { font-weight: bold; color: #007bff; }
            .response { margin: 10px 0; white-space: pre-line; }
            .timestamp { color: #666; font-size: 0.9em; }
        </style>
        <script>
            setTimeout(function(){ location.reload(); }, 10000);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎓 E-24 Bot Dashboard</h1>
                <p>Панель управления ботом расписания</p>
            </div>
            
            <div class="status online">
                <h3>🟢 Бот онлайн</h3>
                <p>Получает сообщения, ответы отображаются здесь</p>
            </div>
            
            {% if current_pair %}
            <div class="current-pair">
                <h3>🔴 Сейчас идет пара:</h3>
                <p><strong>{{ current_pair.subject }}</strong><br>
                {{ current_pair.time }} (Пара #{{ current_pair.pair_number }})</p>
            </div>
            {% endif %}
            
            <div class="status">
                <h3>📱 Последние сообщения:</h3>
                {% if messages %}
                    {% for msg in messages %}
                    <div class="message">
                        <div class="command">{{ msg[1] }}</div>
                        <div class="response">{{ msg[2] }}</div>
                        <div class="timestamp">{{ msg[3] }} | Chat: {{ msg[0] }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <p>Сообщений пока нет</p>
                {% endif %}
            </div>
            
            <p style="text-align: center; color: #666; margin-top: 20px;">
                Страница обновляется каждые 10 секунд<br>
                Текущее время: {{ current_time }}
            </p>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html, 
                                messages=messages, 
                                current_pair=current_pair,
                                current_time=current_time.strftime('%H:%M:%S'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
