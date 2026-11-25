import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ============================================================
# AFG GOLD SMART 4H + LIT V1
# Gold-only | Twelve Data | Manual decision support
# ============================================================

st.set_page_config(
    page_title="AFG GOLD SMART 4H + LIT",
    page_icon="🥇",
    layout="wide",
)

KABUL = ZoneInfo("Asia/Kabul")
API_URL = "https://api.twelvedata.com/time_series"
SYMBOL = "XAU/USD"
REFRESH_MS = 5 * 60 * 1000

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
.main-title {font-size: 2rem; font-weight: 800; letter-spacing: .2px;}
.sub-title {color: #a7b0bd; font-size: .95rem;}
.engine-card {border: 1px solid rgba(128,128,128,.3); border-radius: 12px; padding: 14px;}
.signal-buy {color:#16a36a;font-weight:800;font-size:1.25rem;}
.signal-sell {color:#df5b5b;font-weight:800;font-size:1.25rem;}
.signal-none {color:#9aa3ad;font-weight:800;font-size:1.15rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🥇 AFG GOLD SMART 4H + LIT</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">دو موتور مستقل برای طلا: Inside Bar Trend Breakout و LIT (Liquidity Inducement Trading)</div>',
    unsafe_allow_html=True,
)
st_autorefresh(interval=REFRESH_MS, key="gold_smart_lit_refresh")

with st.sidebar:
    st.header("تنظیمات")
    st.caption("فقط طلا · XAU/USD")
    score_floor = st.slider("حداقل امتیاز LIT", 40, 80, 55, 5)
    rr_target = st.selectbox("هدف اصلی بک‌تست", [1.5, 2.0, 2.5, 3.0], index=1, format_func=lambda x: f"{x:.1f}R")
    max_hold = st.slider("حداکثر مدت نگهداری (کندل 4H)", 6, 48, 24, 2)
    st.caption("تغییر این تنظیمات روی سیگنال و بک‌تست اثر می‌گذارد.")

def get_api_key():
    try:
        key = st.secrets.get("TWELVE_DATA_API_KEY", "")
    except Exception:
        key = ""
    return key or os.getenv("TWELVE_DATA_API_KEY", "")

@st.cache_data(ttl=240, show_spinner=False)
def fetch_candles(symbol, interval, outputsize=5000):
    key = get_api_key()
    if not key:
        raise RuntimeError("کلید TWELVE_DATA_API_KEY در Streamlit Secrets ثبت نشده است.")
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "timezone": "UTC",
        "format": "JSON",
        "apikey": key,
    }
    response = requests.get(API_URL, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        message = payload.get("message") or payload.get("code") or str(payload)
        raise RuntimeError(f"Twelve Data: {message}")
    df = pd.DataFrame(payload["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"])
    df = df.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    return df

def add_indicators(df):
    d = df.copy()
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    d["ema200"] = d.close.ewm(span=200, adjust=False).mean()
    tr = pd.concat([
        d.high - d.low,
        (d.high - d.close.shift()).abs(),
        (d.low - d.close.shift()).abs(),
    ], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
    delta = d.close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))
    d["rsi"] = d["rsi"].fillna(50)
    return d

def closed_only(df, interval_hours):
    if df.empty:
        return df
    now = pd.Timestamp.now(tz="UTC")
    close_times = df["datetime"] + pd.Timedelta(hours=interval_hours)
    return df.loc[close_times <= now].copy().reset_index(drop=True)

def candle_strength(row, side):
    rng = max(float(row.high - row.low), 1e-9)
    body = abs(float(row.close - row.open))
    body_ratio = body / rng
    if side == "BUY":
        close_position = (float(row.close) - float(row.low)) / rng
        return body_ratio >= 0.50 and close_position >= 0.68 and row.close > row.open
    close_position = (float(row.high) - float(row.close)) / rng
    return body_ratio >= 0.50 and close_position >= 0.68 and row.close < row.open

def trend_side(row):
    if row.close > row.ema200 and row.ema50 > row.ema200:
        return "BUY"
    if row.close < row.ema200 and row.ema50 < row.ema200:
        return "SELL"
    return None

def levels_from_signal(df, side, entry, structural_price=None):
    row = df.iloc[-1]
    atr = float(row.atr)
    if not np.isfinite(atr) or atr <= 0:
        return None
    if side == "BUY":
        swing = float(df.iloc[-8:]["low"].min())
        sl = min(swing, structural_price) if structural_price is not None else swing
        sl = min(sl, entry - 0.8 * atr)
        risk = entry - sl
        if risk <= 0 or risk > 3.5 * atr:
            sl = entry - 1.5 * atr
            risk = entry - sl
        return {"entry": entry, "sl": sl, "tp1": entry + 1.5*risk, "tp2": entry + 2*risk, "risk": risk}
    swing = float(df.iloc[-8:]["high"].max())
    sl = max(swing, structural_price) if structural_price is not None else swing
    sl = max(sl, entry + 0.8 * atr)
    risk = sl - entry
    if risk <= 0 or risk > 3.5 * atr:
        sl = entry + 1.5 * atr
        risk = sl - entry
    return {"entry": entry, "sl": sl, "tp1": entry - 1.5*risk, "tp2": entry - 2*risk, "risk": risk}

def smart_inside_bar(df):
    """Moderate 4H inside-bar breakout, aligned with broad EMA trend."""
    if len(df) < 220:
        return {"side": None, "score": 0, "reason": "داده کافی نیست"}
    # signal candle is last closed candle; mother candle is two bars back
    mother = df.iloc[-3]
    inside = df.iloc[-2]
    trigger = df.iloc[-1]
    mother_range = float(mother.high - mother.low)
    is_inside = inside.high < mother.high and inside.low > mother.low
    side = trend_side(trigger)
    if not is_inside or side is None:
        return {"side": None, "score": 0, "reason": "Inside Bar یا جهت روند کامل نیست"}
    atr = float(trigger.atr)
    if not np.isfinite(atr) or atr <= 0:
        return {"side": None, "score": 0, "reason": "ATR نامعتبر"}
    buffer = max(0.03 * atr, 0.01)
    broke = trigger.close > mother.high + buffer if side == "BUY" else trigger.close < mother.low - buffer
    strong = candle_strength(trigger, side)
    # Moderate scoring: breakout + trend are required; strong close is additional quality.
    score = 45 + 35 + (20 if strong else 0) if broke else 0
    if not broke:
        return {"side": None, "score": 0, "reason": "منتظر بسته‌شدن کندل بیرون محدوده مادر"}
    entry = float(trigger.close)
    lv = levels_from_signal(df, side, entry, float(mother.low if side == "BUY" else mother.high))
    if not lv:
        return {"side": None, "score": 0, "reason": "سطوح ورود معتبر نیست"}
    return {"side": side, "score": min(score, 100), "reason": "شکست Inside Bar در جهت روند",
            **lv, "mother_high": float(mother.high), "mother_low": float(mother.low)}

def lit_signal(df, min_score=55):
    """
    LIT-inspired proxy:
    recent liquidity raid, followed by a separate displacement / structure shift.
    Sweep is checked on one of the previous four completed candles, while
    confirmation is checked on the latest completed candle.
    """
    if len(df) < 220:
        return {"side": None, "score": 0, "reason": "داده کافی نیست"}
    row = df.iloc[-1]
    atr = float(row.atr)
    if not np.isfinite(atr) or atr <= 0:
        return {"side": None, "score": 0, "reason": "ATR نامعتبر"}

    buy_sweep = None
    sell_sweep = None
    # Find the most recent liquidity raid among the four candles before confirmation.
    for idx in range(len(df)-5, len(df)-1):
        candle = df.iloc[idx]
        prior = df.iloc[max(0, idx-10):idx]
        if len(prior) < 5:
            continue
        prior_low = float(prior.low.min())
        prior_high = float(prior.high.max())
        if float(candle.low) < prior_low and float(candle.close) > prior_low:
            buy_sweep = {"idx": idx, "level": prior_low, "extreme": float(candle.low)}
        if float(candle.high) > prior_high and float(candle.close) < prior_high:
            sell_sweep = {"idx": idx, "level": prior_high, "extreme": float(candle.high)}

    # Confirm that price displaced away from the sweep and shifted short-term structure.
    buy_mss = sell_mss = False
    buy_disp = row.close > row.open and abs(float(row.close-row.open)) >= 0.50*atr
    sell_disp = row.close < row.open and abs(float(row.close-row.open)) >= 0.50*atr
    buy_fvg = float(row.low) > float(df.iloc[-3].high)
    sell_fvg = float(row.high) < float(df.iloc[-3].low)

    if buy_sweep:
        structure = df.iloc[buy_sweep["idx"]:-1]
        if len(structure):
            buy_mss = float(row.close) > float(structure.high.max())
    if sell_sweep:
        structure = df.iloc[sell_sweep["idx"]:-1]
        if len(structure):
            sell_mss = float(row.close) < float(structure.low.min())

    buy_score = (40 if buy_sweep else 0) + (25 if buy_mss else 0) + (25 if buy_disp else 0) + (10 if buy_fvg else 0)
    sell_score = (40 if sell_sweep else 0) + (25 if sell_mss else 0) + (25 if sell_disp else 0) + (10 if sell_fvg else 0)

    side = None
    score = max(buy_score, sell_score)
    if buy_sweep and (buy_mss or buy_disp) and buy_score >= min_score and buy_score > sell_score:
        side = "BUY"
    elif sell_sweep and (sell_mss or sell_disp) and sell_score >= min_score and sell_score > buy_score:
        side = "SELL"

    if not side:
        return {
            "side": None, "score": int(score),
            "buy_score": buy_score, "sell_score": sell_score,
            "reason": "منتظر Sweep اخیر و تأیید Displacement یا MSS",
        }

    structural = buy_sweep["extreme"] if side == "BUY" else sell_sweep["extreme"]
    lv = levels_from_signal(df, side, float(row.close), structural)
    if not lv:
        return {"side": None, "score": int(score), "reason": "سطوح ورود معتبر نیست"}
    return {
        "side": side, "score": int(score),
        "buy_score": buy_score, "sell_score": sell_score,
        "reason": "Liquidity sweep followed by confirmation",
        **lv,
    }

def backtest(df, engine, rr=2.0, max_bars=24, min_lit_score=55):
    """One position at a time; signal at closed bar, entry at next bar open."""
    if len(df) < 230:
        return pd.DataFrame(), empty_stats()
    rows = []
    i = 205
    while i < len(df)-1:
        hist = df.iloc[:i+1].copy()
        sig = smart_inside_bar(hist) if engine == "SMART 4H" else lit_signal(hist, min_lit_score)
        side = sig.get("side")
        if not side:
            i += 1
            continue
        entry_i = i+1
        entry = float(df.iloc[entry_i].open)
        # Preserve structural stop, but recalculate targets from actual next-open fill.
        planned_sl = float(sig["sl"])
        if side == "BUY":
            sl = planned_sl
            risk = entry - sl
            if risk <= 0 or risk > 4*float(df.iloc[i].atr):
                i += 1
                continue
            target = entry + rr*risk
        else:
            sl = planned_sl
            risk = sl - entry
            if risk <= 0 or risk > 4*float(df.iloc[i].atr):
                i += 1
                continue
            target = entry - rr*risk
        exit_i = None
        outcome = "OPEN"
        exit_price = float(df.iloc[-1].close)
        end_i = min(len(df)-1, entry_i+max_bars-1)
        for j in range(entry_i, end_i+1):
            bar = df.iloc[j]
            if side == "BUY":
                hit_sl = float(bar.low) <= sl
                hit_tp = float(bar.high) >= target
            else:
                hit_sl = float(bar.high) >= sl
                hit_tp = float(bar.low) <= target
            if hit_sl and hit_tp:
                outcome, exit_price, exit_i = "LOSS (same-bar conservative)", sl, j
                break
            if hit_sl:
                outcome, exit_price, exit_i = "LOSS", sl, j
                break
            if hit_tp:
                outcome, exit_price, exit_i = "WIN", target, j
                break
        if exit_i is None and end_i < len(df)-1:
            exit_i = end_i
            exit_price = float(df.iloc[end_i].close)
            outcome = "TIME EXIT"
        if outcome.startswith("WIN"):
            r_value = rr
        elif outcome.startswith("LOSS"):
            r_value = -1.0
        elif side == "BUY":
            r_value = (exit_price-entry)/risk
        else:
            r_value = (entry-exit_price)/risk
        rows.append({
            "زمان سیگنال UTC": df.iloc[i].datetime,
            "جهت": side,
            "ورود": entry,
            "حد ضرر": sl,
            "هدف": target,
            "خروج": exit_price,
            "نتیجه": outcome,
            "R": round(float(r_value), 2),
            "امتیاز": sig.get("score", 0),
        })
        i = (exit_i if exit_i is not None else len(df)-1) + 1
    out = pd.DataFrame(rows)
    return out, calculate_stats(out)

def empty_stats():
    return {"total":0,"closed":0,"open":0,"wins":0,"losses":0,"win_rate":0.0,
            "pf":0.0,"net_r":0.0,"max_dd_r":0.0}

def calculate_stats(trades):
    if trades.empty:
        return empty_stats()
    closed = trades[trades["نتیجه"] != "OPEN"].copy()
    wins = int(closed["نتیجه"].str.startswith("WIN").sum()) if len(closed) else 0
    losses = int(closed["نتیجه"].str.startswith("LOSS").sum()) if len(closed) else 0
    gross_profit = float(closed.loc[closed.R > 0, "R"].sum()) if len(closed) else 0.0
    gross_loss = abs(float(closed.loc[closed.R < 0, "R"].sum())) if len(closed) else 0.0
    pf = gross_profit/gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    equity = closed["R"].cumsum() if len(closed) else pd.Series(dtype=float)
    if len(equity):
        peak = equity.cummax()
        dd = equity - peak
        max_dd = abs(float(dd.min()))
    else:
        max_dd = 0.0
    nclosed = len(closed)
    return {
        "total":len(trades),"closed":nclosed,
        "open":int((trades["نتیجه"]=="OPEN").sum()),
        "wins":wins,"losses":losses,
        "win_rate":round(wins/nclosed*100,2) if nclosed else 0.0,
        "pf":round(pf,2),"net_r":round(float(closed.R.sum()),2) if nclosed else 0.0,
        "max_dd_r":round(max_dd,2),
    }

def show_signal(title, sig):
    st.markdown(f"**{title}**")
    side = sig.get("side")
    if side == "BUY":
        st.markdown('<div class="signal-buy">🟢 BUY</div>', unsafe_allow_html=True)
    elif side == "SELL":
        st.markdown('<div class="signal-sell">🔴 SELL</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="signal-none">⏳ NO SIGNAL</div>', unsafe_allow_html=True)
    st.caption(f"امتیاز: {sig.get('score',0)}/100 · {sig.get('reason','')}")
    if side:
        c1,c2,c3=st.columns(3)
        c1.metric("Entry", f"{sig['entry']:,.2f}")
        c2.metric("Stop Loss", f"{sig['sl']:,.2f}")
        c3.metric("TP1 (1.5R)", f"{sig['tp1']:,.2f}")
        st.metric("TP2 (2R)", f"{sig['tp2']:,.2f}")

# Load market data
try:
    with st.spinner("در حال دریافت کندل‌های بسته‌شده طلا..."):
        raw4h = fetch_candles(SYMBOL, "4h", 5000)
        raw1h = fetch_candles(SYMBOL, "1h", 5000)
    df4h = add_indicators(closed_only(raw4h, 4))
    df1h = add_indicators(closed_only(raw1h, 1))
except Exception as exc:
    st.error(str(exc))
    st.info("در Streamlit → Settings → Secrets، نام TWELVE_DATA_API_KEY و مقدار API key را ثبت کن. کلید را در چت ارسال نکن.")
    st.stop()

if len(df4h) < 220:
    st.error(f"داده 4H کافی نیست: {len(df4h)} کندل بسته دریافت شد؛ حداقل حدود 220 کندل لازم است.")
    st.stop()

last = df4h.iloc[-1]
local_time = last.datetime.tz_convert(KABUL)
st.caption(f"آخرین کندل بسته‌شده 4H: {local_time.strftime('%Y-%m-%d %H:%M')} کابل · قیمت: {last.close:,.2f}")
st.metric("XAU/USD", f"{last.close:,.2f}", f"RSI 4H: {last.rsi:.1f}")

smart = smart_inside_bar(df4h)
lit = lit_signal(df4h, score_floor)

col_a, col_b = st.columns(2)
with col_a:
    with st.container(border=True):
        show_signal("ENGINE 1 · SMART INSIDE BAR 4H", smart)
        st.caption("روند EMA50/EMA200 + شکست Inside Bar؛ فیلتر متوسط و نه بیش از حد سخت.")
with col_b:
    with st.container(border=True):
        show_signal("ENGINE 2 · LIT", lit)
        st.caption("Sweep نقدینگی + Displacement یا MSS؛ FVG امتیاز تکمیلی دارد.")

st.divider()
st.subheader("📊 بک‌تست مستقل و مقایسه‌ای")
st.write("بک‌تست روی کندل‌های بسته‌شده 4H اجرا می‌شود؛ سیگنال پس از بسته‌شدن کندل و ورود در بازشدن کندل بعدی فرض می‌شود.")
c1,c2,c3=st.columns(3)
days = c1.selectbox("دوره", [30,60,90,180], index=2, format_func=lambda x:f"{x} روز")
bt_choice = c2.selectbox("موتور", ["هر دو موتور","فقط SMART 4H","فقط LIT"])
bt_rr = c3.selectbox("هدف خروج", [1.5,2.0,2.5,3.0], index=1, format_func=lambda x:f"{x}R")
if st.button("▶ اجرای بک‌تست", use_container_width=True):
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    sample = df4h[df4h.datetime >= cutoff].copy().reset_index(drop=True)
    # Warmup indicators are preserved by slicing after indicator calculation.
    if len(sample) < 30:
        st.error("تعداد کندل‌های موجود برای این دوره کافی نیست.")
    else:
        selected = ["SMART 4H","LIT"] if bt_choice == "هر دو موتور" else [bt_choice]
        results = {}
        with st.spinner("در حال اجرای بک‌تست..."):
            for engine in selected:
                trades, stats = backtest(sample, engine, bt_rr, max_hold, score_floor)
                results[engine] = (trades, stats)
        st.session_state["gold_lit_bt"] = results
        st.session_state["gold_lit_bt_days"] = days
        st.session_state["gold_lit_bt_rr"] = bt_rr

if "gold_lit_bt" in st.session_state:
    st.markdown(f"**نتایج: {st.session_state['gold_lit_bt_days']} روز · هدف {st.session_state['gold_lit_bt_rr']}R**")
    summary = []
    for engine, (trades, stats) in st.session_state["gold_lit_bt"].items():
        summary.append({
            "سیستم":engine,"کل معاملات":stats["total"],"بسته‌شده":stats["closed"],
            "باز":stats["open"],"برد":stats["wins"],"باخت":stats["losses"],
            "درصد برد":stats["win_rate"],"Profit Factor":stats["pf"],
            "خالص R":stats["net_r"],"Max Drawdown (R)":stats["max_dd_r"],
        })
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
    for engine, (trades, stats) in st.session_state["gold_lit_bt"].items():
        with st.expander(f"{engine} · جزئیات معاملات"):
            if trades.empty:
                st.info("در این بازه معامله‌ای مطابق قوانین سیستم ثبت نشد.")
            else:
                st.dataframe(trades, use_container_width=True, hide_index=True)
                st.download_button(
                    f"دانلود CSV {engine}",
                    trades.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"gold_{engine.lower().replace(' ','_')}_backtest.csv",
                    mime="text/csv",
                    key=f"download_{engine}",
                )

with st.expander("روش کار و محدودیت‌های مهم"):
    st.markdown("""
    - **SMART 4H:** جهت روند با EMA50 و EMA200 تعیین می‌شود. یک Inside Bar باید شکل بگیرد و کندل بعدی بیرون محدوده کندل مادر بسته شود.
    - **LIT:** این نسخه یک مدل الگوریتمی شفاف از ایده‌های Liquidity Inducement است: Sweep سقف/کف اخیر، سپس Displacement یا شکست ساختار (MSS)، و FVG به‌عنوان امتیاز اضافی. این نسخه ادعای بازسازی کامل یک دوره یا روش اختصاصی LIT را ندارد.
    - هر دو موتور مستقل هستند و نتایج جداگانه دارند.
    - ورود بک‌تست در Open کندل بعد از سیگنال است؛ حد ضرر ساختاری و هدف بر اساس R است.
    - اگر حد ضرر و هدف در یک کندل لمس شوند، با فرض محافظه‌کارانه حد ضرر اول حساب می‌شود.
    - معاملات باز از درصد برد و خالص R تحقق‌یافته جدا می‌شوند.
    - اسپرد، کمیسیون، اسلیپیج و تفاوت قیمت بروکر لحاظ نشده‌اند؛ نتیجه ناخالص و نظری است.
    - نرخ برد بالا به‌تنهایی کافی نیست؛ Profit Factor، خالص R، Drawdown و تعداد معاملات را هم مقایسه کن.
    - این برنامه سفارش واقعی ثبت نمی‌کند؛ تصمیم و اجرای معامله دستی است.
    """)
st.caption("AFG GOLD SMART 4H + LIT V1 · XAU/USD · Manual decision support only")
