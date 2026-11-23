import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="AFG AI Crypto & Gold Signal", page_icon="🇦🇫", layout="wide")

st.title("🇦🇫 AFG AI Crypto & Gold Signal")
st.subheader("Technical market dashboard")

TIMEOUT = 20
HEADERS = {"User-Agent": "AFG-AI-Signal/1.0"}

def get_json(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()

def add_indicators(df):
    df = df.copy()
    for col in ["high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["high", "low", "close"]).reset_index(drop=True)

    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["RSI"] = 100 - (100 / (1 + rs))

    previous_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()
    return df

def get_gold_data():
    # XAUS provides real XAU/USD spot and daily history without an API key.
    spot = get_json("https://xaus.com/api/v1/spot")
    history = get_json("https://xaus.com/api/v1/history")

    points = history.get("points", [])
    if len(points) < 55:
        raise ValueError("Gold API returned too few daily history points.")

    df = pd.DataFrame(points)
    # XAUS daily history supplies date, close, high and low (not open/volume).
    df["time"] = pd.to_datetime(df["d"], errors="coerce")
    df = df.rename(columns={"c": "close", "h": "high", "l": "low"})
    df = df.sort_values("time")
    df = add_indicators(df)

    live_price = float(spot["spot_usd_oz"])
    data_state = spot.get("data_state", {})
    if data_state.get("status") == "unavailable":
        raise ValueError("Gold price is currently unavailable from the data provider.")
    if spot.get("stale") is True:
        st.warning("Gold provider is returning its last known price, not a fresh quote.")
    return df, live_price, spot.get("price_as_of") or spot.get("updated_at"), "XAUS XAU/USD"

def get_crypto_data(symbol, interval):
    # Try Bybit first, then Binance as a fallback. Either provider may be restricted
    # in some hosting regions; errors are shown rather than inventing market prices.
    errors = []
    bybit_intervals = {"15m": "15", "1h": "60", "4h": "240", "1d": "D"}
    try:
        payload = get_json(
            "https://api.bybit.com/v5/market/kline",
            {"category": "spot", "symbol": symbol, "interval": bybit_intervals[interval], "limit": 200}
        )
        if payload.get("retCode") != 0:
            raise ValueError(payload.get("retMsg", "Bybit API error"))
        rows = payload.get("result", {}).get("list", [])
        if not rows:
            raise ValueError("Bybit returned no candles.")
        df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume", "turnover"])
        df["time"] = pd.to_datetime(pd.to_numeric(df["time"]), unit="ms")
        df = df.sort_values("time")
        return add_indicators(df), float(df["close"].iloc[-1]), "Bybit spot"
    except Exception as exc:
        errors.append(f"Bybit: {exc}")

    try:
        payload = get_json(
            "https://api.binance.com/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": 200}
        )
        df = pd.DataFrame(payload, columns=[
            "time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "trades", "buy_volume", "buy_quote", "ignore"
        ])
        df["time"] = pd.to_datetime(pd.to_numeric(df["time"]), unit="ms")
        df = df.sort_values("time")
        df = add_indicators(df)
        return df, float(df["close"].iloc[-1]), "Binance spot"
    except Exception as exc:
        errors.append(f"Binance: {exc}")
    raise RuntimeError("Could not retrieve crypto candles. " + " | ".join(errors))

def render_analysis(df, price, source, timeframe_label, as_of=None):
    if len(df) < 55:
        st.error("Not enough candle history to calculate indicators reliably.")
        return

    latest = df.iloc[-1]
    ema20, ema50 = float(latest["EMA20"]), float(latest["EMA50"])
    rsi = float(latest["RSI"])
    atr = float(latest["ATR"])

    if pd.isna(rsi) or pd.isna(atr) or atr <= 0:
        st.error("Indicator data is incomplete. Please try again later.")
        return

    if price > ema20 > ema50 and rsi < 70:
        signal = "BUY"
    elif price < ema20 < ema50 and rsi > 30:
        signal = "SELL"
    else:
        signal = "HOLD"

    st.caption(f"Data: {source} · Timeframe: {timeframe_label}" + (f" · Price timestamp: {as_of}" if as_of else ""))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current / latest price", f"${price:,.2f}")
    c2.metric("RSI (14)", f"{rsi:.2f}")
    c3.metric("EMA 20", f"${ema20:,.2f}")
    c4.metric("EMA 50", f"${ema50:,.2f}")

    st.line_chart(df.set_index("time")[["close", "EMA20", "EMA50"]])

    st.subheader("Market signal")
    if signal == "BUY":
        st.success("BUY — bullish technical conditions")
        sl = price - 1.5 * atr
        risk = price - sl
        tp1, tp2, tp3 = price + risk, price + 2 * risk, price + 3 * risk
    elif signal == "SELL":
        st.error("SELL — bearish technical conditions")
        sl = price + 1.5 * atr
        risk = sl - price
        tp1, tp2, tp3 = price - risk, price - 2 * risk, price - 3 * risk
    else:
        st.warning("HOLD — no clear trend; no active trade levels are suggested.")
        st.info("Wait for a clearer BUY or SELL setup before considering entry, TP or SL.")
        return

    st.markdown("#### Trade plan (indicative, ATR-based)")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry", f"${price:,.2f}")
    p2.metric("Stop Loss (SL)", f"${sl:,.2f}")
    p3.metric("Take Profit 1", f"${tp1:,.2f}")
    p4.metric("Take Profit 2", f"${tp2:,.2f}")
    st.metric("Take Profit 3", f"${tp3:,.2f}")
    st.caption(
        "TP/SL are calculated from 1.5 × ATR (TP1 = 1R, TP2 = 2R, TP3 = 3R). "
        "They are illustrative technical levels, not guaranteed outcomes or trade execution instructions."
    )

market = st.radio("Market", ["Cryptocurrency", "Gold (XAU/USD)"], horizontal=True)

if market == "Gold (XAU/USD)":
    st.write("Gold spot is analyzed using daily XAU/USD history. The data provider's daily history does not provide full intraday OHLC candles.")
    if st.button("Analyze Gold", type="primary"):
        try:
            with st.spinner("Loading gold market data..."):
                df, price, as_of, source = get_gold_data()
            render_analysis(df, price, source, "1D", as_of)
        except Exception as exc:
            st.error(f"Gold data error: {exc}")
else:
    crypto_symbols = {
        "Bitcoin": "BTCUSDT",
        "Ethereum": "ETHUSDT",
        "BNB": "BNBUSDT",
        "Solana": "SOLUSDT"
    }
    coin = st.selectbox("Select cryptocurrency", list(crypto_symbols.keys()))
    interval = st.selectbox("Timeframe", ["15m", "1h", "4h", "1d"])
    if st.button("Analyze Crypto", type="primary"):
        try:
            with st.spinner("Loading crypto market data..."):
                df, price, source = get_crypto_data(crypto_symbols[coin], interval)
            render_analysis(df, price, source, interval)
        except Exception as exc:
            st.error(f"Market data error: {exc}")

st.divider()
st.caption(
    "AFG AI provides educational technical analysis only. It is not personalized financial advice. "
    "Market prices and calculated levels can be delayed or inaccurate. Always verify prices with your broker "
    "and manage risk independently."
)
