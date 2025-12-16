import logging
import random
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# =================== НАСТРОЙКА ЛОГГИРОВАНИЯ ===================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =================== КЛАСС ИГРЫ ===================
class CityGame:
    def __init__(self, player_id):
        self.player_id = player_id
        self.resources = {
            '🌾 Пшеница': 100,
            '🌳 Дерево': 50,
            '🪨 Камень': 30,
            '💰 Золото': 0
        }
        self.buildings = {
            '🌾 Ферма': 0,
            '🌳 Лесопилка': 0,
            '⛏️ Шахта': 0,
            '🏠 Дом': 1
        }
        self.population = 1
        self.day = 1
        self.is_alive = True
        
    # Стоимость построек
    BUILDING_COST = {
        '🌾 Ферма': {'🌳 Дерево': 100, '🪨 Камень': 50},
        '🌳 Лесопилка': {'🌳 Дерево': 150, '🪨 Камень': 80},
        '⛏️ Шахта': {'🌳 Дерево': 200, '🪨 Камень': 100},
        '🏠 Дом': {'🌳 Дерево': 400, '🪨 Камень': 230, '🌾 Пшеница': 100}
    }
    
    # Производство
    BUILDING_PRODUCTION = {
        '🌾 Ферма': 50,
        '🌳 Лесопилка': 40,
        '⛏️ Шахта': 30
    }
    
    def collect_resources(self):
        """Собрать ресурсы"""
        collected = {}
        for building, count in self.buildings.items():
            if building in self.BUILDING_PRODUCTION:
                resource = '🌾 Пшеница' if 'Ферма' in building else \
                          '🌳 Дерево' if 'Лесопилка' in building else '🪨 Камень'
                amount = count * self.BUILDING_PRODUCTION[building]
                self.resources[resource] += amount
                collected[resource] = amount
        return collected
    
    def build(self, building_type):
        """Построить здание"""
        if building_type not in self.BUILDING_COST:
            return False, "Нет такого здания"
        
        # Проверяем ресурсы
        for resource, cost in self.BUILDING_COST[building_type].items():
            if self.resources.get(resource, 0) < cost:
                return False, f"Не хватает {resource}"
        
        # Списываем ресурсы
        for resource, cost in self.BUILDING_COST[building_type].items():
            self.resources[resource] -= cost
        
        # Строим
        self.buildings[building_type] += 1
        return True, f"{building_type} построена!"
    
    def next_day(self):
        """Наступает новый день"""
        self.day += 1
        
        # Население ест
        food_needed = self.population * 10
        if self.resources['🌾 Пшеница'] >= food_needed:
            self.resources['🌾 Пшеница'] -= food_needed
            food_status = f"🍞 Население накормлено (-{food_needed}🌾)"
        else:
            # Голод
            starvation = random.randint(1, max(1, self.population // 2))
            self.population = max(1, self.population - starvation)
            self.resources['🌾 Пшеница'] = 0
            food_status = f"⚠️ ГОЛОД! Умерло {starvation} человек"
        
        # Новые жители
        max_population = self.buildings['🏠 Дом'] * 5
        if self.population < max_population:
            newcomers = random.choices([0, 1, 2], weights=[0.4, 0.4, 0.2])[0]
            self.population += newcomers
            pop_change = f"👥 +{newcomers} новых жителей"
        else:
            pop_change = "🏠 Нет свободных домов для новых жителей"
        
        # Случайные события
        events = []
        if random.random() < 0.3:
            event = random.choice([
                ("🌧️ Дождь помог урожаю", {"🌾 Пшеница": 30}),
                ("🔥 Пожар в лесу", {"🌳 Дерево": -20}),
                ("💎 Нашли клад", {"💰 Золото": 10}),
                ("🎁 Кареван с подарками", {"🌾 Пшеница": 15, "🌳 Дерево": 15}),
                ("🐺 Волки напали на стадо", {"🌾 Пшеница": -25})
            ])
            events.append(event[0])
            for res, val in event[1].items():
                self.resources[res] = max(0, self.resources[res] + val)
        
        return {
            'day': self.day,
            'food_status': food_status,
            'pop_change': pop_change,
            'events': events
        }
    
    def get_status(self):
        """Получить статус города"""
        status = f"🏘️ ГОРОД (День {self.day})\n\n"
        
        # Ресурсы
        status += "📊 РЕСУРСЫ:\n"
        for resource, amount in self.resources.items():
            status += f"{resource}: {amount}\n"
        
        # Население
        status += f"\n👥 НАСЕЛЕНИЕ: {self.population}\n"
        status += f"🍞 Нужно еды: {self.population * 10}/день\n"
        
        # Здания
        status += "\n🏗️ ЗДАНИЯ:\n"
        for building, count in self.buildings.items():
            if count > 0:
                production = self.BUILDING_PRODUCTION.get(building, 0)
                if production > 0:
                    status += f"{building}: {count} (+{production*count}/день)\n"
                else:
                    status += f"{building}: {count}\n"
        
        return status

# =================== ХРАНЕНИЕ ИГРОКОВ ===================
games = {}  # {player_id: CityGame}

# =================== TELEGRAM БОТ ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    player_id = user.id
    
    # Создаем новую игру
    games[player_id] = CityGame(player_id)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n"
        f"🏘️ Добро пожаловать в City Survival!\n\n"
        f"📌 Цель: развивать город и выживать\n"
        f"👥 Каждый житель ест 10🌾 в день\n"
        f"🏠 В каждом доме живет до 5 человек\n\n"
        f"Используй /menu для управления городом"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("📊 Статус города", callback_data='status')],
        [InlineKeyboardButton("⛏️ Собрать ресурсы", callback_data='collect')],
        [InlineKeyboardButton("🏗️ Построить здание", callback_data='build_menu')],
        [InlineKeyboardButton("🏠 Построить дом", callback_data='build_house')],
        [InlineKeyboardButton("⏭️ Следующий день", callback_data='next_day')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("🏘️ Выберите действие:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("🏘️ Выберите действие:", reply_markup=reply_markup)

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    if player_id not in games:
        await query.edit_message_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    await query.edit_message_text(game.get_status())

async def collect_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Собрать ресурсы"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    if player_id not in games:
        await query.edit_message_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    collected = game.collect_resources()
    
    if collected:
        message = "⛏️ Ресурсы собраны!\n\n"
        for resource, amount in collected.items():
            message += f"{resource}: +{amount}\n"
    else:
        message = "⛏️ Нет зданий для сбора ресурсов"
    
    message += f"\n{game.get_status()}"
    await query.edit_message_text(message)

async def build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню строительства"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    if player_id not in games:
        await query.edit_message_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    
    keyboard = [
        [
            InlineKeyboardButton(
                "🌾 Ферма (100🌳 50🪨)",
                callback_data='build_🌾 Ферма'
            )
        ],
        [
            InlineKeyboardButton(
                "🌳 Лесопилка (150🌳 80🪨)",
                callback_data='build_🌳 Лесопилка'
            )
        ],
        [
            InlineKeyboardButton(
                "⛏️ Шахта (200🌳 100🪨)",
                callback_data='build_⛏️ Шахта'
            )
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Показываем текущие ресурсы
    resources_text = "Ваши ресурсы:\n"
    for resource, amount in game.resources.items():
        resources_text += f"{resource}: {amount}\n"
    
    await query.edit_message_text(
        f"🏗️ Выберите здание:\n\n{resources_text}",
        reply_markup=reply_markup
    )

async def build_building(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Построить выбранное здание"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    if player_id not in games:
        await query.edit_message_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    building_type = query.data.split('_', 1)[1]
    
    success, message = game.build(building_type)
    
    if success:
        result = f"✅ {message}\n\n"
    else:
        result = f"❌ {message}\n\n"
    
    result += game.get_status()
    await query.edit_message_text(result)

async def build_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Построить дом"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    if player_id not in games:
        await query.edit_message_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    success, message = game.build('🏠 Дом')
    
    if success:
        result = f"✅ Дом построен!\nТеперь можно принять больше жителей.\n\n"
    else:
        result = f"❌ {message}\n\n"
    
    result += game.get_status()
    await query.edit_message_text(result)

async def next_day_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Следующий день"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    if player_id not in games:
        await query.edit_message_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    day_info = game.next_day()
    
    message = f"📅 День {day_info['day']}\n\n"
    message += f"{day_info['food_status']}\n"
    message += f"{day_info['pop_change']}\n"
    
    if day_info['events']:
        message += "\n📰 СОБЫТИЯ:\n"
        for event in day_info['events']:
            message += f"• {event}\n"
    
    message += f"\n{game.get_status()}"
    
    await query.edit_message_text(message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "🏘️ CITY SURVIVAL - Помощь\n\n"
        "📌 Цель игры: развивать город и выживать\n\n"
        "👥 МЕХАНИКИ:\n"
        "• Каждый житель ест 10🌾 в день\n"
        "• Если еды нет - люди умирают\n"
        "• В каждом доме живет до 5 человек\n"
        "• Новые жители приходят случайно\n\n"
        "🏗️ ЗДАНИЯ:\n"
        "• 🌾 Ферма: производит пшеницу\n"
        "• 🌳 Лесопилка: производит дерево\n"
        "• ⛏️ Шахта: производит камень\n"
        "• 🏠 Дом: увеличивает население\n\n"
        "🎮 КОМАНДЫ:\n"
        "/start - Начать игру\n"
        "/menu - Главное меню\n"
        "/status - Статус города\n"
    )
    
    await query.edit_message_text(help_text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    player_id = update.effective_user.id
    if player_id not in games:
        await update.message.reply_text("Игра не найдена. Используйте /start")
        return
    
    game = games[player_id]
    await update.message.reply_text(game.get_status())

# =================== ОБРАБОТЧИК CALLBACK ===================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    data = query.data
    
    if data == 'menu':
        await menu(update, context)
    elif data == 'status':
        await show_status(update, context)
    elif data == 'collect':
        await collect_resources(update, context)
    elif data == 'build_menu':
        await build_menu(update, context)
    elif data == 'build_house':
        await build_house(update, context)
    elif data == 'next_day':
        await next_day_command(update, context)
    elif data == 'help':
        await help_command(update, context)
    elif data.startswith('build_'):
        await build_building(update, context)

# =================== ЗАПУСК БОТА ===================
def main():
    """Запуск бота"""
    # ТОКЕН ТВОЕГО БОТА (замени на свой)
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    print("🚀 Бот запущен! Иди в Telegram и напиши /start")
    app.run_polling()

if __name__ == "__main__":
    main()
