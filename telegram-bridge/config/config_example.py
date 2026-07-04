from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

# Your Telegram API ID
api_id = ""
# Your Telegram API hash
api_hash = ""

# The usernames or IDs of the Telegram chats/groups/channels you want to listen from.
telegram_chats = [
    # -1001234567890,
]
telegram_chat = telegram_chats

# The WhatsApp chat/group ID you want to send the message to. ex: 123456789@s.whatsapp.net
jid = ""
whatsapp_api_url = "http://localhost:3000/send-message"

# This is where the downloaded Telegram media will go.
media_path = str(BASE_DIR / "downloads" / "telegram_media")
