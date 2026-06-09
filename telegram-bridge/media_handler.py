from loguru import logger
from pathlib import Path
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from config.config import media_path


MEDIA_DIR = Path(media_path)


def ensure_media_dir():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return str(MEDIA_DIR)


async def handler(client, msg, jid):
    if msg.media:
        logger.debug('Processing media message: telegram_message_id={} media_type={}', msg.id, type(msg.media).__name__)
        download_dir = ensure_media_dir()

        if isinstance(msg.media, MessageMediaPhoto):
            logger.info('Downloading Telegram photo: message_id={}', msg.id)
            path = await client.download_media(msg, download_dir)
            logger.info('Photo downloaded: message_id={} path={}', msg.id, path)
            return {
                'jid': jid,
                'message': {
                    'image': {
                        'url': path,
                    },
                    'caption': msg.message or '',
                },
            }

        if isinstance(msg.media, MessageMediaDocument):
            doc = msg.document

            if any(isinstance(attr, DocumentAttributeAudio) for attr in doc.attributes):
                logger.info('Downloading Telegram audio: message_id={}', msg.id)
                path = await client.download_media(msg, download_dir)
                logger.info('Audio downloaded: message_id={} path={}', msg.id, path)
                return {
                    'jid': jid,
                    'message': {
                        'audio': {
                            'url': path,
                        },
                        'mimetype': 'audio/mp4',
                    },
                }

            if any(isinstance(attr, DocumentAttributeVideo) for attr in doc.attributes):
                logger.info('Downloading Telegram video: message_id={}', msg.id)
                path = await client.download_media(msg, download_dir)
                logger.info('Video downloaded: message_id={} path={}', msg.id, path)
                return {
                    'jid': jid,
                    'message': {
                        'video': {
                            'url': path,
                        },
                        'caption': msg.message or '',
                        'pvt': False,
                    },
                }

            logger.warning('Unsupported Telegram document format: message_id={}', msg.id)
            return {
                'jid': jid,
                'message': {
                    'text': 'Unsupported Document Format',
                },
            }

        logger.warning('Unsupported Telegram media format: message_id={} media_type={}', msg.id, type(msg.media).__name__)
        return {
            'jid': jid,
            'message': {
                'text': 'Unsupported Media Format',
            },
        }

    if msg.message:
        logger.debug('Processing text message: message_id={} length={}', msg.id, len(msg.message))
        return {
            'jid': jid,
            'message': {
                'text': msg.message,
            },
        }

    logger.warning('Unsupported Telegram message content: message_id={}', msg.id)
    return {
        'jid': jid,
        'message': {
            'text': 'Received a message with an unsupported content',
        },
    }
