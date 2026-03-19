from aiogram.fsm.state import State, StatesGroup


class EmailCaptureState(StatesGroup):
    waiting_email = State()
