from decouple import config

SIMBANK_IP = config("SIMBANK_IP")
USERNAME = config("USERNAME")
PASSWORD = config("PASSWORD")
BOT_TOKEN = config("BOT_TOKEN")
CHAT_ID = config("CHAT_ID")
STATUS_FILE = config("STATUS_FILE")
LOG_FILE = config("LOG_FILE", default="status.log")
PORT = config("PORT", cast=int)