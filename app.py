# -*- coding: utf-8 -*-
"""
AFG GOLD AI TREND PRO V16.1
A trend-following, rule-based XAU/USD signal dashboard inspired by the
visible behavior of the reference screenshot. It is NOT a reconstruction
of another trader's hidden source code and does not promise profitability.

Install:
    pip install streamlit pandas numpy requests

Run:
    streamlit run AFG_GOLD_AI_TREND_PRO_V16.py

Set TWELVE_DATA_API_KEY in Streamlit secrets, or enter it in the sidebar.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_TITLE = "AFG GOLD AI TREND PRO V16.1"
API_URL = "https://api.twelvedata.com/time_series"
SYMBOL = "XAU/USD"
TRACK_FILE = Path("afg_v16_trade_log.json")
INTERVALS = {"15m": "15min", "1h": "1h", "4h": "4h"}

st.set_page_config(page_title=APP_TITLE, page_icon="🟡", layout="wide")


# ------------------------------ Data ---------------------------------------
@st.cache_data(ttl=180, show_spinner=False)
def fetch_candles(symbol: str, interval: str, outputsize: int, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": symbol, "interval": interval, "outputsize": outputsize,
        "timezone": "UTC", "format": "JSON", "apikey": api_key,
    }
    response = requests.get(API_URL, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise RuntimeError(payload.get("message", "No candle data returned"))
    df = pd.DataFrame(payload["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = np.nan
    df = (df.dropna(subset=["datetime", "open", "high", "low", "close"])
            .sort_values("datetime").drop_duplicates("datetime")
            .set_index("datetime"))
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def closed_candles(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC")
    return df[df.index + pd.Timedelta(minutes=minutes) <= now].copy()


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    c = x.close
    for n in (9, 20, 50, 200):
        x[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
    prev_close = c.shift()
    tr = pd.concat([
        x.high - x.low, (x.high - prev_close).abs(),
        (x.low - prev_close).abs()
    ], axis=1).max(axis=1)
    x["atr"] = tr.rolling(14, min_periods=5).mean()
    x["range"] = (x.high - x.low).replace(0, np.nan)
    x["body"] = (x.close - x.open).abs()
    x["body_ratio"] = x.body / x["range"]
    x["close_pos"] = (x.close - x.low) / x["range"]
    x["upper_wick"] = x.high - x[["open", "close"]].max(axis=1)
    x["lower_wick"] = x[["open", "close"]].min(axis=1) - x.low
    x["vol_sma"] = x.volume.rolling(20, min_periods=5).mean()
    return x


# ------------------------------ Sessions -----------------------------------
def session_info(now_utc: datetime | None = None) -> tuple[str, str]:
    now_utc = now_utc or datetime.now(timezone.utc)
    london = now_utc.astimezone(ZoneInfo("Europe/London"))
    new_york = now_utc.astimezone(ZoneInfo("America/New_York"))
    # Broad local market windows; overlap is identified only when both are active.
    london_open = 7 <= london.hour < 16
    ny_open = 8 <= new_york.hour < 17
    if london_open and ny_open:
        return "LONDON / NY OVERLAP", "HIGH ACTIVITY WINDOW"
    if london_open:
        return "LONDON", "ACTIVE SESSION"
    if ny_open:
        return "NEW YORK", "ACTIVE SESSION"
    return "ASIAN / OFF-HOURS", "LOWER SESSION ACTIVITY"


# ---------------------- Dedicated Rule-Based Trend Engine ------------------
def rule_based_trend_engine(x: pd.DataFrame, h1: pd.DataFrame, h4: pd.DataFrame) -> dict:
    """Explicit trend-following module: direction, regime, continuation and entry triggers."""
    r, p = x.iloc[-1], x.iloc[-2]
    a, b = h1.iloc[-1], h4.iloc[-1]
    price, atr = float(r.close), float(r.atr)
    if not np.isfinite(atr) or atr <= 0:
        return {"direction": "NEUTRAL", "score": 0, "regime": "UNKNOWN", "reasons": []}

    # Trend quality proxies (OHLC data does not provide a reliable exchange-wide ADX).
    ema_spread = abs(float(r.ema20 - r.ema50)) / atr
    ema_slope = float(r.ema20 - x.ema20.iloc[-6]) / atr if len(x) >= 6 else 0.0
    h1_up = a.close > a.ema20 > a.ema50
    h1_down = a.close < a.ema20 < a.ema50
    h4_up = b.close > b.ema50 and b.ema20 > b.ema50
    h4_down = b.close < b.ema50 and b.ema20 < b.ema50
    local_up = r.ema9 > r.ema20 > r.ema50 and price > r.ema20
    local_down = r.ema9 < r.ema20 < r.ema50 and price < r.ema20

    recent = x.iloc[-21:-1]
    prior_high, prior_low = float(recent.high.max()), float(recent.low.min())
    breakout_up = price > prior_high and r.close_pos >= 0.65
    breakout_down = price < prior_low and r.close_pos <= 0.35
    pullback_up = (local_up and r.low <= r.ema20 + atr * 0.25 and
                   price > r.ema20 and r.close > r.open)
    pullback_down = (local_down and r.high >= r.ema20 - atr * 0.25 and
                     price < r.ema20 and r.close < r.open)
    continuation_up = local_up and ema_slope > 0.08 and r.close > p.close
    continuation_down = local_down and ema_slope < -0.08 and r.close < p.close

    # A deliberately soft range filter: avoid only very compressed/flat conditions.
    ranging = ema_spread < 0.22 and abs(ema_slope) < 0.10
    regime = "RANGE / CHOP" if ranging else (
        "BULLISH TREND" if local_up and ema_slope > 0 else
        "BEARISH TREND" if local_down and ema_slope < 0 else "TRANSITION")

    buy_score = 0
    sell_score = 0
    buy_reasons, sell_reasons = [], []
    def award(condition, points, side, reason):
        nonlocal buy_score, sell_score
        if condition:
            if side == "BUY":
                buy_score += points; buy_reasons.append(reason)
            else:
                sell_score += points; sell_reasons.append(reason)

    award(h1_up, 4, "BUY", "Rule Trend: تایید روند ۱ساعته")
    award(h1_down, 4, "SELL", "Rule Trend: تایید روند ۱ساعته")
    award(h4_up, 4, "BUY", "Rule Trend: تایید روند ۴ساعته")
    award(h4_down, 4, "SELL", "Rule Trend: تایید روند ۴ساعته")
    award(local_up, 4, "BUY", "Rule Trend: هم‌ترازی EMA9/20/50")
    award(local_down, 4, "SELL", "Rule Trend: هم‌ترازی EMA9/20/50")
    award(continuation_up, 3, "BUY", "Rule Trend: ادامه مومنتوم صعودی")
    award(continuation_down, 3, "SELL", "Rule Trend: ادامه مومنتوم نزولی")
    award(pullback_up, 3, "BUY", "Rule Trend: ورود پولبک صعودی")
    award(pullback_down, 3, "SELL", "Rule Trend: ورود پولبک نزولی")
    award(breakout_up, 3, "BUY", "Rule Trend: شکست و تثبیت محدوده")
    award(breakout_down, 3, "SELL", "Rule Trend: شکست و تثبیت محدوده")

    # Penalize stretched entries to reduce chasing after an already-extended candle.
    extension = abs(price - float(r.ema20)) / atr
    if extension > 1.8:
        if price > r.ema20:
            buy_score = max(0, buy_score - 3)
        elif price < r.ema20:
            sell_score = max(0, sell_score - 3)

    if ranging:
        buy_score = max(0, buy_score - 3)
        sell_score = max(0, sell_score - 3)

    direction = "BUY" if buy_score > sell_score else "SELL" if sell_score > buy_score else "NEUTRAL"
    return {
        "direction": direction,
        "score": max(buy_score, sell_score),
        "buy_score": buy_score, "sell_score": sell_score,
        "regime": regime, "ema_spread_atr": ema_spread,
        "ema_slope_atr": ema_slope,
        "reasons": buy_reasons if direction == "BUY" else sell_reasons,
        "breakout_up": bool(breakout_up), "breakout_down": bool(breakout_down),
        "pullback_up": bool(pullback_up), "pullback_down": bool(pullback_down),
    }


# ------------------------------ Signal engine ------------------------------
def score_signal(d15: pd.DataFrame, d1: pd.DataFrame, d4: pd.DataFrame,
                 min_score: int = 48, min_rr: float = 1.0) -> dict:
    if len(d15) < 220 or len(d1) < 55 or len(d4) < 30:
        return {"direction": "NO SIGNAL", "reason": "داده کافی نیست."}

    x, h1, h4 = indicators(d15), indicators(d1), indicators(d4)
    r, p = x.iloc[-1], x.iloc[-2]
    a, b = h1.iloc[-1], h4.iloc[-1]
    price, atr = float(r.close), float(r.atr)
    if not np.isfinite(atr) or atr <= 0:
        return {"direction": "NO SIGNAL", "reason": "ATR قابل محاسبه نیست."}

    # Dedicated Rule-Based Trend Following module is the primary directional engine.
    trend = rule_based_trend_engine(x, h1, h4)

    bull = bear = 0
    buy_reasons, sell_reasons = [], []
    if trend["direction"] == "BUY":
        bull += trend["buy_score"]
        buy_reasons.extend(trend["reasons"])
    elif trend["direction"] == "SELL":
        bear += trend["sell_score"]
        sell_reasons.extend(trend["reasons"])

    def add(condition, points, side, reason):
        nonlocal bull, bear
        if condition:
            if side == "BUY":
                bull += points
                buy_reasons.append(reason)
            else:
                bear += points
                sell_reasons.append(reason)

    # Multi-timeframe trend alignment
    h1_bull = a.close > a.ema50 and a.ema20 > a.ema50
    h1_bear = a.close < a.ema50 and a.ema20 < a.ema50
    h4_bull = b.close > b.ema50
    h4_bear = b.close < b.ema50
    add(h1_bull, 12, "BUY", "روند ۱ساعته صعودی")
    add(h1_bear, 12, "SELL", "روند ۱ساعته نزولی")
    add(h4_bull, 10, "BUY", "جهت ۴ساعته صعودی")
    add(h4_bear, 10, "SELL", "جهت ۴ساعته نزولی")

    trend_up = r.ema9 > r.ema20 > r.ema50 and price > r.ema20
    trend_dn = r.ema9 < r.ema20 < r.ema50 and price < r.ema20
    add(trend_up, 12, "BUY", "چیدمان روندی EMA در ۱۵ دقیقه")
    add(trend_dn, 12, "SELL", "چیدمان روندی EMA در ۱۵ دقیقه")

    # Recent structure / breakout
    prior = x.iloc[-21:-1]
    prior_high, prior_low = float(prior.high.max()), float(prior.low.min())
    breakout_up = price > prior_high and r.close_pos > 0.65
    breakout_dn = price < prior_low and r.close_pos < 0.35
    add(breakout_up, 10, "BUY", "شکست سقف ۲۰ کندل با کلوز قوی")
    add(breakout_dn, 10, "SELL", "شکست کف ۲۰ کندل با کلوز قوی")

    # Pullback and candle confirmation
    pullback_up = trend_up and r.low <= r.ema20 + atr * 0.20 and price > r.ema20
    pullback_dn = trend_dn and r.high >= r.ema20 - atr * 0.20 and price < r.ema20
    add(pullback_up, 8, "BUY", "پولبک به EMA20 و حفظ روند")
    add(pullback_dn, 8, "SELL", "پولبک به EMA20 و حفظ روند")

    bull_engulf = (r.close > r.open and p.close < p.open and
                   r.open <= p.close and r.close >= p.open)
    bear_engulf = (r.close < r.open and p.close > p.open and
                   r.open >= p.close and r.close <= p.open)
    bull_pin = r.lower_wick > r.body * 1.8 and r.close_pos > 0.60
    bear_pin = r.upper_wick > r.body * 1.8 and r.close_pos < 0.40
    add(bull_engulf or bull_pin, 7, "BUY", "تأیید کندلی صعودی")
    add(bear_engulf or bear_pin, 7, "SELL", "تأیید کندلی نزولی")

    # Liquidity sweep proxies
    sweep_low = r.low < prior_low and price > prior_low
    sweep_high = r.high > prior_high and price < prior_high
    add(sweep_low, 9, "BUY", "برداشت نقدینگی کف و بازگشت")
    add(sweep_high, 9, "SELL", "برداشت نقدینگی سقف و بازگشت")

    # Momentum / displacement
    displacement_up = r.close > r.open and r.body > atr * 0.65 and r.close_pos > 0.75
    displacement_dn = r.close < r.open and r.body > atr * 0.65 and r.close_pos < 0.25
    add(displacement_up, 6, "BUY", "مومنتوم و کندل قدرتمند صعودی")
    add(displacement_dn, 6, "SELL", "مومنتوم و کندل قدرتمند نزولی")

    # Session bonus: boost active sessions, but never force a trade.
    session, session_quality = session_info()
    active = session in ("LONDON", "NEW YORK", "LONDON / NY OVERLAP")
    # Session is displayed as context only; it does not add points to both directions.

    # Small penalties for conflicting higher-timeframe direction and extreme chop.
    add(h1_bear or h4_bear, -8, "BUY", "تضاد با روند تایم‌فریم بالاتر")
    add(h1_bull or h4_bull, -8, "SELL", "تضاد با روند تایم‌فریم بالاتر")
    ema_gap = abs(float(r.ema20 - r.ema50)) / price
    if ema_gap < 0.00035:
        bull -= 5
        bear -= 5

    direction = "BUY" if bull > bear else "SELL" if bear > bull else "NO SIGNAL"
    raw_score = bull if direction == "BUY" else bear if direction == "SELL" else 0
    score = int(max(0, min(100, raw_score)))
    reasons = buy_reasons if direction == "BUY" else sell_reasons
    if direction == "NO SIGNAL" or score < min_score:
        return {
            "direction": "NO SIGNAL", "score": score,
            "reason": f"امتیاز کافی نیست؛ خرید {bull} / فروش {bear}",
            "session": session, "session_quality": session_quality,
            "trend_engine": trend,
        }

    # ATR-based protective stop; targets are exact 1R / 2R / 3R.
    entry = price
    stop_distance = max(atr * 1.25, price * 0.0008)
    if direction == "BUY":
        sl = entry - stop_distance
        tp1, tp2, tp3 = entry + stop_distance, entry + 2*stop_distance, entry + 3*stop_distance
    else:
        sl = entry + stop_distance
        tp1, tp2, tp3 = entry - stop_distance, entry - 2*stop_distance, entry - 3*stop_distance
    rr = abs(tp2-entry) / abs(entry-sl)
    if rr < min_rr:
        return {"direction": "NO SIGNAL", "score": score, "reason": "نسبت سود به زیان کافی نیست."}

    risk_label = "LOW" if score >= 78 else "MEDIUM" if score >= 58 else "HIGH"
    quality = "A" if score >= 78 else "B" if score >= 62 else "C"
    return {
        "direction": direction, "score": score, "grade": quality,
        "risk_label": risk_label, "entry": entry, "sl": sl,
        "tp1": tp1, "tp2": tp2, "tp3": tp3, "rr": rr,
        "atr": atr, "session": session, "session_quality": session_quality,
        "reasons": reasons, "time": x.index[-1],
        "trend_engine": trend,
        "trend_regime": trend["regime"],
        "valid_until": x.index[-1] + pd.Timedelta(minutes=45),
    }


# ------------------------------ Trade tracking ------------------------------
def load_log() -> list:
    try:
        if TRACK_FILE.exists():
            data = json.loads(TRACK_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def save_log(rows: list) -> None:
    TRACK_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def add_manual_result(result: str, sig: dict):
    rows = load_log()
    rows.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "direction": sig.get("direction"),
        "score": sig.get("score"),
        "result": result,
        "tp1": result in ("TP1", "TP2", "TP3"),
        "tp2": result in ("TP2", "TP3"),
        "tp3": result == "TP3",
    })
    save_log(rows)


def hit_rate(rows: list, key: str) -> tuple[str, int]:
    if len(rows) < 10:
        return "TRACKING — need 10 trades", len(rows)
    vals = [bool(r.get(key)) for r in rows[-100:]]
    return f"{sum(vals)/len(vals)*100:.0f}% REAL HIT-RATE", len(vals)


def price(v):
    return f"{float(v):,.2f}" if v is not None and np.isfinite(float(v)) else "—"


# ------------------------------ UI ------------------------------------------
def render_target(label: str, target: float, rr: int, rows: list, key: str):
    rate, n = hit_rate(rows, key)
    st.markdown(
        f"""
        <div style="background:#0d111b;border:1px solid #26303b;border-left:5px solid #20c978;
        border-radius:14px;padding:14px 16px;margin:9px 0;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <b style="color:#65dca1;letter-spacing:2px">{label}</b>
            <span style="color:#b7a4e8">R:R 1:{rr}.00</span>
            <b style="color:#55dc8a;font-size:18px">{price(target)}</b>
          </div>
          <div style="color:#9a91b2;font-size:12px;margin-top:9px">{rate}</div>
        </div>
        """, unsafe_allow_html=True
    )


def main():
    st.markdown("""
    <style>
    .stApp {background:linear-gradient(180deg,#10070d 0%,#090b16 100%);color:#eee}
    h1,h2,h3 {letter-spacing:1px}
    div[data-testid="stMetric"] {background:#11101b;border:1px solid #30243b;padding:12px;border-radius:12px}
    </style>
    """, unsafe_allow_html=True)
    st.title("🟡 AFG GOLD AI TREND PRO")
    st.caption("XAU/USD • 15m signal • 1H/4H trend context • 45-minute signal validity")

    with st.sidebar:
        st.header("Settings")
        secret_key = st.secrets.get("TWELVE_DATA_API_KEY", "")
        api_key = st.text_input("Twelve Data API Key", value=secret_key, type="password")
        min_score = st.slider("Minimum score", 40, 80, 48)
        outputsize = st.select_slider("Candle history", options=[500, 1000, 2000, 3000, 5000], value=2000)
        auto = st.checkbox("Auto refresh every 3 minutes", value=True)
        st.caption("API key را در Streamlit Secrets نگهداری کنید.")

    if auto:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=180000, key="v16_refresh")
        except Exception:
            pass
    if not api_key:
        st.warning('کلید API را وارد کنید یا در Secrets بنویسید: TWELVE_DATA_API_KEY = "..."')
        return

    try:
        with st.spinner("در حال دریافت اطلاعات XAU/USD..."):
            d15 = closed_candles(fetch_candles(SYMBOL, INTERVALS["15m"], outputsize, api_key), 15)
            d1 = closed_candles(fetch_candles(SYMBOL, INTERVALS["1h"], min(outputsize, 2000), api_key), 60)
            d4 = closed_candles(fetch_candles(SYMBOL, INTERVALS["4h"], min(outputsize, 1000), api_key), 240)
    except Exception as exc:
        st.error(f"خطا در دریافت داده: {exc}")
        return

    if len(d15) < 220 or len(d1) < 55 or len(d4) < 30:
        st.error("داده کافی پس از حذف کندل‌های ناتمام موجود نیست.")
        return

    sig = score_signal(d15, d1, d4, min_score=min_score)
    log_rows = load_log()
    st.caption(f"Last completed 15m candle (UTC): {d15.index[-1]}")

    if sig.get("direction") in ("BUY", "SELL"):
        side_color = "#ff555d" if sig["direction"] == "SELL" else "#22d47a"
        st.markdown(
            f"""<div style="text-align:center;border:2px solid {side_color};border-radius:22px;
            padding:20px 12px;background:#15090d;margin:8px 0 16px 0;">
            <div style="font-size:48px;font-weight:900;color:{side_color};letter-spacing:7px">{sig['direction']}</div>
            <div style="color:#c5a8d9;letter-spacing:2px">XAUUSD · {sig['session']} · R:R 1:2.00</div>
            <div style="display:inline-block;margin:14px;padding:10px 22px;border-radius:30px;
            background:#33220d;color:#ffd16b">🟡 {sig['grade']} — SCORE: {sig['score']}/100 — {sig['risk_label']} RISK</div>
            <div style="margin:8px;color:#73e6a0;font-weight:bold">✅ AI SAYS: TAKE THIS TRADE</div>
            <div style="color:#9c8eaa">Rule-based trend trade · decision support only</div>
            </div>""", unsafe_allow_html=True
        )
        now = pd.Timestamp.now(tz="UTC")
        remaining = max(0, int((sig["valid_until"] - now).total_seconds() / 60))
        c1, c2 = st.columns(2)
        c1.metric("VALID FOR", f"{remaining} min")
        c2.metric("SESSION", sig["session"])
        c1, c2 = st.columns(2)
        c1.metric("ENTRY · MARKET", price(sig["entry"]))
        c2.metric("STOP LOSS / INVALIDATION", price(sig["sl"]))
        st.markdown("### 🎯 3-TARGET PROFIT SYSTEM")
        render_target("TP1", sig["tp1"], 1, log_rows, "tp1")
        render_target("TP2", sig["tp2"], 2, log_rows, "tp2")
        render_target("TP3", sig["tp3"], 3, log_rows, "tp3")
        st.caption("درصد برخورد فقط پس از ثبت حداقل ۱۰ نتیجه دستی نمایش داده می‌شود؛ این آمار تضمین آینده نیست.")
        st.markdown("### ثبت نتیجه معامله")
        st.caption("پس از بسته‌شدن معامله، نتیجه واقعی را ثبت کن. فقط یک‌بار برای هر سیگنال ثبت شود.")
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("TP1", use_container_width=True):
            add_manual_result("TP1", sig); st.success("TP1 ثبت شد."); st.rerun()
        if c2.button("TP2", use_container_width=True):
            add_manual_result("TP2", sig); st.success("TP2 ثبت شد."); st.rerun()
        if c3.button("TP3", use_container_width=True):
            add_manual_result("TP3", sig); st.success("TP3 ثبت شد."); st.rerun()
        if c4.button("STOP LOSS", use_container_width=True):
            add_manual_result("LOSS", sig); st.success("ضرر ثبت شد."); st.rerun()
        with st.expander("دلایل امتیاز سیگنال"):
            for reason in sig.get("reasons", []):
                st.write("• " + reason)
    else:
        st.warning("فعلاً سیگنال واجد شرایط وجود ندارد.")
        st.write(sig.get("reason", "شرایط بازار برای ورود کافی نیست."))
        st.write(f"Session: {sig.get('session', '—')}")

    st.divider()
    st.subheader("عملکرد ثبت‌شده")
    if log_rows:
        rows = log_rows[-100:]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Logged trades", len(rows))
        m2.metric("TP1 hit rate", hit_rate(rows, "tp1")[0])
        m3.metric("TP2 hit rate", hit_rate(rows, "tp2")[0])
        m4.metric("TP3 hit rate", hit_rate(rows, "tp3")[0])
        st.dataframe(pd.DataFrame(rows[-30:]), use_container_width=True, hide_index=True)
        if st.button("پاک‌کردن تاریخچه نتایج"):
            save_log([])
            st.rerun()
    else:
        st.info("هنوز نتیجه‌ای ثبت نشده است. برای آمار واقعی، حداقل ۱۰ معامله را ثبت کن.")

    st.divider()
    st.subheader("یادآوری درباره دقت")
    st.write(
        "این نسخه یک تقریب مستقل از سبک قابل مشاهده در تصویر است: موتور مستقل Rule-Based Trend Following "
        "با تشخیص رژیم، روند چندتایم‌فریمی، ادامه روند، پولبک و شکست؛ به‌علاوه پرایس‌اکشن، "
        "برداشت نقدینگی، مومنتوم و فیلتر سشن، "
        "امتیازدهی و سه تارگت 1R/2R/3R. از تصویر نمی‌توان قوانین پنهان ربات دوستت را "
        "استخراج کرد. امتیاز ۰ تا ۱۰۰ احتمال برد نیست. قبل از معامله واقعی، بک‌تست و "
        "فورواردتست روی قیمت بروکر خودت ضروری است."
    )


if __name__ == "__main__":
    main()
