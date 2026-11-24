import streamlit as st
import pandas as pd
import numpy as np
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ==========================================================
# AFG AI GOLD PRO ELITE V11 - SMART BALANCED
# SMC 30 + ICT 25 + Advanced Price Action 25 + Technical 20
# Twelve Data | Manual trading only | Decision support
# ==========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO ELITE V11",
    page_icon="🇦🇫",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

.signal-card { border:2px solid #a83d50; border-radius:20px; overflow:hidden; background:#0d0717; margin:10px 0 20px; box-shadow:0 8px 30px rgba(0,0,0,.28); }
.signal-head { padding:24px 18px 20px; text-align:center; background:linear-gradient(180deg,#21090e,#160812); border-bottom:1px solid #35203e; }
.signal-side { font-size:42px; font-weight:900; letter-spacing:5px; line-height:1.15; }
.signal-sub { color:#b889a7; font-size:12px; letter-spacing:2px; margin-top:8px; }
.signal-pill { display:inline-block; margin-top:16px; padding:10px 18px; border-radius:30px; border:1px solid #70502a; background:#21170d; color:#f1c76d; font-weight:800; font-size:12px; letter-spacing:1px; }
.signal-status { margin:16px 0 0; padding:17px 12px; border:1px solid #267b4b; border-radius:15px; background:#0b1c16; color:#55d98a; font-weight:900; letter-spacing:2px; font-size:14px; }
.signal-status.wait { border-color:#8d6332; background:#21180e; color:#e7bd68; }
.signal-meta { display:flex; justify-content:space-between; gap:12px; padding:18px; background:#10091d; border-bottom:1px solid #30213b; color:#bca1d9; }
.signal-meta strong { color:#54e28c; font-size:25px; display:block; }
.signal-price { padding:16px 12px; text-align:center; border-bottom:1px solid #30213b; background:#10091a; }
.signal-price .lbl { color:#a68abf; font-size:12px; letter-spacing:3px; font-weight:800; }
.signal-price .num { color:#d4b5ff; font-size:23px; font-weight:800; margin-top:5px; }
.signal-price.stop .num { color:#ff666d; }
.signal-targets { padding:16px 14px; background:#0d0818; }
.signal-target-title { text-align:center; color:#b99bd9; letter-spacing:2px; font-weight:800; margin:2px 0 14px; }
.signal-target { padding:13px 12px; margin:10px 0; border-radius:14px; background:#10121e; border:1px solid #2d3040; border-left:5px solid #38ce81; }
.signal-target-top { display:flex; justify-content:space-between; gap:8px; color:#65d99a; font-weight:800; font-size:13px; }
.signal-target-top .rr { color:#b89bd6; }
.signal-target-bar { height:8px; background:#2a1738; border-radius:20px; margin-top:12px; overflow:hidden; }
.signal-target-bar span { display:block; height:8px; border-radius:20px; background:linear-gradient(90deg,#b87822,#f4b52e); }
.signal-invalidation { display:flex; justify-content:space-between; gap:8px; padding:15px 18px; border-top:1px solid #30213b; color:#b99bd9; font-weight:800; letter-spacing:2px; }
.signal-invalidation strong { color:#ff737a; font-size:20px; }
.signal-muted { color:#9b88ae; font-size:12px; }
@media(max-width:600px){ .signal-side{font-size:34px;} .signal-meta{padding:14px;} .signal-price .num{font-size:20px;} }

hr { border-color:rgba(214,173,85,.22) !important; }
@media(max-width:900px){ div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.6rem!important;} div[data-testid="stHorizontalBlock"]>div[data-testid="column"]{flex:1 1 180px!important;min-width:min(180px,100%)!important;} }
</style>
<div class="hero">
  <div class="hero-kicker">🇦🇫 AFG FINANCIAL INTELLIGENCE</div>
  <div class="hero-title">GOLD PRO <span style="color:#e7c77f">ELITE V11</span></div>
  <div class="hero-sub">ADVANCED PRICE ACTION ONLY · MARKET STRUCTURE · LIQUIDITY · FVG · MANUAL TRADING</div>
</div>
""", unsafe_allow_html=True)

st.caption("V11 PRICE ACTION · Separate SCALP and DAILY signal panels · Range-only signal block · Manual trading only")
st.warning("Technical scores are rule-alignment scores, NOT win probabilities. No system guarantees accuracy or profit. Verify every setup and test on a demo account.")

API_URL = "https://api.twelvedata.com/time_series"
SYMBOLS = {"GOLD": "XAU/USD", "BTC": "BTC/USD"}
INTERVALS = {"5M": "5min", "15M": "15min", "1H": "1h", "4H": "4h"}
DELTAS = {
    "5min": pd.Timedelta(minutes=5), "15min": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4),
}
LOCAL_TZ = ZoneInfo("Asia/Kabul")
TIMEOUT = 25
SCAN_INTERVAL_MINUTES = 5  # frequent refresh for short-term scanner
SCALP_VALIDITY_MINUTES = 45
DAILY_VALIDITY_MINUTES = 240
DAILY_SIGNAL_TARGET = 5  # Daily target across GOLD + BTC; never force trades in a range.
MAX_DAILY_SIGNALS = 9999  # No artificial cap; only valid price-action setups are counted.

st_autorefresh(interval=SCAN_INTERVAL_MINUTES * 60 * 1000, key="afg_v11_smart_refresh")

with st.sidebar:
    st.markdown("### 🇦🇫 AFG GOLD PRO")
    st.caption("V11 · PRICE ACTION ONLY")
    refresh = st.button("🔄 Refresh Market Data", use_container_width=True)
    st.divider()
    st.markdown("**Risk settings**")
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.1, max_value=3.0, value=0.5, step=0.1)
    account_size = st.number_input("Account balance (USD)", min_value=10.0, value=1000.0, step=100.0)
    min_score = st.slider("Minimum price-action score", 40, 100, 50)
    st.caption("Signal direction and qualification use price action only. RSI/ADX/EMA/MACD are shown for reference and do not decide signals.")
    st.divider()
    st.caption("Twelve Data · SCALP refresh every 5 minutes · DAILY signal tracking · Daily target: 5 valid setups across both markets")

try:
    API_KEY = st.secrets["TWELVE_DATA_API_KEY"]
except Exception:
    API_KEY = ""

if not API_KEY:
    st.error("API key not found. Configure TWELVE_DATA_API_KEY in Streamlit Secrets. Never paste your API key into chat.")
    st.stop()

if refresh:
    st.cache_data.clear()


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
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=3)
    df = df[df["datetime"] + DELTAS[interval] <= cutoff].reset_index(drop=True)
    if len(df) < 220:
        raise ValueError(f"Only {len(df)} closed candles received; at least 220 are required.")
    return df


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
    body_ratio = abs(float(row["close"] - row["open"])) / rng
    if direction == "BUY":
        close_location = (float(row["high"]) - float(row["close"])) / rng
        return float(row["close"]) > float(row["open"]) and body_ratio >= 0.30 and close_location <= 0.30
    close_location = (float(row["close"]) - float(row["low"])) / rng
    return float(row["close"]) < float(row["open"]) and body_ratio >= 0.30 and close_location <= 0.30


def analyze_smart_confluence(frames: dict) -> dict:
    """
    SMART BALANCED confluence:
    SMC 30, ICT 25, Advanced Price Action 25, Technical 20.
    All pattern tests use completed candles. This is a rule-based approximation,
    not a claim to identify every discretionary SMC/ICT concept.
    """
    d = frames["15M"].copy().reset_index(drop=True)
    r = d.iloc[-1]
    prev = d.iloc[-2]
    buy_smc = sell_smc = 0
    buy_ict = sell_ict = 0
    buy_pa = sell_pa = 0

    # Confirmed local swing points: two candles on either side.
    lookback = d.tail(62).reset_index(drop=True)
    swing_highs, swing_lows = [], []
    for i in range(2, len(lookback) - 2):
        h, lo = float(lookback.iloc[i]["high"]), float(lookback.iloc[i]["low"])
        if h > float(lookback.iloc[i-2:i]["high"].max()) and h > float(lookback.iloc[i+1:i+3]["high"].max()):
            swing_highs.append((i, h))
        if lo < float(lookback.iloc[i-2:i]["low"].min()) and lo < float(lookback.iloc[i+1:i+3]["low"].min()):
            swing_lows.append((i, lo))

    last_high = swing_highs[-1][1] if swing_highs else None
    last_low = swing_lows[-1][1] if swing_lows else None

    # Liquidity sweep / raid: wick crosses a confirmed swing, close returns inside.
    buy_sweep = last_low is not None and float(r["low"]) < last_low and float(r["close"]) > last_low
    sell_sweep = last_high is not None and float(r["high"]) > last_high and float(r["close"]) < last_high
    if buy_sweep:
        buy_smc += 10
        buy_ict += 5
    if sell_sweep:
        sell_smc += 10
        sell_ict += 5

    # BOS and CHoCH-like close beyond the latest confirmed swing.
    if last_high is not None and float(r["close"]) > last_high:
        buy_smc += 8
    if last_low is not None and float(r["close"]) < last_low:
        sell_smc += 8

    # Three-candle fair value gap. Current candle must create the gap.
    if len(d) >= 3:
        candle_1 = d.iloc[-3]
        bullish_fvg = float(r["low"]) > float(candle_1["high"])
        bearish_fvg = float(r["high"]) < float(candle_1["low"])
        if bullish_fvg:
            buy_smc += 6
            buy_ict += 3
        if bearish_fvg:
            sell_smc += 6
            sell_ict += 3

    # Premium / discount of the recent dealing range.
    dealing = d.tail(60)
    range_high = float(dealing["high"].max())
    range_low = float(dealing["low"].min())
    midpoint = (range_high + range_low) / 2
    if float(r["close"]) < midpoint:
        buy_smc += 6
    elif float(r["close"]) > midpoint:
        sell_smc += 6

    # ICT displacement: large real body relative to ATR and candle range.
    atr = max(float(r["atr"]) if np.isfinite(r["atr"]) else 0.0, 1e-12)
    candle_range = max(float(r["high"] - r["low"]), 1e-12)
    body = abs(float(r["close"] - float(r["open"])))
    bullish_displacement = float(r["close"]) > float(r["open"]) and body / candle_range >= 0.65 and candle_range >= 1.2 * atr
    bearish_displacement = float(r["close"]) < float(r["open"]) and body / candle_range >= 0.65 and candle_range >= 1.2 * atr
    if bullish_displacement:
        buy_ict += 8
    if bearish_displacement:
        sell_ict += 8

    # Approximate OTE retracement zones of the recent range.
    swing_range = range_high - range_low
    if swing_range > 0:
        bullish_ote_low = range_high - swing_range * 0.79
        bullish_ote_high = range_high - swing_range * 0.62
        bearish_ote_low = range_low + swing_range * 0.62
        bearish_ote_high = range_low + swing_range * 0.79
        if bullish_ote_low <= float(r["close"]) <= bullish_ote_high:
            buy_ict += 8
        if bearish_ote_low <= float(r["close"]) <= bearish_ote_high:
            sell_ict += 8

    # Simplified order-block retest: recent opposite candle followed by close beyond its range.
    for i in range(len(d)-2, max(-1, len(d)-9), -1):
        ob, impulse = d.iloc[i], d.iloc[i+1]
        if float(ob["close"]) < float(ob["open"]) and float(impulse["close"]) > float(ob["high"]):
            if float(ob["low"]) <= float(r["close"]) <= float(ob["high"]):
                buy_ict += 5
            break
    for i in range(len(d)-2, max(-1, len(d)-9), -1):
        ob, impulse = d.iloc[i], d.iloc[i+1]
        if float(ob["close"]) > float(ob["open"]) and float(impulse["close"]) < float(ob["low"]):
            if float(ob["low"]) <= float(r["close"]) <= float(ob["high"]):
                sell_ict += 5
            break

    # Kill-zone timing is based on current UTC clock, not candle timestamp.
    now = datetime.now(timezone.utc)
    london = now.astimezone(ZoneInfo("Europe/London"))
    new_york = now.astimezone(ZoneInfo("America/New_York"))
    killzone = (7 <= london.hour < 10) or (8 <= new_york.hour < 11)
    if killzone:
        buy_ict += 4
        sell_ict += 4

    # Advanced price action: engulfing, rejection wick, breakout-retest.
    previous_bullish = float(prev["close"]) > float(prev["open"])
    previous_bearish = float(prev["close"]) < float(prev["open"])
    current_bullish = float(r["close"]) > float(r["open"])
    current_bearish = float(r["close"]) < float(r["open"])

    if current_bullish and previous_bearish and float(r["close"]) > float(prev["open"]) and float(r["open"]) < float(prev["close"]):
        buy_pa += 10
    if current_bearish and previous_bullish and float(r["close"]) < float(prev["open"]) and float(r["open"]) > float(prev["close"]):
        sell_pa += 10

    upper_wick = float(r["high"]) - max(float(r["open"]), float(r["close"]))
    lower_wick = min(float(r["open"]), float(r["close"])) - float(r["low"])
    if lower_wick >= max(body, 1e-12) * 2 and current_bullish:
        buy_pa += 8
    if upper_wick >= max(body, 1e-12) * 2 and current_bearish:
        sell_pa += 8

    prior = d.iloc[-7:-1]
    if len(prior) == 6:
        resistance = float(prior["high"].max())
        support = float(prior["low"].min())
        if float(prev["close"]) > resistance and float(r["low"]) <= resistance and float(r["close"]) > resistance:
            buy_pa += 7
        if float(prev["close"]) < support and float(r["high"]) >= support and float(r["close"]) < support:
            sell_pa += 7

    # Technical indicators are intentionally excluded from signal scoring.
    # Directional decisions are made only from OHLC price action / structure.
    buy_technical = sell_technical = 0

    # Cap each bucket to its declared maximum.
    buy_smc, sell_smc = min(30, buy_smc), min(30, sell_smc)
    buy_ict, sell_ict = min(25, buy_ict), min(25, sell_ict)
    buy_pa, sell_pa = min(25, buy_pa), min(25, sell_pa)
    buy_technical, sell_technical = min(20, buy_technical), min(20, sell_technical)

    buy_total = buy_smc + buy_ict + buy_pa + buy_technical
    sell_total = sell_smc + sell_ict + sell_pa + sell_technical

    buy_confirmations = sum([buy_smc >= 12, buy_ict >= 10, buy_pa >= 10])
    sell_confirmations = sum([sell_smc >= 12, sell_ict >= 10, sell_pa >= 10])

    return {
        "buy_smc": buy_smc, "sell_smc": sell_smc,
        "buy_ict": buy_ict, "sell_ict": sell_ict,
        "buy_pa": buy_pa, "sell_pa": sell_pa,
        "buy_technical": buy_technical, "sell_technical": sell_technical,
        "buy_total": buy_total, "sell_total": sell_total,
        "buy_confirmations": buy_confirmations,
        "sell_confirmations": sell_confirmations,
        "buy_sweep": buy_sweep, "sell_sweep": sell_sweep,
        "bullish_fvg": bullish_fvg if len(d) >= 3 else False,
        "bearish_fvg": bearish_fvg if len(d) >= 3 else False,
        "killzone": killzone, "midpoint": midpoint,
        "last_swing_high": last_high, "last_swing_low": last_low,
    }


def is_true_range(st4: dict, st1: dict, st15: dict) -> bool:
    """
    Block signals only when all three structural horizons are range-bound.
    A single ranging timeframe does not suppress a valid directional setup.
    """
    return (
        st4["bias"] == "RANGE"
        and st1["bias"] == "RANGE"
        and st15["bias"] == "RANGE"
        and not st15["bos_up"]
        and not st15["bos_dn"]
    )


def analyze_signal(frames: dict, score_floor: int):
    """Price-action-only signal engine. Indicators do not decide direction or entry."""
    d5, d15, d1, d4 = (frames[k].copy().reset_index(drop=True) for k in ["5M", "15M", "1H", "4H"])
    smart = analyze_smart_confluence(frames)  # SMC/ICT/PA pattern diagnostics; technical bucket is zero.

    def structure(df):
        x = df.tail(80).reset_index(drop=True)
        highs, lows = [], []
        for i in range(2, len(x)-2):
            if x.iloc[i].high > x.iloc[i-2:i].high.max() and x.iloc[i].high > x.iloc[i+1:i+3].high.max():
                highs.append(float(x.iloc[i].high))
            if x.iloc[i].low < x.iloc[i-2:i].low.min() and x.iloc[i].low < x.iloc[i+1:i+3].low.min():
                lows.append(float(x.iloc[i].low))
        last = x.iloc[-1]
        prev = x.iloc[-2]
        hh = len(highs) >= 2 and highs[-1] > highs[-2]
        hl = len(lows) >= 2 and lows[-1] > lows[-2]
        lh = len(highs) >= 2 and highs[-1] < highs[-2]
        ll = len(lows) >= 2 and lows[-1] < lows[-2]
        bias = "BULLISH" if hh and hl else "BEARISH" if lh and ll else "RANGE"
        sh = highs[-1] if highs else float(x.high.iloc[:-2].tail(20).max())
        sl = lows[-1] if lows else float(x.low.iloc[:-2].tail(20).min())
        bos_up = float(last.close) > sh
        bos_dn = float(last.close) < sl
        return {"bias":bias,"swing_high":sh,"swing_low":sl,"bos_up":bos_up,"bos_dn":bos_dn}

    st4, st1, st15, st5 = map(structure, (d4,d1,d15,d5))
    r, prev, prev2 = d15.iloc[-1], d15.iloc[-2], d15.iloc[-3]
    rng = max(float(r.high-r.low), 1e-12)
    body = abs(float(r.close-r.open))
    upper = float(r.high-max(r.open,r.close))
    lower = float(min(r.open,r.close)-r.low)
    bullish_engulf = float(prev.close)<float(prev.open) and float(r.close)>float(r.open) and float(r.close)>=float(prev.open) and float(r.open)<=float(prev.close)
    bearish_engulf = float(prev.close)>float(prev.open) and float(r.close)<float(r.open) and float(r.close)<=float(prev.open) and float(r.open)>=float(prev.close)
    bull_rejection = lower >= max(body,1e-12)*1.8 and float(r.close)>float(r.open) and (float(r.close)-float(r.low))/rng >= .65
    bear_rejection = upper >= max(body,1e-12)*1.8 and float(r.close)<float(r.open) and (float(r.high)-float(r.close))/rng >= .65

    # Sweep of recent confirmed liquidity pools followed by a close back inside.
    pool = d15.iloc[-22:-2]
    buy_sweep = float(r.low)<float(pool.low.min()) and float(r.close)>float(pool.low.min())
    sell_sweep = float(r.high)>float(pool.high.max()) and float(r.close)<float(pool.high.max())
    # Three-candle imbalance / FVG.
    bull_fvg = float(r.low)>float(prev2.high)
    bear_fvg = float(r.high)<float(prev2.low)
    # Breakout followed by a retest and close back beyond the broken level.
    prior = d15.iloc[-8:-2]
    resistance, support = float(prior.high.max()), float(prior.low.min())
    bull_retest = float(prev.close)>resistance and float(r.low)<=resistance and float(r.close)>resistance
    bear_retest = float(prev.close)<support and float(r.high)>=support and float(r.close)<support

    buy_points = {
        "4H bullish structure": st4["bias"]=="BULLISH",
        "1H bullish structure": st1["bias"]=="BULLISH",
        "15M bullish BOS": st15["bos_up"],
        "Liquidity sweep": buy_sweep,
        "Bullish engulfing": bullish_engulf,
        "Bullish rejection candle": bull_rejection,
        "Bullish FVG": bull_fvg,
        "Breakout retest": bull_retest,
        "5M bullish structure": st5["bias"]=="BULLISH",
    }
    sell_points = {
        "4H bearish structure": st4["bias"]=="BEARISH",
        "1H bearish structure": st1["bias"]=="BEARISH",
        "15M bearish BOS": st15["bos_dn"],
        "Liquidity sweep": sell_sweep,
        "Bearish engulfing": bearish_engulf,
        "Bearish rejection candle": bear_rejection,
        "Bearish FVG": bear_fvg,
        "Breakdown retest": bear_retest,
        "5M bearish structure": st5["bias"]=="BEARISH",
    }
    buy_score = int(sum(buy_points.values())*100/len(buy_points))
    sell_score = int(sum(sell_points.values())*100/len(sell_points))
    # Adaptive PA qualification: range is the only market regime that blocks signals.
    # Outside a range, allow earlier valid setups so directional moves are less likely
    # to be missed. This increases opportunity frequency but does not guarantee wins.
    buy_triggers = sum([buy_sweep,bullish_engulf,bull_rejection,bull_fvg,bull_retest])
    sell_triggers = sum([sell_sweep,bearish_engulf,bear_rejection,bear_fvg,bear_retest])
    ranging = is_true_range(st4, st1, st15)

    buy_context = st1["bias"] == "BULLISH" or st4["bias"] == "BULLISH"
    sell_context = st1["bias"] == "BEARISH" or st4["bias"] == "BEARISH"
    buy_confirmation = st15["bos_up"] or bull_retest or st5["bias"] == "BULLISH"
    sell_confirmation = st15["bos_dn"] or bear_retest or st5["bias"] == "BEARISH"

    strong_buy = (not ranging and st4["bias"] == st1["bias"] == "BULLISH"
                  and st15["bos_up"] and buy_triggers >= 2 and buy_score >= max(55, score_floor))
    strong_sell = (not ranging and st4["bias"] == st1["bias"] == "BEARISH"
                   and st15["bos_dn"] and sell_triggers >= 2 and sell_score >= max(55, score_floor))
    early_buy = (not ranging and buy_context and st4["bias"] != "BEARISH"
                 and buy_triggers >= 1 and buy_confirmation and buy_score >= max(40, score_floor - 10))
    early_sell = (not ranging and sell_context and st4["bias"] != "BULLISH"
                  and sell_triggers >= 1 and sell_confirmation and sell_score >= max(40, score_floor - 10))

    signal, direction = "NO TRADE", None
    score = max(buy_score,sell_score)
    if ranging:
        rejection_reason = "RANGE MARKET — signals are disabled until directional structure appears"
    else:
        rejection_reason = None
        if strong_buy and buy_score>sell_score: signal,direction,score="STRONG BUY","BUY",buy_score
        elif strong_sell and sell_score>buy_score: signal,direction,score="STRONG SELL","SELL",sell_score
        elif early_buy and buy_score>sell_score: signal,direction,score="EARLY BUY","BUY",buy_score
        elif early_sell and sell_score>buy_score: signal,direction,score="EARLY SELL","SELL",sell_score

    current=float(r.close)
    # Volatility estimate from recent candle ranges; no indicator-based direction.
    avg_range=float((d15.high-d15.low).tail(14).mean())
    entry=sl=tp1=tp2=tp3=None
    order_type=None
    risk_distance=entry_distance=rr=None
    rejection=[]
    if direction and avg_range>0:
        recent=d15.tail(12)
        if direction=="BUY":
            # Limit entry at the midpoint of the latest bullish imbalance if available,
            # otherwise at the midpoint of the latest bullish candle body.
            entry=(float(prev2.high)+float(r.low))/2 if bull_fvg else (float(r.open)+float(r.close))/2
            swing=float(recent.low.min())
            sl=min(swing-0.12*avg_range,entry-0.5*avg_range)
            risk_distance=entry-sl
            entry_distance=(current-entry)/avg_range
            order_type="BUY LIMIT"
            valid_entry=-0.15<=entry_distance<=0.85
            valid_risk=0.5*avg_range<=risk_distance<=2.5*avg_range
            if valid_entry and valid_risk: tp1,tp2,tp3=entry+risk_distance,entry+2*risk_distance,entry+3*risk_distance
        else:
            entry=(float(r.high)+float(prev2.low))/2 if bear_fvg else (float(r.open)+float(r.close))/2
            swing=float(recent.high.max())
            sl=max(swing+0.12*avg_range,entry+0.5*avg_range)
            risk_distance=sl-entry
            entry_distance=(entry-current)/avg_range
            order_type="SELL LIMIT"
            valid_entry=-0.15<=entry_distance<=0.85
            valid_risk=0.5*avg_range<=risk_distance<=2.5*avg_range
            if valid_entry and valid_risk: tp1,tp2,tp3=entry-risk_distance,entry-2*risk_distance,entry-3*risk_distance
        if valid_entry and valid_risk and risk_distance>0: rr=2.0
        else:
            rejection.append("Price-action entry or structural stop is outside allowed range")
            signal,direction,order_type="NO TRADE",None,None
            entry=sl=tp1=tp2=tp3=None

    trends={"4H":st4["bias"],"1H":st1["bias"],"15M":st15["bias"],"5M":st5["bias"]}
    checks={
        "4H/1H price structure aligned": st4["bias"]==st1["bias"] and st1["bias"] in ("BULLISH","BEARISH"),
        "15M structure break": st15["bos_up"] or st15["bos_dn"],
        "Liquidity sweep": buy_sweep or sell_sweep,
        "Engulfing / rejection candle": bullish_engulf or bearish_engulf or bull_rejection or bear_rejection,
        "Fair value gap": bull_fvg or bear_fvg,
        "Breakout retest": bull_retest or bear_retest,
        "At least two PA entry triggers": max(buy_triggers,sell_triggers)>=2,
    }
    smart.update({"buy_smc":int(buy_sweep)*10,"sell_smc":int(sell_sweep)*10,
                  "buy_ict":int(bull_fvg)*10,"sell_ict":int(bear_fvg)*10,
                  "buy_pa":int(bullish_engulf or bull_rejection or bull_retest)*20,
                  "sell_pa":int(bearish_engulf or bear_rejection or bear_retest)*20,
                  "buy_technical":0,"sell_technical":0,
                  "buy_total":buy_score,"sell_total":sell_score,
                  "buy_confirmations":buy_triggers,"sell_confirmations":sell_triggers,
                  "buy_sweep":buy_sweep,"sell_sweep":sell_sweep,
                  "bullish_fvg":bull_fvg,"bearish_fvg":bear_fvg,
                  "last_swing_high":st15["swing_high"],"last_swing_low":st15["swing_low"]})
    return {"signal":signal,"direction":direction,"score":int(score),
            "buy_score":buy_score,"sell_score":sell_score,"order_type":order_type,
            "current_price":current,"entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,
            "rr":rr,"risk_distance":risk_distance,"entry_distance_atr":entry_distance,
            "trends":trends,"checks":checks,"is_range":ranging,"range_reason":rejection_reason,"adx":float(r.get("adx",0)),"rsi":float(r.get("rsi",50)),
            "atr":avg_range,"rejection":rejection,"smart_analysis":smart}


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


market, errors = {}, {}
with st.spinner("Loading completed-candle data for Gold and Bitcoin..."):
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

# Independent SCALP and DAILY signal streams with different qualification and expiry.
scalp_results, daily_results = {}, {}
for asset, frames in market.items():
    scalp = analyze_signal(frames, max(40, min_score - 10))
    daily = analyze_signal(frames, max(60, min_score + 10))
    now_utc = datetime.now(timezone.utc)
    last15 = frames["15M"].iloc[-1]
    last_close_time = last15["datetime"].to_pydatetime() + timedelta(minutes=15)
    for res, validity in [(scalp, SCALP_VALIDITY_MINUTES), (daily, DAILY_VALIDITY_MINUTES)]:
        expiry = now_utc + timedelta(minutes=validity)
        age = now_utc - last_close_time
        stale = age > timedelta(minutes=validity)
        remaining = max(0, int((expiry - now_utc).total_seconds()))
        res.update({
            "last_price": float(last15["close"]),
            "last_candle_time": last15["datetime"].to_pydatetime(),
            "generated_at": now_utc, "stale": stale, "expired": remaining <= 0,
            "valid_until": expiry.astimezone(LOCAL_TZ), "remaining": remaining,
            "validity_minutes": validity,
        })
        if stale or remaining <= 0:
            res.update({"signal":"NO TRADE", "direction":None, "order_type":None,
                        "entry":None, "sl":None, "tp1":None, "tp2":None, "tp3":None})
    scalp_results[asset] = scalp
    daily_results[asset] = daily

# Existing detailed diagnostics below refer to the DAILY stream.
results = daily_results

today = datetime.now(LOCAL_TZ).date().isoformat()
if st.session_state.get("daily_date") != today:
    st.session_state["daily_date"] = today
    st.session_state["daily_keys"] = []
daily_keys = st.session_state.get("daily_keys", [])
for asset, res in daily_results.items():
    if res["signal"] in ("STRONG BUY", "STRONG SELL", "EARLY BUY", "EARLY SELL"):
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

if "approval_log" not in st.session_state:
    st.session_state["approval_log"] = []
if "trade_journal" not in st.session_state:
    st.session_state["trade_journal"] = []


def render_signal_card(asset: str, mode: str, res: dict, validity_label: str, daily_count: int = 0):
    """Render a signal panel inspired by the user's reference screenshot."""
    valid = res["signal"] in ("STRONG BUY", "STRONG SELL", "EARLY BUY", "EARLY SELL") and res.get("entry") is not None
    side = "BUY" if valid and res["direction"] == "BUY" else "SELL" if valid else "NO TRADE"
    color = "#4de18a" if side == "BUY" else "#ff626b" if side == "SELL" else "#e7bd68"
    score = int(res.get("score", 0))
    risk_label = "LOW RISK" if score >= 80 else "MEDIUM RISK" if score >= 60 else "HIGHER RISK"
    status = "✓  SETUP CONFIRMED — REVIEW BEFORE ENTRY" if valid else "⏳  WAIT — NO VALID SETUP"
    status_class = "" if valid else "wait"
    generated = res.get("generated_at")
    generated_txt = generated.astimezone(LOCAL_TZ).strftime("%I:%M %p") if generated else "—"
    remaining = max(0, int(res.get("remaining", 0)))
    mm, ss = divmod(remaining, 60)
    market_name = "XAUUSD" if asset == "GOLD" else "BTCUSD"
    entry = res.get("entry")
    sl = res.get("sl")
    targets = [res.get("tp1"), res.get("tp2"), res.get("tp3")]
    rr = ["1:1.00", "1:2.00", "1:3.00"]
    if valid:
        target_html = ""
        for idx, (tp, ratio) in enumerate(zip(targets, rr), 1):
            if tp is None:
                continue
            target_html += f"""
            <div class="signal-target">
              <div class="signal-target-top"><span>🎯 TP{idx}</span><span class="rr">R:R {ratio}</span><span>{tp:,.2f}</span></div>
              <div class="signal-muted" style="margin-top:9px">TARGET {idx} · PLANNED PRICE LEVEL · NOT A HISTORICAL HIT RATE</div>
            </div>"""
        entry_label = "ENTRY · LIMIT" if res.get("order_type") == "LIMIT" else "ENTRY · MARKET"
        invalidation = f"{sl:,.2f}" if sl is not None else "—"
        entry_html = f'<div class="signal-price"><div class="lbl">{entry_label}</div><div class="num">{entry:,.2f}</div></div>'
        stop_html = f'<div class="signal-price stop"><div class="lbl">STOP LOSS</div><div class="num">{sl:,.2f}</div></div>'
        target_section = f'<div class="signal-targets"><div class="signal-target-title">🎯 3-TARGET PROFIT PLAN</div>{target_html}</div>'
    else:
        entry_html = '<div class="signal-price"><div class="lbl">ENTRY</div><div class="num">WAIT FOR CONFIRMATION</div></div>'
        stop_html = ""
        target_section = '<div class="signal-targets"><div class="signal-target-title">NO TARGETS — SETUP NOT CONFIRMED</div><div class="signal-muted">The system does not invent entry, stop-loss or take-profit levels.</div></div>'
        invalidation = "—"

    session = res.get("smart_analysis", {}).get("session_name", "market structure")
    html = f"""
    <div class="signal-card" style="border-color:{color}">
      <div class="signal-head">
        <div class="signal-side" style="color:{color}">{side}</div>
        <div class="signal-sub">{market_name} &nbsp;·&nbsp; {mode.upper()} &nbsp;·&nbsp; PRICE ACTION</div>
        <div class="signal-pill">● {score}/100 &nbsp;—&nbsp; {risk_label}</div>
        <div class="signal-sub">📊 {res.get("trends", {}).get("15M", "—")} &nbsp;·&nbsp; {session}</div>
        <div class="signal-status {status_class}">{status}</div>
      </div>
      <div class="signal-meta">
        <div><strong>{mm:02d}:{ss:02d}</strong><span class="signal-muted">VALID FOR · {validity_label}</span></div>
        <div style="text-align:right"><span class="signal-muted">GENERATED</span><strong style="font-size:19px;color:#c9a9f1">{generated_txt}</strong><span class="signal-muted">KABUL TIME</span></div>
      </div>
      {entry_html}
      {stop_html}
      {target_section}
      <div class="signal-invalidation"><span>INVALIDATION</span><strong>{invalidation}</strong></div>
      <div style="padding:0 18px 14px;text-align:center" class="signal-muted">DAILY TARGET COUNT: {daily_count}/5 · SCORE IS NOT A WIN PROBABILITY</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


st.divider()
st.subheader("MARKET OVERVIEW")
scan_now_local = datetime.now(LOCAL_TZ)
next_scan_local = scan_now_local + timedelta(minutes=SCAN_INTERVAL_MINUTES)
st.info(f"AUTO REFRESH: every {SCAN_INTERVAL_MINUTES} minutes while this dashboard is open · Last calculation: {scan_now_local.strftime('%Y-%m-%d %H:%M:%S')} Kabul time · Next refresh: about {next_scan_local.strftime('%H:%M')} Kabul time. Browser sleep can delay refresh; no push alert is sent.")
overview_cols = st.columns(4)
for idx, (asset, symbol) in enumerate([("GOLD", "XAU/USD"), ("BTC", "BTC/USD")]):
    if asset in results:
        overview_cols[idx*2].metric(symbol, f"{results[asset]['last_price']:,.2f}")
        overview_cols[idx*2+1].metric(f"{asset} DAILY SIGNAL", daily_results[asset]["signal"])
    else:
        overview_cols[idx*2].metric(symbol, "DATA ERROR")
        overview_cols[idx*2+1].metric(f"{asset} SIGNAL", "DISABLED")
st.caption(f"DAILY valid-setup count: {daily_count} / {DAILY_SIGNAL_TARGET} target across GOLD + BTC · Kabul date: {today}. Target is not forced when the market is ranging or setups are invalid.")

st.divider()
st.subheader("⚡ SCALP SIGNALS")
st.caption("Short-term signal cards · refresh every 5 minutes · each signal valid up to 45 minutes.")
sc_cols = st.columns(2)
for col, asset in zip(sc_cols, ["GOLD", "BTC"]):
    with col:
        if asset in scalp_results:
            render_signal_card(asset, "SCALP", scalp_results[asset], "45 MIN")
        else:
            st.error(f"{asset}: market data unavailable")

st.divider()
st.subheader("📈 DAILY SIGNALS")
st.caption("Separate higher-timeframe signal cards · stricter qualification · validity up to 4 hours.")
dy_cols = st.columns(2)
for col, asset in zip(dy_cols, ["GOLD", "BTC"]):
    with col:
        if asset in daily_results:
            render_signal_card(asset, "DAILY", daily_results[asset], "4 HOURS", daily_count)
        else:
            st.error(f"{asset}: market data unavailable")

st.subheader("🔎 DAILY PRICE ACTION DIAGNOSTICS")
scanner = []
for asset, title in [("GOLD","XAU/USD"),("BTC","BTC/USD")]:
    if asset not in results:
        scanner.append({"Market":title,"Price":"—","4H":"—","1H":"—","15M":"—","5M":"—","Score":"—","Signal":"DATA ERROR"})
        continue
    r = results[asset]
    scanner.append({
        "Market":title, "Price":round(r["last_price"],2),
        "4H":r["trends"]["4H"], "1H":r["trends"]["1H"],
        "15M":r["trends"]["15M"], "5M":r["trends"]["5M"],
        "Score":f'{r["score"]}/100', "Signal":r["signal"],
    })
st.dataframe(pd.DataFrame(scanner), use_container_width=True, hide_index=True)

tabs = st.tabs(["🥇 GOLD · XAU/USD", "₿ BITCOIN · BTC/USD"])
for tab, asset, title in zip(tabs, ["GOLD","BTC"], ["GOLD · XAU/USD","BITCOIN · BTC/USD"]):
    with tab:
        st.subheader(title + " · DAILY")
        if asset not in results:
            st.error("This asset is temporarily unavailable.")
            for e in errors.get(asset, []):
                st.write(f"- {e}")
            continue
        r = results[asset]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("PRICE", f'{r["last_price"]:,.2f}')
        c2.metric("SIGNAL", r["signal"])
        c3.metric("PRICE ACTION SCORE", f'{r["score"]}/100')
        c4.metric("RISK / TRADE", f"{risk_pct:.1f}%")

        if r["stale"]:
            st.error("STALE DATA — new trades disabled until fresh 15M data arrives.")
        elif r["expired"]:
            st.warning("SETUP WINDOW EXPIRED — wait for a new setup.")
        elif r["daily_cap"]:
            st.warning("DAILY SIGNAL LIMIT REACHED.")
        elif r["signal"] == "STRONG BUY":
            st.success("STRONG BUY — high rule confluence. Verify live price before placing a manual order.")
        elif r["signal"] == "STRONG SELL":
            st.error("STRONG SELL — high rule confluence. Verify live price before placing a manual order.")
        elif r["signal"] == "EARLY BUY":
            st.warning("EARLY BUY — earlier setup with higher risk; use extra caution.")
        elif r["signal"] == "EARLY SELL":
            st.warning("EARLY SELL — earlier setup with higher risk; use extra caution.")
        else:
            st.info("NO TRADE — market is ranging or no valid directional price-action entry is confirmed.")

        active_signal = r["signal"] in ("STRONG BUY","STRONG SELL","EARLY BUY","EARLY SELL")
        if active_signal and r["entry"] is not None:
            vals = [("LIMIT ENTRY",r["entry"]),("STOP LOSS",r["sl"]),("TAKE PROFIT 1",r["tp1"]),("TAKE PROFIT 2",r["tp2"]),("TAKE PROFIT 3",r["tp3"])]
            cols = st.columns(5)
            for col,(label,value) in zip(cols,vals):
                col.metric(label,f"{value:,.2f}")
            risk_cash = account_size * risk_pct / 100
            st.info(f'Illustrative risk budget: ${risk_cash:,.2f}. Price risk distance: {r["risk_distance"]:.4f}. Lot size is not calculated; confirm broker contract specifications.')
            issued_local = r["generated_at"].astimezone(LOCAL_TZ)
            st.caption(f'Calculated: {issued_local.strftime("%Y-%m-%d %H:%M:%S")} Kabul time · Valid until: {r["valid_until"].strftime("%Y-%m-%d %H:%M")} Kabul time · {r["remaining"]//60} minutes remaining · TP2 target: 2R.')
            if r["signal"].startswith("EARLY"):
                st.warning("EARLY setup: consider smaller risk than your normal plan. This app does not calculate lot size.")
        else:
            st.caption("No active Entry, Stop Loss or Take Profit because the setup did not pass all required filters.")

        st.markdown("### 🧠 ADVANCED PRICE ACTION ANALYSIS")
        smart = r["smart_analysis"]
        smart_rows = [
            {"Engine":"SMC","BUY":f'{smart["buy_smc"]}/30',"SELL":f'{smart["sell_smc"]}/30'},
            {"Engine":"ICT","BUY":f'{smart["buy_ict"]}/25',"SELL":f'{smart["sell_ict"]}/25'},
            {"Engine":"ADVANCED PRICE ACTION","BUY":f'{smart["buy_pa"]}/25',"SELL":f'{smart["sell_pa"]}/25'},
            {"Engine":"TECHNICAL","BUY":f'{smart["buy_technical"]}/20',"SELL":f'{smart["sell_technical"]}/20'},
            {"Engine":"TOTAL","BUY":f'{smart["buy_total"]}/100',"SELL":f'{smart["sell_total"]}/100'},
        ]
        st.dataframe(pd.DataFrame(smart_rows), use_container_width=True, hide_index=True)
        st.caption(
            f'Liquidity sweep BUY: {"YES" if smart["buy_sweep"] else "NO"} · '
            f'Liquidity sweep SELL: {"YES" if smart["sell_sweep"] else "NO"} · '
            f'Bullish FVG: {"YES" if smart["bullish_fvg"] else "NO"} · '
            f'Bearish FVG: {"YES" if smart["bearish_fvg"] else "NO"} · '
            f'ICT Kill Zone: {"ACTIVE" if smart["killzone"] else "INACTIVE"}'
        )
        st.caption(f'Market midpoint: {smart["midpoint"]:,.4f} · Confirmed swing high: {smart["last_swing_high"] if smart["last_swing_high"] is not None else "N/A"} · Confirmed swing low: {smart["last_swing_low"] if smart["last_swing_low"] is not None else "N/A"}')

        st.markdown("**MANUAL SIGNAL APPROVAL**")
        if active_signal and r["entry"] is not None and not r["stale"] and not r["expired"]:
            signal_key = f'{asset}|{r["last_candle_time"].isoformat()}|{r["signal"]}|{r["entry"]:.8f}'
            existing = next((x for x in reversed(st.session_state["approval_log"]) if x["signal_key"] == signal_key), None)
            if existing:
                st.info(f'Your decision for this setup: {existing["decision"]} · {existing["time"]}')
            a1, a2 = st.columns(2)
            if a1.button("✅ APPROVE FOR MANUAL TRADE", key=f'approve_{asset}_{r["last_candle_time"].value}', use_container_width=True):
                st.session_state["approval_log"].append({
                    "signal_key": signal_key, "time": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                    "asset": asset, "decision": "APPROVED", "side": r["direction"],
                    "signal_type": r["signal"], "entry": float(r["entry"]), "sl": float(r["sl"]),
                    "tp1": float(r["tp1"]), "tp2": float(r["tp2"]), "tp3": float(r["tp3"]),
                    "score": int(r["score"])
                })
                st.success("Recorded in dashboard only. Open MT5 and place the trade yourself after checking live price.")
            if a2.button("✖ REJECT SIGNAL", key=f'reject_{asset}_{r["last_candle_time"].value}', use_container_width=True):
                st.session_state["approval_log"].append({
                    "signal_key": signal_key, "time": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                    "asset": asset, "decision": "REJECTED", "side": r["direction"],
                    "signal_type": r["signal"], "entry": float(r["entry"]), "sl": float(r["sl"]),
                    "tp1": float(r["tp1"]), "tp2": float(r["tp2"]), "tp3": float(r["tp3"]),
                    "score": int(r["score"])
                })
                st.warning("Signal rejection recorded in this app session.")
        else:
            st.caption("Approval disabled: no valid, unexpired signal.")

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
                "RSI":round(float(x["rsi"]),1), "ADX":round(float(x["adx"]),1),
            })
        st.dataframe(pd.DataFrame(tf_rows),use_container_width=True,hide_index=True)
        with st.expander("Signal quality checklist"):
            check_rows=[{"Condition":k,"Status":"PASS" if v else "NOT CONFIRMED"} for k,v in r["checks"].items()]
            st.dataframe(pd.DataFrame(check_rows),use_container_width=True,hide_index=True)
            st.caption(f'Legacy confirmation BUY: {r["buy_score"]}/100 · SELL: {r["sell_score"]}/100 · RSI: {r["rsi"]:.1f} · ADX: {r["adx"]:.1f}')
            st.caption("Smart score is rule alignment, not a win probability.")

st.divider()
st.subheader("🛡️ POSITION RISK PLANNER")
st.caption("Cash risk budget only. Contract size, tick value and lot rules differ by broker.")
rc1,rc2,rc3=st.columns(3)
rc1.metric("ACCOUNT BALANCE",f"${account_size:,.2f}")
rc2.metric("RISK SETTING",f"{risk_pct:.2f}%")
rc3.metric("MAX PLANNED LOSS",f"${account_size*risk_pct/100:,.2f}")
st.caption("Do not use the cash risk figure as a lot-size instruction. Confirm JustMarkets contract specifications.")

st.divider()
st.subheader("📝 MANUAL TRADE JOURNAL")
st.caption("Records are kept only in this Streamlit session. Download CSV backups.")
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

st.divider()
st.subheader("🌍 TRADING SESSIONS")
session_cols=st.columns(3)
for col,(name,active,clock) in zip(session_cols,session_status()):
    col.metric(name,"OPEN" if active else "CLOSED",f"Local exchange time {clock}")

if errors:
    with st.expander("Market data warnings"):
        for asset, items in errors.items():
            st.markdown(f"**{asset}**")
            for item in items:
                st.write(f"- {item}")

with st.expander("V11 methodology, limits and safety"):
    st.write("""
    - Uses completed candles only; forming candles are excluded.
    - Signal direction is determined by OHLC price action only: market structure, BOS, liquidity sweeps, engulfing/rejection candles, FVG and breakout-retest. Technical indicators are display-only.
    - SMC includes confirmed swing liquidity sweeps, structure breaks, a three-candle FVG approximation, and premium/discount location.
    - ICT includes displacement, approximate OTE, simplified order-block retests, liquidity raids, and time-based kill zones.
    - Price Action includes engulfing, rejection-wick, and breakout/retest patterns.
    - These are mechanical approximations; discretionary SMC/ICT concepts such as inducement and CHoCH are not fully modeled.
    - STRONG signals require 4H, 1H and 15M trend alignment plus legacy confirmations and smart confluence.
    - EARLY signals require 1H and 15M alignment, legacy confirmations and smart confluence; they are blocked when 4H is explicitly opposite.
    - SCALP signal validity is up to 45 minutes; DAILY signal validity is up to 4 hours. Stale data disables new trades.
    - Dashboard refreshes every 5 minutes while the browser remains active; mobile sleep can delay it. No push notifications.
    - BUY LIMIT / SELL LIMIT levels are analytical estimates, not broker orders.
    - No economic calendar/news feed or automatic 10-minute pre-news alert is connected in this file.
    - Technical score is not a win probability or guarantee.
    - Approval and journal records are session-scoped and may reset after restart/new session; download CSV backups.
    - Daily signal counter is session-scoped and may reset after app restart/new session.
    - No automatic trade execution. Validate on demo with spread, fees, slippage and missed limit fills.
    - Lot size is not calculated because broker contract specifications are not verified.
    """)
st.caption("AFG AI GOLD PRO ELITE V11 · ADVANCED PRICE ACTION ONLY · Decision-support only · No broker order execution")
