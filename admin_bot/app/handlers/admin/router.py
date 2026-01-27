"""Admin router aggregation."""

from aiogram import Router
from app.handlers.admin import menu, users, promo, broadcast, hosts_quick

# Import feature routers here as they are created
# from app.features.admin.nodes import router as nodes_router
# from app.features.admin.hosts import router as hosts_router
# from app.features.admin.squads import router as squads_router

router = Router(name="admin")
router.include_router(menu.router)
router.include_router(users.router)
router.include_router(promo.router)
router.include_router(broadcast.router)
router.include_router(hosts_quick.router)

# Include feature routers
# router.include_router(nodes_router)
# router.include_router(hosts_router)
# router.include_router(squads_router)
