import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def restore_dynamic_modules():
    module_names = {
        "missing_module",
        "no_router_module",
        "valid_module",
        "raising_module",
        "good_module",
        "no_router_config",
        "missing_config",
        "example",
        "admin",
    }
    missing = object()
    previous = {
        name: sys.modules.get(name, missing)
        for name in module_names
    }

    yield

    for name, module in previous.items():
        if module is missing:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module
