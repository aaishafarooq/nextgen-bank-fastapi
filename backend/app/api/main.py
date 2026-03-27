from fastapi import APIRouter
from backend.app.api.routes import home
from backend.app.api.routes.auth import (
    activate,
    login,
    logout,
    password_reset,
    refresh,
    register,
)
from backend.app.api.routes.bank_account import activate as bank_account_activate
from backend.app.api.routes.bank_account import create as create_bank_account

from backend.app.api.routes.next_of_kin import all
from backend.app.api.routes.next_of_kin import create as create_next_of_kin
from backend.app.api.routes.next_of_kin import delete
from backend.app.api.routes.next_of_kin import update as update_next_of_kin
from backend.app.api.routes.profile import create, all_profiles, update, upload, me
from backend.app.api.routes.bank_account import (
    deposit,
    statement,
    transaction_history,
    transfer,
    withdrawal,
)
api_router = APIRouter()

api_router.include_router(home.router)
api_router.include_router(register.router)
api_router.include_router(activate.router)
api_router.include_router(login.router)
api_router.include_router(password_reset.router)
api_router.include_router(refresh.router)
api_router.include_router(logout.router)
api_router.include_router(create.router)
api_router.include_router(update.router)
api_router.include_router(upload.router)
api_router.include_router(me.router)
api_router.include_router(all_profiles.router)
api_router.include_router(create_next_of_kin.router)
api_router.include_router(all.router)
api_router.include_router(update_next_of_kin.router)
api_router.include_router(delete.router)
api_router.include_router(create_bank_account.router)
api_router.include_router(bank_account_activate.router)
api_router.include_router(deposit.router)
api_router.include_router(transfer.router)
api_router.include_router(withdrawal.router)
api_router.include_router(transaction_history.router)
api_router.include_router(statement.router)
