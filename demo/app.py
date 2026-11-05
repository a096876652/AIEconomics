
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from google import genai


# ==========================================
# 0. PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="總體經濟與金融即時儀表板",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 全球總體經濟與金融指標即時儀表板")
st.caption("Global Macro & Financial Market Dashboard")


# ==========================================
# 1. SIDEBAR SETTINGS
# ==========================================

st.sidebar.header("⚙️ 設定與金鑰")

# FRED API Key
fred_key = st.secrets.get("FRED_API_KEY", "")

if fred_key:
    st.sidebar.success("已自動讀取 FRED API Key")
else:
    fred_key = st.sidebar.text_input(
        "請輸入 FRED API Key",
        type="password"
    )

# Gemini API Key
gemini_key = st.secrets.get("GEMINI_API_KEY", "")

if not gemini_key:
    gemini_key = st.sidebar.text_input(
        "請輸入 Gemini API Key",
        type="password"
    )

if st.sidebar.button("🔄 手動刷新數據"):
    st.cache_data.clear()
    st.rerun()


# ==========================================
# 2. DATA DICTIONARIES
# ==========================================

# Yahoo Finance
YFINANCE_TICKERS = {
    "S&P 500": "^GSPC",
    "台灣加權指數": "^TWII",
    "布蘭特原油": "BZ=F",
    "美元/台幣匯率": "TWD=X",
    "黃金期貨": "GC=F"
}

# FRED
FRED_SERIES = {
    "CPI 物價指數": "CPIAUCSL",
    "10年期美債殖利率": "DGS10",
    "2年期美債殖利率": "DGS2",
    "美國失業率": "UNRATE",
    "聯邦基金利率": "FEDFUNDS",
    "日本10年期公債殖利率": "IRLTLT01JPM156N"
}


# ==========================================
# 3. FRED DATA FETCHING
# ==========================================

@st.cache_data(ttl=3600)
def get_fred_data(api_key):

    fred = Fred(api_key=api_key)

    data = {}

    for name, series_id in FRED_SERIES.items():

        try:
            data[name] = fred.get_series(
                series_id,
                observation_start="2015-01-01"
            )

        except Exception as e:
            raise RuntimeError(
                f"FRED {name} 資料讀取失敗：{e}"
            )

    # 保留原始觀測日期，不使用 ffill
    df = pd.concat(data, axis=1)

    return df.sort_index()


# ==========================================
# 4. YAHOO FINANCE DATA FETCHING
# ==========================================

@st.cache_data(ttl=600)
def get_market_data():

    raw = yf.download(
        tickers=list(YFINANCE_TICKERS.values()),
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True
    )

    if raw.empty:
        raise RuntimeError("Yahoo Finance 沒有返回資料")

    # 取得收盤價
    market_df = raw["Close"].copy()

    # 修改欄位名稱
    market_df.rename(
        columns={
            ticker: name
            for name, ticker in YFINANCE_TICKERS.items()
        },
        inplace=True
    )

    return market_df.dropna(how="all")


# ==========================================
# 5. HELPER FUNCTIONS
# ==========================================

def get_latest(series):

    clean = series.dropna()

    if clean.empty:
        return None, None

    return float(clean.iloc[-1]), clean.index[-1]


def format_date(date):

    if date is None:
        return "N/A"

    return pd.Timestamp(date).strftime("%Y-%m-%d")


# ==========================================
# 6. MAIN DASHBOARD
# ==========================================

if not fred_key:

    st.info(
        "👈 請在左側輸入 FRED API Key 以開啟儀表板。"
    )

    st.stop()


try:

    with st.spinner("正在取得全球市場與總體經濟資料..."):

        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

    # ======================================
    # 7. CORE MACROECONOMIC INDICATORS
    # ======================================

    st.divider()
    st.subheader("📊 關鍵總體經濟指標")

    latest_cpi, cpi_date = get_latest(
        macro_df["CPI 物價指數"]
    )

    latest_10y, date_10y = get_latest(
        macro_df["10年期美債殖利率"]
    )

    latest_unemp, unemp_date = get_latest(
        macro_df["美國失業率"]
    )

    latest_fed, fed_date = get_latest(
        macro_df["聯邦基金利率"]
    )

    # CPI YoY
    cpi_series = macro_df["CPI 物價指數"].dropna()

    if len(cpi_series) >= 13:

        cpi_yoy = (
            cpi_series.iloc[-1] /
            cpi_series.iloc[-13] - 1
        ) * 100

    else:
        cpi_yoy = None

    # 10Y daily change
    treasury_10y = macro_df[
        "10年期美債殖利率"
    ].dropna()

    if len(treasury_10y) >= 2:

        change_10y = (
            treasury_10y.iloc[-1] -
            treasury_10y.iloc[-2]
        )

    else:
        change_10y = None

    # Yield spread
    yield_df = macro_df[
        [
            "10年期美債殖利率",
            "2年期美債殖利率"
        ]
    ].dropna()

    yield_df["10Y-2Y Spread"] = (
        yield_df["10年期美債殖利率"] -
        yield_df["2年期美債殖利率"]
    )

    latest_spread, spread_date = get_latest(
        yield_df["10Y-2Y Spread"]
    )

    # KPI cards
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "CPI 物價指數",
            f"{latest_cpi:.2f}" if latest_cpi is not None else "N/A"
        )

    with col2:
        st.metric(
            "CPI 年增率",
            f"{cpi_yoy:.2f}%" if cpi_yoy is not None else "N/A"
        )

    with col3:
        st.metric(
            "10年期美債",
            f"{latest_10y:.2f}%" if latest_10y is not None else "N/A",
            f"{change_10y:+.2f} 個百分點" if change_10y is not None else None
        )

    with col4:
        st.metric(
            "美國失業率",
            f"{latest_unemp:.2f}%" if latest_unemp is not None else "N/A"
        )

    with col5:
        st.metric(
            "聯邦基金利率",
            f"{latest_fed:.2f}%" if latest_fed is not None else "N/A"
        )

    st.caption(
        f"CPI：{format_date(cpi_date)} ｜ "
        f"10Y：{format_date(date_10y)} ｜ "
        f"失業率：{format_date(unemp_date)} ｜ "
        f"聯邦基金利率：{format_date(fed_date)}"
    )


    # ======================================
    # 8. FINANCIAL MARKET DATA
    # ======================================

    st.divider()
    st.subheader("📈 全球金融市場行情")

    market_cols = st.columns(5)

    for col, name in zip(
        market_cols,
        YFINANCE_TICKERS.keys()
    ):

        series = market_df[name].dropna()

        if not series.empty:

            latest = float(series.iloc[-1])

            with col:
                st.metric(
                    name,
                    f"{latest:,.2f}"
                )

        else:

            with col:
                st.metric(name, "N/A")


    # ======================================
    # 9. INTERACTIVE CHARTS
    # ======================================

    st.divider()

    st.subheader("📉 市場走勢與總體經濟趨勢")

    tab1, tab2, tab3 = st.tabs([
        "金融市場走勢",
        "總體經濟趨勢",
        "日本公債殖利率"
    ])

    with tab1:

        market_choice = st.selectbox(
            "選擇金融市場標的：",
            market_df.columns
        )

        fig1 = px.line(
            market_df,
            y=market_choice,
            title=f"{market_choice} 近一年走勢"
        )

        fig1.update_layout(
            template="plotly_dark",
            height=450,
            hovermode="x unified"
        )

        st.plotly_chart(
            fig1,
            use_container_width=True
        )

        st.caption(
            "黃金 GC=F 為 COMEX 黃金期貨報價，"
            "不是直接的現貨價格。"
        )

    with tab2:

        macro_choices = [
            c for c in macro_df.columns
            if macro_df[c].notna().any()
        ]

        macro_choice = st.selectbox(
            "選擇總體經濟指標：",
            macro_choices
        )

        selected_series = macro_df[
            macro_choice
        ].dropna()

        fig2 = px.line(
            x=selected_series.index,
            y=selected_series.values,
            title=f"{macro_choice} 歷史走勢",
            labels={
                "x": "Date",
                "y": macro_choice
            }
        )

        fig2.update_layout(
            template="plotly_dark",
            height=450
        )

        st.plotly_chart(
            fig2,
            use_container_width=True
        )

    with tab3:

        japan_series = macro_df[
            "日本10年期公債殖利率"
        ].dropna()

        japan_latest, japan_date = get_latest(
            japan_series
        )

        st.metric(
            "日本10年期公債殖利率",
            f"{japan_latest:.3f}%" if japan_latest is not None else "N/A"
        )

        st.caption(
            f"最新觀測日期：{format_date(japan_date)}"
        )

        if not japan_series.empty:

            fig_japan = px.line(
                x=japan_series.index,
                y=japan_series.values,
                title="Japan 10-Year Government Bond Yield",
                labels={
                    "x": "Date",
                    "y": "Yield (%)"
                }
            )

            fig_japan.update_layout(
                template="plotly_dark",
                height=450
            )

            st.plotly_chart(
                fig_japan,
                use_container_width=True
            )

        st.caption(
            "資料來源：OECD / FRED；月頻資料，"
            "並非日本公債每日即時殖利率。"
        )


    # ======================================
    # 10. US TREASURY YIELD SPREAD
    # ======================================

    st.divider()

    st.subheader("🇺🇸 美國公債殖利率曲線監控")

    if not yield_df.empty:

        spread_col1, spread_col2 = st.columns(2)

        with spread_col1:

            st.metric(
                "10Y - 2Y 利差",
                f"{latest_spread:.2f} 個百分點"
            )

        with spread_col2:

            if latest_spread < 0:

                st.error(
                    f"🔴 WARNING：美國殖利率曲線倒掛！"
                    f"目前利差為 {latest_spread:.2f} 個百分點。"
                )

            else:

                st.success(
                    f"🟢 NORMAL：殖利率曲線未倒掛。"
                    f"目前利差為 {latest_spread:.2f} 個百分點。"
                )

        st.caption(
            f"最新利差觀測日期：{format_date(spread_date)}"
        )

        # Historical spread chart
        fig_spread = px.line(
            yield_df,
            x=yield_df.index,
            y="10Y-2Y Spread",
            title="US Treasury 10Y - 2Y Yield Spread",
            labels={
                "10Y-2Y Spread": "Yield Spread (Percentage Points)",
                "Date": "Date"
            }
        )

        fig_spread.add_hline(
            y=0,
            line_dash="dash",
            line_color="red",
            annotation_text="Inversion Threshold"
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
            "利差 = DGS10 - DGS2。"
            "負值代表殖利率曲線倒掛；"
            "單位為百分點。"
        )

    else:

        st.warning("目前無法取得完整的 DGS10 / DGS2 資料。")


    # ======================================
    # 11. AI MACROECONOMIC SUMMARY
    # ======================================

    st.divider()

    st.subheader("🤖 AI 總體經濟分析")

    st.write(
        "使用最新 CPI、失業率與聯邦基金利率，"
        "由 Google Gemini 產生專業總體經濟短評。"
    )

    if st.button(
        "✨ 產生 AI 總體經濟摘要",
        type="primary",
        use_container_width=True
    ):

        if not gemini_key:

            st.error(
                "請先在左側輸入 Gemini API Key。"
            )

        elif any(
            value is None
            for value in [
                cpi_yoy,
                latest_unemp,
                latest_fed
            ]
        ):

            st.error(
                "經濟數據不足，無法產生完整分析。"
            )

        else:

            with st.spinner(
                "Gemini 正在分析最新總體經濟數據..."
            ):

                try:

                    client = genai.Client(
                        api_key=gemini_key
                    )

                    prompt = f"""
你是一位華爾街頂尖總體經濟分析師。

請根據以下實際抓取的經濟數據，
撰寫一份約200字的繁體中文總體經濟短評。

【最新數據】

CPI 年增率：{cpi_yoy:.2f}%
CPI 觀測日期：{format_date(cpi_date)}

美國失業率：{latest_unemp:.2f}%
失業率觀測日期：{format_date(unemp_date)}

聯邦基金利率：{latest_fed:.2f}%
利率觀測日期：{format_date(fed_date)}

美國10年期公債殖利率：
{latest_10y:.2f}%（觀測日期：{format_date(date_10y)}）

美國10Y-2Y利差：
{latest_spread:.2f} 個百分點
（觀測日期：{format_date(spread_date)}）

【分析要求】

1. 判斷目前美國通膨環境。
2. 分析勞動市場強弱。
3. 評估聯準會貨幣政策方向。
4. 說明美國債券及股票市場可能受到的影響。
5. 結合殖利率曲線判讀經濟風險。

使用專業投資銀行研究報告的語氣。
請區分實際數據與推論。
不可虛構資料，不可把推測當成事實。
若不同指標觀測日期不同，必須注意資料時點。
全文約200個中文字。
"""

                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )

                    client.close()

                    if response.text:

                        st.success("AI 總體經濟分析完成！")

                        st.markdown(
                            "### 📑 Macro Research Commentary"
                        )

                        st.markdown(response.text)

                    else:

                        st.warning(
                            "Gemini 沒有返回文字，請重新嘗試。"
                        )

                except Exception as e:

                    st.error(
                        f"Gemini API 發生錯誤：{e}"
                    )


    # ======================================
    # 12. DATA SOURCE FOOTER
    # ======================================

    st.divider()

    st.caption(
        "Sources: Federal Reserve Bank of St. Louis (FRED) | "
        "Yahoo Finance | OECD | Google Gemini"
    )

    st.caption(
        "資料更新頻率依各來源而異。"
        "本儀表板僅供學術研究與經濟分析，不構成投資建議。"
    )


except Exception as e:

    st.error(
        f"數據讀取失敗：{e}"
    )

    st.info(
        "請檢查 FRED API Key、網路連線及資料來源是否正常。"
    )
