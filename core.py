"""Общие утилиты ядра бота: логирование и динамическая загрузка модулей."""

import importlib.util
import logging
import sys
from pathlib import Path

from aiogram import Dispatcher, Router

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

MODULES_DIR = "modules"

DEVELOPER_CONTACT = "Напишите разработчику NEPEGNIK"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(level=level, format=LOG_FORMAT)
    return logging.getLogger("bot")


logger = logging.getLogger("bot")


def load_module(module_config: dict, modules_dir: str = MODULES_DIR) -> tuple[Router | None, str]:
    name = module_config["module_name"]
    version = module_config["module_version"]

    try:
        full_path = Path(modules_dir) / module_config["module_path"]

        if not full_path.exists():
            return None, f"Модуль {name} не найден по пути: {full_path}\n{DEVELOPER_CONTACT}"

        spec = importlib.util.spec_from_file_location(name, str(full_path))
        if spec is None or spec.loader is None:
            return None, f"Не удалось прочитать модуль {name} из {full_path}\n{DEVELOPER_CONTACT}"

        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)

        router = getattr(module, "router", None)
        if router is None:
            return None, (
                f"В модуле {name} не найден атрибут 'router'. "
                f"Убедитесь, что модуль содержит роутер или напишите разработчику модуля."
            )

        logger.info(f"Модуль '{name}' v{version} успешно загружен из {full_path}")
        return router, ""
    except Exception as e:
        return None, f"Ошибка загрузки модуля {name}: {type(e).__name__}: {e}"


async def load_and_update_modules(dp: Dispatcher, modules_config: list[dict],
                                  modules_dir: str = MODULES_DIR) -> None:
    logger.info("Начинаю загрузку и обновление модулей...")

    loaded_modules_count = 0
    failed_modules = []

    for module_config in modules_config:
        router, error = load_module(module_config, modules_dir)

        if router is not None:
            dp.include_router(router)
            loaded_modules_count += 1
        else:
            failed_modules.append(f"{module_config['module_name']}: {error}")
            logger.error(error)

    logger.info(
        f"Загрузка модулей завершена: {loaded_modules_count} успешно, "
        f"{len(failed_modules)} с ошибками"
    )

    if failed_modules:
        logger.warning("Не удалось загрузить следующие модули:")
        for fail in failed_modules:
            logger.warning(f"  - {fail}")
