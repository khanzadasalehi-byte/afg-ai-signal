
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
# ===== AFG AI GOLD PRO - TECHNICAL SIGNAL ENGINE =====

st.divider()
st.header("🤖 AFG AI GOLD PRO - تحلیل هوشمند طلا")

def afg_add_indicators(df):
    df = df.copy()

    # EMA
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # ATR
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()

    # ADX and directional indicators
    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0), 0
    )
    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0), 0
    )

    atr_safe = df["ATR"].replace(0, 1e-10)

    plus_di = 100 * plus_dm.ewm(
        alpha=1/14, adjust=False
    ).mean() / atr_safe

    minus_di = 100 * minus_dm.ewm(
        alpha=1/14, adjust=False
    ).mean() / atr_safe

    dx = 100 * (plus_di - minus_di).abs() / (
        plus_di + minus_di
    ).replace(0, 1e-10)

    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di
    df["ADX"] = dx.ewm(alpha=1/14, adjust=False).mean()

    return df


def afg_generate_signal(df):
    last = df.iloc[-1]

    score = 0
    reasons = []

    # EMA trend
    if last["EMA20"] > last["EMA50"] > last["EMA200"]:
        score += 2
        reasons.append("روند صعودی EMA")
    elif last["EMA20"] < last["EMA50"] < last["EMA200"]:
        score -= 2
        reasons.append("روند نزولی EMA")

    # Price position
    if last["close"] > last["EMA20"]:
        score += 1
        reasons.append("قیمت بالاتر از EMA20")
    elif last["close"] < last["EMA20"]:
        score -= 1
        reasons.append("قیمت پایین‌تر از EMA20")

    # RSI
    if 50 < last["RSI"] < 70:
        score += 1
        reasons.append("RSI به نفع خریداران")
    elif 30 < last["RSI"] < 50:
        score -= 1
        reasons.append("RSI به نفع فروشندگان")

    # MACD
    if last["MACD"] > last["MACD_SIGNAL"]:
        score += 1
        reasons.append("MACD صعودی")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        score -= 1
        reasons.append("MACD نزولی")

    # ADX direction
    if last["ADX"] >= 20:
        if last["PLUS_DI"] > last["MINUS_DI"]:
            score += 1
            reasons.append("قدرت روند به نفع خریداران")
        elif last["MINUS_DI"] > last["PLUS_DI"]:
            score -= 1
            reasons.append("قدرت روند به نفع فروشندگان")
    else:
        reasons.append("قدرت روند ضعیف است")

    if score >= 4:
        signal = "BUY"
    elif score <= -4:
        signal = "SELL"
    else:
        signal = "NO TRADE"

    return signal, score, reasons


signal_tf = st.selectbox(
    "تایم‌فریم تحلیل سیگنال",
    {
        "1 دقیقه": "1min",
        "5 دقیقه": "5min",
        "15 دقیقه": "15min",
        "1 ساعت": "1h",
        "4 ساعت": "4h"
    }.keys(),
    key="afg_signal_tf"
)

if st.button("🚀 اجرای تحلیل هوشمند طلا"):
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        intervals = {
            "1 دقیقه": "1min",
            "5 دقیقه": "5min",
            "15 دقیقه": "15min",
            "1 ساعت": "1h",
            "4 ساعت": "4h"
        }

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "XAU/USD",
                "interval": intervals[signal_tf],
                "outputsize": 250,
                "timezone": "UTC",
                "apikey": api_key
            },
            timeout=30
        )

        data = response.json()

        if "values" not in data:
            st.error(data.get("message", "دریافت اطلاعات ناموفق بود."))

        else:
            df = pd.DataFrame(data["values"])

            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna(
                subset=["open", "high", "low", "close"]
            )

            df = df.sort_values("datetime").reset_index(drop=True)

            # Exclude the newest candle because it may still be forming.
            if len(df) > 1:
                df = df.iloc[:-1].copy()

            if len(df) < 210:
                st.warning(
                    f"داده کافی نیست. حداقل 210 کندل لازم است؛ "
                    f"تعداد موجود: {len(df)}"
                )
            else:
                df = afg_add_indicators(df)
                last = df.iloc[-1]

                signal, score, reasons = afg_generate_signal(df)

                st.subheader(f"نتیجه تحلیل: {signal}")

                if signal == "BUY":
                    st.success("سیگنال خرید؛ قبل از ورود ریسک را بررسی کن.")
                elif signal == "SELL":
                    st.error("سیگنال فروش؛ قبل از ورود ریسک را بررسی کن.")
                else:
                    st.warning("شرایط کافی نیست؛ فعلاً معامله نکن.")

                c1, c2, c3 = st.columns(3)
                c1.metric("قیمت کندل بسته‌شده", f"${last['close']:.2f}")
                c2.metric("امتیاز تحلیل", f"{score} از 6")
                c3.metric("RSI", f"{last['RSI']:.2f}")

                st.write("**تایم‌فریم:**", signal_tf)
                st.write("**زمان آخرین کندل بسته‌شده:**", last["datetime"])
                st.write("**ADX:**", round(last["ADX"], 2))
                st.write("**ATR:**", round(last["ATR"], 3))

                st.write("### دلایل تحلیل")
                for reason in reasons:
                    st.write("•", reason)

                # Illustrative ATR-based risk levels
                entry = float(last["close"])
                atr = float(last["ATR"])

                if signal == "BUY" and atr > 0:
                    sl = entry - (1.5 * atr)
                    risk = entry - sl
                    tp1 = entry + risk
                    tp2 = entry + (2 * risk)

                    st.write("### سطوح پیشنهادی خرید")
                    st.metric("Entry", f"${entry:.2f}")
                    st.metric("Stop Loss", f"${sl:.2f}")
                    st.metric("Take Profit 1", f"${tp1:.2f}")
                    st.metric("Take Profit 2", f"${tp2:.2f}")

                elif signal == "SELL" and atr > 0:
                    sl = entry + (1.5 * atr)
                    risk = sl - entry
                    tp1 = entry - risk
                    tp2 = entry - (2 * risk)

                    st.write("### سطوح پیشنهادی فروش")
                    st.metric("Entry", f"${entry:.2f}")
                    st.metric("Stop Loss", f"${sl:.2f}")
                    st.metric("Take Profit 1", f"${tp1:.2f}")
                    st.metric("Take Profit 2", f"${tp2:.2f}")

                st.write("### نمودار EMA")
                chart_df = df.tail(100).set_index("datetime")
                st.line_chart(
                    chart_df[["close", "EMA20", "EMA50", "EMA200"]]
                )

                st.caption(
                    "این سیگنال آموزشی و قانون‌محور است؛ "
                    "تضمین سود نیست. سطوح ATR تخمینی هستند."
                )

    except Exception as e:
        st.error(f"خطا در تحلیل: {e}")

# ===== AFG AI GOLD PRO - MULTI TIMEFRAME CONFIRMATION =====

st.divider()
st.header("🧠 تأیید هوشمند چندتایم‌فریمی")

def afg_fetch_timeframe(interval, api_key):
    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": "XAU/USD",
            "interval": interval,
            "outputsize": 250,
            "timezone": "UTC",
            "apikey": api_key
        },
        timeout=30
    )
    response.raise_for_status()
    data = response.json()

    if "values" not in data:
        raise ValueError(data.get("message", "داده دریافت نشد"))

    frame = pd.DataFrame(data["values"])

    for col in ["open", "high", "low", "close"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = frame.dropna(
        subset=["open", "high", "low", "close"]
    )

    frame = frame.sort_values("datetime").reset_index(drop=True)

    # حذف کندل در حال تشکیل
    if len(frame) > 1:
        frame = frame.iloc[:-1].copy()

    if len(frame) < 210:
        raise ValueError(
            f"داده کافی نیست: فقط {len(frame)} کندل دریافت شد."
        )

    return afg_add_indicators(frame)


if st.button("🔍 تأیید نهایی چهار تایم‌فریم"):
    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        timeframe_map = {
            "5 دقیقه": "5min",
            "15 دقیقه": "15min",
            "1 ساعت": "1h",
            "4 ساعت": "4h"
        }

        results = {}
        errors = {}

        progress = st.progress(0)

        for index, (name, interval) in enumerate(timeframe_map.items()):
            try:
                frame = afg_fetch_timeframe(interval, api_key)
                signal, score, reasons = afg_generate_signal(frame)

                results[name] = {
                    "signal": signal,
                    "score": score,
                    "price": float(frame.iloc[-1]["close"]),
                    "atr": float(frame.iloc[-1]["ATR"]),
                    "time": frame.iloc[-1]["datetime"]
                }

            except Exception as e:
                errors[name] = str(e)

            progress.progress((index + 1) / len(timeframe_map))

        st.subheader("نتیجه هر تایم‌فریم")

        for name in timeframe_map:
            if name in results:
                item = results[name]
                st.write(
                    f"**{name}:** {item['signal']} "
                    f"| امتیاز: {item['score']} از 6 "
                    f"| قیمت: ${item['price']:.2f}"
                )
            else:
                st.error(f"{name}: {errors.get(name, 'نامشخص')}")

        if len(results) == 4:
            buy_count = sum(
                x["signal"] == "BUY" for x in results.values()
            )
            sell_count = sum(
                x["signal"] == "SELL" for x in results.values()
            )

            # تایم‌فریم‌های بالاتر باید هم‌جهت باشند.
            higher_buy = (
                results["1 ساعت"]["signal"] == "BUY"
                and results["4 ساعت"]["signal"] == "BUY"
            )

            higher_sell = (
                results["1 ساعت"]["signal"] == "SELL"
                and results["4 ساعت"]["signal"] == "SELL"
            )

            final_signal = "NO TRADE"

            if higher_buy and buy_count >= 3:
                final_signal = "BUY"

            elif higher_sell and sell_count >= 3:
                final_signal = "SELL"

            st.divider()
            st.subheader("🎯 سیگنال نهایی AFG AI GOLD PRO")

            if final_signal == "BUY":
                st.success("BUY - تأیید روند صعودی در چند تایم‌فریم")

            elif final_signal == "SELL":
                st.error("SELL - تأیید روند نزولی در چند تایم‌فریم")

            else:
                st.warning(
                    "NO TRADE - تایم‌فریم‌ها تأیید کافی ندارند."
                )

            # محاسبه سطوح تخمینی بر اساس ATR پانزده دقیقه
            if final_signal != "NO TRADE":
                entry = results["15 دقیقه"]["price"]
                atr = results["15 دقیقه"]["atr"]

                if atr > 0:
                    if final_signal == "BUY":
                        sl = entry - 1.5 * atr
                        tp1 = entry + 1.5 * atr
                        tp2 = entry + 3 * atr
                    else:
                        sl = entry + 1.5 * atr
                        tp1 = entry - 1.5 * atr
                        tp2 = entry - 3 * atr

                    st.write("### سطوح تخمینی معامله")
                    a, b, c, d = st.columns(4)
                    a.metric("Entry", f"${entry:.2f}")
                    b.metric("Stop Loss", f"${sl:.2f}")
                    c.metric("TP 1", f"${tp1:.2f}")
                    d.metric("TP 2", f"${tp2:.2f}")

            st.caption(
                "این سیستم قانون‌محور است. سیگنال نهایی تضمین سود نیست. "
                "داده‌ها ممکن است با تأخیر یا محدودیت API همراه باشند."
            )

        else:
            st.warning(
                "برای صدور سیگنال نهایی، اطلاعات هر چهار تایم‌فریم لازم است."
            )

    except Exception as e:
        st.error(f"خطا در تحلیل چندتایم‌فریمی: {e}")
# ===== AFG AI GOLD PRO - BACKTESTING ENGINE =====

st.divider()
st.header("📈 AFG AI GOLD PRO - Backtesting")

def afg_backtest(df, initial_capital=500, risk_percent=1,
                 cost_per_ounce=0):

    df = afg_add_indicators(df.copy()).reset_index(drop=True)

    # Calculate the same technical score used by the signal engine
    score = pd.Series(0, index=df.index)

    score += (
        (df["EMA20"] > df["EMA50"]) &
        (df["EMA50"] > df["EMA200"])
    ).astype(int) * 2

    score -= (
        (df["EMA20"] < df["EMA50"]) &
        (df["EMA50"] < df["EMA200"])
    ).astype(int) * 2

    score += (df["close"] > df["EMA20"]).astype(int)
    score -= (df["close"] < df["EMA20"]).astype(int)

    score += (
        (df["RSI"] > 50) & (df["RSI"] < 70)
    ).astype(int)

    score -= (
        (df["RSI"] > 30) & (df["RSI"] < 50)
    ).astype(int)

    score += (df["MACD"] > df["MACD_SIGNAL"]).astype(int)
    score -= (df["MACD"] < df["MACD_SIGNAL"]).astype(int)

    score += (
        (df["ADX"] >= 20) &
        (df["PLUS_DI"] > df["MINUS_DI"])
    ).astype(int)

    score -= (
        (df["ADX"] >= 20) &
        (df["MINUS_DI"] > df["PLUS_DI"])
    ).astype(int)

    df["SCORE"] = score

    equity = float(initial_capital)
    peak = equity
    max_drawdown = 0.0
    trades = []
    equity_points = [equity]

    i = 200

    while i < len(df) - 1 and equity > 0:

        current = df.iloc[i]

        if current["SCORE"] >= 4:
            direction = "BUY"
        elif current["SCORE"] <= -4:
            direction = "SELL"
        else:
            i += 1
            continue

        atr = float(current["ATR"])

        if not atr > 0:
            i += 1
            continue

        # Enter at the next candle open, not the signal candle close.
        entry_index = i + 1
        entry = float(df.iloc[entry_index]["open"])

        stop_distance = 1.5 * atr
        target_distance = 2 * stop_distance

        risk_amount = equity * risk_percent / 100

        units = risk_amount / stop_distance

        # Conservative 1x notional exposure limit.
        units = min(units, equity / entry)

        if direction == "BUY":
            stop = entry - stop_distance
            target = entry + target_distance
        else:
            stop = entry + stop_distance
            target = entry - target_distance

        exit_price = None
        exit_index = entry_index
        exit_reason = "END OF DATA"

        # Check future candles for stop or target.
        for j in range(entry_index, len(df)):

            candle = df.iloc[j]

            if direction == "BUY":
                hit_stop = float(candle["low"]) <= stop
                hit_target = float(candle["high"]) >= target
            else:
                hit_stop = float(candle["high"]) >= stop
                hit_target = float(candle["low"]) <= target

            # If both are touched in one candle, assume stop first.
            if hit_stop:
                exit_price = stop
                exit_reason = "STOP LOSS"
                exit_index = j
                break

            if hit_target:
                exit_price = target
                exit_reason = "TAKE PROFIT"
                exit_index = j
                break

        if exit_price is None:
            exit_index = len(df) - 1
            exit_price = float(df.iloc[-1]["close"])

        if direction == "BUY":
            gross_pnl = (exit_price - entry) * units
        else:
            gross_pnl = (entry - exit_price) * units

        trading_cost = cost_per_ounce * units
        net_pnl = gross_pnl - trading_cost

        equity += net_pnl
        peak = max(peak, equity)

        drawdown = (
            (peak - equity) / peak * 100
            if peak > 0 else 0
        )

        max_drawdown = max(max_drawdown, drawdown)

        trades.append({
            "Direction": direction,
            "Entry Time": df.iloc[entry_index]["datetime"],
            "Exit Time": df.iloc[exit_index]["datetime"],
            "Entry": round(entry, 2),
            "Exit": round(exit_price, 2),
            "Units": round(units, 4),
            "Net PnL ($)": round(net_pnl, 2),
            "Result": "WIN" if net_pnl > 0 else "LOSS",
            "Exit Reason": exit_reason,
            "Equity ($)": round(equity, 2)
        })

        equity_points.append(equity)

        # Do not open another trade before this one closes.
        i = exit_index + 1

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return trades_df, {
            "final_equity": equity,
            "net_profit": equity - initial_capital,
            "win_rate": 0,
            "max_drawdown": max_drawdown,
            "total_trades": 0,
            "profit_factor": None
        }

    wins = trades_df[trades_df["Net PnL ($)"] > 0]
    losses = trades_df[trades_df["Net PnL ($)"] < 0]

    gross_wins = wins["Net PnL ($)"].sum()
    gross_losses = abs(losses["Net PnL ($)"].sum())

    profit_factor = (
        gross_wins / gross_losses
        if gross_losses > 0 else None
    )

    stats = {
        "final_equity": equity,
        "net_profit": equity - initial_capital,
        "win_rate": len(wins) / len(trades_df) * 100,
        "max_drawdown": max_drawdown,
        "total_trades": len(trades_df),
        "profit_factor": profit_factor
    }

    return trades_df, stats


# Backtesting controls
st.subheader("تنظیمات آزمایش")

bt_timeframe = st.selectbox(
    "انتخاب تایم‌فریم Backtesting",
    ["5 دقیقه", "15 دقیقه", "1 ساعت", "4 ساعت"],
    key="afg_bt_tf"
)

bt_intervals = {
    "5 دقیقه": "5min",
    "15 دقیقه": "15min",
    "1 ساعت": "1h",
    "4 ساعت": "4h"
}

bt_cost = st.number_input(
    "هزینه تخمینی هر اونس برای ورود و خروج (دالر)",
    min_value=0.0,
    value=0.0,
    step=0.05
)

st.info(
    "سرمایه اولیه: 500 دلار | "
    "ریسک هر معامله: 1 درصد | "
    "حد سود: 2 برابر فاصله حد ضرر"
)

if st.button("🚀 اجرای Backtesting با سرمایه 500 دلار"):

    try:
        api_key = st.secrets["TWELVE_DATA_API_KEY"]

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "XAU/USD",
                "interval": bt_intervals[bt_timeframe],
                "outputsize": 500,
                "timezone": "UTC",
                "apikey": api_key
            },
            timeout=30
        )

        data = response.json()

        if "values" not in data:
            st.error(data.get("message", "داده تاریخی دریافت نشد."))

        else:
            bt_df = pd.DataFrame(data["values"])

            for col in ["open", "high", "low", "close"]:
                bt_df[col] = pd.to_numeric(
                    bt_df[col], errors="coerce"
                )

            bt_df = bt_df.dropna(
                subset=["open", "high", "low", "close"]
            )

            bt_df = bt_df.sort_values(
                "datetime"
            ).reset_index(drop=True)

            # Exclude potentially unfinished latest candle.
            if len(bt_df) > 1:
                bt_df = bt_df.iloc[:-1].copy()

            if len(bt_df) < 250:
                st.warning(
                    f"داده کافی نیست. تعداد کندل: {len(bt_df)}"
                )

            else:
                trades, stats = afg_backtest(
                    bt_df,
                    initial_capital=500,
                    risk_percent=1,
                    cost_per_ounce=bt_cost
                )

                st.success("آزمایش Backtesting تکمیل شد.")

                a, b, c = st.columns(3)

                a.metric(
                    "سرمایه نهایی",
                    f"${stats['final_equity']:.2f}"
                )

                b.metric(
                    "سود یا زیان خالص",
                    f"${stats['net_profit']:.2f}"
                )

                c.metric(
                    "Win Rate",
                    f"{stats['win_rate']:.1f}%"
                )

                d, e, f = st.columns(3)

                d.metric(
                    "تعداد معاملات",
                    stats["total_trades"]
                )

                e.metric(
                    "Max Drawdown",
                    f"{stats['max_drawdown']:.2f}%"
                )

                pf = stats["profit_factor"]

                f.metric(
                    "Profit Factor",
                    f"{pf:.2f}" if pf is not None else "N/A"
                )

                if not trades.empty:
                    st.subheader("تاریخچه معاملات آزمایشی")
                    st.dataframe(
                        trades,
                        use_container_width=True
                    )

                    st.subheader("نمودار سرمایه")
                    st.line_chart(
                        [500] + trades["Equity ($)"].tolist()
                    )

                else:
                    st.warning(
                        "در این دوره هیچ معامله‌ای با قوانین فعلی ایجاد نشد."
                    )

                st.caption(
                    "نتایج تاریخی تضمین عملکرد آینده نیستند. "
                    "هزینه واقعی، اسپرد، لغزش قیمت، "
                    "محدودیت داده و شرایط اجرای بروکر می‌توانند "
                    "نتایج واقعی را تغییر دهند."
                )

    except Exception as e:
        st.error(f"خطا در Backtesting: {e}")


