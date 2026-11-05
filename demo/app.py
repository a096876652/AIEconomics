
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from fredapi import Fred
from google import genai
from datetime import datetime

# =========================================================
# 1. 頁面設定與深色金融終端風格
# =========================================================

st.set_page_config(
    page_title="全球總體經濟金融儀表板",
    page_icon="🌐",
    layout="wide"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0b1120;
        color: #e5e7eb;
    }
    [data-testid="stSidebar"] {
        background-color: #111827;
    }
    [data-testid="stMetric"] {
        background-color: #172235;
        border: 1px solid #26364d;
        padding: 15px;
        border-radius: 10px;
    }
    h1, h2, h3 {
        color: #e5e7eb;
    }
    div[data-testid="stAlert"] {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌐 全球總體經濟與金融指標儀表板")
st.caption("GLOBAL MACROECONOMIC & FINANCIAL DASHBOARD")

# =========================================================
# 2. 側邊欄設定
# =========================================================

st.sidebar.header("⚙️ 系統設定")


def get_secret(key):
    """安全讀取 Streamlit Secrets，沒有設定時回傳空字串。"""
    try:
        return st.secrets[key]
    except Exception:
        return ""


fred_secret = get_secret("FRED_API_KEY")
gemini_secret = get_secret("GEMINI_API_KEY")

fred_key = st.sidebar.text_input(
    "FRED API Key",
    value=fred_secret,
    type="password"
)

gemini_key = st.sidebar.text_input(
    "Gemini API Key",
    value=gemini_secret,
    type="password"
)

if st.sidebar.button("🔄 手動刷新所有數據", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("資料來源：FRED、Yahoo Finance")
st.sidebar.caption("資料更新時間依各來源發布頻率而異。")

# =========================================================
# 3. FRED 總體經濟數據
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_fred_data(api_key):

    fred = Fred(api_key=api_key)

    series_ids = {
        "CPI 物價指數": "CPIAUCSL",
        "10年期美債殖利率": "DGS10",
        "2年期美債殖利率": "DGS2",
        "美國失業率": "UNRATE",
        "聯邦基金利率": "FEDFUNDS",
        "日本10年期公債殖利率（月頻）": "IRLTLT01JPM156N"
    }

    data = {}
    errors = {}

    for name, series_id in series_ids.items():
        try:
            series = fred.get_series(series_id)
            series = pd.to_numeric(series, errors="coerce")
            series.index = pd.to_datetime(series.index)
            series = series.dropna()

            if not series.empty:
                data[name] = series
            else:
                errors[name] = "沒有取得有效資料"

        except Exception as e:
            errors[name] = str(e)

    if not data:
        raise ValueError("FRED 沒有回傳任何有效資料。")

    # 不對不同頻率資料做 ffill，避免月頻資料被誤當成每日更新
    macro_df = pd.concat(data, axis=1).sort_index()

    return macro_df, errors


# =========================================================
# 4. Yahoo Finance 金融市場數據
# =========================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_market_data():

    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元／台幣匯率": "TWD=X",
        "黃金（COMEX期貨）": "GC=F"
    }

    data = {}
    errors = {}

    for name, ticker in tickers.items():
        try:
            history = yf.Ticker(ticker).history(
                period="1y",
                auto_adjust=False
            )

            if history.empty or "Close" not in history.columns:
                errors[name] = "沒有取得有效行情"
                continue

            close = history["Close"].dropna()

            if not close.empty:
                close.index = pd.to_datetime(close.index).tz_localize(None)
                data[name] = close
            else:
                errors[name] = "收盤價資料為空"

        except Exception as e:
            errors[name] = str(e)

    if not data:
        raise ValueError("Yahoo Finance 沒有回傳任何有效行情。")

    market_df = pd.concat(data, axis=1).sort_index()

    return market_df, errors


# =========================================================
# 5. 共用工具：安全取得最新數值
# =========================================================

def latest_value(df, column):
    if column not in df.columns:
        return None

    series = df[column].dropna()

    if series.empty:
        return None

    return float(series.iloc[-1])


def latest_date(df, column):
    if column not in df.columns:
        return None

    series = df[column].dropna()

    if series.empty:
        return None

    return series.index[-1]


def metric_value(value, suffix="", digits=2):
    if value is None:
        return "暫無資料"

    return f"{value:,.{digits}f}{suffix}"


# =========================================================
# 6. 讀取資料並顯示儀表板
# =========================================================

if not fred_key:
    st.info("請在左側輸入 FRED API Key，才能讀取總體經濟資料。")
    st.stop()

try:
    with st.spinner("正在讀取 FRED 總體經濟資料..."):
        macro_df, fred_errors = get_fred_data(fred_key)

except Exception as e:
    st.error(f"FRED 資料讀取失敗：{e}")
    st.stop()

try:
    with st.spinner("正在讀取全球金融市場行情..."):
        market_df, market_errors = get_market_data()

except Exception as e:
    st.warning(f"市場行情讀取失敗：{e}")
    market_df = pd.DataFrame()
    market_errors = {"市場行情": str(e)}


# =========================================================
# 7. 計算美國 10Y - 2Y 利差
# =========================================================

spread = None

if (
    "10年期美債殖利率" in macro_df.columns
    and "2年期美債殖利率" in macro_df.columns
):
    spread = (
        macro_df["10年期美債殖利率"]
        - macro_df["2年期美債殖利率"]
    ).dropna()


# =========================================================
# 8. 核心總體經濟 KPI
# =========================================================

st.divider()
st.subheader("📊 美國核心總體經濟指標")

cpi = latest_value(macro_df, "CPI 物價指數")
yield_10y = latest_value(macro_df, "10年期美債殖利率")
unemployment = latest_value(macro_df, "美國失業率")
fed_rate = latest_value(macro_df, "聯邦基金利率")

cols = st.columns(4)

cols[0].metric(
    "CPI 物價指數",
    metric_value(cpi, digits=1)
)

cols[1].metric(
    "美國10年期公債殖利率",
    metric_value(yield_10y, "%")
)

cols[2].metric(
    "美國失業率",
    metric_value(unemployment, "%")
)

cols[3].metric(
    "聯邦基金利率",
    metric_value(fed_rate, "%")
)


# =========================================================
# 9. 美國公債殖利率曲線與倒掛警示
# =========================================================

st.divider()
st.subheader("🇺🇸 美國公債殖利率與期限利差")

if spread is not None and not spread.empty:

    latest_spread = float(spread.iloc[-1])
    spread_date = spread.index[-1]

    col1, col2 = st.columns(2)

    col1.metric(
        "美國10Y－2Y利差",
        f"{latest_spread:+.2f} 個百分點",
        help="10年期公債殖利率減去2年期公債殖利率"
    )

    col2.metric(
        "最新資料日期",
        spread_date.strftime("%Y-%m-%d")
    )

    if latest_spread < 0:
        st.warning(
            "⚠️ 美國殖利率曲線倒掛：10年期殖利率低於2年期殖利率。"
            "歷史上倒掛曾與經濟衰退風險上升相關，但並非衰退必然發生的訊號。"
        )
    else:
        st.success(
            "目前10Y－2Y利差為正值，殖利率曲線未呈現倒掛。"
        )

    fig_spread = go.Figure()

    fig_spread.add_trace(
        go.Scatter(
            x=spread.index,
            y=spread.values,
            mode="lines",
            name="10Y－2Y Spread",
            line=dict(color="#38bdf8", width=2)
        )
    )

    fig_spread.add_hline(
        y=0,
        line_dash="dash",
        line_color="red",
        annotation_text="零軸／倒掛界線"
    )

    fig_spread.update_layout(
        title="美國10年期－2年期公債殖利率利差",
        xaxis_title="日期",
        yaxis_title="利差（百分點）",
        template="plotly_dark",
        height=420,
        hovermode="x unified"
    )

    st.plotly_chart(fig_spread, use_container_width=True)

else:
    st.warning("目前無法計算美國10Y－2Y利差，請檢查 FRED 資料。")


# =========================================================
# 10. 日本10年期公債殖利率
# =========================================================

st.divider()
st.subheader("🇯🇵 日本10年期公債殖利率")

japan_name = "日本10年期公債殖利率（月頻）"
japan_yield = latest_value(macro_df, japan_name)
japan_date = latest_date(macro_df, japan_name)

if japan_yield is not None:

    st.metric(
        "日本10年期公債殖利率",
        f"{japan_yield:.2f}%",
        help="FRED：IRLTLT01JPM156N，OECD 月頻資料，非即時日行情"
    )

    st.caption(
        f"最新資料日期：{japan_date:%Y-%m-%d}｜"
        "資料頻率：月頻，並非即時報價。"
    )

    japan_chart = macro_df[[japan_name]].dropna()

    fig_japan = px.line(
        japan_chart,
        y=japan_name,
        title="日本10年期公債殖利率（月頻）"
    )

    fig_japan.update_layout(
        template="plotly_dark",
        height=350,
        yaxis_title="殖利率（%）"
    )

    st.plotly_chart(fig_japan, use_container_width=True)

else:
    st.warning("目前無法取得日本10年期公債殖利率資料。")


# =========================================================
# 11. 全球金融市場行情
# =========================================================

st.divider()
st.subheader("📈 全球金融市場行情")

if not market_df.empty:

    market_choice = st.selectbox(
        "選擇金融市場標的",
        market_df.columns.tolist()
    )

    selected_market = market_df[market_choice].dropna()

    if not selected_market.empty:

        latest_market = float(selected_market.iloc[-1])
        previous_market = (
            float(selected_market.iloc[-2])
            if len(selected_market) >= 2 else None
        )

        change = (
            latest_market - previous_market
            if previous_market is not None else None
        )

        st.metric(
            f"{market_choice} 最新價格",
            f"{latest_market:,.2f}",
            f"{change:+,.2f}" if change is not None else None
        )

        fig_market = px.line(
            selected_market,
            title=f"{market_choice} 近一年走勢"
        )

        fig_market.update_layout(
            template="plotly_dark",
            height=430,
            xaxis_title="日期",
            yaxis_title="價格／指數"
        )

        st.plotly_chart(fig_market, use_container_width=True)

    if market_choice == "黃金（COMEX期貨）":
        st.caption(
            "注意：GC=F 為 Yahoo Finance 上的 COMEX 黃金期貨報價，"
            "不是嚴格定義的倫敦現貨黃金（Spot Gold）價格。"
        )

else:
    st.warning("目前沒有可顯示的市場行情。")


# =========================================================
# 12. FRED 總體經濟歷史圖表
# =========================================================

st.divider()
st.subheader("📉 美國總體經濟指標歷史走勢")

macro_options = [
    col for col in macro_df.columns
    if not macro_df[col].dropna().empty
]

if macro_options:

    macro_choice = st.selectbox(
        "選擇總體經濟指標",
        macro_options
    )

    selected_macro = macro_df[macro_choice].dropna()

    fig_macro = px.line(
        selected_macro,
        title=f"{macro_choice} 歷史走勢"
    )

    fig_macro.update_layout(
        template="plotly_dark",
        height=400,
        xaxis_title="日期",
        yaxis_title="數值"
    )

    st.plotly_chart(fig_macro, use_container_width=True)


# =========================================================
# 13. AI 總體經濟摘要
# =========================================================

st.divider()
st.subheader("🤖 AI 總體經濟分析")
st.write(
    "使用最新取得的美國 CPI、失業率與聯邦基金利率，"
    "生成約200字的繁體中文總體經濟評論。"
)

if st.button(
    "✨ 產生 AI 總體經濟摘要",
    use_container_width=True,
    type="primary"
):

    if not gemini_key:
        st.error(
            "尚未設定 Gemini API Key。"
            "請在左側輸入，或在 Streamlit Cloud 的 Secrets 設定。"
        )

    elif cpi is None or unemployment is None or fed_rate is None:
        st.error("CPI、失業率或聯邦基金利率資料不足，無法產生摘要。")

    else:
        try:
            with st.spinner("AI 正在分析最新總體經濟數據..."):

                client = genai.Client(api_key=gemini_key)

                cpi_date = latest_date(macro_df, "CPI 物價指數")
                unemp_date = latest_date(macro_df, "美國失業率")
                fed_date = latest_date(macro_df, "聯邦基金利率")

                spread_text = (
                    f"{latest_spread:.2f} 個百分點"
                    if spread is not None and not spread.empty
                    else "目前無資料"
                )

                prompt = f"""
你是一位華爾街投資銀行的總體經濟研究分析師。

請根據以下數據，撰寫約200字的繁體中文總體經濟評論。

【最新經濟數據】
CPI物價指數：{cpi:.2f}
CPI資料日期：{cpi_date:%Y-%m-%d}

美國失業率：{unemployment:.2f}%
失業率資料日期：{unemp_date:%Y-%m-%d}

聯邦基金利率：{fed_rate:.2f}%
利率資料日期：{fed_date:%Y-%m-%d}

美國10Y-2Y利差：{spread_text}

【分析要求】
1. 分析通膨、就業與貨幣政策的關係。
2. 評估目前美國經濟可能面臨的風險。
3. 說明對聯準會未來利率政策可能的影響。
4. 使用專業金融研究報告語氣。
5. 不可捏造數據，不可把 CPI 指數值誤稱為 CPI 年增率。
6. 如果缺少 CPI 年增率，請明確說明限制。
7. 約200字，使用繁體中文。
"""

                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt
                )

                result = response.text

                if result:
                    st.success("AI 總體經濟摘要已完成")
                    st.markdown(result)
                else:
                    st.warning("AI 沒有回傳文字，請稍後再試。")

        except Exception as e:
            st.error(f"Gemini AI 呼叫失敗：{e}")


# =========================================================
# 14. 資料來源與錯誤提示
# =========================================================

with st.expander("📚 資料來源與更新說明"):

    st.markdown("""
    **總體經濟資料**
    - FRED：Federal Reserve Economic Data
    - CPI：CPIAUCSL
    - 美國10年期公債殖利率：DGS10
    - 美國2年期公債殖利率：DGS2
    - 美國失業率：UNRATE
    - 聯邦基金利率：FEDFUNDS
    - 日本10年期公債殖利率：IRLTLT01JPM156N（月頻）

    **金融市場資料**
    - Yahoo Finance
    - S&P 500：^GSPC
    - 台灣加權指數：^TWII
    - 布蘭特原油：BZ=F
    - 美元／台幣：TWD=X
    - 黃金：GC=F（COMEX黃金期貨）

    **重要提醒**
    - FRED 各項資料發布頻率不同。
    - 日本公債殖利率序列為月頻，不代表即時市場報價。
    - GC=F 是期貨報價，不等同現貨黃金。
    - 市場行情可能延遲或因資料來源而缺漏。
    - AI 摘要僅作為研究輔助，不構成投資建議。
    """)

    if fred_errors:
        st.warning("部分 FRED 資料讀取失敗：")
        for name, error in fred_errors.items():
            st.write(f"- {name}：{error}")

    if market_errors:
        st.warning("部分市場行情讀取失敗：")
        for name, error in market_errors.items():
            st.write(f"- {name}：{error}")

st.divider()
st.caption(
    f"Dashboard｜最後載入時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
