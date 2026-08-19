"""Общие утилиты и тексты для модулей бота."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

START_TEXT = (
    "Привет! Я пример модульного Telegram‑бота.\n"
    "Используйте /help для получения справки."
)

HELP_TEXT = (
    "📖 **Доступные команды:**\n\n"
    "/start — запустить бота\n"
    "/help — показать эту справку\n"
    "/info — получить информацию о боте\n"
    "/echo [текст] — повторить ваш текст"
)

UNKNOWN_COMMAND_TEXT = (
    "Я не понимаю эту команду.\n"
    "Используйте /help для списка доступных команд."
)

ADMIN_TEXT = "Панель администратора"


def create_router() -> Router:
    return Router()


def register_text_command(router: Router, command: str, text: str) -> None:
    """Регистрирует команду, которая отвечает заранее заданным текстом."""

    async def handler(message: Message) -> None:
        await message.answer(text)

    handler.__name__ = f"cmd_{command}"
    router.message(Command(command))(handler)


def register_fallback(router: Router, text: str = UNKNOWN_COMMAND_TEXT) -> None:
    """Регистрирует обработчик для всех неизвестных сообщений."""

    async def handler(message: Message) -> None:
        await message.answer(text)

    handler.__name__ = "handle_all_messages"
    router.message()(handler)
