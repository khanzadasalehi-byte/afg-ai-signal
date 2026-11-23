
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# =========================================================
# AFG AI GOLD PRO - QUALITY SIGNAL EDITION
# =========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO",
    page_icon="🇦🇫",
    layout="wide"
)

st.title("🇦🇫 AFG AI GOLD PRO")
st.subheader("Advanced Gold Analysis | Multi-Timeframe | Smart Signals")

API_URL = "https://api.twelvedata.com/time_series"

INTERVALS = {
    "5 Minutes": "5min",
    "15 Minutes": "15min",
    "1 Hour": "1h",
    "4 Hours": "4h"
}

MIN_CONFIDENCE = 72
MIN_SCORE = 0.28
OUTPUT_SIZE = 500

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("⚙️ Settings")

api_key = st.sidebar.text_input(
    "Twelve Data API Key",
    type="password",
    help="همان کلید قبلی Twelve Data را وارد کن."
)

if not api_key:
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]
    except Exception:
        api_key = ""

symbol = st.sidebar.selectbox(
    "Trading Symbol",
    ["XAU/USD", "EUR/USD", "BTC/USD"]
)

confidence_limit = st.sidebar.slider(
    "Minimum Signal Confidence",
    60, 95, MIN_CONFIDENCE
)

risk_percent = st.sidebar.slider(
    "Risk Per Trade (%)",
    0.5, 3.0, 1.0, 0.5
)

initial_balance = st.sidebar.number_input(
    "Backtest Starting Balance ($)",
    min_value=100.0,
    value=500.0,
    step=100.0
)

st.sidebar.caption(
    "Confidence is a model score, not a guaranteed win probability."
)

# =========================================================
# DATA
# =========================================================

@st.cache_data(ttl=60, show_spinner=False)
def get_data(symbol, interval, key, outputsize=500):
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": key,
        "timezone": "UTC",
        "order": "ASC"
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=25
    )

    response.raise_for_status()
    result = response.json()

    if "values" not in result:
        message = result.get("message", "No market data returned.")
        raise ValueError(message)

    df = pd.DataFrame(result["values"])

    required = ["datetime", "open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        raise ValueError("Invalid market data format.")

    df["datetime"] = pd.to_datetime(
        df["datetime"], utc=True, errors="coerce"
    )

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required)
    df = df.sort_values("datetime")
    df = df.drop_duplicates("datetime")
    df = df.set_index("datetime")

    if len(df) < 220:
        raise ValueError(
            f"Not enough candles: {len(df)}. Need at least 220."
        )

    # Remove the newest candle because it may still be forming.
    df = df.iloc[:-1].copy()

    if len(df) < 200:
        raise ValueError("Not enough completed candles.")

    return df


# =========================================================
# TECHNICAL INDICATORS
# =========================================================

def calculate_indicators(df):
    df = df.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]

    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi"] = df["rsi"].fillna(50)

    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()

    df["macd"] = fast - slow
    df["macd_signal"] = df["macd"].ewm(
        span=9, adjust=False
    ).mean()

    df["macd_hist"] = df["macd"] - df["macd_signal"]

    previous_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs()
    ], axis=1).max(axis=1)

    df["atr"] = tr.ewm(
        alpha=1/14, adjust=False
    ).mean()

    df["atr_pct"] = (
        df["atr"] / close.replace(0, np.nan)
    ) * 100

    df["bb_mid"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()

    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std

    # ADX calculation
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move) & (up_move > 0),
            up_move, 0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) & (down_move > 0),
            down_move, 0
        ),
        index=df.index
    )

    atr_safe = df["atr"].replace(0, np.nan)

    plus_di = 100 * plus_dm.ewm(
        alpha=1/14, adjust=False
    ).mean() / atr_safe

    minus_di = 100 * minus_dm.ewm(
        alpha=1/14, adjust=False
    ).mean() / atr_safe

    dx = (
        100 * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0, np.nan)
    )

    df["plus_di"] = plus_di.fillna(0)
    df["minus_di"] = minus_di.fillna(0)
    df["adx"] = dx.ewm(
        alpha=1/14, adjust=False
    ).mean().fillna(0)

    return df.dropna()


# =========================================================
# SESSION DETECTION
# =========================================================

def get_sessions(timestamp):
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    london = timestamp.astimezone(
        ZoneInfo("Europe/London")
    )

    new_york = timestamp.astimezone(
        ZoneInfo("America/New_York")
    )

    tokyo = timestamp.astimezone(
        ZoneInfo("Asia/Tokyo")
    )

    sessions = []

    if 8 <= london.hour < 17:
        sessions.append("London")

    if 8 <= new_york.hour < 17:
        sessions.append("New York")

    if 9 <= tokyo.hour < 18:
        sessions.append("Asia")

    return sessions if sessions else ["Quiet Market"]


def session_score(timestamp):
    sessions = get_sessions(timestamp)

    if "London" in sessions and "New York" in sessions:
        return 1.0, "London + New York"

    if "London" in sessions:
        return 0.65, "London"

    if "New York" in sessions:
        return 0.65, "New York"

    if "Asia" in sessions:
        return 0.25, "Asia"

    return 0.0, "Quiet Market"


# =========================================================
# SIGNAL MODEL
# =========================================================

def clamp(value, low=-1, high=1):
    return max(low, min(high, float(value)))


def calculate_signal(df):
    last = df.iloc[-1]

    close = float(last["close"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    ema200 = float(last["ema200"])
    rsi = float(last["rsi"])
    macd_hist = float(last["macd_hist"])
    atr = float(last["atr"])
    adx = float(last["adx"])
    plus_di = float(last["plus_di"])
    minus_di = float(last["minus_di"])

    # 1. Trend
    trend = 0

    if close > ema20 > ema50 > ema200:
        trend = 1
    elif close < ema20 < ema50 < ema200:
        trend = -1
    else:
        trend = clamp(
            ((close - ema50) / max(atr, 1e-9)) / 3
        )

    # 2. RSI
    rsi_score = clamp((rsi - 50) / 20)

    # Avoid chasing extreme RSI
    if rsi > 78:
        rsi_score *= 0.5
    elif rsi < 22:
        rsi_score *= 0.5

    # 3. MACD
    macd_score = clamp(
        (macd_hist / max(atr, 1e-9)) * 8
    )

    # 4. Directional movement
    di_score = clamp(
        (plus_di - minus_di) / 25
    )

    # 5. ADX trend quality
    adx_quality = min(max(adx / 35, 0), 1)

    # 6. Combined technical score
    technical = (
        0.38 * trend +
        0.20 * rsi_score +
        0.22 * macd_score +
        0.20 * di_score
    )

    technical = clamp(technical)

    # Session component
    sess_strength, session_name = session_score(
        df.index[-1].to_pydatetime()
    )

    # Low volatility and very high volatility are both caution flags
    volatility_ok = (
        0.02 <= float(last["atr_pct"]) <= 2.5
    )

    # Directional agreement
    components = [
        (trend, 0.38),
        (rsi_score, 0.20),
        (macd_score, 0.22),
        (di_score, 0.20)
    ]

    direction = 1 if technical > 0 else -1

    agreement = sum(
        weight for value, weight in components
        if value * direction > 0.05
    )

    opposition = sum(
        weight for value, weight in components
        if value * direction < -0.05
    )

    # Confidence is a model score, NOT win probability.
    magnitude = min(abs(technical), 1)

    confidence = (
        55 * agreement +
        30 * magnitude +
        15 * adx_quality
    )

    confidence -= opposition * 15

    if not volatility_ok:
        confidence -= 12

    if sess_strength == 0:
        confidence -= 5

    confidence = int(round(max(0, min(95, confidence))))

    # Final strict filter
    signal = "NO TRADE"

    if (
        technical >= MIN_SCORE
        and confidence >= confidence_limit
        and adx >= 16
        and volatility_ok
    ):
        signal = "BUY"

    elif (
        technical <= -MIN_SCORE
        and confidence >= confidence_limit
        and adx >= 16
        and volatility_ok
    ):
        signal = "SELL"

    # ATR-based trade plan
    stop_loss = None
    take_profit = None

    if signal == "BUY":
        stop_loss = close - 1.5 * atr
        take_profit = close + 2.5 * atr

    elif signal == "SELL":
        stop_loss = close + 1.5 * atr
        take_profit = close - 2.5 * atr

    return {
        "signal": signal,
        "confidence": confidence,
        "score": round(technical, 3),
        "price": close,
        "rsi": round(rsi, 2),
        "adx": round(adx, 2),
        "atr": round(atr, 4),
        "session": session_name,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "trend": round(trend, 2),
        "agreement": round(agreement * 100, 1)
    }


# =========================================================
# LOAD ALL TIMEFRAMES
# =========================================================

if not api_key:
    st.warning(
        "لطفاً کلید Twelve Data را در قسمت تنظیمات وارد کن."
    )
    st.stop()

all_data = {}
all_signals = {}
errors = []

with st.spinner("Downloading market data and analyzing..."):
    for label, interval in INTERVALS.items():
        try:
            raw = get_data(
                symbol, interval, api_key, OUTPUT_SIZE
            )
            analyzed = calculate_indicators(raw)

            all_data[label] = analyzed
            all_signals[label] = calculate_signal(analyzed)

        except Exception as e:
            errors.append(f"{label}: {str(e)}")

if errors:
    with st.expander("Data warnings"):
        for error in errors:
            st.error(error)

if "15 Minutes" not in all_signals:
    st.error(
        "15-minute data is required for the main signal. "
        "Check your API key, symbol and API limits."
    )
    st.stop()

# =========================================================
# MULTI TIMEFRAME CONFIRMATION
# =========================================================

main = all_signals["15 Minutes"]

direction = (
    1 if main["score"] > 0
    else -1 if main["score"] < 0
    else 0
)

available_higher = [
    all_signals[x]
    for x in ["1 Hour", "4 Hours"]
    if x in all_signals
]

higher_votes = [
    1 if item["score"] > 0 else -1
    for item in available_higher
    if abs(item["score"]) >= 0.10
]

higher_agreement = (
    sum(1 for x in higher_votes if x == direction)
    if direction != 0 else 0
)

higher_count = len(higher_votes)

mtf_confirmed = (
    higher_count == 0 or
    higher_agreement >= 1
)

final_signal = main["signal"]
final_confidence = main["confidence"]

if final_signal in ["BUY", "SELL"] and not mtf_confirmed:
    final_signal = "NO TRADE"
    final_confidence = max(0, final_confidence - 10)

# =========================================================
# DASHBOARD
# =========================================================

st.divider()
st.header("🎯 Main Trading Signal")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Gold / Market Price", f"{main['price']:.3f}")

with c2:
    st.metric("Signal", final_signal)

with c3:
    st.metric(
        "Signal Confidence",
        f"{final_confidence}%"
    )

if final_signal == "BUY":
    st.success("BUY signal detected")

elif final_signal == "SELL":
    st.error("SELL signal detected")

else:
    st.warning(
        "NO TRADE — Conditions are not strong enough."
    )

st.caption(
    "Important: Confidence is a mathematical model score, "
    "not a statistically verified probability of winning."
)

# =========================================================
# TRADE PLAN
# =========================================================

st.subheader("📌 Trade Plan")

p1, p2, p3 = st.columns(3)

p1.metric(
    "Entry Reference",
    f"{main['price']:.3f}"
)

p2.metric(
    "Stop Loss",
    f"{main['stop_loss']:.3f}"
    if main["stop_loss"] is not None else "Not available"
)

p3.metric(
    "Take Profit",
    f"{main['take_profit']:.3f}"
    if main["take_profit"] is not None else "Not available"
)

st.info(
    "Trade levels are estimates based on ATR. "
    "Check spread, execution price and position size before trading."
)

# =========================================================
# SESSION INFORMATION
# =========================================================

st.subheader("🌍 Trading Sessions")

now = datetime.now(timezone.utc)

session_cards = [
    ("Asia", now.astimezone(ZoneInfo("Asia/Tokyo"))),
    ("London", now.astimezone(ZoneInfo("Europe/London"))),
    ("New York", now.astimezone(ZoneInfo("America/New_York")))
]

cols = st.columns(3)

for col, (name, local_time) in zip(cols, session_cards):
    hour = local_time.hour
    active = (
        9 <= hour < 18 if name == "Asia"
        else 8 <= hour < 17
    )

    with col:
        st.markdown(f"**{name} Session**")
        st.write(local_time.strftime("%H:%M"))
        if active:
            st.success("Active")
        else:
            st.caption("Outside main session hours")

# =========================================================
# MULTI-TIMEFRAME TABLE
# =========================================================

st.divider()
st.header("📊 Multi-Timeframe Analysis")

rows = []

for label, result in all_signals.items():
    rows.append({
        "Timeframe": label,
        "Signal": result["signal"],
        "Confidence": f"{result['confidence']}%",
        "Score": result["score"],
        "RSI": result["rsi"],
        "ADX": result["adx"],
        "Session": result["session"]
    })

st.dataframe(
    pd.DataFrame(rows),
    use_container_width=True,
    hide_index=True
)

# =========================================================
# BACKTEST
# =========================================================

st.divider()
st.header("🧪 Historical Backtest")

st.caption(
    "Backtest uses completed 15-minute candles. "
    "Entry is at the next candle open. "
    "It is a simplified simulation, not a guarantee of live results."
)

if st.button("Run Backtest", type="primary"):
    bt = all_data["15 Minutes"].copy()

    balance = float(initial_balance)
    equity = [balance]
    trades = []

    position = None
    max_balance = balance
    max_drawdown = 0.0

    # Use only historical values available at each candle close.
    for i in range(220, len(bt) - 1):
        hist = bt.iloc[:i + 1]
        result = calculate_signal(hist)

        current = bt.iloc[i]
        next_bar = bt.iloc[i + 1]

        # Manage an existing trade first.
        if position is not None:
            exit_price = None
            exit_reason = None

            if position["side"] == "BUY":
                hit_sl = current["low"] <= position["sl"]
                hit_tp = current["high"] >= position["tp"]

                if hit_sl:
                    exit_price = position["sl"]
                    exit_reason = "Stop Loss"
                elif hit_tp:
                    exit_price = position["tp"]
                    exit_reason = "Take Profit"

            else:
                hit_sl = current["high"] >= position["sl"]
                hit_tp = current["low"] <= position["tp"]

                if hit_sl:
                    exit_price = position["sl"]
                    exit_reason = "Stop Loss"
                elif hit_tp:
                    exit_price = position["tp"]
                    exit_reason = "Take Profit"

            if exit_price is not None:
                gross = (
                    exit_price - position["entry"]
                    if position["side"] == "BUY"
                    else position["entry"] - exit_price
                )

                pnl = gross * position["quantity"]
                balance += pnl

                trades.append({
                    "Entry Time": position["time"],
                    "Exit Time": bt.index[i],
                    "Side": position["side"],
                    "Confidence": position["confidence"],
                    "Entry": position["entry"],
                    "Exit": exit_price,
                    "PnL": pnl,
                    "Reason": exit_reason
                })

                position = None

                max_balance = max(max_balance, balance)
                dd = (
                    (max_balance - balance) / max_balance * 100
                    if max_balance > 0 else 0
                )
                max_drawdown = max(max_drawdown, dd)

                equity.append(balance)
                continue

        if position is not None:
            continue

        if result["signal"] not in ["BUY", "SELL"]:
            continue

        if result["confidence"] < confidence_limit:
            continue

        entry = float(next_bar["open"])
        atr = float(result["atr"])

        if not np.isfinite(entry) or not np.isfinite(atr) or atr <= 0:
            continue

        risk_amount = balance * (risk_percent / 100)
        stop_distance = 1.5 * atr

        quantity = risk_amount / stop_distance

        # Avoid using more than available notional balance.
        quantity = min(quantity, balance / entry)

        if quantity <= 0:
            continue

        if result["signal"] == "BUY":
            sl = entry - stop_distance
            tp = entry + 2.5 * atr
        else:
            sl = entry + stop_distance
            tp = entry - 2.5 * atr

        position = {
            "side": result["signal"],
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "quantity": quantity,
            "time": bt.index[i + 1],
            "confidence": result["confidence"]
        }

    # Close any remaining position at final available close.
    if position is not None:
        last_close = float(bt.iloc[-1]["close"])

        gross = (
            last_close - position["entry"]
            if position["side"] == "BUY"
            else position["entry"] - last_close
        )

        pnl = gross * position["quantity"]
        balance += pnl

        trades.append({
            "Entry Time": position["time"],
            "Exit Time": bt.index[-1],
            "Side": position["side"],
            "Confidence": position["confidence"],
            "Entry": position["entry"],
            "Exit": last_close,
            "PnL": pnl,
            "Reason": "End of Data"
        })

        equity.append(balance)

    # Results
    if trades:
        trade_df = pd.DataFrame(trades)

        wins = int((trade_df["PnL"] > 0).sum())
        losses = int((trade_df["PnL"] <= 0).sum())
        total = len(trade_df)

        win_rate = wins / total * 100
        net_profit = balance - initial_balance

        gross_profit = trade_df.loc[
            trade_df["PnL"] > 0, "PnL"
        ].sum()

        gross_loss = abs(
            trade_df.loc[trade_df["PnL"] < 0, "PnL"].sum()
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0 else np.inf
        )

        r1, r2, r3, r4 = st.columns(4)

        r1.metric("Total Trades", total)
        r2.metric("Win Rate", f"{win_rate:.1f}%")
        r3.metric("Net P/L", f"${net_profit:.2f}")
        r4.metric(
            "Profit Factor",
            f"{profit_factor:.2f}"
            if np.isfinite(profit_factor) else "∞"
        )

        st.metric(
            "Final Balance",
            f"${balance:.2f}"
        )

        st.metric(
            "Maximum Closed-Trade Drawdown",
            f"{max_drawdown:.2f}%"
        )

        equity_df = pd.DataFrame({
            "Equity": equity
        })

        st.subheader("📈 Equity Curve")
        st.line_chart(equity_df)

        st.subheader("Trade History")
        st.dataframe(
            trade_df,
            use_container_width=True,
            hide_index=True
        )

        csv = trade_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Trade History CSV",
            data=csv,
            file_name="AFG_AI_GOLD_PRO_backtest.csv",
            mime="text/csv"
        )

    else:
        st.warning(
            "No trades passed the confidence and risk filters. "
            "Try a longer history or review the confidence threshold."
        )

# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "AFG AI GOLD PRO | Technical model | Multi-timeframe "
    "| Session analysis | ATR risk | Historical backtest"
)

st.caption(
    "For research and educational purposes. "
    "Not financial advice. Always test on a demo account first."
)
