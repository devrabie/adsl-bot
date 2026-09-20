from aiogram.fsm.state import State, StatesGroup

class AddLineSG(StatesGroup):
    waiting_for_phone = State()
    waiting_for_password = State()
    waiting_for_captcha = State()

class ReauthLineSG(StatesGroup):
    waiting_for_captcha = State()

class EditLineThresholdSG(StatesGroup):
    waiting_for_gb_warning = State()
    waiting_for_gb_critical = State()
    waiting_for_days_warning = State()
    waiting_for_days_critical = State()
