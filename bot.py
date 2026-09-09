import os
import logging
import json
import requests
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

# Функции для работы с Supabase
def supabase_get(table, params=None):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return []

def supabase_get_single(table, id):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        return None
    except Exception as e:
        print(f"EXCEPTION: {e}")
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
        print(f"EXCEPTION: {e}")
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
        print(f"EXCEPTION: {e}")
        return None

# Функция загрузки файла в Supabase Storage
def upload_file_to_supabase(file_data, file_name, folder):
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/public/{folder}/{file_name}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/octet-stream'
        }
        response = requests.post(url, headers=headers, data=file_data, timeout=30)
        if response.status_code in [200, 201]:
            return url
        return None
    except Exception as e:
        print(f"UPLOAD EXCEPTION: {e}")
        return None

# Функция создания платежа в ЮKassa
def create_yookassa_payment(order_id, amount, description):
    try:
        url = 'https://api.yookassa.ru/v3/payments'
        auth_string = f"{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}"
        import base64
        auth_bytes = auth_string.encode('utf-8')
        auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        headers = {
            'Content-Type': 'application/json',
            'Idempotence-Key': f"bot_{order_id}_{datetime.now().timestamp()}",
            'Authorization': f'Basic {auth_base64}'
        }
        
        data = {
            'amount': {
                'value': str(amount),
                'currency': 'RUB'
            },
            'confirmation': {
                'type': 'redirect',
                'return_url': 'https://t.me/mark1zell'
            },
            'description': description,
            'capture': True,
            'metadata': {
                'order_id': str(order_id)
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()
        print(f"YOOKASSA ERROR: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"YOOKASSA EXCEPTION: {e}")
        return None

# Временное хранилище
user_states = {}

class UserState:
    def __init__(self):
        self.current_service = None
        self.selected_options = {}
        self.description = ''
        self.references = []
        self.current_order_id = None

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
    
    services = supabase_get('services', {'select': 'id,emoji,name', 'order': 'id.asc'})
    
    if not services:
        await query.edit_message_text("❌ Услуги не загружены.")
        return
    
    keyboard = []
    for service in services:
        emoji = service.get('emoji', '📦')
        name = service.get('name', 'Без названия')
        sid = service['id']
        keyboard.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"svc_{sid}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠️ Выберите услугу:", reply_markup=reply_markup)

async def show_service_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    if len(parts) < 2:
        return
    
    service_id = int(parts[1])
    service = supabase_get_single('services', service_id)
    
    if not service:
        await query.edit_message_text(f"❌ Услуга не найдена")
        return
    
    options = supabase_get('service_options', {'service_id': f'eq.{service_id}', 'order': 'id.asc'})
    
    state = get_user_state(query.from_user.id)
    state.current_service = service
    state.selected_options = {}
    state.references = []
    
    emoji = service.get('emoji', '📦')
    name = service.get('name', 'Без названия')
    description = service.get('description', '')
    
    if not options:
        await query.edit_message_text(f"{emoji} {name}\n\n{description}\n\n❌ Нет опций. Свяжитесь: @mark1zell")
        return
    
    keyboard = []
    for option in options:
        opt_name = option.get('name', 'Без названия')
        opt_price = option.get('price', 0)
        max_qty = option.get('max_quantity', 1) or 1
        
        if max_qty > 1:
            keyboard.append([InlineKeyboardButton(
                f"{opt_name} - {opt_price}₽ (кол-во)", 
                callback_data=f"qty_{option['id']}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{opt_name} - {opt_price}₽", 
                callback_data=f"toggle_{option['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"{emoji} {name}\n"
    if description:
        text += f"\n{description}\n"
    text += "\nВыберите опции:"
    
    await query.edit_message_text(text, reply_markup=reply_markup)

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
        state.selected_options[option_id] = {
            'name': opt_name,
            'price': opt_price,
            'quantity': 1,
            'total': opt_price
        }
        await query.answer(f"✅ Добавлено: {opt_name} ({opt_price}₽)")
    
    await update_service_options_message(update, context, state)

async def update_service_options_message(update: Update, context: ContextTypes.DEFAULT_TYPE, state):
    query = update.callback_query
    service = state.current_service
    
    if not service:
        return
    
    options = supabase_get('service_options', {'service_id': f'eq.{service["id"]}', 'order': 'id.asc'})
    
    emoji = service.get('emoji', '📦')
    name = service.get('name', 'Без названия')
    description = service.get('description', '')
    
    keyboard = []
    for option in options:
        opt_name = option.get('name', 'Без названия')
        opt_price = option.get('price', 0)
        max_qty = option.get('max_quantity', 1) or 1
        
        is_selected = option['id'] in state.selected_options
        prefix = "✅ " if is_selected else ""
        
        if max_qty > 1:
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{opt_name} - {opt_price}₽ (кол-во)", 
                callback_data=f"qty_{option['id']}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{opt_name} - {opt_price}₽", 
                callback_data=f"toggle_{option['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data='finish_options')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='services')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"{emoji} {name}\n"
    if description:
        text += f"\n{description}\n"
    text += "\nВыберите опции:"
    
    if state.selected_options:
        text += "\n\n✅ Выбранные опции:\n"
        total = 0
        for opt in state.selected_options.values():
            text += f"• {opt['name']} ×{opt['quantity']} = {opt['total']}₽\n"
            total += opt['total']
        text += f"\n💰 Итого: {total}₽"
    
    await query.edit_message_text(text, reply_markup=reply_markup)

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
        await query.answer("❌ Опция не найдена", show_alert=True)
        return
    
    max_qty = option.get('max_quantity', 10) or 10
    min_qty = option.get('min_quantity', 1) or 1
    
    keyboard = []
    for i in range(min_qty, min(max_qty, 10) + 1):
        keyboard.append([InlineKeyboardButton(f"{i} шт.", callback_data=f"setqty_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"svc_{option['service_id']}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"Количество для: {option['name']}", reply_markup=reply_markup)

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
        price = option.get('price', 0)
        discount_min = option.get('discount_min_quantity')
        discount_price = option.get('discount_price')
        
        final_price = price
        if discount_min and qty >= discount_min and discount_price:
            final_price = discount_price
        
        state.selected_options[option_id] = {
            'name': option.get('name', 'Опция'),
            'price': final_price,
            'quantity': qty,
            'total': final_price * qty
        }
        
        await query.answer(f"✅ {option['name']} ×{qty}")
    
    await update_service_options_message(update, context, state)

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
        f"📝 Отправьте описание ТЗ (что нужно сделать, стиль, цвета и т.д.)\n"
        f"📎 Также можете прикрепить до 3 референсов (фото/изображения)"
    )
    
    context.user_data['awaiting_description'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_user_state(user.id)
    
    # Обработка текста ТЗ
    if context.user_data.get('awaiting_description'):
        state.description = update.message.text
        context.user_data['awaiting_description'] = False
        context.user_data['awaiting_references'] = True
        
        await update.message.reply_text(
            "📎 Отправьте до 3 референсов (фото/изображения) или нажмите /done если референсов нет"
        )
        return
    
    # Обработка референсов
    if context.user_data.get('awaiting_references'):
        if update.message.photo or update.message.document:
            if len(state.references) < 3:
                # Получаем файл
                file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
                file = await context.bot.get_file(file_id)
                file_data = await file.download_as_bytearray()
                
                # Загружаем в Supabase
                file_name = f"ref_{user.id}_{datetime.now().timestamp()}.jpg"
                file_url = upload_file_to_supabase(bytes(file_data), file_name, 'references')
                
                if file_url:
                    state.references.append(file_url)
                    await update.message.reply_text(f"✅ Референс {len(state.references)}/3 добавлен!")
                else:
                    await update.message.reply_text("❌ Ошибка загрузки референса")
            else:
                await update.message.reply_text("❌ Максимум 3 референса!")
        else:
            # Если текст - игнорируем или обрабатываем
            pass
        
        if len(state.references) >= 3:
            await create_order_from_bot(update, context, state)
        return

async def create_order_from_bot(update: Update, context: ContextTypes.DEFAULT_TYPE, state):
    user = update.effective_user
    
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
        'reference_urls': state.references,
        'status': 'pending_payment',
        'payment_id': None,
        'paid_at': None
    }
    
    result = supabase_insert('orders', order_data)
    
    if result:
        order_id = result['id']
        state.current_order_id = order_id
        
        # Создаем платеж в ЮKassa
        payment = create_yookassa_payment(order_id, total, f"Оплата заказа #{order_id}")
        
        if payment and payment.get('confirmation', {}).get('confirmation_url'):
            payment_url = payment['confirmation']['confirmation_url']
            payment_id = payment.get('id')
            
            # Сохраняем payment_id
            supabase_update('orders', order_id, {'payment_id': payment_id})
            
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить", url=payment_url)],
                [InlineKeyboardButton("✅ Я оплатил", callback_data=f'check_payment_{order_id}')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Заказ #{order_id} создан!\n\n"
                f"💰 Сумма: {total}₽\n\n"
                f"Для оплаты нажмите кнопку ниже:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"✅ Заказ #{order_id} создан!\n\n"
                f"💰 Сумма: {total}₽\n\n"
                f"Ошибка создания платежа. Свяжитесь с @mark1zell"
            )
    else:
        await update.message.reply_text("❌ Ошибка при создании заказа.")

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    order_id = int(parts[2])
    
    order = supabase_get_single('orders', order_id)
    
    if not order or not order.get('payment_id'):
        await query.edit_message_text("❌ Платеж не найден.")
        return
    
    # Проверяем статус платежа в ЮKassa
    import base64
    auth_string = f"{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}"
    auth_bytes = auth_string.encode('utf-8')
    auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
    
    url = f"https://api.yookassa.ru/v3/payments/{order['payment_id']}"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth_base64}'
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code == 200:
        payment_data = response.json()
        
        if payment_data.get('status') == 'succeeded':
            # Обновляем статус заказа
            supabase_update('orders', order_id, {
                'status': 'paid_card',
                'paid_at': datetime.now().isoformat()
            })
            
            await query.edit_message_text(
                f"✅ Оплата прошла успешно!\n\n"
                f"Заказ #{order_id}\n"
                f"Статус: Оплачен\n\n"
                f"Дизайнер скоро приступит к работе."
            )
        elif payment_data.get('status') == 'pending':
            await query.edit_message_text("⏳ Платеж обрабатывается. Попробуйте через минуту.")
        else:
            await query.edit_message_text(f"❌ Статус платежа: {payment_data.get('status')}")
    else:
        await query.edit_message_text("❌ Ошибка проверки платежа.")

async def done_references(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = get_user_state(update.effective_user.id)
    
    if context.user_data.get('awaiting_references'):
        context.user_data['awaiting_references'] = False
        await create_order_from_bot(update, context, state)

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
        await query.edit_message_text("📋 У вас пока нет заказов.")
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
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('done', done_references))
    application.add_handler(CallbackQueryHandler(set_qty, pattern='^setqty_'))
    application.add_handler(CallbackQueryHandler(show_qty, pattern='^qty_'))
    application.add_handler(CallbackQueryHandler(toggle_option, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(check_payment, pattern='^check_payment_'))
    application.add_handler(CallbackQueryHandler(change_status, pattern='^status_'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_'))
    application.add_handler(CallbackQueryHandler(show_service_options, pattern='^svc_'))
    application.add_handler(CallbackQueryHandler(finish_options, pattern='^finish_options$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_orders, pattern='^admin_'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    application.add_handler(CallbackQueryHandler(show_services, pattern='^services$'))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.IMAGE, handle_message))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
