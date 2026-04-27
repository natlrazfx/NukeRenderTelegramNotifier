# Nuke Render Telegram Notifier

Nuke Render Telegram Notifier is a small Nuke tool that sends a Telegram message when a `Write` render finishes.

It is useful when you start a render, leave Nuke alone, and want to know when it is done without checking the machine every few minutes.

## What it does

- Adds a **Telegram Notify** menu in Nuke
- Sends a test message to check your Telegram setup
- Sends a notification after a `Write` node finishes rendering
- Shows the script name, `Write` node, frame range, output path, machine, user, finish time, and elapsed time
- Works without installing `requests` or any extra Python package
- Can use `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables
- Can still work if `Nuke.exe` is blocked from the internet

## Why

Some renders take long enough that constantly checking Nuke becomes annoying.

The simple version is: Nuke sends a message to Telegram when the render is done.

The slightly less simple version is: if your firewall blocks Nuke from accessing the internet, the tool writes a local queue file and a separate Python bridge sends the Telegram message instead.

This means you can keep Nuke blocked and still get notifications.

## Requirements

- Foundry Nuke
- A Telegram bot token from `@BotFather`
- A Telegram chat ID
- Python available outside Nuke, only needed for the queue bridge fallback

No extra pip installs are required.

## Installation

Copy the folder somewhere Nuke can load it from, for example:

```text
D:/Scripts/nuke/NukeRenderTelegramNotifier
```

Add this to your `.nuke/init.py`:

```python
import nuke

nuke.pluginAddPath(r"D:/Scripts/nuke/NukeRenderTelegramNotifier")
```

Copy:

```text
telegram_settings.example.json
```

to:

```text
telegram_settings.json
```

Then fill in your private Telegram values:

```json
{
  "bot_token": "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE",
  "chat_id": "PASTE_YOUR_CHAT_ID_HERE"
}
```

Restart Nuke.

You should see:

```text
Nuke -> Telegram Notify
```

## Usage

First run:

```text
Nuke -> Telegram Notify -> Send Test Message
```

If the test message arrives, render any `Write` node normally.

When the render finishes, the Telegram message is sent automatically.

## How to get chat_id

For personal messages:

1. Open your bot in Telegram.
2. Press `Start`.
3. Open this URL in a browser:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

4. Look for:

```json
"chat": {
  "id": 123456789
}
```

That number is your `chat_id`.

For groups, add the bot to the group, send a message in the group, then check `getUpdates`. Group chat IDs are often negative.

## Settings

`bot_token`

Telegram bot token from `@BotFather`.

`chat_id`

The chat where the bot should send messages.

`delivery_mode`

Controls how messages are sent.

- `auto`: try direct sending from Nuke, then fall back to the queue
- `direct`: only send directly from Nuke
- `queue`: always use the local queue bridge

`auto_start_bridge`

Starts `telegram_queue_bridge.py` automatically when Nuke starts.

`queue_dir`

Optional custom queue folder. Leave it empty to use the local `queue` folder.

`bridge_python`

Optional Python executable for the bridge. Leave it empty to auto-detect Python.

## Blocked Nuke Network

If Nuke is blocked from the internet, you may see:

```text
PermissionError(13, 'An attempt was made to access a socket in a way forbidden by its access permissions', None, 10013, None)
```

Keep:

```json
"delivery_mode": "auto"
```

or use:

```json
"delivery_mode": "queue"
```

The plugin will write notifications to the local queue, and `telegram_queue_bridge.py` will send them from a normal Python process outside Nuke.

The bridge starts automatically by default. You can also run it manually:

```powershell
py telegram_queue_bridge.py
```

## Environment Variables

You can keep credentials outside the JSON file:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Environment variables override `telegram_settings.json`.

## Files

- `init.py`: loads the plugin callbacks
- `menu.py`: adds the Nuke menu
- `telegram_render_notifier.py`: Nuke-side render callback and queue logic
- `telegram_queue_bridge.py`: external Telegram sender for blocked Nuke setups
- `telegram_settings.example.json`: safe config template

## Security

Do not commit:

- `telegram_settings.json`
- `queue/`
- screenshots or logs that show your bot token

If a bot token was ever posted publicly, rotate it in `@BotFather`.

## Troubleshooting

`bot_token is empty`

Create `telegram_settings.json` from the example file and fill in `bot_token`.

`chat_id is empty`

Fill in `chat_id`, or set `TELEGRAM_CHAT_ID`.

`chat not found`

Open your bot in Telegram and press `Start`.

The test message is queued but does not arrive

Check that `telegram_queue_bridge.py` is running and that `telegram_settings.json` contains valid credentials.

## Don@tes

**If any of this turns out to be useful for you - I'm glad.  
And if you feel like supporting it:  
☕ 1-2 coffees are more than enough ☺️**

[Click to Buy me a Coffee](https://buymeacoffee.com/natlrazfx)
[Subscribe me on Substack](https://substack.com/@natalia289425)
