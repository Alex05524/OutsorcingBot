import asyncio
import logging
import os
import json
import pyotp
import html
from aiogram import Bot, Dispatcher, types, F, Router, BaseMiddleware
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, TelegramObject, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from dotenv import load_dotenv, set_key
from datetime import datetime

from states import OrderForm, StatusForm
from keyboards import remove_admin_keyboard, start_button_keyboard, main_menu_keyboard, edit_request_keyboard, services_keyboard, services_keyboard_1, admin_panel_keyboard
from utils import split_message, load_prices, format_prices, escape_md, process_pdf, convert_pdf_to_images, notify_user, cancel_order, save_feedback_to_json, notify_admins, get_new_orders_list, save_order_to_json, get_order_status, load_orders, save_orders, update_order_status, is_valid_request_id, update_request, get_order_data_by_id
from validators import sanitize_input, is_valid_phone_number, is_valid_address

# Загрузка переменных окружения
load_dotenv()

# Генерация секретного ключа для 2FA
secret = pyotp.random_base32()

# Получение списка admin_ids из переменной окружения
admin_ids_str = os.getenv("ADMIN_ID")
if admin_ids_str:
    admin_ids = list(map(int, admin_ids_str.strip("'").split(',')))
else:
    admin_ids = []

# Получение токена бота и ID админа
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_ID")
if not BOT_TOKEN or not ADMIN_IDS:
    raise ValueError("Токен бота или ID админа не найден. Убедитесь, что переменные окружения BOT_TOKEN и ADMIN_ID заданы.")

# Преобразование строки с ID админов в список целых чисел
if ADMIN_IDS:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS.split(',')]
else:
    ADMIN_IDS = []

# Создаём экземпляр Bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Определение состояний
class OrderForm(StatesGroup):
    full_name = State()
    address = State()
    service = State()
    phone_number = State()
    reason = State()
    status = State()
    request_id = State()
    edit_field = State()
    edit_value = State()

class AdminState(StatesGroup):
    request_id = State()
    status = State()
    new_admin_id = State()

class StatusRequestForm(StatesGroup):
    request_id = State()

class CancelOrderForm(StatesGroup):
    request_id = State()

class FeedbackForm(StatesGroup):
    request_id = State()
    feedback = State()

# Создаём экземпляр Router для маршрутизации обновлений
router = Router()

# Мидлварь для логирования входящих событий
class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        return await handler(event, data)

# Регистрация мидлвари
router.message.middleware(LoggingMiddleware())

# Обработка команды /start
@router.message(Command("start"))
async def start_command(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            "👋 Добро пожаловать, администратор! Нажмите кнопку ниже, чтобы начать.",
            reply_markup=start_button_keyboard(admin=True),
        )
    else:
        await message.answer(
            "👋 Добро пожаловать! Нажмите кнопку ниже, чтобы начать.",
            reply_markup=start_button_keyboard(admin=False),
        )

# Обработка нажатия "Старт"
@router.callback_query(lambda c: c.data == "start_work")
async def start_work(callback_query: CallbackQuery):
    if callback_query.from_user.id in admin_ids:
        await callback_query.message.edit_text("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard(admin=True))
    else:
        await callback_query.message.edit_text("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard(admin=False))

# Обработка команды /2fa для администраторов
@router.message(Command("2fa"))
async def enable_2fa(message: Message):
    if message.from_user.id in ADMIN_IDS:
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=message.from_user.username, issuer_name="OutsourcingBot")
        await message.answer(
            f"🔑 Ваш секретный ключ для 2FA: `{secret}`\n"
            "💾 Сохраните его в надежном месте.\n"
            f"📷 QR-код для настройки: [нажмите здесь]({uri})",
            parse_mode="MarkdownV2"
        )
    else:
        await message.answer("🚫 У вас нет прав для выполнения этого действия.")

# Обработка команды /verify для проверки 2FA
@router.message(Command("verify"))
async def verify_2fa(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("🔍 Пожалуйста, введите ваш код 2FA:")
    else:
        await message.answer("🚫 У вас нет прав для выполнения этого действия.")

# Обработка нажатия на кнопку "Общий список заявок"
@router.callback_query(F.data == 'show_all_orders')
async def show_all_orders(callback_query: CallbackQuery):
    orders = load_orders()
    if not orders:
        await bot.send_message(callback_query.from_user.id, "📭 Список заявок пуст.")
        return

    orders_text = "📋 Общий список заявок:\n\n"
    for order in orders:
        orders_text += (
            f"🆔 ID: {escape_md(str(order.get('id', 'N/A')))}\n"
            f"👤 Имя: {escape_md(order.get('full_name', 'N/A'))}\n"
            f"📞 Телефон: {escape_md(order.get('phone_number', 'N/A'))}\n"
            f"🏠 Адрес: {escape_md(order.get('address', 'N/A'))}\n"
            f"💼 Услуга: {escape_md(order.get('service', 'N/A'))}\n"
            f"📋 Статус: {escape_md(order.get('status', 'N/A'))}\n"
            f"❓ Причина обращения: {escape_md(order.get('reason', 'N/A'))}\n"
            f"📅 Дата создания: {escape_md(order.get('created_at', 'N/A'))}\n"
            f"{escape_md('-' * 20)}\n"
        )

    await bot.send_message(callback_query.from_user.id, orders_text, parse_mode="MarkdownV2")

# Обработка кнопки "Услуги"
@router.callback_query(F.data == "services")
async def show_services(callback_query: CallbackQuery):
    await callback_query.message.edit_text("🔧 Выберите услугу:", reply_markup=services_keyboard())

# Обработка кнопки "Компьютерная помощь"
@router.callback_query(F.data == "service_1")
async def computer_help(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "Мы предлагаем:\n"
        "— Полный аутсорсинг для ИП, ТОО и любых других форм бизнеса.\n"
        "— Установка любых программ, необходимых для работы.\n"
        "— Удалённая настройка через TeamViewer, AnyDesk, Ammyy Admin — быстро и удобно.\n\n"
        "Комплексные услуги для вашей техники:\n"
        "— Установка Windows (10, 11, Server) и Office (2007–2021+).\n"
        "— Настройка драйверов для стабильной работы.\n"
        "— Профессиональная чистка ноутбуков и ПК.\n"
        "— Оптимизация систем для максимальной производительности.",
        reply_markup=services_keyboard()
    )

# Обработка кнопки "Предложения по монтажным работам"
@router.callback_query(F.data == "service_2")
async def installation_proposals(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "Устали от медленного интернета, обрывов соединения и хаоса с проводами?\n"
        "Мы предлагаем профессиональный монтаж локальных сетей \"под ключ\" для вашего дома, офиса или предприятия!\n\n"
        "Почему выбирают нас?\n"
        "Высокая скорость и стабильность: Мы проектируем и настраиваем сети, которые работают без перебоев.\n"
        "Индивидуальный подход: Решения, идеально подходящие под ваши задачи и бюджет.\n"
        "Современные технологии: Используем только проверенные материалы и оборудование.\n"
        "Квалифицированные специалисты: У нас работают опытные инженеры с более чем 5-летним опытом.\n"
        "Гарантия качества: Даем гарантию на все выполненные работы и материалы.\n\n"
        "Мы предлагаем:\n"
        "Проектирование сети: Разработка схем подключения с учётом ваших потребностей.\n"
        "Монтаж и настройка: Установка кабельной системы, Wi-Fi точек, маршрутизаторов и другого оборудования.\n"
        "Техническая поддержка: Обслуживание сетей и оперативное решение любых вопросов.",
        reply_markup=services_keyboard()
    )

# Обработка кнопки "Заказ на выезд"
@router.callback_query(F.data == "service_3")
async def order_visit(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Пожалуйста, введите ваше полное имя для оформления заявки:")
    await state.set_state(OrderForm.full_name)

# Обработка кнопки "Редактировать заявку"
@router.callback_query(F.data == "edit_request")
async def edit_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🆔 Введите номер Вашей ID Заявки:")
    await state.set_state(OrderForm.request_id)

# Обработка ввода ID заявки для редактирования
@router.message(StateFilter(OrderForm.request_id))
async def process_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    if not is_valid_request_id(request_id):
        await message.answer("🚫 Неверный ID заявки. Пожалуйста, введите корректный номер ID.")
        return
    
    order_data = get_order_data_by_id(request_id)
    if not order_data:
        await message.answer("🚫 Заявка с таким ID не найдена. Пожалуйста, введите корректный номер ID.")
        return
    
    await state.update_data(request_id=request_id, order_data=order_data)
    await message.answer("Выберите, что вы хотите изменить:", reply_markup=edit_request_keyboard())
    await state.set_state(OrderForm.edit_field)

# Обработка кнопки "Редактировать имя"
@router.callback_query(F.data == "edit_full_name")
async def edit_name(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("👤 Введите новое имя:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="full_name")

# Обработка кнопки "Редактировать адрес"
@router.callback_query(F.data == "edit_address")
async def edit_address(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🏠 Введите новый адрес:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="address")

# Обработка кнопки "Редактировать телефон"
@router.callback_query(F.data == "edit_phone_number")
async def edit_phone(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("📞 Введите новый номер телефона:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="phone_number")

# Обработка кнопки "Редактировать причину"
@router.callback_query(F.data == "edit_reason")
async def edit_reason(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("❓ Введите новую причину обращения:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="reason")

# Обработка ввода нового значения для редактируемого поля
@router.message(StateFilter(OrderForm.edit_value))
async def process_edit_value(message: Message, state: FSMContext):
    value = message.text.strip()
    data = await state.get_data()
    request_id = data['request_id']
    field = data['edit_field']
    orders = load_orders()
    order_data = next((order for order in orders if order['id'] == request_id), None)
    if order_data is None:
        await message.answer("🚫 Заявка с указанным ID не найдена.")
        return
    if field in ["full_name", "address", "phone_number", "reason"]:
        order_data[field] = value
        save_orders(orders)
        await message.answer(f"💾 Поле {field} успешно обновлено.")
    else:
        await message.answer("🚫 Неверное поле для редактирования.")
    await message.answer("💬 Выберите поле для редактирования или вернитесь в меню:", reply_markup=edit_request_keyboard())
    await state.set_state(OrderForm.edit_field)

# Обработка кнопки "Оформить заявку"
@router.callback_query(F.data == "apply_request")
async def create_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("👤 Пожалуйста, введите ваше полное имя:")
    await state.set_state(OrderForm.full_name)

# Обработка ввода полного имени
@router.message(StateFilter(OrderForm.full_name))
async def process_full_name(message: Message, state: FSMContext):
    full_name = sanitize_input(message.text.strip())
    await state.update_data(full_name=full_name)
    await message.answer("🏠 Введите Ваш адрес:")
    await state.set_state(OrderForm.address)

# Обработка ввода адреса
@router.message(StateFilter(OrderForm.address))
async def process_address(message: Message, state: FSMContext):
    address = sanitize_input(message.text.strip())
    if not is_valid_address(address):
        await message.answer("🚫 Неверный адрес. Пожалуйста, введите корректный адрес.")
        return
    await state.update_data(address=address)
    await message.answer("📋 Выберите услугу:", reply_markup=services_keyboard_1())
    await state.set_state(OrderForm.service)

# Обработка нажатия на кнопку "Компьютерная помощь"
@router.callback_query(F.data == 'computer_help')
async def computer_help(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(service="🔧 Компьютерная помощь")
    await callback_query.message.answer("📞 Введите номер телефона:")
    await state.set_state(OrderForm.phone_number)

# Обработка нажатия на кнопку "Монтажные работы"
@router.callback_query(F.data == 'installation_work')
async def installation_work(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(service="🔧 Монтажные работы")
    await callback_query.message.answer("📞 Введите номер телефона:")
    await state.set_state(OrderForm.phone_number)

# Обработка ввода номера телефона
@router.message(StateFilter(OrderForm.phone_number))
async def process_phone_number(message: Message, state: FSMContext):
    phone_number = sanitize_input(message.text.strip())
    if not is_valid_phone_number(phone_number):
        await message.answer("🚫 Неверный формат номера телефона. Пожалуйста, введите корректный номер.")
        return
    await state.update_data(phone_number=phone_number)
    await message.answer("❓ Введите причину обращения:")
    await state.set_state(OrderForm.reason)

# Обработка ввода причины обращения
@router.message(StateFilter(OrderForm.reason))
async def process_reason(message: Message, state: FSMContext):
    reason = sanitize_input(message.text.strip())
    await state.update_data(reason=reason)
    await state.update_data(status="Ожидает обработки", user_id=message.from_user.id)
    order_data = await state.get_data()
    order_id = await save_order_to_json(bot, order_data)
    order_data['id'] = order_id
    await message.answer(
        f"📋 Заявка #{order_id} успешно оформлена!\n"
        f"👤 Имя: {order_data['full_name']}\n"
        f"🏠 Адрес: {order_data['address']}\n"
        f"💼 Услуга: {order_data['service']}\n"
        f"📞 Телефон: {order_data['phone_number']}\n"
        f"❓ Причина обращения: {order_data['reason']}\n"
        f"📋 Статус: {order_data['status']}\n"
        f"📅 Дата создания: {order_data['created_at']}\n",
        reply_markup=main_menu_keyboard()
    )
    await state.clear()

# Обработка кнопки "Назад" в меню услуг
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Обработка кнопки "Панель администратора"
@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🆔 Введите номер Вашей ID Заявки для изменения статуса:")
    await state.set_state(AdminState.request_id)

# Обработка кнопки "Назад" в панели администратора
@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback_query: CallbackQuery):
    is_admin = callback_query.from_user.id in ADMIN_IDS
    await callback_query.message.edit_text("📋 Выберите действие из меню:", reply_markup=start_button_keyboard(admin=is_admin))

# Обработка ввода ID заявки для изменения статуса
@router.message(StateFilter(AdminState.request_id))
async def process_admin_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    if not is_valid_request_id(request_id):
        await message.answer("🚫 Неверный ID заявки. Пожалуйста, введите корректный номер ID.")
        return
    await state.update_data(request_id=request_id)
    await message.answer("📋 Выберите новый статус заявки:", reply_markup=admin_panel_keyboard())
    await state.set_state(AdminState.status)

# Обработка кнопки "Обработано"
@router.callback_query(F.data == "status_processed")
async def status_processed(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    request_id = data.get('request_id')
    orders = load_orders()
    for order in orders:
        if order['id'] == request_id:
            order['status'] = "Обработано"
            save_orders(orders)
            if 'history' not in order:
                order['history'] = []
            order['history'].append({
                'timestamp': datetime.now().isoformat(),
                'status': "✅ Обработано",
                'admin_id': callback_query.from_user.id
            })
            save_orders(orders)      
            await callback_query.message.edit_text(
                f"🆔 Статус заявки #{request_id} изменен на '✅ Обработано'.\n"
                f"👤 Имя: {order['full_name']}\n"
                f"🏠 Адрес: {order['address']}\n"
                f"📞 Телефон: {order['phone_number']}\n"
                f"❓ Причина обращения: {order['reason']}\n"
                f"📋 Статус: {order['status']}\n"
                f"👤 Обработал администратор: {callback_query.from_user.first_name} {callback_query.from_user.last_name}"
            )
            await callback_query.message.answer("📋 Выберите действие из меню:", reply_markup=start_button_keyboard(admin=True))
            
            # Уведомление пользователя и предложение оставить отзыв
            feedback_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗂️ Оставить отзыв", callback_data=f"leave_feedback:{request_id}")]
            ])
            await bot.send_message(order["user_id"], "✅ Ваша заявка завершена. Пожалуйста, оставьте отзыв.", reply_markup=feedback_button)
            break
    else:
        await callback_query.message.edit_text(f"🚫 Не удалось изменить статус заявки #{request_id}.")
    await state.clear()

# Обработка кнопки "В работе"
@router.callback_query(F.data == "status_in_progress")
async def status_in_progress(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    request_id = data.get('request_id')
    orders = load_orders()
    for order in orders:
        if order['id'] == request_id:
            order['status'] = "🔧 В работе"
            if 'history' not in order:
                order['history'] = []
                order['history'].append({
                    'timestamp': datetime.now().isoformat(),
                   'status': "🔧 В работе",
                    'admin_id': callback_query.from_user.id
                })
            save_orders(orders)
            await callback_query.message.edit_text(
                f"🆔 Статус заявки #{request_id} изменен на '🔧 В работе'.\n"
                f"👤 Имя: {order['full_name']}\n"
                f"🏠 Адрес: {order['address']}\n"
                f"📞 Телефон: {order['phone_number']}\n"
                f"❓ Причина обращения: {order['reason']}\n"
                f"📋 Статус: {order['status']}\n"
                f"👤 Обработал администратор: {callback_query.from_user.first_name} {callback_query.from_user.last_name}"
            )
            await callback_query.message.answer("📋 Выберите действие из меню:", reply_markup=start_button_keyboard(admin=True))
            break
    else:
        await callback_query.message.edit_text(f"🚫 Не удалось изменить статус заявки #{request_id}.")
    await state.clear()

# Обработка нажатия на кнопку "Список новых заявок"
@router.callback_query(F.data == "list_new_orders")
async def list_new_orders(callback_query: CallbackQuery):
    try:
        with open("orders.json", "r", encoding="utf-8") as file:
            orders = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        orders = []

    if not orders:
        await callback_query.message.answer("📭 Нет новых заявок.")
        return

    response_text = "📋 Список новых заявок:\n\n"
    for order in orders:
        response_text += (
            f"🆔 ID заявки: {order['id']}\n"
            f"👤 ФИО: {order['full_name']}\n"
            f"🏠 Адрес: {order['address']}\n"
            f"📞 Телефон: {order['phone_number']}\n"
            f"❓ Причина: {order['reason']}\n\n"
        )

    await callback_query.message.answer(response_text)
    await callback_query.answer()

# Обработка кнопки "Статус заявки"
@router.callback_query(F.data == "status_request")
async def status_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🔍 Введите номер Вашей ID Заявки для просмотра статуса:")
    await state.set_state(StatusRequestForm.request_id)

# Обработка ввода ID заявки для просмотра статуса
@router.message(StateFilter(StatusRequestForm.request_id))
async def process_status_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    orders = load_orders()
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
    for order in orders:
        if order['id'] == request_id:
            if is_admin or order.get('user_id') == user_id:
                await message.answer(
                    f"Статус заявки #{request_id}:\n"
                    f"Имя: {order['full_name']}\n"
                    f"Адрес: {order['address']}\n"
                    f"Телефон: {order['phone_number']}\n"
                    f"Причина обращения: {order['reason']}\n"
                    f"Статус: {order['status']}"
                )
            else:
                await message.answer("🚫 Отказано в доступе к этой заявке.")
            break
    else:
        await message.answer(f"🆔 Заявка с ID #{request_id} не найдена.")
    
    # Возврат в главное меню после показа статуса заявки
    await message.answer("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Обработка кнопки "Добавить администратора"
@router.callback_query(F.data == "add_admin")
async def add_admin(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🆔 Введите ID нового администратора:")
    await state.set_state(AdminState.new_admin_id)

# Обработка ввода ID нового администратора
@router.message(StateFilter(AdminState.new_admin_id))
async def process_new_admin_id(message: Message, state: FSMContext):
    new_admin_id = message.text.strip()
    try:
        new_admin_id = int(new_admin_id)
    except ValueError:
        await message.answer("🚫 Неверный ID. Пожалуйста, введите корректный номер ID.")
        return

    if new_admin_id in ADMIN_IDS: # type: ignore
        await message.answer("✅ Этот ID уже является администратором.")
        return

    ADMIN_IDS.append(new_admin_id) # type: ignore
    new_admin_ids_str = ','.join(map(str, ADMIN_IDS)) # type: ignore
    set_key('.env', 'ADMIN_ID', new_admin_ids_str)

    await message.answer(f"✅ Администратор с ID {new_admin_id} успешно добавлен.")
    
    # Возврат в панель администратора после добавления администратора
    await message.answer("📋 Выберите действие из меню:", reply_markup=start_button_keyboard(admin=True))
    await state.clear()

# Обработка кнопки "Удалить администратора"
@router.callback_query(F.data == "remove_admin")
async def remove_admin(callback_query: CallbackQuery):
    await callback_query.message.edit_text("💬 Выберите администратора для удаления:", reply_markup=remove_admin_keyboard(ADMIN_IDS))

# Обработка подтверждения удаления администратора
@router.callback_query(F.data.startswith("confirm_remove_admin_"))
async def confirm_remove_admin(callback_query: CallbackQuery):
    admin_id = int(callback_query.data.split("_")[-1])
    if admin_id in ADMIN_IDS: # type: ignore
        ADMIN_IDS.remove(admin_id) # type: ignore
        new_admin_ids_str = ','.join(map(str, ADMIN_IDS)) # type: ignore
        set_key('.env', 'ADMIN_ID', new_admin_ids_str)
        await callback_query.message.edit_text(f"✅ Администратор с ID {admin_id} успешно удален.")
    else:
        await callback_query.message.edit_text(f"🚫 Администратор с ID {admin_id} не найден.")
    
    # Возврат в панель администратора после удаления администратора
    await callback_query.message.answer("📋 Выберите действие из меню:", reply_markup=start_button_keyboard(admin=True))

# Аналитика заявок (только для администраторов)
@router.callback_query(lambda c: c.data == "show_stats")
async def show_stats(callback_query: CallbackQuery):
    if callback_query.from_user.id not in admin_ids:
        await callback_query.answer("🚫 У вас нет прав для выполнения этого действия.", show_alert=True)
        return

    orders = load_orders()
    total_orders = len(orders)
    processed_orders = len([order for order in orders if order['status'] == "✅ Обработано"])
    in_progress_orders = len([order for order in orders if order['status'] == "🔧 В работе"])
    pending_orders = len([order for order in orders if order['status'] == "🔄 Ожидает обработки"])
    
    avg_processing_time = sum(
        [
            (datetime.fromisoformat(order['history'][-1]['timestamp']) - datetime.fromisoformat(order['history'][0]['timestamp'])).total_seconds()
            for order in orders
            if order['status'] == "✅ Обработано" and 'history' in order and len(order['history']) > 1
        ]
    ) / processed_orders if processed_orders > 0 else 0
    
    stats_text = f"Всего заявок: {total_orders}\n"
    stats_text += f"✅ Обработано: {processed_orders}\n"
    stats_text += f"🔧 В работе: {in_progress_orders}\n"
    stats_text += f"🔄 Ожидает обработки: {pending_orders}\n"
    stats_text += f"📈 Среднее время обработки: {avg_processing_time / 60:.2f} минут\n"
    
    await callback_query.message.answer(stats_text)

# Обработка кнопки "FAQ"
@router.callback_query(F.data == "show_faq")
async def show_faq(callback_query: CallbackQuery):
    faq_text = "❓ Часто задаваемые вопросы:\n\n"
    faq_text += "1. 📜 Как оформить заявку?\n"
    faq_text += "📝 Ответ: Нажмите на кнопку 'Оформить заявку' и следуйте инструкциям.\n\n"
    faq_text += "2. 📋 Как узнать статус заявки?\n"
    faq_text += "📝 Ответ: Нажмите на кнопку 'Статус заявки' и введите номер Вашей заявки.\n\n"
    faq_text += "3. 🛠️ Как связаться с техподдержкой?\n"
    faq_text += "📝 Ответ: Напишите нам на почту: alex05524@gmail.com или WhatsApp: +7(707)317-28-55.\n\n"
    faq_text += "📝 *Ответ:* Нажмите на кнопку '💲 Стоимость услуг' для получения информации о ценах.\n\n"
    faq_text += "5. 🚫 *Как отменить заявку?*\n"
    faq_text += "📝 *Ответ:* Нажмите на кнопку '🚫 Отменить заявку' и следуйте инструкциям.\n\n"
    faq_text += "6. 🌟 *Как оставить отзыв?*\n"
    faq_text += "📝 *Ответ:* Нажмите на кнопку '📝 Оставить отзыв' после завершения заявки.\n\n"
    faq_text += "7. 🔧 *Какие услуги вы предоставляете?*\n"
    faq_text += "📝 *Ответ:* Нажмите на кнопку '📋 Услуги' для просмотра списка доступных услуг.\n\n"    
    await callback_query.message.edit_text(faq_text)
    # Переход в главное меню после отображения FAQ
    await callback_query.message.answer("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard())

# Обработка кнопки "Отменить заявку"
@router.callback_query(F.data == "cancel_request")
async def cancel_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🆔 Введите номер Вашей ID Заявки для отмены:")
    await state.set_state(CancelOrderForm.request_id)

@router.message(StateFilter(CancelOrderForm.request_id))
async def process_cancel_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    if not get_order_data_by_id(request_id):
        await message.answer("🚫 Неверный ID заявки. Пожалуйста, введите корректный номер ID.")
        await state.clear()
        return
    
    cancel_order(request_id)
    await message.answer("✅ Ваша заявка успешно отменена.")
    await notify_admins(bot, f"👤 Заявка с ID {request_id} была отменена пользователем.")
    
    # Возврат в главное меню после отмены заявки
    await message.answer("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Обработка кнопки "Оставить отзыв"
@router.callback_query(F.data.startswith("leave_feedback:"))
async def leave_feedback(callback_query: CallbackQuery, state: FSMContext):
    request_id = int(callback_query.data.split(":")[1])
    await state.update_data(request_id=request_id)
    await callback_query.message.edit_text("📝 Введите ваш отзыв:")
    await state.set_state(FeedbackForm.feedback)

@router.message(StateFilter(FeedbackForm.feedback))
async def process_feedback(message: Message, state: FSMContext):
    user_data = await state.get_data()
    request_id = user_data['request_id']
    feedback = sanitize_input(message.text)

    # Сохранение отзыва в JSON-файл
    save_feedback_to_json(request_id, feedback)
    await message.answer("📎 Спасибо за Ваш отзыв!")
    await notify_admins(bot, f"👤 Пользователь оставил отзыв на заявку с ID {request_id}: {feedback}")
    
    # Возврат в главное меню после оставления отзыва
    await message.answer("📋 Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Обработка ввода номера телефона
@router.message(StateFilter(OrderForm.phone_number))
async def process_phone_number(message: Message, state: FSMContext):
    phone_number = sanitize_input(message.text.strip())
    if not is_valid_phone_number(phone_number):
        await message.answer("🚫 Неверный формат номера телефона. Пожалуйста, введите корректный номер.")
        return
    await state.update_data(phone_number=phone_number)
    await message.answer("❓ Введите причину обращения:")
    await state.set_state(OrderForm.reason)

# Обработка нажатия на кнопку "Стоимость услуг"
# @router.callback_query(F.data == 'show_price')
# async def show_price(callback_query: CallbackQuery):
#     # Конвертация готового PDF в изображение
#     pdf_path = "price_table.pdf"  # Путь к готовому PDF-файлу
#     image_paths = convert_pdf_to_images(pdf_path, "price_table_image")
    
#     # Отправка изображения
#     for image_path in image_paths:
#         photo = FSInputFile(image_path)
#         await bot.send_photo(callback_query.from_user.id, photo)

# Обработка загрузки PDF-документа
# @router.message(F.document & (F.document.mime_type == "application/pdf"))
# async def handle_pdf(message: types.Message):
#     await process_pdf(message)

# Обработка кнопки "Стоимость услуг"
@router.callback_query(F.data == "show_price")
async def show_price(callback_query: CallbackQuery):
    prices = load_prices()
    formatted_prices = format_prices(prices)
    messages = split_message(formatted_prices)
    for msg in messages:
        await callback_query.message.answer(msg, parse_mode="MarkdownV2")

async def main():
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logging.info("✅ Бот остановлен!")
    finally:
        await shutdown(dp)

async def shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await bot.session.close()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("✅ Бот остановлен!")