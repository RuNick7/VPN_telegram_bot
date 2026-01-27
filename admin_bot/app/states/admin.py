"""Admin FSM states."""

from aiogram.fsm.state import State, StatesGroup


class NodeCreateState(StatesGroup):
    """States for node creation."""
    name = State()
    host = State()
    port = State()
    confirm = State()


class NodeEditState(StatesGroup):
    """States for node editing."""
    node_id = State()
    field = State()
    value = State()


class HostCreateState(StatesGroup):
    """States for host creation."""
    name = State()
    node_id = State()
    ip = State()
    confirm = State()


class HostEditState(StatesGroup):
    """States for host editing."""
    host_id = State()
    field = State()
    value = State()


class SquadCreateState(StatesGroup):
    """States for squad creation."""
    name = State()
    type = State()  # internal or external
    confirm = State()


class UserCreateState(StatesGroup):
    """States for user creation."""
    username = State()
    expire_at = State()
    traffic_limit_bytes = State()
    tag = State()
    telegram_id = State()
    hwid_device_limit = State()


class UserEditState(StatesGroup):
    """States for user editing."""
    username = State()
    field = State()
    value = State()


class UserDeleteState(StatesGroup):
    """States for user deletion."""
    username = State()


class PromoCreateState(StatesGroup):
    """States for promo creation."""
    code = State()
    promo_type = State()
    value = State()
    one_time = State()


class PromoDeleteState(StatesGroup):
    """States for promo deletion."""
    code = State()


class BroadcastState(StatesGroup):
    """States for broadcast."""
    content = State()
    confirm = State()


class HostQuickCreateState(StatesGroup):
    """States for quick host creation."""
    remark = State()
    inbound = State()
    address = State()
    port = State()
    tag = State()
    nodes = State()
    squad = State()
    exclude_confirm = State()
