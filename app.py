# -*- coding: utf-8 -*-
"""
AFG GOLD ULTIMATE PA + SMC
Two independent, rule-based XAU/USD analysis engines:
  1) Broad Price Action engine
  2) Broad Smart Money Concepts engine

Data: Twelve Data (XAU/USD) using Streamlit Secrets: TWELVE_DATA_API_KEY
Signals are decision support, not financial advice. No profitability is guaranteed.

Important implementation notes:
- PA and SMC are interpretive trading frameworks; no finite program can encode every
  discretionary interpretation or every named variant used worldwide.
- This app implements a broad, explicit, OHLC-based rule set. Volume/order-book based
  concepts are proxies or omitted where the data provider does not supply the required data.
- Backtests use completed candles, sequential targets, conservative stop-first handling
  when stop and target are touched in the same candle, and no future candle data.
- Spread, slippage, commissions, and broker execution differences are not included unless
  the user adjusts the optional estimated cost input.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_TITLE = "AFG GOLD ULTIMATE | PRICE ACTION + SMC"
API_URL = "https://api.twelvedata.com/time_series"
SYMBOL = "XAU/USD"
INTERVALS = {"15m": "15min", "1h": "1h", "4h": "4h"}
MAX_OUTPUT = 5000

st.set_page_config(page_title=APP_TITLE, page_icon="🟡", layout="wide")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data(ttl=240, show_spinner=False)
def fetch_candles(symbol: str, interval: str, outputsize: int, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": min(int(outputsize), MAX_OUTPUT),
        "timezone": "UTC",
        "format": "JSON",
        "apikey": api_key,
    }
    response = requests.get(API_URL, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise RuntimeError(payload.get("message", "No candle data returned by Twelve Data"))
    df = pd.DataFrame(payload["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif col != "volume":
            raise RuntimeError(f"Missing required column: {col}")
    if "volume" not in df:
        df["volume"] = np.nan
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"])
    df = df.sort_values("datetime").drop_duplicates("datetime").set_index("datetime")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    c = x["close"]
    x["ema20"] = c.ewm(span=20, adjust=False).mean()
    x["ema50"] = c.ewm(span=50, adjust=False).mean()
    x["ema200"] = c.ewm(span=200, adjust=False).mean()
    prev = c.shift(1)
    tr = pd.concat([
        x["high"] - x["low"],
        (x["high"] - prev).abs(),
        (x["low"] - prev).abs()
    ], axis=1).max(axis=1)
    x["atr"] = tr.rolling(14, min_periods=5).mean()
    x["body"] = (x["close"] - x["open"]).abs()
    x["range"] = (x["high"] - x["low"]).replace(0, np.nan)
    x["body_ratio"] = x["body"] / x["range"]
    x["upper_wick"] = x["high"] - x[["open", "close"]].max(axis=1)
    x["lower_wick"] = x[["open", "close"]].min(axis=1) - x["low"]
    x["close_location"] = (x["close"] - x["low"]) / x["range"]
    x["vol_sma"] = x["volume"].rolling(20, min_periods=5).mean()
    x["range_sma"] = x["range"].rolling(20, min_periods=5).mean()
    x["return"] = c.pct_change()
    return x


def confirmed_pivots(df: pd.DataFrame, left: int = 3, right: int = 3) -> Tuple[pd.Series, pd.Series]:
    """A pivot is only visible after `right` completed candles, preventing lookahead."""
    highs = pd.Series(np.nan, index=df.index, dtype=float)
    lows = pd.Series(np.nan, index=df.index, dtype=float)
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    for i in range(left, len(df) - right):
        if h[i] >= np.max(h[i-left:i+right+1]) and np.sum(h[i] == h[i-left:i+right+1]) == 1:
            highs.iloc[i + right] = h[i]
        if l[i] <= np.min(l[i-left:i+right+1]) and np.sum(l[i] == l[i-left:i+right+1]) == 1:
            lows.iloc[i + right] = l[i]
    return highs, lows


def structure_data(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    x = df.copy()
    ph, pl = confirmed_pivots(x, left, right)
    x["pivot_high"], x["pivot_low"] = ph, pl
    x["last_swing_high"] = ph.ffill()
    x["last_swing_low"] = pl.ffill()
    prev_ph = ph.dropna()
    prev_pl = pl.dropna()
    x["swing_high_type"] = ""
    x["swing_low_type"] = ""
    last = None
    for idx, val in prev_ph.items():
        typ = "SH"
        if last is not None:
            typ = "HH" if val > last else ("LH" if val < last else "EQH")
        x.loc[idx, "swing_high_type"] = typ
        last = val
    last = None
    for idx, val in prev_pl.items():
        typ = "SL"
        if last is not None:
            typ = "HL" if val > last else ("LL" if val < last else "EQL")
        x.loc[idx, "swing_low_type"] = typ
        last = val
    x["bull_bos"] = (x["close"] > x["last_swing_high"].shift(1)) & x["last_swing_high"].shift(1).notna()
    x["bear_bos"] = (x["close"] < x["last_swing_low"].shift(1)) & x["last_swing_low"].shift(1).notna()
    return x


def candle_patterns(row: pd.Series, prev: Optional[pd.Series]) -> Dict[str, bool]:
    o, h, l, c = [float(row[k]) for k in ["open", "high", "low", "close"]]
    rng = max(h - l, 1e-12)
    body = abs(c - o)
    uw, lw = h - max(o, c), min(o, c) - l
    bull_engulf = bear_engulf = False
    if prev is not None:
        po, pc = float(prev["open"]), float(prev["close"])
        bull_engulf = c > o and pc < po and o <= pc and c >= po
        bear_engulf = c < o and pc > po and o >= pc and c <= po
    return {
        "bull_pin": lw >= body * 2.0 and uw <= max(body, rng * 0.25) and c > l + rng * 0.55,
        "bear_pin": uw >= body * 2.0 and lw <= max(body, rng * 0.25) and c < l + rng * 0.45,
        "bull_engulf": bull_engulf,
        "bear_engulf": bear_engulf,
        "inside_bar": prev is not None and h < float(prev["high"]) and l > float(prev["low"]),
        "outside_bar": prev is not None and h > float(prev["high"]) and l < float(prev["low"]),
        "bull_marubozu": c > o and body / rng > 0.85,
        "bear_marubozu": c < o and body / rng > 0.85,
        "doji": body / rng < 0.10,
        "hammer": lw >= body * 2 and uw <= body * 0.7 and c > o,
        "shooting_star": uw >= body * 2 and lw <= body * 0.7 and c < o,
    }


def htf_bias(h1: pd.DataFrame, h4: pd.DataFrame) -> str:
    if len(h1) < 60 or len(h4) < 30:
        return "NEUTRAL"
    a, b = add_indicators(h1).iloc[-1], add_indicators(h4).iloc[-1]
    bull = a.close > a.ema50 and a.ema20 > a.ema50 and b.close > b.ema50
    bear = a.close < a.ema50 and a.ema20 < a.ema50 and b.close < b.ema50
    return "BULLISH" if bull else ("BEARISH" if bear else "NEUTRAL")


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------
def safe_float(v, default=np.nan):
    try:
        return float(v)
    except Exception:
        return default


def market_regime(x: pd.DataFrame) -> str:
    if len(x) < 30:
        return "INSUFFICIENT DATA"
    z = x.iloc[-1]
    atr_pct = z.atr / z.close if z.close else 0
    ema_spread = abs(z.ema20 - z.ema50) / z.close
    if atr_pct > 0.006:
        return "HIGH VOLATILITY"
    if ema_spread < 0.0008 and abs(z.close - z.ema50) / z.close < 0.0015:
        return "RANGE / CHOP"
    return "TREND / TRANSITION"


def nearest_levels(x: pd.DataFrame, price: float, lookback: int = 120) -> Tuple[float, float]:
    z = x.tail(lookback)
    ph, pl = confirmed_pivots(z, 3, 3)
    highs = ph.dropna()
    lows = pl.dropna()
    above = highs[highs > price]
    below = lows[lows < price]
    resistance = float(above.iloc[-1]) if len(above) else float(z.high.max())
    support = float(below.iloc[-1]) if len(below) else float(z.low.min())
    return support, resistance


def score_label(score: int) -> str:
    if score >= 85:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    return "C"


def empty_signal(engine: str, reason: str) -> Dict:
    return {"engine": engine, "direction": "NO SIGNAL", "score": 0, "grade": "-", "reason": reason}


# ---------------------------------------------------------------------------
# Price Action engine - broad rule-based implementation
# ---------------------------------------------------------------------------
def price_action_engine(df15: pd.DataFrame, df1h: pd.DataFrame, df4h: pd.DataFrame,
                        min_score: int = 62, min_rr: float = 1.5) -> Dict:
    if len(df15) < 100 or len(df1h) < 60:
        return empty_signal("PRICE ACTION", "برای تحلیل معتبر، داده کافی نیست.")
    x = structure_data(add_indicators(df15))
    h1 = structure_data(add_indicators(df1h))
    h4 = add_indicators(df4h)
    r = x.iloc[-1]
    p = x.iloc[-2]
    price, atr = float(r.close), safe_float(r.atr)
    if not np.isfinite(atr) or atr <= 0:
        return empty_signal("PRICE ACTION", "ATR قابل محاسبه نیست.")
    bias = htf_bias(df1h, df4h)
    regime = market_regime(x)
    patterns = candle_patterns(r, p)
    recent = x.iloc[-25:-1]
    prev_high, prev_low = float(recent.high.max()), float(recent.low.min())
    support, resistance = nearest_levels(x.iloc[:-1], price)
    trend_bull = r.ema20 > r.ema50 and r.close > r.ema50
    trend_bear = r.ema20 < r.ema50 and r.close < r.ema50
    bull_bos = bool(r.bull_bos)
    bear_bos = bool(r.bear_bos)
    breakout_up = price > prev_high and r.close_location > 0.65
    breakout_dn = price < prev_low and r.close_location < 0.35
    false_break_up = r.high > prev_high and price < prev_high
    false_break_dn = r.low < prev_low and price > prev_low
    near_support = abs(price - support) <= atr * 0.65
    near_resistance = abs(price - resistance) <= atr * 0.65
    pullback_bull = trend_bull and r.low <= r.ema20 + atr * 0.15 and price > r.ema20
    pullback_bear = trend_bear and r.high >= r.ema20 - atr * 0.15 and price < r.ema20

    bull = 0
    bear = 0
    bull_reasons, bear_reasons = [], []
    def add(cond, pts, side, reason):
        nonlocal bull, bear
        if cond:
            if side == "BUY":
                bull += pts
                bull_reasons.append(reason)
            else:
                bear += pts
                bear_reasons.append(reason)

    add(bias == "BULLISH", 12, "BUY", "هم‌جهتی تایم‌فریم ۱ساعته و ۴ساعته")
    add(bias == "BEARISH", 12, "SELL", "هم‌جهتی تایم‌فریم ۱ساعته و ۴ساعته")
    add(trend_bull, 10, "BUY", "روند کوتاه‌مدت صعودی EMA20/50")
    add(trend_bear, 10, "SELL", "روند کوتاه‌مدت نزولی EMA20/50")
    add(bull_bos, 12, "BUY", "شکست ساختار صعودی BOS")
    add(bear_bos, 12, "SELL", "شکست ساختار نزولی BOS")
    add(patterns["bull_engulf"], 9, "BUY", "الگوی Bullish Engulfing")
    add(patterns["bear_engulf"], 9, "SELL", "الگوی Bearish Engulfing")
    add(patterns["bull_pin"] or patterns["hammer"], 7, "BUY", "واکنش کندلی صعودی Pin/Hammer")
    add(patterns["bear_pin"] or patterns["shooting_star"], 7, "SELL", "واکنش کندلی نزولی Pin/Shooting Star")
    add(pullback_bull, 8, "BUY", "پولبک به EMA20 در روند صعودی")
    add(pullback_bear, 8, "SELL", "پولبک به EMA20 در روند نزولی")
    add(false_break_dn, 10, "BUY", "شکست جعلی کف و بازگشت قیمت")
    add(false_break_up, 10, "SELL", "شکست جعلی سقف و بازگشت قیمت")
    add(breakout_up, 8, "BUY", "شکست محدوده ۲۴ کندل با کلوز قوی")
    add(breakout_dn, 8, "SELL", "شکست محدوده ۲۴ کندل با کلوز قوی")
    add(near_support, 6, "BUY", "نزدیکی به حمایت ساختاری")
    add(near_resistance, 6, "SELL", "نزدیکی به مقاومت ساختاری")
    add(r.close_location > 0.75 and r.body_ratio > 0.55, 5, "BUY", "کندل صعودی با بدنه و کلوز قوی")
    add(r.close_location < 0.25 and r.body_ratio > 0.55, 5, "SELL", "کندل نزولی با بدنه و کلوز قوی")
    add(regime == "RANGE / CHOP", -8, "BUY", "کاهش امتیاز در بازار خنثی")
    add(regime == "RANGE / CHOP", -8, "SELL", "کاهش امتیاز در بازار خنثی")

    direction = "BUY" if bull > bear else ("SELL" if bear > bull else "NO SIGNAL")
    score = int(min(100, max(0, bull if direction == "BUY" else bear)))
    reasons = bull_reasons if direction == "BUY" else bear_reasons
    if direction == "NO SIGNAL" or score < min_score:
        return empty_signal("PRICE ACTION", f"شرایط کافی نیست؛ امتیاز خرید {bull}، فروش {bear}، رژیم {regime}.")
    entry = price
    if direction == "BUY":
        structural_sl = min(float(r.low), support) - atr * 0.25
        sl = min(structural_sl, entry - atr * 1.15)
        risk = entry - sl
        tp1, tp2, tp3 = entry + risk, entry + risk * 1.5, entry + risk * 2.0
    else:
        structural_sl = max(float(r.high), resistance) + atr * 0.25
        sl = max(structural_sl, entry + atr * 1.15)
        risk = sl - entry
        tp1, tp2, tp3 = entry - risk, entry - risk * 1.5, entry - risk * 2.0
    rr = abs(tp2 - entry) / max(risk, 1e-9)
    if rr < min_rr:
        return empty_signal("PRICE ACTION", f"نسبت سود به زیان کافی نیست ({rr:.2f}R).")
    return {
        "engine": "PRICE ACTION", "direction": direction, "score": score,
        "grade": score_label(score), "entry": entry, "entry_low": entry - atr*0.12,
        "entry_high": entry + atr*0.12, "sl": sl, "tp1": tp1, "tp2": tp2,
        "tp3": tp3, "rr": rr, "atr": atr, "bias": bias, "regime": regime,
        "reasons": reasons, "time": x.index[-1]
    }


# ---------------------------------------------------------------------------
# Smart Money Concepts engine - broad OHLC-based implementation
# ---------------------------------------------------------------------------
def smc_engine(df15: pd.DataFrame, df1h: pd.DataFrame, df4h: pd.DataFrame,
               min_score: int = 62, min_rr: float = 1.5) -> Dict:
    if len(df15) < 120 or len(df1h) < 60:
        return empty_signal("SMART MONEY CONCEPTS", "برای تحلیل معتبر، داده کافی نیست.")
    x = structure_data(add_indicators(df15))
    r, p = x.iloc[-1], x.iloc[-2]
    price, atr = float(r.close), safe_float(r.atr)
    if not np.isfinite(atr) or atr <= 0:
        return empty_signal("SMART MONEY CONCEPTS", "ATR قابل محاسبه نیست.")
    bias = htf_bias(df1h, df4h)
    hist = x.iloc[:-1]
    # Liquidity pools from confirmed pivot clusters, not arbitrary equal-close comparisons.
    ph, pl = confirmed_pivots(hist.tail(180), 3, 3)
    highs, lows = ph.dropna().tail(30), pl.dropna().tail(30)
    tol = max(atr * 0.12, price * 0.00025)
    eqh = any(abs(float(a)-float(b)) <= tol for i, a in enumerate(highs.values) for b in highs.values[i+1:])
    eql = any(abs(float(a)-float(b)) <= tol for i, a in enumerate(lows.values) for b in lows.values[i+1:])
    prior_high = float(hist.high.tail(20).max())
    prior_low = float(hist.low.tail(20).min())
    sweep_high = float(r.high) > prior_high and price < prior_high
    sweep_low = float(r.low) < prior_low and price > prior_low
    displacement_bull = r.close > r.open and r.body > atr * 0.75 and r.close_location > 0.75
    displacement_bear = r.close < r.open and r.body > atr * 0.75 and r.close_location < 0.25
    # FVG: three-candle imbalance, current candle is the third candle.
    fvg_bull = float(x.low.iloc[-1]) > float(x.high.iloc[-3])
    fvg_bear = float(x.high.iloc[-1]) < float(x.low.iloc[-3])
    bull_fvg_low, bull_fvg_high = (float(x.high.iloc[-3]), float(x.low.iloc[-1])) if fvg_bull else (np.nan, np.nan)
    bear_fvg_low, bear_fvg_high = (float(x.high.iloc[-1]), float(x.low.iloc[-3])) if fvg_bear else (np.nan, np.nan)
    # Premium/discount based on recent completed dealing range.
    dealing_high = float(hist.high.tail(80).max())
    dealing_low = float(hist.low.tail(80).min())
    equilibrium = (dealing_high + dealing_low) / 2
    discount = price < equilibrium
    premium = price > equilibrium
    # Order-block proxy: last opposite candle before a strong displacement + structure break.
    recent = x.iloc[-8:-1]
    bull_mss = bool(r.close > r.last_swing_high) if pd.notna(r.last_swing_high) else False
    bear_mss = bool(r.close < r.last_swing_low) if pd.notna(r.last_swing_low) else False
    bull_ob = False
    bear_ob = False
    ob_low = ob_high = np.nan
    for _, candle in recent.iloc[::-1].iterrows():
        if displacement_bull and candle.close < candle.open:
            bull_ob = True
            ob_low, ob_high = float(candle.low), float(candle.high)
            break
    for _, candle in recent.iloc[::-1].iterrows():
        if displacement_bear and candle.close > candle.open:
            bear_ob = True
            ob_low, ob_high = float(candle.low), float(candle.high)
            break
    # Breaker / mitigation are treated as retests of previously identified OB zones.
    bull_ob_retest = bull_ob and ob_low <= price <= ob_high
    bear_ob_retest = bear_ob and ob_low <= price <= ob_high
    # Internal/external liquidity proxy: local 20-bar pools vs 80-bar extremes.
    ext_high, ext_low = float(hist.high.tail(80).max()), float(hist.low.tail(80).min())
    int_high, int_low = prior_high, prior_low
    internal_sweep_up = float(r.high) > int_high and price < int_high
    internal_sweep_dn = float(r.low) < int_low and price > int_low
    # Three-candle imbalance fill / inversion proxy.
    inv_fvg_bull = fvg_bear and price > float(x.high.iloc[-2])
    inv_fvg_bear = fvg_bull and price < float(x.low.iloc[-2])
    # Range position and volatility regime.
    regime = market_regime(x)
    bull = bear = 0
    br, sr = [], []
    def add(cond, pts, side, why):
        nonlocal bull, bear
        if cond:
            if side == "BUY":
                bull += pts; br.append(why)
            else:
                bear += pts; sr.append(why)
    add(bias == "BULLISH", 10, "BUY", "جهت تایم‌فریم بالاتر صعودی")
    add(bias == "BEARISH", 10, "SELL", "جهت تایم‌فریم بالاتر نزولی")
    add(sweep_low, 15, "BUY", "جمع‌آوری نقدینگی SSL و بازگشت بالای سطح")
    add(sweep_high, 15, "SELL", "جمع‌آوری نقدینگی BSL و بازگشت زیر سطح")
    add(eql and sweep_low, 7, "BUY", "EQL و برداشت نقدینگی کف")
    add(eqh and sweep_high, 7, "SELL", "EQH و برداشت نقدینگی سقف")
    add(displacement_bull, 10, "BUY", "Displacement صعودی")
    add(displacement_bear, 10, "SELL", "Displacement نزولی")
    add(bull_mss, 10, "BUY", "شکست ساختار/MSS صعودی")
    add(bear_mss, 10, "SELL", "شکست ساختار/MSS نزولی")
    add(fvg_bull, 7, "BUY", "تشکیل Bullish FVG")
    add(fvg_bear, 7, "SELL", "تشکیل Bearish FVG")
    add(bull_ob, 8, "BUY", "Order Block صعودی شناسایی‌شده")
    add(bear_ob, 8, "SELL", "Order Block نزولی شناسایی‌شده")
    add(bull_ob_retest, 5, "BUY", "بازگشت قیمت به محدوده OB صعودی")
    add(bear_ob_retest, 5, "SELL", "بازگشت قیمت به محدوده OB نزولی")
    add(discount, 5, "BUY", "قیمت در Discount محدوده معاملاتی")
    add(premium, 5, "SELL", "قیمت در Premium محدوده معاملاتی")
    add(inv_fvg_bull, 4, "BUY", "نشانه Inversion FVG صعودی")
    add(inv_fvg_bear, 4, "SELL", "نشانه Inversion FVG نزولی")
    add(regime == "RANGE / CHOP", -8, "BUY", "کاهش امتیاز در بازار خنثی")
    add(regime == "RANGE / CHOP", -8, "SELL", "کاهش امتیاز در بازار خنثی")

    direction = "BUY" if bull > bear else ("SELL" if bear > bull else "NO SIGNAL")
    score = int(min(100, max(0, bull if direction == "BUY" else bear)))
    reasons = br if direction == "BUY" else sr
    if direction == "NO SIGNAL" or score < min_score:
        return empty_signal("SMART MONEY CONCEPTS", f"شرایط کافی نیست؛ امتیاز خرید {bull}، فروش {bear}، رژیم {regime}.")
    entry = price
    if direction == "BUY":
        candidates = [float(r.low), ob_low if bull_ob else np.nan, dealing_low]
        structural = min([v for v in candidates if np.isfinite(v)])
        sl = min(structural - atr*0.15, entry - atr*1.05)
        risk = entry - sl
        tp1, tp2, tp3 = entry + risk, entry + risk*1.5, entry + risk*2
    else:
        candidates = [float(r.high), ob_high if bear_ob else np.nan, dealing_high]
        structural = max([v for v in candidates if np.isfinite(v)])
        sl = max(structural + atr*0.15, entry + atr*1.05)
        risk = sl - entry
        tp1, tp2, tp3 = entry - risk, entry - risk*1.5, entry - risk*2
    rr = abs(tp2-entry)/max(risk, 1e-9)
    if rr < min_rr:
        return empty_signal("SMART MONEY CONCEPTS", f"نسبت سود به زیان کافی نیست ({rr:.2f}R).")
    return {
        "engine": "SMART MONEY CONCEPTS", "direction": direction, "score": score,
        "grade": score_label(score), "entry": entry, "entry_low": entry-atr*0.12,
        "entry_high": entry+atr*0.12, "sl": sl, "tp1": tp1, "tp2": tp2,
        "tp3": tp3, "rr": rr, "atr": atr, "bias": bias, "regime": regime,
        "reasons": reasons, "time": x.index[-1],
        "liquidity": {"EQH": bool(eqh), "EQL": bool(eql), "BSL_sweep": bool(sweep_high),
                      "SSL_sweep": bool(sweep_low), "internal_high": int_high,
                      "internal_low": int_low, "external_high": ext_high, "external_low": ext_low,
                      "equilibrium": equilibrium}
    }


# ---------------------------------------------------------------------------
# Honest event-driven backtest
# ---------------------------------------------------------------------------
def backtest_engine(df15: pd.DataFrame, df1h: pd.DataFrame, df4h: pd.DataFrame,
                    engine_fn, min_score: int, min_rr: float, cost_points: float = 0.0,
                    max_trades: int = 400) -> Tuple[pd.DataFrame, Dict]:
    """
    Signal at close of bar i; entry at next bar open.
    TP progression is sequential. If stop and next required target are both touched
    in a candle, stop is assumed first. No same-bar entry/exit.
    """
    base = add_indicators(df15)
    rows = []
    start = max(180, len(base) - 2200)
    i = start
    while i < len(base) - 2 and len(rows) < max_trades:
        hist15 = base.iloc[:i+1]
        t = hist15.index[-1]
        hist1 = df1h[df1h.index <= t]
        hist4 = df4h[df4h.index <= t]
        if len(hist1) < 60 or len(hist4) < 30:
            i += 1
            continue
        sig = engine_fn(hist15, hist1, hist4, min_score, min_rr)
        if sig.get("direction") not in ("BUY", "SELL"):
            i += 1
            continue
        side = sig["direction"]
        entry_i = i + 1
        entry = float(base.iloc[entry_i].open)
        sl = float(sig["sl"])
        # Preserve risk geometry from the generated close-based signal, re-anchor targets
        # to actual next open using the original stop distance.
        risk = abs(entry - sl)
        if risk <= 0 or not np.isfinite(risk):
            i += 1
            continue
        sign = 1 if side == "BUY" else -1
        tp1, tp2, tp3 = entry + sign*risk, entry + sign*risk*1.5, entry + sign*risk*2
        stage = 0
        exit_r = 0.0
        outcome = "OPEN"
        exit_i = min(entry_i + 48, len(base)-1)
        for j in range(entry_i, exit_i+1):
            bar = base.iloc[j]
            lo, hi = float(bar.low), float(bar.high)
            stop_hit = (lo <= sl) if side == "BUY" else (hi >= sl)
            target = [tp1, tp2, tp3][stage] if stage < 3 else None
            target_hit = (hi >= target) if side == "BUY" else (lo <= target)
            if stop_hit and target_hit:
                outcome, exit_r = "STOP (conservative same-bar)", -1.0
                break
            if stop_hit:
                outcome, exit_r = "STOP", -1.0
                break
            if target_hit:
                stage += 1
                if stage == 3:
                    outcome, exit_r = "TP3", 2.0
                    break
                continue
            if j == exit_i:
                close = float(bar.close)
                exit_r = sign * (close-entry) / risk
                outcome = "TIME EXIT"
        exit_r -= max(0.0, cost_points) / risk
        rows.append({
            "Signal time UTC": t, "Side": side, "Entry": entry, "Stop": sl,
            "TP1": tp1, "TP2": tp2, "TP3": tp3, "Score": sig["score"],
            "Outcome": outcome, "Targets reached": stage, "R multiple": exit_r,
            "Exit time UTC": base.index[min(j, len(base)-1)]
        })
        # Avoid overlapping positions: resume after exit bar.
        i = max(i + 1, min(j + 1, len(base)-2))
    trades = pd.DataFrame(rows)
    if trades.empty:
        return trades, {"trades": 0}
    rvals = trades["R multiple"].astype(float)
    wins = rvals[rvals > 0]
    losses = rvals[rvals < 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())
    equity = rvals.cumsum()
    peak = equity.cummax()
    dd = equity - peak
    stats = {
        "trades": int(len(trades)),
        "TP1 rate": float((trades["Targets reached"] >= 1).mean() * 100),
        "TP2 rate": float((trades["Targets reached"] >= 2).mean() * 100),
        "TP3 rate": float((trades["Targets reached"] >= 3).mean() * 100),
        "positive trade rate": float((rvals > 0).mean() * 100),
        "expectancy R": float(rvals.mean()),
        "profit factor": float(gross_profit / gross_loss) if gross_loss > 0 else np.inf,
        "max drawdown R": float(dd.min()),
        "net R": float(rvals.sum()),
    }
    return trades, stats


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def fmt_price(v):
    return f"{float(v):,.2f}" if v is not None and np.isfinite(float(v)) else "—"


def show_signal(sig: Dict, color: str):
    st.subheader(sig.get("engine", "ENGINE"))
    if sig.get("direction") not in ("BUY", "SELL"):
        st.info(sig.get("reason", "No valid setup at this time."))
        return
    st.markdown(f"### {'🟢 BUY' if sig['direction']=='BUY' else '🔴 SELL'}  |  Grade {sig['grade']}  |  Score {sig['score']}/100")
    st.caption("امتیاز، امتیاز هم‌گرایی قواعد است و احتمال برد یا درصد موفقیت نیست.")
    a, b, c = st.columns(3)
    a.metric("Entry", fmt_price(sig["entry"]))
    b.metric("Stop Loss", fmt_price(sig["sl"]))
    c.metric("Risk : Reward تا TP2", f"1 : {sig['rr']:.2f}")
    d, e, f = st.columns(3)
    d.metric("TP1 (1R)", fmt_price(sig["tp1"]))
    e.metric("TP2 (1.5R)", fmt_price(sig["tp2"]))
    f.metric("TP3 (2R)", fmt_price(sig["tp3"]))
    st.write(f"**محدوده ورود:** {fmt_price(sig['entry_low'])} تا {fmt_price(sig['entry_high'])}")
    st.write(f"**جهت تایم‌فریم بالاتر:** {sig['bias']}  |  **وضعیت بازار:** {sig['regime']}")
    if sig.get("reasons"):
        st.write("**دلایل سیگنال:**")
        for reason in sig["reasons"]:
            st.write(f"- {reason}")
    st.caption(f"آخرین کندل تکمیل‌شده (UTC): {sig['time']}")


def run_backtest_ui(title: str, engine_fn, d15, d1, d4, min_score, min_rr, cost):
    st.markdown(f"#### بک‌تست مستقل {title}")
    if st.button(f"اجرای بک‌تست {title}", key=f"bt_{title}"):
        with st.spinner("در حال اجرای بک‌تست؛ ممکن است کمی زمان ببرد..."):
            trades, stats = backtest_engine(d15, d1, d4, engine_fn, min_score, min_rr, cost)
        if trades.empty:
            st.warning("در بازه موجود معامله واجد شرایط پیدا نشد.")
            return
        cols = st.columns(4)
        cols[0].metric("تعداد معاملات", stats["trades"])
        cols[1].metric("TP1 hit rate", f'{stats["TP1 rate"]:.1f}%')
        cols[2].metric("TP2 hit rate", f'{stats["TP2 rate"]:.1f}%')
        cols[3].metric("TP3 hit rate", f'{stats["TP3 rate"]:.1f}%')
        cols = st.columns(4)
        cols[0].metric("Expectancy", f'{stats["expectancy R"]:.2f}R')
        pf = stats["profit factor"]
        cols[1].metric("Profit Factor", "∞" if np.isinf(pf) else f"{pf:.2f}")
        cols[2].metric("Max Drawdown", f'{stats["max drawdown R"]:.2f}R')
        cols[3].metric("Net Result", f'{stats["net R"]:.2f}R')
        st.caption("درصد TPها از تمام معاملات سیگنال‌دار محاسبه شده است؛ نه فقط معاملات برنده.")
        st.dataframe(trades.tail(250), use_container_width=True, hide_index=True)
        st.download_button(
            f"دانلود CSV بک‌تست {title}",
            trades.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{title.lower().replace(' ', '_')}_backtest.csv",
            mime="text/csv",
            key=f"dl_{title}"
        )


def main():
    st.title("🟡 AFG GOLD ULTIMATE")
    st.subheader("دو موتور مستقل و جامع: Price Action + Smart Money Concepts")
    st.caption("XAU/USD | تایم‌فریم ورود 15m | فیلترهای 1H و 4H | تازه‌سازی 5 دقیقه‌ای")
    with st.sidebar:
        st.header("تنظیمات")
        api_key = st.text_input("Twelve Data API Key", type="password",
                                value=st.secrets.get("TWELVE_DATA_API_KEY", ""))
        min_score = st.slider("حداقل امتیاز هم‌گرایی", 40, 90, 62, 1)
        min_rr = st.slider("حداقل نسبت سود به زیان", 1.0, 3.0, 1.5, 0.1)
        outputsize = st.select_slider("تعداد کندل", options=[500, 1000, 2000, 3000, 5000], value=2000)
        cost = st.number_input("هزینه تخمینی معامله بر حسب واحد قیمت طلا", min_value=0.0,
                               max_value=100.0, value=0.0, step=0.05,
                               help="برای مدل‌سازی تقریبی spread/slippage؛ مقدار واقعی را از بروکر خود بگیرید.")
        auto = st.checkbox("تازه‌سازی خودکار هر ۵ دقیقه", value=True)
        st.caption("کلید API را فقط در Streamlit Secrets نگهداری کنید؛ آن را در فایل یا چت قرار ندهید.")
    if auto:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=300000, key="gold_refresh")
        except Exception:
            st.caption("برای تازه‌سازی خودکار، بسته streamlit-autorefresh را نصب کنید.")
    if not api_key:
        st.warning("کلید Twelve Data را در Streamlit Secrets با نام TWELVE_DATA_API_KEY وارد کنید.")
        st.code('[secrets]\nTWELVE_DATA_API_KEY = "YOUR_KEY"', language="toml")
        return
    try:
        with st.spinner("دریافت داده‌های طلا از Twelve Data..."):
            d15 = fetch_candles(SYMBOL, INTERVALS["15m"], outputsize, api_key)
            d1 = fetch_candles(SYMBOL, INTERVALS["1h"], min(outputsize, 2000), api_key)
            d4 = fetch_candles(SYMBOL, INTERVALS["4h"], min(outputsize, 1000), api_key)
    except Exception as exc:
        st.error(f"خطا در دریافت داده: {exc}")
        return
    if len(d15) < 200 or len(d1) < 60 or len(d4) < 30:
        st.error("داده کافی از سرویس دریافت نشد.")
        return
    # Do not analyze an in-progress 15m candle. Provider timestamps are UTC.
    now = pd.Timestamp.now(tz="UTC")
    d15 = d15[d15.index + pd.Timedelta(minutes=15) <= now]
    d1 = d1[d1.index + pd.Timedelta(hours=1) <= now]
    d4 = d4[d4.index + pd.Timedelta(hours=4) <= now]
    if len(d15) < 150 or len(d1) < 60 or len(d4) < 30:
        st.warning("پس از حذف کندل‌های ناتمام، داده کافی باقی نماند.")
        return
    d15, d1, d4 = add_indicators(d15), add_indicators(d1), add_indicators(d4)
    st.write(f"**قیمت آخرین کلوز 15m:** {fmt_price(d15.close.iloc[-1])}  |  **زمان UTC:** {d15.index[-1]}")
    pa = price_action_engine(d15, d1, d4, min_score, min_rr)
    smc = smc_engine(d15, d1, d4, min_score, min_rr)
    left, right = st.columns(2)
    with left:
        show_signal(pa, "blue")
    with right:
        show_signal(smc, "violet")
    st.divider()
    st.subheader("مقایسه وضعیت دو موتور")
    comp = pd.DataFrame([
        {"موتور": "Price Action", "جهت": pa.get("direction"), "امتیاز": pa.get("score", 0),
         "درجه": pa.get("grade", "-"), "وضعیت": pa.get("reason", "سیگنال معتبر")},
        {"موتور": "SMC", "جهت": smc.get("direction"), "امتیاز": smc.get("score", 0),
         "درجه": smc.get("grade", "-"), "وضعیت": smc.get("reason", "سیگنال معتبر")},
    ])
    st.dataframe(comp, use_container_width=True, hide_index=True)
    st.divider()
    st.header("بک‌تست تاریخی مستقل")
    st.warning("بک‌تست شبیه‌سازی OHLC است؛ اسپرد، لغزش قیمت، خبرها، اجرای بروکر و تفاوت قیمت CFD ممکن است نتیجه واقعی را تغییر دهد. نتایج گذشته تضمین آینده نیستند.")
    run_backtest_ui("Price Action", price_action_engine, d15, d1, d4, min_score, min_rr, cost)
    run_backtest_ui("SMC", smc_engine, d15, d1, d4, min_score, min_rr, cost)
    with st.expander("محدوده پوشش و محدودیت‌های صادقانه"):
        st.markdown("""
**Price Action:** ساختار HH/HL/LH/LL، پیوت‌های تأییدشده، BOS، روند EMA، پولبک، شکست و شکست جعلی،
حمایت/مقاومت پیوتی، کندل‌های engulfing/pin/hammer/shooting-star/inside/outside/marubozu/doji،
قدرت کندل و رژیم بازار.

**SMC:** BSL/SSL sweep، EQH/EQL مبتنی بر خوشه پیوت، BOS/MSS proxy، displacement،
FVG سه‌کندلی، inversion-FVG proxy، OB مبتنی بر آخرین کندل مخالف پیش از displacement،
premium/discount، dealing range و تفکیک تقریبی نقدینگی داخلی/خارجی.

این‌ها یک پیاده‌سازی گسترده و قابل‌آزمایش از قواعد مشخص هستند؛ نه ادعای کدنویسی تمام برداشت‌های شخصی و نسخه‌های متنوعی که در تمام مکاتب جهان وجود دارد.
OHLC به‌تنهایی برای اثبات سفارش‌های نهادی، جریان سفارش واقعی، footprint، DOM، حجم واقعی بازار جهانی طلا،
Wyckoff کامل، پروفایل حجمی دقیق، یا تشخیص قطعی breaker/mitigation/propulsion کافی نیست.
""")
    st.caption("AFG GOLD ULTIMATE | تصمیم نهایی معامله با کاربر است.")


if __name__ == "__main__":
    main()
