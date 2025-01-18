import re
import html

def is_valid_phone_number(phone_number: str) -> bool:
    """Проверяет, является ли номер телефона допустимым."""
    pattern = re.compile(r"^\+?[1-9]\d{1,14}$")
    return bool(pattern.match(phone_number))

def is_valid_address(address: str) -> bool:
    """Проверяет, является ли адрес допустимым."""
    return len(address) > 5  # Пример простой проверки длины адреса

def sanitize_input(user_input: str) -> str:
    """Санитизирует ввод пользователя для предотвращения XSS-атак."""
    return html.escape(user_input)