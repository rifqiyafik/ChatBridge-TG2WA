import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.py"
STATE_PATH = PROJECT_ROOT / "data" / "admin_state.json"


def load_runtime_config():
    spec = importlib.util.spec_from_file_location("tg2wa_runtime_config", CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load config from {CONFIG_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_chat_id(value):
    text = str(value).strip()
    if text.startswith("-"):
        number = text[1:]
        sign = -1
    else:
        number = text
        sign = 1

    if number.isdigit():
        return sign * int(number)

    return text


def normalize_chat_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return [normalize_chat_id(item) for item in value]
    return [normalize_chat_id(value)]


def load_state():
    if not STATE_PATH.exists():
        return {
            "telegram_sources": [],
            "whatsapp_target": None,
            "approved_admin_user_ids": [],
            "admin_requests": {},
        }

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.setdefault("telegram_sources", [])
    state.setdefault("whatsapp_target", None)
    state.setdefault("approved_admin_user_ids", [])
    state.setdefault("admin_requests", {})
    return state


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_state_telegram_sources(sources):
    state = load_state()
    state["telegram_sources"] = sources
    save_state(state)


def set_state_whatsapp_target(jid, name=None):
    state = load_state()
    state["whatsapp_target"] = {
        "jid": jid,
        "name": name,
    }
    save_state(state)


def add_admin_request(user_id, name, username, reason):
    state = load_state()
    state["admin_requests"][str(user_id)] = {
        "id": int(user_id),
        "name": name,
        "username": username,
        "reason": reason,
    }
    save_state(state)


def pop_admin_request(user_id):
    state = load_state()
    request = state["admin_requests"].pop(str(user_id), None)
    save_state(state)
    return request


def approve_admin_user(user_id):
    state = load_state()
    request = state["admin_requests"].pop(str(user_id), None)
    if request is None:
        save_state(state)
        return False

    admins = {int(item) for item in state.get("approved_admin_user_ids", [])}
    admins.add(int(user_id))
    state["approved_admin_user_ids"] = sorted(admins)
    save_state(state)
    return True


def reject_admin_request(user_id):
    return pop_admin_request(user_id)


def write_runtime_config(*, telegram_chats=None, jid=None):
    current = load_runtime_config()

    next_telegram_chats = (
        normalize_chat_list(telegram_chats)
        if telegram_chats is not None
        else normalize_chat_list(getattr(current, "telegram_chat", getattr(current, "telegram_chats", [])))
    )
    next_jid = jid if jid is not None else getattr(current, "jid", "")

    api_id = getattr(current, "api_id", "")
    api_hash = getattr(current, "api_hash", "")
    whatsapp_api_url = getattr(current, "whatsapp_api_url", "http://localhost:3000/send-message")
    media_path = getattr(current, "media_path", "")

    content = f'''from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

# Your Telegram API ID
api_id = {api_id!r}
# Your Telegram API hash
api_hash = {api_hash!r}
# The usernames or IDs of the Telegram chats/groups/channels you want to listen from.
telegram_chats = {next_telegram_chats!r}

# Backward-compatible alias used by older bridge code.
telegram_chat = telegram_chats
# The WhatsApp chat/group ID you want to send the message to. ex: 123456789@s.whatsapp.net
jid = {next_jid!r}
whatsapp_api_url = {whatsapp_api_url!r}
# This is where the downloaded Telegram media will go.
media_path = {media_path!r}
'''

    CONFIG_PATH.write_text(content, encoding="utf-8")
    return load_runtime_config()
