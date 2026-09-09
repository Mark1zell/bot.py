import os
import logging
import json
import requests
import base64
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
SUPABASE_URL = 'https://lcgbpwowppwwpjjlphod.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjZ2Jwd293cHB3d3BqamxwaG9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2NDAwNTMsImV4cCI6MjEwNDIxNjA1M30.95VPot7saWmlgv1IzBop3E4x-ZxSc8HepqKdDLJa7JI'
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8649063131:AAGZknHiTFk1-Qmi02aCwd-yjD2A03eb-LU')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1492590083'))
YUKASSA_SHOP_ID = '1454329'
YUKASSA_SECRET_KEY = 'live_CrQI-miYwcX7tlYRWVJA3P87VWt9nrUo4hCFgvgcmxI'

# Supabase функции
def supabase_get(table, params=None):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"GET ERROR: {e}")
        return []

def supabase_get_single(table, id):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}"
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        return None
    except Exception as e:
        print(f"GET SINGLE ERROR: {e}")
        return None

def supabase_insert(table, data):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code in [200, 201]:
            data = response.json()
            return data[0] if data else None
        return None
    except Exception as e:
        print(f"INSERT ERROR: {e}")
        return None

def supabase_update(table, id, data):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        response = requests.patch(url, headers=headers, json=data, timeout=15)
        return response.json() if response.ok else None
    except Exception as e:
        print(f"UPDATE ERROR: {e}")
        return None

def upload_file(file_data, file_name, folder):
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/public/public/{folder}/{file_name}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'image/jpeg'
        }
        response = requests.post(url, headers=headers, data=file_data, timeout=30)
        if response.status_code in [200, 201]:
            return url
        return None
    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        return None

def create_yookassa_payment(order_id, amount, description):
    try:
        url = 'https://api.yookassa.ru/v3/payments'
        auth_string = f"{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}"
        auth_base64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Idempotence-Key': f"bot_{order_id}_{datetime.now().timestamp()}",
            'Authorization': f'Basic {auth_base64}'
        }
        data = {
            'amount': {'value': str(amount), 'currency': 'RUB'},
            'confirmation': {'type': 'redirect', 'return_url': 'https://t.me/mark1zell'},
            'description': description,
            'capture': True,
            'metadata': {'order_id': str(order_id)}
        }
        response = requests.post(url, headers=headers, json=data, timeout=15)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"YOOKASSA ERROR: {e}")
        return None

# Состояния
user_states = {}
admin_states = {}

class UserState:
    def __init__(self):
        self.current_service = None
        self.selected_options = {}
        self.description = ''
        self.references = []
        self.current_order_id = None

class AdminState:
    def __init__(self):
        self.selected_order = None
        self.uploading_work = False
        self.work_files = []
        self.work_message = ''

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

def get_admin_state(user_id):
    if user_id not in admin_states:
        admin_states[user_id] = AdminState()
    return admin_states[user_id]

# Пользовательские команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🛠️ Услуги", callback_data='services')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("⭐ Отзывы", callback_data='show_reviews')],
        [InlineKeyboardButton("💬 Связаться", url='https://t.me/mark1zell')],
    ]
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(f"👋 Привет, {user.first_name}!\n\nВыберите действие:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(f"👋 Привет, {user.first_name}!\n\nВыберите действие:", reply_markup=reply_markup)

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    services = supabase_get('services', {'order': 'id.asc'})
    if not services:
        await query.edit_message_text("❌ Услуги не загружены.")
        return
    keyboard = []
    for service in services:
        emoji = service.get('emoji', '📦')
        name = service.get('name', 'Без названия')
        keyboard.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"svc_{service['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text("🛠️ Выберите услугу:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_service_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    if len(parts) < 2:
        return
    service_id = int(parts[1])
    service = supabase_get_single('services', service_id)
    if not service:
        await query.edit_message_text("❌ Услуга не найдена")
        return
    options = supabase_get('service_options', {'service_id': f'eq.{service_id}', 'order': 'id.asc'})
    state = get_user_state(query.from_user.id)
    state.current_service = service
    state.selected_options = {}
    state.references = []
    
    if not options:
        await query.edit_message_text(f"{service.get('emoji', '📦')} {service['name']}\n\nНет опций. @mark1zell")
        return
    
    keyboard = []
    for option in options:
        max_qty = option.get('max_quantity', 1) or 1
        opt_name = option.get('name', 'Без названия')
        opt_price = option.get('price', 0)
        if max_qty > 1:
            keyboard.append([InlineKeyboardButton(f"{opt_name} - {opt_price}₽ (кол-во)", callback_data=f"qty_{option['id']}")])
        else:
            keyboard.append([InlineKeyboardButton(f"{opt_name} - {opt_price}₽", callback_data=f"toggle_{option['id']}")])
    
    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    await query.edit_message_text(f"{service.get('emoji', '📦')} {service['name']}\n\nВыберите опции:", reply_markup=InlineKeyboardMarkup(keyboard))

async def toggle_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split('_')
    if len(parts) < 2:
        await query.answer()
        return
    option_id = int(parts[1])
    state = get_user_state(query.from_user.id)
    option = supabase_get_single('service_options', option_id)
    if not option:
        await query.answer("❌ Опция не найдена", show_alert=True)
        return
    opt_name = option.get('name', 'Опция')
    opt_price = option.get('price', 0)
    if option_id in state.selected_options:
        del state.selected_options[option_id]
        await query.answer(f"❌ Удалено: {opt_name} ({opt_price}₽)")
    else:
        state.selected_options[option_id] = {'name': opt_name, 'price': opt_price, 'quantity': 1, 'total': opt_price}
        await query.answer(f"✅ Добавлено: {opt_name} ({opt_price}₽)")
    await update_options_message(update, context, state)

async def update_options_message(update: Update, context: ContextTypes.DEFAULT_TYPE, state):
    query = update.callback_query
    service = state.current_service
    options = supabase_get('service_options', {'service_id': f'eq.{service["id"]}', 'order': 'id.asc'})
    keyboard = []
    for option in options:
        max_qty = option.get('max_quantity', 1) or 1
        prefix = "✅ " if option['id'] in state.selected_options else ""
        if max_qty > 1:
            keyboard.append([InlineKeyboardButton(f"{prefix}{option['name']} - {option['price']}₽ (кол-во)", callback_data=f"qty_{option['id']}")])
        else:
            keyboard.append([InlineKeyboardButton(f"{prefix}{option['name']} - {option['price']}₽", callback_data=f"toggle_{option['id']}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    
    text = f"{service.get('emoji', '📦')} {service['name']}\n\nВыберите опции:"
    if state.selected_options:
        text += "\n\n✅ Выбранные:\n"
        total = 0
        for opt in state.selected_options.values():
            text += f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽\n"
            total += opt['total']
        text += f"\n💰 Итого: {total}₽"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    if len(parts) < 2:
        return
    option_id = int(parts[1])
    context.user_data['qty_option_id'] = option_id
    option = supabase_get_single('service_options', option_id)
    if not option:
        return
    max_qty = option.get('max_quantity', 10) or 10
    keyboard = []
    for i in range(1, min(max_qty, 10) + 1):
        keyboard.append([InlineKeyboardButton(f"{i} шт.", callback_data=f"setqty_{i}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"svc_{option['service_id']}")])
    await query.edit_message_text(f"Количество: {option['name']}", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    if len(parts) < 2:
        return
    qty = int(parts[1])
    option_id = context.user_data.get('qty_option_id')
    state = get_user_state(query.from_user.id)
    option = supabase_get_single('service_options', option_id)
    if option:
        state.selected_options[option_id] = {'name': option['name'], 'price': option['price'], 'quantity': qty, 'total': option['price'] * qty}
    await update_options_message(update, context, state)

async def finish_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    state = get_user_state(query.from_user.id)
    if not state.selected_options:
        await query.edit_message_text("❌ Выберите хотя бы одну опцию!")
        return
    total = sum(opt['total'] for opt in state.selected_options.values())
    options_text = "\n".join([f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽" for opt in state.selected_options.values()])
    await query.edit_message_text(
        f"📋 Ваш заказ:\n\n{options_text}\n\n💰 Итого: {total}₽\n\n"
        f"<b>Отправьте ОДНИМ сообщением:</b>\n"
        f"1️⃣ Текст ТЗ (опишите что нужно)\n"
        f"2️⃣ Прикрепите до 3 фото-референсов",
        parse_mode='HTML'
    )
    context.user_data['awaiting_order'] = True

async def handle_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    if not context.user_data.get('awaiting_order'):
        return
    
    description = update.message.text or update.message.caption or ''
    photos = []
    if update.message.photo:
        photos.append(update.message.photo[-1])
    
    ref_urls = []
    for photo in photos[:3]:
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"ref_{user.id}_{datetime.now().timestamp()}.jpg"
        file_url = upload_file(bytes(file_data), file_name, 'references')
        if file_url:
            ref_urls.append(file_url)
    
    state.description = description
    state.references = ref_urls
    total = sum(opt['total'] for opt in state.selected_options.values())
    
    order_data = {
        'service': state.current_service['name'],
        'user_name': user.first_name,
        'user_username': user.username,
        'user_id': str(user.id),
        'time': datetime.now().strftime('%d.%m.%Y, %H:%M:%S'),
        'timestamp': datetime.now().isoformat(),
        'options': json.dumps(list(state.selected_options.values())),
        'total': total,
        'description': description,
        'reference_urls': ref_urls,
        'status': 'pending_payment',
        'payment_id': None,
        'paid_at': None
    }
    
    result = supabase_insert('orders', order_data)
    if result:
        order_id = result['id']
        context.user_data['awaiting_order'] = False
        payment = create_yookassa_payment(order_id, total, f"Оплата заказа #{order_id}")
        if payment and payment.get('confirmation', {}).get('confirmation_url'):
            supabase_update('orders', order_id, {'payment_id': payment['id']})
            keyboard = [[InlineKeyboardButton("💳 Оплатить", url=payment['confirmation']['confirmation_url']), InlineKeyboardButton("✅ Я оплатил", callback_data=f'check_payment_{order_id}')]]
            await update.message.reply_text(f"✅ Заказ #{order_id} создан!\n💰 Сумма: {total}₽", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(f"✅ Заказ #{order_id} создан!\nСвяжитесь: @mark1zell")
    else:
        await update.message.reply_text("❌ Ошибка при создании заказа.")

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    if len(parts) < 3:
        return
    order_id = int(parts[2])
    order = supabase_get_single('orders', order_id)
    if not order or not order.get('payment_id'):
        await query.edit_message_text("❌ Платеж не найден")
        return
    auth_string = f"{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    response = requests.get(f"https://api.yookassa.ru/v3/payments/{order['payment_id']}", headers={'Authorization': f'Basic {auth_base64}'})
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'succeeded':
            supabase_update('orders', order_id, {'status': 'paid_card', 'paid_at': datetime.now().isoformat()})
            await query.edit_message_text("✅ Оплата прошла! Дизайнер скоро приступит.")
        else:
            await query.edit_message_text(f"⏳ Статус: {data.get('status')}")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_identifier = user.username or user.first_name or str(user.id)
    orders = supabase_get('orders', {'or': f'(user_username.eq.{user_identifier},user_name.eq.{user_identifier})', 'order': 'timestamp.desc'})
    
    if not orders:
        await query.edit_message_text("📋 У вас пока нет заказов.")
        return
    
    keyboard = []
    for order in orders:
        status_emoji = {'pending_payment': '⏳', 'paid_card': '💳', 'not_started': '🔴', 'in_progress': '🟡', 'ready': '✅'}.get(order.get('status'), '❓')
        keyboard.append([InlineKeyboardButton(
            f"{status_emoji} #{order['id']} - {order['service']} - {order['total']}₽",
            callback_data=f"my_order_{order['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text("📋 Ваши заказы:\nНажмите для деталей:", reply_markup=InlineKeyboardMarkup(keyboard))

async def my_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    if len(parts) < 3:
        return
    order_id = int(parts[2])
    order = supabase_get_single('orders', order_id)
    
    if not order:
        await query.edit_message_text("Заказ не найден.")
        return
    
    options = json.loads(order.get('options', '[]'))
    status_emoji = {'pending_payment': '⏳ Ожидает оплаты', 'paid_card': '💳 Оплачен', 'not_started': '🔴 Ещё не приступили', 'in_progress': '🟡 Готовится', 'ready': '✅ Готов'}.get(order.get('status'), order.get('status'))
    
    text = f"📋 Заказ #{order['id']}\n\n"
    text += f"🛠️ Услуга: {order['service']}\n"
    text += f"📊 Статус: {status_emoji}\n"
    text += f"💰 Сумма: {order['total']}₽\n"
    text += f"📅 Дата: {order.get('time', 'Не указана')}\n\n"
    
    if options:
        text += "📦 Опции:\n"
        for opt in options:
            text += f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽\n"
    
    if order.get('description'):
        text += f"\n📝 Ваше ТЗ:\n{order['description']}\n"
    
    if order.get('work_message'):
        text += f"\n💬 Сообщение от дизайнера:\n{order['work_message']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='my_orders')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    if order.get('reference_urls'):
        for url in order['reference_urls']:
            try:
                await context.bot.send_photo(chat_id=query.from_user.id, photo=url, caption="📎 Референс")
            except:
                pass
    
    if order.get('work_files'):
        media_group = [{'type': 'photo', 'media': url} for url in order['work_files'][:10]]
        if media_group:
            try:
                await context.bot.send_media_group(chat_id=query.from_user.id, media=media_group)
            except:
                pass

async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reviews = supabase_get('reviews', {'order': 'timestamp.desc', 'limit': '10'})
    if not reviews:
        await query.edit_message_text("⭐ Отзывов пока нет.")
        return
    text = "⭐ Отзывы:\n\n"
    for review in reviews:
        stars = '★' * review.get('stars', 5) + '☆' * (5 - review.get('stars', 5))
        text += f"{stars} {review.get('author_name', 'Аноним')}\n{review.get('text', '')}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Админ-панель
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("Нет доступа.")
        return
    keyboard = [
        [InlineKeyboardButton("👥 Пользователи с заказами", callback_data='admin_users')],
        [InlineKeyboardButton("📋 Все заказы", callback_data='admin_all_orders')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')],
    ]
    await query.edit_message_text("👑 Админ-панель:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    orders = supabase_get('orders', {'order': 'timestamp.desc', 'limit': '20'})
    if not orders:
        await query.edit_message_text("Нет заказов.")
        return
    keyboard = []
    for order in orders:
        status = order.get('status', '?')
        keyboard.append([InlineKeyboardButton(f"#{order['id']} - {order['service']} ({status})", callback_data=f"admin_order_{order['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')])
    await query.edit_message_text("Все заказы:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    orders = supabase_get('orders', {'order': 'timestamp.desc'})
    if not orders:
        await query.edit_message_text("Нет заказов.")
        return
    users = {}
    for order in orders:
        uname = order.get('user_username') or order.get('user_name') or 'Unknown'
        if uname not in users:
            users[uname] = []
        users[uname].append(order)
    keyboard = []
    for uname, user_orders in users.items():
        keyboard.append([InlineKeyboardButton(f"👤 @{uname} ({len(user_orders)} зак.)", callback_data=f"admin_user_{uname}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')])
    await query.edit_message_text("👥 Пользователи:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    uname = query.data.replace('admin_user_', '')
    orders = supabase_get('orders', {'or': f'(user_username.eq.{uname},user_name.eq.{uname})', 'order': 'timestamp.desc'})
    if not orders:
        await query.edit_message_text("Заказы не найдены.")
        return
    keyboard = []
    for order in orders:
        status = order.get('status', '?')
        keyboard.append([InlineKeyboardButton(f"📋 #{order['id']} - {order['service']} ({status})", callback_data=f"admin_order_{order['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_users')])
    await query.edit_message_text(f"Заказы @{uname}:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split('_')
    if len(parts) < 3:
        return
    order_id = int(parts[2])
    order = supabase_get_single('orders', order_id)
    if not order:
        await query.edit_message_text("Заказ не найден.")
        return
    state = get_admin_state(query.from_user.id)
    state.selected_order = order
    
    options = json.loads(order.get('options', '[]'))
    text = f"📋 Заказ #{order['id']}\n\n"
    text += f"Услуга: {order['service']}\n"
    text += f"Клиент: @{order.get('user_username', 'нет')}\n"
    text += f"Сумма: {order['total']}₽\n"
    text += f"Статус: {order.get('status', '?')}\n\n"
    if options:
        text += "Опции:\n"
        for opt in options:
            text += f"• {opt['name']} ×{opt['quantity']}\n"
    if order.get('description'):
        text += f"\nТЗ: {order['description']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🟡 Готовится", callback_data=f'status_{order_id}_in_progress')],
        [InlineKeyboardButton("🟢 Готов (загрузить работы)", callback_data=f'upload_work_{order_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_users')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    if order.get('reference_urls'):
        for url in order['reference_urls']:
            try:
                await context.bot.send_photo(chat_id=query.from_user.id, photo=url, caption=f"Референс заказа #{order['id']}")
            except:
                pass

async def upload_work_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split('_')
    if len(parts) < 3:
        return
    order_id = int(parts[2])
    state = get_admin_state(query.from_user.id)
    state.selected_order = supabase_get_single('orders', order_id)
    state.uploading_work = True
    state.work_files = []
    state.work_message = ''
    
    await query.edit_message_text(
        f"📎 Загрузка работы для заказа #{order_id}\n\n"
        f"Отправьте сообщение и фото (до 10 шт.)\n"
        f"Формат: текст + фото одним сообщением"
    )

async def handle_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await handle_order(update, context)
        return
    
    state = get_admin_state(user.id)
    if not state.uploading_work or not state.selected_order:
        return
    
    order = state.selected_order
    message_text = update.message.text or update.message.caption or ''
    photos = []
    if update.message.photo:
        photos.append(update.message.photo[-1])
    
    if message_text:
        state.work_message = message_text
    
    for photo in photos[:10]:
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"work_{order['id']}_{datetime.now().timestamp()}.jpg"
        file_url = upload_file(bytes(file_data), file_name, 'works')
        if file_url:
            state.work_files.append(file_url)
    
    if state.work_files and state.work_message:
        supabase_update('orders', order['id'], {
            'status': 'ready',
            'work_files': state.work_files,
            'work_message': state.work_message
        })
        
        # Отправляем клиенту по user_id (более надежно)
        print(f"DEBUG: Отправка работы для заказа #{order['id']}")
        print(f"DEBUG: user_id = {order.get('user_id')}")
        print(f"DEBUG: user_username = {order.get('user_username')}")
        
        chat_id = None
        if order.get('user_id'):
            chat_id = int(order['user_id'])
        elif order.get('user_username'):
            chat_id = f"@{order['user_username']}"
        
        if chat_id:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Ваш заказ #{order['id']} готов!\n\nСообщение от Дизайнера:\n{state.work_message}"
                )
                print("✅ Текст отправлен")
                
                media_group = [{'type': 'photo', 'media': url} for url in state.work_files[:10]]
                if media_group:
                    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
                    print("✅ Фото отправлены")
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⭐ Напишите ваш отзыв сюда, он автоматически опубликуется в приложении!"
                )
                print("✅ Запрос отзыва отправлен")
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")
        else:
            print("❌ Нет chat_id для отправки")
        
        state.uploading_work = False
        state.work_files = []
        state.work_message = ''
        await update.message.reply_text("✅ Работа отправлена клиенту!")
    else:
        await update.message.reply_text(f"📎 Получено: {len(state.work_files)} фото\nТекст: {'✅' if state.work_message else '❌'}\nОтправьте еще или /done для завершения")

async def change_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split('_')
    if len(parts) < 3:
        return
    order_id = int(parts[1])
    new_status = parts[2]
    supabase_update('orders', order_id, {'status': new_status})
    order = supabase_get_single('orders', order_id)
    
    print(f"DEBUG: Отправка уведомления для заказа #{order_id}")
    print(f"DEBUG: user_id = {order.get('user_id') if order else None}")
    print(f"DEBUG: user_username = {order.get('user_username') if order else None}")
    
    if order:
        status_text = {
            'not_started': '🔴 Ещё не приступили',
            'in_progress': '🟡 Готовится',
            'ready': '✅ Готов!'
        }.get(new_status, new_status)
        
        chat_id = None
        if order.get('user_id'):
            chat_id = int(order['user_id'])
        elif order.get('user_username'):
            chat_id = f"@{order['user_username']}"
        
        if chat_id:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📋 Обновление статуса заказа #{order_id}\n\n"
                         f"Услуга: {order['service']}\n"
                         f"Статус: {status_text}\n"
                         f"Сумма: {order['total']}₽"
                )
                print(f"✅ Уведомление отправлено: {chat_id}")
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")
    
    await query.answer(f"✅ {new_status}")
    await admin_order_detail(update, context)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(set_qty, pattern='^setqty_'))
    application.add_handler(CallbackQueryHandler(show_qty, pattern='^qty_'))
    application.add_handler(CallbackQueryHandler(toggle_option, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(check_payment, pattern='^check_payment_'))
    application.add_handler(CallbackQueryHandler(change_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(upload_work_prompt, pattern='^upload_work_'))
    application.add_handler(CallbackQueryHandler(my_order_detail, pattern='^my_order_'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(admin_user_orders, pattern='^admin_user_'))
    application.add_handler(CallbackQueryHandler(show_service_options, pattern='^svc_'))
    application.add_handler(CallbackQueryHandler(finish_options, pattern='^finish_options$'))
    application.add_handler(CallbackQueryHandler(show_reviews, pattern='^show_reviews$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_users, pattern='^admin_users$'))
    application.add_handler(CallbackQueryHandler(admin_all_orders, pattern='^admin_all_orders$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    application.add_handler(CallbackQueryHandler(show_services, pattern='^services$'))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_admin_upload))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()