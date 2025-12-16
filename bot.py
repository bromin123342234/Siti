from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

class TelegramGameInterface:
    def __init__(self, game: Game):
        self.game = game
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat_id = update.effective_chat.id
        town = self.game.get_or_create_town(chat_id, "Новый Городок")
        
        welcome_text = (
            "🌄 *Добро пожаловать в Суровый Городок!*\n\n"
            "Вы — лидер небольшого поселения в суровых землях. "
            "Ваша задача — обеспечить выживание и рост вашего городка.\n\n"
            "Используйте команду /status чтобы увидеть состояние города.\n"
            "Используйте /build чтобы построить новые здания.\n"
            "Используйте /help для списка всех команд."
        )
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус города"""
        chat_id = update.effective_chat.id
        status_text = self.game.get_town_status(chat_id)
        
        keyboard = [
            [InlineKeyboardButton("🏗️ Строить", callback_data='build_menu')],
            [InlineKeyboardButton("🔄 Обновить", callback_data='refresh')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(status_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def build_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню строительства"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("🏠 Дом (230🪨 400🪵 100🌾)", callback_data='build_house')],
            [InlineKeyboardButton("🌾 Ферма пшеницы (50🪨 100🪵)", callback_data='build_wheat_farm')],
            [InlineKeyboardButton("🌳 Ферма деревьев (100🪨 50🪵)", callback_data='build_tree_farm')],
            [InlineKeyboardButton("⛏️ Шахта (50🪨 150🪵)", callback_data='build_mine')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏗️ *Меню строительства*\n\nВыберите что построить:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_build(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка строительства"""
        query = update.callback_query
        await query.answer()
        
        chat_id = update.effective_chat.id
        town = self.game.towns[chat_id]
        
        building_map = {
            'build_house': (town.build_house, BuildingType.HOUSE),
            'build_wheat_farm': (lambda: town.build_building(BuildingType.WHEAT_FARM), BuildingType.WHEAT_FARM),
            'build_tree_farm': (lambda: town.build_building(BuildingType.TREE_FARM), BuildingType.TREE_FARM),
            'build_mine': (lambda: town.build_building(BuildingType.MINE), BuildingType.MINE)
        }
        
        if query.data in building_map:
            build_func, btype = building_map[query.data]
            success, message = build_func()
            
            if success:
                result_text = f"✅ {message}\n\n{self.game.get_town_status(chat_id)}"
            else:
                result_text = f"❌ {message}\n\n{self.game.get_town_status(chat_id)}"
            
            keyboard = [
                [InlineKeyboardButton("🏗️ Строить ещё", callback_data='build_menu')],
                [InlineKeyboardButton("🔙 К статусу", callback_data='back_to_status')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(result_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback запросов"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'refresh' or query.data == 'back_to_status':
            chat_id = update.effective_chat.id
            status_text = self.game.get_town_status(chat_id)
            
            keyboard = [
                [InlineKeyboardButton("🏗️ Строить", callback_data='build_menu')],
                [InlineKeyboardButton("🔄 Обновить", callback_data='refresh')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(status_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        elif query.data == 'build_menu':
            await self.build_menu(update, context)
        
        elif query.data.startswith('build_'):
            await self.handle_build(update, context)

# Основная функция запуска бота
async def main():
    # Создаем игру и интерфейс
    game = Game()
    interface = TelegramGameInterface(game)
    
    # Создаем приложение
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", interface.start))
    application.add_handler(CommandHandler("status", interface.status))
    application.add_handler(CallbackQueryHandler(interface.handle_callback))
    
    # Запускаем бота
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
