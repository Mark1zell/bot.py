import os
import logging
import json
import requests
import base64
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = 'https://lcgbpwowppwwpjjlphod.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjZ2Jwd293cHB3d3BqamxwaG9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2NDAwNTMsImV4cCI6MjEwNDIxNjA1M30.95VPot7saWmlgv1IzBop3E4x-ZxSc8HepqKdDLJa7JI'
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8649063131:AAGZknHiTFk1-Qmi02aCwd-yjD2A03eb-LU')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1492590083'))

def supabase_get(table, params=None):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception as e:
        print(f"ERROR: {e}")
        return []

def supabase_get_single(table, id):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}"
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        return data[0] if data else None
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
        data = response.json()
        return data[0] if data else None
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

def supabase_update_by_username(table, username, data):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?user_username=eq.{username}"
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

def upload_file(file_data, file_name, folder):
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
        print(f"UPLOAD ERROR: {e}")
        return None

# Русские названия статусов
STATUS_NAMES = {
    'pending_payment': '⏳ Ожидает оплаты',
    'paid_card': '💳 Оплачен',
    'paid_stars': '⭐ Оплачен звёздами',
    'not_started': '🔴 Ещё не приступили',
    'in_progress': '🟡 Готовится',
    'ready': '✅ Готов',
    'cancelled': '❌ Отменён',
    'payment_canceled': '❌ Платёж отменён',
    'refunded': '↩️ Возврат'
}

STATUS_EMOJI = {
    'pending_payment': '⏳',
    'paid_card': '💳',
    'paid_stars': '⭐',
    'not_started': '🔴',
    'in_progress': '🟡',
    'ready': '✅',
    'cancelled': '❌',
    'payment_canceled': '❌',
    'refunded': '↩️'
}

user_states = {}
admin_states = {}

class UserState:
    def __init__(self):
        self.awaiting_review = False
        self.review_stars = 0
        self.review_text = ''
        self.review_images = []
        self.current_order_id = None

class AdminState:
    def __init__(self):
        self.selected_order = None
        self.uploading_work = False
        self.work_files = []
        self.work_message = ''
        self.pending_photos = []
        self.pending_message = ''
        self.processing = False

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

def get_admin_state(user_id):
    if user_id not in admin_states:
        admin_states[user_id] = AdminState()
    return admin_states[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"DEBUG: /start от {user.id} (@{user.username})")
    
    if user.username:
        supabase_update_by_username('orders', user.username, {'user_id': str(user.id)})
    
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
            [InlineKeyboardButton("📋 Все заказы", callback_data='admin_all_orders')],
            [InlineKeyboardButton("⭐ Отзывы", callback_data='show_reviews')],
            [InlineKeyboardButton("🔴 Не начатые", callback_data='admin_not_started')],
        ]
        text = "👑 Админ-панель:"
    else:
        keyboard = [
            [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
            [InlineKeyboardButton("⭐ Отзывы", callback_data='show_reviews')],
            [InlineKeyboardButton("📝 Мои отзывы", callback_data='my_reviews')],
        ]
        text = f"👋 Привет, {user.first_name}!\n\nВы подписаны на уведомления!"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

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

async def my_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_identifier = user.username or user.first_name or str(user.id)
    reviews = supabase_get('reviews', {
        'or': f'(author_username.eq.{user_identifier},author_id.eq.{str(user.id)})',
        'order': 'timestamp.desc'
    })
    if not reviews:
        await query.edit_message_text("📝 У вас пока нет отзывов.")
        return
    text = "📝 Ваши отзывы:\n\n"
    for review in reviews:
        stars = '★' * review.get('stars', 5) + '☆' * (5 - review.get('stars', 5))
        text += f"{stars}\n{review.get('text', '')}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_identifier = user.username or user.first_name or str(user.id)
    orders = supabase_get('orders', {
        'or': f'(user_username.eq.{user_identifier},user_name.eq.{user_identifier},user_id.eq.{str(user.id)})',
        'order': 'timestamp.desc'
    })
    if not orders:
        await query.edit_message_text("📋 Нет заказов.")
        return
    
    keyboard = []
    for order in orders:
        status = order.get('status', 'unknown')
        emoji = STATUS_EMOJI.get(status, '⚪')
        keyboard.append([InlineKeyboardButton(
            f"{emoji} #{order.get('id', '?')} - {order.get('service', 'Нет')}", 
            callback_data=f"my_order_{order.get('id')}"
        )])
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
    
    raw_status = order.get('status', 'unknown')
    status_text = STATUS_NAMES.get(raw_status, f'⚪ {raw_status}')
    
    text = f"📋 Заказ #{order.get('id', '?')}\n\n"
    text += f"🛠️ Услуга: {order.get('service', 'Нет')}\n"
    text += f"📊 Статус: {status_text}\n"
    text += f"💰 Сумма: {order.get('total', 0)}₽\n"
    
    if order.get('work_message'):
        text += f"\n💬 Сообщение от дизайнера:\n{order.get('work_message')}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='my_orders')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Отправляем фото работ
    work_files = order.get('work_files', [])
    if work_files:
        for url in work_files[:10]:
            try:
                await context.bot.send_photo(chat_id=query.from_user.id, photo=url)
            except Exception as e:
                print(f"Ошибка отправки фото: {e}")

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
        keyboard.append([InlineKeyboardButton(f"#{order.get('id', '?')} - {order.get('service', 'Нет')}", callback_data=f"admin_order_{order.get('id')}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text("Все заказы:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_not_started(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    orders = supabase_get('orders', {
        'or': '(status.eq.not_started,status.eq.paid_card,status.eq.in)',
        'order': 'timestamp.desc'
    })
    if not orders:
        await query.edit_message_text("Нет не начатых заказов.")
        return
    keyboard = []
    for order in orders:
        keyboard.append([InlineKeyboardButton(f"#{order.get('id', '?')} - {order.get('service', 'Нет')}", callback_data=f"admin_order_{order.get('id')}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text("🔴 Не начатые заказы:", reply_markup=InlineKeyboardMarkup(keyboard))

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
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
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
        keyboard.append([InlineKeyboardButton(f"📋 #{order.get('id', '?')} - {order.get('service', 'Нет')}", callback_data=f"admin_order_{order.get('id')}")])
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
    
    raw_status = order.get('status', 'unknown')
    status_text = STATUS_NAMES.get(raw_status, f'⚪ {raw_status}')
    
    text = f"📋 Заказ #{order.get('id', '?')}\n\n"
    text += f"🛠️ Услуга: {order.get('service', 'Нет')}\n"
    text += f"👤 Клиент: @{order.get('user_username', 'нет')}\n"
    text += f"💰 Сумма: {order.get('total', 0)}₽\n"
    text += f"📊 Статус: {status_text}\n\n"
    
    if order.get('description'):
        text += f"📝 ТЗ: {order.get('description')}\n"
    
    keyboard = [
        [InlineKeyboardButton("🟡 Готовится", callback_data=f'status_{order_id}_in_progress')],
        [InlineKeyboardButton("🟢 Готов (загрузить работы)", callback_data=f'upload_work_{order_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_users')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

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
    
    status_text = STATUS_NAMES.get(new_status, new_status)
    
    # Уведомляем пользователя
    sent = False
    
    if order and order.get('user_id'):
        try:
            await context.bot.send_message(
                chat_id=int(order['user_id']),
                text=f"📋 Статус заказа #{order_id}:\n{status_text}"
            )
            sent = True
            print(f"✅ Отправлено user_id: {order['user_id']}")
        except Exception as e:
            print(f"❌ user_id: {e}")
    
    if not sent and order and order.get('user_username'):
        try:
            await context.bot.send_message(
                chat_id=f"@{order['user_username']}",
                text=f"📋 Статус заказа #{order_id}:\n{status_text}"
            )
            print(f"✅ Отправлено username: @{order['user_username']}")
        except Exception as e:
            print(f"❌ username: {e}")
    
    await query.answer(f"✅ {status_text}")
    
    try:
        await admin_order_detail(update, context)
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
    state.pending_photos = []
    state.pending_message = ''
    state.processing = False
    
    await query.edit_message_text(
        f"📎 Загрузка работы для заказа #{order_id}\n\n"
        f"Отправьте текст сообщения и фото (до 10 шт.) одним сообщением"
    )

async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    order_id = int(parts[1]) if len(parts) > 1 else None
    
    user = query.from_user
    state = get_user_state(user.id)
    state.awaiting_review = True
    state.review_stars = 0
    state.review_text = ''
    state.review_images = []
    state.current_order_id = order_id
    
    keyboard = []
    for i in range(1, 6):
        keyboard.append([InlineKeyboardButton('⭐' * i, callback_data=f'review_stars_{i}')])
    
    await query.edit_message_text("Поставьте оценку:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_review_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stars = int(query.data.split('_')[2])
    
    user = query.from_user
    state = get_user_state(user.id)
    state.review_stars = stars
    state.review_text = ''
    state.review_images = []
    state.awaiting_review = True
    
    await query.edit_message_text(
        f"Оценка: {'⭐' * stars}\n\n"
        f"📝 Введите текст отзыва:"
    )

async def done_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    
    if not state.awaiting_review:
        await update.message.reply_text("Нет активного отзыва.")
        return
    
    if not state.review_text:
        await update.message.reply_text("Сначала введите текст отзыва.")
        return
    
    order_info = None
    if state.current_order_id:
        order = supabase_get_single('orders', state.current_order_id)
        if order:
            order_info = {
                'service': order.get('service'),
                'total': order.get('total'),
                'options': json.loads(order.get('options', '[]')),
                'time': order.get('time')
            }
    
    review_data = {
        'author_name': user.first_name or user.username or 'Пользователь',
        'author_username': user.username,
        'author_id': str(user.id),
        'stars': state.review_stars,
        'text': state.review_text,
        'images': state.review_images,
        'order_info': order_info,
        'likes_heart': 0,
        'likes_fire': 0,
        'likes_plus': 0,
        'admin_reply': '',
        'timestamp': datetime.now().isoformat()
    }
    
    result = supabase_insert('reviews', review_data)
    
    if result:
        user_identifier = user.username or user.first_name or str(user.id)
        supabase_update('user_last_review', user_identifier, {'can_review': False})
        state.awaiting_review = False
        await update.message.reply_text("✅ Отзыв опубликован! Спасибо!")
    else:
        await update.message.reply_text("❌ Ошибка при публикации.")

def allow_review(order):
    if not order:
        return
    user_identifier = order.get('user_username') or order.get('user_name') or order.get('user_id')
    if not user_identifier:
        return
    try:
        options = json.loads(order.get('options', '[]'))
    except:
        options = []
    order_info = {
        'service': order.get('service'),
        'total': order.get('total'),
        'options': options,
        'time': order.get('time')
    }
    supabase_insert('user_last_review', {
        'user_id': user_identifier,
        'can_review': True,
        'order_info': order_info,
        'timestamp': datetime.now().isoformat()
    })

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    admin_state = get_admin_state(user.id)
    
    if user.id == ADMIN_ID and admin_state.uploading_work:
        await handle_admin_upload(update, context)
        return
    
    if state.awaiting_review:
        await handle_review_message(update, context)
        return

async def handle_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_admin_state(user.id)
    
    if not state.uploading_work or not state.selected_order:
        return
    
    order = state.selected_order
    message_text = update.message.text or update.message.caption or ''
    
    if message_text:
        state.pending_message = message_text
    
    if update.message.photo:
        photo = update.message.photo[-1]
        if photo.file_id not in [p.file_id for p in state.pending_photos]:
            state.pending_photos.append(photo)
            print(f"📸 Получено фото: {len(state.pending_photos)}")
    
    # Если уже обрабатывается - просто добавляем
    if state.processing:
        print("DEBUG: Уже обрабатывается, добавляю фото")
        return
    
    # Запускаем обработку
    state.processing = True
    print("DEBUG: Запуск обработки")
    
    await update.message.reply_text(f"📸 Получено: {len(state.pending_photos)} фото")
    
    # Обрабатываем БЕЗ JobQueue
    await process_pending_work(context, user.id)

async def process_pending_work(context, admin_id=None):
    # Ждем 3 секунды чтобы собрать все фото из media_group
    await asyncio.sleep(3)
    
    state = get_admin_state(admin_id)
    
    if not state.uploading_work or not state.selected_order:
        state.processing = False
        return
    
    order = state.selected_order
    print(f"DEBUG: Обработка {len(state.pending_photos)} фото")
    
    # Загружаем все фото
    for photo in state.pending_photos[:10]:
        try:
            file = await context.bot.get_file(photo.file_id)
            file_data = await file.download_as_bytearray()
            file_name = f"work_{order.get('id', '0')}_{datetime.now().timestamp()}.jpg"
            file_url = upload_file(bytes(file_data), file_name, 'works')
            if file_url:
                state.work_files.append(file_url)
                print(f"✅ Фото загружено")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    state.work_message = state.pending_message
    state.pending_photos = []
    state.pending_message = ''
    
    if state.work_files and state.work_message:
        supabase_update('orders', order.get('id'), {
            'status': 'ready',
            'work_files': state.work_files,
            'work_message': state.work_message
        })
        
        allow_review(order)
        
        sent = False
        chat_id = None
        
        if order.get('user_id'):
            try:
                chat_id = int(order['user_id'])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Ваш заказ #{order.get('id')} готов!\n\n"
                         f"Сообщение от Дизайнера:\n{state.work_message}"
                )
                sent = True
                print(f"✅ Отправлено user_id: {chat_id}")
            except Exception as e:
                print(f"❌ user_id: {e}")
        
        if not sent and order.get('user_username'):
            try:
                chat_id = f"@{order['user_username']}"
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Ваш заказ #{order.get('id')} готов!\n\n"
                         f"Сообщение от Дизайнера:\n{state.work_message}"
                )
                sent = True
                print(f"✅ Отправлено username: {chat_id}")
            except Exception as e:
                print(f"❌ username: {e}")
        
        if sent and state.work_files:
            for url in state.work_files[:10]:
                try:
                    await context.bot.send_photo(chat_id=chat_id, photo=url)
                    print(f"✅ Фото отправлено")
                except Exception as e:
                    print(f"❌ Фото: {e}")
        
        if sent:
            try:
                keyboard = [[InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f'review_{order.get("id")}')]]
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⭐ Понравилась работа? Оставьте отзыв!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                print("✅ Кнопка отзыва отправлена")
            except Exception as e:
                print(f"❌ Кнопка: {e}")
        
        state.uploading_work = False
        state.work_files = []
        state.work_message = ''
        
        try:
            if sent:
                await context.bot.send_message(chat_id=admin_id, text="✅ Работа отправлена клиенту!")
            else:
                await context.bot.send_message(chat_id=admin_id, text="✅ Работа сохранена!")
        except:
            pass
    else:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"❌ Нужно: текст и фото\nФото: {len(state.work_files)}, Текст: {'✅' if state.work_message else '❌'}"
            )
        except:
            pass
    
    state.processing = False

async def handle_review_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    
    if not state.review_text:
        text = update.message.text or update.message.caption or ''
        if text and text != '/done':
            state.review_text = text
            await update.message.reply_text(
                "✅ Текст получен!\n\n"
                "📎 Добавьте фото (до 3) или /done"
            )
        return
    
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"review_{user.id}_{datetime.now().timestamp()}.jpg"
        file_url = upload_file(bytes(file_data), file_name, 'reviews')
        if file_url and len(state.review_images) < 3:
            state.review_images.append(file_url)
            await update.message.reply_text(f"📎 Фото: {len(state.review_images)}/3")
        return

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('done', done_review))
    application.add_handler(CallbackQueryHandler(change_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(upload_work_prompt, pattern='^upload_work_'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(admin_user_orders, pattern='^admin_user_'))
    application.add_handler(CallbackQueryHandler(admin_users, pattern='^admin_users$'))
    application.add_handler(CallbackQueryHandler(admin_all_orders, pattern='^admin_all_orders$'))
    application.add_handler(CallbackQueryHandler(admin_not_started, pattern='^admin_not_started$'))
    application.add_handler(CallbackQueryHandler(my_order_detail, pattern='^my_order_'))
    application.add_handler(CallbackQueryHandler(start_review, pattern='^review_'))
    application.add_handler(CallbackQueryHandler(set_review_stars, pattern='^review_stars_'))
    application.add_handler(CallbackQueryHandler(show_reviews, pattern='^show_reviews$'))
    application.add_handler(CallbackQueryHandler(my_reviews, pattern='^my_reviews$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    application.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
