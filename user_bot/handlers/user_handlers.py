from aiogram import Router

from handlers.account_link import router as account_link_router
from handlers.devices import router as devices_router
from handlers.menu import router as menu_router
from handlers.payments import router as payments_router
from handlers.referrals import router as referrals_router
from handlers.setup import router as setup_router


router = Router()
# Ahead of menu_router: both answer /start, and this one has to see
# `link_<token>` before the plain handler renders the main menu instead.
router.include_router(account_link_router)
router.include_router(menu_router)
router.include_router(referrals_router)
router.include_router(setup_router)
router.include_router(payments_router)
router.include_router(devices_router)
