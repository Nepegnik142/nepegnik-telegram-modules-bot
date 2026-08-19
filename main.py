import asyncio
import logging
import importlib.util
import os
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent, Message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # Токен бота

modules_all = "modules"

modules_config = [
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
    if not isinstance(module_config, dict):
        return None, "Некорректная конфигурация модуля: ожидается словарь."

    required_keys = ("module_name", "module_version", "module_path")
    missing_keys = [key for key in required_keys if key not in module_config]
    if missing_keys:
        return None, (
            "Некорректная конфигурация модуля: отсутствуют обязательные поля: "
            f"{', '.join(missing_keys)}"
        )

    invalid_keys = [
        key for key in required_keys
        if not isinstance(module_config[key], str) or not module_config[key].strip()
    ]
    if invalid_keys:
        return None, (
            "Некорректная конфигурация модуля: обязательные поля должны быть "
            f"непустыми строками: {', '.join(invalid_keys)}"
        )

    module_name = module_config["module_name"]
    registered_module = None
    previous_module = sys.modules.get(module_name)

    try:
        full_path = Path(modules_all) / module_config["module_path"]

        if not full_path.exists():
            error_msg = (
                f"Модуль {module_name} не найден по пути: {full_path}\n"
                "Напишите разработчику NEPEGNIK"
            )
            return None, error_msg

        spec = importlib.util.spec_from_file_location(
            module_name,
            str(full_path)
        )
        if spec is None:
            return None, (
                f"Не удалось создать спецификацию модуля {module_name} "
                f"для пути: {full_path}"
            )
        if spec.loader is None:
            return None, (
                f"Для модуля {module_name} не найден загрузчик по пути: "
                f"{full_path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        registered_module = module
        spec.loader.exec_module(module)

        if hasattr(module, 'router'):
            logger.info(
                f"Модуль '{module_name}' v{module_config['module_version']} "
                f"успешно загружен из {full_path}"
            )
            return module.router, ""
        else:
            error_msg = (
                f"В модуле {module_name} не найден атрибут 'router'. "
                f"Убедитесь, что модуль содержит роутер или напишите разработчику модулю."
            )
            return None, error_msg
    except Exception as e:
        if registered_module is not None:
            if previous_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module

        logger.exception(f"Ошибка загрузки модуля '{module_name}'")
        error_msg = f"Ошибка загрузки модуля {module_name}: {type(e).__name__}: {e}"
        return None, error_msg

async def load_and_update_modules(dp: Dispatcher) -> tuple[int, list[str]]:
    logger.info("Начинаю загрузку и обновление модулей...")

    loaded_modules_count = 0
    failed_modules = []
    module_names = set()

    for module_index, module_config in enumerate(modules_config, start=1):
        configured_name = (
            module_config.get("module_name")
            if isinstance(module_config, dict)
            else None
        )
        display_name = configured_name or f"позиция {module_index}"

        if isinstance(configured_name, str) and configured_name.strip():
            if configured_name in module_names:
                error = (
                    f"Дублирующееся имя модуля '{configured_name}' "
                    "в конфигурации"
                )
                failed_modules.append(f"{display_name}: {error}")
                logger.error(error)
                continue
            module_names.add(configured_name)

        router, error = load_module(module_config)

        if router is not None:
            try:
                dp.include_router(router)
            except Exception as e:
                error = (
                    f"Ошибка подключения модуля {display_name}: "
                    f"{type(e).__name__}: {e}"
                )
                failed_modules.append(f"{display_name}: {error}")
                logger.exception(
                    f"Не удалось подключить модуль '{display_name}'"
                )
            else:
                loaded_modules_count += 1
        else:
            failed_modules.append(f"{display_name}: {error}")
            logger.error(error)

    logger.info(f"Загрузка модулей завершена: {loaded_modules_count} успешно, {len(failed_modules)} с ошибками")

    if failed_modules:
        logger.warning("Не удалось загрузить следующие модули:")
        for fail in failed_modules:
            logger.warning(f"  - {fail}")

    return loaded_modules_count, failed_modules

async def handle_dispatcher_error(event: ErrorEvent) -> None:
    logger.exception(
        f"Ошибка обработки обновления: {type(event.exception).__name__}: "
        f"{event.exception}",
        exc_info=(
            type(event.exception),
            event.exception,
            event.exception.__traceback__,
        ),
    )

    message = event.update.message
    if message is None and event.update.callback_query is not None:
        message = event.update.callback_query.message

    if not isinstance(message, Message):
        return

    try:
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте ещё раз позже."
        )
    except Exception:
        logger.exception("Не удалось отправить уведомление об ошибке пользователю")

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError(
            "Токен бота не задан. Укажите токен в переменной окружения "
            "BOT_TOKEN или замените значение YOUR_BOT_TOKEN_HERE в main.py."
        )

    bot = Bot(token=BOT_TOKEN)
    try:
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        dp.errors.register(handle_dispatcher_error)

        loaded_modules_count, _ = await load_and_update_modules(dp)
        if loaded_modules_count == 0:
            error = "Не удалось загрузить ни одного модуля. Бот не будет запущен."
            logger.critical(error)
            raise RuntimeError(error)

        logger.info("Бот запущен и готов к работе")

        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.critical(
            f"Критическая ошибка при запуске бота: {e}",
            exc_info=True,
        )
        sys.exit(1)
