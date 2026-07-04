from pathlib import Path
from urllib.parse import urljoin

import requests
from telethon import TelegramClient

from config.config import api_id, api_hash
from config_store import PROJECT_ROOT


WORKSPACE_ROOT = PROJECT_ROOT.parent
WHATSAPP_ROOT = WORKSPACE_ROOT / "whatsapp-api"
TELEGRAM_SESSION_NAME = str(PROJECT_ROOT / "Test Session")
TELEGRAM_SESSION_FILES = [
    PROJECT_ROOT / "Test Session.session",
    PROJECT_ROOT / "Test Session.session-journal",
]
WHATSAPP_AUTH_DIR = WHATSAPP_ROOT / "auth_info"
REQUEST_TIMEOUT_SECONDS = 30


def ensure_inside_workspace(path):
    resolved = Path(path).resolve()
    root = WORKSPACE_ROOT.resolve()
    if root not in (resolved, *resolved.parents):
        raise ValueError(f"Refusing to touch path outside workspace: {resolved}")
    return resolved


def delete_path(path):
    resolved = ensure_inside_workspace(path)
    if not resolved.exists():
        return False
    if resolved.is_dir():
        for child in resolved.iterdir():
            delete_path(child)
        try:
            resolved.rmdir()
        except OSError:
            pass
        return True
    try:
        resolved.unlink()
    except OSError:
        pass
    return True


def make_user_client():
    return TelegramClient(TELEGRAM_SESSION_NAME, api_id, api_hash)


async def is_telegram_authorized():
    client = make_user_client()
    await client.connect()
    try:
        return await client.is_user_authorized()
    finally:
        await client.disconnect()


async def list_telegram_dialogs(limit=80):
    client = make_user_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram user account is not logged in.")

        dialogs = []
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            if getattr(entity, "broadcast", False):
                kind = "channel"
            elif getattr(entity, "megagroup", False) or dialog.is_group:
                kind = "group"
            elif dialog.is_user:
                kind = "user"
            else:
                kind = "chat"

            dialogs.append({
                "id": dialog.id,
                "name": dialog.name,
                "type": kind,
            })
        return dialogs
    finally:
        await client.disconnect()


async def logout_telegram():
    client = make_user_client()
    await client.connect()
    try:
        if await client.is_user_authorized():
            await client.log_out()
    finally:
        await client.disconnect()

    deleted = []
    for path in TELEGRAM_SESSION_FILES:
        if delete_path(path):
            deleted.append(str(path))
    return deleted


class WhatsAppApi:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/") + "/"

    def _url(self, path):
        return urljoin(self.base_url, path.lstrip("/"))

    def connect_with_phone(self, phone_number):
        response = requests.post(
            self._url("/connect"),
            json={"phoneNumber": phone_number},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return self._json_response(response)

    def connect(self):
        response = requests.post(
            self._url("/connect"),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return self._json_response(response)

    def get_qr(self):
        response = requests.get(self._url("/qr"), timeout=REQUEST_TIMEOUT_SECONDS)
        return self._json_response(response)

    def list_groups(self):
        response = requests.get(self._url("/groups"), timeout=REQUEST_TIMEOUT_SECONDS)
        return self._json_response(response)

    def logout(self):
        response = requests.delete(
            self._url("/logout"),
            params={"deleteSession": "true"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return self._json_response(response)

    def local_reset_session(self):
        return delete_path(WHATSAPP_AUTH_DIR)

    def _json_response(self, response):
        try:
            data = response.json()
        except ValueError:
            data = {"success": False, "message": response.text}

        if response.status_code >= 400:
            message = data.get("message") or f"HTTP {response.status_code}"
            raise RuntimeError(message)

        return data
