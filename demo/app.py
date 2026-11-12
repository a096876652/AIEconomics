
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import feedparser
from fredapi import Fred
from urllib.parse import quote
from google import genai

# =====================================================
# 1. 基本設定
# =====================================================

st.set_page_config(
    page_title="經濟專家 ECONOMICS EXPERT",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

GEMINI_MODEL = "gemini-3.8-flash"

# =====================================================
# 2. 網站設計
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', sans-serif;
}

.stApp {
    background: linear-gradient(
        135deg,
        #FAF9F6 0%,
        #F0F5FB 55%,
        #F7F4EF 100%
    );
    color: #26364F;
}

.block-container {
    padding-top: 1.8rem;
    max-width: 1500px;
}

h1 {
    color: #243B5A !important;
    font-size: 2.4rem !important;
    font-weight: 800 !important;
}

h2 {
    color: #344F70 !important;
    font-size: 1.65rem !important;
    font-weight: 800 !important;
}

h3 {
    color: #496582 !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
}

p, label, .stMarkdown {
    font-size: 1rem;
}

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.95);
    border: 1px solid #E3E9F0;
    border-radius: 17px;
    padding: 18px;
    box-shadow: 0 4px 15px rgba(42,64,91,0.06);
}

[data-testid="stMetricLabel"] {
    color: #657A93;
    font-size: 1rem !important;
    font-weight: 700;
}

[data-testid="stMetricValue"] {
    color: #263F60;
    font-size: 2rem !important;
    font-weight: 800;
}

[data-testid="stSidebar"] {
    background: #F1F4F8;
    border-right: 1px solid #E1E7EF;
}

[data-testid="stSidebar"] * {
    font-size: 1rem;
}

div[data-testid="stTabs"] button {
    font-size: 1.05rem;
    font-weight: 700;
}

div[data-testid="stButton"] > button {
    background: #E4ECF6;
    color: #2D4665;
    border: 1px solid #CFDAE7;
    border-radius: 12px;
    min-height: 2.8rem;
    font-weight: 700;
}

div[data-testid="stButton"] > button:hover {
    background: #D5E2F1;
    border-color: #9EB4CE;
    color: #233C5B;
}

.hero {
    background: linear-gradient(
        110deg,
        #FFFFFF 0%,
        #EAF1F8 60%,
        #F5F1E9 100%
    );
    border: 1px solid #E1E7EF;
    border-radius: 22px;
    padding: 28px 30px;
    margin-bottom: 22px;
}

.hero-title {
    font-size: 2.2rem;
    font-weight: 800;
    color: #243B5A;
}

.hero-subtitle {
    color: #718197;
    font-size: 1.05rem;
    margin-top: 8px;
}

.info-card {
    background: white;
    border: 1px solid #E4EAF1;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 15px;
    line-height: 1.9;
}

.footer {
    text-align: center;
    color: #8290A2;
    padding: 20px;
    font-size: 0.9rem;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# 3. 標題
# =====================================================

st.markdown("""
<div class="hero">
    <div class="hero-title">
        📊 經濟專家
    </div>
    <div class="hero-subtitle">
        ECONOMICS EXPERT ｜ 總體經濟・金融市場・AI 智能分析
    </div>
</div>
""", unsafe_allow_html=True)


# =====================================================
# 4. API 金鑰設定
# =====================================================

def read_secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


st.sidebar.title("⚙️ 系統設定")
st.sidebar.caption("API 金鑰與資料更新設定")

fred_secret = read_secret("FRED_API_KEY")
gemini_secret = read_secret("GEMINI_API_KEY")

if fred_secret:
    fred_key = fred_secret
    st.sidebar.success("FRED API Key 已讀取")
else:
    fred_key = st.sidebar.text_input(
        "FRED API Key",
        type="password"
    )

if gemini_secret:
    gemini_key = gemini_secret
    st.sidebar.success("Gemini API Key 已讀取")
else:
    gemini_key = st.sidebar.text_input(
        "Gemini API Key",
        type="password"
    )

st.sidebar.markdown("---")

if st.sidebar.button(
    "🔄 重新整理全部資料",
    use_container_width=True
):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 資料來源")
st.sidebar.markdown("""
- FRED 美國聯準會資料庫
- Yahoo Finance 金融行情
- Google News 財經新聞
- Google Gemini AI
""")

st.sidebar.caption(
    "本平台資料僅供研究與教學參考。"
)


# =====================================================
# 5. FRED 總體經濟資料
# =====================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_fred_data(api_key):

    fred = Fred(api_key=api_key)

    series = {
        "CPI 指數": "CPIAUCSL",
        "核心 CPI 指數": "CPILFESL",
        "PCE 指數": "PCEPI",
        "10 年期美債殖利率": "DGS10",
        "美國失業率": "UNRATE",
        "聯邦基金利率": "FEDFUNDS"
    }

    data = {}

    for name, series_id in series.items():
        data[name] = fred.get_series(series_id)

    df = pd.DataFrame(data).sort_index()

    # 保留原始頻率，不對不同頻率的資料進行前向填補
    df = df.tail(2000)

    # CPI 年增率與月增率
    cpi = df["CPI 指數"].dropna()

    df["CPI 年增率"] = (
        cpi.pct_change(12) * 100
    ).reindex(df.index)

    df["CPI 月增率"] = (
        cpi.pct_change(1) * 100
    ).reindex(df.index)

    # 核心 CPI 年增率
    core = df["核心 CPI 指數"].dropna()

    df["核心 CPI 年增率"] = (
        core.pct_change(12) * 100
    ).reindex(df.index)

    # PCE 年增率
    pce = df["PCE 指數"].dropna()

    df["PCE 年增率"] = (
        pce.pct_change(12) * 100
    ).reindex(df.index)

    return df


# =====================================================
# 6. Yahoo Finance 金融市場資料
# =====================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_market_data():

    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "黃金": "GC=F",
        "美元／台幣": "TWD=X"
    }

    raw = yf.download(
        list(tickers.values()),
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True
    )

    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):

        level0 = raw.columns.get_level_values(0)
        level1 = raw.columns.get_level_values(1)

        if "Close" in level0:
            close = raw.xs(
                "Close",
                axis=1,
                level=0
            )

        elif "Close" in level1:
            close = raw.xs(
                "Close",
                axis=1,
                level=1
            )

        else:
            return pd.DataFrame()

    else:

        if "Close" in raw.columns:
            close = raw[["Close"]]
        else:
            return pd.DataFrame()

    close = close.rename(
        columns={
            ticker: name
            for name, ticker in tickers.items()
        }
    )

    return close.sort_index().dropna(how="all")


# =====================================================
# 7. Google News 新聞資料
# =====================================================

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_google_news(keyword):

    safe_keyword = quote(keyword)

    url = (
        "https://news.google.com/rss/search?q="
        + safe_keyword
        + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )

    feed = feedparser.parse(url)

    news = []

    for entry in feed.entries[:10]:

        source_data = entry.get("source", {})

        if hasattr(source_data, "get"):
            source_name = source_data.get(
                "title",
                "Google News"
            )
        else:
            source_name = "Google News"

        news.append({
            "title": entry.get(
                "title",
                "無標題"
            ),
            "link": entry.get(
                "link",
                ""
            ),
            "published": entry.get(
                "published",
                ""
            ),
            "source": source_name
        })

    return news


# =====================================================
# 8. Gemini AI 新聞分析
# =====================================================

def analyze_news_with_gemini(api_key, news_items):

    
def analyze_news_with_gemini(api_key, news_items):

    if not api_key:
        raise ValueError("尚未設定 Gemini API Key")

    if not news_items:
        raise ValueError("目前沒有新聞資料")

    client = genai.Client(api_key=api_key)

    news_text = "\n".join([
        f"{i+1}. {item['title']}"
        for i, item in enumerate(news_items)
    ])

    prompt = f"""
你是一位華爾街總體經濟分析師。

請分析以下財經新聞：

{news_text}

請使用繁體中文提供專業分析：

一、整體市場情緒
1. 情緒分數 0～100
2. 市場目前偏向樂觀或悲觀
3. 主要原因

二、聯準會貨幣政策
1. 鷹派、鴿派或中立
2. 未來利率政策可能方向

三、美國總體經濟
1. CPI 通膨影響
2. 就業市場影響
3. 經濟成長影響

四、金融市場
1. 美元
2. 美國10年期公債殖利率
3. S&P 500
4. 台灣加權指數

五、逐條新聞分析
請製作表格：
新聞標題、經濟意涵、鷹鴿立場、判斷信心。

六、總結
提出三個值得持續追蹤的經濟指標。

請勿虛構新聞內容及數據。
只能根據新聞標題進行初步判斷。
"""

    # 依序使用三個官方穩定模型
    model_list = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash"
    ]

    last_error = None

    for model_name in model_list:

        try:

            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            if not response.text:
                raise ValueError("AI 沒有回傳文字內容")

            return (
                f"**本次使用模型：{model_name}**\n\n"
                + response.text
            )

        except Exception as e:

            last_error = e

            error_text = str(e).lower()

            status_code = getattr(e, "code", None)

            is_503 = (
                status_code == 503
                or "503" in error_text
                or "unavailable" in error_text
            )

            if is_503:
                continue

            # 非 503 錯誤，不盲目切換模型
            raise

    raise RuntimeError(
        "三個 Gemini 模型目前都無法完成請求。\n"
        "Google AI 服務可能暫時超載，請稍後重試。\n"
        f"最後錯誤：{last_error}"
    )


    prompt = f"""
你是一位華爾街總體經濟研究員。

請根據以下財經新聞標題，
進行專業的總體經濟與金融市場分析。

【新聞標題】

{news_text}

請使用繁體中文回答。

一、整體市場情緒
- 情緒分數 0 至 100
- 50 代表中立
- 說明評分理由

二、聯準會貨幣政策判斷
- 鷹派、鴿派或中立
- 分析可能的利率政策方向

三、重要經濟議題
- 美國通膨
- 勞動市場
- 經濟成長
- 國際貿易與能源

四、金融市場影響
- 美元
- 美國 10 年期公債殖利率
- S&P 500
- 台灣加權指數

五、CPI 可能影響
分析這些新聞對未來通膨的可能影響。

六、逐條新聞分析
請製作表格，內容包含：
- 新聞標題
- 主要經濟意涵
- 鷹派／鴿派／中立
- 判斷信心

七、總結
提出三項值得追蹤的總體經濟指標。

重要限制：
你只能根據提供的新聞標題進行初步分析，
不可虛構新聞內文、經濟數據或官員發言。
標題資訊不足時，請明確說明。
不要將推測寫成已確認的事實。
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    result = response.text

    if not result:
        raise ValueError(
            "Gemini 沒有回傳文字內容，請重新嘗試。"
        )

    return result


# =====================================================
# 9. 圖表函式
# =====================================================

def make_line_chart(df, column, title):

    series = df[column].dropna()

    if series.empty:
        return None

    plot_df = series.rename(
        "數值"
    ).reset_index()

    plot_df.columns = [
        "日期",
        "數值"
    ]

    fig = px.line(
        plot_df,
        x="日期",
        y="數值",
        title=title,
        template="plotly_white",
        color_discrete_sequence=["#6487B0"]
    )

    fig.update_layout(
        font=dict(
            family="Noto Sans TC",
            size=14,
            color="#344B66"
        ),
        title_font_size=20,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.85)",
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        ),
        hovermode="x unified",
        xaxis_title="日期",
        yaxis_title=column
    )

    fig.update_traces(
        line=dict(width=3)
    )

    return fig


def latest_value(series):

    valid = series.dropna()

    if valid.empty:
        return None, None

    return float(valid.iloc[-1]), valid.index[-1]


# =====================================================
# 10. 載入資料
# =====================================================

macro_df = pd.DataFrame()
market_df = pd.DataFrame()

fred_error = None
market_error = None

if fred_key:

    try:
        with st.spinner("正在讀取 FRED 總經資料..."):
            macro_df = get_fred_data(fred_key)

    except Exception as e:
        fred_error = str(e)

else:

    fred_error = "尚未設定 FRED API Key。"


try:

    with st.spinner("正在讀取金融市場行情..."):
        market_df = get_market_data()

except Exception as e:

    market_error = str(e)


# =====================================================
# 11. 總體經濟 KPI
# =====================================================

st.markdown("## 📊 美國總體經濟關鍵指標")

if fred_error:

    st.warning(
        f"FRED 資料暫時無法讀取：{fred_error}"
    )

else:

    cpi_yoy, cpi_date = latest_value(
        macro_df["CPI 年增率"]
    )

    core_yoy, core_date = latest_value(
        macro_df["核心 CPI 年增率"]
    )

    ten_year, ten_date = latest_value(
        macro_df["10 年期美債殖利率"]
    )

    unemployment, unemployment_date = latest_value(
        macro_df["美國失業率"]
    )

    fed_rate, fed_date = latest_value(
        macro_df["聯邦基金利率"]
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric(
        "CPI 年增率",
        f"{cpi_yoy:.2f}%" if cpi_yoy is not None else "N/A"
    )

    k2.metric(
        "核心 CPI 年增率",
        f"{core_yoy:.2f}%" if core_yoy is not None else "N/A"
    )

    k3.metric(
        "10 年期美債",
        f"{ten_year:.2f}%" if ten_year is not None else "N/A"
    )

    k4.metric(
        "美國失業率",
        f"{unemployment:.1f}%" if unemployment is not None else "N/A"
    )

    k5.metric(
        "聯邦基金利率",
        f"{fed_rate:.2f}%" if fed_rate is not None else "N/A"
    )

    st.caption(
        "各指標資料發布頻率不同，數值日期請以各自的最新觀測日為準。"
    )

# =====================================================
# 12. 分頁設計
# =====================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 總覽首頁",
    "📈 金融市場",
    "🏛️ 總經資料",
    "🤖 AI 新聞分析",
    "📥 資料下載"
])


# =====================================================
# TAB 1：總覽首頁
# =====================================================

with tab1:

    st.markdown("## 🌐 全球金融市場總覽")

    left, right = st.columns(
        [1.3, 1]
    )

    with left:

        st.markdown("### 美國通膨趨勢")

        if not macro_df.empty:

            inflation_cols = [
                "CPI 年增率",
                "核心 CPI 年增率",
                "PCE 年增率"
            ]

            inflation_df = macro_df[
                inflation_cols
            ].dropna(how="all")

            if not inflation_df.empty:

                plot_df = inflation_df.reset_index()

                plot_df = plot_df.rename(
                    columns={
                        plot_df.columns[0]: "日期"
                    }
                )

                fig = px.line(
                    plot_df,
                    x="日期",
                    y=inflation_cols,
                    title="美國主要通膨指標",
                    template="plotly_white",
                    color_discrete_sequence=[
                        "#E0A66F",
                        "#6586B0",
                        "#83A995"
                    ],
                    labels={
                        "value": "年增率（%）",
                        "variable": "指標"
                    }
                )

                fig.update_layout(
                    font=dict(
                        family="Noto Sans TC",
                        size=13
                    ),
                    title_font_size=19,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="white",
                    legend_title_text=""
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

        else:

            st.info(
                "設定 FRED API Key 後即可查看通膨趨勢。"
            )

    with right:

        st.markdown("### 📚 總經指標解讀")

        st.markdown("""
        <div class="info-card">
        <b>🛒 CPI</b><br>
        觀察美國消費者物價變化。<br><br>

        <b>📊 核心 CPI</b><br>
        排除食品與能源，觀察較持續性的通膨壓力。<br><br>

        <b>💵 10 年期美債殖利率</b><br>
        反映市場對長期利率、通膨及經濟前景的預期。<br><br>

        <b>👷 失業率</b><br>
        觀察勞動市場的變化與景氣狀況。<br><br>

        <b>🏦 聯邦基金利率</b><br>
        觀察聯準會貨幣政策立場。
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 📈 主要市場最新行情")

    if not market_df.empty:

        valid_cols = [
            c for c in market_df.columns
            if market_df[c].notna().any()
        ]

        if valid_cols:

            cols = st.columns(
                min(3, len(valid_cols))
            )

            for i, name in enumerate(valid_cols[:3]):

                series = market_df[name].dropna()

                if len(series) >= 2:

                    change = (
                        series.iloc[-1] /
                        series.iloc[-2] - 1
                    ) * 100

                    cols[i].metric(
                        name,
                        f"{series.iloc[-1]:,.2f}",
                        f"{change:+.2f}%"
                    )

    else:

        st.info(
            f"市場資料暫時無法讀取：{market_error or '目前沒有資料。'}"
        )


# =====================================================
# TAB 2：金融市場
# =====================================================

with tab2:

    st.markdown("## 📈 金融市場走勢分析")

    if market_df.empty:

        st.warning(
            "目前沒有市場行情資料，請稍後重新整理。"
        )

    else:

        valid_cols = [
            c for c in market_df.columns
            if market_df[c].notna().any()
        ]

        selected_market = st.selectbox(
            "選擇金融市場標的",
            valid_cols,
            key="market_select"
        )

        period = st.radio(
            "選擇觀察期間",
            [
                "近 1 個月",
                "近 3 個月",
                "近 6 個月",
                "近 1 年"
            ],
            horizontal=True
        )

        days_map = {
            "近 1 個月": 30,
            "近 3 個月": 90,
            "近 6 個月": 180,
            "近 1 年": 365
        }

        selected_data = market_df[
            [selected_market]
        ].dropna().tail(
            days_map[period]
        )

        fig = make_line_chart(
            selected_data,
            selected_market,
            f"{selected_market}｜{period}走勢"
        )

        if fig is not None:

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        series = selected_data[
            selected_market
        ].dropna()

        if len(series) >= 2:

            total_return = (
                series.iloc[-1] /
                series.iloc[0] - 1
            ) * 100

            daily_return = series.pct_change().dropna()

            a, b, c = st.columns(3)

            a.metric(
                "區間報酬率",
                f"{total_return:+.2f}%"
            )

            b.metric(
                "最新價格",
                f"{series.iloc[-1]:,.2f}"
            )

            c.metric(
                "日報酬標準差",
                f"{daily_return.std() * 100:.2f}%"
            )

        st.caption(
            "資料來源：Yahoo Finance。行情可能延遲或修正，"
            "報酬率為選定觀察區間計算值。"
        )


# =====================================================
# TAB 3：總體經濟資料
# =====================================================

with tab3:

    st.markdown("## 🏛️ 美國總體經濟研究中心")

    if macro_df.empty:

        st.warning(
            "請先設定正確的 FRED API Key。"
        )

    else:

        options = [
            col for col in macro_df.columns
            if macro_df[col].notna().any()
        ]

        selected_macro = st.selectbox(
            "選擇總體經濟指標",
            options,
            key="macro_select"
        )

        fig = make_line_chart(
            macro_df,
            selected_macro,
            f"{selected_macro}｜歷史趨勢"
        )

        if fig is not None:

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        value, date = latest_value(
            macro_df[selected_macro]
        )

        if value is not None:

            st.info(
                f"最新觀測值：{value:,.3f}　"
                f"| 資料日期：{pd.Timestamp(date).strftime('%Y-%m-%d')}"
            )

        definitions = {

            "CPI 指數":
                "消費者物價指數，衡量消費者購買商品與服務的價格變化。",

            "核心 CPI 指數":
                "排除食品與能源價格後的消費者物價指數。",

            "PCE 指數":
                "個人消費支出物價指數，是聯準會重要通膨參考指標。",

            "CPI 年增率":
                "與 12 個月前相比的 CPI 指數變化率。",

            "CPI 月增率":
                "與前一個月相比的 CPI 指數變化率。",

            "核心 CPI 年增率":
                "核心 CPI 指數與 12 個月前相比的變化率。",

            "PCE 年增率":
                "PCE 指數與 12 個月前相比的變化率。",

            "10 年期美債殖利率":
                "美國 10 年期公債殖利率。",

            "美國失業率":
                "失業人口占勞動力人口的比率。",

            "聯邦基金利率":
                "美國銀行間隔夜拆款利率的有效利率指標。"
        }

        st.markdown("### 📖 指標說明")

        st.markdown(
            f"""
            <div class="info-card">
            {definitions.get(selected_macro, "總體經濟觀察指標。")}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.caption(
            "資料來源：Federal Reserve Bank of St. Louis（FRED）。"
            "CPI、核心 CPI 與 PCE 使用原始月資料計算年增率。"
        )


# =====================================================
# TAB 4：AI 新聞分析
# =====================================================

with tab4:

    st.markdown("## 🤖 AI 智能總體經濟分析")

    st.markdown(
        "透過財經新聞標題，分析市場情緒、聯準會政策與總體經濟影響。"
    )

    if "news_keyword" not in st.session_state:

        st.session_state.news_keyword = (
            "Federal Reserve Inflation"
        )

    with st.form("news_search_form"):

        search_kw = st.text_input(
            "新聞搜尋關鍵字",
            value=st.session_state.news_keyword
        )

        search_submit = st.form_submit_button(
            "🔍 搜尋最新新聞"
        )

    if search_submit:

        st.session_state.news_keyword = search_kw.strip()

        st.session_state.pop(
            "ai_report",
            None
        )

    if st.session_state.news_keyword:

        try:

            with st.spinner("正在搜尋財經新聞..."):

                news_items = fetch_google_news(
                    st.session_state.news_keyword
                )

        except Exception as e:

            news_items = []

            st.error(
                f"新聞讀取失敗：{e}"
            )

    else:

        news_items = []

    news_left, news_right = st.columns(
        [1.15, 0.85]
    )

    # -------------------------------------------------
    # 左側：新聞清單
    # -------------------------------------------------

    with news_left:

        st.markdown("### 📰 最新財經新聞")

        if news_items:

            for i, item in enumerate(news_items, 1):

                with st.container(border=True):

                    st.markdown(
                        f"**{i}. {item['title']}**"
                    )

                    st.caption(
                        f"{item['source']}｜{item['published']}"
                    )

                    if item["link"]:

                        st.link_button(
                            "閱讀新聞來源",
                            item["link"]
                        )

        else:

            st.warning(
                "目前沒有找到新聞，請更換關鍵字。"
            )

    # -------------------------------------------------
    # 右側：Gemini AI
    # -------------------------------------------------

    with news_right:

        st.markdown("### 🧠 Gemini AI 分析")

        st.markdown("""
        <div class="info-card">
        <b>AI 分析項目</b><br><br>
        ① 市場情緒評分<br>
        ② 聯準會鷹派與鴿派判斷<br>
        ③ 美國通膨影響<br>
        ④ 美債與美元市場影響<br>
        ⑤ 台灣股市影響
        </div>
        """, unsafe_allow_html=True)

        if not gemini_key:

            st.warning(
                "請先在左側設定 Gemini API Key。"
            )

        elif st.button(
            "🚀 開始 AI 新聞分析",
            type="primary",
            use_container_width=True
        ):

            if not news_items:

                st.warning(
                    "沒有新聞資料可以分析。"
                )

            else:

                try:

                    with st.spinner(
                        "Gemini 正在進行總體經濟分析..."
                    ):

                        report = analyze_news_with_gemini(
                            gemini_key,
                            news_items
                        )

                    st.session_state.ai_report = report

                except Exception as e:

                    st.error(
                        "Gemini AI 分析失敗。"
                    )

                    st.write(
                        "錯誤類型：",
                        type(e).__name__
                    )

                    st.code(
                        str(e)
                    )

                    error_text = str(e).lower()

                    if "429" in error_text:

                        st.warning(
                            "API 請求次數或使用額度可能已達限制。"
                        )

                    elif "403" in error_text:

                        st.warning(
                            "API 金鑰可能沒有使用此模型的權限。"
                        )

                    elif "404" in error_text:

                        st.warning(
                            "找不到模型或 API 端點，請確認模型名稱與 API 設定。"
                        )

                    elif "503" in error_text:

                        st.warning(
                            "Google 模型服務目前可能繁忙，請稍後重試。"
                        )

        if st.session_state.get("ai_report"):

            st.markdown("---")
            st.markdown("### 📋 AI 分析報告")

            st.markdown(
                st.session_state.ai_report
            )

            st.download_button(
                "⬇️ 下載 AI 分析報告",
                data=st.session_state.ai_report,
                file_name="economic_ai_report.md",
                mime="text/markdown"
            )

    st.caption(
        "AI 僅根據新聞標題進行初步分析，不代表已查證新聞全文，"
        "亦不構成投資建議。"
    )


# =====================================================
# TAB 5：資料下載
# =====================================================

with tab5:

    st.markdown("## 📥 總體經濟資料下載")

    left, right = st.columns(2)

    with left:

        st.markdown("### 🏛️ FRED 資料")

        if not macro_df.empty:

            st.dataframe(
                macro_df.tail(30),
                use_container_width=True
            )

            st.download_button(
                "⬇️ 下載 FRED CSV",
                data=macro_df.to_csv().encode(
                    "utf-8-sig"
                ),
                file_name="economic_fred_data.csv",
                mime="text/csv",
                use_container_width=True
            )

        else:

            st.info(
                "目前沒有 FRED 資料。"
            )

    with right:

        st.markdown("### 📈 金融市場資料")

        if not market_df.empty:

            st.dataframe(
                market_df.tail(30),
                use_container_width=True
            )

            st.download_button(
                "⬇️ 下載市場 CSV",
                data=market_df.to_csv().encode(
                    "utf-8-sig"
                ),
                file_name="economic_market_data.csv",
                mime="text/csv",
                use_container_width=True
            )

        else:

            st.info(
                "目前沒有市場資料。"
            )


# =====================================================
# 13. 頁尾
# =====================================================

st.markdown("---")

st.markdown("""
<div class="footer">
    📊 ECONOMICS EXPERT ｜ 經濟專家<br>
    總體經濟・金融市場・AI 智能分析<br>
    資料僅供研究及教學參考，不構成投資建議。
</div>
""", unsafe_allow_html=True)
