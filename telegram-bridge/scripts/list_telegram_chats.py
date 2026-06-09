import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger
from telethon import TelegramClient

from config.config import api_id, api_hash

client = TelegramClient(str(PROJECT_ROOT / 'Test Session'), api_id, api_hash)


async def main():
    logger.info('Fetching Telegram dialogs from the current account...')
    logger.info('Use the id value for telegram_chat in config/config.py')
    print('')
    print('{:<10} {:<18} NAME'.format('TYPE', 'ID'))
    print('-' * 80)

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if getattr(entity, 'broadcast', False):
            kind = 'channel'
        elif getattr(entity, 'megagroup', False):
            kind = 'group'
        elif dialog.is_group:
            kind = 'group'
        elif dialog.is_user:
            kind = 'user'
        else:
            kind = 'chat'

        print('{:<10} {:<18} {}'.format(kind, dialog.id, dialog.name))


with client:
    client.loop.run_until_complete(main())
