import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone
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

st.title("🇦🇫 AFG AI GOLD PRO ELITE")
st.caption("Multi-timeframe XAU/USD analysis | Entry • Stop Loss • TP1 • TP2 • TP3")

st.warning(
    "This is an analytical and educational tool; signals do not guarantee profits. "
    "Confidence is a technical model score, not a statistically validated probability of success."
)

# -------------------------- SETTINGS --------------------------

API_URL = "https://api.twelvedata.com/time_series"
SYMBOL = "XAU/USD"
INTERVALS = {
    "5M": "5min",
    "15M": "15min",
    "1H": "1h",
    "4H": "4h",
}
LOCAL_TZ = ZoneInfo("Asia/Kabul")
TIMEOUT = 25

with st.sidebar:
    st.header("Settings")
    refresh = st.button("🔄 Refresh Market Data", use_container_width=True)
    st.caption("The API key is read from Streamlit Secrets.")
    st.divider()
    st.subheader("Risk Management Settings")
    atr_sl = st.slider("ATR Stop-Loss Multiplier", 1.0, 3.0, 1.5, 0.1)
    min_adx = st.slider("Minimum ADX for Entry", 15, 35, 20, 1)
    min_confidence = st.slider("Minimum Signal Score", 55, 90, 70, 1)
    st.caption("These settings change the analysis rules only and do not guarantee results.")

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
def get_candles(interval: str, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": SYMBOL,
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

    if len(df) < 210:
        raise ValueError(f"Not enough candles: {len(df)}; at least 210 candles are required.")

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

    # ADX measures trend strength, not direction.
    adx_ok = float(r15["adx"]) >= adx_floor
    buy_valid = (
        trend_4h == "BULLISH"
        and trend_1h == "BULLISH"
        and trend_15m != "BEARISH"
        and float(r15["rsi"]) < 70
        and adx_ok
        and buy_pullback
        and bullish_candle
        and buy_score >= confidence_floor
        and buy_score > sell_score
    )
    sell_valid = (
        trend_4h == "BEARISH"
        and trend_1h == "BEARISH"
        and trend_15m != "BULLISH"
        and float(r15["rsi"]) > 30
        and adx_ok
        and sell_pullback
        and bearish_candle
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

    entry = float(r15["close"])
    atr_value = float(r15["atr"])
    sl = tp1 = tp2 = tp3 = None

    if direction and np.isfinite(atr_value) and atr_value > 0:
        risk = atr_value * sl_multiplier
        if direction == "BUY":
            sl = entry - risk
            tp1, tp2, tp3 = entry + risk, entry + 2*risk, entry + 3*risk
        else:
            sl = entry + risk
            tp1, tp2, tp3 = entry - risk, entry - 2*risk, entry - 3*risk

    return {
        "signal": signal,
        "score": int(min(95, score)),
        "buy_score": buy_score,
        "sell_score": sell_score,
        "entry": entry,
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
    }


# -------------------------- MARKET SESSION --------------------------

def market_session():
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour
    sessions = []
    # Approximate UTC windows; daylight-saving changes can shift London/New York.
    if 0 <= hour < 9:
        sessions.append("Asia")
    if 7 <= hour < 16:
        sessions.append("London")
    if 13 <= hour < 22:
        sessions.append("New York")
    return " + ".join(sessions) if sessions else "Between major sessions"


# -------------------------- HISTORICAL BACKTEST --------------------------

def run_backtest(
    frames: dict,
    sl_multiplier: float,
    adx_floor: int,
    confidence_floor: int,
    history_limit: int = 240,
    max_holding_bars: int = 24,
):
    """
    Conservative 15M walk-forward backtest.
    Signals use only candles fully closed by the signal candle close.
    Entry is the next 15M candle open.
    If SL and TP are both touched in one candle, SL is counted first.
    Each TP is evaluated as a separate fixed-R outcome.
    """
    durations = {
        "5M": pd.Timedelta(minutes=5),
        "15M": pd.Timedelta(minutes=15),
        "1H": pd.Timedelta(hours=1),
        "4H": pd.Timedelta(hours=4),
    }

    d15 = frames["15M"].reset_index(drop=True)
    if len(d15) < max_holding_bars + 30:
        return pd.DataFrame(), "Not enough 15M candles are available for backtesting."

    first_i = max(0, len(d15) - history_limit - max_holding_bars - 1)
    last_i = len(d15) - max_holding_bars - 1
    records = []

    for i in range(first_i, last_i):
        signal_bar = d15.iloc[i]
        signal_close_time = signal_bar["datetime"] + durations["15M"]

        sliced = {}
        enough_history = True

        for label in ["5M", "15M", "1H", "4H"]:
            source = frames[label]
            if label == "15M":
                part = source[source["datetime"] <= signal_bar["datetime"]].copy()
            else:
                # Only bars that had fully closed by the 15M signal close.
                part = source[
                    source["datetime"] + durations[label] <= signal_close_time
                ].copy()

            if len(part) < 210:
                enough_history = False
                break
            sliced[label] = part.reset_index(drop=True)

        if not enough_history:
            continue

        try:
            signal = analyze_signal(
                sliced,
                sl_multiplier,
                adx_floor,
                confidence_floor,
            )
        except Exception:
            continue

        if signal["signal"] == "NO TRADE":
            continue

        # Enter at the next 15M candle open, not at the signal candle close.
        entry_index = i + 1
        entry_bar = d15.iloc[entry_index]
        entry = float(entry_bar["open"])
        atr_value = float(signal_bar["atr"])

        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        risk_distance = atr_value * sl_multiplier
        if signal["signal"] == "BUY":
            sl = entry - risk_distance
            targets = {
                "TP1": entry + risk_distance,
                "TP2": entry + 2 * risk_distance,
                "TP3": entry + 3 * risk_distance,
            }
        else:
            sl = entry + risk_distance
            targets = {
                "TP1": entry - risk_distance,
                "TP2": entry - 2 * risk_distance,
                "TP3": entry - 3 * risk_distance,
            }

        outcomes = {}
        for target_name, target_price in targets.items():
            outcome = "TIMEOUT"
            exit_index = None

            end_index = min(
                entry_index + max_holding_bars,
                len(d15) - 1
            )

            for j in range(entry_index, end_index + 1):
                bar = d15.iloc[j]
                high = float(bar["high"])
                low = float(bar["low"])

                if signal["signal"] == "BUY":
                    stop_hit = low <= sl
                    target_hit = high >= target_price
                else:
                    stop_hit = high >= sl
                    target_hit = low <= target_price

                # Conservative same-bar assumption: stop loss first.
                if stop_hit:
                    outcome = "SL"
                    exit_index = j
                    break
                if target_hit:
                    outcome = "TP"
                    exit_index = j
                    break

            outcomes[target_name] = outcome

        records.append({
            "Signal Time": signal_bar["datetime"],
            "Direction": signal["signal"],
            "Score": signal["score"],
            "Entry": entry,
            "SL": sl,
            "TP1": targets["TP1"],
            "TP2": targets["TP2"],
            "TP3": targets["TP3"],
            "TP1 Result": outcomes["TP1"],
            "TP2 Result": outcomes["TP2"],
            "TP3 Result": outcomes["TP3"],
        })

    if not records:
        return pd.DataFrame(), (
            "No evaluable signals were found in the historical period, "
            "or there was not enough history to align the timeframes."
        )

    result_df = pd.DataFrame(records).sort_values("Signal Time").reset_index(drop=True)
    return result_df, None


def backtest_stats(trades: pd.DataFrame, target_name: str):
    outcomes = trades[f"{target_name} Result"]
    total = len(outcomes)
    wins = int((outcomes == "TP").sum())
    losses = int((outcomes == "SL").sum())
    timeouts = int((outcomes == "TIMEOUT").sum())
    win_rate = (wins / total * 100) if total else 0.0
    reward_r = {"TP1": 1, "TP2": 2, "TP3": 3}[target_name]
    r_values = np.where(
        outcomes == "TP",
        reward_r,
        np.where(outcomes == "SL", -1.0, 0.0)
    )
    net_r = float(np.sum(r_values))
    avg_r = float(np.mean(r_values)) if total else 0.0

    equity = np.cumsum(r_values)
    running_peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    drawdowns = running_peak - equity
    max_dd_r = float(np.max(drawdowns)) if len(drawdowns) else 0.0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "win_rate": win_rate,
        "net_r": net_r,
        "avg_r": avg_r,
        "max_dd_r": max_dd_r,
    }


# -------------------------- LOAD & ANALYZE --------------------------

if refresh:
    st.cache_data.clear()

frames = {}
errors = []

with st.spinner("Fetching and analyzing gold market data from Twelve Data..."):
    for label, interval in INTERVALS.items():
        try:
            raw = get_candles(interval, API_KEY)
            frames[label] = add_indicators(raw)
        except Exception as exc:
            errors.append(f"{label}: {exc}")

if errors:
    st.error("Could not retrieve all market data:")
    for err in errors:
        st.write(f"- {err}")
    st.info("Check the API key, request limits, and internet connection.")
    st.stop()

result = analyze_signal(frames, atr_sl, min_adx, min_confidence)
last_price = float(frames["15M"].iloc[-1]["close"])
last_time = frames["15M"].iloc[-1]["datetime"].to_pydatetime()
local_time = last_time.astimezone(LOCAL_TZ)

# Daily safety limit: count each distinct live signal candle only once.
# The counter is kept in the current Streamlit session and resets on a new Kabul date.
MAX_DAILY_SIGNALS = 3
today_key = local_time.date().isoformat()
if st.session_state.get("daily_signal_date") != today_key:
    st.session_state["daily_signal_date"] = today_key
    st.session_state["daily_signal_keys"] = []

signal_keys = st.session_state.get("daily_signal_keys", [])
if result["signal"] in ("BUY", "SELL"):
    signal_key = f"{last_time.isoformat()}|{result['signal']}"
    if signal_key not in signal_keys:
        if len(signal_keys) >= MAX_DAILY_SIGNALS:
            result["signal"] = "NO TRADE"
            result["entry"] = None
            result["sl"] = None
            result["tp1"] = None
            result["tp2"] = None
            result["tp3"] = None
            result["daily_limit_reached"] = True
        else:
            signal_keys.append(signal_key)
            st.session_state["daily_signal_keys"] = signal_keys

result.setdefault("daily_limit_reached", False)
daily_signal_count = len(st.session_state.get("daily_signal_keys", []))

# -------------------------- TOP METRICS --------------------------

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("XAU/USD Price", f"{last_price:,.2f}")
m2.metric("Signal", result["signal"])
m3.metric("Model Score", f'{result["score"]}%')
m4.metric("Daily Signals", f"{daily_signal_count}/{MAX_DAILY_SIGNALS}")
m5.metric("Current Session", market_session())

st.caption(f"Last 15M candle time: {local_time.strftime('%Y-%m-%d %H:%M')} Kabul")

# -------------------------- SIGNAL PANEL --------------------------

st.divider()
st.subheader("🎯 Main Signal & Trade Management")

if result["signal"] == "BUY":
    st.success("BUY signal — only after reviewing market conditions and your personal risk.")
elif result["signal"] == "SELL":
    st.error("SELL signal — only after reviewing market conditions and your personal risk.")
else:
    if result.get("daily_limit_reached", False):
        st.warning("DAILY LIMIT REACHED — the maximum of 3 signals has been reached for this Kabul market day.")
    else:
        st.warning("NO TRADE — entry conditions are not fully met. Do not force a trade.")

if result["signal"] != "NO TRADE":
    cols = st.columns(5)
    values = [
        ("ENTRY", result["entry"]),
        ("STOP LOSS", result["sl"]),
        ("TAKE PROFIT 1", result["tp1"]),
        ("TAKE PROFIT 2", result["tp2"]),
        ("TAKE PROFIT 3", result["tp3"]),
    ]
    for col, (label, value) in zip(cols, values):
        col.metric(label, f"{value:,.2f}")
    st.caption(
        "SL and TP levels are calculated using 15M ATR with 1:1, 1:2, and 1:3 risk/reward ratios. "
        "Spread, slippage, and commissions are not included in these calculations."
    )
else:
    st.write(
        "The system has not identified a valid entry point at this time. "
        "SL and TP levels are intentionally hidden to avoid implying that an invalid setup is tradable."
    )

# -------------------------- MULTI-TIMEFRAME TABLE --------------------------

st.divider()
st.subheader("📊 Multi-Timeframe Analysis")

rows = []
for label in ["5M", "15M", "1H", "4H"]:
    r = frames[label].iloc[-1]
    rows.append({
        "Timeframe": label,
        "Price": round(float(r["close"]), 2),
        "EMA 20": round(float(r["ema20"]), 2),
        "EMA 50": round(float(r["ema50"]), 2),
        "EMA 200": round(float(r["ema200"]), 2),
        "RSI": round(float(r["rsi"]), 2),
        "ADX": round(float(r["adx"]), 2),
        "+DI": round(float(r["plus_di"]), 2),
        "-DI": round(float(r["minus_di"]), 2),
        "MACD": "Positive" if r["macd_hist"] > 0 else "Negative",
        "Trend": trend_of(r),
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# -------------------------- WHY SIGNAL --------------------------

st.subheader("🔎 Why the System Made This Decision")
why = [
    f"Trend 4H: {result['trend_4h']}",
    f"Trend 1H: {result['trend_1h']}",
    f"Trend 15M: {result['trend_15m']}",
    f"Buy Score: {result['buy_score']}/100",
    f"Sell Score: {result['sell_score']}/100",
    f"15M ADX Filter: {'Confirmed' if result['adx_ok'] else 'Not Confirmed'}",
    f"BUY Pullback to EMA20: {'Confirmed' if result['buy_pullback'] else 'Not Confirmed'}",
    f"SELL Pullback to EMA20: {'Confirmed' if result['sell_pullback'] else 'Not Confirmed'}",
    f"Bullish Candle Confirmation: {'Confirmed' if result['bullish_candle'] else 'Not Confirmed'}",
    f"Bearish Candle Confirmation: {'Confirmed' if result['bearish_candle'] else 'Not Confirmed'}",
]
for item in why:
    st.write(f"• {item}")

# -------------------------- BACKTEST DASHBOARD --------------------------

st.divider()
st.subheader("🧪 Historical Strategy Backtest")

st.info(
    "The backtest runs on up to the latest 240 15-minute opportunities. "
    "Entry is simulated at the next candle open, and each target is evaluated separately. "
    "This is a limited historical sample and does not prove future profitability."
)

with st.spinner("Running the backtest on historical candles..."):
    backtest_trades, backtest_error = run_backtest(
        frames,
        atr_sl,
        min_adx,
        min_confidence,
    )

if backtest_error:
    st.warning(backtest_error)
    st.caption(
        "If the data sample is small, check your Twelve Data plan limits or available history. "
        "No results or win rate are fabricated when sufficient data is unavailable."
    )
else:
    st.metric("Evaluable Signals", len(backtest_trades))

    stat_cols = st.columns(3)
    for col, target in zip(stat_cols, ["TP1", "TP2", "TP3"]):
        stats = backtest_stats(backtest_trades, target)
        col.metric(
            f"{target} — Win Rate",
            f"{stats['win_rate']:.1f}%",
            help="Hits on this target divided by all evaluable trades; timeouts are not counted as wins."
        )

    detail_rows = []
    for target in ["TP1", "TP2", "TP3"]:
        stats = backtest_stats(backtest_trades, target)
        detail_rows.append({
            "Target": target,
            "Trades": stats["total"],
            "Wins (TP)": stats["wins"],
            "Stop Losses (SL)": stats["losses"],
            "Timed Out": stats["timeouts"],
            "Win Rate": f"{stats['win_rate']:.1f}%",
            "Net R": round(stats["net_r"], 2),
            "Average R": round(stats["avg_r"], 3),
            "Maximum Drawdown (R)": round(stats["max_dd_r"], 2),
        })

    st.dataframe(
        pd.DataFrame(detail_rows),
        use_container_width=True,
        hide_index=True
    )

    buy_count = int((backtest_trades["Direction"] == "BUY").sum())
    sell_count = int((backtest_trades["Direction"] == "SELL").sum())
    b1, b2 = st.columns(2)
    b1.metric("BUY Signals", buy_count)
    b2.metric("SELL Signals", sell_count)

    with st.expander("View Backtest Trades"):
        display_trades = backtest_trades.copy()
        display_trades["Signal Time"] = (
            pd.to_datetime(display_trades["Signal Time"], utc=True)
            .dt.tz_convert(LOCAL_TZ)
            .dt.strftime("%Y-%m-%d %H:%M")
        )
        st.dataframe(
            display_trades.sort_values("Signal Time", ascending=False),
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Backtest assumptions: each target is evaluated separately with a fixed 1R risk; "
        "if SL and TP are both touched in the same candle, SL is assumed to occur first; "
        "spread, commissions, slippage, price gaps, and real order execution are not modeled. "
        "overlapping trades are counted independently, so this report is not a portfolio simulation."
    )


# -------------------------- RECENT PRICE DATA --------------------------

with st.expander("Show Latest 15-Minute Candles"):
    view = frames["15M"][["datetime", "open", "high", "low", "close", "rsi", "adx"]].tail(12).copy()
    view["datetime"] = view["datetime"].dt.strftime("%Y-%m-%d %H:%M UTC")
    st.dataframe(view.sort_values("datetime", ascending=False), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "AFG AI GOLD PRO ELITE | Data is provided by Twelve Data. "
    "Signals may change when a new candle closes. Before any trade, "
    "independently verify your broker's live price, spread, position size, and maximum account risk. "
    "Daily signal counter is session-based and resets when the Kabul date changes or the app session restarts."
)
