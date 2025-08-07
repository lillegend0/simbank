import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from config import SIMBANK_IP, USERNAME, PASSWORD, BOT_TOKEN, CHAT_ID, PORT, STATUS_FILE
from dotenv import load_dotenv, find_dotenv

# Загрузка переменных окружения
load_dotenv(find_dotenv())
LOG_FILE = os.getenv("LOG_FILE", "status.log")
MOSCOW_TZ = timezone(timedelta(hours=3))

def ensure_log_dir():
    """Создание директории логов, если необходимо."""
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

def log(message: str):
    """Запись сообщения в лог-файл с таймстампом."""
    ensure_log_dir()
    timestamp = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"❗ Ошибка записи в лог: {e}")

def send_telegram(message: str):
    """Отправка сообщения в Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error = f"Ошибка отправки Telegram: {e} - Ответ: {getattr(resp, 'text', '')}"
        print(error)
        log(f"❗ {error}")

def get_status_page() -> str:
    """Получение HTML-страницы со статусами симбанка."""
    url = f"{SIMBANK_IP}/default/en_US/status.html"
    try:
        response = requests.get(url, auth=(USERNAME, PASSWORD), timeout=15)
        if response.status_code == 401:
            return "ERROR: Unauthorized (401)"
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"ERROR: {e}"

def parse_status(html: str) -> Tuple[str, Dict[str, str]]:
    """Парсинг HTML и получение значений статусов, пустые заменяем на 'N'."""
    soup = BeautifulSoup(html, "html.parser")

    def extract(id_: str) -> str:
        el = soup.find(id=id_)
        text = el.text.strip() if el else ""
        return text if text else "N"  # заменяем пустое на "N"

    statuses = {
        "gsm_sim": extract(f"l{PORT}_gsm_sim"),
        "module_status": extract(f"l{PORT}_module_status"),
        "gsm_status": extract(f"l{PORT}_gsm_status"),
        "status_line": extract(f"l{PORT}_status_line"),
    }

    summary = (
        f"🧩 <b>Статус SIM-карты (порт {PORT}):</b>\n"
        f"📍 SIM Inserted: <code>{statuses['gsm_sim']}</code>\n"
        f"🔗 Module Status: <code>{statuses['module_status']}</code>\n"
        f"⚠ GSM Status: <code>{statuses['gsm_status']}</code>\n"
        f"📡 Status Line: <code>{statuses['status_line']}</code>"
    )

    return summary, statuses

def load_previous() -> Dict[str, Dict[str, str]]:
    """Загрузка предыдущих статусов."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            log(f"❗ Ошибка загрузки предыдущих статусов: {e}")
    return {}

def save_statuses(data: Dict[str, Dict[str, str]]):
    """Сохранение текущих статусов."""
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        log(f"❗ Ошибка при сохранении статусов: {e}")

def monitor():
    previous = load_previous()
    html = get_status_page()

    if html.startswith("ERROR"):
        send_telegram(f"❗ <b>Ошибка при получении статуса:</b>\n<code>{html}</code>")
        log(f"Ошибка получения HTML: {html}")
        return

    summary, current = parse_status(html)
    now = datetime.now(timezone.utc).isoformat()

    alerts = []
    updated = {}

    for key, value in current.items():
        prev = previous.get(key, {})
        prev_val = prev.get("value", "")
        since = prev.get("since", now)
        alert_sent = prev.get("alert_sent", False)

        # Нормализуем значения: пустое => "N"
        curr_norm = value or "N"
        prev_norm = prev_val or "N"

        # Если значение изменилось — сбрасываем таймер и флаг
        if curr_norm != prev_norm:
            since = now
            alert_sent = False
            log(f"{key} изменился: {prev_val} → {value}")

        # Проверка: если отключено ("N") > 2 минут и не отправляли
        if curr_norm == "N":
            if not alert_sent:
                alerts.append(f"❌ <b>{key}</b> отключено.")
                alert_sent = True
                log(f"{key} отключено")

        # ✅ Восстановление: если раньше было "N", а теперь не "N"
        elif prev_norm == "N" and curr_norm != "N":
            alerts.append(f"✅ <b>{key}</b> восстановилось.")
            alert_sent = False
            log(f"{key} восстановилось")

        # Обновляем статус
        updated[key] = {
            "value": value,
            "since": since,
            "alert_sent": alert_sent
        }

    if alerts:
        send_telegram("\n".join(alerts) + "\n\n" + summary)
        log("Уведомление отправлено: " + " | ".join(alerts))
    else:
        print("Изменений нет или не прошло 2 минуты.")
        log("Изменений нет или не прошло 2 минуты.")

    save_statuses(updated)

if __name__ == "__main__":
    monitor()