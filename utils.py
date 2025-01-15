import json
import os
import logging

# Указываем абсолютный путь к файлу orders.json
ORDERS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'orders.json')

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info(f"Используемый путь к файлу: {ORDERS_FILE_PATH}")

def load_orders() -> list:
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

def save_order_to_json(order_data: dict) -> int:
    """Сохраняет заявку на выезд в JSON и возвращает её ID."""
    data = load_orders()
    if not isinstance(data, list):
        logging.error("Не удалось загрузить заявки: данные не в правильном формате.")
        return -1

    next_id = max([order.get("id", 0) for order in data], default=0) + 1
    order_data["id"] = next_id
    order_data["status"] = "Ожидает обработки"  # Устанавливаем статус по умолчанию
    data.append(order_data)
    save_orders(data)
    logging.info(f"Заявка #{next_id} успешно сохранена.")
    return next_id

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

def update_order_status(order_id: int, status: str) -> bool:
    """Обновляет статус заявки по её ID."""
    orders = load_orders()
    for order in orders:
        if order["id"] == order_id:
            order["status"] = status
            save_orders(orders)
            logging.info(f"Статус заявки #{order_id} успешно изменен на '{status}'.")
            return True
    logging.info(f"Заявка #{order_id} не найдена для обновления статуса.")
    return False

def get_order_data_by_id(request_id):
    """Возвращает данные заявки по её ID."""
    orders = load_orders()
    for order in orders:
        if order["id"] == request_id:
            return order
    return None