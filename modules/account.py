import asyncio
import datetime
import logging
import os
import secrets
import string
import struct

import aiomysql
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

router = Router()

logger = logging.getLogger(__name__)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "hypego")
SHOP_DB_NAME = os.getenv("SHOP_DB_NAME", "bot_data")

RCON_HOST = os.getenv("RCON_HOST", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "0") or 0)
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "")
RCON_TIMEOUT = float(os.getenv("RCON_TIMEOUT", "10"))

KICK_COMMAND_TEMPLATE = os.getenv("KICK_COMMAND_TEMPLATE", "kick {user} {reason}")
KICK_REASON = os.getenv("KICK_REASON", "Кик из Telegram")
PASSWORD_CHANGE_COMMAND_TEMPLATE = os.getenv("PASSWORD_CHANGE_COMMAND_TEMPLATE", "")

ADMIN_IDS = {
    int(chunk)
    for chunk in os.getenv("ADMIN_IDS", "").replace(",", " ").split()
    if chunk.strip().lstrip("-").isdigit()
}

PASSWORD_ALPHABET = string.ascii_letters + string.digits

TIMEZONE_NAME = os.getenv("TIMEZONE_NAME", "MSK")
TIMEZONE = datetime.timezone(datetime.timedelta(hours=float(os.getenv("TIMEZONE_OFFSET", "3"))))

_pool: aiomysql.Pool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> aiomysql.Pool:
    global _pool
    async with _pool_lock:
        if _pool is None or _pool.closed:
            _pool = await aiomysql.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME,
                autocommit=True,
                minsize=1,
                maxsize=5,
                charset="utf8mb4",
            )
    return _pool


async def fetch_all(query: str, args: tuple = ()) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, args)
        return list(await cursor.fetchall())


async def fetch_one(query: str, args: tuple = ()) -> dict | None:
    rows = await fetch_all(query, args)
    return rows[0] if rows else None


async def execute(query: str, args: tuple = ()) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn, conn.cursor() as cursor:
        await cursor.execute(query, args)
        return cursor.rowcount


class RconError(Exception):
    pass


async def run_rcon(command: str) -> str:
    if not RCON_PORT or not RCON_PASSWORD:
        raise RconError("RCON не настроен: задайте RCON_PORT и RCON_PASSWORD")

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(RCON_HOST, RCON_PORT), timeout=RCON_TIMEOUT
    )
    try:
        await _rcon_send(writer, 1, 3, RCON_PASSWORD)
        request_id, _ = await _rcon_read(reader)
        if request_id == -1:
            raise RconError("RCON: неверный пароль")

        await _rcon_send(writer, 2, 2, command)
        _, payload = await _rcon_read(reader)
        return payload
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def _rcon_send(
    writer: asyncio.StreamWriter,
    request_id: int,
    packet_type: int,
    payload: str,
) -> None:
    body = struct.pack("<ii", request_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
    writer.write(struct.pack("<i", len(body)) + body)
    await writer.drain()


async def _rcon_read(reader: asyncio.StreamReader) -> tuple[int, str]:
    header = await asyncio.wait_for(reader.readexactly(4), timeout=RCON_TIMEOUT)
    (length,) = struct.unpack("<i", header)
    body = await asyncio.wait_for(reader.readexactly(length), timeout=RCON_TIMEOUT)
    request_id, _ = struct.unpack("<ii", body[:8])
    return request_id, body[8:-2].decode("utf-8", errors="replace")


def format_duration(seconds: int | None) -> str:
    total = int(seconds or 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours} ч. {minutes} мин. {secs} сек."


def format_date(value) -> str:
    """Аккаунты хранят даты либо как строку, либо как unix-время."""
    text = str(value or "").strip()

    if not text:
        return "неизвестно"

    if text.isdigit():
        moment = datetime.datetime.fromtimestamp(int(text), TIMEZONE)
        return f"{moment:%H:%M %d.%m.%Y} {TIMEZONE_NAME}"

    return text


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def get_accounts(user_id: int) -> list[str]:
    rows = await fetch_all(
        "SELECT nickname FROM auth WHERE tgId = %s ORDER BY nickname", (user_id,)
    )
    return [row["nickname"] for row in rows]


async def get_account(user_id: int, nickname: str) -> dict | None:
    if is_admin(user_id):
        return await fetch_one(
            "SELECT * FROM auth WHERE LOWER(nickname) = LOWER(%s)", (nickname,)
        )
    return await fetch_one(
        "SELECT * FROM auth WHERE LOWER(nickname) = LOWER(%s) AND tgId = %s",
        (nickname, user_id),
    )


async def build_account_card(account: dict) -> str:
    nickname = account["nickname"]

    played = await fetch_one(
        "SELECT time, session_time FROM time WHERE LOWER(nickname) = LOWER(%s)", (nickname,)
    )
    balance = await fetch_one(
        "SELECT money FROM economy WHERE LOWER(nickname) = LOWER(%s)", (nickname,)
    )

    lines = [
        f"📝 Информация по аккаунту '{nickname}':",
        "",
        f"📅 Дата регистрации: {format_date(account.get('reg_date'))}",
        "",
        f"🎮 Всего наиграно времени: {format_duration(played.get('time') if played else 0)}",
        (
            "🕒 Длительность последней сессии: "
            f"{format_duration(played.get('session_time') if played else 0)}"
        ),
        "",
        f"💰 Баланс: {(balance or {}).get('money') or 0} $",
        "",
        "🔐 Последний вход:",
        f"» Дата - {format_date(account.get('last_date'))}",
        f"» IP - {account.get('address') or 'неизвестно'}",
        f"» Устройство - {account.get('last_device') or 'неизвестно'}",
        f"» Порт - {account.get('last_port') or 'неизвестно'}",
        "",
        f"🌀 Привязанный Telegram: {account.get('tgId') or 'нет'}",
        "",
        f"👤 Выберите действие, которое хотите совершить с аккаунтом '{nickname}'",
    ]
    return "\n".join(lines)


def accounts_keyboard(nicknames: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🎮 {nickname}", callback_data=f"acc:menu:{nickname}")]
        for nickname in nicknames
    ]
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="acc:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_keyboard(nickname: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Покупки", callback_data=f"acc:buys:{nickname}")],
            [
                InlineKeyboardButton(
                    text="👢 Кикнуть с сервера", callback_data=f"acc:ask:kick:{nickname}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 Сменить пароль", callback_data=f"acc:ask:pwd:{nickname}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛡 Сбросить защиту", callback_data=f"acc:ask:prot:{nickname}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔓 Отвязать аккаунт", callback_data=f"acc:ask:unlink:{nickname}"
                )
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=f"acc:menu:{nickname}"),
                InlineKeyboardButton(text="◀️ Аккаунты", callback_data="acc:list"),
            ],
        ]
    )


def back_keyboard(nickname: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"acc:menu:{nickname}")]
        ]
    )


def confirm_keyboard(action: str, nickname: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да", callback_data=f"acc:do:{action}:{nickname}"
                ),
                InlineKeyboardButton(
                    text="◀️ Нет", callback_data=f"acc:menu:{nickname}"
                ),
            ]
        ]
    )


CONFIRM_TEXTS = {
    "kick": "👢 Кикнуть игрока '{nickname}' с сервера?",
    "pwd": "🔑 Сгенерировать новый пароль для аккаунта '{nickname}'?",
    "prot": "🛡 Сбросить защиту (скин и привязку устройства) аккаунта '{nickname}'?",
    "unlink": "🔓 Отвязать аккаунт '{nickname}' от вашего Telegram?",
}


async def show_accounts(target: Message | CallbackQuery, user_id: int) -> None:
    nicknames = await get_accounts(user_id)

    if not nicknames:
        await answer(target, "❌ К вашему Telegram не привязан ни один аккаунт.", None)
        return

    if len(nicknames) == 1:
        await show_account(target, user_id, nicknames[0])
        return

    await answer(target, "🎮 Выберите аккаунт:", accounts_keyboard(nicknames))


async def show_account(target: Message | CallbackQuery, user_id: int, nickname: str) -> None:
    account = await get_account(user_id, nickname)

    if not account:
        await answer(target, "❌ Аккаунт не найден или не привязан к вам.", None)
        return

    await answer(
        target, await build_account_card(account), account_keyboard(account["nickname"])
    )


async def answer(
    target: Message | CallbackQuery, text: str, keyboard: InlineKeyboardMarkup | None
) -> None:
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


@router.message(Command("account"))
async def cmd_account(message: Message):
    await show_accounts(message, message.from_user.id)


@router.callback_query(F.data == "acc:list")
async def cb_list(callback: CallbackQuery):
    await callback.answer()
    await show_accounts(callback, callback.from_user.id)


@router.callback_query(F.data == "acc:close")
async def cb_close(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


@router.callback_query(F.data.startswith("acc:menu:"))
async def cb_menu(callback: CallbackQuery):
    await callback.answer()
    await show_account(callback, callback.from_user.id, callback.data.split(":", 2)[2])


@router.callback_query(F.data.startswith("acc:buys:"))
async def cb_purchases(callback: CallbackQuery):
    await callback.answer()
    nickname = callback.data.split(":", 2)[2]
    account = await get_account(callback.from_user.id, nickname)

    if not account:
        await callback.message.edit_text("❌ Аккаунт не найден или не привязан к вам.")
        return

    rows = await fetch_all(
        f"SELECT payment_id, cost, payment_type, status, created_at "
        f"FROM `{SHOP_DB_NAME}`.purchases "
        f"WHERE LOWER(nickname) = LOWER(%s) ORDER BY id DESC LIMIT 10",
        (account["nickname"],),
    )

    if not rows:
        text = f"🛒 Покупок у {account['nickname']} не найдено."
    else:
        lines = [f"🛒 Последние покупки {account['nickname']}:", ""]
        for row in rows:
            lines.append(
                f"#{row['payment_id'] or '—'} — {row['cost']} ₽ "
                f"({row['payment_type'] or 'не указан'}, {row['status']})\n"
                f"» {row['created_at'] or 'дата неизвестна'}"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=back_keyboard(account["nickname"]))


@router.callback_query(F.data.startswith("acc:ask:"))
async def cb_confirm(callback: CallbackQuery):
    await callback.answer()
    _, _, action, nickname = callback.data.split(":", 3)

    if action not in CONFIRM_TEXTS:
        return

    account = await get_account(callback.from_user.id, nickname)

    if not account:
        await callback.message.edit_text("❌ Аккаунт не найден или не привязан к вам.")
        return

    await callback.message.edit_text(
        CONFIRM_TEXTS[action].format(nickname=account["nickname"]),
        reply_markup=confirm_keyboard(action, account["nickname"]),
    )


@router.callback_query(F.data.startswith("acc:do:"))
async def cb_action(callback: CallbackQuery):
    await callback.answer()
    _, _, action, nickname = callback.data.split(":", 3)

    account = await get_account(callback.from_user.id, nickname)

    if not account:
        await callback.message.edit_text("❌ Аккаунт не найден или не привязан к вам.")
        return

    nickname = account["nickname"]

    if action == "kick":
        text = await do_kick(nickname)
    elif action == "pwd":
        text = await do_password_change(callback.from_user.id, nickname)
    elif action == "prot":
        text = await do_reset_protection(nickname)
    elif action == "unlink":
        text = await do_unlink(callback.from_user.id, nickname)
    else:
        return

    keyboard = (
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Аккаунты", callback_data="acc:list")]
            ]
        )
        if action == "unlink"
        else back_keyboard(nickname)
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


async def do_kick(nickname: str) -> str:
    command = KICK_COMMAND_TEMPLATE.replace("{user}", nickname).replace(
        "{reason}", KICK_REASON
    )
    try:
        output = await run_rcon(command)
    except (RconError, OSError, asyncio.IncompleteReadError, asyncio.TimeoutError) as error:
        logger.error("Кик %s не выполнен: %s", nickname, error)
        return f"❌ Не удалось кикнуть {nickname}: {error}"

    return f"👢 Игрок {nickname} кикнут с сервера.\n\n{output.strip() or 'Сервер не ответил.'}"


async def do_password_change(user_id: int, nickname: str) -> str:
    if not PASSWORD_CHANGE_COMMAND_TEMPLATE:
        return (
            "❌ Смена пароля недоступна: в окружении не задан "
            "PASSWORD_CHANGE_COMMAND_TEMPLATE."
        )

    password = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(12))
    command = PASSWORD_CHANGE_COMMAND_TEMPLATE.replace("{user}", nickname).replace(
        "{password}", password
    )

    try:
        await run_rcon(command)
    except (RconError, OSError, asyncio.IncompleteReadError, asyncio.TimeoutError) as error:
        logger.error("Смена пароля %s не выполнена: %s", nickname, error)
        await execute(
            "INSERT INTO password_changes (tg_id, nickname, success) VALUES (%s, %s, 0)",
            (user_id, nickname),
        )
        return f"❌ Не удалось сменить пароль для {nickname}: {error}"

    await execute(
        "INSERT INTO password_changes (tg_id, nickname, success) VALUES (%s, %s, 1)",
        (user_id, nickname),
    )
    return (
        f"🔑 Новый пароль для {nickname}:\n\n"
        f"{password}\n\n"
        "Сохраните его и удалите это сообщение."
    )


async def do_reset_protection(nickname: str) -> str:
    affected = await execute(
        "UPDATE protection SET skin = NULL, cid = NULL WHERE LOWER(nickname) = LOWER(%s)",
        (nickname,),
    )

    if not affected:
        return f"🛡 У {nickname} нет активной защиты."

    return f"🛡 Защита аккаунта {nickname} сброшена."


async def do_unlink(user_id: int, nickname: str) -> str:
    affected = await execute(
        "UPDATE auth SET tgId = NULL WHERE LOWER(nickname) = LOWER(%s) AND tgId = %s",
        (nickname, user_id),
    )

    if not affected:
        return f"❌ Аккаунт {nickname} уже не привязан к вашему Telegram."

    return f"🔓 Аккаунт {nickname} отвязан от вашего Telegram."
