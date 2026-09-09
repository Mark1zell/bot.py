import os
import logging
import json
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://lcgbpwowppwwpjjlphod.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjZ2Jwd293cHB3d3BqamxwaG9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2NDAwNTMsImV4cCI6MjEwNDIxNjA1M30.95VPot7saWmlgv1IzBop3E4x-ZxSc8HepqKdDLJa7JI')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8649063131:AAGZknHiTFk1-Qmi02aCwd-yjD2A03eb-LU')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1492590083'))

# Функции для работы с Supabase через HTTP
def supabase_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json() if response.ok else []

def supabase_get_single(table, id):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    return data[0] if data else None

def supabase_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    response = requests.post(url, headers=headers, json=data)
    data = response.json()
    return data[0] if data else None

def supabase_update(table, id, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    response = requests.patch(url, headers=headers, json=data)
    return response.json() if response.ok else None

# Временное хранилище
user_states = {}

class UserState:
    def __init__(self):
        self.current_service = None
        self.selected_options = {}
        self.description = ''

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🛠️ Услуги", callback_data='services')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("💬 Связаться", url='https://t.me/mark1zell')],
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(f"👋 Привет, {user.first_name}!\n\nВыберите действие:", reply_markup=reply_markup)
    else:
        query = update.callback_query
        await query.edit_message_text(f"👋 Привет, {user.first_name}!\n\nВыберите действие:", reply_markup=reply_markup)

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    services = supabase_get('services', {'order': 'order.asc'})
    
    if not services:
        await query.edit_message_text("Услуги пока не добавлены.")
        return
    
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(
            f"{service.get('emoji', '📦')} {service['name']}", 
            callback_data=f"service_{service['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите услугу:", reply_markup=reply_markup)

async def show_service_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split('_')[1])
    service = supabase_get_single('services', service_id)
    options = supabase_get('service_options', {'service_id': f'eq.{service_id}', 'order': 'order.asc'})
    
    if not service:
        await query.edit_message_text("Услуга не найдена.")
        return
    
    state = get_user_state(query.from_user.id)
    state.current_service = service
    state.selected_options = {}
    
    if not options:
        await query.edit_message_text(f"{service['name']}\n\nНет опций. Свяжитесь: @mark1zell")
        return
    
    keyboard = []
    for option in options:
        max_qty = option.get('max_quantity', 1) or 1
        if max_qty > 1:
            keyboard.append([InlineKeyboardButton(
                f"{option['name']} - {option['price']}₽ (кол-во)", 
                callback_data=f"qty_{option['id']}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{option['name']} - {option['price']}₽", 
                callback_data=f"toggle_{option['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"{service.get('emoji', '📦')} {service['name']}\n\nВыберите опции:", reply_markup=reply_markup)

async def toggle_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    option_id = int(query.data.split('_')[1])
    state = get_user_state(query.from_user.id)
    
    option = supabase_get_single('service_options', option_id)
    if not option:
        return
    
    if option_id in state.selected_options:
        del state.selected_options[option_id]
    else:
        state.selected_options[option_id] = {
            'name': option['name'],
            'price': option['price'],
            'quantity': 1,
            'total': option['price']
        }
    
    await show_service_options(update, context)

async def show_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    option_id = int(query.data.split('_')[1])
    context.user_data['qty_option_id'] = option_id
    
    option = supabase_get_single('service_options', option_id)
    if not option:
        return
    
    max_qty = option.get('max_quantity', 10) or 10
    min_qty = option.get('min_quantity', 1) or 1
    
    keyboard = []
    for i in range(min_qty, min(max_qty, 10) + 1):
        keyboard.append([InlineKeyboardButton(f"{i} шт.", callback_data=f"setqty_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"service_{option['service_id']}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"Количество для: {option['name']}", reply_markup=reply_markup)

async def set_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    qty = int(query.data.split('_')[1])
    option_id = context.user_data.get('qty_option_id')
    state = get_user_state(query.from_user.id)
    
    option = supabase_get_single('service_options', option_id)
    if option:
        price = option['price']
        discount_min = option.get('discount_min_quantity')
        discount_price = option.get('discount_price')
        
        final_price = price
        if discount_min and qty >= discount_min and discount_price:
            final_price = discount_price
        
        state.selected_options[option_id] = {
            'name': option['name'],
            'price': final_price,
            'quantity': qty,
            'total': final_price * qty
        }
    
    await show_service_options(update, context)

async def finish_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    state = get_user_state(query.from_user.id)
    
    if not state.selected_options:
        await query.edit_message_text("Выберите хотя бы одну опцию!")
        return
    
    total = sum(opt['total'] for opt in state.selected_options.values())
    options_text = "\n".join([f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽" for opt in state.selected_options.values()])
    
    await query.edit_message_text(
        f"📋 Ваш заказ:\n\n{options_text}\n\nИтого: {total}₽\n\nОтправьте описание ТЗ:"
    )
    
    context.user_data['awaiting_description'] = True

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    
    if not context.user_data.get('awaiting_description'):
        return
    
    state.description = update.message.text
    context.user_data['awaiting_description'] = False
    
    total = sum(opt['total'] for opt in state.selected_options.values())
    
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
        'status': 'pending_payment'
    }
    
    result = supabase_insert('orders', order_data)
    
    if result:
        order_id = result['id']
        
        keyboard = [
            [InlineKeyboardButton("🔙 В начало", callback_data='back_to_start')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Заказ #{order_id} создан!\n\nСумма: {total}₽\n\nОплатите через приложение или свяжитесь с дизайнером.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Ошибка при создании заказа")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_identifier = user.username or user.first_name or str(user.id)
    
    orders = supabase_get('orders', {
        'or': f'(user_username.eq.{user_identifier},user_name.eq.{user_identifier})',
        'status': 'neq.cancelled',
        'order': 'timestamp.desc'
    })
    
    if not orders:
        await query.edit_message_text("У вас пока нет заказов.")
        return
    
    text = "📋 Ваши заказы:\n\n"
    for order in orders:
        status_emoji = {
            'pending_payment': '⏳',
            'paid_card': '💳',
            'not_started': '🔴',
            'in_progress': '🟡',
            'ready': '✅'
        }.get(order.get('status'), '❓')
        
        text += f"{status_emoji} Заказ #{order['id']} - {order['service']}\n"
        text += f"   Сумма: {order['total']}₽\n"
        text += f"   Статус: {order.get('status', 'неизвестно')}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("Нет доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 Все заказы", callback_data='admin_orders')],
        [InlineKeyboardButton("⏳ Неоплаченные", callback_data='admin_pending')],
        [InlineKeyboardButton("✅ Готовые", callback_data='admin_ready')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("👑 Админ-панель:", reply_markup=reply_markup)

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    filter_type = query.data.split('_')[1] if len(query.data.split('_')) > 1 else 'orders'
    
    params = {'order': 'timestamp.desc', 'limit': '10'}
    if filter_type == 'pending':
        params['status'] = 'eq.pending_payment'
    elif filter_type == 'ready':
        params['status'] = 'eq.ready'
    
    orders = supabase_get('orders', params)
    
    if not orders:
        await query.edit_message_text("Заказов нет.")
        return
    
    keyboard = []
    for order in orders:
        keyboard.append([InlineKeyboardButton(
            f"#{order['id']} - {order['service']} - {order.get('status', '?')}", 
            callback_data=f"admin_order_{order['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Заказы:", reply_markup=reply_markup)

async def admin_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(query.data.split('_')[2])
    order = supabase_get_single('orders', order_id)
    
    if not order:
        await query.edit_message_text("Заказ не найден.")
        return
    
    options = json.loads(order.get('options', '[]'))
    
    text = f"📋 Заказ #{order['id']}\n\n"
    text += f"Услуга: {order['service']}\n"
    text += f"Клиент: {order['user_name']}"
    if order.get('user_username'):
        text += f" (@{order['user_username']})"
    text += f"\nСумма: {order['total']}₽\n"
    text += f"Статус: {order.get('status', '?')}\n\n"
    
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

async def change_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    parts = query.data.split('_')
    order_id = int(parts[1])
    new_status = parts[2]
    
    supabase_update('orders', order_id, {'status': new_status})
    
    await query.answer(f"✅ Статус: {new_status}")
    await admin_order_detail(update, context)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(show_services, pattern='^services$'))
    application.add_handler(CallbackQueryHandler(show_service_options, pattern='^service_'))
    application.add_handler(CallbackQueryHandler(toggle_option, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(show_qty, pattern='^qty_'))
    application.add_handler(CallbackQueryHandler(set_qty, pattern='^setqty_'))
    application.add_handler(CallbackQueryHandler(finish_options, pattern='^finish_options$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_orders, pattern='^admin_'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(change_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description))
    
    application.run_polling()

if __name__ == '__main__':
    main()
