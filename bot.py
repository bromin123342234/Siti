import logging
import random
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Хранение данных игроков
players_data = {}

class GameState:
    def __init__(self, player_id):
        self.player_id = player_id
        self.resources = {
            'wheat': 100,  # Пшеница
            'wood': 50,    # Дерево
            'stone': 30,   # Камень
            'gold': 0      # Золото
        }
        self.buildings = {
            'wheat_farm': 0,  # Ферма пшеницы
            'wood_farm': 0,   # Ферма деревьев
            'stone_mine': 0,  # Шахта камня
            'houses': 1       # Дома
        }
        self.population = 1   # Население
        self.last_update = datetime.now()
        self.day = 1
        self.taxes_collected = False

# Стоимости построек
BUILDING_COSTS = {
    'wheat_farm': {'wood': 100, 'stone': 50},
    'wood_farm': {'wood': 150, 'stone': 80},
    'stone_mine': {'wood': 200, 'stone': 100},
    'house': {'wood': 400, 'stone': 230, 'wheat': 100}
}

# Производство зданий
BUILDING_PRODUCTION = {
    'wheat_farm': 50,
    'wood_farm': 40,
    'stone_mine': 30
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск игры"""
    player_id = update.effective_user.id
    
    if player_id not in players_data:
        players_data[player_id] = GameState(player_id)
    
    game = players_data[player_id]
    await update.message.reply_text(
        f"🏘️ Добро пожаловать в ваш городок!\n"
        f"День {game.day}\n\n"
        f"📊 Ресурсы:\n"
        f"🌾 Пшеница: {game.resources['wheat']}\n"
        f"🌳 Дерево: {game.resources['wood']}\n"
        f"🪨 Камень: {game.resources['stone']}\n"
        f"💰 Золото: {game.resources['gold']}\n\n"
        f"👥 Население: {game.population}\n"
        f"🏠 Домов: {game.buildings['houses']}\n\n"
        f"Используйте /menu для управления городом",
        parse_mode='Markdown'
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("🏗️ Построить здание", callback_data='build')],
        [InlineKeyboardButton("📊 Статус города", callback_data='status')],
        [InlineKeyboardButton("⛏️ Собирать ресурсы", callback_data='collect')],
        [InlineKeyboardButton("🏠 Построить дом", callback_data='build_house')],
        [InlineKeyboardButton("⏭️ Следующий день", callback_data='next_day')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏘️ Меню управления городом:", reply_markup=reply_markup)

async def collect_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор ресурсов"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    game = players_data[player_id]
    
    # Производство от зданий
    production = {
        'wheat': game.buildings['wheat_farm'] * BUILDING_PRODUCTION['wheat_farm'],
        'wood': game.buildings['wood_farm'] * BUILDING_PRODUCTION['wood_farm'],
        'stone': game.buildings['stone_mine'] * BUILDING_PRODUCTION['stone_mine']
    }
    
    for resource, amount in production.items():
        game.resources[resource] += amount
    
    await query.edit_message_text(
        f"⛏️ Ресурсы собраны!\n\n"
        f"🌾 +{production['wheat']} пшеницы\n"
        f"🌳 +{production['wood']} дерева\n"
        f"🪨 +{production['stone']} камня\n\n"
        f"📊 Всего ресурсов:\n"
        f"🌾 {game.resources['wheat']} | 🌳 {game.resources['wood']} | 🪨 {game.resources['stone']}",
        parse_mode='Markdown'
    )

async def show_build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню строительства"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    game = players_data[player_id]
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"🌾 Ферма пшеницы ({BUILDING_COSTS['wheat_farm']['wood']}🌳 {BUILDING_COSTS['wheat_farm']['stone']}🪨)", 
                callback_data='build_wheat'
            )
        ],
        [
            InlineKeyboardButton(
                f"🌳 Лесопилка ({BUILDING_COSTS['wood_farm']['wood']}🌳 {BUILDING_COSTS['wood_farm']['stone']}🪨)", 
                callback_data='build_wood'
            )
        ],
        [
            InlineKeyboardButton(
                f"⛏️ Шахта ({BUILDING_COSTS['stone_mine']['wood']}🌳 {BUILDING_COSTS['stone_mine']['stone']}🪨)", 
                callback_data='build_stone'
            )
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"🏗️ Выберите здание для строительства:\n"
        f"Ваши ресурсы: 🌾{game.resources['wheat']} 🌳{game.resources['wood']} 🪨{game.resources['stone']}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def build_building(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Строительство здания"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    game = players_data[player_id]
    
    building_type = query.data.split('_')[1]  # wheat, wood, stone
    
    building_key = f"{building_type}_farm" if building_type != 'stone' else "stone_mine"
    costs = BUILDING_COSTS[building_key]
    
    # Проверка ресурсов
    if (game.resources['wood'] >= costs['wood'] and 
        game.resources['stone'] >= costs['stone']):
        
        # Списание ресурсов
        game.resources['wood'] -= costs['wood']
        game.resources['stone'] -= costs['stone']
        
        # Строительство
        game.buildings[building_key] += 1
        
        building_names = {
            'wheat': '🌾 Ферму пшеницы',
            'wood': '🌳 Лесопилку',
            'stone': '⛏️ Шахту'
        }
        
        await query.edit_message_text(
            f"✅ {building_names[building_type]} построена!\n"
            f"📈 Производство увеличено\n\n"
            f"Осталось ресурсов:\n"
            f"🌳 Дерево: {game.resources['wood']}\n"
            f"🪨 Камень: {game.resources['stone']}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            f"❌ Недостаточно ресурсов!\n\n"
            f"Нужно: 🌳{costs['wood']} 🪨{costs['stone']}\n"
            f"У вас: 🌳{game.resources['wood']} 🪨{game.resources['stone']}",
            parse_mode='Markdown'
        )

async def build_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Строительство дома"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    game = players_data[player_id]
    
    costs = BUILDING_COSTS['house']
    
    # Проверка ресурсов
    if (game.resources['wood'] >= costs['wood'] and 
        game.resources['stone'] >= costs['stone'] and
        game.resources['wheat'] >= costs['wheat']):
        
        # Списание ресурсов
        game.resources['wood'] -= costs['wood']
        game.resources['stone'] -= costs['stone']
        game.resources['wheat'] -= costs['wheat']
        
        # Строительство дома
        game.buildings['houses'] += 1
        
        await query.edit_message_text(
            f"🏠 Новый дом построен!\n"
            f"Теперь можно принять больше жителей.\n\n"
            f"Осталось ресурсов:\n"
            f"🌾 Пшеница: {game.resources['wheat']}\n"
            f"🌳 Дерево: {game.resources['wood']}\n"
            f"🪨 Камень: {game.resources['stone']}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            f"❌ Недостаточно ресурсов для дома!\n\n"
            f"Нужно: 🌾{costs['wheat']} 🌳{costs['wood']} 🪨{costs['stone']}\n"
            f"У вас: 🌾{game.resources['wheat']} 🌳{game.resources['wood']} 🪨{game.resources['stone']}",
            parse_mode='Markdown'
        )

async def next_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к следующему дню"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    game = players_data[player_id]
    
    # Расход пшеницы на население
    food_needed = game.population * 10
    if game.resources['wheat'] >= food_needed:
        game.resources['wheat'] -= food_needed
        starvation = False
    else:
        # Голод - умирает часть населения
        starvation = True
        deaths = random.randint(1, max(1, game.population // 3))
        game.population = max(0, game.population - deaths)
        game.resources['wheat'] = 0
    
    # Новые жители (случайно)
    if game.buildings['houses'] * 5 > game.population:  # В каждом доме может жить до 5 человек
        new_citizens = random.choices(
            [0, 1, 2], 
            weights=[0.3, 0.5, 0.2], 
            k=1
        )[0]
        game.population += new_citizens
    
    # Случайные события
    events = []
    if random.random() < 0.2:  # 20% шанс события
        event_type = random.choice(['good', 'bad', 'neutral'])
        if event_type == 'good':
            bonus = random.randint(20, 50)
            resource = random.choice(['wheat', 'wood', 'stone'])
            game.resources[resource] += bonus
            events.append(f"🎉 Удача! Нашли {bonus} {resource}")
        elif event_type == 'bad':
            loss = random.randint(10, 30)
            resource = random.choice(['wheat', 'wood', 'stone'])
            game.resources[resource] = max(0, game.resources[resource] - loss)
            events.append(f"🌪️ Бедствие! Потеряно {loss} {resource}")
    
    game.day += 1
    
    # Формируем сообщение
    message = f"📅 День {game.day}\n\n"
    
    if starvation:
        message += f"⚠️ ГОЛОД! Не хватило еды для всех!\n"
        message += f"👥 Население уменьшилось до {game.population}\n\n"
    else:
        message += f"🍞 Население накормлено (-{food_needed}🌾)\n\n"
    
    if events:
        message += "📰 События дня:\n"
        for event in events:
            message += f"• {event}\n"
        message += "\n"
    
    message += (
        f"📊 Ресурсы:\n"
        f"🌾 Пшеница: {game.resources['wheat']}\n"
        f"🌳 Дерево: {game.resources['wood']}\n"
        f"🪨 Камень: {game.resources['stone']}\n"
        f"💰 Золото: {game.resources['gold']}\n\n"
        f"👥 Население: {game.population}\n"
        f"🏠 Домов: {game.buildings['houses']}\n\n"
        f"🏭 Производство в день:\n"
        f"🌾 Фермы: {game.buildings['wheat_farm']} (+{game.buildings['wheat_farm'] * BUILDING_PRODUCTION['wheat_farm']}/день)\n"
        f"🌳 Лесопилки: {game.buildings['wood_farm']} (+{game.buildings['wood_farm'] * BUILDING_PRODUCTION['wood_farm']}/день)\n"
        f"⛏️ Шахты: {game.buildings['stone_mine']} (+{game.buildings['stone_mine'] * BUILDING_PRODUCTION['stone_mine']}/день)"
    )
    
    await query.edit_message_text(message, parse_mode='Markdown')

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус города"""
    query = update.callback_query
    await query.answer()
    
    player_id = query.from_user.id
    game = players_data[player_id]
    
    message = (
        f"🏘️ Статус города\n\n"
        f"📅 День: {game.day}\n\n"
        f"📊 Ресурсы:\n"
        f"🌾 Пшеница: {game.resources['wheat']}\n"
        f"🌳 Дерево: {game.resources['wood']}\n"
        f"🪨 Камень: {game.resources['stone']}\n"
        f"💰 Золото: {game.resources['gold']}\n\n"
        f"👥 Население: {game.population}\n"
        f"🍞 Расход еды: {game.population * 10}/день\n\n"
        f"🏭 Здания:\n"
        f"🌾 Ферм пшеницы: {game.buildings['wheat_farm']}\n"
        f"🌳 Лесопилок: {game.buildings['wood_farm']}\n"
        f"⛏️ Шахт: {game.buildings['stone_mine']}\n"
        f"🏠 Домов: {game.buildings['houses']}\n\n"
        f"📈 Максимум жителей: {game.buildings['houses'] * 5}"
    )
    
    await query.edit_message_text(message, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback запросов"""
    query = update.callback_query
    
    if query.data == 'menu' or query.data == 'back_to_menu':
        await menu(update, context)
    elif query.data == 'build':
        await show_build_menu(update, context)
    elif query.data == 'status':
        await show_status(update, context)
    elif query.data == 'collect':
        await collect_resources(update, context)
    elif query.data == 'build_house':
        await build_house(update, context)
    elif query.data == 'next_day':
        await next_day(update, context)
    elif query.data.startswith('build_'):
        if query.data in ['build_wheat', 'build_wood', 'build_stone']:
            await build_building(update, context)
        else:
            await show_build_menu(update, context)

def main():
    """Запуск бота"""
    # Токен бота (замени на свой)
    TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
