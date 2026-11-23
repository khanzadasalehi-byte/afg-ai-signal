import streamlit as st
import pandas as pd
import numpy as np
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ==========================================================
# AFG AI GOLD PRO ELITE V10
# 40-minute market refresh + time-limited manual signals
# Provider: Twelve Data | Signals are decision support only
# ==========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO ELITE V10",
    page_icon="🇦🇫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------ STYLE ------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root { --gold:#d6ad55; --gold2:#f4d58a; }
html, body, [class*="css"] { font-family:Inter,sans-serif; }
.stApp { background:radial-gradient(circle at 12% 0%,#20283a 0%,#0b101a 42%,#080b12 100%); color:#edf1f7; }
.block-container { max-width:1550px; padding-top:1.25rem; padding-bottom:3rem; }
[data-testid="stHeader"] { background:rgba(8,11,18,.78); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#111827,#090d15); border-right:1px solid rgba(214,173,85,.25); }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:var(--gold2); }
.hero { padding:25px 28px; border:1px solid rgba(214,173,85,.42); border-radius:20px; background:linear-gradient(115deg,rgba(214,173,85,.16),rgba(17,24,39,.94) 48%,rgba(10,14,22,.96)); margin-bottom:18px; }
.hero-kicker { color:var(--gold2); font-size:.72rem; font-weight:800; letter-spacing:.22em; }
.hero-title { color:#fff; font-size:clamp(1.65rem,3vw,2.55rem); font-weight:900; margin:7px 0; }
.hero-sub { color:#aeb8c8; font-size:.92rem; }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(25,34,50,.96),rgba(13,19,30,.96)); border:1px solid rgba(214,173,85,.22); padding:14px 16px; border-radius:15px; }
[data-testid="stMetricLabel"] { color:#aeb8c8 !important; }
[data-testid="stMetricValue"] { color:#fff !important; font-weight:800 !important; white-space:normal !important; overflow-wrap:anywhere !important; }
h2 { color:#f4d58a !important; } h3 { color:#e7c77f !important; }
.stButton>button { border:1px solid rgba(214,173,85,.55); border-radius:11px; background:linear-gradient(110deg,#b88b35,#e6c574); color:#11151d; font-weight:800; min-height:2.65rem; }
[data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid rgba(214,173,85,.18); border-radius:12px; }
[data-testid="stExpander"] { border:1px solid rgba(214,173,85,.22); border-radius:13px; background:rgba(17,24,39,.55); }
hr { border-color:rgba(214,173,85,.22) !important; }
@media(max-width:900px){ div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.6rem!important;} div[data-testid="stHorizontalBlock"]>div[data-testid="column"]{flex:1 1 180px!important;min-width:min(180px,100%)!important;} }
</style>
<div class="hero">
  <div class="hero-kicker">🇦🇫 AFG FINANCIAL INTELLIGENCE</div>
  <div class="hero-title">GOLD PRO <span style="color:#e7c77f">ELITE V10</span></div>
  <div class="hero-sub">40-MINUTE MARKET SCAN · TIME-LIMITED SIGNALS · MANUAL TRADING</div>
</div>
""", unsafe_allow_html=True)

st.caption("V10 · Separate Gold and Bitcoin · Automatic dashboard refresh every 40 minutes · Signal validity: 40 minutes · Manual trading only")
st.warning("A technical score is NOT a win probability. No system can guarantee 99% accuracy or profit. Verify every setup and test on a demo account.")

# ------------------------------ CONFIG ------------------------------

API_URL = "https://api.twelvedata.com/time_series"
SYMBOLS = {"GOLD": "XAU/USD", "BTC": "BTC/USD"}
INTERVALS = {"5M": "5min", "15M": "15min", "1H": "1h", "4H": "4h"}
DELTAS = {
    "5min": pd.Timedelta(minutes=5),
    "15min": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
}
LOCAL_TZ = ZoneInfo("Asia/Kabul")
TIMEOUT = 25
SCAN_INTERVAL_MINUTES = 40
SIGNAL_VALIDITY_MINUTES = 40
MAX_DAILY_SIGNALS = 3

# Refresh the dashboard while it remains open in the browser. This is not a push notification.
st_autorefresh(interval=SCAN_INTERVAL_MINUTES * 60 * 1000, key="afg_v10_40min_refresh")

with st.sidebar:
    st.markdown("### 🇦🇫 AFG GOLD PRO")
    st.caption("V10 · 40-MINUTE SCAN MODE")
    refresh = st.button("🔄 Refresh Market Data", use_container_width=True)
    st.divider()
    st.markdown("**Risk settings**")
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.1, max_value=3.0, value=0.5, step=0.1)
    account_size = st.number_input("Account balance (USD)", min_value=10.0, value=1000.0, step=100.0)
    min_score = st.slider("Minimum technical score", 70, 100, 85)
    st.caption("Higher filters mean fewer setups, not guaranteed higher win rate.")
    st.divider()
    st.caption("Data: Twelve Data · Scan every 40 minutes · Max 3 new setups per Kabul day")

try:
    API_KEY = st.secrets["TWELVE_DATA_API_KEY"]
except Exception:
    API_KEY = ""

if not API_KEY:
    st.error("API key not found. Keep TWELVE_DATA_API_KEY configured in Streamlit Secrets. Do not paste your key into chat.")
    st.stop()

if refresh:
    st.cache_data.clear()

# ------------------------------ DATA ------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_candles(symbol: str, interval: str, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": symbol, "interval": interval, "outputsize": 1000,
        "apikey": api_key, "timezone": "UTC", "format": "JSON",
    }
    response = requests.get(API_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        msg = payload.get("message") or payload.get("code") or str(payload)
        raise ValueError(f"Twelve Data: {msg}")
    df = pd.DataFrame(payload["values"])
    needed = ["datetime", "open", "high", "low", "close"]
    if any(c not in df.columns for c in needed):
        raise ValueError("Invalid candle data structure.")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=needed).sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    # Exclude the currently-forming candle.
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=3)
    df = df[df["datetime"] + DELTAS[interval] <= cutoff].reset_index(drop=True)
    if len(df) < 220:
        raise ValueError(f"Only {len(df)} closed candles received; at least 220 are required.")
    return df

# ------------------------------ INDICATORS ------------------------------

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    close = d["close"]
    d["ema20"] = close.ewm(span=20, adjust=False).mean()
    d["ema50"] = close.ewm(span=50, adjust=False).mean()
    d["ema200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    d["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    d["macd"] = fast - slow
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]

    prev = close.shift(1)
    tr = pd.concat([(d["high"]-d["low"]), (d["high"]-prev).abs(), (d["low"]-prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    up, down = d["high"].diff(), -d["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=d.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=d.index)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / d["atr"].replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / d["atr"].replace(0, np.nan)
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    d["plus_di"] = plus_di.fillna(0)
    d["minus_di"] = minus_di.fillna(0)
    d["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean().fillna(0)

    d["atr_pct"] = (d["atr"] / close.replace(0, np.nan) * 100).replace([np.inf, -np.inf], np.nan)
    return d

def trend_of(row) -> str:
    if row["close"] > row["ema50"] > row["ema200"]:
        return "BULLISH"
    if row["close"] < row["ema50"] < row["ema200"]:
        return "BEARISH"
    return "MIXED"

def candle_quality(row, direction: str) -> bool:
    rng = max(float(row["high"] - row["low"]), 1e-12)
    body = abs(float(row["close"] - row["open"]))
    body_ratio = body / rng
    if direction == "BUY":
        close_location = (float(row["high"]) - float(row["close"])) / rng
        return float(row["close"]) > float(row["open"]) and body_ratio >= 0.30 and close_location <= 0.30
    close_location = (float(row["close"]) - float(row["low"])) / rng
    return float(row["close"]) < float(row["open"]) and body_ratio >= 0.30 and close_location <= 0.30

def analyze_signal(frames: dict, score_floor: int, adx_floor: int):
    r5, r15, r1, r4 = (frames[k].iloc[-1] for k in ["5M", "15M", "1H", "4H"])
    trends = {k: trend_of(frames[k].iloc[-1]) for k in ["5M", "15M", "1H", "4H"]}
    buy_score = sell_score = 0
    checks = {}

    # Weighted confluence: 4H 25, 1H 25, 15M 30, 5M 10, trend strength 10.
    buy_score += 25 if trends["4H"] == "BULLISH" else 0
    sell_score += 25 if trends["4H"] == "BEARISH" else 0
    buy_score += 25 if trends["1H"] == "BULLISH" else 0
    sell_score += 25 if trends["1H"] == "BEARISH" else 0

    buy15 = (r15["close"] > r15["ema20"] and r15["ema20"] > r15["ema50"])
    sell15 = (r15["close"] < r15["ema20"] and r15["ema20"] < r15["ema50"])
    buy_rsi = 50 < float(r15["rsi"]) < 67
    sell_rsi = 33 < float(r15["rsi"]) < 50
    buy_macd = float(r15["macd_hist"]) > 0
    sell_macd = float(r15["macd_hist"]) < 0
    buy_di = float(r15["plus_di"]) > float(r15["minus_di"])
    sell_di = float(r15["minus_di"]) > float(r15["plus_di"])
    buy_score += 8 if buy15 else 0
    sell_score += 8 if sell15 else 0
    buy_score += 7 if buy_rsi else 0
    sell_score += 7 if sell_rsi else 0
    buy_score += 7 if buy_macd else 0
    sell_score += 7 if sell_macd else 0
    buy_score += 8 if buy_di else 0
    sell_score += 8 if sell_di else 0

    buy5 = float(r5["close"]) > float(r5["ema20"]) and float(r5["macd_hist"]) > 0
    sell5 = float(r5["close"]) < float(r5["ema20"]) and float(r5["macd_hist"]) < 0
    buy_score += 10 if buy5 else 0
    sell_score += 10 if sell5 else 0

    adx_ok = float(r15["adx"]) >= adx_floor
    buy_candle = candle_quality(r15, "BUY")
    sell_candle = candle_quality(r15, "SELL")

    recent = frames["15M"].tail(8)
    atr = float(r15["atr"]) if np.isfinite(r15["atr"]) else 0.0
    tolerance = atr * 0.30
    buy_touch = bool(((recent["low"] <= recent["ema20"] + tolerance) & (recent["low"] >= recent["ema20"] - tolerance*1.5)).any()) if atr > 0 else False
    sell_touch = bool(((recent["high"] >= recent["ema20"] - tolerance) & (recent["high"] <= recent["ema20"] + tolerance*1.5)).any()) if atr > 0 else False
    buy_pullback = buy_touch and buy15 and float(r15["close"]) > float(recent.iloc[-2]["close"])
    sell_pullback = sell_touch and sell15 and float(r15["close"]) < float(recent.iloc[-2]["close"])

    checks["4H + 1H aligned"] = trends["4H"] == trends["1H"] and trends["4H"] in ("BULLISH", "BEARISH")
    checks["15M structure"] = buy15 or sell15
    checks["15M pullback"] = buy_pullback or sell_pullback
    checks["15M candle confirmation"] = buy_candle or sell_candle
    checks["5M momentum confirmation"] = buy5 or sell5
    checks["ADX trend strength"] = adx_ok
    checks["RSI not overextended"] = buy_rsi or sell_rsi
    checks["MACD momentum"] = buy_macd or sell_macd

    signal, direction = "NO TRADE", None
    score = max(buy_score, sell_score)
    if (trends["4H"] == trends["1H"] == trends["15M"] == "BULLISH"
        and buy_pullback and buy_candle and buy5 and buy_rsi and buy_macd and buy_di
        and adx_ok and buy_score >= score_floor and buy_score > sell_score):
        signal, direction, score = "BUY", "BUY", buy_score
    elif (trends["4H"] == trends["1H"] == trends["15M"] == "BEARISH"
        and sell_pullback and sell_candle and sell5 and sell_rsi and sell_macd and sell_di
        and adx_ok and sell_score >= score_floor and sell_score > buy_score):
        signal, direction, score = "SELL", "SELL", sell_score

    current = float(r15["close"])
    entry = sl = tp1 = tp2 = tp3 = None
    order_type = None
    rr = None
    risk_distance = None
    entry_distance = None
    rejection = []

    if direction and atr > 0:
        ema = float(r15["ema20"])
        structure = frames["15M"].tail(12)
        if direction == "BUY":
            entry = ema + 0.05 * atr
            entry_distance = (current - entry) / atr
            swing = float(structure["low"].min())
            sl = min(swing - 0.12*atr, entry - 0.50*atr)
            risk_distance = entry - sl
            order_type = "BUY LIMIT"
            valid_entry = 0.05 <= entry_distance <= 0.65
            valid_risk = 0.50*atr <= risk_distance <= 2.0*atr
            if valid_entry and valid_risk:
                tp1, tp2, tp3 = entry + risk_distance, entry + 2*risk_distance, entry + 3*risk_distance
        else:
            entry = ema - 0.05 * atr
            entry_distance = (entry - current) / atr
            swing = float(structure["high"].max())
            sl = max(swing + 0.12*atr, entry + 0.50*atr)
            risk_distance = sl - entry
            order_type = "SELL LIMIT"
            valid_entry = 0.05 <= entry_distance <= 0.65
            valid_risk = 0.50*atr <= risk_distance <= 2.0*atr
            if valid_entry and valid_risk:
                tp1, tp2, tp3 = entry-risk_distance, entry-2*risk_distance, entry-3*risk_distance
        if valid_entry and valid_risk and risk_distance > 0:
            rr = 2.0
        else:
            rejection.append("Limit entry too far/too close or stop distance invalid")
            signal, direction, order_type = "NO TRADE", None, None
            entry = sl = tp1 = tp2 = tp3 = None

    return {
        "signal": signal, "direction": direction, "score": int(min(100, score)),
        "buy_score": buy_score, "sell_score": sell_score, "order_type": order_type,
        "current_price": current, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "rr": rr, "risk_distance": risk_distance, "entry_distance_atr": entry_distance,
        "trends": trends, "checks": checks, "adx": float(r15["adx"]), "rsi": float(r15["rsi"]),
        "atr": atr, "rejection": rejection,
    }

# ------------------------------ SESSION / DAILY LIMIT ------------------------------

def session_status():
    now = datetime.now(timezone.utc)
    tokyo = now.astimezone(ZoneInfo("Asia/Tokyo"))
    london = now.astimezone(ZoneInfo("Europe/London"))
    ny = now.astimezone(ZoneInfo("America/New_York"))
    return [
        ("ASIA", 9 <= tokyo.hour < 18, tokyo.strftime("%H:%M")),
        ("LONDON", 8 <= london.hour < 17, london.strftime("%H:%M")),
        ("NEW YORK", 8 <= ny.hour < 17, ny.strftime("%H:%M")),
    ]

# ------------------------------ LOAD DATA ------------------------------

market, errors = {}, {}
with st.spinner("Loading closed-candle data for Gold and Bitcoin..."):
    for asset, symbol in SYMBOLS.items():
        frames, asset_errors = {}, []
        for label, interval in INTERVALS.items():
            try:
                frames[label] = add_indicators(get_candles(symbol, interval, API_KEY))
            except Exception as exc:
                asset_errors.append(f"{label}: {exc}")
        if len(frames) == len(INTERVALS):
            market[asset] = frames
        if asset_errors:
            errors[asset] = asset_errors

if not market:
    st.error("No complete market dataset could be loaded. Check Twelve Data access, API limits, symbols and connection.")
    for asset, items in errors.items():
        st.write(f"**{asset}**")
        for item in items:
            st.write(f"- {item}")
    st.stop()

results = {}
for asset, frames in market.items():
    res = analyze_signal(frames, min_score, 20)
    last15 = frames["15M"].iloc[-1]
    last_close_time = last15["datetime"].to_pydatetime() + timedelta(minutes=15)
    age = datetime.now(timezone.utc) - last_close_time
    stale = age > timedelta(minutes=SIGNAL_VALIDITY_MINUTES)
    expiry = last_close_time + timedelta(minutes=SIGNAL_VALIDITY_MINUTES)
    remaining = max(0, int((expiry - datetime.now(timezone.utc)).total_seconds()))
    res.update({
        "last_price": float(last15["close"]),
        "last_candle_time": last15["datetime"].to_pydatetime(),
        "generated_at": datetime.now(timezone.utc),
        "stale": stale,
        "expired": remaining <= 0,
        "valid_until": expiry.astimezone(LOCAL_TZ),
        "remaining": remaining,
    })
    if stale or remaining <= 0:
        res.update({"signal":"NO TRADE", "direction":None, "order_type":None,
                    "entry":None, "sl":None, "tp1":None, "tp2":None, "tp3":None})
    results[asset] = res

# Persistent daily signal count across Streamlit reruns (session state).
today = datetime.now(LOCAL_TZ).date().isoformat()
if st.session_state.get("daily_date") != today:
    st.session_state["daily_date"] = today
    st.session_state["daily_keys"] = []
daily_keys = st.session_state.get("daily_keys", [])
for asset, res in results.items():
    if res["signal"] in ("BUY", "SELL"):
        key = f"{asset}|{res['last_candle_time'].isoformat()}|{res['signal']}"
        if key not in daily_keys:
            if len(daily_keys) >= MAX_DAILY_SIGNALS:
                res.update({"signal":"NO TRADE", "direction":None, "order_type":None,
                            "entry":None, "sl":None, "tp1":None, "tp2":None, "tp3":None,
                            "daily_cap":True})
            else:
                daily_keys.append(key)
                st.session_state["daily_keys"] = daily_keys
    res.setdefault("daily_cap", False)
daily_count = len(st.session_state.get("daily_keys", []))

# Approval history is intentionally session-scoped; it is not a broker order.
if "approval_log" not in st.session_state:
    st.session_state["approval_log"] = []
if "trade_journal" not in st.session_state:
    st.session_state["trade_journal"] = []

# ------------------------------ TOP SUMMARY ------------------------------

st.divider()
st.subheader("MARKET OVERVIEW")
scan_now_local = datetime.now(LOCAL_TZ)
next_scan_local = scan_now_local + timedelta(minutes=SCAN_INTERVAL_MINUTES)
st.info(f"AUTO SCAN: every {SCAN_INTERVAL_MINUTES} minutes while this dashboard is open · Last calculation: {scan_now_local.strftime('%Y-%m-%d %H:%M:%S')} Kabul time · Next scheduled refresh: about {next_scan_local.strftime('%H:%M')} Kabul time. Phone/browser sleep can delay refresh; this is not a push alert.")
overview_cols = st.columns(4)
if "GOLD" in results:
    overview_cols[0].metric("XAU/USD", f"{results['GOLD']['last_price']:,.2f}")
    overview_cols[1].metric("GOLD SIGNAL", results["GOLD"]["order_type"] or "NO TRADE")
else:
    overview_cols[0].metric("XAU/USD", "DATA ERROR")
    overview_cols[1].metric("GOLD SIGNAL", "DISABLED")
if "BTC" in results:
    overview_cols[2].metric("BTC/USD", f"{results['BTC']['last_price']:,.2f}")
    overview_cols[3].metric("BTC SIGNAL", results["BTC"]["order_type"] or "NO TRADE")
else:
    overview_cols[2].metric("BTC/USD", "DATA ERROR")
    overview_cols[3].metric("BTC SIGNAL", "DISABLED")

st.caption(f"Daily setup counter: {daily_count}/{MAX_DAILY_SIGNALS} · Kabul date: {today} · Counter is maintained for this app session.")

# ------------------------------ SCANNER ------------------------------

st.divider()
st.subheader("🔎 V10 MARKET SCANNER")
scanner = []
for asset, title in [("GOLD","XAU/USD"),("BTC","BTC/USD")]:
    if asset not in results:
        scanner.append({"Market":title,"Price":"—","4H":"—","1H":"—","15M":"—","5M":"—","Score":"—","Result":"DATA ERROR"})
        continue
    r = results[asset]
    scanner.append({
        "Market":title, "Price":round(r["last_price"],2),
        "4H":r["trends"]["4H"], "1H":r["trends"]["1H"],
        "15M":r["trends"]["15M"], "5M":r["trends"]["5M"],
        "Score":f"{r['score']}/100",
        "Result":r["order_type"] or "NO TRADE",
    })
st.dataframe(pd.DataFrame(scanner), use_container_width=True, hide_index=True)

# ------------------------------ ASSET WORKSPACES ------------------------------

tabs = st.tabs(["🥇 GOLD · XAU/USD", "₿ BITCOIN · BTC/USD"])
for tab, asset, title in zip(tabs, ["GOLD","BTC"], ["GOLD · XAU/USD","BITCOIN · BTC/USD"]):
    with tab:
        st.subheader(title)
        if asset not in results:
            st.error("This asset is temporarily unavailable. The other market can still be analyzed.")
            for e in errors.get(asset, []):
                st.write(f"- {e}")
            continue

        r = results[asset]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("PRICE", f"{r['last_price']:,.2f}")
        c2.metric("SIGNAL", r["order_type"] or "NO TRADE")
        c3.metric("TECHNICAL SCORE", f"{r['score']}/100")
        c4.metric("RISK / TRADE", f"{risk_pct:.1f}%")

        if r["stale"]:
            st.error("STALE DATA — new trades are disabled until fresh 15M data arrives.")
        elif r["expired"]:
            st.warning("SETUP WINDOW EXPIRED — wait for a new closed-candle setup.")
        elif r["daily_cap"]:
            st.warning("DAILY SIGNAL LIMIT REACHED.")
        elif r["signal"] == "BUY":
            st.success("BUY LIMIT candidate — pending setup only; no order is sent to your broker.")
        elif r["signal"] == "SELL":
            st.error("SELL LIMIT candidate — pending setup only; no order is sent to your broker.")
        else:
            st.warning("NO TRADE — all strict confirmation conditions are not aligned.")

        if r["signal"] in ("BUY","SELL") and r["entry"] is not None:
            vals = [("LIMIT ENTRY",r["entry"]),("STOP LOSS",r["sl"]),("TAKE PROFIT 1",r["tp1"]),("TAKE PROFIT 2",r["tp2"]),("TAKE PROFIT 3",r["tp3"])]
            cols = st.columns(5)
            for col,(label,value) in zip(cols,vals):
                col.metric(label,f"{value:,.2f}")
            risk_cash = account_size * risk_pct / 100
            st.info(f"Illustrative risk budget: ${risk_cash:,.2f}. Price risk distance: {r['risk_distance']:.4f}. Position size depends on your broker's contract specifications, tick value and lot rules; do not infer lots from this screen.")
            issued_local = r["generated_at"].astimezone(LOCAL_TZ)
            st.caption(f"Signal calculated: {issued_local.strftime('%Y-%m-%d %H:%M:%S')} Kabul time · Valid until: {r['valid_until'].strftime('%Y-%m-%d %H:%M')} Kabul time · {r['remaining']//60} minutes remaining · Planned reward/risk to TP2: 2R.")
        else:
            st.caption("No active entry, stop-loss or take-profit levels because the setup did not pass every filter.")

        st.markdown("**MANUAL SIGNAL APPROVAL**")
        if r["signal"] in ("BUY", "SELL") and r["entry"] is not None and not r["stale"] and not r["expired"]:
            signal_key = f"{asset}|{r['last_candle_time'].isoformat()}|{r['signal']}|{r['entry']:.8f}"
            existing = next((x for x in reversed(st.session_state["approval_log"]) if x["signal_key"] == signal_key), None)
            if existing:
                st.info(f"Your decision for this setup: {existing['decision']} · {existing['time']}")
            a1, a2 = st.columns(2)
            if a1.button("✅ APPROVE FOR MANUAL TRADE", key=f"approve_{asset}_{r['last_candle_time'].value}", use_container_width=True):
                st.session_state["approval_log"].append({
                    "signal_key": signal_key, "time": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                    "asset": asset, "decision": "APPROVED", "side": r["signal"],
                    "entry": float(r["entry"]), "sl": float(r["sl"]), "tp1": float(r["tp1"]),
                    "tp2": float(r["tp2"]), "tp3": float(r["tp3"]), "score": int(r["score"])
                })
                st.success("Approved in this dashboard only. Open MT5 and place the order yourself after checking the live price and contract details.")
            if a2.button("✖ REJECT SIGNAL", key=f"reject_{asset}_{r['last_candle_time'].value}", use_container_width=True):
                st.session_state["approval_log"].append({
                    "signal_key": signal_key, "time": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                    "asset": asset, "decision": "REJECTED", "side": r["signal"],
                    "entry": float(r["entry"]), "sl": float(r["sl"]), "tp1": float(r["tp1"]),
                    "tp2": float(r["tp2"]), "tp3": float(r["tp3"]), "score": int(r["score"])
                })
                st.warning("Signal rejection recorded in this app session.")
        else:
            st.caption("Approval is disabled because there is no valid, unexpired signal.")

        st.markdown("**TIMEFRAME ALIGNMENT**")
        tf_rows=[]
        for tf in ["5M","15M","1H","4H"]:
            x=market[asset][tf].iloc[-1]
            tf_rows.append({
                "Timeframe":tf, "Trend":trend_of(x),
                "Close":round(float(x["close"]),4),
                "EMA 20":round(float(x["ema20"]),4),
                "EMA 50":round(float(x["ema50"]),4),
                "EMA 200":round(float(x["ema200"]),4),
                "RSI":round(float(x["rsi"]),1),
                "ADX":round(float(x["adx"]),1),
            })
        st.dataframe(pd.DataFrame(tf_rows),use_container_width=True,hide_index=True)

        with st.expander("Signal quality checklist"):
            check_rows=[{"Condition":k,"Status":"PASS" if v else "NOT CONFIRMED"} for k,v in r["checks"].items()]
            st.dataframe(pd.DataFrame(check_rows),use_container_width=True,hide_index=True)
            st.caption(f"BUY score: {r['buy_score']}/100 · SELL score: {r['sell_score']}/100 · RSI: {r['rsi']:.1f} · ADX: {r['adx']:.1f}")
            st.caption("A PASS checklist or high score is not a statistical probability of success.")

# ------------------------------ RISK CALCULATOR ------------------------------

st.divider()
st.subheader("🛡️ POSITION RISK PLANNER")
st.caption("Use this to estimate a cash risk budget. Contract size, pip/tick value and lot sizing differ by broker and instrument.")
rc1,rc2,rc3=st.columns(3)
rc1.metric("ACCOUNT BALANCE",f"${account_size:,.2f}")
rc2.metric("RISK SETTING",f"{risk_pct:.2f}%")
rc3.metric("MAX PLANNED LOSS",f"${account_size*risk_pct/100:,.2f}")
st.caption("Do not use the cash risk figure as a lot-size instruction. Confirm contract specifications with your broker.")

# ------------------------------ MANUAL TRADE JOURNAL ------------------------------

st.divider()
st.subheader("📝 MANUAL TRADE JOURNAL")
st.caption("Record trades that you actually placed in MT5. This is a local app-session log, not a permanent cloud database.")
with st.form("manual_trade_journal_form", clear_on_submit=True):
    j1, j2, j3 = st.columns(3)
    journal_asset = j1.selectbox("Market", ["GOLD", "BTC"])
    journal_side = j2.selectbox("Direction", ["BUY", "SELL"])
    journal_result = j3.selectbox("Result", ["OPEN", "WIN", "LOSS", "BREAKEVEN", "CANCELLED"])
    j4, j5, j6 = st.columns(3)
    journal_entry = j4.number_input("Actual Entry Price", min_value=0.0, value=0.0, format="%.5f")
    journal_exit = j5.number_input("Exit Price (0 if open)", min_value=0.0, value=0.0, format="%.5f")
    journal_pnl = j6.number_input("P/L in USD (optional)", value=0.0, format="%.2f")
    journal_notes = st.text_input("Notes (optional)", max_chars=160)
    journal_submit = st.form_submit_button("➕ SAVE TRADE RECORD", use_container_width=True)
    if journal_submit:
        if journal_entry <= 0:
            st.error("Enter a valid actual entry price before saving.")
        else:
            st.session_state["trade_journal"].append({
                "Time Kabul": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                "Market": journal_asset, "Direction": journal_side, "Status": journal_result,
                "Entry": journal_entry, "Exit": journal_exit if journal_exit > 0 else None,
                "P/L USD": journal_pnl, "Notes": journal_notes
            })
            st.success("Trade record saved for this app session.")

if st.session_state["trade_journal"]:
    journal_df = pd.DataFrame(st.session_state["trade_journal"])
    st.dataframe(journal_df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ DOWNLOAD TRADE JOURNAL CSV", journal_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"AFG_trade_journal_{today}.csv", mime="text/csv", use_container_width=True)
else:
    st.info("No manual trades recorded in this session yet.")

if st.session_state["approval_log"]:
    with st.expander("Signal approval history"):
        approval_df = pd.DataFrame(st.session_state["approval_log"])
        st.dataframe(approval_df.drop(columns=["signal_key"], errors="ignore"), use_container_width=True, hide_index=True)
        st.download_button("⬇️ DOWNLOAD APPROVAL HISTORY CSV", approval_df.drop(columns=["signal_key"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"AFG_approval_history_{today}.csv", mime="text/csv", use_container_width=True)

# ------------------------------ SESSIONS ------------------------------

st.divider()
st.subheader("🌍 TRADING SESSIONS")
session_cols=st.columns(3)
for col,(name,active,clock) in zip(session_cols,session_status()):
    col.metric(name,"OPEN" if active else "CLOSED",f"Local exchange time {clock}")

# ------------------------------ DATA WARNINGS / AUDIT ------------------------------

if errors:
    with st.expander("Market data warnings"):
        for asset, items in errors.items():
            st.markdown(f"**{asset}**")
            for item in items:
                st.write(f"- {item}")

with st.expander("V10 methodology, limits and safety"):
    st.write("""
    - Uses completed candles only; the current forming candle is excluded.
    - Dashboard recalculates every 40 minutes while the browser session remains active; mobile background sleep or connection loss can delay refresh. No push notifications are sent.
    - A setup expires 40 minutes after the latest completed 15-minute candle close; expired or stale setups are disabled.
    - Requires aligned 4H, 1H and 15M trends, a 15M EMA pullback and candle confirmation, 5M momentum, RSI and ADX filters.
    - BUY LIMIT / SELL LIMIT levels are analytical estimates, not broker orders.
    - Technical score measures rule alignment only. It is not a win rate, confidence probability or guarantee.
    - Manual approvals and trade journal records are held in Streamlit session state and can reset after app restart or a new session; download CSV backups regularly.
    - The daily signal counter is held in Streamlit session state. A full app restart or a new session may reset it; it is not a durable account-wide trading lock.
    - This version does not claim a verified 99% accuracy. Validate it with out-of-sample historical testing and a demo account, including fees, spread, slippage and missed limit fills.
    - Position size is intentionally not calculated because broker contract specifications are not known.
    """)
st.caption("AFG AI GOLD PRO ELITE V10 · Decision-support software only · No trade execution")
