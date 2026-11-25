import streamlit as st
import pandas as pd
import numpy as np
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ==========================================================
# AFG AI GOLD PRO ELITE V13 - DUAL ENGINE
# SMC 100% + PRICE ACTION 100% + INDEPENDENT BACKTESTS
# ==========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO ELITE V13 DUAL ENGINE",
    page_icon="🇦🇫",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root { --gold:#39c6b3; --gold2:#a6f3e7; }
html, body, [class*="css"] { font-family:Inter,sans-serif; }
.stApp { background:radial-gradient(circle at 12% 0%,#20283a 0%,#0b101a 42%,#080b12 100%); color:#edf1f7; }
.block-container { max-width:1550px; padding-top:1.25rem; padding-bottom:3rem; }
[data-testid="stHeader"] { background:rgba(8,11,18,.78); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#111827,#090d15); border-right:1px solid rgba(57,198,179,.25); }
.hero { padding:28px; border:1px solid rgba(57,198,179,.42); border-radius:24px; background:linear-gradient(125deg,rgba(57,198,179,.23),rgba(17,24,39,.96) 52%,rgba(10,14,22,.98)); margin-bottom:18px; }
.hero-title { color:#fff; font-size:clamp(1.6rem,3vw,2.5rem); font-weight:900; margin:7px 0; }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(27,43,57,.98),rgba(10,18,29,.98)); border:1px solid rgba(57,198,179,.30); padding:16px; border-radius:16px; }
[data-testid="stMetricLabel"] { color:#aeb8c8 !important; }
[data-testid="stMetricValue"] { color:#fff !important; font-weight:800 !important; }
h2 { color:#f4d58a !important; } h3 { color:#e7c77f !important; }
.stButton>button { border:1px solid rgba(57,198,179,.55); border-radius:11px; background:linear-gradient(110deg,#238f84,#72e0d0); color:#11151d; font-weight:800; min-height:2.6rem; }
hr { border-color:rgba(57,198,179,.22) !important; }
</style>
<div class="hero">
 <div style="color:#a6f3e7;font-size:.75rem;font-weight:800;letter-spacing:.2em">🇦🇫 AFG FINANCIAL INTELLIGENCE</div>
 <div class="hero-title">GOLD PRO <span style="color:#e7c77f">ELITE V13</span></div>
 <div style="color:#aeb8c8">DUAL STRATEGY CENTER · SMC 100% + PRICE ACTION 100% · MANUAL TRADING</div>
</div>
""", unsafe_allow_html=True)

st.caption("هر موتور امتیازدهی مستقل ۱۰۰٪ دارد. بک‌تست هر موتور نیز جداگانه اجرا می‌شود.")
API_URL = "https://api.twelvedata.com/time_series"
SYMBOLS = {"GOLD": "XAU/USD", "BTC": "BTC/USD"}
INTERVALS = {"5M": "5min", "15M": "15min", "1H": "1h", "4H": "4h"}
DELTAS = {"5min": pd.Timedelta(minutes=5), "15min": pd.Timedelta(minutes=15),
          "1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4)}
LOCAL_TZ = ZoneInfo("Asia/Kabul")
TIMEOUT = 25
MIN_SCORE = 30
SIGNAL_VALIDITY_MINUTES = 45
MAX_DAILY_SIGNALS = 8

st_autorefresh(interval=5 * 60 * 1000, key="v13_refresh")

with st.sidebar:
    st.markdown("### 🇦🇫 AFG GOLD PRO")
    st.caption("V13 · TWO INDEPENDENT 100% ENGINES")
    refresh = st.button("🔄 Refresh Market Data", use_container_width=True)
    st.caption("SMC 100% و Price Action 100% جداگانه")
    st.caption("حداکثر ۸ سیگنال روزانه · اعتبار ۴۵ دقیقه")

try:
    API_KEY = st.secrets["TWELVE_DATA_API_KEY"]
except Exception:
    API_KEY = ""

if not API_KEY:
    st.error("کلید Twelve Data در Streamlit Secrets پیدا نشد. نام Secret باید TWELVE_DATA_API_KEY باشد.")
    st.stop()

if refresh:
    st.cache_data.clear()

@st.cache_data(ttl=60, show_spinner=False)
def get_candles(symbol: str, interval: str, api_key: str, outputsize: int = 1000) -> pd.DataFrame:
    params = {"symbol": symbol, "interval": interval, "outputsize": outputsize,
              "apikey": api_key, "timezone": "UTC", "format": "JSON"}
    response = requests.get(API_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise ValueError(f"Twelve Data: {payload.get('message') or payload.get('code') or payload}")
    df = pd.DataFrame(payload["values"])
    needed = ["datetime", "open", "high", "low", "close"]
    if any(c not in df.columns for c in needed):
        raise ValueError("ساختار داده تاریخی معتبر نیست.")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=needed).sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=3)
    df = df[df["datetime"] + DELTAS[interval] <= cutoff].reset_index(drop=True)
    if len(df) < 220:
        raise ValueError(f"داده بسته‌شده کافی نیست: {len(df)} کندل؛ حداقل ۲۲۰ لازم است.")
    return df

def add_indicators(df):
    d = df.copy()
    c = d["close"]
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
    tr = pd.concat([(d.high-d.low), (d.high-prev).abs(), (d.low-prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    up, down = d.high.diff(), -d.low.diff()
    pdm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=d.index)
    mdm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=d.index)
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/d.atr.replace(0,np.nan)
    mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/d.atr.replace(0,np.nan)
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    d["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean().fillna(0)
    return d

def trend_of(row):
    if row.close > row.ema50 > row.ema200: return "BULLISH"
    if row.close < row.ema50 < row.ema200: return "BEARISH"
    return "MIXED"

def candle_quality(row, side):
    rng = max(float(row.high-row.low), 1e-12)
    body = abs(float(row.close-row.open))/rng
    if side == "BUY":
        return row.close > row.open and body >= .30 and (row.high-row.close)/rng <= .30
    return row.close < row.open and body >= .30 and (row.close-row.low)/rng <= .30

def make_levels(d, side, current):
    atr = float(d.iloc[-1].atr)
    if not np.isfinite(atr) or atr <= 0: return None
    ema = float(d.iloc[-1].ema20)
    near = abs(current-ema) <= .15*atr
    if side == "BUY":
        entry = current if near else ema+.05*atr
        sl = min(float(d.tail(12).low.min())-.12*atr, entry-.55*atr)
        risk = entry-sl
        valid_entry = near or 0 <= (current-entry)/atr <= 1.20
        if not valid_entry or not (.35*atr <= risk <= 2.5*atr): return None
        return {"entry":entry,"sl":sl,"tp1":entry+risk,"tp2":entry+2*risk,"tp3":entry+3*risk,
                "order_type":"BUY MARKET" if near else "BUY LIMIT"}
    entry = current if near else ema-.05*atr
    sl = max(float(d.tail(12).high.max())+.12*atr, entry+.55*atr)
    risk = sl-entry
    valid_entry = near or 0 <= (entry-current)/atr <= 1.20
    if not valid_entry or not (.35*atr <= risk <= 2.5*atr): return None
    return {"entry":entry,"sl":sl,"tp1":entry-risk,"tp2":entry-2*risk,"tp3":entry-3*risk,
            "order_type":"SELL MARKET" if near else "SELL LIMIT"}

def analyze_smc(frames, score_floor=MIN_SCORE):
    d = frames["15M"]
    if len(d) < 220: return {"signal":"NO TRADE","score":0}
    r = d.iloc[-1]; current=float(r.close); atr=float(r.atr) if np.isfinite(r.atr) else 0
    if atr <= 0: return {"signal":"NO TRADE","score":0}
    prior=d.iloc[-25:-1]; liq=d.iloc[-21:-1]
    prior_hi, prior_lo=float(liq.high.max()),float(liq.low.min())
    sweep_buy=float(r.low)<prior_lo and current>prior_lo
    sweep_sell=float(r.high)>prior_hi and current<prior_hi
    fvg_buy=float(r.low)>float(d.iloc[-3].high)
    fvg_sell=float(r.high)<float(d.iloc[-3].low)
    bos_buy=current>float(prior.tail(12).high.max())
    bos_sell=current<float(prior.tail(12).low.min())
    p=d.iloc[-2]
    ob_buy=p.close<p.open and current>p.high and current-p.low>=.35*atr
    ob_sell=p.close>p.open and current<p.low and p.high-current>=.35*atr
    buy=(40 if sweep_buy else 0)+(25 if bos_buy else 0)+(20 if fvg_buy else 0)+(15 if ob_buy else 0)
    sell=(40 if sweep_sell else 0)+(25 if bos_sell else 0)+(20 if fvg_sell else 0)+(15 if ob_sell else 0)
    recent=d.tail(24)
    ema_gap=abs(float(r.ema20-r.ema50))/atr
    range_atr=(float(recent.high.max()-recent.low.min()))/atr
    choppy=float(r.adx)<10 and ema_gap<.08 and range_atr<2
    side = "BUY" if buy>=score_floor and buy>sell+1 else "SELL" if sell>=score_floor and sell>buy+1 else None
    if choppy: side=None
    levels=make_levels(d,side,current) if side else None
    if not levels: side=None
    return {"signal":side or "NO TRADE","score":int(max(buy,sell)),"buy_score":buy,"sell_score":sell,
            "engine":"SMC 100%","atr":atr,**(levels or {})}

def analyze_price_action(frames, score_floor=MIN_SCORE):
    d=frames["15M"]
    if len(d)<220: return {"signal":"NO TRADE","score":0}
    r=d.iloc[-1]; p=d.iloc[-2]; current=float(r.close)
    atr=float(r.atr) if np.isfinite(r.atr) else 0
    if atr<=0: return {"signal":"NO TRADE","score":0}
    recent=d.iloc[-21:-1]
    ph=float(recent.high.max()); pl=float(recent.low.min())
    rng=max(float(r.high-r.low),1e-12)
    body=abs(float(r.close-r.open))/rng
    upper=(float(r.high)-max(float(r.open),float(r.close)))/rng
    lower=(min(float(r.open),float(r.close))-float(r.low))/rng
    bull_engulf=(r.close>r.open and p.close<p.open and r.close>=p.open and r.open<=p.close)
    bear_engulf=(r.close<r.open and p.close>p.open and r.open>=p.close and r.close<=p.open)
    bull_pin=(lower>=.55 and body<=.35 and r.close>r.open)
    bear_pin=(upper>=.55 and body<=.35 and r.close<r.open)
    breakout_up=current>ph and r.close>r.open
    breakout_dn=current<pl and r.close<r.open
    trend_up=r.close>r.ema20>r.ema50
    trend_dn=r.close<r.ema20<r.ema50
    buy=(30 if bull_engulf else 0)+(25 if bull_pin else 0)+(25 if breakout_up else 0)+(20 if trend_up else 0)
    sell=(30 if bear_engulf else 0)+(25 if bear_pin else 0)+(25 if breakout_dn else 0)+(20 if trend_dn else 0)
    # Avoid low-quality indecision candles; no forced trades in compressed conditions.
    choppy=float(r.adx)<10 and abs(float(r.ema20-r.ema50))/atr<.08 and (float(d.tail(24).high.max()-d.tail(24).low.min())/atr)<2
    side="BUY" if buy>=score_floor and buy>sell+1 else "SELL" if sell>=score_floor and sell>buy+1 else None
    if choppy: side=None
    levels=make_levels(d,side,current) if side else None
    if not levels: side=None
    return {"signal":side or "NO TRADE","score":int(max(buy,sell)),"buy_score":buy,"sell_score":sell,
            "engine":"PRICE ACTION 100%","atr":atr,**(levels or {})}

def load_live_market():
    market, errors = {}, {}
    for asset,symbol in SYMBOLS.items():
        frames={}; issues=[]
        for label,interval in INTERVALS.items():
            try: frames[label]=add_indicators(get_candles(symbol,interval,API_KEY))
            except Exception as e: issues.append(f"{label}: {e}")
        if len(frames)==4: market[asset]=frames
        if issues: errors[asset]=issues
    return market,errors

def run_backtest(symbol, days, engine_name, score_floor=MIN_SCORE):
    """Walk-forward 15m backtest. Signals use only candles closed by decision time."""
    interval_map={"5M":"5min","15M":"15min","1H":"1h","4H":"4h"}
    frames={}
    # 5000 bars per interval; provider plan may restrict history. Coverage is checked below.
    for label,interval in interval_map.items():
        raw=get_candles(symbol,interval,API_KEY,outputsize=5000)
        frames[label]=add_indicators(raw)
    d15=frames["15M"]
    end=d15.datetime.iloc[-1]+DELTAS["15min"]
    start=end-pd.Timedelta(days=int(days))
    test_indices=d15.index[(d15.datetime+DELTAS["15min"]>=start)&(d15.datetime+DELTAS["15min"]<=end)].tolist()
    if len(test_indices)<20:
        raise ValueError(f"تعداد کندل‌های ۱۵ دقیقه‌ای در بازه کافی نیست: {len(test_indices)}.")
    first=test_indices[0]
    if first<220: raise ValueError("داده پیش‌زمینه کافی برای محاسبه اندیکاتورها موجود نیست.")
    trades=[]
    i=first
    while i<test_indices[-1]:
        decision_time=d15.iloc[i].datetime+DELTAS["15min"]
        sliced={}
        for label,delta in [("5M",DELTAS["5min"]),("15M",DELTAS["15min"]),("1H",DELTAS["1h"]),("4H",DELTAS["4h"])]:
            eligible=frames[label][frames[label].datetime+delta<=decision_time]
            if len(eligible)<220: sliced={}; break
            sliced[label]=eligible
        if not sliced:
            i+=1; continue
        sig=analyze_smc(sliced,score_floor) if engine_name=="SMC 100%" else analyze_price_action(sliced,score_floor)
        if sig.get("signal") not in ("BUY","SELL") or not sig.get("entry"):
            i+=1; continue
        side=sig["signal"]; entry=float(sig["entry"]); sl=float(sig["sl"])
        tp3=float(sig["tp3"]); order=sig.get("order_type","")
        fill_index=None; fill_price=None
        # Market fills at next candle open; limit fills only if touched within 3 bars.
        for j in range(i+1,min(i+4,len(d15))):
            bar=d15.iloc[j]
            if "MARKET" in order:
                fill_index=j; fill_price=float(bar.open); break
            touched=float(bar.low)<=entry<=float(bar.high)
            if touched:
                fill_index=j; fill_price=entry; break
        if fill_index is None:
            i+=1; continue
        outcome="OPEN"; exit_price=float(d15.iloc[-1].close); exit_index=len(d15)-1
        for k in range(fill_index,len(d15)):
            bar=d15.iloc[k]
            if side=="BUY":
                hit_sl=float(bar.low)<=sl; hit_tp=float(bar.high)>=tp3
            else:
                hit_sl=float(bar.high)>=sl; hit_tp=float(bar.low)<=tp3
            if hit_sl and hit_tp:
                outcome="LOSS (SL first)"; exit_price=sl; exit_index=k; break
            if hit_sl:
                outcome="LOSS"; exit_price=sl; exit_index=k; break
            if hit_tp:
                outcome="WIN (TP3)"; exit_price=tp3; exit_index=k; break
        risk=abs(fill_price-sl)
        if risk<=0: i=fill_index+1; continue
        if side=="BUY": r_multiple=(exit_price-fill_price)/risk
        else: r_multiple=(fill_price-exit_price)/risk
        trades.append({"موتور":engine_name,"جهت":side,"زمان سیگنال (UTC)":decision_time,
                       "زمان ورود (UTC)":d15.iloc[fill_index].datetime+DELTAS["15min"],
                       "قیمت ورود":round(fill_price,3),"حد ضرر":round(sl,3),"هدف سوم":round(tp3,3),
                       "نتیجه":outcome,"R":round(r_multiple,2)})
        # One position at a time per engine; skip bars until this trade exits.
        i=max(exit_index+1,fill_index+1)
    if not trades: return pd.DataFrame(), {"trades":0,"wins":0,"losses":0,"win_rate":0.0,"net_r":0.0}
    out=pd.DataFrame(trades)
    wins=int(out["نتیجه"].str.startswith("WIN").sum())
    losses=int(out["نتیجه"].str.startswith("LOSS").sum())
    return out, {"trades":len(out),"wins":wins,"losses":losses,
                 "win_rate":round(wins/len(out)*100,2),
                 "net_r":round(float(out["R"].sum()),2)}

# ---------------- LIVE DASHBOARD ----------------
market, errors = load_live_market()
if not market:
    st.error("داده کامل بازار دریافت نشد. دسترسی Twelve Data، نمادها و محدودیت API را بررسی کن.")
    for a,items in errors.items():
        st.write(f"**{a}**")
        for x in items: st.write("- "+x)
    st.stop()

st.subheader("⚡ LIVE MARKET CENTER")
for asset,frames in market.items():
    st.markdown(f"### {'🥇 GOLD' if asset=='GOLD' else '₿ BITCOIN'} · {SYMBOLS[asset]}")
    a,b,c=st.columns(3)
    last=float(frames["15M"].iloc[-1].close)
    a.metric("LIVE PRICE",f"{last:,.2f}")
    smc=analyze_smc(frames)
    pa=analyze_price_action(frames)
    b.metric("SMC 100%",smc.get("order_type",smc["signal"]) if smc["signal"]!="NO TRADE" else "NO TRADE")
    c.metric("PRICE ACTION 100%",pa.get("order_type",pa["signal"]) if pa["signal"]!="NO TRADE" else "NO TRADE")
    cols=st.columns(2)
    for col,res,label in [(cols[0],smc,"SMC"),(cols[1],pa,"PRICE ACTION")]:
        with col:
            st.markdown(f"**{label} · امتیاز {res.get('score',0)}/100**")
            if res["signal"] in ("BUY","SELL"):
                x,y,z=st.columns(3)
                x.metric("ENTRY",f"{res['entry']:,.2f}")
                y.metric("SL",f"{res['sl']:,.2f}")
                z.metric("TP3",f"{res['tp3']:,.2f}")
                st.caption(f"TP1: {res['tp1']:,.2f} · TP2: {res['tp2']:,.2f}")
                st.info("سیگنال تحلیلی است؛ ورود دستی و بررسی قیمت بروکر ضروری است.")
            else:
                st.caption("فعلاً سیگنال معتبر وجود ندارد.")
    st.divider()

# ---------------- INDEPENDENT BACKTEST AREA ----------------
st.subheader("📊 BACKTEST LAB · بخش مستقل بک‌تست")
st.warning("بک‌تست از داده تاریخی Twelve Data استفاده می‌کند. نتیجه گذشته تضمین سود آینده نیست.")
with st.form("backtest_form"):
    c1,c2,c3=st.columns(3)
    bt_asset=c1.selectbox("بازار",["GOLD · XAU/USD","BTC · BTC/USD"])
    bt_days=c2.selectbox("مدت آزمایش", [7,14,30], index=0, format_func=lambda x:f"{x} روز گذشته")
    bt_engine=c3.selectbox("موتور",["هر دو موتور","SMC 100%","PRICE ACTION 100%"])
    submitted=st.form_submit_button("▶ شروع بک‌تست",use_container_width=True)

if submitted:
    bt_symbol="XAU/USD" if bt_asset.startswith("GOLD") else "BTC/USD"
    selected=["SMC 100%","PRICE ACTION 100%"] if bt_engine=="هر دو موتور" else [bt_engine]
    all_results={}
    try:
        with st.spinner("در حال دریافت کندل‌های تاریخی و اجرای آزمایش..."):
            for eng in selected:
                # The cached historical candles are reused between the two independent engines.
                trades,stats=run_backtest(bt_symbol,bt_days,eng)
                all_results[eng]=(trades,stats)
        st.session_state["bt_results"]=all_results
        st.session_state["bt_asset"]=bt_asset
        st.session_state["bt_days"]=bt_days
    except Exception as exc:
        st.error(f"بک‌تست اجرا نشد: {exc}")
        st.caption("اگر محدودیت پلن Twelve Data اجازه ۵۰۰۰ کندل ندهد یا تاریخ کافی موجود نباشد، نتیجه نمایش داده نمی‌شود.")

if "bt_results" in st.session_state:
    st.markdown(f"**نتایج آخرین اجرا: {st.session_state.get('bt_asset','')} · {st.session_state.get('bt_days',7)} روز**")
    for eng,(trades,stats) in st.session_state["bt_results"].items():
        st.markdown(f"### {eng}")
        m=st.columns(5)
        m[0].metric("معاملات",stats["trades"])
        m[1].metric("برد",stats["wins"])
        m[2].metric("باخت",stats["losses"])
        m[3].metric("Win rate",f"{stats['win_rate']:.2f}%")
        m[4].metric("خالص نتیجه",f"{stats['net_r']:.2f} R")
        if trades.empty:
            st.info("در این بازه معامله‌ای مطابق قوانین موتور پیدا نشد.")
        else:
            st.dataframe(trades,use_container_width=True,hide_index=True)
            csv=trades.to_csv(index=False).encode("utf-8-sig")
            st.download_button(f"دانلود گزارش {eng} CSV",csv,file_name=f"backtest_{eng.replace(' ','_')}.csv",mime="text/csv",key=f"csv_{eng}")

with st.expander("روش محاسبه و محدودیت‌های بک‌تست"):
    st.write("""
    - هر موتور مستقل است: SMC فقط امتیاز SMC/Liquidity را می‌سنجد؛ Price Action فقط الگوهای کندلی، شکست محدوده و روند را امتیاز می‌دهد.
    - سیگنال روی کندل ۱۵ دقیقه‌ای بسته‌شده ساخته می‌شود؛ کندل‌های تایم‌فریم‌های دیگر فقط تا زمان بسته‌شدن خودشان مجازند.
    - سفارش MARKET در بازشدن کندل بعدی فرض می‌شود؛ سفارش LIMIT فقط در سه کندل بعدی و در صورت لمس قیمت ورود پر می‌شود.
    - معامله هم‌زمان جدید برای همان موتور تا بسته‌شدن معامله قبلی آغاز نمی‌شود.
    - برخورد هم‌زمان SL و TP3 در یک کندل، محافظه‌کارانه ضرر محسوب می‌شود.
    - خروج آزمایشی روی SL یا TP3 است؛ TP1 و TP2 فقط در گزارش زنده نمایش داده می‌شوند.
    - کارمزد، اسپرد، اسلیپیج و اختلاف قیمت کارگزار لحاظ نشده‌اند؛ نتایج ناخالص و نظری‌اند.
    - داده تاریخی محدود به دسترسی و سهمیه پلن Twelve Data است. اگر داده کافی نباشد، خطا نمایش داده می‌شود و نتیجه ساختگی تولید نمی‌شود.
    - امتیاز ۱۰۰ به معنی احتمال برد ۱۰۰٪ نیست. ابتدا روی حساب دمو و با هزینه‌های واقعی بررسی کن.
    """)
st.caption("AFG AI GOLD PRO ELITE V13 · SMC 100% + PRICE ACTION 100% · Manual decision support only")
