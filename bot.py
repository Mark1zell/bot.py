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
    
    if user.id == ADMIN_ID:
        keyboard = [[InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')]]
        text = "👑 Привет, Админ!"
    else:
        keyboard = [
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
        keyboard.append([InlineKeyboardButton(f"{emoji} #{order.get('id', '?')} - {order.get('service', 'Нет')}", callback_data=f"my_order_{order.get('id')}")])
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
    
    text = f"📋 Заказ #{order.get('id', '?')}\n\n"
    text += f"Услуга: {order.get('service', 'Нет')}\n"
    text += f"Статус: {status_map.get(order.get('status'), 'Неизвестно')}\n"
    text += f"Сумма: {order.get('total', 0)}₽\n"
    
    if order.get('work_message'):
        text += f"\n💬 Сообщение: {order.get('work_message')}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='my_orders')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    if order.get('work_files'):
        media_group = [{'type': 'photo', 'media': url} for url in order.get('work_files', [])[:10]]
        if media_group:
            try:
                await context.bot.send_media_group(chat_id=query.from_user.id, media=media_group)
            except:
                pass

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
        keyboard.append([InlineKeyboardButton(f"#{order.get('id', '?')} - {order.get('service', 'Нет')}", callback_data=f"admin_order_{order.get('id')}")])
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
    
    text = f"📋 Заказ #{order.get('id', '?')}\n\n"
    text += f"Услуга: {order.get('service', 'Нет')}\n"
    text += f"Клиент: @{order.get('user_username', 'нет')}\n"
    text += f"Сумма: {order.get('total', 0)}₽\n"
    text += f"Статус: {order.get('status', '?')}\n\n"
    
    if order.get('description'):
        text += f"ТЗ: {order.get('description')}\n"
    
    keyboard = [
        [InlineKeyboardButton("🟡 Готовится", callback_data=f'status_{order_id}_in_progress')],
        [InlineKeyboardButton("🟢 Готов (загрузить)", callback_data=f'upload_work_{order_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_users')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    if order.get('reference_urls'):
        for url in order.get('reference_urls'):
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
    
    if order:
        user_username = order.get('user_username')
        if user_username:
            try:
                await context.bot.send_message(
                    chat_id=f"@{user_username}",
                    text=f"📋 Статус заказа #{order_id}: {status_text}"
                )
                print(f"✅ Уведомление отправлено @{user_username}")
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")
    
    await query.answer("✅ Статус обновлен!")
    await admin_order_detail(update, context)

async def upload_work_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split('_')
    order_id = int(parts[2])
    state = get_admin_state(query.from_user.id)
    state.selected_order = supabase_get_single('orders', order_id)
    state.uploading_work = True
    state.work_files = []
    state.work_message = ''
    
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
    
    await query.edit_message_text(
        f"Оценка: {'⭐' * stars}\n\n"
        f"Напишите ваш отзыв текстом и прикрепите фото (до 3 шт.)"
    )

def allow_review(order):
    user_identifier = order.get('user_username') or order.get('user_name') or order.get('user_id')
    if not user_identifier:
        return
    
    options = json.loads(order.get('options', '[]'))
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
    photos = []
    if update.message.photo:
        photos.append(update.message.photo[-1])
    
    if message_text:
        state.work_message = message_text
    
    for photo in photos[:10]:
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"work_{order.get('id')}_{datetime.now().timestamp()}.jpg"
        file_url = upload_file(bytes(file_data), file_name, 'works')
        if file_url:
            state.work_files.append(file_url)
    
    if state.work_files and state.work_message:
        supabase_update('orders', order.get('id'), {
            'status': 'ready',
            'work_files': state.work_files,
            'work_message': state.work_message
        })
        
        allow_review(order)
        
        sent = False
        chat_id = None
        
        if order.get('user_username'):
            try:
                chat_id = f"@{order.get('user_username')}"
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Ваш заказ #{order.get('id')} готов!\n\n"
                         f"Сообщение от Дизайнера:\n{state.work_message}"
                )
                sent = True
                print(f"✅ Отправлено @{order.get('user_username')}")
            except Exception as e:
                print(f"❌ Ошибка username: {e}")
        
        if not sent and order.get('user_id'):
            try:
                chat_id = int(order.get('user_id'))
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Ваш заказ #{order.get('id')} готов!\n\n"
                         f"Сообщение от Дизайнера:\n{state.work_message}"
                )
                sent = True
                print(f"✅ Отправлено user_id: {chat_id}")
            except Exception as e:
                print(f"❌ Ошибка user_id: {e}")
        
        if sent and state.work_files:
            try:
                media_group = [{'type': 'photo', 'media': url} for url in state.work_files[:10]]
                if media_group:
                    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
                print("✅ Фото отправлены")
            except Exception as e:
                print(f"❌ Ошибка фото: {e}")
        
        if sent:
            try:
                keyboard = [[InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f'review_{order.get("id")}')]]
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Понравилась работа? Оставьте отзыв!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                print("✅ Кнопка отзыва отправлена")
            except Exception as e:
                print(f"❌ Ошибка кнопки: {e}")
        
        state.uploading_work = False
        state.work_files = []
        state.work_message = ''
        
        if sent:
            await update.message.reply_text("✅ Работа отправлена клиенту!")
        else:
            await update.message.reply_text("✅ Работа сохранена! (уведомление не доставлено)")
    else:
        await update.message.reply_text(f"📎 Фото: {len(state.work_files)}, Текст: {'✅' if state.work_message else '❌'}")

async def handle_review_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    
    text = update.message.text or update.message.caption or ''
    photos = []
    if update.message.photo:
        photos.append(update.message.photo[-1])
    
    if text:
        state.review_text = text
    
    for photo in photos[:3]:
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        file_name = f"review_{user.id}_{datetime.now().timestamp()}.jpg"
        file_url = upload_file(bytes(file_data), file_name, 'reviews')
        if file_url:
            state.review_images.append(file_url)
    
    if state.review_text and state.review_stars > 0:
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
            state.review_stars = 0
            state.review_text = ''
            state.review_images = []
            
            await update.message.reply_text("✅ Отзыв опубликован! Спасибо!")
        else:
            await update.message.reply_text("❌ Ошибка при публикации отзыва.")
    else:
        await update.message.reply_text(
            f"📎 Фото: {len(state.review_images)}, Текст: {'✅' if state.review_text else '❌'}, Оценка: {state.review_stars}⭐\n"
            f"Отправьте текст и фото одним сообщением"
        )

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(change_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(upload_work_prompt, pattern='^upload_work_'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(admin_user_orders, pattern='^admin_user_'))
    application.add_handler(CallbackQueryHandler(admin_users, pattern='^admin_users$'))
    application.add_handler(CallbackQueryHandler(admin_all_orders, pattern='^admin_all_orders$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(my_order_detail, pattern='^my_order_'))
    application.add_handler(CallbackQueryHandler(start_review, pattern='^review_'))
    application.add_handler(CallbackQueryHandler(set_review_stars, pattern='^review_stars_'))
    application.add_handler(CallbackQueryHandler(show_reviews, pattern='^show_reviews$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    application.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
