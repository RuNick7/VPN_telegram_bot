"""Admin router aggregation."""

from aiogram import Router

from app.handlers.admin import broadcast, gifts, hosts_quick, menu, payments, promo, users
from app.middlewares import AdminAccessMiddleware

router = Router(name="admin")

# Authorization for every admin handler lives here, not in the handlers. Both
# observers are needed: aiogram dispatches Messages and CallbackQueries through
# separate chains, so registering one leaves the other unguarded.
router.message.middleware(AdminAccessMiddleware())
router.callback_query.middleware(AdminAccessMiddleware())

router.include_router(menu.router)
router.include_router(users.router)
router.include_router(promo.router)
router.include_router(broadcast.router)
router.include_router(hosts_quick.router)
router.include_router(gifts.router)
router.include_router(payments.router)
