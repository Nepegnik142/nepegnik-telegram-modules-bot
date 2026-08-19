from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я пример модульного Telegram‑бота.\n"
        "Используйте /help для получения справки."
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 **Доступные команды:**\n\n"
        "/start — запустить бота\n"
        "/help — показать эту справку\n"
        "/info — получить информацию о боте\n"
        "/echo [текст] — повторить ваш текст"
    )
    await message.answer(help_text)

@router.message()
async def handle_all_messages(message: Message):
    await message.answer(
        "Я не понимаю эту команду.\n"
        "Используйте /help для списка доступных команд."
    )
