
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, time
from zoneinfo import ZoneInfo

# =========================================================
# AFG AI GOLD PRO - SESSIONS + FUNDAMENTAL + TECHNICAL
# =========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO",
    page_icon="🇦🇫",
    layout="wide"
)

st.title("🇦🇫 AFG AI GOLD PRO")
st.subheader("Gold Market Analysis | Technical + Fundamental + Sessions")

st.caption(
    "تحلیل قانون‌محور بازار طلا با درصد قدرت سیگنال؛ "
    "این درصدها احتمال واقعی برد یا تضمین سود نیستند."
)

# ---------------- CONFIG ----------------

API_URL = "https://api.twelvedata.com/time_series"
TIMEOUT = 20

TIMEFRAMES = {
    "5 دقیقه": "5min",
    "15 دقیقه": "15min",
    "1 ساعت": "1h",
    "4 ساعت": "4h"
}

WEIGHTS = {
    "technical": 0.40,
    "fundamental": 0.35,
    "session": 0.25
}

KABUL = ZoneInfo("Asia/Kabul")
TOKYO = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")

# ---------------- API KEY ----------------

try:
    saved_key = st.secrets.get("TWELVE_DATA_API_KEY", "")
except Exception:
    saved_key = ""

with st.sidebar:
    st.header("تنظیمات سیستم")

    api_key = st.text_input(
        "Twelve Data API Key",
        value=saved_key,
        type="password"
    )

    selected_tf = st.selectbox(
        "تایم‌فریم اصلی",
        list(TIMEFRAMES.keys()),
        index=1
    )

    risk_percent = st.slider(
        "ریسک هر معامله (%)",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.5
    )

    account_balance = st.number_input(
        "سرمایه فرضی ($)",
        min_value=10.0,
        value=500.0,
        step=50.0
    )

    refresh = st.button("🔄 دریافت اطلاعات جدید", use_container_width=True)

if not api_key:
    st.warning(
        "کلید Twelve Data پیدا نشد. آن را در قسمت تنظیمات وارد کن "
        "یا در Streamlit Secrets با نام TWELVE_DATA_API_KEY ذخیره کن."
    )
    st.stop()


# ---------------- DATA FETCH ----------------

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(symbol, interval, key, outputsize=200):

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": key,
        "format": "JSON",
        "timezone": "UTC"
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=TIMEOUT
    )

    response.raise_for_status()
    result = response.json()

    if "values" not in result:
        message = result.get(
            "message",
            result.get("code", "Unknown API error")
        )
        raise ValueError(f"{symbol}: {message}")

    df = pd.DataFrame(result["values"])

    if df.empty:
        raise ValueError(f"No data returned for {symbol}")

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
        errors="coerce"
    )

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(
            df["volume"],
            errors="coerce"
        )
    else:
        df["volume"] = 0

    df = df.dropna(
        subset=["datetime", "open", "high", "low", "close"]
    )

    df = df.sort_values("datetime").reset_index(drop=True)

    return df


# ---------------- INDICATORS ----------------

def add_indicators(df):

    df = df.copy()

    df["EMA20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    df["EMA200"] = df["close"].ewm(
        span=200, adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI"] = df["RSI"].fillna(50)

    ema12 = df["close"].ewm(
        span=12, adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26, adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    df["MACD_HIST"] = (
        df["MACD"] - df["MACD_SIGNAL"]
    )

    previous_close = df["close"].shift(1)

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    df["ATR"] = tr.ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()

    plus_dm = plus_dm.where(
        (plus_dm > minus_dm) & (plus_dm > 0), 0
    )

    minus_dm = minus_dm.where(
        (minus_dm > plus_dm) & (minus_dm > 0), 0
    )

    atr_safe = df["ATR"].replace(0, np.nan)

    plus_di = 100 * plus_dm.ewm(
        alpha=1 / 14, adjust=False
    ).mean() / atr_safe

    minus_di = 100 * minus_dm.ewm(
        alpha=1 / 14, adjust=False
    ).mean() / atr_safe

    dx = (
        100 * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0, np.nan)
    )

    df["PLUS_DI"] = plus_di.fillna(0)
    df["MINUS_DI"] = minus_di.fillna(0)

    df["ADX"] = dx.ewm(
        alpha=1 / 14, adjust=False
    ).mean().fillna(0)

    df["BB_MID"] = df["close"].rolling(20).mean()
    bb_std = df["close"].rolling(20).std()

    df["BB_UPPER"] = df["BB_MID"] + 2 * bb_std
    df["BB_LOWER"] = df["BB_MID"] - 2 * bb_std

    return df


# ---------------- TECHNICAL SCORE ----------------

def technical_analysis(df):

    row = df.iloc[-1]
    previous = df.iloc[-2]

    score = 0.0
    reasons = []

    # EMA trend
    if row["close"] > row["EMA20"] > row["EMA50"]:
        score += 0.25
        reasons.append("روند EMA صعودی")

    elif row["close"] < row["EMA20"] < row["EMA50"]:
        score -= 0.25
        reasons.append("روند EMA نزولی")

    # Long-term trend
    if row["close"] > row["EMA200"]:
        score += 0.15
        reasons.append("قیمت بالاتر از EMA200")

    elif row["close"] < row["EMA200"]:
        score -= 0.15
        reasons.append("قیمت پایین‌تر از EMA200")

    # RSI
    if 50 < row["RSI"] < 70:
        score += 0.15
        reasons.append("RSI مثبت")

    elif 30 < row["RSI"] < 50:
        score -= 0.15
        reasons.append("RSI منفی")

    elif row["RSI"] >= 70:
        score -= 0.05
        reasons.append("RSI در محدوده اشباع خرید")

    elif row["RSI"] <= 30:
        score += 0.05
        reasons.append("RSI در محدوده اشباع فروش")

    # MACD
    if row["MACD_HIST"] > 0:
        score += 0.20
        reasons.append("MACD صعودی")

    elif row["MACD_HIST"] < 0:
        score -= 0.20
        reasons.append("MACD نزولی")

    # ADX / Direction
    if row["ADX"] >= 20:
        if row["PLUS_DI"] > row["MINUS_DI"]:
            score += 0.15
            reasons.append("قدرت روند خریداران")

        elif row["MINUS_DI"] > row["PLUS_DI"]:
            score -= 0.15
            reasons.append("قدرت روند فروشندگان")

    # Bollinger
    if row["close"] > row["BB_MID"]:
        score += 0.10

    elif row["close"] < row["BB_MID"]:
        score -= 0.10

    score = float(np.clip(score, -1, 1))

    return score, reasons


# ---------------- SESSION ANALYSIS ----------------

def session_status():

    now_utc = datetime.now(ZoneInfo("UTC"))

    tokyo_time = now_utc.astimezone(TOKYO)
    london_time = now_utc.astimezone(LONDON)
    ny_time = now_utc.astimezone(NEW_YORK)
    kabul_time = now_utc.astimezone(KABUL)

    def is_between(t, start, end):
        return start <= t < end

    asia_active = is_between(
        tokyo_time.time(),
        time(9, 0),
        time(18, 0)
    )

    london_active = is_between(
        london_time.time(),
        time(8, 0),
        time(17, 0)
    )

    ny_active = is_between(
        ny_time.time(),
        time(8, 0),
        time(17, 0)
    )

    active = []

    if asia_active:
        active.append("Asia")

    if london_active:
        active.append("London")

    if ny_active:
        active.append("New York")

    if london_active and ny_active:
        label = "London + New York Overlap"
    elif active:
        label = " + ".join(active)
    else:
        label = "No Major Session"

    return {
        "active": active,
        "label": label,
        "kabul": kabul_time,
        "tokyo": tokyo_time,
        "london": london_time,
        "new_york": ny_time
    }


def session_analysis(df, sessions):

    if not sessions["active"]:
        return 0.0, [
            "در حال حاضر سشن اصلی فعال نیست"
        ]

    recent = df.tail(20)

    if len(recent) < 5:
        return 0.0, ["داده کافی برای تحلیل سشن موجود نیست"]

    close = float(recent["close"].iloc[-1])
    old_close = float(recent["close"].iloc[-5])

    momentum = (close - old_close) / old_close

    recent_high = float(recent["high"].iloc[:-1].max())
    recent_low = float(recent["low"].iloc[:-1].min())

    score = 0.0
    reasons = []

    if close > recent_high:
        score += 0.55
        reasons.append("شکست سقف اخیر")

    elif close < recent_low:
        score -= 0.55
        reasons.append("شکست کف اخیر")

    if momentum > 0:
        score += 0.30
        reasons.append("مومنتوم مثبت در سشن")

    elif momentum < 0:
        score -= 0.30
        reasons.append("مومنتوم منفی در سشن")

    if "London" in sessions["active"]:
        score *= 1.05
        reasons.append("فعال بودن سشن لندن")

    if "New York" in sessions["active"]:
        score *= 1.10
        reasons.append("فعال بودن سشن نیویورک")

    if "Asia" in sessions["active"]:
        reasons.append("فعال بودن سشن آسیا")

    score = float(np.clip(score, -1, 1))

    return score, reasons


# ---------------- FUNDAMENTAL PROXY ----------------

def fundamental_analysis(gold_df, eurusd_df, usdjpy_df):

    reasons = []

    # EUR/USD falling can indicate USD strength.
    eur_change = (
        eurusd_df["close"].iloc[-1]
        / eurusd_df["close"].iloc[-5] - 1
    )

    # USD/JPY rising can indicate USD strength.
    jpy_change = (
        usdjpy_df["close"].iloc[-1]
        / usdjpy_df["close"].iloc[-5] - 1
    )

    usd_strength = (
        (-float(eur_change) + float(jpy_change)) / 2
    )

    # Rising USD is generally a headwind for gold.
    usd_score = -np.tanh(usd_strength * 300)

    # Gold's recent momentum is used as a secondary market proxy.
    gold_change = (
        gold_df["close"].iloc[-1]
        / gold_df["close"].iloc[-5] - 1
    )

    gold_momentum_score = np.tanh(
        float(gold_change) * 300
    )

    score = (
        0.70 * usd_score
        + 0.30 * gold_momentum_score
    )

    if usd_strength > 0:
        reasons.append(
            "قدرت نسبی دلار افزایش یافته؛ فشار احتمالی بر طلا"
        )
    elif usd_strength < 0:
        reasons.append(
            "قدرت نسبی دلار کاهش یافته؛ حمایت احتمالی از طلا"
        )
    else:
        reasons.append("تغییر قابل‌توجهی در شاخص جایگزین دلار دیده نشد")

    if gold_change > 0:
        reasons.append("مومنتوم کوتاه‌مدت طلا مثبت است")
    else:
        reasons.append("مومنتوم کوتاه‌مدت طلا منفی است")

    reasons.append(
        "این تحلیل جایگزین فاندامنتال است؛ "
        "اخبار زنده و نرخ بهره مستقیماً دریافت نمی‌شوند."
    )

    return float(np.clip(score, -1, 1)), reasons


# ---------------- MULTI TIMEFRAME ----------------

def timeframe_direction(df):

    row = df.iloc[-1]

    if (
        row["close"] > row["EMA20"]
        and row["EMA20"] > row["EMA50"]
        and row["MACD_HIST"] > 0
    ):
        return "BUY"

    if (
        row["close"] < row["EMA20"]
        and row["EMA20"] < row["EMA50"]
        and row["MACD_HIST"] < 0
    ):
        return "SELL"

    return "NO TRADE"


# ---------------- SIGNAL ENGINE ----------------

def calculate_signal(technical, fundamental, session):

    final_score = (
        technical * WEIGHTS["technical"]
        + fundamental * WEIGHTS["fundamental"]
        + session * WEIGHTS["session"]
    )

    buy_percent = (final_score + 1) * 50
    sell_percent = 100 - buy_percent

    if buy_percent >= 65:
        signal = "BUY"

    elif sell_percent >= 65:
        signal = "SELL"

    else:
        signal = "NO TRADE"

    return (
        signal,
        round(buy_percent, 1),
        round(sell_percent, 1),
        round(abs(final_score) * 100, 1)
    )


# ---------------- MAIN APP ----------------

if refresh:
    st.cache_data.clear()

try:

    with st.spinner("در حال دریافت اطلاعات بازار طلا..."):

        interval = TIMEFRAMES[selected_tf]

        gold_raw = fetch_data(
            "XAU/USD", interval, api_key, 250
        )

        gold = add_indicators(gold_raw)

        # Additional timeframes
        mtf_data = {}

        for label, tf in TIMEFRAMES.items():
            if label == selected_tf:
                mtf_data[label] = gold
            else:
                raw = fetch_data(
                    "XAU/USD", tf, api_key, 220
                )
                mtf_data[label] = add_indicators(raw)

        # Fundamental proxy data
        eurusd = fetch_data(
            "EUR/USD", "15min", api_key, 100
        )

        usdjpy = fetch_data(
            "USD/JPY", "15min", api_key, 100
        )

    # Scores
    tech_score, tech_reasons = technical_analysis(gold)

    sessions = session_status()

    session_score, session_reasons = session_analysis(
        gold, sessions
    )

    fund_score, fund_reasons = fundamental_analysis(
        gold, eurusd, usdjpy
    )

    signal, buy_pct, sell_pct, strength = calculate_signal(
        tech_score,
        fund_score,
        session_score
    )

    latest = gold.iloc[-1]

    price = float(latest["close"])
    atr = float(latest["ATR"])

    if not np.isfinite(atr) or atr <= 0:
        atr = price * 0.002

    # SL / TP
    if signal == "BUY":
        stop_loss = price - (1.5 * atr)
        take_profit = price + (3.0 * atr)

    elif signal == "SELL":
        stop_loss = price + (1.5 * atr)
        take_profit = price - (3.0 * atr)

    else:
        stop_loss = None
        take_profit = None

    risk_amount = account_balance * risk_percent / 100

    # Approximate position size:
    # Assumes 1 unit = 1 ounce and ignores broker leverage/margin rules.
    stop_distance = 1.5 * atr

    position_size = (
        risk_amount / stop_distance
        if stop_distance > 0 else 0
    )

    # Multi-timeframe directions
    mtf_results = {
        label: timeframe_direction(data)
        for label, data in mtf_data.items()
    }

    buy_count = list(mtf_results.values()).count("BUY")
    sell_count = list(mtf_results.values()).count("SELL")

    # ---------------- DASHBOARD ----------------

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "قیمت فعلی طلا",
        f"${price:,.2f}"
    )

    col2.metric(
        "قدرت سیگنال",
        f"{strength}%"
    )

    col3.metric(
        "BUY",
        f"{buy_pct}%"
    )

    col4.metric(
        "SELL",
        f"{sell_pct}%"
    )

    st.divider()

    # Main signal
    if signal == "BUY":
        st.success(f"سیگنال نهایی: BUY | قدرت جهت: {strength}%")

    elif signal == "SELL":
        st.error(f"سیگنال نهایی: SELL | قدرت جهت: {strength}%")

    else:
        st.warning(
            f"سیگنال نهایی: NO TRADE | قدرت جهت: {strength}%"
        )

    # Weighted components
    st.subheader("📊 ترکیب سه بخش تحلیل")

    components = pd.DataFrame({
        "بخش تحلیل": [
            "تکنیکال",
            "فاندامنتال",
            "سشن بازار"
        ],
        "امتیاز جهت‌دار (%)": [
            round((tech_score + 1) * 50, 1),
            round((fund_score + 1) * 50, 1),
            round((session_score + 1) * 50, 1)
        ],
        "وزن": [
            "40%",
            "35%",
            "25%"
        ]
    })

    st.dataframe(
        components,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "در هر بخش، 50٪ یعنی خنثی؛ بالاتر از 50٪ تمایل صعودی "
        "و پایین‌تر از 50٪ تمایل نزولی است."
    )

    st.divider()

    # Sessions
    st.subheader("🌍 تحلیل سشن‌های بازار")

    s1, s2, s3 = st.columns(3)

    s1.metric(
        "سشن فعال",
        sessions["label"]
    )

    s2.metric(
        "زمان افغانستان",
        sessions["kabul"].strftime("%H:%M")
    )

    s3.metric(
        "امتیاز سشن",
        f"{(session_score + 1) * 50:.1f}%"
    )

    st.write(
        "توکیو:",
        sessions["tokyo"].strftime("%H:%M"),
        "| لندن:",
        sessions["london"].strftime("%H:%M"),
        "| نیویورک:",
        sessions["new_york"].strftime("%H:%M")
    )

    st.caption(
        "ساعات سشن‌ها بر اساس قراردادهای رایج بازار FX هستند، "
        "نه ساعات رسمی یا تضمینی بروکر طلا. تغییر ساعت تابستانی "
        "لندن و نیویورک به‌صورت خودکار لحاظ می‌شود."
    )

    for reason in session_reasons:
        st.write("•", reason)

    st.divider()

    # Technical
    st.subheader("📈 تحلیل تکنیکال")

    t1, t2, t3, t4 = st.columns(4)

    t1.metric("RSI", f"{latest['RSI']:.2f}")
    t2.metric("ADX", f"{latest['ADX']:.2f}")
    t3.metric("ATR", f"{latest['ATR']:.2f}")
    t4.metric("MACD", f"{latest['MACD']:.3f}")

    st.write(
        f"EMA20: {latest['EMA20']:.2f} | "
        f"EMA50: {latest['EMA50']:.2f} | "
        f"EMA200: {latest['EMA200']:.2f}"
    )

    for reason in tech_reasons:
        st.write("•", reason)

    st.divider()

    # Fundamental
    st.subheader("🌐 تحلیل فاندامنتال و شاخص‌های جایگزین")

    st.metric(
        "امتیاز فاندامنتال",
        f"{(fund_score + 1) * 50:.1f}%"
    )

    st.write(
        f"EUR/USD: {eurusd['close'].iloc[-1]:.5f}"
    )

    st.write(
        f"USD/JPY: {usdjpy['close'].iloc[-1]:.5f}"
    )

    for reason in fund_reasons:
        st.write("•", reason)

    st.divider()

    # Multi timeframe
    st.subheader("⏱️ تأیید چند تایم‌فریمی")

    mtf_table = pd.DataFrame({
        "تایم‌فریم": list(mtf_results.keys()),
        "سیگنال": list(mtf_results.values())
    })

    st.dataframe(
        mtf_table,
        use_container_width=True,
        hide_index=True
    )

    st.write(
        f"تعداد BUY: {buy_count} از 4 | "
        f"تعداد SELL: {sell_count} از 4"
    )

    st.divider()

    # Trade plan
    st.subheader("🎯 مدیریت معامله")

    if signal != "NO TRADE":

        a, b, c = st.columns(3)

        a.metric("قیمت ورود", f"${price:.2f}")
        b.metric("حد ضرر (SL)", f"${stop_loss:.2f}")
        c.metric("حد سود (TP)", f"${take_profit:.2f}")

        st.write(
            f"سرمایه فرضی: ${account_balance:.2f} | "
            f"ریسک: {risk_percent:.1f}% | "
            f"مقدار ریسک: ${risk_amount:.2f}"
        )

        st.write(
            f"حجم تقریبی: {position_size:.4f} اونس"
        )

        st.caption(
            "حجم بالا با فرض قرارداد 1 واحد = 1 اونس محاسبه شده است. "
            "اهرم، مارجین، اندازه قرارداد و هزینه بروکر لحاظ نشده‌اند؛ "
            "قبل از معامله واقعی با مشخصات بروکر تطبیق بده."
        )

    else:
        st.info(
            "در شرایط فعلی ورود پیشنهاد نمی‌شود. "
            "منتظر هم‌جهتی بهتر بازار بمان."
        )

    st.divider()

    # Chart
    st.subheader("📉 نمودار قیمت طلا")

    chart_data = gold.tail(100).set_index("datetime")

    st.line_chart(
        chart_data[["close", "EMA20", "EMA50", "EMA200"]],
        use_container_width=True
    )

    # Recent data
    with st.expander("مشاهده آخرین کندل‌ها"):
        st.dataframe(
            gold.tail(20).sort_values(
                "datetime",
                ascending=False
            ),
            use_container_width=True
        )

    st.caption(
        f"آخرین زمان داده دریافتی (UTC): "
        f"{latest['datetime'].strftime('%Y-%m-%d %H:%M')}"
    )

except requests.exceptions.Timeout:
    st.error(
        "زمان دریافت اطلاعات از Twelve Data تمام شد. "
        "لطفاً دوباره تلاش کن."
    )

except requests.exceptions.RequestException as e:
    st.error(f"خطای ارتباط با API: {e}")

except Exception as e:
    st.error(f"خطا در تحلیل سیستم: {e}")

st.divider()

st.caption(
    "AFG AI GOLD PRO | Technical + Fundamental Proxy + Sessions | "
    "ابزار کمکی تحلیل بازار، نه تضمین سود."
)
