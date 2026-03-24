import datetime
import requests
from app.configs.settings import settings


def discord_send_message(text):
    now = datetime.datetime.now()
    message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(text)}"}
    requests.post(settings.discord_webhook_url, data=message)
