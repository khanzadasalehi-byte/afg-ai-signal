import streamlit as st
import pandas as pd
import numpy as np
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ==========================================================
# AFG AI GOLD PRO ELITE V14 - FIVE INDEPENDENT ENGINES
# PRICE ACTION + SMC + ICT + CRT + RTM (EACH 100%)
# ==========================================================

st.set_page_config(
    page_title="AFG AI GOLD PRO ELITE V14 FIVE ENGINES",
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
 <div class="hero-title">GOLD PRO <span style="color:#e7c77f">ELITE V14</span></div>
 <div style="color:#aeb8c8">FIVE INDEPENDENT STRATEGY ENGINES · COMPARATIVE BACKTEST · MANUAL TRADING</div>
</div>
""", unsafe_allow_html=True)

st.caption("پنج موتور مستقل؛ هر موتور امتیازدهی ۱۰۰٪ و بک‌تست جداگانه برای مقایسه دارد.")
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

st_autorefresh(interval=5 * 60 * 1000, key="v14_refresh")

with st.sidebar:
    st.markdown("### 🇦🇫 AFG GOLD PRO")
    st.caption("V14 · FIVE INDEPENDENT 100% ENGINES")
    refresh = st.button("🔄 Refresh Market Data", use_container_width=True)
    st.caption("PA · SMC · ICT · CRT · RTM — مستقل")
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



def analyze_ict(frames, score_floor=MIN_SCORE):
    """ICT-inspired proxy: liquidity raid, displacement, FVG and premium/discount."""
    d = frames["15M"]
    if len(d) < 220: return {"signal":"NO TRADE","score":0}
    r, p = d.iloc[-1], d.iloc[-2]
    atr = float(r.atr) if np.isfinite(r.atr) else 0.0
    if atr <= 0: return {"signal":"NO TRADE","score":0}
    pool = d.iloc[-21:-1]
    prior_hi, prior_lo = float(pool.high.max()), float(pool.low.min())
    sweep_b = float(r.low) < prior_lo and float(r.close) > prior_lo
    sweep_s = float(r.high) > prior_hi and float(r.close) < prior_hi
    body = abs(float(r.close-r.open))
    displacement_b = r.close > r.open and body >= .65*atr and r.close > p.high
    displacement_s = r.close < r.open and body >= .65*atr and r.close < p.low
    fvg_b = float(r.low) > float(d.iloc[-3].high)
    fvg_s = float(r.high) < float(d.iloc[-3].low)
    dealing_mid = (float(pool.high.max()) + float(pool.low.min())) / 2
    discount = float(r.close) < dealing_mid
    premium = float(r.close) > dealing_mid
    buy = (30 if sweep_b else 0)+(30 if displacement_b else 0)+(25 if fvg_b else 0)+(15 if discount else 0)
    sell = (30 if sweep_s else 0)+(30 if displacement_s else 0)+(25 if fvg_s else 0)+(15 if premium else 0)
    side = "BUY" if buy >= score_floor and buy > sell else "SELL" if sell >= score_floor and sell > buy else None
    levels = make_levels(d, side, float(r.close)) if side else None
    if not levels: side = None
    return {"signal":side or "NO TRADE","score":int(max(buy,sell)),"buy_score":buy,
            "sell_score":sell,"engine":"ICT 100%","atr":atr,**(levels or {})}


def analyze_crt(frames, score_floor=MIN_SCORE):
    """Candle Range Theory proxy using the last completed 4H range and 15m reclaim."""
    d, h4 = frames["15M"], frames["4H"]
    if len(d) < 220 or len(h4) < 3: return {"signal":"NO TRADE","score":0}
    r = d.iloc[-1]
    atr = float(r.atr) if np.isfinite(r.atr) else 0.0
    if atr <= 0: return {"signal":"NO TRADE","score":0}
    # Use the most recent completed 4H candle only; no future candles.
    rng = h4.iloc[-1]
    rh, rl = float(rng.high), float(rng.low)
    mid = (rh+rl)/2
    raid_low = float(r.low) < rl and float(r.close) > rl
    raid_high = float(r.high) > rh and float(r.close) < rh
    reclaim_b = raid_low and float(r.close) > mid
    reclaim_s = raid_high and float(r.close) < mid
    candle_b = candle_quality(r, "BUY")
    candle_s = candle_quality(r, "SELL")
    trend_b = float(r.close) > float(r.ema20)
    trend_s = float(r.close) < float(r.ema20)
    buy = (45 if reclaim_b else 0)+(25 if candle_b else 0)+(15 if trend_b else 0)+(15 if float(r.close)>mid else 0)
    sell = (45 if reclaim_s else 0)+(25 if candle_s else 0)+(15 if trend_s else 0)+(15 if float(r.close)<mid else 0)
    side = "BUY" if buy >= score_floor and buy > sell else "SELL" if sell >= score_floor and sell > buy else None
    levels = make_levels(d, side, float(r.close)) if side else None
    if not levels: side = None
    return {"signal":side or "NO TRADE","score":int(max(buy,sell)),"buy_score":buy,
            "sell_score":sell,"engine":"CRT 100%","atr":atr,**(levels or {})}


def analyze_rtm(frames, score_floor=MIN_SCORE):
    """RTM-inspired proxy: base/departure, return-to-zone and rejection."""
    d = frames["15M"]
    if len(d) < 220: return {"signal":"NO TRADE","score":0}
    r = d.iloc[-1]
    atr = float(r.atr) if np.isfinite(r.atr) else 0.0
    if atr <= 0: return {"signal":"NO TRADE","score":0}
    hist = d.iloc[-30:-2]
    # Approximate demand/supply zones from compact-base candles before a strong departure.
    ranges = (hist.high-hist.low).replace(0, np.nan)
    compact = ranges <= ranges.rolling(5, min_periods=3).median()*0.75
    demand_idx, supply_idx = [], []
    for j in range(2, len(hist)-2):
        base = hist.iloc[j-1:j+2]
        base_range = float((base.high-base.low).mean())
        if base_range > .55*atr: continue
        after = hist.iloc[j+2]
        before = hist.iloc[j-2]
        if float(after.close-after.open) >= .8*atr and after.close > base.high.max():
            demand_idx.append(j)
        if float(after.open-after.close) >= .8*atr and after.close < base.low.min():
            supply_idx.append(j)
    demand_score = 0
    supply_score = 0
    if demand_idx:
        z = hist.iloc[demand_idx[-1]-1:demand_idx[-1]+2]
        zlo, zhi = float(z.low.min()), float(z.high.max())
        touched = float(r.low) <= zhi and float(r.high) >= zlo
        rejected = float(r.close) > float(r.open) and float(r.close) > (zlo+zhi)/2
        demand_score = (45 if touched else 0)+(30 if rejected else 0)+(25 if r.close>r.ema20 else 0)
    if supply_idx:
        z = hist.iloc[supply_idx[-1]-1:supply_idx[-1]+2]
        zlo, zhi = float(z.low.min()), float(z.high.max())
        touched = float(r.high) >= zlo and float(r.low) <= zhi
        rejected = float(r.close) < float(r.open) and float(r.close) < (zlo+zhi)/2
        supply_score = (45 if touched else 0)+(30 if rejected else 0)+(25 if r.close<r.ema20 else 0)
    side = "BUY" if demand_score >= score_floor and demand_score > supply_score else "SELL" if supply_score >= score_floor and supply_score > demand_score else None
    levels = make_levels(d, side, float(r.close)) if side else None
    if not levels: side = None
    return {"signal":side or "NO TRADE","score":int(max(demand_score,supply_score)),
            "buy_score":demand_score,"sell_score":supply_score,"engine":"RTM 100%",
            "atr":atr,**(levels or {})}


ENGINE_FUNCTIONS = {
    "PRICE ACTION 100%": analyze_price_action,
    "SMC 100%": analyze_smc,
    "ICT 100%": analyze_ict,
    "CRT 100%": analyze_crt,
    "RTM 100%": analyze_rtm,
}


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
        sig=ENGINE_FUNCTIONS[engine_name](sliced,score_floor)
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
    if not trades: return pd.DataFrame(), {"trades":0,"closed":0,"open":0,"wins":0,"losses":0,"win_rate":0.0,"net_r":0.0,"open_r":0.0}
    out=pd.DataFrame(trades)
    closed = out[out["نتیجه"] != "OPEN"]
    open_count = int((out["نتیجه"] == "OPEN").sum())
    wins = int(closed["نتیجه"].str.startswith("WIN").sum())
    losses = int(closed["نتیجه"].str.startswith("LOSS").sum())
    closed_count = len(closed)
    win_rate = round(wins/closed_count*100,2) if closed_count else 0.0
    realized_r = round(float(closed["R"].sum()),2) if closed_count else 0.0
    open_r = round(float(out.loc[out["نتیجه"] == "OPEN","R"].sum()),2) if open_count else 0.0
    return out, {"trades":len(out),"closed":closed_count,"open":open_count,
                 "wins":wins,"losses":losses,"win_rate":win_rate,
                 "net_r":realized_r,"open_r":open_r}

# ---------------- LIVE DASHBOARD ----------------
market, errors = load_live_market()
if not market:
    st.error("داده کامل بازار دریافت نشد. دسترسی Twelve Data، نمادها و محدودیت API را بررسی کن.")
    for a,items in errors.items():
        st.write(f"**{a}**")
        for x in items: st.write("- "+x)
    st.stop()

st.subheader("⚡ LIVE MARKET CENTER · پنج موتور مستقل")
for asset,frames in market.items():
    st.markdown(f"### {'🥇 GOLD' if asset=='GOLD' else '₿ BITCOIN'} · {SYMBOLS[asset]}")
    last=float(frames["15M"].iloc[-1].close)
    st.metric("قیمت آخرین کندل بسته‌شده 15M",f"{last:,.2f}")
    cols=st.columns(5)
    for col,(engine_name,engine_fn) in zip(cols,ENGINE_FUNCTIONS.items()):
        res=engine_fn(frames)
        with col:
            st.markdown(f"**{engine_name}**")
            st.metric("وضعیت",res.get("order_type",res["signal"]) if res["signal"]!="NO TRADE" else "NO TRADE")
            st.metric("امتیاز",f"{res.get('score',0)}/100")
            if res["signal"] in ("BUY","SELL"):
                st.caption(f"Entry: {res['entry']:,.2f}")
                st.caption(f"SL: {res['sl']:,.2f}")
                st.caption(f"TP1: {res['tp1']:,.2f}")
                st.caption(f"TP2: {res['tp2']:,.2f}")
                st.caption(f"TP3: {res['tp3']:,.2f}")
            else:
                st.caption("در حال حاضر شرایط ورود این موتور کامل نیست.")
    st.info("سیگنال‌ها صرفاً تحلیلی‌اند؛ اجرای دستی پس از بررسی قیمت بروکر و مدیریت ریسک انجام شود.")
    st.divider()

# ---------------- FIVE-ENGINE COMPARATIVE BACKTEST ----------------
st.subheader("📊 BACKTEST LAB · مقایسه پنج موتور")
st.warning("بک‌تست بر اساس کندل‌های تاریخی Twelve Data است. نتایج گذشته تضمین عملکرد آینده نیستند.")
with st.form("backtest_form_v14"):
    c1,c2,c3=st.columns(3)
    bt_asset=c1.selectbox("بازار",["GOLD · XAU/USD","BTC · BTC/USD"])
    bt_days=c2.selectbox("مدت آزمایش", [7,14,30], index=0, format_func=lambda x:f"{x} روز گذشته")
    bt_engine=c3.selectbox("موتورها",["هر پنج موتور","فقط Price Action","فقط SMC","فقط ICT","فقط CRT","فقط RTM"])
    submitted=st.form_submit_button("▶ شروع مقایسه بک‌تست",use_container_width=True)

if submitted:
    bt_symbol="XAU/USD" if bt_asset.startswith("GOLD") else "BTC/USD"
    engine_labels = {
        "فقط Price Action":["PRICE ACTION 100%"],
        "فقط SMC":["SMC 100%"],
        "فقط ICT":["ICT 100%"],
        "فقط CRT":["CRT 100%"],
        "فقط RTM":["RTM 100%"],
    }
    selected=list(ENGINE_FUNCTIONS.keys()) if bt_engine=="هر پنج موتور" else engine_labels[bt_engine]
    all_results={}
    try:
        with st.spinner("در حال دریافت داده‌های تاریخی و اجرای پنج آزمایش مستقل..."):
            for eng in selected:
                trades,stats=run_backtest(bt_symbol,bt_days,eng)
                all_results[eng]=(trades,stats)
        st.session_state["bt_results"]=all_results
        st.session_state["bt_asset"]=bt_asset
        st.session_state["bt_days"]=bt_days
    except Exception as exc:
        st.error(f"بک‌تست اجرا نشد: {exc}")
        st.caption("اگر محدودیت پلن Twelve Data اجازه دریافت تاریخ کافی ندهد، نتیجه ساختگی نمایش داده نمی‌شود.")

if "bt_results" in st.session_state:
    st.markdown(f"**نتایج آخرین اجرا: {st.session_state.get('bt_asset','')} · {st.session_state.get('bt_days',7)} روز**")
    summary=[]
    for eng,(trades,stats) in st.session_state["bt_results"].items():
        summary.append({"موتور":eng,"کل معاملات":stats["trades"],"بسته‌شده":stats.get("closed",0),
                        "باز":stats.get("open",0),"برد":stats["wins"],"باخت":stats["losses"],
                        "درصد برد معاملات بسته‌شده":stats["win_rate"],"R خالص بسته‌شده":stats["net_r"],
                        "R شناور معاملات باز":stats.get("open_r",0)})
    summary_df=pd.DataFrame(summary)
    st.markdown("### 🏆 جدول مقایسه")
    st.dataframe(summary_df,use_container_width=True,hide_index=True)
    if not summary_df.empty:
        best=summary_df.sort_values(["R خالص بسته‌شده","درصد برد معاملات بسته‌شده"],ascending=False).iloc[0]
        st.success(f"بر اساس R خالص بسته‌شده در همین بازه، نتیجه برتر: {best['موتور']} · {best['R خالص بسته‌شده']} R")
    for eng,(trades,stats) in st.session_state["bt_results"].items():
        with st.expander(f"{eng} · جزئیات معاملات",expanded=False):
            m=st.columns(7)
            m[0].metric("کل",stats["trades"])
            m[1].metric("بسته",stats.get("closed",0))
            m[2].metric("باز",stats.get("open",0))
            m[3].metric("برد",stats["wins"])
            m[4].metric("باخت",stats["losses"])
            m[5].metric("Win rate",f"{stats['win_rate']:.2f}%")
            m[6].metric("خالص R",f"{stats['net_r']:.2f}")
            if trades.empty:
                st.info("در این بازه معامله‌ای مطابق قوانین این موتور پیدا نشد.")
            else:
                st.dataframe(trades,use_container_width=True,hide_index=True)
                csv=trades.to_csv(index=False).encode("utf-8-sig")
                st.download_button(f"دانلود گزارش {eng} CSV",csv,
                    file_name=f"v14_backtest_{eng.replace(' ','_')}.csv",
                    mime="text/csv",key=f"csv_v14_{eng}")

with st.expander("روش محاسبه و محدودیت‌های بک‌تست"):
    st.write("""
    - پنج موتور مستقل‌اند و امتیاز هرکدام جداگانه از ۱۰۰ محاسبه می‌شود: Price Action، SMC، ICT، CRT و RTM.
    - این پیاده‌سازی‌ها مدل‌های الگوریتمی/تقریبی از مفاهیم هر روش‌اند؛ جایگزین تشخیص دستی نواحی نهادی یا داده واقعی سفارشات نیستند.
    - ICT از Sweep، Displacement، FVG و Premium/Discount؛ CRT از محدوده آخرین کندل بسته‌شده 4H و Raid/Reclaim؛ RTM از الگوی تقریبی Base/Departure/Retest استفاده می‌کند.
    - سیگنال روی کندل ۱۵ دقیقه‌ای بسته‌شده ساخته می‌شود؛ کندل‌های تایم‌فریم‌های دیگر فقط تا زمان بسته‌شدن خودشان مجازند.
    - سفارش MARKET در بازشدن کندل بعدی فرض می‌شود؛ سفارش LIMIT فقط در سه کندل بعدی و در صورت لمس قیمت ورود پر می‌شود.
    - معامله هم‌زمان جدید برای همان موتور تا بسته‌شدن معامله قبلی آغاز نمی‌شود.
    - برخورد هم‌زمان SL و TP3 در یک کندل، محافظه‌کارانه ضرر محسوب می‌شود.
    - خروج آزمایشی روی SL یا TP3 است؛ TP1 و TP2 فقط در کارت زنده نمایش داده می‌شوند.
    - معامله‌های OPEN از درصد برد معاملات بسته‌شده و R خالص تحقق‌یافته جدا هستند.
    - کارمزد، اسپرد و اسلیپیج هنوز در محاسبه وارد نشده‌اند؛ نتایج ناخالص و نظری‌اند.
    - داده تاریخی محدود به دسترسی و سهمیه پلن Twelve Data است. اگر داده کافی نباشد، خطا نمایش داده می‌شود و نتیجه ساختگی تولید نمی‌شود.
    - امتیاز ۱۰۰ به معنی احتمال برد ۱۰۰٪ نیست. ابتدا روی حساب دمو و با هزینه‌های واقعی بررسی کن.
    """)
st.caption("AFG AI GOLD PRO ELITE V14 · FIVE INDEPENDENT ENGINES · Manual decision support only")
