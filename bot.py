import os
import logging
import json
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, request
import threading
import asyncio
from threading import Lock

# ========== НАСТРОЙКА ЛОГГИРОВАНИЯ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КОНСТАНТЫ И НАСТРОЙКИ ==========
TOKEN = os.getenv('BOT_TOKEN', 'ВАШ_ТОКЕН_ЗДЕСЬ')  # Получи у @BotFather
PORT = int(os.getenv('PORT', 8080))
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')  # Для продакшена

# ========== ИГРОВАЯ ЛОГИКА ==========
class Player:
    def __init__(self, name):
        self.name = name
        self.resources = {
            'gold': 100,      # Начальный капитал
            'wheat': 50,      # Начальная пшеница
            'wood': 30,       # Начальное дерево
            'stone': 20       # Начальный камень
        }
        self.production = {
            'wheat': 0,       # Пшеница в секунду
            'wood': 0,
            'stone': 0
        }
        self.buildings = {
            'wheat_farm': 0,
            'lumber_mill': 0,
            'quarry': 0,
            'house': 0
        }
        self.people = {
            'current': 0,
            'max': 0,
            'last_spawn': datetime.now()
        }
        self.last_update = datetime.now()
        self.lock = Lock()
    
    def update_resources(self):
        """Обновить ресурсы с течением времени"""
        with self.lock:
            now = datetime.now()
            elapsed = (now - self.last_update).total_seconds()
            
            if elapsed > 0:
                # Производство
                self.resources['wheat'] += self.production['wheat'] * elapsed
                self.resources['wood'] += self.production['wood'] * elapsed
                self.resources['stone'] += self.production['stone'] * elapsed
                
                # Система дней (каждые 30 секунд = 1 игровой день)
                if (now - self.people['last_spawn']).total_seconds() >= 30:
                    self.simulate_day()
                    self.people['last_spawn'] = now
                
                self.last_update = now
    
    def simulate_day(self):
        """Симуляция одного игрового дня"""
        # Питание жителей
        food_needed = self.people['current'] * 10
        
        if self.resources['wheat'] >= food_needed:
            self.resources['wheat'] -= food_needed
            
            # Шанс на приход новых жителей
            if self.people['current'] < self.people['max']:
                if random.random() > 0.4:  # 60% шанс
                    newcomers = random.randint(0, 2)
                    if newcomers > 0:
                        self.people['current'] += newcomers
        else:
            # Голод
            starvation = random.randint(1, 2)
            self.people['current'] = max(0, self.people['current'] - starvation)
    
    # Методы строительства
    def build_wheat_farm(self):
        with self.lock:
            if self.resources['gold'] >= 50:
                self.resources['gold'] -= 50
                self.buildings['wheat_farm'] += 1
                self.production['wheat'] += 2
                return True, "✅ Построена ферма пшеницы!"
            return False, "❌ Недостаточно золота (нужно 50💰)"
    
    def build_lumber_mill(self):
        with self.lock:
            if self.resources['gold'] >= 70:
                self.resources['gold'] -= 70
                self.buildings['lumber_mill'] += 1
                self.production['wood'] += 1.5
                return True, "✅ Построена лесопилка!"
            return False, "❌ Недостаточно золота (нужно 70💰)"
    
    def build_quarry(self):
        with self.lock:
            if self.resources['gold'] >= 100:
                self.resources['gold'] -= 100
                self.buildings['quarry'] += 1
                self.production['stone'] += 1
                return True, "✅ Построена каменоломня!"
            return False, "❌ Недостаточно золота (нужно 100💰)"
    
    def build_house(self):
        with self.lock:
            if (self.resources['stone'] >= 230 and 
                self.resources['wood'] >= 400 and 
                self.resources['wheat'] >= 100):
                
                self.resources['stone'] -= 230
                self.resources['wood'] -= 400
                self.resources['wheat'] -= 100
                self.buildings['house'] += 1
                self.people['max'] += 5
                
                # Автозаселение
                if self.people['current'] < self.people['max']:
                    self.people['current'] = min(self.people['max'], self.people['current'] + 2)
                
                return True, "🏠 Построен дом! +5 к максимальному населению"
            
            errors = []
            if self.resources['stone'] < 230:
                errors.append(f"камень: {self.resources['stone']:.0f}/230")
            if self.resources['wood'] < 400:
                errors.append(f"дерево: {self.resources['wood']:.0f}/400")
            if self.resources['wheat'] < 100:
                errors.append(f"пшеница: {self.resources['wheat']:.0f}/100")
            
            return False, f"❌ Не хватает: {', '.join(errors)}"
    
    def get_status_text(self):
        """Текст статуса для Telegram"""
        self.update_resources()
        
        status = f"""
🏙️ *{self.name}*

📊 *Ресурсы:*
💰 Золото: `{self.resources['gold']:.0f}`
🌾 Пшеница: `{self.resources['wheat']:.1f}` (+{self.production['wheat']:.1f}/сек)
🌲 Дерево: `{self.resources['wood']:.1f}` (+{self.production['wood']:.1f}/сек)
⛰️ Камень: `{self.resources['stone']:.1f}` (+{self.production['stone']:.1f}/сек)

👥 *Население:* `{self.people['current']}/{self.people['max']}`
🍞 Потребление: `{self.people['current'] * 10}` пшеницы/день

🏗️ *Постройки:*
🌾 Фермы: `{self.buildings['wheat_farm']}`
🌲 Лесопилки: `{self.buildings['lumber_mill']}`
⛏️ Каменоломни: `{self.buildings['quarry']}`
🏠 Дома: `{self.buildings['house']}`
"""
        
        # Предупреждения
        warnings = []
        if self.people['current'] > 0 and self.resources['wheat'] < self.people['current'] * 10:
            warnings.append("⚠️ Запасов пшеницы меньше чем на 1 день!")
        if self.people['current'] == self.people['max'] and self.people['max'] > 0:
            warnings.append("⚠️ Нужны новые дома для роста населения!")
        
        if warnings:
            status += "\n" + "\n".join(warnings)
        
        return status
    
    def get_keyboard(self):
        """Клавиатура для игры"""
        keyboard = [
            [
                InlineKeyboardButton("🌾 Ферма (50💰)", callback_data='build_farm'),
                InlineKeyboardButton("🌲 Лесопилка (70💰)", callback_data='build_lumber')
            ],
            [
                InlineKeyboardButton("⛏️ Каменоломня (100💰)", callback_data='build_quarry'),
                InlineKeyboardButton("🏠 Дом (230⛰️ 400🌲 100🌾)", callback_data='build_house')
            ],
            [
                InlineKeyboardButton("📊 Обновить", callback_data='refresh'),
                InlineKeyboardButton("❓ Помощь", callback_data='help')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

# ========== ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ==========
players_db = {}
db_lock = Lock()

# ========== FLASK СЕРВЕР ДЛЯ KEEP-ALIVE ==========
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🏙️ City Survival Bot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                margin: 0;
                padding: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                width: 100%;
                text-align: center;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 2.8em;
            }
            .subtitle {
                color: #666;
                font-size: 1.2em;
                margin-bottom: 30px;
            }
            .stats {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 15px;
                margin: 25px 0;
            }
            .stat-item {
                display: flex;
                justify-content: space-between;
                margin: 10px 0;
                font-size: 1.1em;
            }
            .btn {
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.1em;
                margin: 10px;
                transition: transform 0.3s, box-shadow 0.3s;
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .btn:hover {
                transform: translateY(-3px);
                box-shadow: 0 8px 25px rgba(102,126,234,0.6);
            }
            .emoji-list {
                font-size: 2em;
                margin: 20px 0;
                letter-spacing: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji-list">🏙️🌾🌲⛏️🏠👥</div>
            <h1>City Survival Bot</h1>
            <p class="subtitle">Симулятор выживания и развития города в Telegram</p>
            
            <div class="stats">
                <div class="stat-item">
                    <span>✅ Статус:</span>
                    <span style="color: #28a745; font-weight: bold;">Активен</span>
                </div>
                <div class="stat-item">
                    <span>👥 Игроков онлайн:</span>
                    <span style="color: #667eea; font-weight: bold;">""" + str(len(players_db)) + """</span>
                </div>
                <div class="stat-item">
                    <span>🕐 Последнее обновление:</span>
                    <span>""" + datetime.now().strftime("%H:%M:%S") + """</span>
                </div>
            </div>
            
            <p>Бот работает 24/7 на облачном хостинге</p>
            <p>Играйте прямо в Telegram!</p>
            
            <div style="margin-top: 30px;">
                <a href="https://t.me/your_bot_username" class="btn">🎮 Начать игру в Telegram</a>
                <a href="/health" class="btn" style="background: #28a745;">🩺 Проверить здоровье</a>
            </div>
        </div>
    </body>
    </html>
    """

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Запуск Flask сервера в отдельном потоке"""
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

# ========== TELEGRAM BOT HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    with db_lock:
        if user_id not in players_db:
            players_db[user_id] = Player(user.first_name or "Градоначальник")
            logger.info(f"Новый игрок: {user.first_name} (ID: {user_id})")
    
    player = players_db[user_id]
    
    welcome_text = f"""
👋 Приветствуем, {user.first_name}!

🏙️ *City Survival* - игра о выживании и развитии города.

*Цель:* Построй процветающий город в суровых условиях.

*Основная механика:*
• Строй здания для производства ресурсов
• Заселяй жителей
• Следи, чтобы всем хватало еды
• Выживай и расширяйся!

*Ресурсы:*
💰 Золото - для покупки зданий
🌾 Пшеница - еда для жителей
🌲 Дерево - строительство
⛰️ Камень - строительство

*Управление:* Используй кнопки ниже 👇
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=player.get_keyboard()
    )
    
    await send_game_status(update, context)

async def send_game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить статус игры"""
    user_id = update.effective_user.id
    
    if user_id not in players_db:
        return
    
    player = players_db[user_id]
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=player.get_status_text(),
                parse_mode='Markdown',
                reply_markup=player.get_keyboard()
            )
        else:
            await update.message.reply_text(
                player.get_status_text(),
                parse_mode='Markdown',
                reply_markup=player.get_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка отправки статуса: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id not in players_db:
        await query.edit_message_text("Игра не найдена. Напишите /start")
        return
    
    player = players_db[user_id]
    response_text = ""
    
    if query.data == 'build_farm':
        success, message = player.build_wheat_farm()
        response_text = message
    elif query.data == 'build_lumber':
        success, message = player.build_lumber_mill()
        response_text = message
    elif query.data == 'build_quarry':
        success, message = player.build_quarry()
        response_text = message
    elif query.data == 'build_house':
        success, message = player.build_house()
        response_text = message
    elif query.data == 'refresh':
        response_text = "📊 Статус обновлен"
    elif query.data == 'help':
        await query.edit_message_text(
            text="*❓ Помощь*\n\n"
                 "*Строительство:*\n"
                 "• Ферма: +2🌾/сек, стоит 50💰\n"
                 "• Лесопилка: +1.5🌲/сек, стоит 70💰\n"
                 "• Каменоломня: +1⛰️/сек, стоит 100💰\n"
                 "• Дом: +5👥 макс. население, стоит 230⛰️ 400🌲 100🌾\n\n"
                 "*Жители:*\n"
                 "• Каждый житель ест 10🌾 в день\n"
                 "• Новые жители приходят случайно\n"
                 "• При недостатке еды жители умирают\n\n"
                 "Игра обновляется автоматически!",
            parse_mode='Markdown',
            reply_markup=player.get_keyboard()
        )
        return
    
    # Отправляем результат и обновленный статус
    if response_text:
        await query.edit_message_text(
            text=response_text + "\n\n" + player.get_status_text(),
            parse_mode='Markdown',
            reply_markup=player.get_keyboard()
        )
    else:
        await send_game_status(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
*🏙️ City Survival Bot*

*Команды:*
/start - Начать игру
/help - Эта справка
/stats - Статистика игры

*Как играть:*
1. Собирайте ресурсы (пшеница, дерево, камень)
2. Стройте здания с помощью кнопок
3. Расширяйте население
4. Следите, чтобы хватало еды

*Совет:* Начинайте с ферм пшеницы, чтобы прокормить первых жителей!

Удачи в развитии вашего города! 🏙️
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - статистика сервера"""
    with db_lock:
        total_players = len(players_db)
        total_buildings = sum(sum(p.buildings.values()) for p in players_db.values())
        total_resources = sum(
            p.resources['gold'] + p.resources['wheat'] + 
            p.resources['wood'] + p.resources['stone'] 
            for p in players_db.values()
        )
    
    stats_text = f"""
*📊 Статистика сервера*

👥 Всего игроков: `{total_players}`
🏗️ Всего построек: `{total_buildings}`
💰 Всего ресурсов: `{total_resources:.0f}`

*Топ-5 игроков по населению:*
"""
    
    # Сортируем игроков по населению
    sorted_players = sorted(
        [(pid, p) for pid, p in players_db.items()],
        key=lambda x: x[1].people['current'],
        reverse=True
    )[:5]
    
    for i, (pid, player) in enumerate(sorted_players, 1):
        stats_text += f"{i}. {player.name}: {player.people['current']} жителей\n"
    
    stats_text += f"\n🕐 Сервер работает стабильно\n📍 Порт: {PORT}"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    """Запуск бота"""
    print("🚀 Запуск City Survival Bot...")
    
    # Запускаем Flask сервер в отдельном потоке
    print(f"🌐 Запуск веб-сервера на порту {PORT}...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Создаем приложение бота
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен!")
    print("📱 Перейдите в Telegram и найдите своего бота")
    print("🌐 Веб-интерфейс доступен по адресу: http://localhost:" + str(PORT))
    
    if WEBHOOK_URL:
        # Режим вебхука для продакшена
        print(f"🔗 Настройка вебхука: {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        # Режим поллинга для разработки
        print("🔄 Используется режим поллинга")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Проверяем токен
    if TOKEN == 'ВАШ_ТОКЕН_ЗДЕСЬ':
        print("❌ ОШИБКА: Токен бота не установлен!")
        print("1. Создайте бота через @BotFather в Telegram")
        print("2. Получите токен")
        print("3. Установите переменную окружения BOT_TOKEN или замените значение в коде")
        print("\nДля локального запуска:")
        print("export BOT_TOKEN='ваш_токен'")
        print("python bot.py")
    else:
        main()
