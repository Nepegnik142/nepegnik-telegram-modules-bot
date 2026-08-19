from modules.shared import ADMIN_TEXT, create_router, register_text_command

router = create_router()

register_text_command(router, "admin", ADMIN_TEXT)
