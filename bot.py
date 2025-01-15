import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F, Router, BaseMiddleware
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, TelegramObject
from dotenv import load_dotenv

from states import OrderForm, StatusForm
from keyboards import start_button_keyboard, main_menu_keyboard, edit_request_keyboard, services_keyboard, admin_panel_keyboard
from utils import save_order_to_json, get_order_status, load_orders, save_orders, update_order_status, is_valid_request_id, update_request, get_order_data_by_id

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота и ID админа
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("Токен бота или ID админа не найден. Убедитесь, что переменные окружения BOT_TOKEN и ADMIN_ID заданы.")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Определение состояний
class OrderForm(StatesGroup):
    full_name = State()
    address = State()
    phone_number = State()
    reason = State()
    request_id = State()
    edit_field = State()
    edit_value = State()

class AdminState(StatesGroup):
    request_id = State()
    status = State()

class StatusRequestForm(StatesGroup):
    request_id = State()

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
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Добро пожаловать, администратор! Нажмите кнопку ниже, чтобы начать.",
            reply_markup=start_button_keyboard(admin=True),
        )
    else:
        await message.answer(
            "Добро пожаловать! Нажмите кнопку ниже, чтобы начать.",
            reply_markup=start_button_keyboard(admin=False),
        )

# Обработка нажатия "Старт"
@router.callback_query(F.data == "start_work")
async def start_work(callback_query: CallbackQuery):
    if callback_query.from_user.id == ADMIN_ID:
        await callback_query.message.edit_text("Выберите действие из меню:", reply_markup=main_menu_keyboard(admin=True))
    else:
        await callback_query.message.edit_text("Выберите действие из меню:", reply_markup=main_menu_keyboard(admin=False))

# Обработка кнопки "Услуги"
@router.callback_query(F.data == "services")
async def show_services(callback_query: CallbackQuery):
    await callback_query.message.edit_text("Выберите услугу:", reply_markup=services_keyboard())

# Обработка кнопки "Редактировать заявку"
@router.callback_query(F.data == "edit_request")
async def edit_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите номер Вашей ID Заявки:")
    await state.set_state(OrderForm.request_id)

# Обработка ввода ID заявки для редактирования
@router.message(StateFilter(OrderForm.request_id))
async def process_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    if not is_valid_request_id(request_id):
        await message.answer("Неверный ID заявки. Пожалуйста, введите корректный номер ID.")
        return
    
    order_data = get_order_data_by_id(request_id)
    if not order_data:
        await message.answer("Заявка с таким ID не найдена. Пожалуйста, введите корректный номер ID.")
        return
    
    await state.update_data(request_id=request_id, order_data=order_data)
    await message.answer("Выберите, что вы хотите изменить:", reply_markup=edit_request_keyboard())
    await state.set_state(OrderForm.edit_field)

# Обработка кнопки "Редактировать имя"
@router.callback_query(F.data == "edit_name")
async def edit_name(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите новое имя:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="full_name")

# Обработка кнопки "Редактировать адрес"
@router.callback_query(F.data == "edit_address")
async def edit_address(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите новый адрес:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="address")

# Обработка кнопки "Редактировать телефон"
@router.callback_query(F.data == "edit_phone")
async def edit_phone(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите новый номер телефона:")
    await state.set_state(OrderForm.edit_value)
    await state.update_data(edit_field="phone_number")

# Обработка ввода нового значения
@router.message(StateFilter(OrderForm.edit_value))
async def process_edit_value(message: Message, state: FSMContext):
    new_value = message.text.strip()
    data = await state.get_data()
    request_id = data.get('request_id')
    edit_field = data.get('edit_field')
    update_request(request_id, {edit_field: new_value})
    
    order_data = get_order_data_by_id(request_id)
    await message.answer(
        f"Заявка #{request_id} успешно обновлена!\n"
        f"Имя: {order_data['full_name']}\n"
        f"Адрес: {order_data['address']}\n"
        f"Телефон: {order_data['phone_number']}\n"
        f"Причина обращения: {order_data['reason']}\n"
        f"Статус: {order_data['status']}"
    )
    # Возврат в главное меню после оформления заявки
    await message.answer("Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Обработка кнопки "Оформить заявку"
@router.callback_query(F.data == "apply_request")
async def create_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Пожалуйста, введите ваше полное имя:")
    await state.set_state(OrderForm.full_name)

# Обработка ввода полного имени для новой заявки
@router.message(StateFilter(OrderForm.full_name))
async def process_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    await state.update_data(full_name=full_name)
    await message.answer("Введите Ваш адрес:")
    await state.set_state(OrderForm.address)

# Обработка ввода адреса
@router.message(StateFilter(OrderForm.address))
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    await state.update_data(address=address)
    await message.answer("Введите Ваш телефон:")
    await state.set_state(OrderForm.phone_number)

# Обработка ввода номера телефона
@router.message(StateFilter(OrderForm.phone_number))
async def process_phone_number(message: Message, state: FSMContext):
    phone_number = message.text.strip()
    await state.update_data(phone_number=phone_number)
    await message.answer("Введите причину обращения:")
    await state.set_state(OrderForm.reason)

# Обработка ввода причины обращения
@router.message(StateFilter(OrderForm.reason))
async def process_reason(message: Message, state: FSMContext):
    reason = message.text.strip()
    await state.update_data(reason=reason)
    order_data = await state.get_data()
    order_id = save_order_to_json(order_data)
    
    await message.answer(
        f"Заявка #{order_id} успешно оформлена!\n"
        f"Имя: {order_data['full_name']}\n"
        f"Адрес: {order_data['address']}\n"
        f"Телефон: {order_data['phone_number']}\n"
        f"Причина обращения: {order_data['reason']}"
    )

    # Возврат в главное меню после оформления заявки
    await message.answer("Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Обработка кнопки "Назад" в меню услуг
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback_query: CallbackQuery):
    await callback_query.message.edit_text("Выберите действие из меню:", reply_markup=main_menu_keyboard())

# Обработка кнопки "Панель администратора"
@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите номер Вашей ID Заявки для изменения статуса:")
    await state.set_state(AdminState.request_id)

# Обработка ввода ID заявки для изменения статуса
@router.message(StateFilter(AdminState.request_id))
async def process_admin_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    if not is_valid_request_id(request_id):
        await message.answer("Неверный ID заявки. Пожалуйста, введите корректный номер ID.")
        return
    await state.update_data(request_id=request_id)
    await message.answer("Выберите новый статус заявки:", reply_markup=admin_panel_keyboard())
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
            await callback_query.message.edit_text(
                f"Статус заявки #{request_id} изменен на 'Обработано'.\n"
                f"Имя: {order['full_name']}\n"
                f"Адрес: {order['address']}\n"
                f"Телефон: {order['phone_number']}\n"
                f"Причина обращения: {order['reason']}\n"
                f"Статус: {order['status']}"
            )
            break
    else:
        await callback_query.message.edit_text(f"Не удалось изменить статус заявки #{request_id}.")
    await state.clear()

# Обработка кнопки "В работе"
@router.callback_query(F.data == "status_in_progress")
async def status_in_progress(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    request_id = data.get('request_id')
    orders = load_orders()
    for order in orders:
        if order['id'] == request_id:
            order['status'] = "В работе"
            save_orders(orders)
            await callback_query.message.edit_text(
                f"Статус заявки #{request_id} изменен на 'В работе'.\n"
                f"Имя: {order['full_name']}\n"
                f"Адрес: {order['address']}\n"
                f"Телефон: {order['phone_number']}\n"
                f"Причина обращения: {order['reason']}\n"
                f"Статус: {order['status']}"
            )
            break
    else:
        await callback_query.message.edit_text(f"Не удалось изменить статус заявки #{request_id}.")
    await state.clear()

# Обработка кнопки "Статус заявки"
@router.callback_query(F.data == "status_request")
async def status_request(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите номер Вашей ID Заявки для просмотра статуса:")
    await state.set_state(StatusRequestForm.request_id)

# Обработка ввода ID заявки для просмотра статуса
@router.message(StateFilter(StatusRequestForm.request_id))
async def process_status_request_id(message: Message, state: FSMContext):
    request_id = int(message.text.strip())
    if not is_valid_request_id(request_id):
        await message.answer("Неверный ID заявки. Пожалуйста, введите корректный номер ID.")
        return
    
    order_data = get_order_data_by_id(request_id)
    if not order_data:
        await message.answer("Заявка с таким ID не найдена. Пожалуйста, введите корректный номер ID.")
        return
    
    await message.answer(
        f"Заявка #{request_id}\n"
        f"Имя: {order_data['full_name']}\n"
        f"Адрес: {order_data['address']}\n"
        f"Телефон: {order_data['phone_number']}\n"
        f"Причина обращения: {order_data['reason']}\n"
        f"Статус: {order_data['status']}"
    )
    # Возврат в главное меню после просмотра статуса заявки
    await message.answer("Выберите действие из меню:", reply_markup=main_menu_keyboard())
    await state.clear()

# Основная функция для запуска бота
async def on_start(dp: Dispatcher):
    await dp.start_polling()

if __name__ == "__main__":
    from aiogram import Bot, Dispatcher

    # Создание экземпляра бота
    bot = Bot(token=BOT_TOKEN)

    # Создание экземпляра диспетчера
    dp = Dispatcher()

    # Регистрация мидлвари
    dp.update.middleware(LoggingMiddleware())

    # Регистрация маршрутов
    dp.include_router(router)

    try:
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")