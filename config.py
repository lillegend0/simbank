
from decouple import config
SIMBANK_IP = config("SIMBANK_IP")
USERNAME = config("USERNAME")
PASSWORD = config("PASSWORD")

BOT_TOKEN = config("BOT_TOKEN")
CHAT_ID = config("CHAT_ID")

PORT = config("PORT", cast=int)

STATUS_FILE = "statuses.json"