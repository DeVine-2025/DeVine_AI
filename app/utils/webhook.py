import logging
import datetime
import threading
import requests
from app.configs.settings import settings

logger = logging.getLogger(__name__)


def discord_send_message(text):
    if not settings.discord_webhook_url:
        return

    def _send():
        try:
            now = datetime.datetime.now()
            message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(text)}"}
            requests.post(settings.discord_webhook_url, data=message, timeout=5)
        except Exception as e:
            logger.warning(f"Discord 웹훅 전송 실패: {e}")

    threading.Thread(target=_send, daemon=True).start()
