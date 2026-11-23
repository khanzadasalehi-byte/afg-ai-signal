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
    "ابزار تحلیلی و آموزشی است؛ سیگنال‌ها تضمین سود نیستند. "
    "درصد اطمینان، امتیاز مدل بر اساس شروط تکنیکال است، نه احتمال آماری موفقیت."
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
    st.header("تنظیمات")
    refresh = st.button("🔄 دریافت اطلاعات تازه", use_container_width=True)
    st.caption("کلید API از Streamlit Secrets خوانده می‌شود.")
    st.divider()
    st.subheader("تنظیمات مدیریت ریسک")
    atr_sl = st.slider("ضریب ATR حد ضرر", 1.0, 3.0, 1.5, 0.1)
    min_adx = st.slider("حداقل ADX برای ورود", 15, 35, 20, 1)
    min_confidence = st.slider("حداقل امتیاز سیگنال", 55, 90, 70, 1)
    st.caption("تغییر این گزینه‌ها فقط منطق تحلیلی را تغییر می‌دهد و تضمین‌کننده نتیجه نیست.")

try:
    API_KEY = st.secrets["TWELVE_DATA_API_KEY"]
except Exception:
    API_KEY = ""

if not API_KEY:
    st.error(
        "کلید API پیدا نشد. در تنظیمات Streamlit → Secrets، "
        "کلید TWELVE_DATA_API_KEY را مانند قبل نگه‌دار."
    )
    st.stop()


# -------------------------- DATA --------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_candles(interval: str, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": 300,
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
        raise ValueError("ساختار اطلاعات دریافتی معتبر نیست.")

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=required).sort_values("datetime").reset_index(drop=True)

    if len(df) < 210:
        raise ValueError(f"تعداد کندل کافی نیست: {len(df)}؛ حداقل 210 کندل لازم است.")

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
        sessions.append("آسیا")
    if 7 <= hour < 16:
        sessions.append("لندن")
    if 13 <= hour < 22:
        sessions.append("نیویورک")
    return " + ".join(sessions) if sessions else "بین سیشن‌های اصلی"


# -------------------------- LOAD & ANALYZE --------------------------

if refresh:
    st.cache_data.clear()

frames = {}
errors = []

with st.spinner("در حال دریافت و تحلیل اطلاعات طلا از Twelve Data..."):
    for label, interval in INTERVALS.items():
        try:
            raw = get_candles(interval, API_KEY)
            frames[label] = add_indicators(raw)
        except Exception as exc:
            errors.append(f"{label}: {exc}")

if errors:
    st.error("دریافت اطلاعات کامل نشد:")
    for err in errors:
        st.write(f"- {err}")
    st.info("کلید API، محدودیت درخواست‌ها و اتصال اینترنت را بررسی کن.")
    st.stop()

result = analyze_signal(frames, atr_sl, min_adx, min_confidence)
last_price = float(frames["15M"].iloc[-1]["close"])
last_time = frames["15M"].iloc[-1]["datetime"].to_pydatetime()
local_time = last_time.astimezone(LOCAL_TZ)

# -------------------------- TOP METRICS --------------------------

m1, m2, m3, m4 = st.columns(4)
m1.metric("قیمت XAU/USD", f"{last_price:,.2f}")
m2.metric("سیگنال", result["signal"])
m3.metric("امتیاز تحلیلی", f'{result["score"]}%')
m4.metric("سیشن فعلی", market_session())

st.caption(f"زمان آخرین کندل 15M: {local_time.strftime('%Y-%m-%d %H:%M')} کابل")

# -------------------------- SIGNAL PANEL --------------------------

st.divider()
st.subheader("🎯 سیگنال اصلی و مدیریت معامله")

if result["signal"] == "BUY":
    st.success("سیگنال BUY — فقط پس از بررسی شرایط بازار و ریسک شخصی")
elif result["signal"] == "SELL":
    st.error("سیگنال SELL — فقط پس از بررسی شرایط بازار و ریسک شخصی")
else:
    st.warning("NO TRADE — شروط ورود کامل نیستند؛ از ورود اجباری خودداری کن.")

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
        "سطوح SL و TP با ATR تایم‌فریم 15M و نسبت‌های ریسک/بازده 1:1، 1:2 و 1:3 محاسبه شده‌اند. "
        "اسپرد، لغزش قیمت و کارمزد در این محاسبه لحاظ نشده‌اند."
    )
else:
    st.write(
        "سیستم در حال حاضر نقطه ورود معتبر تشخیص نداده است. "
        "سطوح SL و TP عمداً نمایش داده نمی‌شوند تا از برداشت اشتباه درباره یک معامله نامعتبر جلوگیری شود."
    )

# -------------------------- MULTI-TIMEFRAME TABLE --------------------------

st.divider()
st.subheader("📊 تحلیل چند تایم‌فریم")

rows = []
for label in ["5M", "15M", "1H", "4H"]:
    r = frames[label].iloc[-1]
    rows.append({
        "تایم‌فریم": label,
        "قیمت": round(float(r["close"]), 2),
        "EMA 20": round(float(r["ema20"]), 2),
        "EMA 50": round(float(r["ema50"]), 2),
        "EMA 200": round(float(r["ema200"]), 2),
        "RSI": round(float(r["rsi"]), 2),
        "ADX": round(float(r["adx"]), 2),
        "+DI": round(float(r["plus_di"]), 2),
        "-DI": round(float(r["minus_di"]), 2),
        "MACD": "مثبت" if r["macd_hist"] > 0 else "منفی",
        "روند": trend_of(r),
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# -------------------------- WHY SIGNAL --------------------------

st.subheader("🔎 دلیل تصمیم سیستم")
why = [
    f"روند 4H: {result['trend_4h']}",
    f"روند 1H: {result['trend_1h']}",
    f"روند 15M: {result['trend_15m']}",
    f"امتیاز خرید: {result['buy_score']}/100",
    f"امتیاز فروش: {result['sell_score']}/100",
    f"فیلتر ADX در 15M: {'تأیید شد' if result['adx_ok'] else 'تأیید نشد'}",
    f"پولبک خرید به EMA20: {'تأیید شد' if result['buy_pullback'] else 'تأیید نشد'}",
    f"پولبک فروش به EMA20: {'تأیید شد' if result['sell_pullback'] else 'تأیید نشد'}",
    f"کندل تأییدی صعودی: {'تأیید شد' if result['bullish_candle'] else 'تأیید نشد'}",
    f"کندل تأییدی نزولی: {'تأیید شد' if result['bearish_candle'] else 'تأیید نشد'}",
]
for item in why:
    st.write(f"• {item}")

# -------------------------- RECENT PRICE DATA --------------------------

with st.expander("نمایش آخرین کندل‌های 15 دقیقه"):
    view = frames["15M"][["datetime", "open", "high", "low", "close", "rsi", "adx"]].tail(12).copy()
    view["datetime"] = view["datetime"].dt.strftime("%Y-%m-%d %H:%M UTC")
    st.dataframe(view.sort_values("datetime", ascending=False), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "AFG AI GOLD PRO ELITE | داده‌ها از Twelve Data دریافت می‌شوند. "
    "سیگنال‌ها ممکن است با بسته‌شدن کندل جدید تغییر کنند. پیش از هر معامله، "
    "قیمت لحظه‌ای کارگزار، اسپرد، اندازه موقعیت و حداکثر ریسک حساب را جداگانه بررسی کن."
)
