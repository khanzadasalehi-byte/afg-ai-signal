import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

# ==========================================================
# AFG GOLD CRT 100 - Candle Range Theory only
# XAU/USD | 15m execution | previous completed 1H candle range
# Decision-support only; no broker execution.
# ==========================================================

st.set_page_config(page_title="AFG GOLD CRT 100", page_icon="🥇", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="crt_refresh")

st.title("🥇 AFG GOLD CRT 100")
st.caption("فقط منطق CRT | طلا XAU/USD | بررسی خودکار هر ۵ دقیقه")

st.info(
    "این ربات از CRT به‌تنهایی استفاده می‌کند: محدوده کندل کامل‌شده ۱ ساعته، "
    "شکار نقدینگی بیرون محدوده و بسته‌شدن دوباره داخل محدوده در کندل ۱۵ دقیقه. "
    "CRT به معنی برد ۱۰۰٪ نیست."
)

with st.sidebar:
    st.subheader("تنظیمات")
    min_rr = st.selectbox("حداقل نسبت سود به ضرر", [1.0, 1.2, 1.5], index=0)
    atr_buffer = st.slider("ضریب فاصله حد ضرر (ATR)", 0.05, 0.50, 0.15, 0.05)
    show_debug = st.checkbox("نمایش جزئیات تحلیل", value=True)
    st.caption("کلید API باید در Streamlit Secrets با نام TWELVE_DATA_API_KEY ثبت شده باشد.")

@st.cache_data(ttl=240, show_spinner=False)
def fetch_candles(symbol, interval, outputsize, api_key):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "timezone": "UTC",
        "apikey": api_key,
        "format": "JSON",
    }
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    data = response.json()
    if "values" not in data:
        raise RuntimeError(data.get("message", data.get("code", "پاسخ نامعتبر از Twelve Data")))
    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"])
    return df.sort_values("datetime").reset_index(drop=True)

def add_atr(df, period=14):
    x = df.copy()
    prev_close = x["close"].shift(1)
    tr = pd.concat([
        x["high"] - x["low"],
        (x["high"] - prev_close).abs(),
        (x["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    x["atr"] = tr.rolling(period).mean()
    return x

def attach_previous_hour_range(m15, h1):
    """Attach the latest completed 1H candle range to each 15m candle."""
    left = m15.sort_values("datetime").copy()
    right = h1[["datetime", "high", "low"]].copy()
    right["range_ready_at"] = right["datetime"] + pd.Timedelta(hours=1)
    right = right.rename(columns={"high": "crt_high", "low": "crt_low"})
    right = right[["range_ready_at", "crt_high", "crt_low"]].sort_values("range_ready_at")
    return pd.merge_asof(
        left, right, left_on="datetime", right_on="range_ready_at",
        direction="backward", allow_exact_matches=True
    )

def find_signal(m15, h1, atr_buffer=0.15, min_rr=1.0):
    x = add_atr(m15, 14)
    x = attach_previous_hour_range(x, h1)
    x = x.dropna(subset=["atr", "crt_high", "crt_low"])
    if len(x) < 2:
        return None, x, "داده کافی برای تحلیل وجود ندارد."

    # Use latest completed 15m candle only. The caller removes a still-forming candle.
    c = x.iloc[-1]
    prev = x.iloc[-2]
    rng = float(c["crt_high"] - c["crt_low"])
    atr = float(c["atr"])
    if not np.isfinite(rng) or rng <= 0 or not np.isfinite(atr) or atr <= 0:
        return None, x, "محدوده یا ATR معتبر نیست."

    # CRT: sweep beyond one side of the previous completed 1H range,
    # then close back inside that same range.
    bull = (
        c["low"] < c["crt_low"]
        and c["close"] > c["crt_low"]
        and c["close"] < c["crt_high"]
        and c["close"] > c["open"]
    )
    bear = (
        c["high"] > c["crt_high"]
        and c["close"] < c["crt_high"]
        and c["close"] > c["crt_low"]
        and c["close"] < c["open"]
    )

    if not bull and not bear:
        return None, x, "در آخرین کندل کامل‌شده، Sweep و برگشت معتبر CRT دیده نشد."

    entry = float(c["close"])
    if bull:
        side = "BUY"
        sl = float(c["low"] - atr * atr_buffer)
        tp = float(c["crt_high"])
        risk = entry - sl
        reward = tp - entry
    else:
        side = "SELL"
        sl = float(c["high"] + atr * atr_buffer)
        tp = float(c["crt_low"])
        risk = sl - entry
        reward = entry - tp

    rr = reward / risk if risk > 0 else 0
    if risk <= 0 or reward <= 0 or rr < min_rr:
        return None, x, f"الگوی CRT دیده شد، اما نسبت سود به ضرر ({rr:.2f}R) کمتر از حداقل انتخاب‌شده است."

    signal = {
        "side": side, "entry": entry, "sl": sl, "tp": tp, "rr": rr,
        "time": c["datetime"], "range_high": float(c["crt_high"]),
        "range_low": float(c["crt_low"]), "sweep_extreme": float(c["low"] if bull else c["high"]),
        "atr": atr
    }
    return signal, x, "سیگنال CRT تأیید شد."

def backtest(m15, h1, atr_buffer, min_rr, max_hold=32):
    x = add_atr(m15, 14)
    x = attach_previous_hour_range(x, h1).reset_index(drop=True)
    trades = []
    start = max(20, 1)
    for i in range(start, len(x) - 1):
        c = x.iloc[i]
        if pd.isna(c["atr"]) or pd.isna(c["crt_high"]) or pd.isna(c["crt_low"]):
            continue
        atr = float(c["atr"])
        if atr <= 0:
            continue
        bull = c["low"] < c["crt_low"] and c["close"] > c["crt_low"] and c["close"] < c["crt_high"] and c["close"] > c["open"]
        bear = c["high"] > c["crt_high"] and c["close"] < c["crt_high"] and c["close"] > c["crt_low"] and c["close"] < c["open"]
        if not bull and not bear:
            continue
        # Conservative next-candle-open entry; avoids using the signal candle close as a fill.
        entry_i = i + 1
        entry = float(x.iloc[entry_i]["open"])
        if bull:
            side = "BUY"
            sl = float(c["low"] - atr * atr_buffer)
            tp = float(c["crt_high"])
            risk = entry - sl
            reward = tp - entry
        else:
            side = "SELL"
            sl = float(c["high"] + atr * atr_buffer)
            tp = float(c["crt_low"])
            risk = sl - entry
            reward = entry - tp
        rr = reward / risk if risk > 0 else 0
        if risk <= 0 or reward <= 0 or rr < min_rr:
            continue

        outcome = "OPEN"
        result_r = 0.0
        exit_time = None
        end_i = min(len(x) - 1, entry_i + max_hold - 1)
        for j in range(entry_i, end_i + 1):
            bar = x.iloc[j]
            if side == "BUY":
                hit_sl = bar["low"] <= sl
                hit_tp = bar["high"] >= tp
            else:
                hit_sl = bar["high"] >= sl
                hit_tp = bar["low"] <= tp
            # If SL and TP occur in the same candle, count SL first (conservative).
            if hit_sl:
                outcome, result_r, exit_time = "LOSS", -1.0, bar["datetime"]
                break
            if hit_tp:
                outcome, result_r, exit_time = "WIN", rr, bar["datetime"]
                break
        if outcome == "OPEN":
            last = x.iloc[end_i]
            mark = float(last["close"])
            result_r = ((mark - entry) / risk) if side == "BUY" else ((entry - mark) / risk)
            outcome, exit_time = "TIME EXIT", result_r, last["datetime"]
        trades.append({
            "زمان سیگنال": c["datetime"], "جهت": side, "ورود": entry,
            "حد ضرر": sl, "هدف": tp, "نتیجه": outcome,
            "نتیجه R": result_r, "زمان خروج": exit_time
        })
    return pd.DataFrame(trades)

try:
    api_key = st.secrets["TWELVE_DATA_API_KEY"]
except Exception:
    api_key = None

if not api_key:
    st.error("کلید API پیدا نشد. در Streamlit → Settings → Secrets این نام را ثبت کن: TWELVE_DATA_API_KEY")
    st.code('TWELVE_DATA_API_KEY = "کلید-شخصی-خودت"')
    st.stop()

try:
    with st.spinner("دریافت داده‌های طلا..."):
        raw15 = fetch_candles("XAU/USD", "15min", 5000, api_key)
        raw1h = fetch_candles("XAU/USD", "1h", 5000, api_key)
    now = pd.Timestamp.now(tz="UTC")
    # Remove candles that have not fully closed yet.
    m15 = raw15[raw15["datetime"] + pd.Timedelta(minutes=15) <= now].copy()
    h1 = raw1h[raw1h["datetime"] + pd.Timedelta(hours=1) <= now].copy()
    if len(m15) < 100 or len(h1) < 30:
        st.error("داده کافی از ارائه‌دهنده دریافت نشد.")
        st.stop()

    latest_price = float(m15.iloc[-1]["close"])
    st.metric("آخرین قیمت بسته‌شدن ۱۵ دقیقه", f"{latest_price:,.2f}")
    signal, enriched, message = find_signal(m15, h1, atr_buffer, min_rr)

    if signal:
        st.success(f"سیگنال CRT: {signal['side']}")
        a, b, c, d = st.columns(4)
        a.metric("ورود", f"{signal['entry']:,.2f}")
        b.metric("حد ضرر", f"{signal['sl']:,.2f}")
        c.metric("هدف CRT", f"{signal['tp']:,.2f}")
        d.metric("نسبت سود به ضرر", f"{signal['rr']:.2f}R")
        st.write("زمان کندل تأیید (UTC):", signal["time"].strftime("%Y-%m-%d %H:%M"))
        st.caption("سیگنال پس از بسته‌شدن کندل ۱۵ دقیقه صادر شده است؛ پیش از معامله قیمت و اسپرد بروکر را بررسی کن.")
    else:
        st.warning("فعلاً سیگنال معتبر CRT وجود ندارد.")
        st.write(message)

    if show_debug:
        with st.expander("جزئیات آخرین تحلیل"):
            last = enriched.iloc[-1]
            st.write({
                "کندل ۱۵ دقیقه UTC": str(last["datetime"]),
                "High محدوده ۱ ساعته": round(float(last["crt_high"]), 2) if pd.notna(last["crt_high"]) else None,
                "Low محدوده ۱ ساعته": round(float(last["crt_low"]), 2) if pd.notna(last["crt_low"]) else None,
                "ATR(14)": round(float(last["atr"]), 3) if pd.notna(last["atr"]) else None,
                "قانون": "Sweep بیرون محدوده + بسته‌شدن داخل محدوده + کندل برگشتی هم‌جهت"
            })

    st.divider()
    st.subheader("بک‌تست تاریخی CRT")
    st.caption("بک‌تست روی کندل‌های ۱۵ دقیقه با محدوده آخرین کندل کامل‌شده ۱ ساعته؛ ورود در بازشدن کندل بعدی. هزینه اسپرد، کمیسیون و لغزش قیمت در نتایج لحاظ نشده است.")
    days = st.selectbox("دوره بک‌تست", [30, 60, 90, 180], index=0)
    bt = backtest(m15, h1, atr_buffer, min_rr)
    if not bt.empty:
        cutoff = now - pd.Timedelta(days=days)
        bt = bt[bt["زمان سیگنال"] >= cutoff].copy()
    if bt.empty:
        st.warning("در این دوره معامله‌ای با قوانین انتخاب‌شده پیدا نشد. دوره را بیشتر کن یا داده بیشتری دریافت کن.")
    else:
        closed = bt[bt["نتیجه"].isin(["WIN", "LOSS", "TIME EXIT"])]
        wins = int((closed["نتیجه"] == "WIN").sum())
        losses = int((closed["نتیجه"] == "LOSS").sum())
        win_rate = wins / len(closed) * 100 if len(closed) else 0
        gross_win = closed.loc[closed["نتیجه R"] > 0, "نتیجه R"].sum()
        gross_loss = abs(closed.loc[closed["نتیجه R"] < 0, "نتیجه R"].sum())
        pf = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0)
        net_r = closed["نتیجه R"].sum()
        equity = closed["نتیجه R"].cumsum()
        drawdown = (equity - equity.cummax()).min() if len(equity) else 0
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("تعداد معاملات بسته", len(closed))
        q2.metric("درصد برد", f"{win_rate:.1f}%")
        q3.metric("Profit Factor", f"{pf:.2f}" if np.isfinite(pf) else "∞")
        q4.metric("خالص نتیجه", f"{net_r:.2f}R")
        st.write(f"برد: {wins} | باخت: {losses} | افت سرمایه: {drawdown:.2f}R")
        st.dataframe(bt, use_container_width=True, hide_index=True)
        st.download_button("دانلود گزارش بک‌تست CSV", bt.to_csv(index=False).encode("utf-8-sig"),
                           file_name="AFG_GOLD_CRT_BACKTEST.csv", mime="text/csv")
    st.caption(f"آخرین بروزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | داده: Twelve Data")
except Exception as e:
    st.error(f"خطا در دریافت یا تحلیل داده: {e}")
    st.caption("اگر خطای API دیدی، وضعیت کلید Twelve Data و محدودیت درخواست‌ها را بررسی کن.")
