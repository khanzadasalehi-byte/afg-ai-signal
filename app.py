
import streamlit as st
import pandas as pd
import numpy as np
import requests

# =====================================
# AFG AI GOLD PRO
# =====================================

st.set_page_config(
    page_title="AFG AI GOLD PRO",
    page_icon="🇦🇫",
    layout="wide"
)

st.title("🇦🇫 AFG AI GOLD PRO")
st.subheader("AI-Powered Gold & Crypto Technical Analysis")

TIMEOUT = 20
HEADERS = {"User-Agent": "AFG-AI-GOLD-PRO/2.0"}


# =====================================
# DATA CONNECTION
# =====================================

def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


# =====================================
# TECHNICAL INDICATORS
# =====================================

def add_indicators(df):

    df = df.copy()

    for col in ["high", "low", "close"]:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    df = df.dropna(
        subset=["high", "low", "close"]
    ).reset_index(drop=True)

    if len(df) < 30:
        raise ValueError("Not enough market history.")

    # EMA
    df["EMA20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    df["EMA200"] = df["close"].ewm(
        span=200, adjust=False
    ).mean()

    # RSI
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14, adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14, adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    df.loc[
        (avg_loss == 0) & (avg_gain > 0), "RSI"
    ] = 100

    df.loc[
        (avg_loss == 0) & (avg_gain == 0), "RSI"
    ] = 50

    # MACD
    ema12 = df["close"].ewm(
        span=12, adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26, adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["MACD_signal"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    df["MACD_hist"] = (
        df["MACD"] - df["MACD_signal"]
    )

    # ATR
    previous_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(
        alpha=1/14, adjust=False
    ).mean()

    # Bollinger Bands
    middle = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()

    df["BB_middle"] = middle
    df["BB_upper"] = middle + 2 * std
    df["BB_lower"] = middle - 2 * std

    # ADX
    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0), 0
    )

    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0), 0
    )

    atr_safe = df["ATR"].replace(0, np.nan)

    plus_di = (
        100 * plus_dm.ewm(alpha=1/14, adjust=False).mean()
        / atr_safe
    )

    minus_di = (
        100 * minus_dm.ewm(alpha=1/14, adjust=False).mean()
        / atr_safe
    )

    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di

    di_sum = (plus_di + minus_di).replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / di_sum

    df["ADX"] = dx.ewm(
        alpha=1/14, adjust=False
    ).mean()

    return df


# =====================================
# GOLD DATA
# =====================================

def get_gold_data():

    spot = get_json(
        "https://xaus.com/api/v1/spot"
    )

    history = get_json(
        "https://xaus.com/api/v1/history"
    )

    if spot.get("stale") is True:
        raise ValueError(
            "Gold price is stale. Please try again later."
        )

    if spot.get("data_state", {}).get("status") == "unavailable":
        raise ValueError("Gold price is unavailable.")

    points = history.get("points", [])

    if len(points) < 55:
        raise ValueError(
            "Not enough gold history data."
        )

    df = pd.DataFrame(points)

    df["time"] = pd.to_datetime(
        df["d"], errors="coerce"
    )

    df = df.rename(columns={
        "c": "close",
        "h": "high",
        "l": "low"
    })

    df = df.dropna(subset=["time"])

    df = df.sort_values("time")

    df = add_indicators(df)

    live_price = float(spot["spot_usd_oz"])

    return (
        df,
        live_price,
        spot.get("price_as_of") or spot.get("updated_at"),
        "XAUS XAU/USD"
    )


# =====================================
# CRYPTO DATA
# =====================================

def get_crypto_data(symbol, interval):

    errors = []

    bybit_intervals = {
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D"
    }

    # Try Bybit
    try:

        payload = get_json(
            "https://api.bybit.com/v5/market/kline",
            {
                "category": "spot",
                "symbol": symbol,
                "interval": bybit_intervals[interval],
                "limit": 200
            }
        )

        if payload.get("retCode") != 0:
            raise ValueError(
                payload.get("retMsg", "Bybit error")
            )

        rows = payload.get(
            "result", {}
        ).get("list", [])

        if not rows:
            raise ValueError("No candles from Bybit.")

        df = pd.DataFrame(
            rows,
            columns=[
                "time", "open", "high", "low",
                "close", "volume", "turnover"
            ]
        )

        df["time"] = pd.to_datetime(
            pd.to_numeric(df["time"]),
            unit="ms"
        )

        df = df.sort_values("time")

        df = add_indicators(df)

        return (
            df,
            float(df["close"].iloc[-1]),
            "Bybit spot"
        )

    except Exception as exc:
        errors.append(f"Bybit: {exc}")

    # Binance fallback
    try:

        payload = get_json(
            "https://api.binance.com/api/v3/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": 200
            }
        )

        df = pd.DataFrame(
            payload,
            columns=[
                "time", "open", "high", "low",
                "close", "volume", "close_time",
                "quote_volume", "trades",
                "buy_volume", "buy_quote", "ignore"
            ]
        )

        df["time"] = pd.to_datetime(
            pd.to_numeric(df["time"]),
            unit="ms"
        )

        df = df.sort_values("time")

        df = add_indicators(df)

        return (
            df,
            float(df["close"].iloc[-1]),
            "Binance spot"
        )

    except Exception as exc:
        errors.append(f"Binance: {exc}")

    raise RuntimeError(
        "Crypto data unavailable. " + " | ".join(errors)
    )


# =====================================
# AI-STYLE SIGNAL ENGINE
# =====================================

def analyze_signal(df, price):

    latest = df.iloc[-1]

    required = [
        "EMA20", "EMA50", "EMA200",
        "RSI", "MACD_hist", "ATR",
        "ADX", "PLUS_DI", "MINUS_DI"
    ]

    if latest[required].isna().any():
        return None

    ema20 = float(latest["EMA20"])
    ema50 = float(latest["EMA50"])
    ema200 = float(latest["EMA200"])

    rsi = float(latest["RSI"])
    macd = float(latest["MACD_hist"])
    atr = float(latest["ATR"])
    adx = float(latest["ADX"])

    plus_di = float(latest["PLUS_DI"])
    minus_di = float(latest["MINUS_DI"])

    if atr <= 0:
        return None

    score = 0
    reasons = []

    # Trend analysis
    if ema20 > ema50 > ema200:
        score += 2
        reasons.append("Strong bullish EMA alignment")

    elif ema20 < ema50 < ema200:
        score -= 2
        reasons.append("Strong bearish EMA alignment")

    # Price position
    if price > ema20:
        score += 1
        reasons.append("Price above EMA20")

    elif price < ema20:
        score -= 1
        reasons.append("Price below EMA20")

    # RSI
    if 50 < rsi < 70:
        score += 1
        reasons.append("Bullish RSI momentum")

    elif 30 < rsi < 50:
        score -= 1
        reasons.append("Bearish RSI momentum")

    elif rsi >= 70:
        reasons.append("RSI overbought warning")

    elif rsi <= 30:
        reasons.append("RSI oversold warning")

    # MACD
    if macd > 0:
        score += 1
        reasons.append("Positive MACD momentum")

    elif macd < 0:
        score -= 1
        reasons.append("Negative MACD momentum")

    # ADX and directional movement
    if adx >= 20:

        if plus_di > minus_di:
            score += 1
            reasons.append("ADX confirms bullish direction")

        elif minus_di > plus_di:
            score -= 1
            reasons.append("ADX confirms bearish direction")

    else:
        reasons.append("Weak trend strength")

    # Final decision
    if score >= 4:
        signal = "BUY"

    elif score <= -4:
        signal = "SELL"

    else:
        signal = "NO TRADE"

    return {
        "signal": signal,
        "score": score,
        "reasons": reasons,
        "rsi": rsi,
        "adx": adx,
        "atr": atr,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200
    }


# =====================================
# DISPLAY ANALYSIS
# =====================================

def render_analysis(
    df, price, source, timeframe, as_of=None
):

    if len(df) < 55:
        st.error("Not enough candle history.")
        return

    result = analyze_signal(df, price)

    if result is None:
        st.error(
            "Indicator calculations are incomplete. "
            "More historical candles are needed."
        )
        return

    latest = df.iloc[-1]

    st.caption(
        f"Source: {source} | Timeframe: {timeframe}"
        + (f" | Updated: {as_of}" if as_of else "")
    )

    # Market information
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Price", f"${price:,.4f}")
    c2.metric("RSI", f"{result['rsi']:.2f}")
    c3.metric("ADX", f"{result['adx']:.2f}")
    c4.metric("ATR", f"{result['atr']:.4f}")

    # EMA information
    st.subheader("Trend Indicators")

    a, b, c = st.columns(3)

    a.metric("EMA20", f"${result['ema20']:,.4f}")
    b.metric("EMA50", f"${result['ema50']:,.4f}")
    c.metric("EMA200", f"${result['ema200']:,.4f}")

    # Chart
    st.subheader("Technical Market Chart")

    chart_columns = [
        "close", "EMA20", "EMA50", "EMA200"
    ]

    st.line_chart(
        df.set_index("time")[chart_columns].tail(100)
    )

    st.subheader("Bollinger Bands")

    st.line_chart(
        df.set_index("time")[
            ["close", "BB_upper", "BB_middle", "BB_lower"]
        ].tail(100)
    )

    st.subheader("MACD Analysis")

    st.line_chart(
        df.set_index("time")[
            ["MACD", "MACD_signal", "MACD_hist"]
        ].tail(100)
    )

    # Signal
    st.divider()
    st.subheader("AFG AI Signal Engine")

    signal = result["signal"]
    score = result["score"]

    if signal == "BUY":
        st.success("BUY — Bullish conditions detected")

    elif signal == "SELL":
        st.error("SELL — Bearish conditions detected")

    else:
        st.warning("NO TRADE — Wait for confirmation")

    st.metric("Technical Score", f"{score:+d} / 6")

    st.write("**Analysis reasons:**")

    for reason in result["reasons"]:
        st.write("- " + reason)

    if signal == "NO TRADE":
        st.info(
            "No active trade levels are suggested. "
            "Wait for a stronger and clearer setup."
        )
        return

    # Risk management
    atr = result["atr"]

    if signal == "BUY":

        sl = price - 1.5 * atr
        risk = price - sl

        tp1 = price + risk
        tp2 = price + 2 * risk
        tp3 = price + 3 * risk

    else:

        sl = price + 1.5 * atr
        risk = sl - price

        tp1 = price - risk
        tp2 = price - 2 * risk
        tp3 = price - 3 * risk

    st.subheader("Trade Plan (Illustrative)")

    p1, p2 = st.columns(2)

    p1.metric("Entry", f"${price:,.4f}")
    p2.metric("Stop Loss", f"${sl:,.4f}")

    p3, p4, p5 = st.columns(3)

    p3.metric("Take Profit 1", f"${tp1:,.4f}")
    p4.metric("Take Profit 2", f"${tp2:,.4f}")
    p5.metric("Take Profit 3", f"${tp3:,.4f}")

    st.caption(
        "SL uses 1.5 ATR. Targets represent 1R, 2R and 3R. "
        "These are illustrative levels, not guaranteed results."
    )


# =====================================
# MAIN DASHBOARD
# =====================================

st.sidebar.title("AFG AI Settings")

market = st.radio(
    "Select Market",
    ["Gold (XAU/USD)", "Cryptocurrency"]
)

if market == "Gold (XAU/USD)":

    st.info(
        "Gold currently uses daily historical candles. "
        "Intraday gold scalping is not yet supported."
    )

    if st.button("Analyze Gold", type="primary"):

        try:
            with st.spinner("Analyzing gold market..."):

                df, price, as_of, source = get_gold_data()

            render_analysis(
                df, price, source, "1D", as_of
            )

        except Exception as exc:
            st.error(f"Gold data error: {exc}")

else:

    crypto_symbols = {
        "Bitcoin": "BTCUSDT",
        "Ethereum": "ETHUSDT",
        "BNB": "BNBUSDT",
        "Solana": "SOLUSDT"
    }

    coin = st.selectbox(
        "Select Cryptocurrency",
        list(crypto_symbols.keys())
    )

    interval = st.selectbox(
        "Select Timeframe",
        ["15m", "1h", "4h", "1d"]
    )

    if st.button("Analyze Crypto", type="primary"):

        try:
            with st.spinner("Analyzing crypto market..."):

                df, price, source = get_crypto_data(
                    crypto_symbols[coin], interval
                )

            render_analysis(
                df, price, source, interval
            )

        except Exception as exc:
            st.error(f"Crypto data error: {exc}")


# =====================================
# FOOTER
# =====================================

st.divider()

st.caption(
    "AFG AI GOLD PRO | Technical Analysis Engine | "
    "Educational use only. Signals are not guaranteed. "
    "Always verify prices and manage risk independently."
)
# ===== AFG AI GOLD PRO - TWELVE DATA CONNECTION TEST =====

st.divider()
st.subheader("🟡 تست اتصال زنده طلا - Twelve Data")

if st.button("آزمایش اتصال طلا"):
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "XAU/USD",
                "interval": "1h",
                "outputsize": 10,
                "apikey": api_key
            },
            timeout=20
        )

        data = response.json()

        if "values" in data:
            df_test = pd.DataFrame(data["values"])
            df_test["close"] = pd.to_numeric(df_test["close"])
            df_test = df_test.iloc[::-1].reset_index(drop=True)

            st.success("اتصال به Twelve Data موفق شد!")
            st.metric("آخرین قیمت طلا", f"${df_test['close'].iloc[-1]:,.2f}")
            st.dataframe(df_test.tail(5), use_container_width=True)
        else:
            st.error("داده دریافت نشد:")
            st.write(data.get("message", data))

    except Exception as e:
        st.error(f"خطا در اتصال: {e}")


# ===== AFG AI GOLD PRO - MULTI TIMEFRAME GOLD =====

st.divider()
st.subheader("📊 تحلیل چند تایم‌فریمی طلا")

gold_timeframes = {
    "1 دقیقه - Scalping": "1min",
    "5 دقیقه - Scalping": "5min",
    "15 دقیقه - Scalping": "15min",
    "1 ساعت - Intraday": "1h",
    "4 ساعت - Intraday": "4h"
}

selected_tf = st.selectbox(
    "انتخاب تایم‌فریم طلا",
    list(gold_timeframes.keys())
)

if st.button("دریافت کندل‌های طلا"):
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        interval = gold_timeframes[selected_tf]

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "XAU/USD",
                "interval": interval,
                "outputsize": 100,
                "order": "asc",
                "timezone": "UTC",
                "apikey": api_key
            },
            timeout=25
        )

        data = response.json()

        if "values" not in data:
            st.error("دریافت اطلاعات ناموفق بود:")
            st.write(data.get("message", data))

        else:
            gold_df = pd.DataFrame(data["values"])

            for col in ["open", "high", "low", "close"]:
                gold_df[col] = pd.to_numeric(
                    gold_df[col], errors="coerce"
                )

            gold_df = gold_df.dropna(
                subset=["open", "high", "low", "close"]
            )

            gold_df = gold_df.sort_values(
                "datetime"
            ).reset_index(drop=True)

            if gold_df.empty:
                st.warning("کندل معتبری دریافت نشد.")
            else:
                st.success(
                    f"دریافت اطلاعات {selected_tf} موفق بود!"
                )

                st.metric(
                    "آخرین قیمت بسته‌شدن کندل",
                    f"${gold_df['close'].iloc[-1]:,.2f}"
                )

                st.line_chart(
                    gold_df.set_index("datetime")["close"]
                )

                st.dataframe(
                    gold_df.tail(10),
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"خطا: {e}")
