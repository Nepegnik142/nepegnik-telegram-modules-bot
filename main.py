import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from core import load_and_update_modules, setup_logging

logger = setup_logging()

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Токен бота

modules_config = [
    {
        "module_name": "example",  # Название модуля
        "module_version": "1.0",  # Версия модуля
        "module_path": "example.py"  # Расположение или файл модуля
    },
    {
        "module_name": "admin",
        "module_version": "1.1",
        "module_path": "admin.py"
    },
    # Добавьте другие модули по необходимости или измените на свои
]


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    await load_and_update_modules(dp, modules_config)

    logger.info("Бот запущен и готов к работе")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
