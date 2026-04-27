from __future__ import annotations

import json
import os
import ssl
import time
import ctypes
from pathlib import Path
from urllib import error, parse, request


PLUGIN_DIR = Path(__file__).resolve().parent
QUEUE_DIR = PLUGIN_DIR / "queue"
SENT_DIR = QUEUE_DIR / "sent"
FAILED_DIR = QUEUE_DIR / "failed"
LOCK_PATH = QUEUE_DIR / "bridge.lock"
CONFIG_PATH = PLUGIN_DIR / "telegram_settings.json"
POLL_SECONDS = 2.0


def load_payload(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_current_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_config_fallbacks(payload):
    telegram = payload.setdefault("telegram", {})
    config = load_current_config()
    config_token = str(config.get("bot_token", "")).strip()
    config_chat_id = str(config.get("chat_id", "")).strip()

    if config_token and not config_token.startswith("PASTE_YOUR_"):
        telegram["bot_token"] = config_token

    if config_chat_id and not config_chat_id.startswith("PASTE_YOUR_"):
        telegram["chat_id"] = config_chat_id

    return payload


def send_to_telegram(payload):
    payload = apply_config_fallbacks(payload)
    telegram = payload["telegram"]
    url = "{0}/bot{1}/sendMessage".format(
        str(telegram.get("api_base", "https://api.telegram.org")).rstrip("/"),
        telegram["bot_token"].strip(),
    )
    body = parse.urlencode(
        {
            "chat_id": str(telegram["chat_id"]).strip(),
            "text": payload["text"],
            "parse_mode": telegram.get("parse_mode", "HTML"),
            "disable_web_page_preview": telegram.get("disable_web_page_preview", True),
        }
    ).encode("utf-8")

    context = None
    if not telegram.get("verify_ssl", True):
        context = ssl._create_unverified_context()

    req = request.Request(url, data=body)
    with request.urlopen(
        req,
        timeout=float(telegram.get("timeout_seconds", 10)),
        context=context,
    ) as response:
        raw = response.read().decode("utf-8", errors="replace")

    parsed = json.loads(raw)
    if not parsed.get("ok"):
        raise RuntimeError(raw)


def ensure_dirs():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def write_lock():
    LOCK_PATH.write_text(
        json.dumps({"pid": os.getpid(), "created_at": time.time()}, indent=2),
        encoding="utf-8",
    )


def remove_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def already_running():
    if not LOCK_PATH.exists():
        return False

    try:
        data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
    except Exception:
        return False

    if pid <= 0:
        return False

    return is_process_running(pid)


def is_process_running(pid: int):
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


def process_once():
    ensure_dirs()
    queue_files = sorted(
        path for path in QUEUE_DIR.glob("*.json") if path.is_file()
    )
    for path in queue_files:
        try:
            payload = load_payload(path)
            send_to_telegram(payload)
            target = SENT_DIR / path.name
            path.replace(target)
            print("Sent:", target)
        except Exception as exc:
            target = FAILED_DIR / path.name
            path.replace(target)
            print("Failed:", target, exc)


def main():
    ensure_dirs()
    if already_running():
        print("Bridge already running:", LOCK_PATH)
        return

    write_lock()
    print("Watching queue:", QUEUE_DIR)
    try:
        while True:
            process_once()
            time.sleep(POLL_SECONDS)
    finally:
        remove_lock()


if __name__ == "__main__":
    main()
