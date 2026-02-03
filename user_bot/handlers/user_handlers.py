from aiogram import Router

from handlers.menu import router as menu_router
from handlers.payments import router as payments_router
from handlers.referrals import router as referrals_router
from handlers.setup import router as setup_router


router = Router()
router.include_router(menu_router)
router.include_router(referrals_router)
router.include_router(setup_router)
router.include_router(payments_router)
