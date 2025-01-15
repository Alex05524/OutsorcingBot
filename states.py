from aiogram.fsm.state import State, StatesGroup

class OrderForm(StatesGroup):
    full_name = State()
    address = State()
    phone_number = State()
    reason = State()
    edit_value = State()
    confirm_finish = State()
    @staticmethod
    def request_id():
        return 'some_value'

class StatusForm(StatesGroup):
    request_id = State()

class ReviewForm(StatesGroup):
    review = State()