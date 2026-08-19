import logging
import os

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

logger = logging.getLogger(__name__)

router = Router()


def _load_admin_ids() -> frozenset[int]:
    raw = os.environ.get("ADMIN_IDS", "")
    admin_ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            admin_ids.add(int(part))
        except ValueError:
            logger.warning(f"Некорректный ID администратора в ADMIN_IDS: {part!r}")
    return frozenset(admin_ids)


ADMIN_IDS = _load_admin_ids()


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id if message.from_user else None

    if not is_admin(user_id):
        logger.warning(f"Отказано в доступе к /admin для пользователя {user_id}")
        await message.answer("Недостаточно прав для выполнения этой команды.")
        return

    await message.answer("Панель администратора")
