from __future__ import annotations

import getpass
import json
import os
import shutil
import ssl
import socket
import subprocess
import uuid
import time
import ctypes
from datetime import datetime
from html import escape
from urllib import error, parse, request

import nuke


PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PLUGIN_DIR, "telegram_settings.json")
QUEUE_DIR = os.path.join(PLUGIN_DIR, "queue")
BRIDGE_SCRIPT_PATH = os.path.join(PLUGIN_DIR, "telegram_queue_bridge.py")
ENV_BOT_TOKEN_KEY = "TELEGRAM_BOT_TOKEN"
ENV_CHAT_ID_KEY = "TELEGRAM_CHAT_ID"
_RENDER_STATE = {}
_REGISTERED = False
_BRIDGE_STARTED = False


def _tprint(message):
    nuke.tprint("[Telegram Notify] {0}".format(message))


def _load_settings():
    settings = {
        "enabled": True,
        "bot_token": "",
        "chat_id": "",
        "api_base": "https://api.telegram.org",
        "timeout_seconds": 10,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "verify_ssl": True,
        "delivery_mode": "auto",
        "queue_dir": QUEUE_DIR,
        "auto_start_bridge": True,
        "bridge_python": "",
        "notify_on_render_complete": True,
        "test_message_prefix": "Nuke Telegram notifier test",
    }

    if not os.path.exists(CONFIG_PATH):
        return settings

    try:
        with open(CONFIG_PATH, "r") as handle:
            file_settings = json.load(handle)
    except Exception as exc:
        _tprint("Failed to read config: {0}".format(exc))
        return settings

    if isinstance(file_settings, dict):
        settings.update(file_settings)

    env_bot_token = os.getenv(ENV_BOT_TOKEN_KEY, "").strip()
    env_chat_id = os.getenv(ENV_CHAT_ID_KEY, "").strip()
    if env_bot_token:
        settings["bot_token"] = env_bot_token
    if env_chat_id:
        settings["chat_id"] = env_chat_id

    return settings


def _validate_settings(settings):
    delivery_mode = settings.get("delivery_mode", "auto")
    if delivery_mode not in ("auto", "direct", "queue"):
        return False, "delivery_mode must be auto, direct, or queue"
    if not settings.get("enabled", True):
        return False, "Notifier is disabled in telegram_settings.json"
    if not settings.get("bot_token"):
        return False, "bot_token is empty"
    if not settings.get("chat_id"):
        return False, "chat_id is empty"
    return True, ""


def _queue_dir(settings):
    queue_dir = settings.get("queue_dir") or QUEUE_DIR
    return os.path.abspath(os.path.expanduser(queue_dir))


def _bridge_lock_path(settings):
    return os.path.join(_queue_dir(settings), "bridge.lock")


def _bridge_is_running(settings):
    lock_path = _bridge_lock_path(settings)
    if not os.path.exists(lock_path):
        return False

    try:
        with open(lock_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        pid = int(data.get("pid", 0))
    except Exception:
        return False

    if pid <= 0:
        return False

    return _is_process_running(pid)


def _is_process_running(pid):
    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    synchronize = 0x00100000
    process = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
    if not process:
        return False

    try:
        wait_result = ctypes.windll.kernel32.WaitForSingleObject(process, 0)
        return wait_result == 0x00000102
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


def _resolve_bridge_python(settings):
    configured = str(settings.get("bridge_python", "")).strip()
    if configured:
        return configured

    for candidate in ("pyw", "py", "pythonw", "python"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return ""


def _start_bridge_if_needed():
    global _BRIDGE_STARTED

    if _BRIDGE_STARTED:
        return

    settings = _load_settings()
    if not settings.get("auto_start_bridge", True):
        return

    if _bridge_is_running(settings):
        _BRIDGE_STARTED = True
        return

    python_cmd = _resolve_bridge_python(settings)
    if not python_cmd:
        _tprint("Bridge autostart skipped: no Python launcher found.")
        return

    command = [python_cmd]
    exe_name = os.path.basename(python_cmd).lower()
    if exe_name in ("py", "py.exe", "pyw", "pyw.exe"):
        command.append("-3")
    command.append(BRIDGE_SCRIPT_PATH)

    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )

    try:
        subprocess.Popen(
            command,
            cwd=PLUGIN_DIR,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        _BRIDGE_STARTED = True
        _tprint("Started Telegram queue bridge in background.")
    except Exception as exc:
        _tprint("Failed to autostart Telegram queue bridge: {0}".format(exc))


def _ensure_queue_dir(queue_dir):
    if not os.path.isdir(queue_dir):
        os.makedirs(queue_dir)


def _enqueue_message(text, source):
    settings = _load_settings()
    queue_dir = _queue_dir(settings)
    _ensure_queue_dir(queue_dir)
    payload = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "text": text,
        "telegram": {
            "api_base": settings.get("api_base", "https://api.telegram.org"),
            "parse_mode": settings.get("parse_mode", "HTML"),
            "disable_web_page_preview": settings.get("disable_web_page_preview", True),
            "timeout_seconds": settings.get("timeout_seconds", 10),
            "verify_ssl": settings.get("verify_ssl", True),
        },
    }
    filename = "{0}_{1}.json".format(
        datetime.now().strftime("%Y%m%d_%H%M%S"),
        payload["id"],
    )
    file_path = os.path.join(queue_dir, filename)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return file_path


def _post_to_telegram(text):
    settings = _load_settings()
    is_valid, reason = _validate_settings(settings)
    if not is_valid:
        raise RuntimeError(reason)

    api_base = settings["api_base"].rstrip("/")
    bot_token = settings["bot_token"].strip()
    url = "{0}/bot{1}/sendMessage".format(api_base, bot_token)
    payload = {
        "chat_id": str(settings["chat_id"]).strip(),
        "text": text,
        "parse_mode": settings.get("parse_mode", "HTML"),
        "disable_web_page_preview": settings.get("disable_web_page_preview", True),
    }
    data = parse.urlencode(payload).encode("utf-8")
    timeout = float(settings.get("timeout_seconds", 10))
    req = request.Request(url, data=data)
    verify_ssl = bool(settings.get("verify_ssl", True))
    context = None
    if not verify_ssl:
        context = ssl._create_unverified_context()

    try:
        with request.urlopen(req, timeout=timeout, context=context) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        # Nuke on Windows can fail SSL verification even when the URL is reachable.
        if verify_ssl and isinstance(reason, ssl.SSLError):
            _tprint("SSL verification failed. Retrying Telegram request without SSL verification.")
            insecure_context = ssl._create_unverified_context()
            try:
                with request.urlopen(req, timeout=timeout, context=insecure_context) as response:
                    body = response.read().decode("utf-8", errors="replace")
            except error.HTTPError as retry_exc:
                retry_body = retry_exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    "Telegram API HTTP {0} after SSL retry: {1}".format(
                        retry_exc.code, retry_body
                    )
                )
            except error.URLError as retry_exc:
                retry_reason = getattr(retry_exc, "reason", retry_exc)
                raise RuntimeError(
                    "Telegram connection failed after SSL retry: {0!r}".format(retry_reason)
                )
        else:
            raise RuntimeError("Telegram connection failed: {0!r}".format(reason))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Telegram API HTTP {0}: {1}".format(exc.code, body))

    try:
        parsed = json.loads(body)
    except ValueError:
        raise RuntimeError("Telegram API returned invalid JSON: {0}".format(body))

    if not parsed.get("ok"):
        raise RuntimeError("Telegram API error: {0}".format(body))

    return parsed


def _deliver_message(text, source):
    settings = _load_settings()
    delivery_mode = settings.get("delivery_mode", "auto")

    if delivery_mode == "queue":
        queue_path = _enqueue_message(text, source)
        _tprint("Notification queued: {0}".format(queue_path))
        return {"ok": True, "queued": True, "queue_path": queue_path}

    try:
        return _post_to_telegram(text)
    except RuntimeError as exc:
        if delivery_mode == "direct":
            raise

        if "PermissionError(13" in str(exc) or "10013" in str(exc):
            queue_path = _enqueue_message(text, source)
            _tprint(
                "Direct Telegram access is blocked. Notification queued instead: {0}".format(
                    queue_path
                )
            )
            return {"ok": True, "queued": True, "queue_path": queue_path}
        raise


def _root_script_name():
    script_path = nuke.root().name() or ""
    if not script_path or script_path == "Root":
        return "Unsaved Script"
    return os.path.basename(script_path)


def _render_range_for(node):
    first_frame = int(nuke.root()["first_frame"].value())
    last_frame = int(nuke.root()["last_frame"].value())

    if "use_limit" in node.knobs() and node["use_limit"].value():
        first_frame = int(node["first"].value())
        last_frame = int(node["last"].value())

    return first_frame, last_frame


def _build_render_message(node, render_state):
    first_frame, last_frame = render_state["frame_range"]
    script_name = _root_script_name()
    output_path = ""
    if "file" in node.knobs():
        output_path = node["file"].evaluate()

    elapsed_seconds = max(0.0, time.time() - render_state["started_at"])
    elapsed_text = "{0:.1f}s".format(elapsed_seconds)
    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "<b>Nuke render finished</b>",
        "Script: <code>{0}</code>".format(escape(script_name)),
        "Write node: <code>{0}</code>".format(escape(node.fullName())),
        "Frames: <code>{0}-{1}</code>".format(first_frame, last_frame),
        "Output: <code>{0}</code>".format(escape(output_path or "Not set")),
        "Machine: <code>{0}</code>".format(escape(socket.gethostname())),
        "User: <code>{0}</code>".format(escape(getpass.getuser())),
        "Finished: <code>{0}</code>".format(finished_at),
        "Elapsed: <code>{0}</code>".format(elapsed_text),
    ]
    return "\n".join(lines)


def _build_test_message():
    script_name = _root_script_name()
    settings = _load_settings()
    prefix = settings.get("test_message_prefix", "Nuke Telegram notifier test")
    return "\n".join(
        [
            "<b>{0}</b>".format(escape(prefix)),
            "Script: <code>{0}</code>".format(escape(script_name)),
            "Machine: <code>{0}</code>".format(escape(socket.gethostname())),
            "User: <code>{0}</code>".format(escape(getpass.getuser())),
            "Time: <code>{0}</code>".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ]
    )


def _before_render():
    node = nuke.thisNode()
    _RENDER_STATE[node.fullName()] = {
        "started_at": time.time(),
        "frame_range": _render_range_for(node),
    }


def _after_render():
    settings = _load_settings()
    if not settings.get("notify_on_render_complete", True):
        return

    node = nuke.thisNode()
    render_state = _RENDER_STATE.pop(
        node.fullName(),
        {
            "started_at": time.time(),
            "frame_range": _render_range_for(node),
        },
    )

    try:
        message = _build_render_message(node, render_state)
        _deliver_message(message, "render_complete")
        _tprint("Notification sent for node {0}".format(node.fullName()))
    except Exception as exc:
        _tprint("Notification failed after render: {0}".format(exc))


def register_callbacks():
    global _REGISTERED

    if _REGISTERED:
        return

    nuke.addBeforeRender(_before_render, nodeClass="Write")
    nuke.addAfterRender(_after_render, nodeClass="Write")
    _REGISTERED = True
    _start_bridge_if_needed()
    _tprint("Callbacks registered")


def send_test_message():
    try:
        result = _deliver_message(_build_test_message(), "manual_test")
    except Exception as exc:
        nuke.message(
            "Telegram test failed.\n\n{0}\n\nConfig: {1}\nEnv override keys: {2}, {3}".format(
                exc,
                CONFIG_PATH,
                ENV_BOT_TOKEN_KEY,
                ENV_CHAT_ID_KEY,
            )
        )
        return

    if result.get("queued"):
        nuke.message(
            "Telegram direct access is blocked in Nuke, so the test was queued locally.\n\nQueue file: {0}\n\nRun telegram_queue_bridge.py outside Nuke to send queued notifications.".format(
                result.get("queue_path", _queue_dir(_load_settings()))
            )
        )
    else:
        nuke.message("Telegram test message sent successfully.")


def show_config_path():
    nuke.message(
        "Telegram config file:\n{0}\n\nYou can set bot_token/chat_id here or via env vars {1} and {2}. Restart Nuke after changes.".format(
            CONFIG_PATH,
            ENV_BOT_TOKEN_KEY,
            ENV_CHAT_ID_KEY,
        )
    )
