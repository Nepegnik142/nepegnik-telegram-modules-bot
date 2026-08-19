from modules.shared import (
    HELP_TEXT,
    START_TEXT,
    create_router,
    register_fallback,
    register_text_command,
)

router = create_router()

register_text_command(router, "start", START_TEXT)
register_text_command(router, "help", HELP_TEXT)
register_fallback(router)
