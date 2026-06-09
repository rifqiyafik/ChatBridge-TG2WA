import sys
from pathlib import Path

from loguru import logger
from telethon import TelegramClient, events

from config.config import api_id, api_hash, telegram_chat, jid, whatsapp_api_url
from whatsapp_sender import send_message

LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stderr, level='INFO', format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}')
logger.add(LOG_DIR / 'bridge.log', rotation='5 MB', retention='7 days', level='DEBUG', encoding='utf-8')

client = TelegramClient('Test Session', api_id, api_hash)


def mask_jid(value):
    if not value:
        return '<empty>'
    if isinstance(value, str) and '@' in value:
        prefix, suffix = value.split('@', 1)
        return f'{prefix[:4]}***@{suffix}'
    return str(value)


def normalize_telegram_chats(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


async def on_message(event):
    msg = event.message
    logger.info('Telegram message received: id={} chat_id={} has_media={} text_preview={!r}', msg.id, event.chat_id, bool(msg.media), (msg.message or '')[:80])

    try:
        result = await send_message(client, msg, jid)
        logger.success('Message forwarded to WhatsApp: telegram_message_id={} result={}', msg.id, result)
    except Exception:
        logger.exception('Failed to forward Telegram message: id={}', msg.id)


def main():
    telegram_sources = normalize_telegram_chats(telegram_chat)

    logger.info('Starting Telegram to WhatsApp bridge')
    logger.info('Telegram source chat config: {}', telegram_sources)
    logger.info('WhatsApp target JID: {}', mask_jid(jid))
    logger.info('WhatsApp API endpoint: {}', whatsapp_api_url)

    if not jid:
        logger.warning('WhatsApp JID is empty. Fill jid in config/config.py before expecting messages to be delivered.')

    logger.info('Connecting to Telegram...')
    client.start()
    logger.success('Telegram client connected')

    source_entities = []
    for source in telegram_sources:
        try:
            source_entity = client.loop.run_until_complete(client.get_entity(source))
        except Exception:
            logger.exception('Cannot resolve telegram_chat={!r}. Run: python scripts/list_telegram_chats.py, then use the numeric ID in config/config.py', source)
            raise SystemExit(1)

        logger.success(
            'Telegram source resolved: config={} id={} title={!r}',
            source,
            source_entity.id,
            getattr(source_entity, 'title', None) or getattr(source_entity, 'first_name', None),
        )
        source_entities.append(source_entity)

    client.add_event_handler(on_message, events.NewMessage(chats=source_entities))

    logger.success('Waiting for new messages from {} Telegram source(s)...', len(source_entities))
    client.run_until_disconnected()


if __name__ == '__main__':
    main()
