import json
import os
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile, Message
from dotenv import load_dotenv
from pdf2image import convert_from_path
import fitz
from tabulate import tabulate

# Указываем абсолютный путь к файлу orders.json
ORDERS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'orders.json')

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info(f"Используемый путь к файлу: {ORDERS_FILE_PATH}")

# Загрузка переменных окружения
load_dotenv()

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

def load_orders():
    """Загружает заявки из JSON-файла."""
    logging.info(f"Загрузка заявок из файла: {ORDERS_FILE_PATH}")
    if os.path.exists(ORDERS_FILE_PATH):
        try:
            with open(ORDERS_FILE_PATH, "r", encoding="utf-8") as file:
                orders = json.load(file)
                logging.info(f"Загружено заявок: {len(orders)}")
                return orders
        except json.JSONDecodeError:
            logging.error("Ошибка чтения файла orders.json. Файл пуст или поврежден.")
            return []
    logging.warning(f"Файл {ORDERS_FILE_PATH} не найден.")
    return []

def save_orders(data: list):
    """Сохраняет заявки в JSON-файл.""" 
    with open(ORDERS_FILE_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    logging.info("Заявки успешно сохранены в файл orders.json")

async def notify_admins(bot: Bot, message: str):
    admin_ids_str = os.getenv("ADMIN_ID")
    if admin_ids_str:
        admin_ids = [int(admin_id.strip()) for admin_id in admin_ids_str.split(',')]
        for admin_id in admin_ids:
            await bot.send_message(admin_id, message)
    else:
        logging.warning("Переменная окружения ADMIN_ID не задана.")

async def notify_new_order(bot: Bot, order_data):
    message_text = (
        f"Новая заявка #{order_data['id']}:\n"
        f"Имя: {order_data['full_name']}\n"
        f"Адрес: {order_data['address']}\n"
        f"Телефон: {order_data['phone_number']}\n"
        f"Причина обращения: {order_data['reason']}\n"
        f"Статус: {order_data['status']}"
    )
    await notify_admins(bot, message_text)

async def notify_order_update(bot: Bot, order_data):
    message_text = (
        f"Обновление заявки #{order_data['id']}:\n"
        f"Имя: {order_data['full_name']}\n"
        f"Адрес: {order_data['address']}\n"
        f"Телефон: {order_data['phone_number']}\n"
        f"Причина обращения: {order_data['reason']}\n"
        f"Новый статус: {order_data['status']}"
    )
    await notify_admins(bot, message_text)

async def save_order_to_json(bot: Bot, order_data: dict) -> int:
    """Сохраняет заявку на выезд в JSON и уведомляет администраторов."""
    logging.info(f"Сохранение заявки: {order_data}")
    orders = load_orders()
    if orders:
        last_order_id = orders[-1].get("id", 0)
        order_data["id"] = last_order_id + 1
    else:
        order_data["id"] = 1

    # Добавление даты создания заявки
    order_data["created_at"] = datetime.now().isoformat()

    # Инициализация истории, если отсутствует
    if "history" not in order_data:
        order_data["history"] = []

    orders.append(order_data)
    logging.info(f"Обновленный список заявок: {orders}")
    save_orders(orders)
    logging.info(f"Заявка #{order_data['id']} успешно сохранена.")

    # Уведомление администраторов
    await notify_new_order(bot, order_data)
    return order_data["id"]

def cancel_order(request_id: int):
    """Удаляет заявку из JSON-файла по ID."""
    orders = load_orders()
    orders = [order for order in orders if order["id"] != request_id]
    save_orders(orders)
    logging.info(f"Заявка с ID {request_id} была удалена.")

def get_order_status(order_id: int) -> str:
    """Возвращает статус заявки по её ID."""
    orders = load_orders()
    if not isinstance(orders, list):
        return "Ошибка загрузки заявок"

    for order in orders:
        if order["id"] == order_id:
            reason = order.get("reason", "Причина не указана")
            status = order.get("status", "Статус не указан")
            return f"{reason}\n{status}"

    logging.info(f"Заявка #{order_id} не найдена.")
    return "Заявка не найдена"

def update_order(order_id, key, value):
    """Обновляет заявку по ID."""
    try:
        orders = load_orders()
        order = next((order for order in orders if order["id"] == order_id), None)
        if order:
            current_value = order.get(key, None)
            order[key] = value
            save_orders(orders)
            return current_value, value
        return None, None
    except Exception as e:
        logging.error(f"Ошибка при работе с JSON: {e}")
        return None, None

def is_valid_request_id(request_id):
    """Проверяет валидность ID заявки."""
    orders = load_orders()
    return any(order["id"] == request_id for order in orders)

def update_request(request_id, new_data):
    """Обновляет заявку по request_id."""
    orders = load_orders()
    for order in orders:
        if order['id'] == request_id:
            order.update(new_data)
            save_orders(orders)
            return True
    return False

def update_order_status(request_id: int, new_status: str):
    """Обновляет статус заявки и сохраняет изменения в JSON-файл."""
    orders = load_orders()
    for order in orders:
        if order["id"] == request_id:
            if "history" not in order:
                order["history"] = []
            order["status"] = new_status
            order["history"].append({'timestamp': datetime.now().isoformat(), 'status': new_status})
            save_orders(orders)
            logging.info(f"Статус заявки #{request_id} обновлен на '{new_status}'.")
            return order
    logging.warning(f"Заявка с ID {request_id} не найдена.")
    return None

def get_order_data_by_id(request_id: int):
    """Возвращает данные заявки по ID."""
    orders = load_orders()
    for order in orders:
        if order["id"] == request_id:
            return order
    return None

def get_new_orders_list() -> str:
    """Возвращает список новых заявок."""
    orders = load_orders()
    if not orders:
        return "Нет новых заявок."

    response_text = "Список новых заявок:\n\n"
    for order in orders:
        request_id = order.get('id', 'Не указан')
        full_name = order.get('full_name', 'Не указано')
        address = order.get('address', 'Не указан')
        phone_number = order.get('phone_number', 'Не указан')
        reason = order.get('reason', 'Не указана')
        status = order.get('status', 'Ожидает обработки')

        if request_id == 'Не указан':
            logging.warning(f"Заявка без ID: {order}")

        response_text += (
            f"ID заявки: {request_id}\n"
            f"ФИО: {full_name}\n"
            f"Адрес: {address}\n"
            f"Телефон: {phone_number}\n"
            f"Причина: {reason}\n"
            f"Статус: {status}\n\n"
        )

    return response_text

def save_feedback_to_json(request_id: int, feedback: str):
    """Сохраняет отзыв пользователя в JSON-файл."""
    orders = load_orders()
    for order in orders:
        if order["id"] == request_id:
            if "feedback" not in order:
                order["feedback"] = []
            order["feedback"].append({'timestamp': datetime.now().isoformat(), 'feedback': feedback})
            save_orders(orders)
            logging.info(f"Отзыв для заявки #{request_id} успешно сохранен.")
            return order
    logging.warning(f"Заявка с ID {request_id} не найдена.")
    return None

async def notify_user(bot: Bot, user_id: int, message: str):
    """Отправляет уведомление пользователю."""
    await bot.send_message(user_id, message)

async def process_pdf(message: Message):
    """Обрабатывает загруженный PDF-документ, конвертирует в изображения и отправляет в Telegram."""
    file_path = await message.document.download()
    images = convert_from_path(file_path.name)

    try:
        for i, image in enumerate(images):
            image_path = f"page_{i+1}.jpg"
            image.save(image_path, "JPEG")
            await message.answer_photo(FSInputFile(image_path))
            os.remove(image_path)
    finally:
        os.remove(file_path.name)

def convert_pdf_to_images(pdf_path, output_folder="images"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    pdf_document = fitz.open(pdf_path)
    image_paths = []

    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap()
        image_path = f"{output_folder}/page_{page_num + 1}.png"
        pix.save(image_path)
        image_paths.append(image_path)

    return image_paths

def escape_md(text: str) -> str:
    """Экранирует специальные символы MarkdownV2"""
    if not isinstance(text, str):
        return text
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return ''.join(f'\\{char}' if char in special_chars else char for char in text)

def load_prices():
    with open('prices.json', 'r', encoding='utf-8') as file:
        return json.load(file)

def format_prices(prices):
    table_data = []
    for service in prices['services']:
        name = escape_md(service['name'])
        price = escape_md(service['price'])
        note = escape_md(service['note'])
        table_data.append([name, price, note])
    
    headers = ["Услуга", "Цена (KZT)", "Примечание"]
    formatted_prices = "💲 *Стоимость услуг:*\n\n"
    formatted_prices += "```\n"
    formatted_prices += tabulate(table_data, headers, tablefmt="grid")
    formatted_prices += "\n```"
    return formatted_prices

def split_message(message, max_length=4096):
    """Разбивает сообщение на части, чтобы избежать ошибки MESSAGE_TOO_LONG"""
    parts = []
    while len(message) > max_length:
        split_index = message.rfind('\n', 0, max_length)
        if split_index == -1:
            split_index = max_length
        parts.append(message[:split_index])
        message = message[split_index:]
    parts.append(message)
    return parts