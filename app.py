import streamlit as st
import pandas as pd
import numpy as np
import requests

# ==========================================
# AFG AI GOLD PRO - Gold analysis dashboard
# ==========================================

st.set_page_config(
    page_title="AFG AI GOLD PRO",
    page_icon="🇦🇫",
    layout="wide"
)

st.title("🇦🇫 AFG AI GOLD PRO")
st.subheader("Gold Technical Analysis | Signals | Multi-Timeframe | Backtesting")

TIMEOUT = 30
API_URL = "https://api.twelvedata.com/time_series"

TIMEFRAMES = {
    "1 دقیقه": "1min",
    "5 دقیقه": "5min",
    "15 دقیقه": "15min",
    "1 ساعت": "1h",
    "4 ساعت": "4h"
}


# ==========================================
# DATA
# ==========================================

def get_api_key():
    try:
        key = st.secrets["TWELVE_DATA_API_KEY"]
    except Exception:
        raise ValueError(
            "کلید Twelve Data پیدا نشد. در Streamlit → Settings → Secrets "
            "مقدار TWELVE_DATA_API_KEY را تنظیم کن."
        )

    if not key:
        raise ValueError("کلید Twelve Data خالی است.")

    return key


def fetch_gold_candles(interval, outputsize=250):
    api_key = get_api_key()

    response = requests.get(
        API_URL,
        params={
            "symbol": "XAU/USD",
            "interval": interval,
            "outputsize": outputsize,
            "timezone": "UTC",
            "apikey": api_key
        },
        timeout=TIMEOUT
    )
    response.raise_for_status()
    payload = response.json()

    if "values" not in payload:
        message = payload.get("message") or payload.get("status") or str(payload)
        raise ValueError(f"Twelve Data: {message}")

    df = pd.DataFrame(payload["values"])

    required = ["datetime", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"ستون‌های داده ناقص است: {missing}")

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)

    df = df.dropna(
        subset=["datetime", "open", "high", "low", "close"]
    )
    df = df.sort_values("datetime").drop_duplicates("datetime")
    df = df.reset_index(drop=True)

    # Exclude the newest candle because it may still be forming.
    if len(df) > 1:
        df = df.iloc[:-1].copy().reset_index(drop=True)

    if len(df) < 210:
        raise ValueError(
            f"تعداد کندل کافی نیست: {len(df)}. حداقل 210 کندل بسته‌شده لازم است."
        )

    return df


# ==========================================
# INDICATORS AND SIGNAL
# ==========================================

def afg_add_indicators(df):
    df = df.copy()

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=["open", "high", "low", "close"]
    ).reset_index(drop=True)

    if len(df) < 210:
        raise ValueError("حداقل 210 کندل برای محاسبه اندیکاتورها لازم است.")

    close = df["close"]

    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()
    df["EMA200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    df.loc[(avg_loss == 0) & (avg_gain > 0), "RSI"] = 100
    df.loc[(avg_loss == 0) & (avg_gain == 0), "RSI"] = 50

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    previous_close = close.shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()

    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0), 0
    )
    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0), 0
    )

    atr_safe = df["ATR"].replace(0, np.nan)

    df["PLUS_DI"] = (
        100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    )
    df["MINUS_DI"] = (
        100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    )

    di_sum = (df["PLUS_DI"] + df["MINUS_DI"]).replace(0, np.nan)
    dx = 100 * (df["PLUS_DI"] - df["MINUS_DI"]).abs() / di_sum
    df["ADX"] = dx.ewm(alpha=1/14, adjust=False).mean()

    middle = close.rolling(20).mean()
    deviation = close.rolling(20).std()
    df["BB_middle"] = middle
    df["BB_upper"] = middle + 2 * deviation
    df["BB_lower"] = middle - 2 * deviation

    return df


def afg_generate_signal(df):
    last = df.iloc[-1]

    required = [
        "EMA20", "EMA50", "EMA200", "RSI",
        "MACD", "MACD_SIGNAL", "ATR",
        "ADX", "PLUS_DI", "MINUS_DI"
    ]

    if last[required].isna().any():
        raise ValueError("اندیکاتورها هنوز کامل محاسبه نشده‌اند.")

    score = 0
    reasons = []

    if last["EMA20"] > last["EMA50"] > last["EMA200"]:
        score += 2
        reasons.append("چیدمان EMA صعودی است")
    elif last["EMA20"] < last["EMA50"] < last["EMA200"]:
        score -= 2
        reasons.append("چیدمان EMA نزولی است")

    if last["close"] > last["EMA20"]:
        score += 1
        reasons.append("قیمت بالاتر از EMA20 است")
    elif last["close"] < last["EMA20"]:
        score -= 1
        reasons.append("قیمت پایین‌تر از EMA20 است")

    if 50 < last["RSI"] < 70:
        score += 1
        reasons.append("قدرت RSI به نفع خریداران است")
    elif 30 < last["RSI"] < 50:
        score -= 1
        reasons.append("قدرت RSI به نفع فروشندگان است")
    elif last["RSI"] >= 70:
        reasons.append("هشدار اشباع خرید RSI")
    elif last["RSI"] <= 30:
        reasons.append("هشدار اشباع فروش RSI")

    if last["MACD"] > last["MACD_SIGNAL"]:
        score += 1
        reasons.append("MACD صعودی است")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        score -= 1
        reasons.append("MACD نزولی است")

    if last["ADX"] >= 20:
        if last["PLUS_DI"] > last["MINUS_DI"]:
            score += 1
            reasons.append("ADX جهت صعودی را تأیید می‌کند")
        elif last["MINUS_DI"] > last["PLUS_DI"]:
            score -= 1
            reasons.append("ADX جهت نزولی را تأیید می‌کند")
    else:
        reasons.append("قدرت روند ضعیف است")

    if score >= 4:
        signal = "BUY"
    elif score <= -4:
        signal = "SELL"
    else:
        signal = "NO TRADE"

    return signal, score, reasons


# ==========================================
# DISPLAY
# ==========================================

def show_signal(df, timeframe_name):
    df = afg_add_indicators(df)
    signal, score, reasons = afg_generate_signal(df)
    last = df.iloc[-1]

    st.caption(
        f"تایم‌فریم: {timeframe_name} | "
        f"آخرین کندل بسته‌شده (UTC): {last['datetime']}"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("قیمت بسته‌شدن", f"${last['close']:,.2f}")
    c2.metric("RSI", f"{last['RSI']:.2f}")
    c3.metric("ADX", f"{last['ADX']:.2f}")
    c4.metric("ATR", f"{last['ATR']:.3f}")

    st.subheader(f"نتیجه تحلیل: {signal}")
    if signal == "BUY":
        st.success("BUY — شرایط تکنیکال صعودی")
    elif signal == "SELL":
        st.error("SELL — شرایط تکنیکال نزولی")
    else:
        st.warning("NO TRADE — منتظر تأیید بیشتر بمان")

    st.metric("امتیاز تکنیکال", f"{score:+d} از 6")

    st.write("**دلایل تحلیل:**")
    for reason in reasons:
        st.write(f"- {reason}")

    if signal != "NO TRADE" and last["ATR"] > 0:
        entry = float(last["close"])
        risk = 1.5 * float(last["ATR"])

        if signal == "BUY":
            sl = entry - risk
            tp1 = entry + risk
            tp2 = entry + 2 * risk
        else:
            sl = entry + risk
            tp1 = entry - risk
            tp2 = entry - 2 * risk

        st.subheader("سطوح تخمینی (نه تضمینی)")
        x1, x2, x3, x4 = st.columns(4)
        x1.metric("Entry مرجع", f"${entry:.2f}")
        x2.metric("Stop Loss", f"${sl:.2f}")
        x3.metric("Take Profit 1", f"${tp1:.2f}")
        x4.metric("Take Profit 2", f"${tp2:.2f}")

    chart = df.tail(100).set_index("datetime")
    st.subheader("نمودار قیمت و EMA")
    st.line_chart(chart[["close", "EMA20", "EMA50", "EMA200"]])

    with st.expander("اندیکاتورهای بیشتر"):
        st.line_chart(
            chart[["BB_upper", "BB_middle", "BB_lower", "close"]]
        )
        st.line_chart(
            chart[["MACD", "MACD_SIGNAL", "MACD_HIST"]]
        )

    return {
        "signal": signal,
        "score": score,
        "price": float(last["close"]),
        "atr": float(last["ATR"]),
        "datetime": last["datetime"]
    }


# ==========================================
# MULTI-TIMEFRAME CONFIRMATION
# ==========================================

def multi_timeframe_analysis():
    intervals = {
        "5 دقیقه": "5min",
        "15 دقیقه": "15min",
        "1 ساعت": "1h",
        "4 ساعت": "4h"
    }

    results = {}
    progress = st.progress(0)

    for index, (name, interval) in enumerate(intervals.items()):
        frame = fetch_gold_candles(interval, 250)
        frame = afg_add_indicators(frame)
        signal, score, reasons = afg_generate_signal(frame)
        last = frame.iloc[-1]

        results[name] = {
            "signal": signal,
            "score": score,
            "price": float(last["close"]),
            "atr": float(last["ATR"]),
            "datetime": last["datetime"]
        }
        progress.progress((index + 1) / len(intervals))

    st.subheader("نتیجه هر تایم‌فریم")
    for name, item in results.items():
        st.write(
            f"**{name}:** {item['signal']} | "
            f"امتیاز: {item['score']:+d} | "
            f"قیمت: ${item['price']:.2f}"
        )

    buy_count = sum(v["signal"] == "BUY" for v in results.values())
    sell_count = sum(v["signal"] == "SELL" for v in results.values())

    final_signal = "NO TRADE"
    if (
        results["1 ساعت"]["signal"] == "BUY"
        and results["4 ساعت"]["signal"] == "BUY"
        and buy_count >= 3
    ):
        final_signal = "BUY"
    elif (
        results["1 ساعت"]["signal"] == "SELL"
        and results["4 ساعت"]["signal"] == "SELL"
        and sell_count >= 3
    ):
        final_signal = "SELL"

    st.divider()
    st.subheader("سیگنال نهایی چندتایم‌فریمی")

    if final_signal == "BUY":
        st.success("BUY — روند صعودی در تایم‌فریم‌های بالاتر تأیید شده")
    elif final_signal == "SELL":
        st.error("SELL — روند نزولی در تایم‌فریم‌های بالاتر تأیید شده")
    else:
        st.warning("NO TRADE — تأیید کافی وجود ندارد")

    if final_signal != "NO TRADE":
        entry = results["15 دقیقه"]["price"]
        atr = results["15 دقیقه"]["atr"]
        risk = 1.5 * atr

        if final_signal == "BUY":
            sl, tp1, tp2 = entry - risk, entry + risk, entry + 2 * risk
        else:
            sl, tp1, tp2 = entry + risk, entry - risk, entry - 2 * risk

        a, b, c, d = st.columns(4)
        a.metric("Entry مرجع", f"${entry:.2f}")
        b.metric("Stop Loss", f"${sl:.2f}")
        c.metric("TP1", f"${tp1:.2f}")
        d.metric("TP2", f"${tp2:.2f}")


# ==========================================
# BACKTESTING
# ==========================================

def afg_backtest(df, initial_capital=500, risk_percent=1,
                 cost_per_ounce=0):

    if initial_capital <= 0:
        raise ValueError("سرمایه اولیه باید بیشتر از صفر باشد.")
    if not 0 < risk_percent <= 100:
        raise ValueError("درصد ریسک باید بین صفر و 100 باشد.")
    if cost_per_ounce < 0:
        raise ValueError("هزینه معامله نمی‌تواند منفی باشد.")

    df = afg_add_indicators(df.copy()).reset_index(drop=True)

    score = pd.Series(0, index=df.index)

    score += (
        (df["EMA20"] > df["EMA50"]) &
        (df["EMA50"] > df["EMA200"])
    ).astype(int) * 2

    score -= (
        (df["EMA20"] < df["EMA50"]) &
        (df["EMA50"] < df["EMA200"])
    ).astype(int) * 2

    score += (df["close"] > df["EMA20"]).astype(int)
    score -= (df["close"] < df["EMA20"]).astype(int)

    score += ((df["RSI"] > 50) & (df["RSI"] < 70)).astype(int)
    score -= ((df["RSI"] > 30) & (df["RSI"] < 50)).astype(int)

    score += (df["MACD"] > df["MACD_SIGNAL"]).astype(int)
    score -= (df["MACD"] < df["MACD_SIGNAL"]).astype(int)

    score += (
        (df["ADX"] >= 20) & (df["PLUS_DI"] > df["MINUS_DI"])
    ).astype(int)

    score -= (
        (df["ADX"] >= 20) & (df["MINUS_DI"] > df["PLUS_DI"])
    ).astype(int)

    df["SCORE"] = score

    equity = float(initial_capital)
    peak = equity
    max_drawdown = 0.0
    trades = []
    i = 200

    while i < len(df) - 1 and equity > 0:
        current = df.iloc[i]

        if current["SCORE"] >= 4:
            direction = "BUY"
        elif current["SCORE"] <= -4:
            direction = "SELL"
        else:
            i += 1
            continue

        atr = float(current["ATR"])
        entry_index = i + 1
        entry = float(df.iloc[entry_index]["open"])

        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(entry) or entry <= 0:
            i += 1
            continue

        stop_distance = 1.5 * atr
        target_distance = 2.0 * stop_distance

        # cost_per_ounce is the TOTAL round-trip cost per ounce.
        risk_per_unit = stop_distance + cost_per_ounce
        risk_amount = equity * risk_percent / 100
        units = min(risk_amount / risk_per_unit, equity / entry)

        if units <= 0:
            i += 1
            continue

        if direction == "BUY":
            stop = entry - stop_distance
            target = entry + target_distance
        else:
            stop = entry + stop_distance
            target = entry - target_distance

        exit_price = None
        exit_index = len(df) - 1
        exit_reason = "END OF DATA"

        for j in range(entry_index, len(df)):
            candle = df.iloc[j]
            op = float(candle["open"])
            hi = float(candle["high"])
            lo = float(candle["low"])
            close = float(candle["close"])

            if direction == "BUY":
                hit_stop = lo <= stop
                hit_target = hi >= target

                if hit_stop:
                    exit_price = op if op < stop else stop
                    exit_reason = "STOP LOSS"
                    exit_index = j
                    break
                if hit_target:
                    exit_price = target
                    exit_reason = "TAKE PROFIT"
                    exit_index = j
                    break

                worst_pnl = (lo - entry) * units
                close_pnl = (close - entry) * units

            else:
                hit_stop = hi >= stop
                hit_target = lo <= target

                if hit_stop:
                    exit_price = op if op > stop else stop
                    exit_reason = "STOP LOSS"
                    exit_index = j
                    break
                if hit_target:
                    exit_price = target
                    exit_reason = "TAKE PROFIT"
                    exit_index = j
                    break

                worst_pnl = (entry - hi) * units
                close_pnl = (entry - close) * units

            worst_equity = equity + worst_pnl - cost_per_ounce * units
            close_equity = equity + close_pnl - cost_per_ounce * units
            peak = max(peak, close_equity)

            if peak > 0:
                max_drawdown = max(
                    max_drawdown,
                    (peak - worst_equity) / peak * 100
                )

        if exit_price is None:
            exit_price = float(df.iloc[-1]["close"])

        if direction == "BUY":
            gross_pnl = (exit_price - entry) * units
        else:
            gross_pnl = (entry - exit_price) * units

        trading_cost = cost_per_ounce * units
        net_pnl = gross_pnl - trading_cost
        equity += net_pnl
        peak = max(peak, equity)

        if peak > 0:
            max_drawdown = max(
                max_drawdown,
                (peak - equity) / peak * 100
            )

        trades.append({
            "Direction": direction,
            "Entry Time": df.iloc[entry_index]["datetime"],
            "Exit Time": df.iloc[exit_index]["datetime"],
            "Entry": round(entry, 2),
            "Exit": round(exit_price, 2),
            "Units": round(units, 4),
            "Gross PnL ($)": round(gross_pnl, 4),
            "Cost ($)": round(trading_cost, 4),
            "Net PnL ($)": round(net_pnl, 4),
            "Result": "WIN" if net_pnl > 0 else "LOSS",
            "Exit Reason": exit_reason,
            "Equity ($)": round(equity, 2)
        })

        i = exit_index + 1

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return trades_df, {
            "final_equity": equity,
            "net_profit": equity - initial_capital,
            "win_rate": 0.0,
            "max_drawdown": max_drawdown,
            "total_trades": 0,
            "profit_factor": None
        }

    wins = trades_df[trades_df["Net PnL ($)"] > 0]
    losses = trades_df[trades_df["Net PnL ($)"] < 0]

    gross_wins = wins["Net PnL ($)"].sum()
    gross_losses = abs(losses["Net PnL ($)"].sum())

    profit_factor = gross_wins / gross_losses if gross_losses > 0 else None

    stats = {
        "final_equity": equity,
        "net_profit": equity - initial_capital,
        "win_rate": len(wins) / len(trades_df) * 100,
        "max_drawdown": max_drawdown,
        "total_trades": len(trades_df),
        "profit_factor": profit_factor
    }

    return trades_df, stats


# ==========================================
# STREAMLIT INTERFACE
# ==========================================

st.sidebar.title("AFG AI GOLD PRO")
section = st.sidebar.radio(
    "بخش مورد نظر",
    [
        "تحلیل یک تایم‌فریم",
        "تأیید چندتایم‌فریمی",
        "Backtesting"
    ]
)

if section == "تحلیل یک تایم‌فریم":
    tf_name = st.selectbox("انتخاب تایم‌فریم طلا", list(TIMEFRAMES.keys()))
    if st.button("اجرای تحلیل طلا", type="primary"):
        try:
            with st.spinner("در حال دریافت و تحلیل اطلاعات طلا..."):
                frame = fetch_gold_candles(TIMEFRAMES[tf_name], 250)
                result = show_signal(frame, tf_name)
        except Exception as exc:
            st.error(f"خطا در تحلیل طلا: {exc}")

elif section == "تأیید چندتایم‌فریمی":
    st.info(
        "برای سیگنال نهایی، 5m و 15m و 1h و 4h بررسی می‌شوند. "
        "تأیید تایم‌فریم‌های 1h و 4h الزامی است."
    )
    if st.button("اجرای تأیید چهار تایم‌فریم", type="primary"):
        try:
            with st.spinner("در حال بررسی چهار تایم‌فریم..."):
                multi_timeframe_analysis()
        except Exception as exc:
            st.error(f"خطا در تحلیل چندتایم‌فریمی: {exc}")

else:
    st.subheader("آزمایش استراتژی با سرمایه فرضی 500 دلار")
    bt_name = st.selectbox(
        "تایم‌فریم Backtesting",
        ["5 دقیقه", "15 دقیقه", "1 ساعت", "4 ساعت"]
    )
    bt_cost = st.number_input(
        "هزینه مجموع ورود و خروج برای هر اونس (دلار)",
        min_value=0.0,
        value=0.0,
        step=0.05
    )

    st.info(
        "سرمایه اولیه: 500 دلار | ریسک هدف هر معامله: 1% | "
        "حد ضرر: 1.5 ATR | حد سود: 2R"
    )

    if st.button("اجرای Backtesting", type="primary"):
        try:
            with st.spinner("در حال دریافت داده تاریخی و اجرای آزمایش..."):
                bt_df = fetch_gold_candles(TIMEFRAMES[bt_name], 500)
                trades, stats = afg_backtest(
                    bt_df,
                    initial_capital=500,
                    risk_percent=1,
                    cost_per_ounce=bt_cost
                )

            st.success("Backtesting تکمیل شد.")

            a, b, c = st.columns(3)
            a.metric("سرمایه نهایی", f"${stats['final_equity']:.2f}")
            b.metric("سود / زیان خالص", f"${stats['net_profit']:.2f}")
            c.metric("درصد معاملات برنده", f"{stats['win_rate']:.1f}%")

            d, e, f = st.columns(3)
            d.metric("تعداد معاملات", stats["total_trades"])
            e.metric("Max Drawdown", f"{stats['max_drawdown']:.2f}%")
            pf = stats["profit_factor"]
            f.metric("Profit Factor", f"{pf:.2f}" if pf is not None else "N/A")

            if not trades.empty:
                st.subheader("تاریخچه معاملات")
                st.dataframe(trades, use_container_width=True)

                st.subheader("منحنی سرمایه")
                equity_curve = [500] + trades["Equity ($)"].tolist()
                st.line_chart(pd.DataFrame({"Equity ($)": equity_curve}))
            else:
                st.warning("در داده‌های دریافت‌شده معامله‌ای مطابق قوانین پیدا نشد.")

            st.caption(
                "این آزمایش شبیه‌سازی است، نه نتیجه تضمینی. "
                "هزینه واقعی بروکر، اسپرد، لغزش، کمیسیون، سوآپ، "
                "اهرم و اندازه قرارداد ممکن است متفاوت باشد."
            )

        except Exception as exc:
            st.error(f"خطا در Backtesting: {exc}")


# ==========================================
# FOOTER
# ==========================================

st.divider()
st.caption(
    "AFG AI GOLD PRO | Technical rule-based analysis. "
    "این برنامه سفارش واقعی ثبت نمی‌کند و توصیه مالی نیست. "
    "پیش از استفاده واقعی، داده و نتایج را مستقل بررسی کن."
)
