import nuke

import telegram_render_notifier


toolbar = nuke.menu("Nuke")
telegram_menu = toolbar.addMenu("Telegram Notify")
telegram_menu.addCommand(
    "Send Test Message",
    "telegram_render_notifier.send_test_message()",
)
telegram_menu.addCommand(
    "Show Config Path",
    "telegram_render_notifier.show_config_path()",
)
