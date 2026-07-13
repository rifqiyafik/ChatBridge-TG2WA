import asyncio
import sys
from pathlib import Path

from loguru import logger
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

try:
    from config import bot_config
except ImportError as exc:
    raise SystemExit(
        "Missing config/bot_config.py. Copy config/bot_config_example.py to "
        "config/bot_config.py, then fill bot_token and admin_user_ids."
) from exc

admin_user_ids = getattr(bot_config, "admin_user_ids", [])
bot_token = getattr(bot_config, "bot_token", "")
list_limit = getattr(bot_config, "list_limit", 30)
primary_admin_user_id = getattr(bot_config, "primary_admin_user_id", None)
whatsapp_api_base_url = getattr(bot_config, "whatsapp_api_base_url", "http://localhost:3000")

from admin_services import (
    WhatsAppApi,
    is_telegram_authorized,
    list_telegram_dialogs,
    logout_telegram,
    make_user_client,
)
from config_store import (
    PROJECT_ROOT,
    add_admin_request,
    approve_admin_user,
    load_runtime_config,
    load_state,
    normalize_chat_id,
    normalize_chat_list,
    reject_admin_request,
    set_state_telegram_sources,
    set_state_whatsapp_target,
    write_runtime_config,
)


LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add(LOG_DIR / "admin_bot.log", rotation="5 MB", retention="7 days", level="DEBUG", encoding="utf-8")

SESSIONS_DIR = PROJECT_ROOT / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
ADMIN_SESSION = str(SESSIONS_DIR / "Admin Bot")
bot = TelegramClient(ADMIN_SESSION, load_runtime_config().api_id, load_runtime_config().api_hash)
pending = {}


HELP_TEXT = """📖 **Panduan Penggunaan TG2WA**

Ikuti langkah-langkah berikut secara berurutan untuk mengatur koneksi:

**Langkah 1: Login Telegram**
Gunakan `/tg_login` (atau `/tg_login <nomor_hp>`) untuk login ke akun Telegram bridge.

**Langkah 2: Lihat Daftar Grup Telegram**
Gunakan `/tg_groups` untuk melihat daftar chat/grup/channel di akun Telegram Anda.

**Langkah 3: Daftarkan Sumber Telegram**
Gunakan `/tg_add_source <chat_id> [nama]` untuk mendaftarkan grup mana yang pesannya ingin diteruskan.

**Langkah 4: Login WhatsApp**
Gunakan `/wa_login` untuk login menggunakan metode Scan QR Code. Atau, jika Anda ingin menggunakan Pairing Code (nomor HP), gunakan perintah `/wa_login <nomor_hp>`.

**Langkah 5: Lihat Daftar Grup WhatsApp**
Gunakan `/wa_groups` untuk melihat daftar grup WhatsApp Anda.

**Langkah 6: Tetapkan Target WhatsApp**
Gunakan `/wa_set_group <jid> [nama]` untuk menetapkan grup tujuan pengiriman pesan.

---
**Perintah Tambahan:**
`/status` - Lihat status koneksi dan grup yang aktif
`/cancel` - Batalkan proses login yang sedang berjalan
`/logout_all` - Logout dari Telegram & WhatsApp

**Manajemen Admin:**
`/admins` - Lihat daftar admin dan request pending
`/approve_admin <user_id>` - Terima request admin (hanya admin utama)
`/reject_admin <user_id>` - Tolak request admin (hanya admin utama)
"""


def is_admin(user_id):
    configured = {int(item) for item in admin_user_ids}
    approved = {int(item) for item in load_state().get("approved_admin_user_ids", [])}
    return int(user_id) in configured | approved


def get_primary_admin_user_id():
    if primary_admin_user_id:
        return int(primary_admin_user_id)
    if admin_user_ids:
        return int(admin_user_ids[0])
    return None


def is_primary_admin(user_id):
    primary = get_primary_admin_user_id()
    return primary is not None and int(user_id) == primary


async def reject_non_admin(event, command, parts):
    sender = await event.get_sender()
    user_id = getattr(sender, "id", None)
    if user_id and is_admin(user_id):
        return False

    if command == "/start":
        await handle_admin_request(event, parts, is_start=True)
    else:
        logger.warning("Rejected non-admin bot access: user_id={}", user_id)
        await respond(event, "Access denied. Gunakan /start untuk meminta akses.")
    return True


async def handle_admin_request(event, parts, is_start=False):
    sender = await event.get_sender()
    user_id = sender.id

    if is_admin(user_id):
        await respond(event, "Anda sudah terdaftar sebagai admin.")
        return

    reason = " ".join(parts[1:]).strip()
    display_name = " ".join(part for part in [getattr(sender, "first_name", None), getattr(sender, "last_name", None)] if part)
    username = getattr(sender, "username", None)
    add_admin_request(user_id, display_name, username, reason)

    primary = get_primary_admin_user_id()
    if primary:
        lines = [
            "Admin access request",
            f"- user_id: {user_id}",
            f"- name: {display_name or '-'}",
            f"- username: @{username}" if username else "- username: -",
            f"- reason: {reason or '-'}",
            "",
            f"Approve: /approve_admin {user_id}",
            f"Reject: /reject_admin {user_id}",
        ]
        await bot.send_message(primary, "\n".join(lines))

    if is_start:
        await respond(event, "Akses ditolak. Permintaan akses Anda telah dikirim ke admin utama. Harap menunggu konfirmasi.")
    else:
        await respond(event, "Request admin sudah dikirim ke admin utama.")

async def get_status_text():
    config = load_runtime_config()
    sources = normalize_chat_list(getattr(config, "telegram_chat", []))
    tg_ok = await is_telegram_authorized()
    
    wa_status_icon = "🔴 Terputus"
    wa_groups = []
    try:
        response = WhatsAppApi(whatsapp_api_base_url).list_groups()
        wa_groups = response.get("data") or []
        wa_status_icon = "🟢 Terhubung"
    except Exception as exc:
        pass

    tg_status_icon = "🟢 Terhubung" if tg_ok else "🔴 Terputus"
    
    wa_target_jid = getattr(config, 'jid', '')
    wa_target = mask_jid(wa_target_jid)
    
    state = load_state()
    if wa_target_jid:
        wa_target_name = None
        wa_target_state = state.get("whatsapp_target") or {}
        if str(wa_target_state.get("id")) == str(wa_target_jid) and wa_target_state.get("name"):
            wa_target_name = wa_target_state["name"]
            
        if not wa_target_name and wa_groups:
            for g in wa_groups:
                if str(g.get("id")) == str(wa_target_jid):
                    wa_target_name = g.get("name")
                    break
                    
        if wa_target_name:
            wa_target = wa_target_name
            
    if not wa_target_jid:
        wa_target = "Belum diatur ⚠️"
        
    source_lines = ""
    if sources:
        tg_sources_state = state.get("telegram_sources", [])
        name_map = {str(item.get("id")): item.get("name") for item in tg_sources_state}
        for s in sources:
            name = name_map.get(str(s))
            if not name:
                name = await find_telegram_dialog_name(s) or "-"
            source_lines += f"\n  ▪️ {s} ({name})"
    else:
        source_lines = "\n  ▪️ Belum ada sumber yang didaftarkan ⚠️"

    return (
        "📊 **Status Sistem TG2WA**\n\n"
        "**📱 Telegram Bridge**\n"
        f"Koneksi: {tg_status_icon}\n"
        f"Sumber Pesan:{source_lines}\n\n"
        "**💬 WhatsApp Target**\n"
        f"Koneksi: {wa_status_icon}\n"
        f"Grup Tujuan: `{wa_target}`\n\n"
        "💡 *Ketik /help untuk melihat panduan langkah demi langkah penggunaan bot.*"
    )

def command_parts(text):
    return (text or "").strip().split()


def mask_jid(value):
    if not value:
        return "<empty>"
    if "@" not in value:
        return value[:4] + "***"
    prefix, suffix = value.split("@", 1)
    return f"{prefix[:4]}***@{suffix}"


def format_sources(sources):
    if not sources:
        return "No Telegram source registered."
    lines = ["Telegram sources:"]
    for item in sources:
        lines.append(f"- {item}")
    return "\n".join(lines)


def format_rows(rows, *, title, id_key="id", name_key="name", type_key=None, limit=None):
    if not rows:
        return f"{title}: empty."

    visible = rows[: limit or list_limit]
    lines = [f"{title} ({len(rows)} total, showing {len(visible)}):"]
    for row in visible:
        kind = f" [{row.get(type_key)}]" if type_key and row.get(type_key) else ""
        lines.append(f"- `{row.get(id_key)}`{kind} - {row.get(name_key) or '-'}")

    if len(rows) > len(visible):
        lines.append(f"... {len(rows) - len(visible)} more not shown.")
    return "\n".join(lines)


async def respond(event, text, **kwargs):
    user_id = getattr(event, "sender_id", "unknown")
    if hasattr(event, "get_sender"):
        try:
            sender = await event.get_sender()
            user_id = sender.id if sender else user_id
        except Exception:
            pass
    msg_log = str(text).replace('\n', ' ')
    logger.info(f"Bot response to user_id={user_id}: {msg_log[:150]}{'...' if len(msg_log)>150 else ''}")
    return await event.respond(text, **kwargs)

async def send_long(event, text):
    max_len = 3800
    if len(text) <= max_len:
        await respond(event, text)
        return

    for start in range(0, len(text), max_len):
        await respond(event, text[start:start + max_len])


async def find_telegram_dialog_name(chat_id):
    try:
        dialogs = await list_telegram_dialogs(limit=200)
    except Exception:
        return None

    for dialog in dialogs:
        if str(dialog["id"]) == str(chat_id):
            return dialog.get("name")
    return None


async def handle_pending(event, user_id, text):
    state = pending.get(user_id)
    if not state:
        return False

    if text.startswith("/cancel"):
        client = state.get("client")
        if client:
            await client.disconnect()
        pending.pop(user_id, None)
        await respond(event, "Proses dibatalkan.")
        return True

    if text.startswith("/"):
        return False

    if state["action"] == "tg_confirm_relogin":
        ans = text.strip().lower()
        if ans in ("ya", "y", "yes"):
            await respond(event, "Menghapus sesi Telegram lama...")
            await logout_telegram()
            await start_telegram_login(event, state["phone"])
        else:
            pending.pop(user_id, None)
            await respond(event, "Login Telegram dibatalkan.")
        return True

    if state["action"] == "wa_confirm_relogin":
        ans = text.strip().lower()
        if ans in ("ya", "y", "yes"):
            await respond(event, "Menghapus sesi WhatsApp lama...")
            api = WhatsAppApi(whatsapp_api_base_url)
            try:
                api.logout()
            except Exception:
                pass
            api.local_reset_session()
            pending.pop(user_id, None)
            await start_wa_login(event, state.get("phone"))
        else:
            pending.pop(user_id, None)
            await respond(event, "Login WhatsApp dibatalkan.")
        return True

    if state["action"] == "wa_phone":
        wa_ok = False
        try:
            WhatsAppApi(whatsapp_api_base_url).list_groups()
            wa_ok = True
        except Exception:
            pass
        if wa_ok:
            state["action"] = "wa_confirm_relogin"
            state["phone"] = text.strip()
            await respond(event, "Sesi WhatsApp sudah ada. Apakah Anda ingin melanjutkan login baru dan menghapus sesi lama? (ya/tidak)")
        else:
            pending.pop(user_id, None)
            await start_wa_login(event, text.strip())
        return True

    if state["action"] == "tg_phone":
        tg_ok = await is_telegram_authorized()
        if tg_ok:
            state["action"] = "tg_confirm_relogin"
            state["phone"] = text.strip()
            await respond(event, "Sesi Telegram sudah ada. Apakah Anda ingin melanjutkan login baru dan menghapus sesi lama? (ya/tidak)")
        else:
            await start_telegram_login(event, text.strip())
        return True

    if state["action"] == "tg_code":
        # Extract only digits from the text to allow spaces or prefix text
        code = "".join(c for c in text if c.isdigit())
        client = state["client"]
        try:
            await client.sign_in(
                phone=state["phone"],
                code=code,
                phone_code_hash=state["phone_code_hash"],
            )
            await client.disconnect()
            pending.pop(user_id, None)
            await respond(event, "Telegram bridge login berhasil.")
        except SessionPasswordNeededError:
            state["action"] = "tg_password"
            await respond(event, "Akun memakai 2FA. Kirim password Telegram 2FA.")
        except PhoneCodeInvalidError:
            await respond(event, "❌ Kode yang Anda masukkan salah. Silakan periksa kembali dan kirimkan kode yang benar. (Gunakan /cancel untuk membatalkan)")
        except PhoneCodeExpiredError:
            pending.pop(user_id, None)
            await respond(event, "❌ Kode sudah kedaluwarsa. Silakan ulangi proses login dari awal dengan /tg_login.")
        except Exception as exc:
            logger.exception("Telegram code login failed")
            await respond(event, f"Telegram login gagal: {exc}. Silakan coba lagi atau gunakan /cancel.")
        return True

    if state["action"] == "tg_password":
        client = state["client"]
        try:
            await client.sign_in(password=text.strip())
            await client.disconnect()
            pending.pop(user_id, None)
            await respond(event, "Telegram bridge login berhasil.")
        except Exception as exc:
            logger.exception("Telegram password login failed")
            await respond(event, f"Telegram login gagal: {exc}")
        return True

    return False

async def poll_wa_qr(event, api):
    import io
    import qrcode
    max_retries = 30 # 1 minute
    for _ in range(max_retries):
        await asyncio.sleep(2)
        try:
            data = await asyncio.to_thread(api.get_qr)
            qr_string = (data.get("data") or {}).get("qr")
            if qr_string:
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_string)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                bio = io.BytesIO()
                bio.name = 'qr.png'
                img.save(bio, 'PNG')
                bio.seek(0)
                await respond(event, "Silakan scan QR code berikut menggunakan WhatsApp Anda (Linked devices > Link a device).\n\n⏳ *QR Code ini hanya berlaku selama 40 detik.*\nJika Anda gagal/terlambat scan, abaikan pesan ini dan ketik `/wa_login` kembali.\n\n💡 *Opsi Lain:* Jika Anda kesulitan scan QR, Anda bisa login menggunakan nomor HP (Pairing Code) dengan mengetik:\n`/wa_login <nomor_hp_anda>` (contoh: `/wa_login 6281234567890`)", file=bio)
                
                logger.info("QR Code sent to user for WhatsApp login. Starting connection polling.")
                asyncio.create_task(poll_wa_connection(event, "QR Code"))
                return
        except Exception as exc:
            pass
    logger.warning("Failed to retrieve QR code from WhatsApp server.")
    await respond(event, "❌ Gagal mendapatkan QR Code dari server WhatsApp. Silakan ulangi dengan /wa_login.")

async def poll_wa_connection(event, phone):
    api = WhatsAppApi(whatsapp_api_base_url)
    max_retries = 60
    for _ in range(max_retries):
        await asyncio.sleep(5)
        try:
            await asyncio.to_thread(api.list_groups)
            logger.info(f"WhatsApp login success confirmed for {phone}.")
            await respond(event, f"✅ Login WhatsApp berhasil ({phone})! Sesi telah tersambung.\nGunakan /wa_groups untuk melihat grup.")
            return
        except Exception:
            pass
    logger.warning(f"WhatsApp pairing timeout/expired for {phone}.")
    await respond(event, f"❌ Waktu pairing WhatsApp habis (expired) untuk {phone}. Silakan ulangi dengan /wa_login.")

async def start_wa_login(event, phone=None):
    api = WhatsAppApi(whatsapp_api_base_url)
    try:
        data = await asyncio.to_thread(api.connect_with_phone, phone) if phone else await asyncio.to_thread(api.connect)
    except Exception as exc:
        await respond(event, f"WhatsApp API error: {exc}")
        return
        
    if phone:
        pairing_code = (data.get("data") or {}).get("pairingCode")
        if pairing_code:
            await respond(event, 
                "Pairing code WhatsApp:\n"
                f"`{pairing_code}`\n\n"
                "Masukkan di WhatsApp > Linked devices > Link a device > Link with phone number instead.\n\n"
                "⏳ *Menunggu proses login... (maksimal 5 menit)*"
            )
            asyncio.create_task(poll_wa_connection(event, phone))
        else:
            await respond(event, data.get("message", "WhatsApp connection initiated."))
    else:
        await respond(event, "Meminta QR Code dari server WhatsApp...")
        asyncio.create_task(poll_wa_qr(event, api))



async def start_telegram_login(event, phone):
    sender = await event.get_sender()
    user_id = sender.id

    old_state = pending.pop(user_id, None)
    if old_state and old_state.get("client"):
        await old_state["client"].disconnect()

    client = make_user_client()
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
    except Exception:
        await client.disconnect()
        raise

    pending[user_id] = {
        "action": "tg_code",
        "client": client,
        "phone": phone,
        "phone_code_hash": sent.phone_code_hash,
    }
    await respond(
        event,
        "Kode Telegram sudah dikirim.\n\n"
        "⚠️ **PENTING (KEAMANAN TELEGRAM):**\n"
        "Agar Telegram **tidak memblokir** kode login Anda secara otomatis (karena dideteksi dibagikan dalam chat), "
        "**mohon kirimkan kode tersebut dengan spasi di antara setiap angka**.\n\n"
        "Contoh: jika kode Anda adalah `12345`, balas dengan: `1 2 3 4 5`.\n\n"
        "Gunakan /cancel untuk membatalkan."
    )


@bot.on(events.NewMessage)
async def handle_message(event):
    sender = await event.get_sender()
    user_id = sender.id
    text = event.raw_text.strip()
    
    command_name = text.split()[0].lower() if text else ""
    if command_name.startswith("/"):
        logger.info(f"Command '{command_name}' from user_id={user_id}")
    else:
        logger.debug(f"Message from user_id={user_id}")

    # For pending interactions, we might not have a slash command but we should log the action.
    if user_id in pending and not command_name.startswith("/"):
        action = pending[user_id].get("action", "unknown")
        logger.info(f"Processing pending action '{action}' for user_id={user_id}")

    parts = command_parts(text)
    command = parts[0].split("@", 1)[0].lower() if parts else ""

    if command == "/request":
        await handle_admin_request(event, parts)
        return

    if await reject_non_admin(event, command, parts):
        return

    if await handle_pending(event, user_id, text):
        return

    if not parts:
        return

    try:
        if command == "/start":
            await respond(event, await get_status_text())
            return
            
        if command == "/help":
            await respond(event, HELP_TEXT)
            return

        if command == "/cancel":
            pending.pop(user_id, None)
            await respond(event, "Tidak ada proses aktif.")
            return

        if command == "/status":
            await respond(event, await get_status_text())
            return

        if command == "/admins":
            state = load_state()
            configured = sorted({int(item) for item in admin_user_ids})
            approved = sorted({int(item) for item in state.get("approved_admin_user_ids", [])})
            requests = state.get("admin_requests", {})
            lines = [
                "Admin users",
                f"- primary: {get_primary_admin_user_id()}",
                f"- configured: {configured or '-'}",
                f"- approved: {approved or '-'}",
                "",
                "Pending requests:",
            ]
            if requests:
                for request in requests.values():
                    username = f" @{request.get('username')}" if request.get("username") else ""
                    lines.append(f"- {request.get('id')} - {request.get('name') or '-'}{username}")
            else:
                lines.append("- none")
            await respond(event, "\n".join(lines))
            return

        if command == "/approve_admin":
            if not is_primary_admin(user_id):
                await respond(event, "Hanya admin utama yang dapat approve admin baru.")
                return
            if len(parts) < 2:
                await respond(event, "Format: /approve_admin <user_id>")
                return
            target_id = int(parts[1])
            if not approve_admin_user(target_id):
                await respond(event, f"Tidak ada request pending untuk user_id: {target_id}")
                return
            await respond(event, f"Admin disetujui: {target_id}")
            await bot.send_message(target_id, "Request admin Anda sudah disetujui. Ketik /start untuk melihat status dan menggunakan bot.")
            return

        if command == "/reject_admin":
            if not is_primary_admin(user_id):
                await respond(event, "Hanya admin utama yang dapat reject admin request.")
                return
            if len(parts) < 2:
                await respond(event, "Format: /reject_admin <user_id>")
                return
            target_id = int(parts[1])
            reject_admin_request(target_id)
            await respond(event, f"Request admin ditolak: {target_id}")
            await bot.send_message(target_id, "Request admin Anda ditolak.")
            return

        if command == "/tg_login":
            if len(parts) < 2:
                pending[user_id] = {"action": "tg_phone"}
                await respond(event, "Kirim nomor Telegram akun bridge, contoh: 6281234567890. Gunakan /cancel untuk batal.")
                return

            tg_ok = await is_telegram_authorized()
            if tg_ok:
                pending[user_id] = {"action": "tg_confirm_relogin", "phone": parts[1]}
                await respond(event, "Sesi Telegram sudah ada. Apakah Anda ingin melanjutkan login baru dan menghapus sesi lama? (ya/tidak)")
                return

            await start_telegram_login(event, parts[1])
            return

        if command == "/tg_groups":
            search_query = " ".join(parts[1:]).strip().lower() if len(parts) > 1 else ""
            try:
                rows = await list_telegram_dialogs(limit=200)
                logger.info(f"/tg_groups: Fetched {len(rows)} dialogs from Telegram API")
            except Exception as e:
                logger.error(f"/tg_groups: Error fetching dialogs: {e}")
                if "database is locked" in str(e).lower():
                    await respond(event, "❌ **Sesi Telegram sedang digunakan (Database is locked).**\n\nHal ini terjadi karena script `bridge.py` sedang berjalan. Harap matikan sementara `bridge.py` saat Anda ingin melihat daftar grup Telegram, lalu coba lagi.")
                    return
                rows = []
                
            if search_query:
                search_words = search_query.split()
                rows = [r for r in rows if all(w in (r.get("name") or "").lower() for w in search_words)]
                logger.info(f"/tg_groups: Filtered with words {search_words}, remaining: {len(rows)} dialogs")
                
            await send_long(event, format_rows(rows, title="Telegram dialogs", type_key="type"))
            return

        if command == "/tg_sources":
            config = load_runtime_config()
            await respond(event, format_sources(normalize_chat_list(getattr(config, "telegram_chat", []))))
            return

        if command == "/tg_add_source":
            if len(parts) < 2:
                await respond(event, "Format: /tg_add_source <chat_id> [nama]")
                return
            chat_id = normalize_chat_id(parts[1])
            name = " ".join(parts[2:]).strip() or await find_telegram_dialog_name(chat_id)
            config = load_runtime_config()
            sources = normalize_chat_list(getattr(config, "telegram_chat", []))
            if chat_id not in sources:
                sources.append(chat_id)
            write_runtime_config(telegram_chats=sources)
            
            state = load_state()
            existing_sources = state.get("telegram_sources", [])
            name_map = {str(item.get("id")): item.get("name") for item in existing_sources}
            name_map[str(chat_id)] = name
            set_state_telegram_sources([{"id": item, "name": name_map.get(str(item))} for item in sources])
            
            await respond(event, f"Telegram source ditambahkan: {chat_id}" + (f" - {name}" if name else ""))
            return

        if command == "/tg_remove_source":
            if len(parts) < 2:
                await respond(event, "Format: /tg_remove_source <chat_id>")
                return
            chat_id = normalize_chat_id(parts[1])
            config = load_runtime_config()
            sources = [item for item in normalize_chat_list(getattr(config, "telegram_chat", [])) if item != chat_id]
            write_runtime_config(telegram_chats=sources)
            
            state = load_state()
            existing_sources = state.get("telegram_sources", [])
            name_map = {str(item.get("id")): item.get("name") for item in existing_sources}
            set_state_telegram_sources([{"id": item, "name": name_map.get(str(item))} for item in sources])
            
            await respond(event, f"Telegram source dihapus: {chat_id}")
            return

        if command == "/tg_logout":
            deleted = await logout_telegram()
            await respond(event, "Telegram bridge logout selesai." + (f"\nDeleted: {len(deleted)} file." if deleted else ""))
            return

        if command == "/wa_login":
            wa_ok = False
            try:
                WhatsAppApi(whatsapp_api_base_url).list_groups()
                wa_ok = True
            except Exception:
                pass
            
            phone = parts[1] if len(parts) > 1 else None
            
            if wa_ok:
                pending[user_id] = {"action": "wa_confirm_relogin", "phone": phone}
                await respond(event, "Sesi WhatsApp sudah ada. Apakah Anda ingin melanjutkan login baru dan menghapus sesi lama? (ya/tidak)")
                return

            await start_wa_login(event, phone)
            return

        if command == "/wa_groups":
            search_query = " ".join(parts[1:]).strip().lower() if len(parts) > 1 else ""
            try:
                data = WhatsAppApi(whatsapp_api_base_url).list_groups()
                rows = data.get("data") or []
                logger.info(f"/wa_groups: Fetched {len(rows)} groups from WhatsApp API")
            except Exception as e:
                logger.error(f"/wa_groups: Error fetching WhatsApp groups: {e}")
                rows = []
                
            if search_query:
                search_words = search_query.split()
                rows = [r for r in rows if all(w in (r.get("name") or "").lower() for w in search_words)]
                logger.info(f"/wa_groups: Filtered with words {search_words}, remaining: {len(rows)} groups")
                
            await send_long(event, format_rows(rows, title="WhatsApp groups"))
            return

        if command == "/wa_set_group":
            if len(parts) < 2:
                await respond(event, "Format: /wa_set_group <jid> [nama]")
                return
            jid = parts[1].strip()
            name = " ".join(parts[2:]).strip() or None
            write_runtime_config(jid=jid)
            set_state_whatsapp_target(jid, name)
            await respond(event, f"Target WhatsApp diset: {mask_jid(jid)}" + (f" - {name}" if name else ""))
            return

        if command == "/wa_logout":
            api = WhatsAppApi(whatsapp_api_base_url)
            try:
                api.logout()
                message = "WhatsApp logout via API selesai."
            except Exception as exc:
                message = f"WhatsApp API logout gagal: {exc}"
            deleted = api.local_reset_session()
            await respond(event, message + (f"\nLocal auth_info deleted: {deleted}" if deleted else "\nLocal auth_info not found."))
            return

        if command == "/logout_all":
            deleted_tg = await logout_telegram()
            api = WhatsAppApi(whatsapp_api_base_url)
            try:
                api.logout()
                wa_message = "WhatsApp API logout selesai."
            except Exception as exc:
                wa_message = f"WhatsApp API logout gagal: {exc}"
            deleted_wa = api.local_reset_session()
            await respond(event, 
                "Logout all selesai.\n"
                f"- Telegram session files deleted: {len(deleted_tg)}\n"
                f"- {wa_message}\n"
                f"- WhatsApp local auth_info deleted: {deleted_wa}"
            )
            return

        await respond(event, "Command tidak dikenal. Kirim /help.")

    except Exception as exc:
        logger.exception("Admin bot command failed: command={}", command)
        await respond(event, f"Command gagal: {exc}")


async def main():
    if not bot_token:
        raise SystemExit("bot_token is empty in config/bot_config.py")
    if not admin_user_ids:
        raise SystemExit("admin_user_ids is empty in config/bot_config.py")

    await bot.start(bot_token=bot_token)
    logger.success("TG2WA admin bot is running")
    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
