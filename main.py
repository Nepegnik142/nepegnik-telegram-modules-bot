import asyncio
import logging
import importlib.util
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Токен бота

modules_all = "modules"

modules_config = [
    #Модуль account идёт перед example: в example есть обработчик всех сообщений
    {
        "module_name": "account",
        "module_version": "1.0",
        "module_path": "account.py"
    },
    {
        "module_name": "example", #Название модуля
        "module_version": "1.0", #Версия модуля
        "module_path": "example.py" #Расположение или файл модуля
    },
    {
        "module_name": "admin",
        "module_version": "1.1",
        "module_path": "admin.py"
    },
    #Добавьте другие модули по необходимости или измените на свои
]

def load_module(module_config: dict) -> tuple[Router | None, str]:
    try:
        full_path = Path(modules_all) / module_config["module_path"]

        if not full_path.exists():
            error_msg = f"Модуль {module_config['module_name']} не найден по пути: {full_path}\nНапишите разработчику NEPEGNIK"
            return None, error_msg

        spec = importlib.util.spec_from_file_location(
            module_config["module_name"],
            str(full_path)
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_config["module_name"]] = module
        spec.loader.exec_module(module)

        if hasattr(module, 'router'):
            logger.info(
                f"Модуль '{module_config['module_name']}' v{module_config['module_version']} "
                f"успешно загружен из {full_path}"
            )
            return module.router, ""
        else:
            error_msg = (
                f"В модуле {module_config['module_name']} не найден атрибут 'router'. "
                f"Убедитесь, что модуль содержит роутер или напишите разработчику модулю."
            )
            return None, error_msg
    except Exception as e:
        error_msg = f"Ошибка загрузки модуля {module_config['module_name']}: {type(e).__name__}: {e}"
        return None, error_msg

async def load_and_update_modules(dp: Dispatcher) -> None:
    logger.info("Начинаю загрузку и обновление модулей...")

    loaded_modules_count = 0
    failed_modules = []

    for module_config in modules_config:
        router, error = load_module(module_config)

        if router is not None:
            dp.include_router(router)
            loaded_modules_count += 1
        else:
            failed_modules.append(f"{module_config['module_name']}: {error}")
            logger.error(error)

    logger.info(f"Загрузка модулей завершена: {loaded_modules_count} успешно, {len(failed_modules)} с ошибками")

    if failed_modules:
        logger.warning("Не удалось загрузить следующие модули:")
        for fail in failed_modules:
            logger.warning(f"  - {fail}")

async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    await load_and_update_modules(dp)

    logger.info("Бот запущен и готов к работе")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
