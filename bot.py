import os
import logging
import json
import requests
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================================================
# КОНФИГ
# ================================================================
SUPABASE_URL = 'https://lcgbpwowppwwpjjlphod.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjZ2Jwd293cHB3d3BqamxwaG9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2NDAwNTMsImV4cCI6MjEwNDIxNjA1M30.95VPot7saWmlgv1IzBop3E4x-ZxSc8HepqKdDLJa7JI'

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN не задан в переменных окружения')

ADMIN_ID = int(os.environ.get('ADMIN_ID', '1492590083'))


# ================================================================
# SUPABASE HELPERS
# ================================================================
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
        result = response.json()
        return result[0] if result else None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def supabase_upsert(table, data, on_conflict='user_id'):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=representation'
        }
        response = requests.post(url, headers=headers, json=data, timeout=15)
        result = response.json()
        return result[0] if result else None
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

        print(f"📤 UPLOAD: {folder}/{file_name} — STATUS: {response.status_code}")
        if response.status_code not in [200, 201]:
            print(f"📤 RESPONSE: {response.text[:500]}")

        if response.status_code in [200, 201]:
            return f"{SUPABASE_URL}/storage/v1/object/public/{folder}/{file_name}"
        return None
    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        return None


# ================================================================
# СТАТУСЫ
# ================================================================
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


# ================================================================
# СОСТОЯНИЯ
# ================================================================
user_states = {}
admin_states = {}
debounce_tasks = {}


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


# ================================================================
# /start
# ================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"DEBUG: /start от {user.id} (@{user.username})")

    if user.username:
        supabase_update_by_username('orders', user.username, {'user_id': str(user.id)})

    # Записываем юзера в users_bot (чтобы фронт знал, что он подписан)
    supabase_upsert('users_bot', {
        'user_id': str(user.id),
        'username': user.username or '',
        'first_name': user.first_name or ''
    })

    args = context.args
    from_app = args and args[0] == 'from_app'

    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🚀 Открыть приложение", url='https://t.me/Mark1zDesign_bot/mark1zapp')],
            [InlineKeyboardButton("📋 Все заказы", callback_data='admin_all_orders')],
            [InlineKeyboardButton("🔴 Не начатые", callback_data='admin_not_started')],
            [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
            [InlineKeyboardButton("⭐ Отзывы", callback_data='show_reviews')],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data='show_help')],
        ]
        text = (
            "👑 <b>Админ-панель Mark1z Design</b>\n\n"
            "Управляйте заказами и клиентами прямо здесь.\n\n"
            "• <b>Все заказы</b> — полный список\n"
            "• <b>Не начатые</b> — те, что ждут старта\n"
            "• <b>Пользователи</b> — список клиентов\n"
            "• <b>Отзывы</b> — что пишут клиенты\n\n"
            "Заказы можно менять: «Готовится» → «Готов».\n"
            "Когда нажмёте «Готов», бот попросит прислать фото работ."
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🚀 Открыть приложение", url='https://t.me/Mark1zDesign_bot/mark1zapp')],
            [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
            [InlineKeyboardButton("⭐ Отзывы", callback_data='show_reviews')],
            [InlineKeyboardButton("📝 Мои отзывы", callback_data='my_reviews')],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data='show_help')],
        ]
        text = (
            f"👋 <b>Привет, {user.first_name}!</b>\n\n"
            "Я бот <b>Mark1z Design</b> — помогаю следить за заказами.\n\n"
            "🛠 <b>Как оформить заказ?</b>\n"
            "Открой приложение и выбери услугу или товар.\n\n"
            "📋 <b>Как следить за статусом?</b>\n"
            "Нажми «Мои заказы» — там всё видно.\n\n"
            "💬 <b>Вопросы?</b>\n"
            "Пиши дизайнеру: @mark1zell"
        )

    if from_app:
        text += "\n\n✅ Вы подписаны на уведомления от приложения!"

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ================================================================
# TELEGRAM STARS
# ================================================================
async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram требует ответить в течение 10 секунд."""
    query = update.pre_checkout_query
    print(f"💫 PreCheckout: {query.invoice_payload}, {query.total_amount}⭐")
    await query.answer(ok=True)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Клиент оплатил звёздами."""
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    amount = payment.total_amount
    charge_id = payment.telegram_payment_charge_id

    print(f"✅ Оплата звёздами: {payload}, {amount}⭐, charge_id={charge_id}")

    try:
        order_id = int(payload.replace('order_', ''))
    except Exception:
        print(f"⚠️ Не удалось распарсить order_id из payload: {payload}")
        return

    supabase_update('orders', order_id, {
        'status': 'paid_stars',
        'paid_at': datetime.now().isoformat(),
        'payment_id': charge_id,
        'stars_amount': amount   # ← количество звёзд
    })

    try:
        await update.message.reply_text(
            f"✅ Оплата прошла! Заказ #{order_id} оплачен {amount} звёздами.\n"
            f"Дизайнер скоро приступит к работе."
        )
    except Exception as e:
        print(f"❌ Не удалось отправить сообщение: {e}")


# ================================================================
# ОТЗЫВЫ (просмотр)
# ================================================================
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


# ================================================================
# ЗАКАЗЫ ПОЛЬЗОВАТЕЛЯ
# ================================================================
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
    if order.get('stars_amount'):
        text += f"⭐ Оплачено: {order.get('stars_amount')} звёзд\n"

    if order.get('work_message'):
        text += f"\n💬 Сообщение от дизайнера:\n{order.get('work_message')}\n"

    keyboard = [
        [InlineKeyboardButton("💬 Связаться с дизайнером", url='https://t.me/mark1zell')],
        [InlineKeyboardButton("🔙 Назад", callback_data='my_orders')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    work_files = order.get('work_files', [])
    if work_files:
        for url in work_files[:10]:
            try:
                await context.bot.send_photo(chat_id=query.from_user.id, photo=url)
            except Exception as e:
                print(f"Ошибка отправки фото: {e}")


# ================================================================
# АДМИН: ЗАКАЗЫ
# ================================================================
async def admin_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    orders = supabase_get('orders', {'order': 'timestamp.desc', 'limit': '30'})
    if not orders:
        await query.edit_message_text("Нет заказов.")
        return

    not_started = [o for o in orders if o.get('status') in ('paid_card', 'paid_stars', 'not_started', 'pending_payment')]
    in_progress = [o for o in orders if o.get('status') == 'in_progress']
    ready = [o for o in orders if o.get('status') == 'ready']

    keyboard = []
    if not_started:
        keyboard.append([InlineKeyboardButton(f"── 🔴 Не начатые ({len(not_started)}) ──", callback_data='noop')])
        for order in not_started[:10]:
            keyboard.append([InlineKeyboardButton(
                f"🔴 #{order.get('id')} · {order.get('service', 'Нет')} · {order.get('total', 0)}₽",
                callback_data=f"admin_order_{order.get('id')}"
            )])
    if in_progress:
        keyboard.append([InlineKeyboardButton(f"── 🟡 В работе ({len(in_progress)}) ──", callback_data='noop')])
        for order in in_progress[:10]:
            keyboard.append([InlineKeyboardButton(
                f"🟡 #{order.get('id')} · {order.get('service', 'Нет')} · {order.get('total', 0)}₽",
                callback_data=f"admin_order_{order.get('id')}"
            )])
    if ready:
        keyboard.append([InlineKeyboardButton(f"── ✅ Готовые ({len(ready)}) ──", callback_data='noop')])
        for order in ready[:5]:
            keyboard.append([InlineKeyboardButton(
                f"✅ #{order.get('id')} · {order.get('service', 'Нет')}",
                callback_data=f"admin_order_{order.get('id')}"
            )])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text(
        "📋 <b>Все заказы</b>\n\n🔴 — не начатые\n🟡 — в работе\n✅ — готовые",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_not_started(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    orders = supabase_get('orders', {
        'or': '(status.eq.not_started,status.eq.paid_card,status.eq.paid_stars)',
        'order': 'timestamp.desc'
    })
    if not orders:
        await query.edit_message_text("🔴 Нет не начатых заказов.")
        return
    keyboard = []
    for order in orders:
        keyboard.append([InlineKeyboardButton(
            f"🔴 #{order.get('id')} · {order.get('service', 'Нет')} · {order.get('total', 0)}₽",
            callback_data=f"admin_order_{order.get('id')}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    await query.edit_message_text("🔴 <b>Не начатые заказы:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


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
    status_emoji = STATUS_EMOJI.get(raw_status, '⚪')

    text = f"{status_emoji} <b>Заказ #{order.get('id', '?')}</b>\n\n"
    text += f"🛠 Услуга: <b>{order.get('service', 'Нет')}</b>\n"
    text += f"👤 Клиент: {order.get('user_name', 'нет')}"
    if order.get('user_username'):
        text += f" (@{order.get('user_username')})"
    text += f"\n💰 Сумма: {order.get('total', 0)}₽\n"
    text += f"📅 Время: {order.get('time', '—')}\n"
    text += f"📊 Статус: {status_text}\n"

    if order.get('description'):
        text += f"\n📝 <b>ТЗ клиента:</b>\n{order.get('description')}\n"

    try:
        options = json.loads(order.get('options', '[]')) if isinstance(order.get('options'), str) else (order.get('options') or [])
    except Exception:
        options = []
    if options:
        text += "\n📦 <b>Опции:</b>\n"
        for o in options:
            text += f" • {o.get('name')} ×{o.get('quantity', 1)} — {o.get('total', o.get('price', 0))}₽\n"

    keyboard = []
    if raw_status not in ('in_progress',):
        keyboard.append([InlineKeyboardButton("🟡 Готовится", callback_data=f'status_{order_id}_in_progress')])
    if raw_status != 'ready':
        keyboard.append([InlineKeyboardButton("🟢 Готов (загрузить работы)", callback_data=f'upload_work_{order_id}')])
    if raw_status != 'not_started':
        keyboard.append([InlineKeyboardButton("🔴 Вернуть в не начатые", callback_data=f'status_{order_id}_not_started')])

    if order.get('user_username'):
        keyboard.append([InlineKeyboardButton("💬 Написать клиенту", url=f"https://t.me/{order.get('user_username')}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_all_orders')])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    refs = order.get('reference_urls') or []
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except Exception:
            refs = []
    for url in refs[:5]:
        try:
            await context.bot.send_photo(chat_id=query.from_user.id, photo=url, caption="📎 Референс клиента")
        except Exception as e:
            print(f"Ошибка отправки референса: {e}")


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

    if new_status == 'in':
        new_status = 'in_progress'
        print("⚠️ ЗАЩИТА: 'in' → 'in_progress'")

    print(f"DEBUG: change_status #{order_id} → '{new_status}'")

    supabase_update('orders', order_id, {'status': new_status})
    order = supabase_get_single('orders', order_id)

    status_text = STATUS_NAMES.get(new_status, new_status)

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
    except Exception:
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


# ================================================================
# ЗАГРУЗКА РАБОТЫ АДМИНОМ (дебаунс)
# ================================================================
async def handle_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_admin_state(user.id)

    if not state.uploading_work or not state.selected_order:
        return

    message_text = update.message.text or update.message.caption or ''

    if message_text:
        state.pending_message = message_text

    if update.message.photo:
        photo = update.message.photo[-1]
        existing_ids = [p.file_id for p in state.pending_photos]
        if photo.file_id not in existing_ids:
            state.pending_photos.append(photo)
            print(f"📸 Получено фото: {len(state.pending_photos)}")

    media_group_id = update.message.media_group_id
    if media_group_id:
        debounce_key = (user.id, f"mg_{media_group_id}")
    else:
        debounce_key = (user.id, f"msg_{update.message.message_id}")

    old_task = debounce_tasks.get(debounce_key)
    if old_task and not old_task.done():
        old_task.cancel()

    async def delayed_process():
        try:
            await asyncio.sleep(3)
            await process_pending_work(context, user.id)
        except asyncio.CancelledError:
            print("DEBUG: Дебаунс продлён, ждём ещё фото")
            raise

    debounce_tasks[debounce_key] = asyncio.create_task(delayed_process())

    if len(state.pending_photos) == 1:
        await update.message.reply_text(
            "📎 Получено фото: 1\n"
            "Отправьте остальные фото и/или текст, затем подождите ~3 сек."
        )


async def process_pending_work(context, admin_id=None):
    state = get_admin_state(admin_id)

    if not state.uploading_work or not state.selected_order:
        state.processing = False
        return

    if state.processing:
        print("DEBUG: Уже обрабатывается, пропускаем")
        return

    if not state.pending_photos and not state.pending_message:
        print("DEBUG: Нет ни фото, ни текста, пропускаем")
        return

    state.processing = True

    try:
        order = state.selected_order
        photos_count = len(state.pending_photos)
        print(f"DEBUG: Обработка {photos_count} фото")

        for photo in state.pending_photos[:10]:
            try:
                file = await context.bot.get_file(photo.file_id)
                file_data = await file.download_as_bytearray()
                file_name = f"work_{order.get('id', '0')}_{datetime.now().timestamp()}_{len(state.work_files)}.jpg"
                file_url = await asyncio.to_thread(upload_file, bytes(file_data), file_name, 'works')
                if file_url:
                    state.work_files.append(file_url)
                    print(f"✅ Фото {len(state.work_files)}/{photos_count} загружено")
            except Exception as e:
                print(f"❌ Ошибка загрузки фото: {e}")

        state.work_message = state.pending_message
        state.pending_photos = []
        state.pending_message = ''

        print(f"DEBUG: work_files={len(state.work_files)}, work_message='{state.work_message[:30] if state.work_message else None}', user_id={order.get('user_id')}, username={order.get('user_username')}")       

                # Разрешаем отправку, если есть ИЛИ фото, ИЛИ текст
        if state.work_files or state.work_message:
            supabase_update('orders', order.get('id'), {
                'status': 'ready',
                'work_files': state.work_files,
                'work_message': state.work_message or ''
            })
                'work_files': state.work_files,
                'work_message': state.work_message
            })

            allow_review(order)

            sent = False
            chat_id = None

                        if order.get('user_id'):
                try:
                    chat_id = int(order['user_id'])
                    text_to_send = f"✅ Ваш заказ #{order.get('id')} готов!"
                    if state.work_message:
                        text_to_send += f"\n\nСообщение от Дизайнера:\n{state.work_message}"
                    await context.bot.send_message(chat_id=chat_id, text=text_to_send)
                    sent = True
                    print("✅ Текст отправлен по user_id")
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
                    print("✅ Текст отправлен по username")
                except Exception as e:
                    print(f"❌ username: {e}")

            if sent and state.work_files:
                for i, url in enumerate(state.work_files[:10]):
                    try:
                        await context.bot.send_photo(chat_id=chat_id, photo=url)
                        print(f"✅ Фото {i+1}/{len(state.work_files)} отправлено")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"❌ Фото {i+1}: {e}")

            if sent:
                try:
                    keyboard = [[InlineKeyboardButton(
                        "⭐ Оставить отзыв",
                        callback_data=f'review_{order.get("id")}'
                    )]]
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="⭐ Понравилась работа? Оставьте отзыв!",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    print(f"❌ Кнопка: {e}")

            state.uploading_work = False
            state.work_files = []
            state.work_message = ''

            try:
                if sent:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"✅ Работа отправлена клиенту! Фото: {photos_count}"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text="✅ Работа сохранена! (пользователь не подписан)"
                    )
            except Exception:
                pass
        else:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ Нужно: текст и фото\n"
                         f"Фото: {len(state.work_files)}, "
                         f"Текст: {'✅' if state.work_message else '❌'}"
                )
            except Exception:
                pass
    finally:
        state.processing = False


# ================================================================
# ОТЗЫВЫ (создание)
# ================================================================
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

    try:
        stars = int(query.data.split('_')[2])
    except Exception:
        await query.answer("Ошибка", show_alert=True)
        return

    user = query.from_user
    state = get_user_state(user.id)
    state.review_stars = stars
    state.review_text = ''
    state.review_images = []
    state.awaiting_review = True

    print(f"⭐⭐ Пользователь {user.id} поставил {stars} звезд")

    # Пытаемся отправить сообщение с просьбой написать текст
    sent = False
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                f"Оценка: {'⭐' * stars}\n\n"
                "📝 Теперь напишите текст отзыва — просто отправьте его следующим сообщением."
            )
        )
        sent = True
        print(f"✅ Просьба написать текст отправлена юзеру {user.id}")
    except Exception as e:
        print(f"❌ Не удалось отправить сообщение: {e}")

    # Если не удалось — правим исходное сообщение
    if not sent:
        try:
            await query.edit_message_text(
                f"Оценка: {'⭐' * stars}\n\n"
                "⚠️ Чтобы продолжить, нажмите /start в боте, затем снова выберите оценку."
            )
        except Exception:
            pass

    # Удаляем кнопки со звёздами
    try:
        await query.message.delete()
    except Exception:
        pass


async def done_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)

    if not state.awaiting_review:
        await update.message.reply_text("Нет активного отзыва.")
        return

    if not state.review_text:
        await update.message.reply_text("Сначала введите текст отзыва.")
        return

    success = await publish_review(context, user, state)
    if success:
        state.awaiting_review = False
        state.review_stars = 0
        state.review_text = ''
        state.review_images = []
        await update.message.reply_text("✅ Спасибо за отзыв! Ждём вас снова!")
    else:
        await update.message.reply_text("❌ Ошибка публикации.")


async def handle_review_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)

    if not state.awaiting_review:
        return

    text = update.message.text or update.message.caption or ''

    print(f"DEBUG: handle_review_message от {user.id}, text='{text[:50]}', awaiting={state.awaiting_review}")

    # Если пришёл текст — публикуем
    if text and not state.review_text:
        state.review_text = text
        print(f"✅ Текст отзыва получен: {text[:50]}")

        success = await publish_review(context, user, state)

        if success:
            state.awaiting_review = False
            state.review_stars = 0
            state.review_text = ''
            state.review_images = []
            await update.message.reply_text(
                "✅ <b>Спасибо за отзыв!</b>\n\n"
                "Ждём вас снова! 🎨",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Не удалось сохранить отзыв. Попробуйте позже.")
            state.awaiting_review = False
        return

    # Если фото — сохраняем
    if update.message.photo and len(state.review_images) < 3:
        photo = update.message.photo[-1]
        try:
            file = await context.bot.get_file(photo.file_id)
            file_data = await file.download_as_bytearray()
            file_name = f"review_{user.id}_{datetime.now().timestamp()}.jpg"
            file_url = upload_file(bytes(file_data), file_name, 'reviews')
            if file_url:
                state.review_images.append(file_url)
                await update.message.reply_text(f"📎 Фото добавлено ({len(state.review_images)}/3)")
        except Exception as e:
            print(f"❌ Ошибка фото: {e}")


async def publish_review(context, user, state):
    """Публикует отзыв в Supabase."""
    order_info = None
    if state.current_order_id:
        order = supabase_get_single('orders', state.current_order_id)
        if order:
            try:
                options_raw = order.get('options')
                if isinstance(options_raw, str):
                    options = json.loads(options_raw)
                elif isinstance(options_raw, list):
                    options = options_raw
                else:
                    options = []
            except Exception:
                options = []

            order_info = {
                'service': order.get('service'),
                'total': order.get('total'),
                'options': options,
                'time': order.get('time'),
                'completed_at': order.get('completed_at')
                'stars_amount': order.get('stars_amount')
            }

    review_data = {
        'author_name': user.first_name or user.username or 'Пользователь',
        'author_username': user.username or '',
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

    try:
        result = supabase_insert('reviews', review_data)
    except Exception as e:
        print(f"❌ Ошибка insert отзыва: {e}")
        return False

    if not result:
        return False

    user_identifier = user.username or user.first_name or str(user.id)
    try:
        supabase_update_by_username('user_last_review', user_identifier, {'can_review': False})
    except Exception as e:
        print(f"⚠️ Не удалось сбросить can_review: {e}")

    return True


def allow_review(order):
    if not order:
        return
    user_identifier = order.get('user_username') or order.get('user_name') or order.get('user_id')
    if not user_identifier:
        return
    try:
        options = json.loads(order.get('options', '[]'))
    except Exception:
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


# ================================================================
# ОБЩИЙ ОБРАБОТЧИК СООБЩЕНИЙ
# ================================================================
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    admin_state = get_admin_state(user.id)

    # Админ загружает работу
    if user.id == ADMIN_ID and admin_state.uploading_work:
        await handle_admin_upload(update, context)
        return

    # Юзер пишет отзыв
    if state.awaiting_review:
        await handle_review_message(update, context)
        return


# ================================================================
# HELP / BACK
# ================================================================
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        send = query.edit_message_text
    else:
        user_id = update.effective_user.id
        send = update.message.reply_text

    if user_id == ADMIN_ID:
        text = (
            "👑 <b>Как работать админу</b>\n\n"
            "1. <b>Все заказы</b> — открыть список\n"
            "2. Выбрать заказ → «Готовится» или «Готов»\n"
            "3. При «Готов» бот попросит фото (до 10) + текст\n"
            "4. Отправить фото альбомом и текст одним сообщением\n"
            "5. Клиент получит уведомление\n\n"
            "❓ Если фото не отправляются — попробуй ещё раз, "
            "иногда Telegram теряет часть альбома."
        )
    else:
        text = (
            "ℹ️ <b>Помощь</b>\n\n"
            "📋 <b>Мои заказы</b> — все ваши заказы\n"
            "⭐ <b>Отзывы</b> — что пишут другие\n"
            "📝 <b>Мои отзывы</b> — ваши отзывы\n\n"
            "💡 <b>Совет:</b> когда дизайнер закончит работу, "
            "вам придёт уведомление и кнопка «Оставить отзыв».\n\n"
            "💬 <b>Связаться с дизайнером:</b> @mark1zell"
        )

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')]]
    await send(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


# ================================================================
# ЗАПУСК
# ================================================================
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', show_help))
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
    application.add_handler(CallbackQueryHandler(show_help, pattern='^show_help$'))
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern='^noop$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))

    application.add_handler(MessageHandler(filters.ALL, handle_all_messages))

    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
