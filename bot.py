import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация Supabase
SUPABASE_URL = 'https://lcgbpwowppwwpjjlphod.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjZ2Jwd293cHB3d3BqamxwaG9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2NDAwNTMsImV4cCI6MjEwNDIxNjA1M30.95VPot7saWmlgv1IzBop3E4x-ZxSc8HepqKdDLJa7JI'
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ID админа
ADMIN_ID = 1492590083  # Замените на ваш Telegram ID

# Токен бота
BOT_TOKEN = '8649063131:AAGZknHiTFk1-Qmi02aCwd-yjD2A03eb-LU'  # Замените на токен вашего бота

# Временное хранилище состояний пользователей
user_states = {}

class UserState:
    def __init__(self):
        self.current_service = None
        self.selected_options = {}
        self.description = ''
        self.current_order_id = None

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

# ================================================================
# КОМАНДЫ БОТА
# ================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🛠️ Услуги", callback_data='services')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("💬 Связаться с дизайнером", url='https://t.me/mark1zell')],
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Добро пожаловать в Mark1z Design Bot!\n"
        f"Выберите действие:",
        reply_markup=reply_markup
    )

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список услуг"""
    query = update.callback_query
    await query.answer()
    
    services = supabase.table('services').select('*').order('order').execute()
    
    if not services.data:
        await query.edit_message_text("Услуги пока не добавлены.")
        return
    
    keyboard = []
    for service in services.data:
        keyboard.append([InlineKeyboardButton(
            f"{service['emoji']} {service['name']}", 
            callback_data=f"service_{service['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите услугу:", reply_markup=reply_markup)

async def show_service_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать опции услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split('_')[1])
    
    service = supabase.table('services').select('*').eq('id', service_id).single().execute()
    options = supabase.table('service_options').select('*').eq('service_id', service_id).order('order').execute()
    
    if not service.data:
        await query.edit_message_text("Услуга не найдена.")
        return
    
    state = get_user_state(query.from_user.id)
    state.current_service = service.data
    state.selected_options = {}
    
    if not options.data:
        await query.edit_message_text(
            f"{service.data['emoji']} {service.data['name']}\n\n"
            f"Для этой услуги пока нет опций.\n"
            f"Свяжитесь с дизайнером: @mark1zell"
        )
        return
    
    keyboard = []
    for option in options.data:
        max_qty = option.get('max_quantity', 1)
        if max_qty > 1:
            keyboard.append([InlineKeyboardButton(
                f"{option['name']} - {option['price']}₽ (выбрать количество)", 
                callback_data=f"option_qty_{option['id']}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{option['name']} - {option['price']}₽", 
                callback_data=f"option_toggle_{option['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"{service.data['emoji']} {service.data['name']}\n\n"
        f"Выберите опции:",
        reply_markup=reply_markup
    )

async def toggle_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить опцию"""
    query = update.callback_query
    await query.answer()
    
    option_id = int(query.data.split('_')[2])
    state = get_user_state(query.from_user.id)
    
    option = supabase.table('service_options').select('*').eq('id', option_id).single().execute()
    
    if not option.data:
        return
    
    if option_id in state.selected_options:
        del state.selected_options[option_id]
        await query.answer(f"❌ Убрано: {option.data['name']}")
    else:
        state.selected_options[option_id] = {
            'name': option.data['name'],
            'price': option.data['price'],
            'quantity': 1,
            'total': option.data['price']
        }
        await query.answer(f"✅ Добавлено: {option.data['name']}")
    
    # Обновляем сообщение
    await show_service_options(update, context)

async def show_quantity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор количества"""
    query = update.callback_query
    await query.answer()
    
    option_id = int(query.data.split('_')[2])
    context.user_data['current_option_id'] = option_id
    
    option = supabase.table('service_options').select('*').eq('id', option_id).single().execute()
    
    if not option.data:
        return
    
    max_qty = option.data.get('max_quantity', 10)
    min_qty = option.data.get('min_quantity', 1)
    
    keyboard = []
    for i in range(min_qty, min(max_qty, 10) + 1):
        keyboard.append([InlineKeyboardButton(f"{i} шт.", callback_data=f"qty_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"service_{context.user_data.get('service_id', '')}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Выберите количество для {option.data['name']}:",
        reply_markup=reply_markup
    )

async def set_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить количество"""
    query = update.callback_query
    await query.answer()
    
    qty = int(query.data.split('_')[1])
    option_id = context.user_data.get('current_option_id')
    state = get_user_state(query.from_user.id)
    
    option = supabase.table('service_options').select('*').eq('id', option_id).single().execute()
    
    if option.data:
        price = option.data['price']
        discount_min = option.data.get('discount_min_quantity')
        discount_price = option.data.get('discount_price')
        
        final_price = price
        if discount_min and qty >= discount_min and discount_price:
            final_price = discount_price
        
        state.selected_options[option_id] = {
            'name': option.data['name'],
            'price': final_price,
            'quantity': qty,
            'total': final_price * qty
        }
        
        await query.answer(f"✅ {option.data['name']} ×{qty}")
    
    await show_service_options(update, context)

async def finish_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершить выбор опций"""
    query = update.callback_query
    await query.answer()
    
    state = get_user_state(query.from_user.id)
    
    if not state.selected_options:
        await query.edit_message_text("Выберите хотя бы одну опцию!")
        return
    
    total = sum(opt['total'] for opt in state.selected_options.values())
    
    options_text = "\n".join([
        f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽"
        for opt in state.selected_options.values()
    ])
    
    await query.edit_message_text(
        f"📋 Ваш заказ:\n\n"
        f"{options_text}\n\n"
        f"Итого: {total}₽\n\n"
        f"Отправьте описание вашего ТЗ (что нужно сделать, стиль, цвета и т.д.):"
    )
    
    context.user_data['awaiting_description'] = True

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания ТЗ"""
    user = update.effective_user
    state = get_user_state(user.id)
    
    if not context.user_data.get('awaiting_description'):
        return
    
    state.description = update.message.text
    context.user_data['awaiting_description'] = False
    
    total = sum(opt['total'] for opt in state.selected_options.values())
    
    # Создаем заказ в Supabase
    order_data = {
        'service': state.current_service['name'],
        'user_name': user.first_name,
        'user_username': user.username,
        'time': datetime.now().strftime('%d.%m.%Y, %H:%M:%S'),
        'timestamp': datetime.now().isoformat(),
        'options': json.dumps(list(state.selected_options.values())),
        'total': total,
        'description': state.description,
        'reference_urls': [],
        'status': 'pending_payment',
        'payment_id': None,
        'paid_at': None,
        'discount_used': 0,
        'original_total': 0,
        'free_option': None,
        'discount_applied': False,
        'discount_percent': 0
    }
    
    result = supabase.table('orders').insert(order_data).execute()
    
    if result.data:
        order_id = result.data[0]['id']
        state.current_order_id = order_id
        
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить картой", callback_data=f'pay_card_{order_id}')],
            [InlineKeyboardButton("🔙 В начало", callback_data='back_to_start')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Заказ #{order_id} создан!\n\n"
            f"Сумма: {total}₽\n\n"
            f"Для оплаты нажмите кнопку ниже:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Ошибка при создании заказа")

async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заказы пользователя"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_identifier = user.username or user.first_name or str(user.id)
    
    orders = supabase.table('orders').select('*').or_(
        f'user_username.eq.{user_identifier},user_name.eq.{user_identifier}'
    ).neq('status', 'cancelled').order('timestamp', desc=True).execute()
    
    if not orders.data:
        await query.edit_message_text("У вас пока нет заказов.")
        return
    
    text = "📋 Ваши заказы:\n\n"
    for order in orders.data:
        status_emoji = {
            'pending_payment': '⏳',
            'paid_card': '💳',
            'not_started': '🔴',
            'in_progress': '🟡',
            'ready': '✅'
        }.get(order['status'], '❓')
        
        text += f"{status_emoji} Заказ #{order['id']} - {order['service']}\n"
        text += f"   Сумма: {order['total']}₽\n"
        text += f"   Статус: {order['status']}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("У вас нет доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 Все заказы", callback_data='admin_orders')],
        [InlineKeyboardButton("📋 Неоплаченные", callback_data='admin_pending')],
        [InlineKeyboardButton("✅ Готовые", callback_data='admin_ready')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("👑 Админ-панель:", reply_markup=reply_markup)

async def admin_show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заказы админу"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    filter_type = query.data.split('_')[1]
    
    if filter_type == 'orders':
        orders = supabase.table('orders').select('*').order('timestamp', desc=True).execute()
    elif filter_type == 'pending':
        orders = supabase.table('orders').select('*').eq('status', 'pending_payment').execute()
    elif filter_type == 'ready':
        orders = supabase.table('orders').select('*').eq('status', 'ready').execute()
    
    if not orders.data:
        await query.edit_message_text("Заказов нет.")
        return
    
    keyboard = []
    for order in orders.data[:10]:  # Показываем первые 10
        keyboard.append([InlineKeyboardButton(
            f"#{order['id']} - {order['service']} - {order['status']}", 
            callback_data=f'admin_order_{order["id"]}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Заказы:", reply_markup=reply_markup)

async def admin_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детали заказа админу"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(query.data.split('_')[2])
    order = supabase.table('orders').select('*').eq('id', order_id).single().execute()
    
    if not order.data:
        await query.edit_message_text("Заказ не найден.")
        return
    
    order = order.data
    options = json.loads(order.get('options', '[]'))
    
    text = f"📋 Заказ #{order['id']}\n\n"
    text += f"Услуга: {order['service']}\n"
    text += f"Клиент: {order['user_name']}"
    if order.get('user_username'):
        text += f" (@{order['user_username']})"
    text += f"\nСумма: {order['total']}₽\n"
    text += f"Статус: {order['status']}\n"
    text += f"Время: {order['time']}\n\n"
    
    if options:
        text += "Опции:\n"
        for opt in options:
            text += f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽\n"
    
    if order.get('description'):
        text += f"\nТЗ: {order['description']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔴 Не приступили", callback_data=f'status_{order_id}_not_started')],
        [InlineKeyboardButton("🟡 Готовится", callback_data=f'status_{order_id}_in_progress')],
        [InlineKeyboardButton("🟢 Готов", callback_data=f'status_{order_id}_ready')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_orders')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def change_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить статус заказа"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    parts = query.data.split('_')
    order_id = int(parts[1])
    new_status = parts[2]
    
    supabase.table('orders').update({'status': new_status}).eq('id', order_id).execute()
    
    await query.answer(f"✅ Статус обновлен: {new_status}")
    await admin_order_details(update, context)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    keyboard = [
        [InlineKeyboardButton("🛠️ Услуги", callback_data='services')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("💬 Связаться с дизайнером", url='https://t.me/mark1zell')],
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Главное меню:",
        reply_markup=reply_markup
    )

# ================================================================
# ЗАПУСК БОТА
# ================================================================

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler('start', start))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(show_services, pattern='^services$'))
    application.add_handler(CallbackQueryHandler(show_service_options, pattern='^service_'))
    application.add_handler(CallbackQueryHandler(toggle_option, pattern='^option_toggle_'))
    application.add_handler(CallbackQueryHandler(show_quantity_selection, pattern='^option_qty_'))
    application.add_handler(CallbackQueryHandler(set_quantity, pattern='^qty_'))
    application.add_handler(CallbackQueryHandler(finish_options, pattern='^finish_options$'))
    application.add_handler(CallbackQueryHandler(show_my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_show_orders, pattern='^admin_(orders|pending|ready)$'))
    application.add_handler(CallbackQueryHandler(admin_order_details, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(change_order_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description))
    
    # Запуск
    application.run_polling()

if __name__ == '__main__':
    main()
