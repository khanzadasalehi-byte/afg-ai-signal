import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import hashlib
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="KhanGoldSignal | GOLD & BTC",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "KhanGoldSignal"
UTC = timezone.utc
ASSETS = {
    "GOLD": {"symbol": "XAU/USD", "label": "XAUUSD"},
    "BITCOIN": {"symbol": "BTC/USD", "label": "BTCUSD"}
}
PROFILES = {
    "Scalping": {
        "entry_tf": "1min", "trend_tf": "5min", "confirm_tf": "15min",
        "min_score": 65, "min_adx": 15, "atr_sl": 1.5,
        "pullback_min": .05, "pullback_max": .75
    },
    "Intraday": {
        "entry_tf": "15min", "trend_tf": "1h", "confirm_tf": "4h",
        "min_score": 65, "min_adx": 16, "atr_sl": 1.7,
        "pullback_min": .08, "pullback_max": .90
    },
    "Swing": {
        "entry_tf": "4h", "trend_tf": "1day", "confirm_tf": "1day",
        "min_score": 65, "min_adx": 17, "atr_sl": 2.0,
        "pullback_min": .10, "pullback_max": 1.10
    }
}
VALIDITY_MINUTES = 45
SIGNAL_TABLE = "signals"
OUTBOX_TABLE = "telegram_outbox"

st.markdown(
    """<style>
    .stApp{background:#090611;color:#e3d9f2}
    .block-container{max-width:1400px;padding-top:1rem}
    [data-testid=stSidebar]{background:#17131f}
    div[data-testid=stMetric]{background:#100b1b;border:1px solid #30233d;padding:10px;border-radius:12px}
    </style>""",
    unsafe_allow_html=True
)

# --------------------------- General helpers ---------------------------

def utc_now():
    return datetime.now(UTC)

def iso_utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.astimezone(UTC).isoformat()

def parse_dt(value):
    if not value:
        return None
    try:
        result = pd.Timestamp(value).to_pydatetime()
        if result.tzinfo is None:
            result = result.replace(tzinfo=UTC)
        return result.astimezone(UTC)
    except Exception:
        return None

def num(value, default=None):
    try:
        result = float(value)
        return result if np.isfinite(result) else default
    except Exception:
        return default

def price(value):
    result = num(value)
    return f"{result:,.2f}" if result is not None else "—"

def secret(name, default=""):
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return str(default).strip()

def interval_delta(tf):
    values = {
        "1min": timedelta(minutes=1),
        "5min": timedelta(minutes=5),
        "15min": timedelta(minutes=15),
        "30min": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1day": timedelta(days=1)
    }
    return values[tf]

def market_session():
    now = utc_now()
    london = now.astimezone(ZoneInfo("Europe/London"))
    new_york = now.astimezone(ZoneInfo("America/New_York"))
    london_open = london.weekday() < 5 and 8 <= london.hour < 17
    ny_open = new_york.weekday() < 5 and 8 <= new_york.hour < 17
    if london_open and ny_open:
        return "LONDON / NEW YORK OVERLAP"
    if london_open:
        return "LONDON"
    if ny_open:
        return "NEW YORK"
    return "ASIA / OFF SESSION" if now.weekday() < 5 else "WEEKEND"

# --------------------------- Gold market calendar ---------------------------
# Default schedule is a configurable reference schedule, not a broker guarantee.
# Defaults: Sunday 18:00 New York open; Friday 17:00 close;
# daily maintenance break 17:00-18:00 New York time.
# Configure these values in Streamlit secrets to match the actual broker.

def gold_market_status(now=None):
    now = now or utc_now()
    tz_name = secret("GOLD_MARKET_TIMEZONE", "America/New_York")
    try:
        market_tz = ZoneInfo(tz_name)
    except Exception:
        return False, f"Invalid GOLD_MARKET_TIMEZONE: {tz_name}"

    local = now.astimezone(market_tz)

    closed_dates = {
        item.strip()
        for item in secret("GOLD_MARKET_CLOSED_DATES", "").split(",")
        if item.strip()
    }
    if local.date().isoformat() in closed_dates:
        return False, "Configured market holiday"

    try:
        friday_close = time.fromisoformat(secret("GOLD_FRIDAY_CLOSE", "17:00"))
        sunday_open = time.fromisoformat(secret("GOLD_SUNDAY_OPEN", "18:00"))
        maintenance_start = time.fromisoformat(secret("GOLD_MAINTENANCE_START", "17:00"))
        maintenance_end = time.fromisoformat(secret("GOLD_MAINTENANCE_END", "18:00"))
    except Exception:
        return False, "Invalid gold market session configuration"

    weekday = local.weekday()
    clock = local.timetz().replace(tzinfo=None)

    if weekday == 5:
        return False, "Weekend closure"
    if weekday == 6 and clock < sunday_open:
        return False, "Weekend closure"
    if weekday == 4 and clock >= friday_close:
        return False, "Weekend closure"
    if maintenance_start <= clock < maintenance_end:
        return False, "Daily maintenance break"

    # Optional full-day holiday range, comma-separated YYYY-MM-DD.
    # Exact dates are configured by the operator; no holiday is guessed.
    return True, "OPEN"

def market_status_text():
    is_open, reason = gold_market_status()
    return ("OPEN", reason) if is_open else ("CLOSED", reason)

# --------------------------- Market data ---------------------------

@st.cache_data(ttl=45, show_spinner=False)
def get_candles(api_key, symbol, interval, outputsize=500):
    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": api_key,
            "format": "JSON",
            "timezone": "UTC"
        },
        timeout=25
    )
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise RuntimeError(
            f"Twelve Data {symbol} {interval}: "
            f"{payload.get('message', payload.get('code', 'No data'))}"
        )

    data = pd.DataFrame(payload["values"])
    for column in ("open", "high", "low", "close"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["datetime"] = pd.to_datetime(
        data["datetime"], utc=True, errors="coerce"
    )
    data = (
        data.dropna(subset=["datetime", "open", "high", "low", "close"])
        .sort_values("datetime")
        .drop_duplicates("datetime")
        .set_index("datetime")
    )
    data = data[data.index <= utc_now() - interval_delta(interval)]
    if len(data) < 220:
        raise RuntimeError(f"Not enough closed candles for {symbol} {interval}.")
    return data

def add_indicators(data):
    result = data.copy()
    close = result.close

    for length in (20, 50, 200):
        result[f"ema{length}"] = close.ewm(
            span=length, adjust=False
        ).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    result["rsi"] = (
        (100 - 100 / (1 + rs))
        .mask((loss == 0) & (gain > 0), 100)
        .mask((gain == 0) & (loss > 0), 0)
    )

    previous = close.shift(1)
    true_range = pd.concat(
        [
            result.high - result.low,
            (result.high - previous).abs(),
            (result.low - previous).abs()
        ],
        axis=1
    ).max(axis=1)
    result["atr"] = true_range.ewm(alpha=1/14, adjust=False).mean()

    up = result.high.diff()
    down = -result.low.diff()
    plus = pd.Series(
        np.where((up > down) & (up > 0), up, 0), index=result.index
    )
    minus = pd.Series(
        np.where((down > up) & (down > 0), down, 0), index=result.index
    )
    smooth = true_range.ewm(alpha=1/14, adjust=False).mean().replace(0, np.nan)
    pdi = 100 * plus.ewm(alpha=1/14, adjust=False).mean() / smooth
    mdi = 100 * minus.ewm(alpha=1/14, adjust=False).mean() / smooth
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    result["adx"] = dx.ewm(alpha=1/14, adjust=False).mean()
    result["plus_di"] = pdi
    result["minus_di"] = mdi

    return result.replace([np.inf, -np.inf], np.nan).dropna()

def trend(row):
    if (
        row.ema20 > row.ema50
        and row.close > row.ema200
        and row.plus_di > row.minus_di
    ):
        return "BULLISH"
    if (
        row.ema20 < row.ema50
        and row.close < row.ema200
        and row.minus_di > row.plus_di
    ):
        return "BEARISH"
    return "SIDEWAYS"

# --------------------------- Strategy ---------------------------

def evaluate(entry_raw, trend_raw, confirm_raw, profile):
    cfg = PROFILES[profile]
    entry_data = add_indicators(entry_raw)
    trend_data = add_indicators(trend_raw)
    confirm_data = add_indicators(confirm_raw)

    if min(len(entry_data), len(trend_data), len(confirm_data)) < 5:
        raise RuntimeError("Insufficient indicator history")

    current = entry_data.iloc[-1]
    previous = entry_data.iloc[-2]
    main_trend = trend(trend_data.iloc[-1])
    higher_trend = trend(confirm_data.iloc[-1])
    entry_trend = trend(current)

    current_price = float(current.close)
    atr_value = float(current.atr)

    long_conditions = [
        entry_trend == "BULLISH",
        main_trend == "BULLISH",
        higher_trend == "BULLISH",
        current.adx >= cfg["min_adx"],
        current.plus_di > current.minus_di,
        50 <= current.rsi <= 70,
        current_price > current.ema20,
        current.ema20 > current.ema50,
        current.close > current.open,
        current.close > previous.high
    ]
    short_conditions = [
        entry_trend == "BEARISH",
        main_trend == "BEARISH",
        higher_trend == "BEARISH",
        current.adx >= cfg["min_adx"],
        current.minus_di > current.plus_di,
        30 <= current.rsi <= 50,
        current_price < current.ema20,
        current.ema20 < current.ema50,
        current.close < current.open,
        current.close < previous.low
    ]
    weights = [15, 20, 15, 10, 10, 8, 7, 5, 5, 5]
    long_score = sum(w for w, ok in zip(weights, long_conditions) if ok)
    short_score = sum(w for w, ok in zip(weights, short_conditions) if ok)

    if long_score > short_score:
        direction, score = "BUY", long_score
    elif short_score > long_score:
        direction, score = "SELL", short_score
    else:
        direction, score = "WAIT", max(long_score, short_score)

    distance_atr = (
        abs(current_price - float(current.ema20)) / atr_value
        if atr_value > 0 else 999
    )
    aligned = (
        main_trend == ("BULLISH" if direction == "BUY" else "BEARISH")
        and higher_trend == ("BULLISH" if direction == "BUY" else "BEARISH")
    )
    if (
        direction == "WAIT"
        or not aligned
        or score < cfg["min_score"]
        or not cfg["pullback_min"] <= distance_atr <= cfg["pullback_max"]
        or float(current.high - current.low) > 2.8 * atr_value
    ):
        direction = "WAIT"

    entry_type = "NONE"
    entry_price = zone_low = zone_high = stop_loss = np.nan
    targets = [np.nan, np.nan, np.nan]
    grade = "—"
    risk_label = "NO TRADE"
    status = "WAIT"

    if direction in ("BUY", "SELL") and atr_value > 0:
        # Near the live/closed-candle price: MARKET. Otherwise a two-price LIMIT zone.
        # A LIMIT zone is centered around EMA20 and has a total width of 0.10 ATR.
        market_threshold = max(0.08, min(0.15, cfg["pullback_min"] + 0.05))
        if distance_atr <= market_threshold:
            entry_type = "MARKET"
            entry_price = current_price
            zone_low = zone_high = np.nan
        else:
            entry_type = "LIMIT"
            zone_low = float(current.ema20 - 0.05 * atr_value)
            zone_high = float(current.ema20 + 0.05 * atr_value)
            entry_price = (zone_low + zone_high) / 2.0

        swing_low = float(entry_data.low.tail(10).min())
        swing_high = float(entry_data.high.tail(10).max())

        if direction == "BUY":
            stop_loss = min(swing_low, entry_price - cfg["atr_sl"] * atr_value)
            risk = entry_price - stop_loss
        else:
            stop_loss = max(swing_high, entry_price + cfg["atr_sl"] * atr_value)
            risk = stop_loss - entry_price

        if risk > 0 and np.isfinite(risk):
            sign = 1 if direction == "BUY" else -1
            targets = [entry_price + sign * risk * factor for factor in (1, 2, 3)]
            grade = "A" if score >= 85 else "B" if score >= 70 else "C"
            risk_label = (
                "LOWER SETUP RISK" if score >= 85
                else "MODERATE SETUP" if score >= 70
                else "WEAKER SETUP"
            )
            status = "ACTIVE_TRADE" if entry_type == "MARKET" else "PENDING_LIMIT"
        else:
            direction = "WAIT"
            entry_type = "NONE"
            entry_price = zone_low = zone_high = stop_loss = np.nan
            targets = [np.nan, np.nan, np.nan]

    return {
        "asset": "",
        "profile": profile,
        "direction": direction,
        "entry_type": entry_type,
        "entry_price": num(entry_price),
        "zone_low": num(zone_low),
        "zone_high": num(zone_high),
        "stop_loss": num(stop_loss),
        "tp1": num(targets[0]),
        "tp2": num(targets[1]),
        "tp3": num(targets[2]),
        "score": int(score),
        "grade": grade,
        "risk_level": risk_label,
        "session": market_session(),
        "candle_time": iso_utc(entry_data.index[-1].to_pydatetime()),
        "current_price": current_price,
        "atr": atr_value,
        "status": status
    }

def build_candidate(api_key, asset, profile):
    asset_cfg = ASSETS[asset]
    profile_cfg = PROFILES[profile]
    entry_data = get_candles(
        api_key, asset_cfg["symbol"], profile_cfg["entry_tf"], 500
    )
    trend_data = get_candles(
        api_key, asset_cfg["symbol"], profile_cfg["trend_tf"], 400
    )
    confirm_data = get_candles(
        api_key, asset_cfg["symbol"], profile_cfg["confirm_tf"], 400
    )
    candidate = evaluate(entry_data, trend_data, confirm_data, profile)
    candidate["asset"] = asset
    candidate["current_price"] = float(entry_data.close.iloc[-1])
    candidate["atr"] = float(add_indicators(entry_data).atr.iloc[-1])
    candidate["setup_key"] = hashlib.sha256(
        (
            f"{asset}|{profile}|{candidate['direction']}|"
            f"{candidate['entry_type']}|{candidate['candle_time']}"
        ).encode()
    ).hexdigest()[:32]
    return candidate

# --------------------------- Supabase: existing schema ---------------------------

def supabase_config():
    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_KEY") or secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None, None
    return url.rstrip("/"), key

def db_request(method, table, params=None, payload=None, prefer=None):
    url, key = supabase_config()
    if not url:
        raise RuntimeError("Supabase URL/KEY missing in Streamlit secrets")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if prefer:
        headers["Prefer"] = prefer
    response = requests.request(
        method,
        f"{url}/rest/v1/{table}",
        headers=headers,
        params=params,
        json=payload,
        timeout=20
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase {response.status_code}: {response.text[:400]}")
    return response.json() if response.text.strip() else []

def get_signal_by_key(key):
    rows = db_request(
        "GET", SIGNAL_TABLE,
        {"select": "*", "signal_key": f"eq.{key}", "limit": "1"}
    )
    return rows[0] if rows else None

def get_route_latest(asset, profile):
    rows = db_request(
        "GET", SIGNAL_TABLE,
        {
            "select": "*",
            "asset": f"eq.{asset}",
            "profile": f"eq.{profile}",
            "order": "generated_at.desc",
            "limit": "1"
        }
    )
    return rows[0] if rows else None

def update_signal(signal_key, updates):
    return db_request(
        "PATCH", SIGNAL_TABLE,
        {"signal_key": f"eq.{signal_key}"},
        updates,
        "return=representation"
    )

def make_signal_row(candidate):
    now = utc_now()
    row_status = candidate["status"]
    generated = iso_utc(now)
    row = {
        "signal_key": candidate["setup_key"],
        "asset": candidate["asset"],
        "profile": candidate["profile"],
        "direction": candidate["direction"],
        "entry_type": candidate["entry_type"],
        "entry_price": candidate["entry_price"],
        "zone_low": candidate["zone_low"],
        "zone_high": candidate["zone_high"],
        "stop_loss": candidate["stop_loss"],
        "tp1": candidate["tp1"],
        "tp2": candidate["tp2"],
        "tp3": candidate["tp3"],
        "score": candidate["score"],
        "grade": candidate["grade"],
        "risk_level": candidate["risk_level"],
        "session": candidate["session"],
        "candle_time": candidate["candle_time"],
        "generated_at": generated,
        "expires_at": iso_utc(now + timedelta(minutes=VALIDITY_MINUTES)),
        "status": row_status,
        "extension_count": 0
    }
    if row_status == "ACTIVE_TRADE":
        row["trade_opened_at"] = generated
    return row

def is_active(signal):
    return bool(signal) and signal.get("status") in (
        "PENDING_LIMIT", "ACTIVE_TRADE", "TP1_HIT", "TP2_HIT"
    )

def review_pending(existing, candidate):
    if existing.get("status") != "PENDING_LIMIT":
        return existing
    expiry = parse_dt(existing.get("expires_at"))
    now = utc_now()
    if expiry and now < expiry:
        return existing

    old_entry = num(existing.get("entry_price"))
    current_price = num(candidate.get("current_price"))
    atr_value = num(candidate.get("atr"), 0)
    same_direction = (
        candidate.get("direction") == existing.get("direction")
        and candidate.get("direction") in ("BUY", "SELL")
    )
    tolerance = max((atr_value or 0) * 0.5, (old_entry or 0) * 0.0005)

    actionable = False
    if old_entry is not None and current_price is not None:
        if existing.get("direction") == "BUY":
            actionable = current_price > old_entry and current_price - old_entry <= tolerance
        elif existing.get("direction") == "SELL":
            actionable = current_price < old_entry and old_entry - current_price <= tolerance

    if same_direction and actionable:
        update_signal(
            existing["signal_key"],
            {
                "expires_at": iso_utc(now + timedelta(minutes=VALIDITY_MINUTES)),
                "extension_count": int(existing.get("extension_count") or 0) + 1,
                "last_review_at": iso_utc(now),
                "last_review_reason": "Setup still valid; original prices preserved"
            }
        )
    else:
        update_signal(
            existing["signal_key"],
            {
                "status": "INVALIDATED",
                "last_review_at": iso_utc(now),
                "last_review_reason": "Setup invalid or original entry no longer actionable"
            }
        )
    return get_signal_by_key(existing["signal_key"])

def get_or_create_signal(candidate):
    existing = get_route_latest(candidate["asset"], candidate["profile"])
    if is_active(existing):
        return (
            review_pending(existing, candidate)
            if existing.get("status") == "PENDING_LIMIT"
            else existing
        )

    if candidate.get("direction") not in ("BUY", "SELL"):
        return existing

    prior = get_signal_by_key(candidate["setup_key"])
    if prior:
        return prior

    rows = db_request(
        "POST",
        SIGNAL_TABLE,
        payload=make_signal_row(candidate),
        prefer="return=representation"
    )
    if not rows:
        raise RuntimeError("Supabase did not return inserted signal")
    return rows[0]

def get_history(limit=200):
    return db_request(
        "GET", SIGNAL_TABLE,
        {"select": "*", "order": "generated_at.desc", "limit": str(limit)}
    )

def get_active():
    return db_request(
        "GET", SIGNAL_TABLE,
        {
            "select": "*",
            "status": "in.(PENDING_LIMIT,ACTIVE_TRADE,TP1_HIT,TP2_HIT)",
            "order": "generated_at.asc",
            "limit": "300"
        }
    )

def snapshot_from_row(row):
    return {
        key: row.get(key)
        for key in (
            "asset", "profile", "direction", "entry_type", "entry_price",
            "zone_low", "zone_high", "stop_loss", "tp1", "tp2", "tp3",
            "score", "grade", "risk_level", "session", "candle_time"
        )
    }

# --------------------------- Telegram outbox ---------------------------

def telegram_config():
    token = secret("TELEGRAM_BOT_TOKEN")
    chat = secret("TELEGRAM_CHAT_ID")
    return (token, chat) if token and chat else (None, None)

def telegram_text(row):
    snapshot = snapshot_from_row(row)
    symbol = ASSETS.get(snapshot["asset"], {}).get("symbol", snapshot["asset"])
    if snapshot["entry_type"] == "LIMIT":
        entry_text = (
            f"{snapshot['direction']} LIMIT ZONE: "
            f"{price(snapshot['zone_low'])} – {price(snapshot['zone_high'])}\n"
            f"Calculation reference (zone midpoint): {price(snapshot['entry_price'])}"
        )
    else:
        entry_text = f"MARKET ENTRY: {price(snapshot['entry_price'])}"

    return (
        f"🟡 KHAN GOLD SIGNAL\n"
        f"Asset: {symbol}\n"
        f"Profile: {snapshot['profile']}\n"
        f"Direction: {snapshot['direction']}\n"
        f"Score: {snapshot['score']}/100 | Grade: {snapshot['grade']}\n"
        f"{entry_text}\n"
        f"SL: {price(snapshot['stop_loss'])}\n"
        f"TP1: {price(snapshot['tp1'])}\n"
        f"TP2: {price(snapshot['tp2'])}\n"
        f"TP3: {price(snapshot['tp3'])}\n"
        f"Session: {snapshot['session']}\n"
        f"Initial validity: {VALIDITY_MINUTES} minutes\n"
        f"Analytical signal only; not an order execution service."
    )

def send_telegram(row):
    # Last safety gate: never send a new Gold alert while Gold is closed.
    if row.get("asset") == "GOLD":
        is_open, _ = gold_market_status()
        if not is_open:
            return "MARKET_CLOSED"

    key = row.get("signal_key")
    existing = db_request(
        "GET", OUTBOX_TABLE,
        {"select": "*", "signal_key": f"eq.{key}", "limit": "1"}
    )

    if existing:
        item = existing[0]
        if item.get("status") in ("SENT", "UNKNOWN", "SENDING"):
            return item.get("status")
        if item.get("status") != "PENDING":
            return item.get("status")
    else:
        message = telegram_text(row)
        created = db_request(
            "POST",
            OUTBOX_TABLE,
            payload={
                "signal_key": key,
                "status": "PENDING",
                "message_payload": json.dumps(
                    {"text": message}, ensure_ascii=False
                ),
                "created_at": iso_utc(utc_now()),
                "updated_at": iso_utc(utc_now())
            },
            prefer="return=representation"
        )
        if not created:
            return "OUTBOX_ERROR"
        item = created[0]

    item_id = item.get("id")
    db_request(
        "PATCH", OUTBOX_TABLE, {"id": f"eq.{item_id}"},
        {"status": "SENDING", "updated_at": iso_utc(utc_now())},
        "return=minimal"
    )

    token, chat = telegram_config()
    if not token:
        db_request(
            "PATCH", OUTBOX_TABLE, {"id": f"eq.{item_id}"},
            {
                "status": "FAILED",
                "error_message": "Telegram credentials missing",
                "updated_at": iso_utc(utc_now())
            },
            "return=minimal"
        )
        return "FAILED"

    payload = item.get("message_payload") or "{}"
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"text": payload}

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": payload.get("text", "")},
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError("Telegram did not confirm delivery")

        db_request(
            "PATCH", OUTBOX_TABLE, {"id": f"eq.{item_id}"},
            {
                "status": "SENT",
                "telegram_message_id": str(data["result"]["message_id"]),
                "sent_at": iso_utc(utc_now()),
                "updated_at": iso_utc(utc_now()),
                "error_message": None
            },
            "return=minimal"
        )
        return "SENT"

    except requests.Timeout as error:
        db_request(
            "PATCH", OUTBOX_TABLE, {"id": f"eq.{item_id}"},
            {
                "status": "UNKNOWN",
                "error_message": str(error)[:400],
                "updated_at": iso_utc(utc_now())
            },
            "return=minimal"
        )
        return "UNKNOWN"
    except Exception as error:
        db_request(
            "PATCH", OUTBOX_TABLE, {"id": f"eq.{item_id}"},
            {
                "status": "FAILED",
                "error_message": str(error)[:400],
                "updated_at": iso_utc(utc_now())
            },
            "return=minimal"
        )
        return "FAILED"

# --------------------------- Estimated candle trade lifecycle ---------------------------
# Replays all available closed candles from the persisted publication/fill time.
# This makes repeated dashboard refreshes deterministic without adding DB columns.
# If SL and TP are both touched in one candle, SL is processed first.

def manage_trade(row):
    if row.get("status") not in (
        "PENDING_LIMIT", "ACTIVE_TRADE", "TP1_HIT", "TP2_HIT"
    ):
        return row

    asset = row.get("asset")
    profile = row.get("profile")
    signal_key = row.get("signal_key")

    try:
        candles = get_candles(
            secret("TWELVE_DATA_API_KEY"),
            ASSETS[asset]["symbol"],
            PROFILES[profile]["entry_tf"],
            500
        )
    except Exception:
        return row

    published_at = parse_dt(row.get("generated_at"))
    opened_at = parse_dt(row.get("trade_opened_at"))
    direction = row.get("direction")
    entry = num(row.get("entry_price"))
    stop = num(row.get("stop_loss"))

    if published_at is None or entry is None or stop is None:
        return row

    status = "PENDING_LIMIT" if row.get("entry_type") == "LIMIT" else "ACTIVE_TRADE"
    fill_time = opened_at
    last_event_time = None
    last_reason = None
    closed_at = None

    if row.get("entry_type") == "MARKET":
        fill_time = opened_at or published_at
        status = "ACTIVE_TRADE"

    for candle_time, candle in candles.iterrows():
        candle_dt = candle_time.to_pydatetime().astimezone(UTC)
        if candle_dt <= published_at:
            continue
        if status in ("SL_HIT", "TP3_HIT", "INVALIDATED", "CANCELLED"):
            break

        low = float(candle.low)
        high = float(candle.high)

        if status == "PENDING_LIMIT":
            zone_low = num(row.get("zone_low"), entry)
            zone_high = num(row.get("zone_high"), entry)
            if low <= zone_high and high >= zone_low:
                status = "ACTIVE_TRADE"
                fill_time = candle_dt
                last_event_time = candle_dt
                last_reason = "Estimated limit-zone fill from closed candle"

                sl_hit = low <= stop if direction == "BUY" else high >= stop
                if sl_hit:
                    status = "SL_HIT"
                    closed_at = candle_dt
                    last_reason = "SL checked first on entry candle (conservative)"
                    break
            else:
                continue

        if status in ("ACTIVE_TRADE", "TP1_HIT", "TP2_HIT"):
            sl_hit = low <= stop if direction == "BUY" else high >= stop
            if sl_hit:
                status = "SL_HIT"
                closed_at = candle_dt
                last_event_time = candle_dt
                last_reason = "Conservative rule: stop checked before targets"
                break

            targets = [num(row.get(f"tp{i}")) for i in (1, 2, 3)]
            touched = [
                target is not None and (
                    high >= target if direction == "BUY" else low <= target
                )
                for target in targets
            ]

            if status == "ACTIVE_TRADE" and touched[0]:
                status = "TP1_HIT"
                last_event_time = candle_dt
                last_reason = "TP1 touched; estimated partial allocation 50%"
            if status == "TP1_HIT" and touched[1]:
                status = "TP2_HIT"
                last_event_time = candle_dt
                last_reason = "TP2 touched; cumulative estimated allocation 80%"
            if status == "TP2_HIT" and touched[2]:
                status = "TP3_HIT"
                closed_at = candle_dt
                last_event_time = candle_dt
                last_reason = "TP3 touched; estimated trade completion"
                break

    # Never overwrite immutable entry, SL, TP, score, direction or grade.
    updates = {"status": status}
    if fill_time and row.get("entry_type") == "LIMIT":
        updates["trade_opened_at"] = iso_utc(fill_time)
    if last_event_time:
        updates["last_review_at"] = iso_utc(utc_now())
        updates["last_review_reason"] = last_reason
    if closed_at:
        updates["closed_at"] = iso_utc(closed_at)

    current_status = row.get("status")
    if (
        status != current_status
        or (fill_time and row.get("entry_type") == "LIMIT"
            and not row.get("trade_opened_at"))
        or (closed_at and not row.get("closed_at"))
    ):
        update_signal(signal_key, updates)
        return get_signal_by_key(signal_key)

    return row

def manage_all():
    try:
        rows = get_active()
    except Exception:
        return
    for row in rows:
        try:
            manage_trade(row)
        except Exception:
            pass

# --------------------------- Dashboard ---------------------------

def show_signal(row):
    snapshot = snapshot_from_row(row)
    status = row.get("status", "UNKNOWN")
    symbol = ASSETS.get(snapshot["asset"], {}).get("symbol", snapshot["asset"])

    with st.container(border=True):
        first, second, third = st.columns([2, 1, 1])
        first.subheader(f"{symbol} — {snapshot['profile']}")
        second.metric("Direction", snapshot["direction"])
        third.metric("Score", f"{snapshot['score']}/100")

        st.caption(
            f"Signal key: {row.get('signal_key', '—')} | "
            f"Grade: {snapshot['grade']} | Status: {status}"
        )

        if snapshot["entry_type"] == "LIMIT":
            st.markdown(
                f"**{snapshot['direction']} LIMIT ZONE**  \n"
                f"### {price(snapshot['zone_low'])} – {price(snapshot['zone_high'])}"
            )
            st.caption(
                f"SL/TP calculation reference — zone midpoint: "
                f"{price(snapshot['entry_price'])}"
            )
        elif snapshot["entry_type"] == "MARKET":
            st.markdown(
                f"**MARKET ENTRY**  \n### {price(snapshot['entry_price'])}"
            )

        col1, col2, col3 = st.columns(3)
        col1.metric("Stop Loss", price(snapshot["stop_loss"]))
        col2.metric("Session", snapshot["session"])
        col3.metric("Entry type", snapshot["entry_type"])

        col1, col2, col3 = st.columns(3)
        col1.metric("TP1", price(snapshot["tp1"]))
        col2.metric("TP2", price(snapshot["tp2"]))
        col3.metric("TP3", price(snapshot["tp3"]))

        if status == "PENDING_LIMIT":
            expiry = parse_dt(row.get("expires_at"))
            seconds = (
                max(0, int((expiry - utc_now()).total_seconds()))
                if expiry else 0
            )
            st.info(
                f"Validity: {seconds // 60:02d}:{seconds % 60:02d} | "
                "Expiry is reviewed; published prices stay unchanged."
            )
        elif status in ("ACTIVE_TRADE", "TP1_HIT", "TP2_HIT"):
            st.success(f"Estimated trade lifecycle: {status}")
        elif status in (
            "INVALIDATED", "SL_HIT", "TP3_HIT", "CANCELLED"
        ):
            st.warning(f"Signal status: {status}")

        st.caption(
            f"Generated: {row.get('generated_at', '—')} | "
            f"Candle: {snapshot['candle_time']}"
        )

def route(asset, profile):
    try:
        # Critical: while Gold is closed, do not generate a candidate,
        # create a new signal, or send a new Telegram notification.
        if asset == "GOLD":
            is_open, reason = gold_market_status()
            if not is_open:
                st.warning(f"GOLD market CLOSED — {reason}")
                previous = get_route_latest(asset, profile)
                if previous:
                    st.caption("Last published Gold signal (unchanged snapshot):")
                    show_signal(previous)
                return

        api_key = secret("TWELVE_DATA_API_KEY")
        if not api_key:
            st.warning(
                "TWELVE_DATA_API_KEY is missing in Streamlit secrets."
            )
            return

        candidate = build_candidate(api_key, asset, profile)
        row = get_or_create_signal(candidate)

        if not row:
            st.info("No valid setup at this time.")
            return

        if row.get("status") in ("PENDING_LIMIT", "ACTIVE_TRADE"):
            try:
                send_telegram(row)
            except Exception:
                pass

        show_signal(row)

    except Exception as error:
        st.warning(f"{asset} / {profile}: {error}")

def dashboard():
    st.title("🟡 KhanGoldSignal")
    st.caption(
        "Rule-Based Multi-Timeframe Trend Following | GOLD + BITCOIN"
    )

    with st.sidebar:
        st.header("Control Panel")
        if st.button("Refresh Market Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        auto_refresh = st.checkbox("Auto refresh", True)
        st.caption(
            "Initial validity: 45 minutes | Scalping / Intraday / Swing"
        )

        gold_open, gold_reason = gold_market_status()
        if gold_open:
            st.success("GOLD market: OPEN")
        else:
            st.error(f"GOLD market: CLOSED — {gold_reason}")

    if auto_refresh:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=15000, key="khangold_refresh")
        except Exception:
            pass

    manage_all()

    gold_tab, bitcoin_tab, trade_tab, history_tab, performance_tab = st.tabs(
        [
            "🥇 GOLD",
            "₿ BITCOIN",
            "Trade Management",
            "History",
            "Performance"
        ]
    )

    with gold_tab:
        st.header("GOLD — XAU/USD")
        for profile in PROFILES:
            route("GOLD", profile)

    with bitcoin_tab:
        st.header("BITCOIN — BTC/USD")
        for profile in PROFILES:
            route("BITCOIN", profile)

    with trade_tab:
        try:
            rows = get_active()
            if not rows:
                st.info("No active signals or trades.")
            for row in rows:
                show_signal(row)
            st.caption(
                "Trade fill and target events are estimated from closed candles, "
                "not broker-confirmed."
            )
        except Exception as error:
            st.error(str(error))

    with history_tab:
        try:
            rows = get_history(200)
            if rows:
                columns = (
                    "signal_key", "asset", "profile", "direction",
                    "entry_type", "entry_price", "zone_low", "zone_high",
                    "score", "stop_loss", "tp1", "tp2", "tp3",
                    "status", "generated_at", "closed_at"
                )
                st.dataframe(
                    [
                        {key: row.get(key) for key in columns}
                        for row in rows
                    ],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No saved signals yet.")
        except Exception as error:
            st.error(str(error))

    with performance_tab:
        try:
            rows = get_history(1000)
            completed = [
                row for row in rows
                if row.get("status") in ("TP3_HIT", "SL_HIT")
            ]
            wins = sum(row.get("status") == "TP3_HIT" for row in completed)
            losses = sum(row.get("status") == "SL_HIT" for row in completed)
            total = len(completed)

            col1, col2, col3 = st.columns(3)
            col1.metric("Completed", total)
            col2.metric("TP3", wins)
            col3.metric("SL", losses)

            rate = wins / total * 100 if total else None
            st.metric(
                "TP3 completion rate",
                f"{rate:.1f}%" if rate is not None else "—"
            )
            st.caption(
                "Based only on persisted estimated lifecycle statuses; "
                "not a guarantee of future results."
            )
        except Exception as error:
            st.error(str(error))

    st.divider()
    st.caption(
        "Analytical signals only. No broker orders are placed. "
        "Verify spread, slippage and risk independently."
    )

if __name__ == "__main__":
    dashboard()
