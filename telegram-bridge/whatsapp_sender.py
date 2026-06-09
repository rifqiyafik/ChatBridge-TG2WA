import requests as req
from loguru import logger
from time import sleep
from urllib.parse import urlparse, urlunparse

from config.config import whatsapp_api_url
from media_handler import handler

REQUEST_TIMEOUT_SECONDS = 30
RECONNECT_WAIT_SECONDS = 8


def get_connect_url():
    parsed = urlparse(whatsapp_api_url)
    return urlunparse((parsed.scheme, parsed.netloc, '/connect', '', '', ''))


def post_to_whatsapp_api(message_object):
    response = req.post(whatsapp_api_url, json=message_object, timeout=REQUEST_TIMEOUT_SECONDS)
    logger.info('WhatsApp API response: status_code={} body_preview={!r}', response.status_code, response.text[:300])
    return response


def reconnect_whatsapp_api():
    connect_url = get_connect_url()
    logger.warning('WhatsApp API is not connected. Calling reconnect endpoint: {}', connect_url)

    response = req.post(connect_url, timeout=REQUEST_TIMEOUT_SECONDS)
    logger.info('WhatsApp connect response: status_code={} body_preview={!r}', response.status_code, response.text[:300])
    response.raise_for_status()

    logger.info('Waiting {} seconds for WhatsApp API connection to settle', RECONNECT_WAIT_SECONDS)
    sleep(RECONNECT_WAIT_SECONDS)


async def send_message(client, msg, jid):
    message_object = await handler(client, msg, jid)
    message_keys = list(message_object.get('message', {}).keys())

    logger.info('Sending message to WhatsApp API: endpoint={} jid={} message_keys={}', whatsapp_api_url, jid, message_keys)
    response = post_to_whatsapp_api(message_object)

    if response.status_code == 401:
        reconnect_whatsapp_api()
        logger.info('Retrying message send after WhatsApp API reconnect attempt')
        response = post_to_whatsapp_api(message_object)

    response.raise_for_status()
    return response.json()
