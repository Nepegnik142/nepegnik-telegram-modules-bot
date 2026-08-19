import logging
import sys
from pathlib import Path

import pytest
from aiogram import Router

import main


def module_config(name: str, path: str) -> dict:
    return {
        "module_name": name,
        "module_version": "test",
        "module_path": path,
    }


def test_load_module_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "modules_all", str(tmp_path))
    config = module_config("missing_module", "does_not_exist.py")

    router, error = main.load_module(config)

    assert router is None
    assert "missing_module" in error
    assert str(tmp_path / "does_not_exist.py") in error
    assert "missing_module" not in sys.modules


def test_load_module_without_router(tmp_path, monkeypatch):
    module_path = tmp_path / "no_router.py"
    module_path.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(main, "modules_all", str(tmp_path))
    config = module_config("no_router_module", module_path.name)

    router, error = main.load_module(config)

    assert router is None
    assert "router" in error


def test_load_module_returns_module_router_and_registers_module(
    tmp_path, monkeypatch
):
    module_path = tmp_path / "valid.py"
    module_path.write_text(
        "from aiogram import Router\nrouter = Router()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "modules_all", str(tmp_path))
    config = module_config("valid_module", module_path.name)

    router, error = main.load_module(config)

    assert isinstance(router, Router)
    assert error == ""
    assert sys.modules["valid_module"].router is router


def test_load_module_import_error_is_returned(tmp_path, monkeypatch):
    module_path = tmp_path / "raising.py"
    module_path.write_text(
        "raise RuntimeError('import failed')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "modules_all", str(tmp_path))
    config = module_config("raising_module", module_path.name)

    router, error = main.load_module(config)

    assert router is None
    assert "RuntimeError" in error
    assert "raising_module" in error
    assert "raising_module" in sys.modules


@pytest.mark.asyncio
async def test_load_and_update_modules_loads_successes_and_logs_failures(
    tmp_path, monkeypatch, caplog
):
    good_path = tmp_path / "good.py"
    good_path.write_text(
        "from aiogram import Router\nrouter = Router()\n",
        encoding="utf-8",
    )
    no_router_path = tmp_path / "no_router.py"
    no_router_path.write_text("value = 1\n", encoding="utf-8")
    configs = [
        module_config("good_module", good_path.name),
        module_config("no_router_config", no_router_path.name),
        module_config("missing_config", "missing.py"),
    ]
    monkeypatch.setattr(main, "modules_all", str(tmp_path))
    monkeypatch.setattr(main, "modules_config", configs)

    class FakeDispatcher:
        def __init__(self):
            self.routers = []

        def include_router(self, router):
            self.routers.append(router)

    dispatcher = FakeDispatcher()
    with caplog.at_level(logging.INFO, logger=main.logger.name):
        await main.load_and_update_modules(dispatcher)

    assert dispatcher.routers == [sys.modules["good_module"].router]
    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR
    ]
    assert any("no_router_config" in message for message in error_messages)
    assert any("missing_config" in message for message in error_messages)
    assert (
        "Загрузка модулей завершена: 1 успешно, 2 с ошибками"
        in caplog.text
    )


def test_real_modules_config_resolves(monkeypatch):
    modules_dir = Path(__file__).parents[1] / "modules"
    monkeypatch.setattr(main, "modules_all", str(modules_dir))

    for config in main.modules_config:
        router, error = main.load_module(config)
        assert router is not None, error
        assert error == ""
