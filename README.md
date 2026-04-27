# Nuke Render Telegram Notifier

Nuke Render Telegram Notifier sends a Telegram message when a Nuke `Write` render finishes.

It is made for a very practical Nuke situation: you start a render, switch to another task, and want Telegram to tell you when the render is done.

## What it does

- Adds a **Telegram Notify** menu to Nuke
- Sends a test Telegram message from inside Nuke
- Sends a Telegram message after a `Write` node finishes rendering
- Includes script name, `Write` node, frame range, output path, machine, user, finish time, and elapsed time
- Uses only the Python standard library, so there are no extra Python packages to install
- Supports `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables
- Can fall back to a local queue if `Nuke.exe` is blocked from network access
- Can auto-start the queue bridge in the background when Nuke starts

## Why

Some renders are long enough that I do not want to keep checking Nuke.

Telegram notifications are simple and reliable, but Nuke is often blocked from direct internet access by firewall or security settings. This tool handles both cases:

- if Nuke can reach Telegram, it sends directly
- if Nuke is blocked, it writes a local queue file and an external bridge sends the message

## Requirements

- Foundry Nuke
- Python available outside Nuke for the queue bridge fallback
- A Telegram bot token from `@BotFather`
- A Telegram chat ID

No `requests` dependency is required.

## Installation

1. Copy this folder into a location Nuke can load, for example:

```text
D:/Scripts/nuke/NukeRenderTelegramNotifier
```

2. Add the plugin path to your `.nuke/init.py`:

```python
import nuke

nuke.pluginAddPath(r"D:/Scripts/nuke/NukeRenderTelegramNotifier")
```

3. Copy `telegram_settings.example.json` to:

```text
telegram_settings.json
```

4. Fill in:

```json
{
  "bot_token": "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE",
  "chat_id": "PASTE_YOUR_CHAT_ID_HERE"
}
```

5. Restart Nuke.

The menu should appear here:

```text
Nuke -> Telegram Notify
```

## Usage

First test the Telegram connection:

```text
Nuke -> Telegram Notify -> Send Test Message
```

If the test message arrives, render any `Write` node normally. A notification will be sent when the render completes.

## Configuration

The local config file is:

```text
telegram_settings.json
```

This file is intentionally ignored by git because it contains private Telegram credentials.

`bot_token`

Telegram bot token from `@BotFather`.

`chat_id`

Target chat ID. For personal messages, this is your own Telegram chat ID. For groups, it is the group chat ID.

`delivery_mode`

Controls how messages are delivered.

- `auto`: try direct sending first, then fall back to the local queue if Nuke is blocked
- `direct`: only send directly from Nuke
- `queue`: always write queue files and let the bridge send them

`auto_start_bridge`

Starts `telegram_queue_bridge.py` in the background when Nuke loads the plugin.

`queue_dir`

Optional custom queue folder. Leave empty to use the plugin's local `queue` folder.

`bridge_python`

Optional Python executable for the bridge. Leave empty to auto-detect `pyw`, `py`, `pythonw`, or `python`.

## Environment Variables

You can use environment variables instead of writing credentials into `telegram_settings.json`:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Environment variables override the values from the JSON config.

## Network-Blocked Nuke

If Nuke is blocked from internet access, you may see an error like:

```text
PermissionError(13, 'An attempt was made to access a socket in a way forbidden by its access permissions', None, 10013, None)
```

With `delivery_mode` set to `auto`, the plugin writes a queue file instead of failing. The queue bridge then sends it from a normal Python process outside Nuke.

The queue bridge is:

```text
telegram_queue_bridge.py
```

It is auto-started by default. You can also run it manually:

```powershell
py telegram_queue_bridge.py
```

## Files

- `init.py`: registers the render callbacks
- `menu.py`: adds the Nuke menu
- `telegram_render_notifier.py`: Nuke-side callback and queue logic
- `telegram_queue_bridge.py`: external sender for blocked Nuke setups
- `telegram_settings.example.json`: safe config template

## Security

Do not commit `telegram_settings.json`.

Do not commit the `queue` folder. Queue files may contain message text and render paths from your projects.

If a bot token was ever shared publicly, rotate it in `@BotFather`.

## Troubleshooting

`Telegram test failed: bot_token is empty`

Create `telegram_settings.json` from the example file and fill in `bot_token`.

`Telegram test failed: chat_id is empty`

Fill in `chat_id`, or set `TELEGRAM_CHAT_ID`.

`chat not found`

Open your bot in Telegram and press `Start`, then try again.

`PermissionError 10013`

Nuke is blocked from network access. Use `delivery_mode: "auto"` or `delivery_mode: "queue"`.

The message is queued but does not arrive

Check that `telegram_queue_bridge.py` is running and that `telegram_settings.json` contains valid Telegram credentials.

## License

Add your preferred license before publishing.

## Support

If this tool saves you time, and you feel like supporting it:

1-2 coffees are more than enough.

[Click to Buy me a Coffee](https://buymeacoffee.com/natlrazfx)
