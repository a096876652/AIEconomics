import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# 優先使用 Streamlit Secrets，若無則讓學生在側邊欄輸入
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 1. 抓取 FRED 數據 (設快取 1 小時)
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    return df

# 2. 抓取 Market 數據 (設快取 10 分鐘)
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
    return df

# 頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心 KPI 卡片
        st.subheader("📊 關鍵總體經濟指標 (FRED)")
        col1, col2, col3, col4 = st.columns(4)
        
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        
        latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        col3.metric("美國失業率", f"{latest_unemp:.1f}%")
        
        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
        col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")

        # 第二區塊：互動式圖表
        st.write("---")
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
    
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

from fredapi import Fred
from google import genai


# ==========================================
# 1. PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Global Macro Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("🌎 GLOBAL MACRO DASHBOARD")
st.caption("Macroeconomic & Financial Market Monitor")

st.divider()


# ==========================================
# 2. API CONFIGURATION
# ==========================================

FRED_API_KEY = st.secrets["FRED_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


# ==========================================
# 3. DATA DICTIONARIES
# ==========================================

YFINANCE_TICKERS = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Gold Futures": "GC=F",
    "US Dollar Index": "DX-Y.NYB"
}

FRED_SERIES = {
    "CPI": "CPIAUCSL",
    "Unemployment": "UNRATE",
    "Fed Funds Rate": "FEDFUNDS",
    "US 10Y": "DGS10",
    "US 2Y": "DGS2",
    "Japan 10Y": "IRLTLT01JPM156N"
}


# ==========================================
# 4. FRED DATA FETCHING
# ==========================================

@st.cache_data(ttl=3600)
def load_fred_data(api_key):

    fred = Fred(api_key=api_key)

    data = {}

    for name, series_id in FRED_SERIES.items():

        try:
            data[name] = fred.get_series(
                series_id,
                observation_start="2015-01-01"
            )

        except Exception as e:
            st.warning(f"{name} data error: {e}")

    return pd.DataFrame(data)


# ==========================================
# 5. YFINANCE DATA FETCHING
# ==========================================

@st.cache_data(ttl=300)
def load_market_data():

    data = {}

    for name, ticker in YFINANCE_TICKERS.items():

        try:
            df = yf.Ticker(ticker).history(
                period="5y",
                interval="1d"
            )

            if not df.empty:
                data[name] = df["Close"].dropna()

        except Exception as e:
            st.warning(f"{name} fetch error: {e}")

    return data


# ==========================================
# 6. LOAD DATA
# ==========================================

with st.spinner("Loading macroeconomic data..."):

    fred_df = load_fred_data(FRED_API_KEY)
    market_data = load_market_data()

if fred_df.empty:
    st.error("FRED data unavailable. Please check API settings.")
    st.stop()


# ==========================================
# 7. HELPER FUNCTION
# ==========================================

def latest_value(column):

    series = fred_df[column].dropna()

    if series.empty:
        return None, None

    return float(series.iloc[-1]), series.index[-1]


# ==========================================
# 8. MARKET OVERVIEW
# ==========================================

st.header("📈 Financial Market Overview")

market_columns = st.columns(4)

for col, name in zip(
    market_columns,
    YFINANCE_TICKERS.keys()
):

    series = market_data.get(name)

    with col:

        if series is not None and not series.empty:

            latest = float(series.iloc[-1])

            st.metric(
                label=name,
                value=f"{latest:,.2f}"
            )

        else:
            st.metric(name, "N/A")


# Gold price chart
if "Gold Futures" in market_data:

    gold = market_data["Gold Futures"]

    fig_gold = px.line(
        x=gold.index,
        y=gold.values,
        title="COMEX Gold Futures (GC=F)",
        labels={"x": "Date", "y": "USD"}
    )

    fig_gold.update_layout(
        template="plotly_dark",
        height=350
    )

    st.plotly_chart(
        fig_gold,
        use_container_width=True
    )


# ==========================================
# 9. MACROECONOMIC INDICATORS
# ==========================================

st.header("🌐 US Macroeconomic Indicators")

cpi_value, cpi_date = latest_value("CPI")
unemployment, unemployment_date = latest_value(
    "Unemployment"
)
fed_rate, fed_rate_date = latest_value(
    "Fed Funds Rate"
)

# CPI year-over-year calculation
cpi_series = fred_df["CPI"].dropna()

if len(cpi_series) >= 13:

    cpi_yoy = (
        cpi_series.iloc[-1] /
        cpi_series.iloc[-13] - 1
    ) * 100

else:
    cpi_yoy = None


macro_cols = st.columns(3)

with macro_cols[0]:

    st.metric(
        "CPI YoY",
        f"{cpi_yoy:.2f}%" if cpi_yoy is not None else "N/A"
    )

with macro_cols[1]:

    st.metric(
        "Unemployment Rate",
        f"{unemployment:.2f}%" if unemployment is not None else "N/A"
    )

with macro_cols[2]:

    st.metric(
        "Federal Funds Rate",
        f"{fed_rate:.2f}%" if fed_rate is not None else "N/A"
    )

st.caption(
    "CPI uses CPIAUCSL index to calculate year-over-year "
    "change. Other indicators use their latest available observations."
)


# ==========================================
# 10. JAPAN 10Y GOVERNMENT BOND YIELD
# ==========================================

st.header("🇯🇵 Japan Government Bond Market")

japan_yield, japan_date = latest_value("Japan 10Y")

st.metric(
    "Japan 10-Year Government Bond Yield",
    f"{japan_yield:.3f}%" if japan_yield is not None else "N/A"
)

japan_series = fred_df["Japan 10Y"].dropna()

if not japan_series.empty:

    fig_japan = px.line(
        x=japan_series.index,
        y=japan_series.values,
        title="Japan 10Y Government Bond Yield",
        labels={
            "x": "Date",
            "y": "Yield (%)"
        }
    )

    fig_japan.update_layout(
        template="plotly_dark",
        height=350
    )

    st.plotly_chart(
        fig_japan,
        use_container_width=True
    )

st.caption(
    "Source: FRED / OECD. Monthly, not seasonally adjusted."
)


# ==========================================
# 11. US TREASURY YIELD CURVE
# ==========================================

st.divider()

st.header("📉 US Treasury Yield Curve Monitor")

yield_df = fred_df[["US 10Y", "US 2Y"]].dropna()

yield_df["Spread"] = (
    yield_df["US 10Y"] - yield_df["US 2Y"]
)

if not yield_df.empty:

    latest_spread = float(
        yield_df["Spread"].iloc[-1]
    )

    spread_date = yield_df.index[-1]

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "10Y - 2Y Spread",
            f"{latest_spread:.2f} percentage points",
            help="DGS10 minus DGS2"
        )

    with col2:

        if latest_spread < 0:

            st.error(
                f"🔴 WARNING: Yield Curve Inversion! "
                f"Spread = {latest_spread:.2f}%"
            )

        else:

            st.success(
                f"🟢 NORMAL: Positive Yield Spread "
                f"= {latest_spread:.2f}%"
            )

    # Historical spread chart

    fig_spread = px.line(
        yield_df,
        x=yield_df.index,
        y="Spread",
        title="US Treasury 10Y - 2Y Yield Spread",
        labels={
            "Spread": "Spread (%)",
            "Date": "Date"
        }
    )

    fig_spread.add_hline(
        y=0,
        line_dash="dash",
        line_color="red",
        annotation_text="Yield Curve Inversion"
    )

    fig_spread.update_layout(
        template="plotly_dark",
        height=450,
        hovermode="x unified"
    )

    st.plotly_chart(
        fig_spread,
        use_container_width=True
    )

    st.caption(
        f"Latest available observation: {spread_date:%Y-%m-%d}. "
        "Spread below zero indicates yield curve inversion."
    )


# ==========================================
# 12. AI MACROECONOMIC ANALYSIS
# ==========================================

st.divider()

st.header("🤖 AI Macroeconomic Research")

st.write(
    "Use the latest available economic indicators "
    "to generate an AI macroeconomic commentary."
)

if st.button(
    "✨ 產生 AI 總體經濟摘要",
    type="primary",
    use_container_width=True
):

    # Validate inputs
    if any(
        value is None
        for value in [
            cpi_yoy,
            unemployment,
            fed_rate
        ]
    ):

        st.error("Economic data incomplete. Cannot generate analysis.")

    else:

        with st.spinner("Gemini is analyzing the economy..."):

            try:

                prompt = f"""
                你是一位華爾街頂尖總體經濟分析師。

                請根據以下真實經濟數據，
                撰寫約200字的繁體中文總體經濟短評。

                【最新經濟數據】

                CPI YoY: {cpi_yoy:.2f}%
                CPI observation date: {cpi_date}

                Unemployment Rate: {unemployment:.2f}%
                Unemployment observation date: {unemployment_date}

                Federal Funds Rate: {fed_rate:.2f}%
                Fed Funds observation date: {fed_rate_date}

                【分析要求】

                1. 分析目前美國通膨趨勢。
                2. 評估勞動市場是否降溫。
                3. 分析聯準會未來貨幣政策方向。
                4. 說明對美債、美元及股票市場的可能影響。

                請使用專業投資銀行研究報告口吻。
                不可虛構數據，不可把推測寫成事實。
                必須區分數據事實與分析判斷。
                請控制在約200個中文字。
                """

                client = genai.Client(
                    api_key=GEMINI_API_KEY
                )

                try:
                    response = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=prompt
                    )
                finally:
                    client.close()

                if response.text:

                    st.success("AI Analysis Completed")

                    st.markdown("### 📊 AI Macro Commentary")

                    st.markdown(response.text)

                else:

                    st.warning("Gemini returned an empty response.")

            except Exception as e:

                st.error(f"Gemini API Error: {e}")


# ==========================================
# 13. FOOTER
# ==========================================

st.divider()

st.caption(
    "Data Sources: Yahoo Finance | FRED | OECD | Google Gemini"
)

st.caption(
    "For informational and educational purposes only. "
    "Not investment advice."
)

