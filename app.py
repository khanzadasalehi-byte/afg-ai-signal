import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# AFG AI GOLD PRO ELITE V12 - SMC + LIQUIDITY 100%
st.set_page_config(page_title="AFG AI GOLD PRO ELITE V12", page_icon="🇦🇫", layout="wide")
st.title("🇦🇫 AFG AI GOLD PRO ELITE V12")
st.caption("SMC + Liquidity 100% · Gold XAU/USD · Live signals and a separate historical backtest")

API_URL = "https://api.twelvedata.com/time_series"
API_KEY = st.secrets.get("TWELVE_DATA_API_KEY", "")
TZ = ZoneInfo("Asia/Kabul")
TIMEOUT = 25
INTERVALS = {"5M": ("5min", pd.Timedelta(minutes=5)),
             "15M": ("15min", pd.Timedelta(minutes=15)),
             "1H": ("1h", pd.Timedelta(hours=1)),
             "4H": ("4h", pd.Timedelta(hours=4))}

if not API_KEY:
    st.error("TWELVE_DATA_API_KEY را در Streamlit Secrets ثبت کن.")
    st.stop()

@st.cache_data(ttl=60, show_spinner=False)
def fetch_candles(symbol, interval, outputsize=1000):
    params = {"symbol": symbol, "interval": interval, "outputsize": outputsize,
              "apikey": API_KEY, "timezone": "UTC", "format": "JSON"}
    response = requests.get(API_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise ValueError(payload.get("message", str(payload)))
    df = pd.DataFrame(payload["values"])
    required = ["datetime", "open", "high", "low", "close"]
    if any(c not in df for c in required):
        raise ValueError("ساختار داده دریافتی معتبر نیست.")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = (df.dropna(subset=required).sort_values("datetime")
          .drop_duplicates("datetime").reset_index(drop=True))
    return df

def add_indicators(df):
    d = df.copy()
    c = d.close
    d["ema20"] = c.ewm(span=20, adjust=False).mean()
    d["ema50"] = c.ewm(span=50, adjust=False).mean()
    d["ema200"] = c.ewm(span=200, adjust=False).mean()
    delta = c.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, np.nan)
    d["rsi"] = (100 - 100/(1+rs)).fillna(50)
    prev = c.shift(1)
    tr = pd.concat([d.high-d.low, (d.high-prev).abs(), (d.low-prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    up, down = d.high.diff(), -d.low.diff()
    plus = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=d.index)
    minus = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=d.index)
    pdi = 100*plus.ewm(alpha=1/14, adjust=False).mean()/d.atr.replace(0, np.nan)
    mdi = 100*minus.ewm(alpha=1/14, adjust=False).mean()/d.atr.replace(0, np.nan)
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    d["plus_di"], d["minus_di"] = pdi.fillna(0), mdi.fillna(0)
    d["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean().fillna(0)
    return d

def trend_of(row):
    if row.close > row.ema50 > row.ema200:
        return "BULLISH"
    if row.close < row.ema50 < row.ema200:
        return "BEARISH"
    return "MIXED"

def analyze_signal(frames, score_floor=30):
    """Final score is exclusively SMC + Liquidity (100%)."""
    d = frames["15M"]
    if len(d) < 220 or any(len(frames[k]) < 220 for k in ("5M","1H","4H")):
        return {"signal":"NO TRADE", "reason":"داده کافی نیست"}
    r = d.iloc[-1]
    prev = d.iloc[-2]
    atr, current = float(r.atr), float(r.close)
    if not np.isfinite(atr) or atr <= 0:
        return {"signal":"NO TRADE", "reason":"ATR نامعتبر"}
    prior = d.iloc[-25:-1]
    liq = d.iloc[-21:-1]
    prior_high, prior_low = float(liq.high.max()), float(liq.low.min())
    sweep_buy = float(r.low) < prior_low and current > prior_low
    sweep_sell = float(r.high) > prior_high and current < prior_high
    fvg_buy = float(r.low) > float(d.iloc[-3].high)
    fvg_sell = float(r.high) < float(d.iloc[-3].low)
    swing_high, swing_low = float(prior.tail(12).high.max()), float(prior.tail(12).low.min())
    bos_buy, bos_sell = current > swing_high, current < swing_low
    ob_buy = prev.close < prev.open and current > prev.high and (current-prev.low) >= .35*atr
    ob_sell = prev.close > prev.open and current < prev.low and (prev.high-current) >= .35*atr
    buy = (40 if sweep_buy else 0)+(25 if bos_buy else 0)+(20 if fvg_buy else 0)+(15 if ob_buy else 0)
    sell = (40 if sweep_sell else 0)+(25 if bos_sell else 0)+(20 if fvg_sell else 0)+(15 if ob_sell else 0)
    recent = d.tail(24)
    ema_gap = abs(float(r.ema20)-float(r.ema50))/atr
    range_atr = (float(recent.high.max())-float(recent.low.min()))/atr
    choppy = float(r.adx) < 10 and ema_gap < .08 and range_atr < 2
    direction = None
    if not choppy and buy >= score_floor and buy > sell+1:
        direction = "BUY"
    elif not choppy and sell >= score_floor and sell > buy+1:
        direction = "SELL"
    if not direction:
        return {"signal":"NO TRADE", "buy_score":buy, "sell_score":sell,
                "score":max(buy,sell), "reason":"شرایط SMC کامل نیست یا بازار فشرده است"}
    ema = float(r.ema20)
    near = abs(current-ema) <= .15*atr
    if direction == "BUY":
        entry = current if near else ema+.05*atr
        sl = min(float(d.tail(12).low.min())-.12*atr, entry-.55*atr)
        dist = (current-entry)/atr
        valid = (near or 0 <= dist <= 1.2) and .35*atr <= entry-sl <= 2.5*atr
        risk = entry-sl
        levels = (entry+risk, entry+2*risk, entry+3*risk)
    else:
        entry = current if near else ema-.05*atr
        sl = max(float(d.tail(12).high.max())+.12*atr, entry+.55*atr)
        dist = (entry-current)/atr
        valid = (near or 0 <= dist <= 1.2) and .35*atr <= sl-entry <= 2.5*atr
        risk = sl-entry
        levels = (entry-risk, entry-2*risk, entry-3*risk)
    if not valid:
        return {"signal":"NO TRADE", "buy_score":buy, "sell_score":sell,
                "score":max(buy,sell), "reason":"فاصله ورود یا حد ضرر نامعتبر"}
    return {"signal":direction, "score":max(buy,sell), "buy_score":buy, "sell_score":sell,
            "order_type":direction+(" MARKET" if near else " LIMIT"),
            "entry":entry, "sl":sl, "tp1":levels[0], "tp2":levels[1], "tp3":levels[2],
            "atr":atr, "reason":"SMC + Liquidity"}

def get_live_frames():
    frames = {}
    for label, (interval, delta) in INTERVALS.items():
        raw = fetch_candles("XAU/USD", interval, 1000)
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=3)
        raw = raw[raw.datetime+delta <= cutoff].reset_index(drop=True)
        if len(raw) < 220:
            raise ValueError(f"{label}: فقط {len(raw)} کندل بسته دریافت شد؛ حداقل 220 لازم است.")
        frames[label] = add_indicators(raw)
    return frames

def historical_frames(days):
    # Fetch up to 5000 candles per timeframe to provide indicator warm-up.
    frames = {}
    for label, (interval, delta) in INTERVALS.items():
        raw = fetch_candles("XAU/USD", interval, 5000)
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=3)
        raw = raw[raw.datetime+delta <= cutoff].reset_index(drop=True)
        if len(raw) < 230:
            raise ValueError(f"داده تاریخی {label} کافی نیست: {len(raw)} کندل.")
        frames[label] = add_indicators(raw)
    end = pd.Timestamp.now(tz="UTC").floor("15min")
    start = end-pd.Timedelta(days=days)
    return frames, start, end

def run_backtest(frames, start, end):
    """15m close signal; market fills next bar open; limits expire after 3 bars.
    SL is checked before TP when both occur inside one candle. One position at a time.
    """
    d15 = frames["15M"]
    start_i = int(d15.datetime.searchsorted(start))
    trades, active = [], None
    for i in range(max(start_i, 220), len(d15)-1):
        decision_time = d15.iloc[i].datetime + pd.Timedelta(minutes=15)
        if decision_time > end:
            break
        if active is not None:
            bar = d15.iloc[i]
            side = active["side"]
            if active["status"] == "PENDING":
                if side == "BUY":
                    filled = float(bar.low) <= active["entry"]
                else:
                    filled = float(bar.high) >= active["entry"]
                if filled:
                    active["status"] = "OPEN"
                    active["fill_time"] = decision_time
                elif i-active["signal_i"] >= 3:
                    active["result"], active["exit_time"], active["r"] = "UNFILLED", decision_time, 0.0
                    trades.append(active); active = None
            elif active["status"] == "OPEN":
                hit_sl = float(bar.low) <= active["sl"] if side == "BUY" else float(bar.high) >= active["sl"]
                hit_tp = float(bar.high) >= active["tp3"] if side == "BUY" else float(bar.low) <= active["tp3"]
                if hit_sl or hit_tp:
                    # Conservative same-candle rule: stop loss takes precedence.
                    if hit_sl:
                        active["result"], active["r"] = "LOSS", -1.0
                    else:
                        active["result"], active["r"] = "WIN", 3.0
                    active["exit_time"] = decision_time
                    trades.append(active); active = None
        if active is not None:
            continue
        # Build only candles completed by this decision timestamp: no look-ahead.
        aligned = {}
        for key, df in frames.items():
            delta = INTERVALS[key][1]
            eligible = df[df.datetime+delta <= decision_time]
            if len(eligible) < 220:
                aligned = {}; break
            aligned[key] = eligible
        if not aligned:
            continue
        sig = analyze_signal(aligned, 30)
        if sig.get("signal") not in ("BUY","SELL") or sig.get("entry") is None:
            continue
        next_bar = d15.iloc[i+1]
        side = sig["signal"]
        is_market = "MARKET" in sig.get("order_type","")
        if is_market:
            fill = float(next_bar.open)
            # Recalculate targets using actual next-bar open while preserving risk distance.
            risk = abs(float(sig["entry"])-float(sig["sl"]))
            if side == "BUY":
                sl, t1, t2, t3 = fill-risk, fill+risk, fill+2*risk, fill+3*risk
            else:
                sl, t1, t2, t3 = fill+risk, fill-risk, fill-2*risk, fill-3*risk
            active = {"side":side,"entry":fill,"sl":sl,"tp1":t1,"tp2":t2,"tp3":t3,
                      "signal_time":decision_time,"signal_i":i,"status":"OPEN",
                      "fill_time":next_bar.datetime+pd.Timedelta(minutes=15),
                      "result":None,"r":None,"score":sig["score"]}
        else:
            active = {"side":side,"entry":float(sig["entry"]),"sl":float(sig["sl"]),
                      "tp1":float(sig["tp1"]),"tp2":float(sig["tp2"]),"tp3":float(sig["tp3"]),
                      "signal_time":decision_time,"signal_i":i,"status":"PENDING",
                      "fill_time":None,"result":None,"r":None,"score":sig["score"]}
    if active is not None:
        active["result"], active["exit_time"], active["r"] = "OPEN", None, 0.0
        trades.append(active)
    return pd.DataFrame(trades)

st.sidebar.header("تنظیمات")
st.sidebar.caption("امتیاز نهایی فقط از SMC و نقدینگی محاسبه می‌شود: Sweep 40، BOS 25، FVG 20، OB proxy 15.")
live_tab, bt_tab = st.tabs(["⚡ سیگنال زنده طلا", "📊 بک‌تست جداگانه SMC 100%"])

with live_tab:
    st.subheader("سیگنال زنده GOLD · XAU/USD")
    if st.button("🔄 دریافت سیگنال زنده", key="live_refresh"):
        st.cache_data.clear()
    try:
        with st.spinner("دریافت داده‌های بازار..."):
            live = get_live_frames()
        result = analyze_signal(live, 30)
        last = live["15M"].iloc[-1]
        st.metric("قیمت آخرین کندل ۱۵ دقیقه", f"{last.close:,.2f}")
        st.metric("وضعیت", result["order_type"] if result["signal"] in ("BUY","SELL") else "NO TRADE")
        st.metric("امتیاز SMC", f'{result.get("score",0):.0f} / 100')
        if result["signal"] in ("BUY","SELL"):
            c = st.columns(5)
            for col, (name, key) in zip(c, [("Entry","entry"),("Stop Loss","sl"),("TP1","tp1"),("TP2","tp2"),("TP3","tp3")]):
                col.metric(name, f'{result[key]:,.2f}')
            st.success("سیگنال تحلیلی است؛ پیش از معامله قیمت زنده و شرایط بروکر را بررسی کن.")
        else:
            st.warning(result.get("reason","فعلاً سیگنال معتبر وجود ندارد."))
        st.caption("این بخش فقط سیگنال تحلیلی می‌دهد و هیچ معامله‌ای اجرا نمی‌کند.")
    except Exception as e:
        st.error(f"خطا در دریافت داده زنده: {e}")

with bt_tab:
    st.subheader("بک‌تست تاریخی مستقل · GOLD XAU/USD")
    st.write("این بخش جدا از سیگنال زنده است و تنظیمات یا نتیجه سیگنال زنده را تغییر نمی‌دهد.")
    days = st.selectbox("مدت بررسی", [7, 14, 30], index=0, format_func=lambda x: f"{x} روز گذشته")
    st.caption("تایم‌فریم تصمیم ۱۵ دقیقه · امتیاز SMC حداقل ۳۰ · فقط کندل‌های بسته")
    if st.button("▶ شروع بک‌تست", type="primary", key="run_bt"):
        try:
            with st.spinner("دریافت تاریخچه و اجرای بک‌تست؛ لطفاً صبر کن..."):
                hist, start, end = historical_frames(days)
                # Verify that requested period is actually covered by the 15m feed.
                available_start = hist["15M"].iloc[0].datetime
                if available_start > start-pd.Timedelta(hours=2):
                    raise ValueError(f"تاریخچه ۱۵ دقیقه‌ای کافی نیست. شروع داده موجود: {available_start}")
                trades = run_backtest(hist, start, end)
            st.session_state["v12_backtest_result"] = trades
            st.session_state["v12_backtest_period"] = days
        except Exception as e:
            st.error(f"بک‌تست انجام نشد: {e}")
    if "v12_backtest_result" in st.session_state:
        trades = st.session_state["v12_backtest_result"].copy()
        period = st.session_state.get("v12_backtest_period", 7)
        completed = trades[trades.result.isin(["WIN","LOSS"])] if not trades.empty else trades
        wins = int((completed.result=="WIN").sum()) if not completed.empty else 0
        losses = int((completed.result=="LOSS").sum()) if not completed.empty else 0
        unfilled = int((trades.result=="UNFILLED").sum()) if not trades.empty else 0
        total_r = float(completed.r.sum()) if not completed.empty else 0.0
        winrate = 100*wins/len(completed) if len(completed) else 0.0
        m = st.columns(5)
        m[0].metric("مدت", f"{period} روز")
        m[1].metric("معاملات بسته", len(completed))
        m[2].metric("برد", wins)
        m[3].metric("باخت", losses)
        m[4].metric("درصد برد", f"{winrate:.1f}%")
        st.metric("مجموع نتیجه نظری", f"{total_r:+.2f} R")
        st.caption(f"سفارش‌های لیمیت اجرا نشده: {unfilled} · معاملات باز پایان دوره در نتیجه برد/باخت حساب نشده‌اند.")
        if not trades.empty:
            view = trades.copy()
            for col in ["signal_time","fill_time","exit_time"]:
                view[col] = pd.to_datetime(view[col], utc=True, errors="coerce").dt.tz_convert(TZ).astype(str)
            view = view.rename(columns={"side":"جهت","entry":"ورود","sl":"حد ضرر","tp1":"TP1","tp2":"TP2","tp3":"TP3",
                                        "signal_time":"زمان سیگنال کابل","fill_time":"زمان ورود کابل",
                                        "exit_time":"زمان خروج کابل","result":"نتیجه","r":"نتیجه R","score":"امتیاز SMC"})
            cols = [c for c in ["جهت","زمان سیگنال کابل","زمان ورود کابل","ورود","حد ضرر","TP1","TP2","TP3","نتیجه","نتیجه R","امتیاز SMC","زمان خروج کابل"] if c in view]
            st.dataframe(view[cols], use_container_width=True, hide_index=True)
            st.download_button("دانلود گزارش CSV", trades.to_csv(index=False).encode("utf-8-sig"),
                               file_name="AFG_V12_SMC_100_backtest.csv", mime="text/csv")
        else:
            st.info("در این بازه هیچ سیگنال واجد شرایطی پیدا نشد؛ نتیجه ساختگی تولید نشده است.")
    st.warning("مهم: نتیجه بک‌تست نظری است؛ کارمزد، اسپرد و لغزش قیمت در آن محاسبه نشده‌اند. در یک کندل که SL و TP3 هر دو لمس شوند، SL مقدم فرض می‌شود. ورود MARKET با قیمت بازشدن کندل بعدی و سفارش LIMIT با لمس قیمت طی سه کندل بعدی محاسبه می‌شود. این نتیجه تضمین سود آینده نیست.")

with st.expander("روش محاسبه و محدودیت‌ها"):
    st.markdown("""
    - امتیاز نهایی ۱۰۰٪ SMC + Liquidity است: نقدینگی/Sweep برابر ۴۰، شکست ساختار BOS برابر ۲۵، FVG برابر ۲۰ و الگوی جایگزین Order Block برابر ۱۵.
    - قیمت EMA و ATR فقط برای تعیین محل ورود و حد ضرر/هدف و فیلتر شرایط فشرده استفاده می‌شوند؛ امتیاز جداگانه‌ای به روش‌های دیگر نمی‌دهند.
    - بک‌تست در هر لحظه فقط از کندل‌هایی استفاده می‌کند که تا همان زمان بسته شده‌اند.
    - در هر لحظه فقط یک معامله فعال نگه داشته می‌شود تا معاملات هم‌پوشان شمرده نشوند.
    - گزارش R ناخالص است و اسپرد، کمیسیون، سواپ و اسلیپیج را شامل نمی‌شود.
    - این نسخه ابزار تصمیم‌یار است، نه مشاور مالی و نه سیستم اجرای خودکار معامله.
    """)
st.caption("AFG AI GOLD PRO ELITE V12 · SMC + LIQUIDITY 100% · Manual trading only")
