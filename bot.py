import logging
import random
from datetime import datetime
from enum import Enum
from typing import Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Типы ресурсов
class ResourceType(Enum):
    WHEAT = "🌾 Пшеница"
    WOOD = "🪵 Дерево"
    STONE = "⛰️ Камень"

# Типы зданий
class BuildingType(Enum):
    WHEAT_FARM = "🌾 Ферма пшеницы"
    TREE_FARM = "🌳 Ферма деревьев"
    MINE = "⛏️ Шахта"
    HOUSE = "🏠 Дом"

# Класс здания
class Building:
    def __init__(self, building_type: BuildingType, level: int = 1):
        self.type = building_type
        self.level = level
        self.last_production_time = datetime.now()
    
    def get_production_rate(self) -> Dict[ResourceType, float]:
        """Возвращает количество ресурсов в час"""
        rates = {
            BuildingType.WHEAT_FARM: {ResourceType.WHEAT: 20 * self.level},
            BuildingType.TREE_FARM: {ResourceType.WOOD: 15 * self.level},
            BuildingType.MINE: {ResourceType.STONE: 10 * self.level},
        }
        return rates.get(self.type, {})
    
    def upgrade_cost(self) -> Dict[ResourceType, int]:
        """Стоимость улучшения"""
        return {
            ResourceType.WOOD: 100 * self.level,
            ResourceType.STONE: 50 * self.level,
        }

# Класс города
class Town:
    def __init__(self, name: str):
        self.name = name
        self.resources = {
            ResourceType.WHEAT: 500,
            ResourceType.WOOD: 300,
            ResourceType.STONE: 200,
        }
        self.buildings = []
        self.population = 3
        self.max_population = 5
        self.last_update = datetime.now()
        self.day = 1
        self.happiness = 100
        
        # Стартовые постройки
        self.buildings.append(Building(BuildingType.WHEAT_FARM))
        self.buildings.append(Building(BuildingType.TREE_FARM))
        self.buildings.append(Building(BuildingType.HOUSE))
    
    def update_resources(self):
        """Обновление ресурсов на основе времени"""
        now = datetime.now()
        hours_passed = (now - self.last_update).total_seconds() / 3600
        
        if hours_passed > 0:
            # Производство ресурсов
            for building in self.buildings:
                production = building.get_production_rate()
                for resource, rate in production.items():
                    produced = rate * hours_passed
                    self.resources[resource] = max(0, self.resources.get(resource, 0) + produced)
            
            # Потребление пшеницы
            wheat_consumed = self.population * 10 * (hours_passed / 24)
            self.resources[ResourceType.WHEAT] = max(0, self.resources[ResourceType.WHEAT] - wheat_consumed)
            
            # Проверка голода
            if self.resources[ResourceType.WHEAT] <= 0:
                starvation = min(self.population, random.randint(1, 3))
                self.population = max(0, self.population - starvation)
                self.happiness = max(0, self.happiness - 20)
            
            # Случайное прибытие жителей
            if self.population < self.max_population:
                arrival_chance = 0.05 * hours_passed
                if random.random() < arrival_chance:
                    new_residents = random.randint(1, 2)
                    self.population = min(self.max_population, self.population + new_residents)
            
            self.last_update = now
    
    def can_build_house(self) -> Tuple[bool, str]:
        """Проверка возможности постройки дома"""
        required = {
            ResourceType.STONE: 230,
            ResourceType.WOOD: 400,
            ResourceType.WHEAT: 100,
        }
        
        for resource, amount in required.items():
            if self.resources.get(resource, 0) < amount:
                return False, f"Недостаточно {resource.value}"
        
        return True, ""
    
    def build_house(self) -> Tuple[bool, str]:
        """Постройка дома"""
        can_build, message = self.can_build_house()
        if not can_build:
            return False, message
        
        # Списание ресурсов
        self.resources[ResourceType.STONE] -= 230
        self.resources[ResourceType.WOOD] -= 400
        self.resources[ResourceType.WHEAT] -= 100
        
        # Добавление здания
        self.buildings.append(Building(BuildingType.HOUSE))
        self.max_population += 5
        self.happiness = min(100, self.happiness + 10)
        
        return True, "Дом успешно построен!"
    
    def can_build_building(self, building_type: BuildingType) -> Tuple[bool, str]:
        """Проверка возможности постройки здания"""
        costs = {
            BuildingType.WHEAT_FARM: {
                ResourceType.WOOD: 100,
                ResourceType.STONE: 50,
            },
            BuildingType.TREE_FARM: {
                ResourceType.WOOD: 50,
                ResourceType.STONE: 100,
            },
            BuildingType.MINE: {
                ResourceType.WOOD: 150,
                ResourceType.STONE: 50,
            },
        }
        
        if building_type not in costs:
            return False, "Неизвестный тип здания"
        
        cost = costs[building_type]
        for resource, amount in cost.items():
            if self.resources.get(resource, 0) < amount:
                return False, f"Недостаточно {resource.value}"
        
        return True, ""
    
    def build_building(self, building_type: BuildingType) -> Tuple[bool, str]:
        """Постройка производственного здания"""
        can_build, message = self.can_build_building(building_type)
        if not can_build:
            return False, message
        
        # Списание ресурсов
        costs = {
            BuildingType.WHEAT_FARM: {
                ResourceType.WOOD: 100,
                ResourceType.STONE: 50,
            },
            BuildingType.TREE_FARM: {
                ResourceType.WOOD: 50,
                ResourceType.STONE: 100,
            },
            BuildingType.MINE: {
                ResourceType.WOOD: 150,
                ResourceType.STONE: 50,
            },
        }
        
        cost = costs[building_type]
        for resource, amount in cost.items():
            self.resources[resource] -= amount
        
        # Добавление здания
        self.buildings.append(Building(building_type))
        self.happiness = min(100, self.happiness + 5)
        
        return True, f"{building_type.value} построена!"
    
    def get_status_text(self) -> str:
        """Получение текста статуса города"""
        self.update_resources()
        
        # Подсчет зданий
        building_counts = {}
        for building in self.buildings:
            count = building_counts.get(building.type.value, 0)
            building_counts[building.type.value] = count + 1
        
        buildings_text = ""
        for building_name, count in building_counts.items():
            buildings_text += f"  {building_name}: {count}\n"
        
        status = (
            f"🏙️ *{self.name}*\n"
            f"📅 День: {self.day}\n"
            f"😊 Настроение: {self.happiness}/100\n\n"
            
            f"👥 *Население:* {self.population}/{self.max_population}\n\n"
            
            f"📦 *Ресурсы:*\n"
            f"  {ResourceType.WHEAT.value}: {int(self.resources[ResourceType.WHEAT])}\n"
            f"  {ResourceType.WOOD.value}: {int(self.resources[ResourceType.WOOD])}\n"
            f"  {ResourceType.STONE.value}: {int(self.resources[ResourceType.STONE])}\n\n"
            
            f"🏗️ *Постройки:*\n{buildings_text}\n"
            
            f"⚠️ *Внимание:*\n"
            f"  Каждый житель потребляет 10 пшеницы в день\n"
            f"  Дом стоит: 230 камня, 400 дерева, 100 пшеницы\n"
            f"  Жители приходят случайно"
        )
        
        return status

# Главный класс игры
class Game:
    def __init__(self):
        self.towns = {}
    
    def get_town(self, chat_id: int) -> Town:
        """Получение или создание города"""
        if chat_id not in self.towns:
            town_name = f"Городок_{chat_id % 1000}"
            self.towns[chat_id] = Town(town_name)
        
        town = self.towns[chat_id]
        town.update_resources()
        
        return town

# Создаем экземпляр игры
game = Game()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    chat_id = update.effective_chat.id
    town = game.get_town(chat_id)
    
    welcome_text = (
        "🌄 *Добро пожаловать в Суровый Городок!*\n\n"
        "Вы — лидер небольшого поселения в суровых землях.\n"
        "Ваша задача — обеспечить выживание и рост вашего городка.\n\n"
        "*Основные правила:*\n"
        "• Каждый житель потребляет 10 пшеницы в день\n"
        "• Дом стоит: 230 камня, 400 дерева, 100 пшеницы\n"
        "• Дом увеличивает максимальное население на 5\n"
        "• Жители приходят случайно\n\n"
        "Используйте /status чтобы увидеть состояние города."
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Статус", callback_data='status'),
         InlineKeyboardButton("🏗️ Строить", callback_data='build_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status"""
    chat_id = update.effective_chat.id
    town = game.get_town(chat_id)
    
    await show_status(update, context, town)

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE, town: Town) -> None:
    """Показать статус города"""
    status_text = town.get_status_text()
    
    keyboard = [
        [InlineKeyboardButton("🏗️ Строить", callback_data='build_menu'),
         InlineKeyboardButton("🔄 Обновить", callback_data='status')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            status_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            status_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )

async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /build"""
    await show_build_menu(update, context)

async def show_build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню строительства"""
    keyboard = [
        [InlineKeyboardButton("🏠 Дом (230⛰️ 400🪵 100🌾)", callback_data='build_house')],
        [InlineKeyboardButton("🌾 Ферма пшеницы (50⛰️ 100🪵)", callback_data='build_wheat')],
        [InlineKeyboardButton("🌳 Ферма деревьев (100⛰️ 50🪵)", callback_data='build_tree')],
        [InlineKeyboardButton("⛏️ Шахта (50⛰️ 150🪵)", callback_data='build_mine')],
        [InlineKeyboardButton("🔙 Назад", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    menu_text = "🏗️ *Меню строительства*\n\nВыберите что построить:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            menu_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            menu_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    town = game.get_town(chat_id)
    
    if query.data == 'status':
        await show_status(update, context, town)
    
    elif query.data == 'build_menu':
        await show_build_menu(update, context)
    
    elif query.data == 'build_house':
        success, message = town.build_house()
        
        if success:
            result_text = f"✅ {message}\n\n{town.get_status_text()}"
        else:
            result_text = f"❌ Не удалось построить дом: {message}\n\n{town.get_status_text()}"
        
        keyboard = [
            [InlineKeyboardButton("🏗️ Строить ещё", callback_data='build_menu'),
             InlineKeyboardButton("🔙 К статусу", callback_data='status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            result_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
    
    elif query.data in ['build_wheat', 'build_tree', 'build_mine']:
        building_map = {
            'build_wheat': BuildingType.WHEAT_FARM,
            'build_tree': BuildingType.TREE_FARM,
            'build_mine': BuildingType.MINE
        }
        
        building_type = building_map[query.data]
        success, message = town.build_building(building_type)
        
        if success:
            result_text = f"✅ {message}\n\n{town.get_status_text()}"
        else:
            result_text = f"❌ Не удалось построить {building_type.value.lower()}: {message}\n\n{town.get_status_text()}"
        
        keyboard = [
            [InlineKeyboardButton("🏗️ Строить ещё", callback_data='build_menu'),
             InlineKeyboardButton("🔙 К статусу", callback_data='status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            result_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "📖 *Список команд:*\n\n"
        "*/start* - Начать игру\n"
        "*/status* - Показать статус города\n"
        "*/build* - Меню строительства\n"
        "*/help* - Эта справка\n\n"
        
        "*Управление:*\n"
        "Используйте кнопки под сообщениями для управления городом.\n\n"
        
        "*Правила игры:*\n"
        "• Стройте дома для увеличения населения\n"
        "• Стройте фермы и шахты для ресурсов\n"
        "• Следите за запасами пшеницы\n"
        "• Жители приходят случайно\n"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для отладки (только для разработчиков)"""
    chat_id = update.effective_chat.id
    town = game.get_town(chat_id)
    
    # Добавляем немного ресурсов для тестирования
    town.resources[ResourceType.WHEAT] += 100
    town.resources[ResourceType.WOOD] += 100
    town.resources[ResourceType.STONE] += 100
    
    await update.message.reply_text("✅ Ресурсы добавлены! Используйте /status", parse_mode='Markdown')

def main() -> None:
    """Запуск бота"""
    # Замените 'YOUR_BOT_TOKEN' на токен вашего бота
    # Получить токен можно у @BotFather в Telegram
    TOKEN = "YOUR_BOT_TOKEN"
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("build", build_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    
    # Регистрируем обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_UPDATES)

if __name__ == "__main__":
    main()
