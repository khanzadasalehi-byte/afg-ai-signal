"""
AFG GOLD | ORIGINAL RULE-BASED MULTI-FILTER TREND FOLLOWING
==========================================================
A standalone XAU/USD decision-support app.

Install:
    pip install streamlit pandas numpy requests
Run:
    streamlit run afg_gold_multifilter.py

Data:
    Twelve Data time_series endpoint (XAU/USD, 15-minute candles).
    Enter your own API key in the sidebar.

Important:
- This is an original, transparent rule-based implementation.
- It does NOT claim to reproduce another trader's private source code.
- No daily trade, win rate, or profit is guaranteed.
- Backtest uses next-candle-open entries and conservative same-candle
  stop/target handling. It is a simulation, not a promise of live results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AFG GOLD | MULTI-FILTER TREND FOLLOWING", page_icon="🟡", layout="centered")

APP_NAME = "AFG GOLD | MULTI-FILTER TREND FOLLOWING"
SYMBOL = "XAU/USD"
API_URL = "https://api.twelvedata.com/time_series"
KABUL_TZ = ZoneInfo("Asia/Kabul")


# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------
@dataclass
class StrategyConfig:
    min_score: int = 55
    min_adx: float = 16.0
    max_adx: float = 55.0
    atr_stop: float = 1.4
    max_holding_bars: int = 8
    signal_valid_minutes: int = 45
    use_session_filter: bool = False
    use_volatility_filter: bool = True
    min_atr_pct: float = 0.025
    max_atr_pct: float = 0.80


# ---------------------------------------------------------------------
# MARKET DATA
# ---------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_xauusd(api_key: str, interval: str, outputsize: int) -> pd.DataFrame:
    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "timezone": "UTC",
        "format": "JSON",
        "apikey": api_key,
    }
    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if "values" not in payload:
        message = payload.get("message") or payload.get("code") or str(payload)
        raise RuntimeError(f"Twelve Data did not return candle data: {message}")

    frame = pd.DataFrame(payload["values"])
    required = ["datetime", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise RuntimeError(f"Missing data columns: {', '.join(missing)}")

    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True, errors="coerce")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=required)
    frame = frame.sort_values("datetime").drop_duplicates("datetime")
    frame = frame.set_index("datetime")
    return frame


# ---------------------------------------------------------------------
# INDICATORS — all calculated from current/past candles only
# ---------------------------------------------------------------------
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()
    previous_close = x["close"].shift(1)

    x["ema20"] = ema(x["close"], 20)
    x["ema50"] = ema(x["close"], 50)
    x["ema200"] = ema(x["close"], 200)

    true_range = pd.concat(
        [
            x["high"] - x["low"],
            (x["high"] - previous_close).abs(),
            (x["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    x["atr"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()
    x["atr_pct"] = (x["atr"] / x["close"]) * 100

    upward = x["high"].diff()
    downward = -x["low"].diff()
    plus_dm = pd.Series(
        np.where((upward > downward) & (upward > 0), upward, 0.0),
        index=x.index,
    )
    minus_dm = pd.Series(
        np.where((downward > upward) & (downward > 0), downward, 0.0),
        index=x.index,
    )
    smoothed_tr = true_range.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / smoothed_tr
    minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / smoothed_tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    x["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

    change = x["close"].diff()
    average_gain = change.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    average_loss = (-change.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    x["rsi"] = 100 - (100 / (1 + relative_strength))

    x["prior_high_20"] = x["high"].shift(1).rolling(20).max()
    x["prior_low_20"] = x["low"].shift(1).rolling(20).min()
    x["prior_high_8"] = x["high"].shift(1).rolling(8).max()
    x["prior_low_8"] = x["low"].shift(1).rolling(8).min()
    return x


def completed_hourly_bias(raw_15m: pd.DataFrame) -> pd.Series:
    """
    Resample to right-labelled/right-closed 1H candles.
    merge_asof backward means a 15m decision only sees an hourly candle
    whose closing timestamp is at or before that decision timestamp.
    """
    hourly = raw_15m.resample("1h", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()

    hourly["ema50"] = ema(hourly["close"], 50)
    hourly["ema200"] = ema(hourly["close"], 200)
    hourly["bias"] = np.select(
        [
            hourly["ema50"] > hourly["ema200"],
            hourly["ema50"] < hourly["ema200"],
        ],
        [1, -1],
        default=0,
    )

    left = pd.DataFrame({"decision_time": raw_15m.index}).sort_values("decision_time")
    right = (
        hourly[["bias"]]
        .reset_index()
        .rename(columns={"datetime": "hour_close_time"})
        .sort_values("hour_close_time")
    )
    merged = pd.merge_asof(
        left,
        right,
        left_on="decision_time",
        right_on="hour_close_time",
        direction="backward",
    )
    return pd.Series(merged["bias"].fillna(0).to_numpy(), index=raw_15m.index)


def session_for(timestamp: pd.Timestamp) -> str:
    utc = timestamp.tz_convert("UTC")
    minute = utc.hour * 60 + utc.minute
    london = 7 * 60 <= minute < 16 * 60
    new_york = 12 * 60 <= minute < 21 * 60
    if london and new_york:
        return "LONDON / NY OVERLAP"
    if london:
        return "LONDON"
    if new_york:
        return "NEW YORK"
    return "OFF SESSION"


# ---------------------------------------------------------------------
# ORIGINAL MULTI-FILTER TREND FOLLOWING ENGINE
# ---------------------------------------------------------------------
def build_strategy(raw: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    x = add_indicators(raw)
    x["htf_bias"] = completed_hourly_bias(raw)

    # Trend direction is the essential filter. Other filters are scored
    # progressively so the strategy is not unnecessarily restrictive.
    bull_stack = (x["ema20"] > x["ema50"]) & (x["ema50"] > x["ema200"])
    bear_stack = (x["ema20"] < x["ema50"]) & (x["ema50"] < x["ema200"])
    bull_bias = x["htf_bias"] == 1
    bear_bias = x["htf_bias"] == -1

    # Entry triggers: reclaim EMA20 after pullback OR close beyond recent range.
    bull_reclaim = (x["close"] > x["ema20"]) & (x["close"].shift(1) <= x["ema20"].shift(1))
    bear_reclaim = (x["close"] < x["ema20"]) & (x["close"].shift(1) >= x["ema20"].shift(1))
    bull_break = x["close"] > x["prior_high_8"]
    bear_break = x["close"] < x["prior_low_8"]
    bull_trigger = bull_reclaim | bull_break
    bear_trigger = bear_reclaim | bear_break

    # Balanced score: trend 40, strength 15, momentum 15, price behaviour 15,
    # volatility 10, active session 5. Score is NOT a probability of winning.
    trend_score = np.where(x["htf_bias"] != 0, 20, 0)
    trend_score += np.where(bull_bias & bull_stack | bear_bias & bear_stack, 20, 0)

    strength_score = np.where(
        x["adx"] >= 25, 15,
        np.where(x["adx"] >= cfg.min_adx, 10, 0),
    )

    momentum_ok = (
        (bull_bias & x["rsi"].between(48, 74))
        | (bear_bias & x["rsi"].between(26, 52))
    )
    momentum_score = np.where(momentum_ok, 15, 0)

    price_ok = (
        (bull_bias & (x["close"] > x["ema20"]))
        | (bear_bias & (x["close"] < x["ema20"]))
    )
    trigger_score = np.where(
        (bull_bias & bull_trigger) | (bear_bias & bear_trigger), 15, 0
    )
    price_score = np.where(price_ok, 8, 0) + trigger_score

    volatility_ok = x["atr_pct"].between(cfg.min_atr_pct, cfg.max_atr_pct)
    volatility_score = np.where(volatility_ok, 10, 0)

    sessions = pd.Series([session_for(t) for t in x.index], index=x.index)
    active_session = sessions != "OFF SESSION"
    session_score = np.where(active_session, 5, 2)

    x["score"] = np.minimum(
        trend_score + strength_score + momentum_score + price_score
        + volatility_score + session_score,
        100,
    ).astype(int)
    x["grade"] = np.select(
        [x["score"] >= 75, x["score"] >= 60],
        ["A", "B"],
        default="C",
    )
    x["risk_label"] = np.select(
        [x["score"] >= 75, x["score"] >= 60],
        ["LOW RISK", "MEDIUM RISK"],
        default="HIGH RISK",
    )
    x["session"] = sessions
    x["market_state"] = np.select(
        [x["adx"] >= 25, x["adx"] >= cfg.min_adx],
        ["TRENDING", "MIXED"],
        default="WEAK / RANGE",
    )

    x["direction"] = 0
    x.loc[bull_bias & bull_trigger, "direction"] = 1
    x.loc[bear_bias & bear_trigger, "direction"] = -1

    # No forced signals. Core trend + trigger required; remaining checks
    # are flexible scoring gates. Session filter is optional.
    eligible = (x["direction"] != 0) & (x["score"] >= cfg.min_score)
    eligible &= x["adx"] >= cfg.min_adx
    eligible &= x["adx"] <= cfg.max_adx
    if cfg.use_volatility_filter:
        eligible &= volatility_ok
    if cfg.use_session_filter:
        eligible &= active_session

    x["eligible"] = eligible
    x["decision"] = np.where(eligible, "TAKE THIS TRADE", "WAIT THIS TRADE")
    return x


# ---------------------------------------------------------------------
# RISK AND TARGET LEVELS
# ---------------------------------------------------------------------
def trade_levels(entry: float, atr: float, direction: int, cfg: StrategyConfig):
    risk_distance = max(float(atr) * cfg.atr_stop, float(entry) * 0.0005)
    stop = entry - direction * risk_distance
    # 3 targets, with partial allocation 50% / 30% / 20%.
    multiples = (1.0, 2.0, 3.0)
    targets = [entry + direction * risk_distance * r for r in multiples]
    return stop, targets, risk_distance, multiples


# ---------------------------------------------------------------------
# HONEST HISTORICAL SIMULATION
# ---------------------------------------------------------------------
def run_backtest(data: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Signal at candle close; enter at next candle open.
    Each trade allocates 50/30/20 to TP1/TP2/TP3.
    Stop is checked before targets within each candle (conservative).
    Remaining quantity is closed at stop or final holding candle close.
    Trades do not overlap, preventing multiple simultaneous exposure.
    """
    trades = []
    i = 220

    while i < len(data) - 2:
        signal = data.iloc[i]
        if not bool(signal["eligible"]) or not np.isfinite(signal["atr"]):
            i += 1
            continue

        direction = int(signal["direction"])
        entry_i = i + 1
        entry_bar = data.iloc[entry_i]
        entry = float(entry_bar["open"])
        stop, targets, risk_distance, multiples = trade_levels(
            entry, float(signal["atr"]), direction, cfg
        )

        allocations = [0.50, 0.30, 0.20]
        target_hits = [False, False, False]
        remaining = 1.0
        realized_r = 0.0
        exit_reason = "TIME EXIT"
        last_i = min(entry_i + cfg.max_holding_bars - 1, len(data) - 1)
        actual_exit_i = last_i

        for j in range(entry_i, last_i + 1):
            bar = data.iloc[j]

            stop_touched = (
                float(bar["low"]) <= stop if direction == 1
                else float(bar["high"]) >= stop
            )
            if stop_touched and remaining > 0:
                realized_r -= remaining
                remaining = 0.0
                exit_reason = "STOP LOSS"
                actual_exit_i = j
                break

            for k, target in enumerate(targets):
                if not target_hits[k]:
                    target_touched = (
                        float(bar["high"]) >= target if direction == 1
                        else float(bar["low"]) <= target
                    )
                    if target_touched:
                        target_hits[k] = True
                        realized_r += allocations[k] * multiples[k]
                        remaining -= allocations[k]

            if remaining <= 1e-9:
                remaining = 0.0
                exit_reason = "TP3"
                actual_exit_i = j
                break

        if remaining > 0:
            close_price = float(data.iloc[actual_exit_i]["close"])
            open_r = direction * (close_price - entry) / risk_distance
            realized_r += remaining * open_r

        trades.append({
            "entry_time": data.index[entry_i],
            "side": "BUY" if direction == 1 else "SELL",
            "score": int(signal["score"]),
            "entry": entry,
            "stop": stop,
            "tp1": targets[0],
            "tp2": targets[1],
            "tp3": targets[2],
            "tp1_hit": target_hits[0],
            "tp2_hit": target_hits[1],
            "tp3_hit": target_hits[2],
            "exit_reason": exit_reason,
            "net_R": realized_r,
        })
        i = actual_exit_i + 1

    return pd.DataFrame(trades)


def metric_hit_rate(trades: pd.DataFrame, column: str) -> float:
    if trades.empty:
        return 0.0
    return float(trades[column].mean() * 100)


# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {background:#080611;color:#e9dcff}
    .hero {border:2px solid #23c879;border-radius:18px;padding:18px;
           background:#07180e;text-align:center;margin:8px 0}
    .hero.sell {border-color:#e34b60;background:#1a070d}
    .hero .direction {font-size:42px;font-weight:900;letter-spacing:5px}
    .panel {background:#100b1c;border:1px solid #30233f;border-radius:12px;
            padding:14px;margin:8px 0;text-align:center}
    .target {background:#0c101b;border:1px solid #26353b;border-left:5px solid #27cf83;
             border-radius:13px;padding:13px;margin:9px 0}
    .muted {color:#a596bd;font-size:12px;letter-spacing:2px}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🟡 AFG GOLD")
st.caption("ORIGINAL RULE-BASED MULTI-FILTER TREND FOLLOWING · XAU/USD")

with st.sidebar:
    st.header("داده بازار")
    api_key = st.text_input("Twelve Data API Key", type="password")
    candle_count = st.selectbox("تعداد کندل تاریخی", [500, 1000, 2000, 4000], index=2)

    st.header("تنظیمات استراتژی")
    min_score = st.slider("حداقل امتیاز ورود", 50, 80, 55, 5)
    min_adx = st.slider("حداقل قدرت روند (ADX)", 12, 30, 16, 1)
    max_adx = st.slider("حداکثر ADX", 35, 70, 55, 1)
    atr_stop = st.slider("فاصله حد ضرر بر اساس ATR", 1.0, 2.5, 1.4, 0.1)
    holding_bars = st.slider("حداکثر نگهداری معامله (کندل ۱۵ دقیقه)", 2, 24, 8, 1)
    validity = st.selectbox("اعتبار سیگنال (دقیقه)", [30, 45, 60], index=1)
    use_session = st.checkbox("فقط سشن لندن و نیویورک", value=False)
    use_volatility = st.checkbox("فعال‌بودن فیلتر نوسان", value=True)
    st.caption("تقسیم خروج: TP1=50٪، TP2=30٪، TP3=20٪")
    st.caption("تارگت‌ها: 1R، 2R و 3R")

cfg = StrategyConfig(
    min_score=min_score,
    min_adx=float(min_adx),
    max_adx=float(max_adx),
    atr_stop=float(atr_stop),
    max_holding_bars=int(holding_bars),
    signal_valid_minutes=int(validity),
    use_session_filter=use_session,
    use_volatility_filter=use_volatility,
)

if not api_key:
    st.info("کلید API حساب Twelve Data را در تنظیمات وارد کن تا قیمت و سیگنال زنده دریافت شود.")
    st.subheader("منطق اصلی استراتژی")
    st.write(
        "روند ۱ ساعته + هم‌جهتی EMAهای ۲۰/۵۰/۲۰۰ + قدرت روند ADX + "
        "مومنتوم RSI + ورود پولبک/شکست + فیلتر نوسان و جلسه معاملاتی."
    )
    st.warning("این سیستم برای فرصت‌های منظم طراحی شده؛ اما در نبود شرایط معتبر، معامله اجباری صادر نمی‌کند.")
    st.stop()

try:
    with st.spinner("در حال دریافت داده‌های XAU/USD و محاسبه استراتژی..."):
        raw = fetch_xauusd(api_key, "15min", int(candle_count))

    if len(raw) < 250:
        st.error("داده کافی نیست. حداقل حدود ۲۵۰ کندل برای محاسبات پایدار لازم است.")
        st.stop()

    data = build_strategy(raw, cfg)
    latest = data.iloc[-1]
    latest_time = data.index[-1]
    now_utc = pd.Timestamp.now(tz="UTC")
    age_minutes = max(0.0, (now_utc - latest_time).total_seconds() / 60)
    fresh = age_minutes <= 30

    if not fresh:
        st.warning(
            f"آخرین کندل دریافتی {age_minutes:.0f} دقیقه پیش بسته شده است. "
            "این سیگنال را زنده تلقی نکن؛ منبع داده ممکن است تأخیر داشته باشد."
        )

    valid = bool(latest["eligible"]) and fresh
    direction = int(latest["direction"])

    if valid:
        side = "BUY" if direction == 1 else "SELL"
        hero_class = "hero" if direction == 1 else "hero sell"
        entry = float(latest["close"])
        stop, targets, risk_distance, rr_values = trade_levels(
            entry, float(latest["atr"]), direction, cfg
        )
        generated_local = latest_time.tz_convert(KABUL_TZ)
        expiry_minutes = max(0, validity - int(age_minutes))

        st.markdown(
            f"""
            <div class="{hero_class}">
              <div class="direction">{side}</div>
              <div class="muted">XAUUSD · {latest['session']} · R:R 1:3.00</div>
              <h3>{latest['grade']} — SCORE: {int(latest['score'])}/100 — {latest['risk_label']}</h3>
              <h3>✅ AI SAYS: TAKE THIS TRADE</h3>
              <div>{latest['market_state']} · ADX {latest['adx']:.1f} · RSI {latest['rsi']:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="panel"><div class="muted">GENERATED · VALID FOR {expiry_minutes} MIN</div>'
            f'<h3>{generated_local.strftime("%Y-%m-%d %H:%M")} KABUL</h3></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="panel"><div class="muted">ENTRY · MARKET</div><h2>{entry:,.2f}</h2></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="panel"><div class="muted">STOP LOSS / INVALIDATION</div>'
            f'<h2 style="color:#ef6677">{stop:,.2f}</h2></div>',
            unsafe_allow_html=True,
        )
        for number, (target, allocation, multiple) in enumerate(
            zip(targets, [50, 30, 20], rr_values), start=1
        ):
            st.markdown(
                f'<div class="target"><b>🎯 TP{number} · {allocation}%</b>'
                f'<h3>{target:,.2f} <span class="muted">R:R 1:{multiple:.2f}</span></h3>'
                f'<div class="muted">HIT RATE: after enough recorded/backtested trades</div></div>',
                unsafe_allow_html=True,
            )
        st.caption("قیمت Entry در این نسخه قیمت بسته‌شدن کندل تأیید است؛ برای اجرای واقعی، اسپرد و لغزش قیمت را بررسی کن.")
    else:
        st.markdown(
            """
            <div class="hero">
              <div class="direction">WAIT</div>
              <h3>⏳ AI SAYS: WAIT THIS TRADE</h3>
              <div class="muted">No confirmed entry at the latest completed candle</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric("امتیاز فعلی", f"{int(latest['score'])}/100")
        trend_label = "صعودی" if latest["htf_bias"] == 1 else "نزولی" if latest["htf_bias"] == -1 else "خنثی"
        st.write(
            f"جهت روند ۱ ساعته: **{trend_label}** · "
            f"وضعیت بازار: **{latest['market_state']}** · "
            f"ADX: **{latest['adx']:.1f}** · RSI: **{latest['rsi']:.1f}**"
        )
        st.write("امتیاز بالا به‌تنهایی کافی نیست؛ جهت روند و ماشه ورود نیز باید تأیید شوند.")

    st.subheader("نمای بازار")
    col1, col2, col3 = st.columns(3)
    col1.metric("آخرین قیمت", f"{latest['close']:,.2f}")
    col2.metric("روند ۱ ساعته", "BULLISH" if latest["htf_bias"] == 1 else "BEARISH" if latest["htf_bias"] == -1 else "NEUTRAL")
    col3.metric("جلسه", latest["session"])
    st.line_chart(data[["close", "ema20", "ema50", "ema200"]].tail(180), height=280)

    st.subheader("بک‌تست تاریخی")
    st.caption(
        "سیگنال در بسته‌شدن کندل، ورود در بازشدن کندل بعدی؛ "
        "در برخورد هم‌زمان حد ضرر و تارگت در یک کندل، حد ضرر اول فرض می‌شود."
    )
    if st.button("اجرای بک‌تست روی داده‌های دریافت‌شده", type="primary"):
        with st.spinner("در حال شبیه‌سازی معاملات..."):
            results = run_backtest(data, cfg)

        if results.empty:
            st.warning("در داده‌های انتخاب‌شده معامله‌ای با قوانین فعلی پیدا نشد. بازه داده را بیشتر کن یا تنظیمات را بررسی کن.")
        else:
            total = len(results)
            wins = int((results["net_R"] > 0).sum())
            losses = int((results["net_R"] < 0).sum())
            gross_r = float(results["net_R"].sum())
            avg_r = float(results["net_R"].mean())
            hit1 = metric_hit_rate(results, "tp1_hit")
            hit2 = metric_hit_rate(results, "tp2_hit")
            hit3 = metric_hit_rate(results, "tp3_hit")
            equity = results["net_R"].cumsum()
            drawdown_r = float((equity - equity.cummax()).min()) if len(equity) else 0.0

            m1, m2, m3 = st.columns(3)
            m1.metric("تعداد معاملات", total)
            m2.metric("معاملات مثبت", wins)
            m3.metric("معاملات منفی", losses)
            m4, m5, m6 = st.columns(3)
            m4.metric("TP1 hit rate", f"{hit1:.1f}%")
            m5.metric("TP2 hit rate", f"{hit2:.1f}%")
            m6.metric("TP3 hit rate", f"{hit3:.1f}%")
            m7, m8 = st.columns(2)
            m7.metric("جمع نتیجه", f"{gross_r:.2f} R")
            m8.metric("میانگین هر معامله", f"{avg_r:.3f} R")
            st.metric("بیشترین افت منحنی معاملات", f"{drawdown_r:.2f} R")
            st.line_chart(equity.rename("Cumulative R"), height=220)
            st.dataframe(results.tail(150), use_container_width=True)
            st.download_button(
                "دانلود گزارش بک‌تست CSV",
                results.to_csv(index=False).encode("utf-8"),
                "afg_gold_multifilter_backtest.csv",
                "text/csv",
            )
            st.caption(
                "نتایج مربوط به داده و تنظیمات انتخاب‌شده است؛ اسپرد، کمیسیون، "
                "لغزش، کیفیت فید و اجرای واقعی ممکن است نتیجه را تغییر دهند."
            )

    with st.expander("قوانین دقیق استراتژی — شفاف و قابل بررسی"):
        st.markdown(
            """
            **۱. جهت اصلی روند:** EMA50 و EMA200 در کندل‌های یک‌ساعته کامل‌شده، جهت غالب را تعیین می‌کنند.

            **۲. هم‌جهتی تایم‌فریم اجرا:** در ۱۵ دقیقه، EMA20/50/200 برای امتیاز روند بررسی می‌شوند.

            **۳. قدرت روند:** ADX؛ حداقل پیش‌فرض ۱۶ است تا سیستم بیش از حد سخت‌گیر نباشد.

            **۴. مومنتوم:** RSI در محدوده‌های متعادل بررسی می‌شود؛ BUY حدود ۴۸ تا ۷۴ و SELL حدود ۲۶ تا ۵۲.

            **۵. ماشه ورود:** عبور دوباره قیمت از EMA20 پس از پولبک یا بسته‌شدن بیرون محدوده ۸ کندل قبلی.

            **۶. فیلتر نوسان:** ATR نسبت به قیمت؛ قابل خاموش‌کردن از تنظیمات.

            **۷. امتیازدهی:** روند تا ۴۰، ADX تا ۱۵، مومنتوم ۱۵، رفتار قیمت تا ۱۵، نوسان ۱۰ و جلسه ۵ امتیاز. امتیاز، احتمال برد نیست.

            **۸. مدیریت معامله:** حد ضرر پیش‌فرض ۱.۴ ATR؛ تارگت‌ها ۱R، ۲R و ۳R با تقسیم حجم ۵۰٪، ۳۰٪ و ۲۰٪.

            **۹. عدم اجبار:** اگر روند یا ماشه ورود معتبر نباشد، سیستم WAIT می‌دهد؛ حتی اگر هدف، داشتن فرصت‌های روزانه باشد.

            **۱۰. اصالت:** این قوانین یک طراحی مستقل و قابل‌آزمایش‌اند؛ ادعا نمی‌شود که قوانین خصوصی سیستم دوستت هستند.
            """
        )

    st.caption(
        f"آخرین کندل داده: {latest_time.isoformat()} · "
        "منبع قیمت: Twelve Data · سیگنال‌ها فقط ابزار تصمیم‌یار هستند."
    )

except requests.RequestException as error:
    st.error(f"خطا در ارتباط با ارائه‌دهنده داده: {error}")
    st.info("اتصال اینترنت، اعتبار API Key و محدودیت درخواست‌های Twelve Data را بررسی کن.")
except Exception as error:
    st.error(f"خطا در اجرای برنامه: {error}")
    st.info("اگر خطا ادامه داشت، متن کامل خطا را بفرست تا اصلاح شود.")
