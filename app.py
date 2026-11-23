import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ==========================================================
# AFG AI GOLD PRO ELITE
# Gold multi-timeframe analysis with Entry, SL and TP1-TP3
# Data provider: Twelve Data (XAU/USD)
# ==========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO ELITE",
    page_icon="🇦🇫",
    layout="wide"
)

# -------------------------- ELITE VISUAL THEME --------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root { --gold: #d6ad55; --gold2: #f4d58a; --ink: #0a0e16; --panel: #111827; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: radial-gradient(circle at 12% 0%, #20283a 0%, #0b101a 42%, #080b12 100%); color: #edf1f7; }
.block-container { max-width: 1500px; padding-top: 1.4rem; padding-bottom: 3rem; }
[data-testid="stHeader"] { background: rgba(8,11,18,.78); }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#111827,#090d15); border-right: 1px solid rgba(214,173,85,.25); }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color: var(--gold2); }
.hero { padding: 25px 28px; border: 1px solid rgba(214,173,85,.42); border-radius: 20px; background: linear-gradient(115deg,rgba(214,173,85,.16),rgba(17,24,39,.94) 48%,rgba(10,14,22,.96)); box-shadow: 0 14px 40px rgba(0,0,0,.28); margin-bottom: 18px; }
.hero-kicker { color: var(--gold2); font-size: .72rem; font-weight: 800; letter-spacing: .22em; text-transform: uppercase; }
.hero-title { color: #fff; font-size: clamp(1.65rem,3vw,2.55rem); line-height: 1.12; font-weight: 900; margin: 7px 0; }
.hero-sub { color: #aeb8c8; font-size: .92rem; }
.hero-chip { display:inline-block; border:1px solid rgba(244,213,138,.35); border-radius:999px; color:#f4d58a; padding:5px 11px; font-size:.72rem; margin:12px 6px 0 0; }
h1,h2,h3 { letter-spacing: -.025em; }
h2 { color: #f4d58a !important; }
h3 { color: #e7c77f !important; }
[data-testid="stMetric"] { background: linear-gradient(145deg,rgba(25,34,50,.96),rgba(13,19,30,.96)); border:1px solid rgba(214,173,85,.22); padding:15px 17px; border-radius:15px; box-shadow:0 8px 24px rgba(0,0,0,.16); }
[data-testid="stMetricLabel"] { color:#aeb8c8 !important; font-size:.78rem !important; }
[data-testid="stMetricValue"] {
    color:#fff !important;
    font-weight:800 !important;
    font-size:clamp(1rem, 2.1vw, 1.75rem) !important;
    line-height:1.25 !important;
    white-space:normal !important;
    overflow:visible !important;
    text-overflow:clip !important;
    word-break:normal !important;
    overflow-wrap:anywhere !important;
}
[data-testid="stMetricValue"] > div {
    white-space:normal !important;
    overflow:visible !important;
    text-overflow:clip !important;
}
@media (max-width: 900px) {
    div[data-testid="stHorizontalBlock"] {
        flex-wrap:wrap !important;
        gap:0.65rem !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        flex:1 1 180px !important;
        min-width: min(180px, 100%) !important;
    }
}
@media (max-width: 480px) {
    [data-testid="stMetric"] {
        padding:12px 13px !important;
    }
    [data-testid="stMetricValue"] {
        font-size:1.15rem !important;
    }
}
[data-testid="stMetricDelta"] { color:#d6ad55 !important; }
.stButton>button { border:1px solid rgba(214,173,85,.55); border-radius:11px; background:linear-gradient(110deg,#b88b35,#e6c574); color:#11151d; font-weight:800; min-height:2.7rem; }
.stButton>button:hover { border-color:#f4d58a; color:#080b12; box-shadow:0 0 18px rgba(214,173,85,.25); }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid rgba(214,173,85,.18); border-radius:12px; overflow:hidden; }
[data-testid="stExpander"] { border:1px solid rgba(214,173,85,.22); border-radius:13px; background:rgba(17,24,39,.55); }
hr { border-color:rgba(214,173,85,.22) !important; }
.stAlert { border-radius:13px; }
small, .stCaption { color:#9ba8ba !important; }
</style>
<div class="hero">
  <div class="hero-kicker">🇦🇫 AFG FINANCIAL INTELLIGENCE</div>
  <div class="hero-title">GOLD PRO <span style="color:#e7c77f">ELITE</span></div>
  <div class="hero-sub">Automatic BUY LIMIT / SELL LIMIT · XAU/USD</div>
</div>
""", unsafe_allow_html=True)

st.caption("XAU/USD · Closed-candle analysis · BUY LIMIT / SELL LIMIT")
st.caption("Technical score is not a win probability. Signals are suggestions only; verify prices and risk with your broker.")

# -------------------------- SETTINGS --------------------------

API_URL = "https://api.twelvedata.com/time_series"
SYMBOLS = {"GOLD": "XAU/USD", "BTC": "BTC/USD"}
INTERVALS = {
    "5M": "5min",
    "15M": "15min",
    "1H": "1h",
    "4H": "4h",
}
INTERVAL_DELTAS = {
    "5min": pd.Timedelta(minutes=5),
    "15min": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
}
LOCAL_TZ = ZoneInfo("Asia/Kabul")
TIMEOUT = 25

with st.sidebar:
    st.markdown("### 🇦🇫 AFG GOLD PRO")
    st.caption("XAU/USD · LIMIT SIGNALS")
    refresh = st.button("🔄 Refresh Market Data", use_container_width=True)
    st.caption("Data: Twelve Data · Daily signal cap: 3")

try:
    API_KEY = st.secrets["TWELVE_DATA_API_KEY"]
except Exception:
    API_KEY = ""

if not API_KEY:
    st.error(
        "API key not found. In Streamlit Settings → Secrets, "
        "keep the TWELVE_DATA_API_KEY secret configured as before."
    )
    st.stop()


# -------------------------- DATA --------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_candles(symbol: str, interval: str, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 1000,
        "apikey": api_key,
        "timezone": "UTC",
        "format": "JSON",
    }
    response = requests.get(API_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    if "values" not in payload:
        message = payload.get("message") or payload.get("code") or str(payload)
        raise ValueError(f"Twelve Data: {message}")

    df = pd.DataFrame(payload["values"])
    required = ["datetime", "open", "high", "low", "close"]
    if any(col not in df.columns for col in required):
        raise ValueError("The received data has an invalid structure.")

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=required).sort_values("datetime").reset_index(drop=True)

    # Twelve Data timestamps candle openings. Keep only candles whose full
    # interval has elapsed, with a small safety buffer for delayed updates.
    interval_delta = INTERVAL_DELTAS[interval]
    closed_before = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=2)
    df = df[df["datetime"] + interval_delta <= closed_before].reset_index(drop=True)

    if len(df) < 210:
        raise ValueError(
            f"Not enough fully closed candles: {len(df)}; at least 210 are required."
        )

    return df


# -------------------------- INDICATORS --------------------------

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()
    d["ema200"] = d["close"].ewm(span=200, adjust=False).mean()

    delta = d["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))
    d["rsi"] = d["rsi"].fillna(50)

    fast = d["close"].ewm(span=12, adjust=False).mean()
    slow = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = fast - slow
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]

    prev_close = d["close"].shift(1)
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - prev_close).abs(),
        (d["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    up_move = d["high"].diff()
    down_move = -d["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=d.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=d.index
    )
    atr_safe = d["atr"].replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    d["plus_di"] = plus_di.fillna(0)
    d["minus_di"] = minus_di.fillna(0)
    d["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean().fillna(0)

    return d


def trend_of(row) -> str:
    if row["close"] > row["ema50"] and row["ema50"] > row["ema200"]:
        return "BULLISH"
    if row["close"] < row["ema50"] and row["ema50"] < row["ema200"]:
        return "BEARISH"
    return "MIXED"


def analyze_signal(data: dict, sl_multiplier: float, adx_floor: int, confidence_floor: int):
    # Higher timeframe direction filter: 4H + 1H must agree.
    r5 = data["5M"].iloc[-1]
    r15 = data["15M"].iloc[-1]
    r1h = data["1H"].iloc[-1]
    r4h = data["4H"].iloc[-1]

    trend_1h = trend_of(r1h)
    trend_4h = trend_of(r4h)
    trend_15m = trend_of(r15)

    buy_score = 0
    sell_score = 0

    # Higher timeframe agreement
    if trend_4h == "BULLISH": buy_score += 20
    if trend_1h == "BULLISH": buy_score += 20
    if trend_4h == "BEARISH": sell_score += 20
    if trend_1h == "BEARISH": sell_score += 20

    # 15m setup
    if r15["close"] > r15["ema20"]: buy_score += 10
    if r15["ema20"] > r15["ema50"]: buy_score += 10
    if r15["close"] < r15["ema20"]: sell_score += 10
    if r15["ema20"] < r15["ema50"]: sell_score += 10

    if 50 < r15["rsi"] < 68: buy_score += 10
    if 32 < r15["rsi"] < 50: sell_score += 10
    if r15["macd_hist"] > 0: buy_score += 10
    if r15["macd_hist"] < 0: sell_score += 10
    if r15["plus_di"] > r15["minus_di"]: buy_score += 10
    if r15["minus_di"] > r15["plus_di"]: sell_score += 10

    # 5m confirmation, deliberately lower weight
    if r5["close"] > r5["ema20"] and r5["macd_hist"] > 0: buy_score += 10
    if r5["close"] < r5["ema20"] and r5["macd_hist"] < 0: sell_score += 10

    # Pullback + candle confirmation on 15M.
    # A valid pullback must approach EMA20 within 0.35 ATR during the last
    # six candles, then the latest candle must close back in the trend direction.
    recent = data["15M"].tail(6).copy()
    atr_now = float(r15["atr"]) if np.isfinite(r15["atr"]) else 0.0
    tolerance = max(atr_now * 0.35, 0.0)

    buy_pullback = False
    sell_pullback = False
    bullish_candle = False
    bearish_candle = False

    if len(recent) >= 2 and atr_now > 0:
        buy_touch = (
            (recent["low"] <= recent["ema20"] + tolerance)
            & (recent["low"] >= recent["ema20"] - tolerance * 1.5)
        ).any()
        sell_touch = (
            (recent["high"] >= recent["ema20"] - tolerance)
            & (recent["high"] <= recent["ema20"] + tolerance * 1.5)
        ).any()

        candle_range = max(float(r15["high"] - r15["low"]), 1e-9)
        candle_body = abs(float(r15["close"] - r15["open"]))
        bullish_candle = (
            float(r15["close"]) > float(r15["open"])
            and float(r15["close"]) > float(recent.iloc[-2]["close"])
            and (float(r15["high"]) - float(r15["close"])) / candle_range <= 0.40
            and candle_body / candle_range >= 0.25
        )
        bearish_candle = (
            float(r15["close"]) < float(r15["open"])
            and float(r15["close"]) < float(recent.iloc[-2]["close"])
            and (float(r15["close"]) - float(r15["low"])) / candle_range <= 0.40
            and candle_body / candle_range >= 0.25
        )

        buy_pullback = bool(
            buy_touch
            and float(r15["close"]) > float(r15["ema20"])
            and float(r15["ema20"]) > float(r15["ema50"])
        )
        sell_pullback = bool(
            sell_touch
            and float(r15["close"]) < float(r15["ema20"])
            and float(r15["ema20"]) < float(r15["ema50"])
        )

    # ADX measures trend strength, not direction. A trade must also have
    # momentum confirmation on 5M and directional structure on 15M.
    adx_ok = float(r15["adx"]) >= adx_floor
    five_min_buy_confirm = (
        float(r5["close"]) > float(r5["ema20"])
        and float(r5["macd_hist"]) > 0
    )
    five_min_sell_confirm = (
        float(r5["close"]) < float(r5["ema20"])
        and float(r5["macd_hist"]) < 0
    )
    buy_valid = (
        trend_4h == "BULLISH"
        and trend_1h == "BULLISH"
        and trend_15m == "BULLISH"
        and 50 < float(r15["rsi"]) < 68
        and adx_ok
        and buy_pullback
        and bullish_candle
        and five_min_buy_confirm
        and buy_score >= confidence_floor
        and buy_score > sell_score
    )
    sell_valid = (
        trend_4h == "BEARISH"
        and trend_1h == "BEARISH"
        and trend_15m == "BEARISH"
        and 32 < float(r15["rsi"]) < 50
        and adx_ok
        and sell_pullback
        and bearish_candle
        and five_min_sell_confirm
        and sell_score >= confidence_floor
        and sell_score > buy_score
    )

    signal = "NO TRADE"
    score = max(buy_score, sell_score)
    direction = None

    if buy_valid:
        signal, direction = "BUY", "BUY"
        score = buy_score
    elif sell_valid:
        signal, direction = "SELL", "SELL"
        score = sell_score

    current_price = float(r15["close"])
    atr_value = float(r15["atr"])
    entry = current_price
    sl = tp1 = tp2 = tp3 = None
    order_type = None
    limit_distance_atr = None

    # AI-calculated pending limit order: anchor the retracement near EMA20,
    # then require the limit to remain on the correct side of market price.
    if direction and np.isfinite(atr_value) and atr_value > 0:
        recent_structure = data["15M"].tail(12)
        ema20_value = float(r15["ema20"])
        if direction == "BUY":
            entry = ema20_value + 0.08 * atr_value
            limit_distance_atr = (current_price - entry) / atr_value
            swing_low = float(recent_structure["low"].min())
            sl = min(swing_low - 0.15 * atr_value, entry - 0.35 * atr_value)
            order_type = "BUY LIMIT"
            risk = entry - sl
            valid_limit = 0.03 <= limit_distance_atr <= 0.75
            valid_risk = 0.35 * atr_value <= risk <= 2.0 * atr_value
            if valid_limit and valid_risk:
                tp1, tp2, tp3 = entry + risk, entry + 2 * risk, entry + 3 * risk
            else:
                direction = None
        else:
            entry = ema20_value - 0.08 * atr_value
            limit_distance_atr = (entry - current_price) / atr_value
            swing_high = float(recent_structure["high"].max())
            sl = max(swing_high + 0.15 * atr_value, entry + 0.35 * atr_value)
            order_type = "SELL LIMIT"
            risk = sl - entry
            valid_limit = 0.03 <= limit_distance_atr <= 0.75
            valid_risk = 0.35 * atr_value <= risk <= 2.0 * atr_value
            if valid_limit and valid_risk:
                tp1, tp2, tp3 = entry - risk, entry - 2 * risk, entry - 3 * risk
            else:
                direction = None

        if direction is None:
            signal = "NO TRADE"
            entry = current_price
            sl = tp1 = tp2 = tp3 = None
            order_type = None

    return {
        "signal": signal,
        "score": int(min(100, score)),
        "buy_score": buy_score,
        "sell_score": sell_score,
        "entry": entry,
        "current_price": current_price,
        "order_type": order_type,
        "limit_distance_atr": limit_distance_atr,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "trend_4h": trend_4h,
        "trend_1h": trend_1h,
        "trend_15m": trend_15m,
        "adx_ok": adx_ok,
        "buy_pullback": buy_pullback,
        "sell_pullback": sell_pullback,
        "bullish_candle": bullish_candle,
        "bearish_candle": bearish_candle,
        "five_min_buy_confirm": five_min_buy_confirm,
        "five_min_sell_confirm": five_min_sell_confirm,
    }


# -------------------------- MARKET SESSION --------------------------

def market_session():
    # Local exchange clocks automatically account for daylight-saving changes.
    tokyo_hour = datetime.now(ZoneInfo("Asia/Tokyo")).hour
    london_hour = datetime.now(ZoneInfo("Europe/London")).hour
    new_york_hour = datetime.now(ZoneInfo("America/New_York")).hour

    sessions = []
    if 9 <= tokyo_hour < 18:
        sessions.append("Asia")
    if 8 <= london_hour < 17:
        sessions.append("London")
    if 8 <= new_york_hour < 17:
        sessions.append("New York")
    return " + ".join(sessions) if sessions else "Between major sessions"


# -------------------------- LOAD & ANALYZE --------------------------

if refresh:
    st.cache_data.clear()

market = {}
errors = []
with st.spinner("Fetching Gold and Bitcoin market data..."):
    for asset, symbol in SYMBOLS.items():
        asset_frames = {}
        for label, interval in INTERVALS.items():
            try:
                raw = get_candles(symbol, interval, API_KEY)
                asset_frames[label] = add_indicators(raw)
            except Exception as exc:
                errors.append(f"{asset} {label}: {exc}")
        if len(asset_frames) == len(INTERVALS):
            market[asset] = asset_frames

if errors:
    st.error("Some market data could not be loaded:")
    for err in errors:
        st.write(f"- {err}")
    st.info("Check Twelve Data symbol access, API limits and connection. Both assets require all four timeframes.")
    st.stop()

results = {}
for asset, asset_frames in market.items():
    res = analyze_signal(asset_frames, 1.5, 20, 70)
    last_time = asset_frames["15M"].iloc[-1]["datetime"].to_pydatetime()
    latest_close = last_time + timedelta(minutes=15)
    age = datetime.now(timezone.utc) - latest_close
    stale = age > timedelta(minutes=45)
    res["stale_data"] = stale
    if stale:
        res.update({"signal": "NO TRADE", "entry": None, "order_type": None,
                    "sl": None, "tp1": None, "tp2": None, "tp3": None})
    res["last_time"] = last_time
    res["last_price"] = float(asset_frames["15M"].iloc[-1]["close"])
    # A setup is valid for up to 45 minutes after the last closed 15M candle.
    expiry = latest_close + timedelta(minutes=45)
    remaining = max(0, int((expiry - datetime.now(timezone.utc)).total_seconds()))
    res["valid_until"] = expiry.astimezone(LOCAL_TZ)
    res["valid_remaining"] = remaining
    results[asset] = res

# Shared daily cap: no more than 3 new Gold + BTC setups per Kabul day.
MAX_DAILY_SIGNALS = 3
today_key = datetime.now(LOCAL_TZ).date().isoformat()
if st.session_state.get("daily_signal_date") != today_key:
    st.session_state["daily_signal_date"] = today_key
    st.session_state["daily_signal_keys"] = []
signal_keys = st.session_state.get("daily_signal_keys", [])
for asset, res in results.items():
    if res["signal"] in ("BUY", "SELL"):
        key = f"{asset}|{res['last_time'].isoformat()}|{res['signal']}"
        if key not in signal_keys:
            if len(signal_keys) >= MAX_DAILY_SIGNALS:
                res.update({"signal": "NO TRADE", "entry": None, "order_type": None,
                            "sl": None, "tp1": None, "tp2": None, "tp3": None,
                            "daily_limit_reached": True})
            else:
                signal_keys.append(key)
                st.session_state["daily_signal_keys"] = signal_keys
    res.setdefault("daily_limit_reached", False)
daily_signal_count = len(st.session_state.get("daily_signal_keys", []))

# -------------------------- TOP METRICS --------------------------

gold = results["GOLD"]
btc = results["BTC"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("XAU/USD", f"{gold['last_price']:,.2f}")
m2.metric("GOLD SIGNAL", gold["signal"])
m3.metric("BTC/USD", f"{btc['last_price']:,.2f}")
m4.metric("DAILY SIGNALS", f"{daily_signal_count}/{MAX_DAILY_SIGNALS}")

# -------------------------- SIGNAL PANELS --------------------------

for asset, title in [("GOLD", "XAU/USD GOLD"), ("BTC", "BTC/USD BITCOIN")]:
    res = results[asset]
    asset_frames = market[asset]
    st.divider()
    st.subheader(f"🎯 {title} SIGNAL")
    if res["signal"] == "BUY":
        st.success("BUY LIMIT setup calculated by the AI — pending until price reaches entry.")
    elif res["signal"] == "SELL":
        st.error("SELL LIMIT setup calculated by the AI — pending until price reaches entry.")
    elif res.get("stale_data"):
        st.warning("STALE DATA — new signals are disabled until fresh market data arrives.")
    elif res.get("daily_limit_reached"):
        st.warning("DAILY LIMIT REACHED — maximum 3 combined Gold and BTC signals for today.")
    else:
        st.warning("NO TRADE — required conditions are not fully aligned.")

    if res["signal"] != "NO TRADE":
        st.info(f"{res['order_type']} · PENDING · Current price: {res['current_price']:,.2f}")
        cols = st.columns(5)
        values = [("LIMIT ENTRY", res["entry"]), ("STOP LOSS", res["sl"]),
                  ("TAKE PROFIT 1", res["tp1"]), ("TAKE PROFIT 2", res["tp2"]),
                  ("TAKE PROFIT 3", res["tp3"])]
        for col, (label, value) in zip(cols, values):
            col.metric(label, f"{value:,.2f}")
        st.caption(f"Technical score: {res['score']}% · Signal valid until {res['valid_until'].strftime('%H:%M')} Kabul time · {res['valid_remaining']//60} min remaining")
    else:
        st.caption("Signal validity: Not applicable — no active setup.")

# -------------------------- TRADING SESSIONS --------------------------

st.divider()
st.subheader("🌍 TRADING SESSIONS")
now_utc = datetime.now(timezone.utc)
tokyo_now = now_utc.astimezone(ZoneInfo("Asia/Tokyo"))
london_now = now_utc.astimezone(ZoneInfo("Europe/London"))
ny_now = now_utc.astimezone(ZoneInfo("America/New_York"))
session_states = [
    ("ASIA", 9 <= tokyo_now.hour < 18, tokyo_now.strftime('%H:%M')),
    ("LONDON", 8 <= london_now.hour < 17, london_now.strftime('%H:%M')),
    ("NEW YORK", 8 <= ny_now.hour < 17, ny_now.strftime('%H:%M')),
]
sc = st.columns(3)
for col, (name, active, clock) in zip(sc, session_states):
    col.metric(name, "OPEN" if active else "CLOSED", f"Local exchange time {clock}")

# -------------------------- MARKET OVERVIEW --------------------------

st.divider()
st.subheader("📊 MARKET OVERVIEW")
for asset, title in [("GOLD", "XAU/USD"), ("BTC", "BTC/USD")]:
    st.markdown(f"**{title}**")
    rows = []
    for label in ["5M", "15M", "1H", "4H"]:
        r = market[asset][label].iloc[-1]
        rows.append({"Timeframe": label, "Price": round(float(r["close"]), 2),
                     "Trend": trend_of(r), "RSI": round(float(r["rsi"]), 1),
                     "ADX": round(float(r["adx"]), 1)})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with st.expander("How the signal is calculated"):
    st.write("The system checks 4H and 1H trend direction, 15M trend and pullback, RSI, ADX, candle confirmation and 5M momentum. It only shows a limit setup when the entry is on the correct side of the current price and the stop distance is acceptable.")
    st.caption("Maximum 3 combined Gold and BTC signals per Kabul day in this app session. The signal timer is a technical validity estimate, not a broker order expiry; verify all prices with your broker. This app does not place trades.")
