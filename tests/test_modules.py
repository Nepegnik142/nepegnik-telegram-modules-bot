from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import Mock

import main


def load_module_by_name(name, modules_dir, monkeypatch):
    config = next(
        config
        for config in main.modules_config
        if config["module_name"] == name
    )
    monkeypatch.setattr(main, "modules_all", str(modules_dir))
    router, error = main.load_module(config)
    assert router is not None, error
    return __import__(name)


async def test_cmd_start_answers_greeting(monkeypatch):
    message = Mock()
    message.answer = AsyncMock()
    modules_dir = Path(__file__).parents[1] / "modules"
    module = load_module_by_name("example", modules_dir, monkeypatch)

    await module.cmd_start(message)

    message.answer.assert_awaited_once()
    assert "Привет" in message.answer.await_args.args[0]


async def test_cmd_help_answers_command_list(monkeypatch):
    message = Mock()
    message.answer = AsyncMock()
    modules_dir = Path(__file__).parents[1] / "modules"
    module = load_module_by_name("example", modules_dir, monkeypatch)

    await module.cmd_help(message)

    message.answer.assert_awaited_once()
    assert "Доступные команды" in message.answer.await_args.args[0]
    assert "/echo" in message.answer.await_args.args[0]


async def test_handle_all_messages_answers_fallback(monkeypatch):
    message = Mock()
    message.answer = AsyncMock()
    modules_dir = Path(__file__).parents[1] / "modules"
    module = load_module_by_name("example", modules_dir, monkeypatch)

    await module.handle_all_messages(message)

    message.answer.assert_awaited_once()
    assert "не понимаю" in message.answer.await_args.args[0]


async def test_cmd_admin_answers_admin_panel(monkeypatch):
    message = Mock()
    message.answer = AsyncMock()
    modules_dir = Path(__file__).parents[1] / "modules"
    module = load_module_by_name("admin", modules_dir, monkeypatch)

    await module.cmd_admin(message)

    message.answer.assert_awaited_once()
    assert "администратора" in message.answer.await_args.args[0]
