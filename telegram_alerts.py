
import os
import ast
import json
import requests
import numpy as np
import pandas as pd

from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# AFG AI GOLD PRO ELITE V11 - Telegram Worker
API_URL = "https://api.twelvedata.com/time_series"
TIMEOUT = 25
LOCAL_TZ = ZoneInfo("Asia/Kabul")

SYMBOLS = {"GOLD": "XAU/USD", "BTC": "BTC/USD"}
INTERVALS = {
    "5M": "5min",
    "15M": "15min",
    "1H": "1h",
    "4H": "4h",
}
DELTAS = {
    "5min": pd.Timedelta(minutes=5),
    "15min": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
}

API_KEY = os.environ["TWELVE_DATA_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = Path("signal_state.json")
MAX_DAILY_SIGNALS = 5
SIGNAL_VALIDITY_MINUTES = 45
MIN_SCORE = 55


# Load the exact V11 analysis functions from app.py.
# Streamlit interface code is not imported or executed.
def load_v11_engine():
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    required = {
        "get_candles",
        "add_indicators",
        "trend_of",
        "candle_quality",
        "analyze_signal",
    }

    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in required:
                node.decorator_list = []
                functions.append(node)

    found = {node.name for node in functions}
    missing = required - found
    if missing:
        raise RuntimeError(
            "V11 functions missing from app.py: " + ", ".join(sorted(missing))
        )

    module = ast.Module(body=functions, type_ignores=[])
    namespace = {
        "pd": pd,
        "np": np,
        "requests": requests,
        "API_URL": API_URL,
        "TIMEOUT": TIMEOUT,
        "DELTAS": DELTAS,
    }
    exec(compile(module, "v11_engine", "exec"), namespace)
    return namespace


engine = load_v11_engine()
get_candles = engine["get_candles"]
add_indicators = engine["add_indicators"]
analyze_signal = engine["analyze_signal"]


def load_state():
    if not STATE_FILE.exists():
        return {"date": "", "sent": []}

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data.get("sent"), list):
            return {"date": "", "sent": []}
        return data
    except Exception:
        return {"date": "", "sent": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8"
    )


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message.")


def scan_market(asset, symbol):
    frames = {}

    for label, interval in INTERVALS.items():
        candles = get_candles(symbol, interval, API_KEY)
        frames[label] = add_indicators(candles)

    result = analyze_signal(frames, MIN_SCORE, 20)

    last15 = frames["15M"].iloc[-1]
    candle_time = last15["datetime"].to_pydatetime()
    candle_close = candle_time + timedelta(minutes=15)

    now = datetime.now(timezone.utc)
    age = now - candle_close

    if age > timedelta(minutes=SIGNAL_VALIDITY_MINUTES):
        return None

    if age < timedelta(0):
        return None

    if result["signal"] not in ("BUY", "SELL"):
        return None

    if result["entry"] is None or result["sl"] is None:
        return None

    if any(result[k] is None for k in ("tp1", "tp2", "tp3")):
        return None

    result["asset"] = asset
    result["symbol"] = symbol
    result["candle_time"] = candle_time
    result["candle_close"] = candle_close
    return result


def format_message(r):
    local_time = r["candle_close"].astimezone(LOCAL_TZ)

    return (
        "🇦🇫 AFG AI GOLD PRO ELITE V11\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Market: {r['asset']} ({r['symbol']})\n"
        f"Signal: {r['order_type']}\n"
        f"Score: {r['score']}/100\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Entry: {r['entry']:.5f}\n"
        f"Stop Loss: {r['sl']:.5f}\n"
        f"TP1: {r['tp1']:.5f}\n"
        f"TP2: {r['tp2']:.5f}\n"
        f"TP3: {r['tp3']:.5f}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"15M candle close: {local_time:%Y-%m-%d %H:%M} Kabul\n"
        f"Validity: {SIGNAL_VALIDITY_MINUTES} minutes\n"
        "Manual trading only. Verify live price before trading."
    )


def main():
    today = datetime.now(LOCAL_TZ).date().isoformat()
    state = load_state()

    if state.get("date") != today:
        state = {"date": today, "sent": []}

    for asset, symbol in SYMBOLS.items():
        try:
            result = scan_market(asset, symbol)

            if result is None:
                print(f"{asset}: no valid new signal.")
                continue

            key = (
                f"{asset}|{result['candle_time'].isoformat()}|"
                f"{result['signal']}"
            )

            if key in state["sent"]:
                print(f"{asset}: this signal was already sent.")
                continue

            if len(state["sent"]) >= MAX_DAILY_SIGNALS:
                print("Daily signal limit reached.")
                break

            message = format_message(result)
            send_telegram(message)

            state["sent"].append(key)
            save_state(state)

            print(f"{asset}: Telegram alert sent.")

        except Exception as exc:
            # Do not print API keys or bot tokens.
            print(f"{asset}: scan failed: {type(exc).__name__}: {exc}")

    save_state(state)


if __name__ == "__main__":
    main()
