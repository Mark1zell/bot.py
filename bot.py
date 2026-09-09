import os
import logging
import json
import requests
import base64
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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
        print(f"ERROR: {e}")
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
        print(f"ERROR: {e}")
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
        print(f"ERROR: {e}")
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
        print(f"ERROR: {e}")
        return None

def upload_file_to_storage(file_data, file_name, folder):
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/{folder}/{file_name}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'image/jpeg',
            'x-upsert': 'true'
        }
        response = requests.post(url, headers=headers, data=file_data, timeout=30)
        if response.status_code in [200, 201]:
            return f"{SUPABASE_URL}/storage/v1/object/public/{folder}/{file_name}"
        return None
    except Exception as e:
        print(f"Upload error: {e}")
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
        print(f"Yookassa error: {e}")
        return None

def check_yookassa_payment_status(payment_id):
    try:
        url = f"https://api.yookassa.ru/v3/payments/{payment_id}"
        auth_string = f"{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        headers = {'Authorization': f'Basic {auth_base64}'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Check payment error: {e}")
        return None

# Состояния
user_states = {}

class UserState:
    def __init__(self):
        self.current_service = None
        self.selected_options = {}
        self.description = ''
        self.references = []

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

# АВТОМАТИЧЕСКАЯ ПРОВЕРКА ПЛАТЕЖЕЙ
async def auto_check_payments(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет все pending заказы и уведомляет админа об оплате"""
    print("🔄 Автопроверка платежей...")
    
    # Получаем все заказы со статусом pending_payment
    orders = supabase_get('orders', {'status': 'eq.pending_payment'})
    
    for order in orders:
        payment_id = order.get('payment_id')
        if not payment_id:
            continue
        
        payment_data = check_yookassa_payment_status(payment_id)
        
        if payment_data and payment_data.get('status') == 'succeeded':
            # Обновляем статус заказа
            supabase_update('orders', order['id'], {
                'status': 'paid_card',
                'paid_at': datetime.now().isoformat()
            })
            
            # Уведомляем админа
            options = json.loads(order.get('options', '[]'))
            options_text = "\n".join([f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽" for opt in options])
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💰 ЗАКАЗ #{order['id']} ОПЛАЧЕН!\n\n"
                     f"Услуга: {order['service']}\n"
                     f"Сумма: {order['total']}₽\n"
                     f"Клиент: @{order.get('user_username', 'нет')}\n\n"
                     f"Опции:\n{options_text}\n\n"
                     f"ТЗ: {order.get('description', 'Нет')}"
            )
            
            # Отправляем референсы админу
            if order.get('reference_urls'):
                for ref_url in order['reference_urls']:
                    try:
                        await context.bot.send_photo(
                            chat_id=ADMIN_ID,
                            photo=ref_url,
                            caption=f"Референс заказа #{order['id']}"
                        )
                    except:
                        pass
            
            # Уведомляем пользователя (если он начал диалог)
            if order.get('user_id'):
                try:
                    await context.bot.send_message(
                        chat_id=int(order['user_id']),
                        text=f"✅ Ваш заказ #{order['id']} оплачен!\nДизайнер скоро приступит к работе."
                    )
                except:
                    pass
            
            print(f"✅ Заказ #{order['id']} оплачен (автопроверка)")

# АВТОМАТИЧЕСКАЯ ОТПРАВКА УВЕДОМЛЕНИЙ О СТАТУСАХ
async def auto_check_status_changes(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет изменения статусов и уведомляет пользователей"""
    # Получаем заказы с новыми статусами
    orders = supabase_get('orders', {'order': 'timestamp.desc', 'limit': '50'})
    
    for order in orders:
        status = order.get('status')
        user_id = order.get('user_id')
        
        if not user_id:
            continue
        
        # Проверяем, было ли уже отправлено уведомление для этого статуса
        notification_key = f"notified_{order['id']}_{status}"
        
        # В реальном приложении нужно хранить отправленные уведомления в БД
        # Для простоты - просто отправляем
        
        status_text_map = {
            'paid_card': '💳 Оплачен! Дизайнер скоро приступит.',
            'not_started': '🔴 Дизайнер ещё не приступил к работе.',
            'in_progress': '🟡 Дизайнер приступил к вашей работе!',
            'ready': '✅ Ваша работа готова!'
        }
        
        if status in status_text_map:
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"📋 Заказ #{order['id']}\n\n{status_text_map[status]}"
                )
            except:
                pass

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')],
        ]
        text = "👑 Привет, Админ!"
    else:
        keyboard = [
            [InlineKeyboardButton("🛠️ Услуги", callback_data='services')],
            [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
            [InlineKeyboardButton("⭐ Отзывы", callback_data='show_reviews')],
            [InlineKeyboardButton("💬 Связаться", url='https://t.me/mark1zell')],
        ]
        text = f"👋 Привет, {user.first_name}!"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    services = supabase_get('services', {'order': 'id.asc'})
    if not services:
        await query.edit_message_text("❌ Услуги не загружены.")
        return
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(f"{service.get('emoji','📦')} {service['name']}", callback_data=f"svc_{service['id']}")])
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
        await query.edit_message_text(f"{service.get('emoji','📦')} {service['name']}\n\nНет опций.")
        return
    
    keyboard = []
    for option in options:
        keyboard.append([InlineKeyboardButton(f"{option['name']} - {option['price']}₽", callback_data=f"toggle_{option['id']}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    await query.edit_message_text(f"{service.get('emoji','📦')} {service['name']}\n\nВыберите опции:", reply_markup=InlineKeyboardMarkup(keyboard))

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
        await query.answer("❌ Не найдено", show_alert=True)
        return
    if option_id in state.selected_options:
        del state.selected_options[option_id]
        await query.answer(f"❌ Удалено: {option['name']}")
    else:
        state.selected_options[option_id] = {'name': option['name'], 'price': option['price'], 'quantity': 1, 'total': option['price']}
        await query.answer(f"✅ Добавлено: {option['name']} ({option['price']}₽)")
    await update_options_message(update, context, state)

async def update_options_message(update: Update, context: ContextTypes.DEFAULT_TYPE, state):
    query = update.callback_query
    service = state.current_service
    options = supabase_get('service_options', {'service_id': f'eq.{service["id"]}', 'order': 'id.asc'})
    keyboard = []
    for option in options:
        prefix = "✅ " if option['id'] in state.selected_options else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{option['name']} - {option['price']}₽", callback_data=f"toggle_{option['id']}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    
    text = f"{service.get('emoji','📦')} {service['name']}\n\nВыберите опции:"
    if state.selected_options:
        text += "\n\n✅ Выбранные:\n"
        total = 0
        for opt in state.selected_options.values():
            text += f"• {opt['name']} = {opt['total']}₽\n"
            total += opt['total']
        text += f"\n💰 Итого: {total}₽"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def finish_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    state = get_user_state(query.from_user.id)
    if not state.selected_options:
        await query.edit_message_text("❌ Выберите опции!")
        return
    total = sum(opt['total'] for opt in state.selected_options.values())
    options_text = "\n".join([f"• {opt['name']} = {opt['total']}₽" for opt in state.selected_options.values()])
    await query.edit_message_text(
        f"📋 Заказ:\n\n{options_text}\n\n💰 Итого: {total}₽\n\n"
        f"Отправьте ОДНИМ сообщением:\n1️⃣ Текст ТЗ\n2️⃣ До 3 фото"
    )
    context.user_data['awaiting_order'] = True

async def handle_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    
    if not context.user_data.get('awaiting_order'):
        return
    
    description = update.message.text or update.message.caption or ''
    
    # Загружаем фото
    ref_urls = []
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"ref_{user.id}_{int(datetime.now().timestamp())}.jpg"
        file_url = upload_file_to_storage(bytes(file_data), file_name, 'references')
        if file_url:
            ref_urls.append(file_url)
            print(f"✅ Референс загружен: {file_url}")
    
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
            payment_url = payment['confirmation']['confirmation_url']
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить", url=payment_url)],
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f'check_payment_{order_id}')],
            ]
            await update.message.reply_text(f"✅ Заказ #{order_id} создан!\n💰 Сумма: {total}₽", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(f"✅ Заказ #{order_id} создан!")
    else:
        await update.message.reply_text("❌ Ошибка создания заказа.")

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
    
    await query.edit_message_text("🔄 Проверяем оплату...")
    
    payment_data = check_yookassa_payment_status(order['payment_id'])
    
    if payment_data and payment_data.get('status') == 'succeeded':
        supabase_update('orders', order_id, {'status': 'paid_card', 'paid_at': datetime.now().isoformat()})
        await query.edit_message_text("✅ Оплата прошла!")
    else:
        keyboard = [[InlineKeyboardButton("🔄 Проверить снова", callback_data=f'check_payment_{order_id}')]]
        await query.edit_message_text("⏳ Оплата не обнаружена:", reply_markup=InlineKeyboardMarkup(keyboard))

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_identifier = user.username or user.first_name or str(user.id)
    orders = supabase_get('orders', {'or': f'(user_username.eq.{user_identifier},user_name.eq.{user_identifier},user_id.eq.{str(user.id)})', 'order': 'timestamp.desc'})
    if not orders:
        await query.edit_message_text("📋 Нет заказов.")
        return
    
    status_map = {'pending_payment': '⏳', 'paid_card': '💳', 'not_started': '🔴', 'in_progress': '🟡', 'ready': '✅'}
    keyboard = []
    for order in orders:
        emoji = status_map.get(order.get('status'), '❓')
        keyboard.append([InlineKeyboardButton(f"{emoji} #{order['id']} - {order['service']} - {order['total']}₽", callback_data=f"my_order_{order['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text("📋 Ваши заказы:", reply_markup=InlineKeyboardMarkup(keyboard))

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
    
    status_map = {
        'pending_payment': '⏳ Ожидает оплаты',
        'paid_card': '💳 Оплачен',
        'not_started': '🔴 Дизайнер ещё не приступил',
        'in_progress': '🟡 Дизайнер приступил к вашей работе',
        'ready': '✅ Работа готова!'
    }
    
    text = f"📋 Заказ #{order['id']}\n\n"
    text += f"Услуга: {order['service']}\n"
    text += f"Статус: {status_map.get(order.get('status'), order.get('status'))}\n"
    text += f"Сумма: {order['total']}₽\n"
    if order.get('description'):
        text += f"\nТЗ: {order['description']}\n"
    if order.get('work_message'):
        text += f"\n💬 Сообщение: {order['work_message']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='my_orders')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

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
        return
    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
        [InlineKeyboardButton("📋 Все заказы", callback_data='admin_all_orders')],
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
        keyboard.append([InlineKeyboardButton(f"#{order['id']} - {order['service']}", callback_data=f"admin_order_{order['id']}")])
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
        keyboard.append([InlineKeyboardButton(f"👤 @{uname} ({len(user_orders)})", callback_data=f"admin_user_{uname}")])
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
        keyboard.append([InlineKeyboardButton(f"📋 #{order['id']} - {order['service']}", callback_data=f"admin_order_{order['id']}")])
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
    
    status_map = {'pending_payment': '⏳ Ожидает', 'paid_card': '💳 Оплачен', 'not_started': '🔴 Не приступили', 'in_progress': '🟡 Готовится', 'ready': '✅ Готов'}
    
    text = f"📋 Заказ #{order['id']}\n\n"
    text += f"Услуга: {order['service']}\n"
    text += f"Клиент: @{order.get('user_username', 'нет')}\n"
    text += f"Сумма: {order['total']}₽\n"
    text += f"Статус: {status_map.get(order.get('status'), order.get('status'))}\n"
    if order.get('description'):
        text += f"\nТЗ: {order['description']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🟡 Приступил", callback_data=f'status_{order_id}_in_progress')],
        [InlineKeyboardButton("🟢 Готов", callback_data=f'upload_work_{order_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_users')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    if order.get('reference_urls'):
        for url in order['reference_urls']:
            try:
                await context.bot.send_photo(chat_id=query.from_user.id, photo=url, caption=f"Референс #{order_id}")
            except:
                pass

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
    
    status_text_map = {
        'not_started': '🔴 Дизайнер ещё не приступил',
        'in_progress': '🟡 Дизайнер приступил к вашей работе!',
        'ready': '✅ Ваша работа готова!'
    }
    status_text = status_text_map.get(new_status, new_status)
    
    if order and order.get('user_id'):
        try:
            await context.bot.send_message(
                chat_id=int(order['user_id']),
                text=f"📋 Статус заказа #{order_id}: {status_text}"
            )
        except:
            pass
    
    await query.answer("✅ Статус обновлен!")
    await admin_order_detail(update, context)

async def upload_work_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split('_')
    if len(parts) < 3:
        return
    order_id = int(parts[2])
    context.user_data['upload_order_id'] = order_id
    context.user_data['uploading_work'] = True
    context.user_data['work_files'] = []
    context.user_data['work_message'] = ''
    
    await query.edit_message_text(f"📎 Загрузка работы для заказа #{order_id}\n\nОтправьте текст и фото")

async def handle_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await handle_order(update, context)
        return
    
    if not context.user_data.get('uploading_work'):
        return
    
    order_id = context.user_data.get('upload_order_id')
    message_text = update.message.text or update.message.caption or ''
    
    if message_text:
        context.user_data['work_message'] = message_text
    
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"work_{order_id}_{int(datetime.now().timestamp())}.jpg"
        file_url = upload_file_to_storage(bytes(file_data), file_name, 'works')
        if file_url:
            context.user_data['work_files'].append(file_url)
    
    work_files = context.user_data.get('work_files', [])
    work_message = context.user_data.get('work_message', '')
    
    if work_files and work_message:
        supabase_update('orders', order_id, {
            'status': 'ready',
            'work_files': work_files,
            'work_message': work_message
        })
        context.user_data['uploading_work'] = False
        
        # Уведомляем пользователя
        order = supabase_get_single('orders', order_id)
        if order and order.get('user_id'):
            try:
                await context.bot.send_message(
                    chat_id=int(order['user_id']),
                    text=f"✅ Ваш заказ #{order_id} готов!\n\n{work_message}"
                )
                media_group = [{'type': 'photo', 'media': url} for url in work_files[:10]]
                if media_group:
                    await context.bot.send_media_group(chat_id=int(order['user_id']), media=media_group)
            except:
                pass
        
        await update.message.reply_text(f"✅ Работа сохранена! Фото: {len(work_files)}")
    else:
        await update.message.reply_text(f"📎 Фото: {len(work_files)}, Текст: {'✅' if work_message else '❌'}")

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

def main():
    print("Запуск бота...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler('start', start))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(change_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(upload_work_prompt, pattern='^upload_work_'))
    application.add_handler(CallbackQueryHandler(my_order_detail, pattern='^my_order_'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(admin_user_orders, pattern='^admin_user_'))
    application.add_handler(CallbackQueryHandler(show_service_options, pattern='^svc_'))
    application.add_handler(CallbackQueryHandler(toggle_option, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(check_payment, pattern='^check_payment_'))
    application.add_handler(CallbackQueryHandler(finish_options, pattern='^finish_options$'))
    application.add_handler(CallbackQueryHandler(show_reviews, pattern='^show_reviews$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_users, pattern='^admin_users$'))
    application.add_handler(CallbackQueryHandler(admin_all_orders, pattern='^admin_all_orders$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    application.add_handler(CallbackQueryHandler(show_services, pattern='^services$'))
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_admin_upload))
    
    # Автоматическая проверка платежей каждые 30 секунд
    application.job_queue.run_repeating(auto_check_payments, interval=30, first=10)
    
    # Автоматическая проверка статусов каждые 60 секунд
    application.job_queue.run_repeating(auto_check_status_changes, interval=60, first=20)
    
    print("✅ Бот запущен!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
