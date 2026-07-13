import sys
import time
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

SESSION_DIR = Path('sessions')
SESSION_DIR.mkdir(exist_ok=True)
SESSION_PATH = str(SESSION_DIR / 'Test Session')
SESSION_FILE = SESSION_DIR / 'Test Session.session'


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


def wait_for_authorized_session():
    """Wait until the session file is created and authorized by the admin bot.
    
    IMPORTANT: We do NOT keep the client object or connection open when unauthorized
    to avoid database locks (sqlite3.OperationalError: database is locked) and
    prevent conflicts with admin_bot's OTP /tg_login process.
    """
    global client
    logged_once = False
    
    while True:
        # Check if the session file exists on disk
        if not SESSION_FILE.exists() or SESSION_FILE.stat().st_size == 0:
            if not logged_once:
                logger.warning(
                    'Session file {} not found. '
                    'Please log in via the admin bot using /tg_login. '
                    'Checking again every 30 seconds...',
                    SESSION_FILE.name,
                )
                logged_once = True
            time.sleep(30)
            continue
            
        logger.info('Session file found. Checking authorization status...')
        temp_client = TelegramClient(SESSION_PATH, api_id, api_hash)
        
        try:
            # Connect only to check authorization status
            temp_client.loop.run_until_complete(temp_client.connect())
            authorized = temp_client.loop.run_until_complete(temp_client.is_user_authorized())
            
            if authorized:
                logger.success('Telegram session is authorized!')
                # Store the client globally
                client = temp_client
                break
            else:
                logger.warning('Session file exists but is NOT authorized yet. Waiting for login to complete...')
        except Exception as e:
            logger.error('Error checking telegram session: {}', e)
        finally:
            # Always ensure the temp client is disconnected to release the SQLite lock!
            try:
                if temp_client.is_connected():
                    coro = temp_client.disconnect()
                    if coro:
                        temp_client.loop.run_until_complete(coro)
            except Exception:
                pass
            del temp_client
            
        time.sleep(30)


def main():
    global client
    telegram_sources = normalize_telegram_chats(telegram_chat)

    logger.info('Starting Telegram to WhatsApp bridge')
    logger.info('Telegram source chat config: {}', telegram_sources)
    logger.info('WhatsApp target JID: {}', mask_jid(jid))
    logger.info('WhatsApp API endpoint: {}', whatsapp_api_url)

    if not jid:
        logger.warning('WhatsApp JID is empty. Fill jid in config/config.py before expecting messages to be delivered.')

    # Step 1: Wait until the session file is created and fully authorized via admin_bot
    wait_for_authorized_session()

    # Step 2: Now that we have a verified authorized session, start the client
    logger.info('Connecting to Telegram...')
    client.loop.run_until_complete(client.connect())
    logger.success('Telegram client connected and authorized')

    # Fetch 'me' first to cache the logged-in user's own identity (so their ID is resolvable)
    try:
        me = client.loop.run_until_complete(client.get_me())
        logger.info('Logged in as user: {} (ID: {})', getattr(me, 'username', 'no_username'), me.id)
    except Exception as e:
        logger.warning('Failed to retrieve user info: {}', e)

    source_entities = []
    for source in telegram_sources:
        try:
            source_entity = client.loop.run_until_complete(client.get_entity(source))
            source_entities.append(source_entity)
            logger.success(
                'Telegram source resolved: config={} id={} title={!r}',
                source,
                source_entity.id,
                getattr(source_entity, 'title', None) or getattr(source_entity, 'first_name', None),
            )
        except ValueError:
            logger.warning('Entity for source {} not found in cache. Fetching dialogs to populate cache...', source)
            try:
                # Fetch dialogs to populate Telethon's internal entity cache
                client.loop.run_until_complete(client.get_dialogs(limit=100))
                source_entity = client.loop.run_until_complete(client.get_entity(source))
                source_entities.append(source_entity)
                logger.success(
                    'Telegram source resolved after fetching dialogs: config={} id={} title={!r}',
                    source,
                    source_entity.id,
                    getattr(source_entity, 'title', None) or getattr(source_entity, 'first_name', None),
                )
            except Exception:
                logger.error('Cannot resolve telegram_chat={!r} even after fetching dialogs. Skipping this source.', source)
        except Exception:
            logger.error('Cannot resolve telegram_chat={!r}. Skipping this source.', source)

    if not source_entities:
        logger.error('No Telegram source chats could be resolved! The bridge has nothing to listen to. Exiting.')
        raise SystemExit(1)

    client.add_event_handler(on_message, events.NewMessage(chats=source_entities))

    logger.success('Waiting for new messages from {} Telegram source(s)...', len(source_entities))
    client.run_until_disconnected()


client = None

if __name__ == '__main__':
    main()

