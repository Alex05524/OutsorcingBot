from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def start_button_keyboard(admin=False):
    buttons = [
        [InlineKeyboardButton(text="🚀 Старт", callback_data="start_work")]
        ]
    if admin:
        buttons.append([InlineKeyboardButton(text="🔧 Панель администратора", callback_data="admin_panel")])
        buttons.append([InlineKeyboardButton(text="📊 Аналитика заявок", callback_data="show_stats")])
        buttons.append([InlineKeyboardButton(text="Список новых заявок", callback_data="list_new_orders")])
        buttons.append([InlineKeyboardButton(text="Добавить администратора", callback_data="add_admin")])
        buttons.append([InlineKeyboardButton(text="Удалить администратора", callback_data="remove_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def main_menu_keyboard(admin=False):
    buttons = [ 
        [InlineKeyboardButton(text="📋 Услуги", callback_data="services")],
        [InlineKeyboardButton(text="📝 Оформить заявку", callback_data="apply_request")],
        [InlineKeyboardButton(text="📦 Статус заявки", callback_data="status_request")],
        [InlineKeyboardButton(text="✏️ Редактировать заявку", callback_data="edit_request")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="show_faq")]
    ]
    if admin:
        buttons.append([InlineKeyboardButton(text="📊 Аналитика заявок", callback_data="show_stats")])
        buttons.append([InlineKeyboardButton(text="🔧 Панель администратора", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
    
def services_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Компьютерная помощь", callback_data="service_1")],
        [InlineKeyboardButton(text="Предложения по монтажным работам", callback_data="service_2")],
        [InlineKeyboardButton(text="Заказ на выезд", callback_data="service_3")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="cancel_request")],
        [InlineKeyboardButton(text="Оставить отзыв", callback_data="leave_feedback")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def edit_request_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать имя", callback_data="edit_full_name")],
        [InlineKeyboardButton(text="Редактировать адрес", callback_data="edit_address")],
        [InlineKeyboardButton(text="Редактировать телефон", callback_data="edit_phone_number")],
        [InlineKeyboardButton(text="Редактировать причину", callback_data="edit_reason")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def admin_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обработано", callback_data="status_processed")],
        [InlineKeyboardButton(text="В работе", callback_data="status_in_progress")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
    ])

def remove_admin_keyboard(admin_ids):
    buttons = []
    for admin_id in admin_ids:
        buttons.append([InlineKeyboardButton(text=f"Удалить администратора {admin_id}", callback_data=f"confirm_remove_admin_{admin_id}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)