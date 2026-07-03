import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Reconfigure stdout to support utf-8 print on Windows if possible
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

from loguru import logger
from telethon import TelegramClient

from config.config import api_id, api_hash

client = TelegramClient(str(PROJECT_ROOT / 'Test Session'), api_id, api_hash)


async def main():
    logger.info('Fetching Telegram dialogs from the current account...')
    logger.info('Use the id value for telegram_chat in config/config.py')
    print('')

    # Ensure tmp directory exists and is ignored
    tmp_dir = PROJECT_ROOT / 'tmp'
    tmp_dir.mkdir(exist_ok=True)
    output_file = tmp_dir / 'telegram_chats.txt'

    header = '{:<10} {:<18} NAME'.format('TYPE', 'ID')
    separator = '-' * 80

    try:
        print(header)
        print(separator)
    except Exception:
        pass

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(header + '\n')
            f.write(separator + '\n')

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

                line = '{:<10} {:<18} {}'.format(kind, dialog.id, dialog.name)
                
                # Safely print to terminal (fallback to ascii-replaced if fails)
                try:
                    print(line)
                except Exception:
                    try:
                        print(line.encode('ascii', errors='replace').decode('ascii'))
                    except Exception:
                        pass
                
                f.write(line + '\n')

        logger.info(f'Results successfully saved to {output_file}')
    except Exception as e:
        logger.error(f'Failed to save results to file: {e}')


with client:
    client.loop.run_until_complete(main())
