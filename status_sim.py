import requests
import time
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from config import SIMBANK_IP, USERNAME, PASSWORD, BOT_TOKEN, CHAT_ID, PORT, STATUS_FILE
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

MOSCOW_TZ = timezone(timedelta(hours=3))

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, data=data)
        resp.raise_for_status()
    except Exception as e:
        print(f"Ошибка отправки Telegram: {e}")
        log_change(f"❗ Ошибка отправки Telegram: {e}")

def log_change(message):
    timestamp = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with open("status.log", "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

def get_status_html():
    url = f"{SIMBANK_IP}/default/en_US/status.html"
    try:
        response = requests.get(url, auth=(USERNAME, PASSWORD), timeout=15)
        if response.status_code == 401:
            return f"ERROR: Не удалось авторизоваться. Код: {response.status_code}"
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"ERROR: {e}"

def parse_html_status(html_text):
    soup = BeautifulSoup(html_text, "html.parser")

    def extract(tag_id):
        tag = soup.find(id=tag_id)
        return tag.text.strip() if tag else "N/A"

    statuses = {
        "gsm_sim": extract(f"l{PORT}_gsm_sim"),
        "module_status": extract(f"l{PORT}_module_status"),
        "gsm_status": extract(f"l{PORT}_gsm_status"),
        "status_line": extract(f"l{PORT}_status_line"),
    }

    summary = (
        f"🧩 *Статус SIM-карты (порт {PORT}):*\n"
        f"📍 SIM Inserted: `{statuses['gsm_sim']}`\n"
        f"🔗 Module Status: `{statuses['module_status']}`\n"
        f"⚠ GSM Status: `{statuses['gsm_status']}`\n"
        f"📡 Status Line: `{statuses['status_line']}`\n"
    )
    return summary, statuses

def load_previous_statuses():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке статусов: {e}")
            log_change(f"❗ Ошибка загрузки файла статусов: {e}")
    return {}

def save_statuses(statuses):
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(statuses, f, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении статусов: {e}")
        log_change(f"❗ Ошибка при сохранении статусов: {e}")

def main():
    previous_statuses = load_previous_statuses()

    html_data = get_status_html()

    if html_data.startswith("ERROR"):
        send_telegram(f"❗ Ошибка при получении статуса:\n{html_data}")
        print(html_data)
        log_change(f"Ошибка получения HTML: {html_data}")
        return

    summary, current_raw = parse_html_status(html_data)
    now = datetime.now(timezone.utc).isoformat()

    updated_statuses = {}
    alerts = []

    for key, curr_value in current_raw.items():
        prev_data = previous_statuses.get(key, {})
        prev_value = prev_data.get("value")
        since = prev_data.get("since", now)
        alert_sent = prev_data.get("alert_sent", False)

        if curr_value != prev_value:
            since = now
            if curr_value == "Y":
                alert_sent = False
            log_change(f"{key} изменился: {prev_value} → {curr_value}")

        if curr_value == "N":
            down_since = datetime.fromisoformat(since)
            if down_since.tzinfo is None:
                down_since = down_since.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) - down_since > timedelta(minutes=2):
                if not alert_sent:
                    alerts.append(f"❌ *{key}* отключено более 2 минут.")
                    alert_sent = True
                    log_change(f"{key} отключено более 2 минут")

        elif curr_value == "Y" and prev_value == "N":
            alerts.append(f"✅ *{key}* восстановилось.")
            alert_sent = False
            log_change(f"{key} восстановилось")

        updated_statuses[key] = {
            "value": curr_value,
            "since": since,
            "alert_sent": alert_sent
        }

    if alerts:
        alert_text = "\n".join(alerts)
        send_telegram(f"{alert_text}\n\n{summary}")
        log_change(f"Отправлено уведомление: {alert_text.replace(chr(10), ' | ')}")
    else:
        print("Изменений нет или не прошло 2 минуты.")

    save_statuses(updated_statuses)

if __name__ == "__main__":
    main()