
import streamlit as st
import pandas as pd
import requests

st.set_page_config(
    page_title="AFG AI Crypto Signal",
    page_icon="📈",
    layout="wide"
)

st.title("🇦🇫 AFG AI Crypto Signal")
st.subheader("AI Cryptocurrency Analysis Dashboard")

symbols = {
    "Bitcoin": "BTCUSDT",
    "Ethereum": "ETHUSDT",
    "BNB": "BNBUSDT",
    "Solana": "SOLUSDT"
}

coin = st.selectbox("Select Cryptocurrency", list(symbols.keys()))
symbol = symbols[coin]

interval = st.selectbox(
    "Timeframe",
    ["15m", "1h", "4h", "1d"]
)

if st.button("Analyze Market"):
    try:
        url = "https://api.binance.com/api/v3/klines"

        response = requests.get(
            url,
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": 100
            },
            timeout=15
        )
        response.raise_for_status()

        data = response.json()

        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low",
            "close", "volume", "close_time",
            "quote_volume", "trades",
            "buy_volume", "buy_quote", "ignore"
        ])

        df["close"] = df["close"].astype(float)

        df["EMA20"] = df["close"].ewm(
            span=20, adjust=False
        ).mean()

        df["EMA50"] = df["close"].ewm(
            span=50, adjust=False
        ).mean()

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(
            alpha=1/14, adjust=False
        ).mean()

        avg_loss = loss.ewm(
            alpha=1/14, adjust=False
        ).mean()

        rs = avg_gain / avg_loss.replace(0, float("nan"))
        df["RSI"] = 100 - (100 / (1 + rs))

        price = df["close"].iloc[-1]
        rsi = df["RSI"].iloc[-1]

        st.metric("Current Price", f"${price:,.2f}")
        st.metric("RSI", f"{rsi:.2f}")

        st.line_chart(df.set_index("time")["close"])

        if price > df["EMA20"].iloc[-1] > df["EMA50"].iloc[-1] and rsi < 70:
            signal = "BUY"
        elif price < df["EMA20"].iloc[-1] < df["EMA50"].iloc[-1] and rsi > 30:
            signal = "SELL"
        else:
            signal = "HOLD"

        st.subheader("AI Market Signal")

        if signal == "BUY":
            st.success("BUY - Bullish conditions")
        elif signal == "SELL":
            st.error("SELL - Bearish conditions")
        else:
            st.warning("HOLD - No clear trend")

        st.caption(
            "Educational technical indicator. "
            "Not financial advice or a guaranteed prediction."
        )

    except Exception as e:
        st.error(f"Market data error: {e}")
