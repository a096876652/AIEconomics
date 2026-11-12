import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from fredapi import Fred
import feedparser
from urllib.parse import quote
from datetime import datetime, timezone
from google import genai

# =========================================================
# 1. 頁面設定與視覺風格
# =========================================================
st.set_page_config(
    page_title="總經研究室｜市場儀表板",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: 'Noto Sans TC', sans-serif;
}
.stApp {
    background: linear-gradient(135deg, #fffaf4 0%, #f4f8ff 52%, #f8f5ff 100%);
    color: #26334a;
}
[data-testid="stHeader"] { background: rgba(255,255,255,0.72); }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1500px; }
h1 { color: #34466b !important; font-size: 2.35rem !important; font-weight: 800 !important; }
h2 { color: #40577d !important; font-size: 1.65rem !important; font-weight: 800 !important; }
h3 { color: #52698d !important; font-size: 1.25rem !important; font-weight: 700 !important; }
p, label, .stMarkdown, .stText, [data-testid="stMetricLabel"] {
    font-size: 1.02rem;
}
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.92);
    border: 1px solid #e5eaf4;
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 5px 18px rgba(74, 93, 130, 0.07);
}
[data-testid="stMetricValue"] {
    color: #34466b;
    font-size: 2rem !important;
    font-weight: 800;
}
[data-testid="stMetricLabel"] {
    color: #667895;
    font-size: 1rem !important;
    font-weight: 700;
}
[data-testid="stMetricDelta"] { font-size: 0.95rem !important; }
div[data-testid="stTabs"] button {
    font-size: 1.05rem;
    font-weight: 700;
    border-radius: 12px 12px 0 0;
}
div[data-testid="stButton"] > button {
    border-radius: 12px;
    min-height: 2.8rem;
    font-weight: 700;
    border: 1px solid #cbd8ed;
    background: #eaf1ff;
    color: #34466b;
}
div[data-testid="stButton"] > button:hover {
    border-color: #9db5df;
    background: #dce8ff;
    color: #263b62;
}
div[data-testid="stAlert"] { border-radius: 14px; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #fff4e8 0%, #f1f5ff 100%);
    border-right: 1px solid #e6eaf2;
}
[data-testid="stSidebar"] * { font-size: 1rem; }
div[data-testid="stSelectbox"] label, div[data-testid="stTextInput"] label {
    font-weight: 700;
    color: #52698d;
}
.soft-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid #e6ebf4;
    border-radius: 18px;
    padding: 18px 20px;
    margin: 8px 0 14px 0;
    box-shadow: 0 5px 18px rgba(74, 93, 130, 0.05);
}
.hero {
    background: linear-gradient(110deg, #fff0df 0%, #eaf2ff 55%, #f2eaff 100%);
    border: 1px solid #e6e9f3;
    border-radius: 24px;
    padding: 24px 28px;
    margin-bottom: 18px;
}
.hero-title { font-size: 2rem; font-weight: 800; color: #34466b; }
.hero-sub { font-size: 1.05rem; color: #687895; margin-top: 5px; }
.small-note { color: #7b879b; font-size: 0.88rem; }
.news-item {
    background: #fff;
    border: 1px solid #e8edf5;
    border-radius: 14px;
    padding: 13px 16px;
    margin-bottom: 10px;
}
.news-item a { color: #40577d; text-decoration: none; font-weight: 700; }
.news-item a:hover { color: #7a83bd; text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 標題與側邊欄設定
# =========================================================
st.markdown("""
<div class="hero">
  <div class="hero-title">總經研究室</div>
  <div class="hero-sub">把複雜的總體經濟與金融市場，整理成一眼就看懂的每日儀表板。</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("## 🧸 儀表板設定")
st.sidebar.caption("先設定資料來源金鑰，再開始探索市場。")

def get_secret_or_input(secret_name: str, label: str):
    try:
        secret_value = st.secrets.get(secret_name, "")
    except Exception:
        secret_value = ""
    if secret_value:
        st.sidebar.success(f"✅ {label}已從 Secrets 讀取")
        return secret_value
    return st.sidebar.text_input(label, type="password", key=f"input_{secret_name}")

fred_key = get_secret_or_input("FRED_API_KEY", "FRED API Key")
gemini_key = get_secret_or_input("GEMINI_API_KEY", "Gemini API Key（AI 新聞分析）")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 更新資料")
if st.sidebar.button("重新整理全部資料", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("市場資料快取約 10 分鐘；總經資料約 1 小時；新聞約 30 分鐘。")
st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 資料來源")
st.sidebar.markdown("- FRED：美國總經資料\n- Yahoo Finance：市場行情\n- Google News RSS：新聞標題\n- Gemini：新聞文字分析")

# =========================================================
# 3. 資料抓取函式
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def get_fred_data(api_key: str):
    fred = Fred(api_key=api_key)
    series = {
        "CPI 指數": "CPIAUCSL",
        "10 年期美債殖利率": "DGS10",
        "美國失業率": "UNRATE",
        "聯邦基金利率": "FEDFUNDS",
        "核心 CPI 指數": "CPILFESL",
        "PCE 物價指數": "PCEPI",
    }
    result = {}
    for label, series_id in series.items():
        result[label] = fred.get_series(series_id)
    df = pd.DataFrame(result).sort_index().ffill()
    # CPI / 核心 CPI / PCE 為月資料；保留最近 5 年方便觀察趨勢
    return df.tail(60)

@st.cache_data(ttl=600, show_spinner=False)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "黃金": "GC=F",
        "美元/台幣": "TWD=X",
    }
    raw = yf.download(
        list(tickers.values()),
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if raw.empty:
        return pd.DataFrame()
    # 新版 yfinance 可能回傳 MultiIndex 欄位，這裡統一整理
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw.xs("Close", axis=1, level=0)
        elif "Close" in raw.columns.get_level_values(1):
            close = raw.xs("Close", axis=1, level=1)
        else:
            close = raw
    else:
        close = raw["Close"] if "Close" in raw.columns else raw
    close = close.rename(columns={v: k for k, v in tickers.items()})
    close = close.sort_index().dropna(how="all")
    return close

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_google_news(keyword: str):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:10]:
        items.append({
            "title": entry.get("title", "（無標題）"),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "source": entry.get("source", {}).get("title", "Google News"),
        })
    return items

def latest_valid(series: pd.Series):
    s = series.dropna()
    if s.empty:
        return None, None
    return float(s.iloc[-1]), s.index[-1]

def make_line_chart(df, column, title, y_title=None):
    plot_df = df[[column]].dropna().reset_index()
    plot_df.columns = ["日期", "數值"]
    fig = px.line(
        plot_df, x="日期", y="數值", title=title,
        template="plotly_white",
        color_discrete_sequence=["#7C9CCB"],
    )
    fig.update_layout(
        title_font_size=20,
        font=dict(family="Noto Sans TC", size=14, color="#40506b"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.72)",
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
        yaxis_title=y_title or column,
        xaxis_title="日期",
    )
    fig.update_traces(line=dict(width=3), hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>")
    return fig

# =========================================================
# 4. 主畫面
# =========================================================
if not fred_key:
    st.info("👈 請先在左側輸入 FRED API Key，才能載入總經資料。")
    st.markdown("""
    <div class="soft-card">
    <b>💡 小提醒</b><br>
    FRED API Key 可至 Federal Reserve Bank of St. Louis 的 FRED 網站免費申請。
    佈署到 Streamlit Community Cloud 時，建議將金鑰放在 App 的 Secrets，不要直接寫在程式碼裡。
    </div>
    """, unsafe_allow_html=True)
    st.stop()

try:
    with st.spinner("🐻 正在整理最新總經與市場資料..."):
        macro_df = get_fred_data(fred_key)
    if macro_df.empty:
        st.error("FRED 沒有回傳資料，請檢查 API Key 或稍後再試。")
        st.stop()
except Exception as e:
    st.error(f"FRED 資料讀取失敗：{e}")
    st.stop()

try:
    market_df = get_market_data()
except Exception as e:
    market_df = pd.DataFrame()
    st.warning(f"市場行情暫時無法載入：{e}")

# 計算 CPI 年增率與月增率（由指數自行計算）
if "CPI 指數" in macro_df:
    macro_df["CPI 年增率"] = macro_df["CPI 指數"].pct_change(12) * 100
    macro_df["CPI 月增率"] = macro_df["CPI 指數"].pct_change(1) * 100
if "核心 CPI 指數" in macro_df:
    macro_df["核心 CPI 年增率"] = macro_df["核心 CPI 指數"].pct_change(12) * 100
if "PCE 物價指數" in macro_df:
    macro_df["PCE 年增率"] = macro_df["PCE 物價指數"].pct_change(12) * 100

# 最新值
cpi, cpi_date = latest_valid(macro_df.get("CPI 指數", pd.Series(dtype=float)))
ten_year, ten_date = latest_valid(macro_df.get("10 年期美債殖利率", pd.Series(dtype=float)))
unemp, unemp_date = latest_valid(macro_df.get("美國失業率", pd.Series(dtype=float)))
fed_rate, fed_date = latest_valid(macro_df.get("聯邦基金利率", pd.Series(dtype=float)))
cpi_yoy, _ = latest_valid(macro_df.get("CPI 年增率", pd.Series(dtype=float)))
core_yoy, _ = latest_valid(macro_df.get("核心 CPI 年增率", pd.Series(dtype=float)))

st.markdown("## 🌤️ 今日總經天氣")
st.caption("以下顯示各資料序列目前可取得的最新觀測值；不同指標發布頻率不同，並非全部都是今天的數據。")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("CPI 年增率", f"{cpi_yoy:.2f}%" if cpi_yoy is not None else "N/A")
k2.metric("核心 CPI 年增率", f"{core_yoy:.2f}%" if core_yoy is not None else "N/A")
k3.metric("10 年期美債", f"{ten_year:.2f}%" if ten_year is not None else "N/A")
k4.metric("美國失業率", f"{unemp:.1f}%" if unemp is not None else "N/A")
k5.metric("聯邦基金利率", f"{fed_rate:.2f}%" if fed_rate is not None else "N/A")

date_labels = []
for label, date_value in [
    ("CPI", cpi_date), ("10Y", ten_date), ("失業率", unemp_date), ("政策利率", fed_date)
]:
    if date_value is not None:
        date_labels.append(f"{label}：{pd.Timestamp(date_value).strftime('%Y-%m-%d')}")
st.caption("資料日期｜" + "　｜　".join(date_labels))

st.markdown("---")
tab_overview, tab_market, tab_macro, tab_news, tab_data = st.tabs([
    "🏡 總覽首頁", "📈 金融市場", "🏛️ 總經指標", "📰 新聞與 AI", "📥 原始資料"
])

# ---------------------------------------------------------
# Tab 1：總覽
# ---------------------------------------------------------
with tab_overview:
    st.markdown("## ✨ 市場快速總覽")
    left, right = st.columns([1.25, 1])
    with left:
        st.markdown("### 📊 美國通膨趨勢")
        inflation_cols = [c for c in ["CPI 年增率", "核心 CPI 年增率", "PCE 年增率"] if c in macro_df.columns]
        if inflation_cols:
            temp = macro_df[inflation_cols].dropna(how="all").reset_index()
            temp = temp.rename(columns={temp.columns[0]: "日期"})
            fig = px.line(
                temp, x="日期", y=inflation_cols,
                template="plotly_white",
                color_discrete_sequence=["#E7A66B", "#829BCB", "#8CB8A2"],
                labels={"value": "年增率（%）", "variable": "指標"},
            )
            fig.update_layout(
                font=dict(family="Noto Sans TC", size=14, color="#40506b"),
                title="CPI、核心 CPI 與 PCE 年增率",
                title_font_size=19,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(255,255,255,0.72)",
                margin=dict(l=15, r=15, t=55, b=15),
                legend_title_text="",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("目前沒有足夠的通膨資料可繪圖。")
    with right:
        st.markdown("### 🧭 指標怎麼看？")
        st.markdown("""
        <div class="soft-card">
        <b>🛒 CPI</b><br>觀察消費者購買商品與服務的價格變化。<br><br>
        <b>🏠 核心 CPI</b><br>排除食品與能源，較適合觀察較持續的通膨壓力。<br><br>
        <b>💵 10 年期美債殖利率</b><br>反映市場對利率、通膨與長期經濟前景的綜合定價。<br><br>
        <b>👷 失業率</b><br>觀察勞動市場是否降溫，需搭配薪資與非農就業一起判讀。
        </div>
        """, unsafe_allow_html=True)
    st.markdown("### 🌍 主要市場近況")
    if not market_df.empty:
        cols = st.columns(min(3, len(market_df.columns)))
        for i, col in enumerate(market_df.columns[:3]):
            s = market_df[col].dropna()
            if len(s) >= 2:
                change = (s.iloc[-1] / s.iloc[-2] - 1) * 100
                cols[i].metric(col, f"{s.iloc[-1]:,.2f}", f"{change:+.2f}%")
    else:
        st.info("市場行情目前無法取得，請稍後重新整理。")

# ---------------------------------------------------------
# Tab 2：金融市場
# ---------------------------------------------------------
with tab_market:
    st.markdown("## 📈 金融市場觀察")
    if market_df.empty or market_df.dropna(how="all").empty:
        st.warning("目前無市場資料。")
    else:
        valid_market_cols = [c for c in market_df.columns if market_df[c].notna().any()]
        selected_market = st.selectbox("選擇想觀察的市場：", valid_market_cols, key="market_select")
        period = st.radio("圖表區間", ["近 1 個月", "近 3 個月", "近 6 個月", "近 1 年"], horizontal=True)
        days = {"近 1 個月": 30, "近 3 個月": 90, "近 6 個月": 180, "近 1 年": 365}[period]
        series = market_df[selected_market].dropna().tail(days)
        market_view = series.to_frame(name=selected_market)
        st.plotly_chart(make_line_chart(market_view, selected_market, f"{selected_market}｜{period}走勢"), use_container_width=True)
        if len(series) >= 2:
            total_return = (series.iloc[-1] / series.iloc[0] - 1) * 100
            daily_return = series.pct_change().dropna()
            a, b, c = st.columns(3)
            a.metric("區間報酬率", f"{total_return:+.2f}%")
            b.metric("最新收盤／調整後價格", f"{series.iloc[-1]:,.2f}")
            c.metric("區間波動度（日報酬標準差）", f"{daily_return.std() * 100:.2f}%")
        st.caption("行情來源：Yahoo Finance。此處為市場觀察用途，非交易所官方報價；資料可能延遲或因供應商調整而修正。")

# ---------------------------------------------------------
# Tab 3：總經
# ---------------------------------------------------------
with tab_macro:
    st.markdown("## 🏛️ 總體經濟資料室")
    macro_options = [c for c in macro_df.columns if macro_df[c].notna().any()]
    selected_macro = st.selectbox("選擇總經指標：", macro_options, key="macro_select")
    macro_view = macro_df[[selected_macro]].dropna()
    st.plotly_chart(make_line_chart(macro_view, selected_macro, f"{selected_macro}｜近 5 年趨勢"), use_container_width=True)
    latest_value, latest_date = latest_valid(macro_df[selected_macro])
    if latest_value is not None:
        st.info(f"最新觀測值：**{latest_value:,.3f}**　｜　資料日期：**{pd.Timestamp(latest_date).strftime('%Y-%m-%d')}**")
    st.markdown("### 📚 指標小字典")
    definitions = {
        "CPI 指數": "消費者物價指數，反映一籃子消費品與服務價格的變化。",
        "CPI 年增率": "與 12 個月前相比的 CPI 指數變化率。",
        "CPI 月增率": "與前一個月相比的 CPI 指數變化率；需留意季節調整口徑。",
        "核心 CPI 指數": "排除食品與能源價格後的 CPI 指數。",
        "核心 CPI 年增率": "核心 CPI 指數相較 12 個月前的變化率。",
        "PCE 物價指數": "美國個人消費支出物價指數，是聯準會重要通膨參考指標。",
        "PCE 年增率": "PCE 物價指數相較 12 個月前的變化率。",
        "10 年期美債殖利率": "美國 10 年期公債殖利率，反映市場對長期利率與風險的定價。",
        "美國失業率": "失業人口占勞動力人口的比率。",
        "聯邦基金利率": "銀行間隔夜拆款利率的目標區間中點附近之有效利率指標。",
    }
    st.markdown(f"<div class='soft-card'>{definitions.get(selected_macro, '此指標可用於觀察美國總體經濟變化。')}</div>", unsafe_allow_html=True)
    st.caption("資料來源：Federal Reserve Bank of St. Louis（FRED）。指數與利率資料發布頻率不同；月資料不代表每日即時變化。")

# ---------------------------------------------------------
# Tab 4：新聞與 AI
# ---------------------------------------------------------
with tab_news:
    st.markdown("## 📰 財經新聞與 AI 情緒觀察")
    search_kw = st.text_input(
        "🔎 輸入新聞關鍵字",
        value="Federal Reserve Inflation",
        help="例如：Federal Reserve Inflation、US economy、Taiwan central bank",
    )
    fetch_button = st.button("🔍 搜尋最新新聞", type="primary")
    if "news_items" not in st.session_state or fetch_button:
        with st.spinner("正在整理新聞標題..."):
            st.session_state.news_items = fetch_google_news(search_kw)
            st.session_state.news_keyword = search_kw
    news_items = st.session_state.get("news_items", [])
    if news_items:
        news_left, news_right = st.columns([1.15, 0.85])
        with news_left:
            st.markdown("### 🗞️ 新聞清單")
            for idx, item in enumerate(news_items, 1):
                title = item["title"].replace("<", "&lt;").replace(">", "&gt;")
                link = item["link"]
                published = item["published"]
                st.markdown(
                    f"<div class='news-item'><b>{idx:02d}</b>　<a href='{link}' target='_blank'>{title}</a>"
                    f"<div class='small-note'>{item['source']}　{published}</div></div>",
                    unsafe_allow_html=True,
                )
        with news_right:
            st.markdown("### 🤖 AI 鷹鴿派分析")
            if not gemini_key:
                st.info("請在左側輸入 Gemini API Key，或在 Streamlit Secrets 設定 GEMINI_API_KEY。")
            elif st.button("🐻 開始分析新聞", type="primary", key="analyze_news"):
                try:
                    client = genai.Client(api_key=gemini_key)
                    titles = "\n".join([f"{i+1}. {x['title']}" for i, x in enumerate(news_items)])
                    prompt = f"""
你是一位審慎的總體經濟研究員。請根據以下新聞標題做初步分類，不可把標題推論當成已確認事實。
新聞：
{titles}

請用繁體中文輸出：
1. 整體政策情緒：偏鷹／偏鴿／中立／訊息不足
2. 市場情緒分數：0 到 100，並說明 50 代表中性
3. 三個主要觀察主題
4. 逐條新聞表格：標題摘要、可能的政策含意、情緒（鷹／鴿／中立）、判斷信心（高／中／低）
5. 最後列出需要再查證的資訊

限制：只根據標題做初步分析；不要虛構新聞內文、數據、官員發言或市場反應。若標題資訊不足，請明確標示。
"""
                    with st.spinner("AI 正在整理新聞線索..."):
                        response = client.models.generate_content(
                            model = "gemini-2-flash",
                            contents=prompt,
                        )
                    st.markdown(response.text or "AI 沒有回傳可顯示的文字。")
                except Exception as e:
                    st.error(f"AI 分析失敗：{e}")
                    st.caption("若出現 503 UNAVAILABLE，通常代表模型服務暫時繁忙；可稍後重試。若出現 404，請檢查模型名稱是否仍受 API 支援。")
    else:
        st.warning("目前沒有找到新聞，請換一組關鍵字再搜尋。")
    st.caption("提醒：新聞標題的 AI 分析只是輿論線索整理，不等於完整新聞查證，也不是投資建議。")

# ---------------------------------------------------------
# Tab 5：資料下載
# ---------------------------------------------------------
with tab_data:
    st.markdown("## 📥 原始資料與下載")
    st.markdown("可將目前載入的資料下載為 CSV，方便在 Excel 或其他分析工具中使用。")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("### 🏛️ FRED 總經資料")
        st.dataframe(macro_df.tail(20), use_container_width=True)
        st.download_button(
            "⬇️ 下載總經資料 CSV",
            data=macro_df.to_csv(index=True).encode("utf-8-sig"),
            file_name="fred_macro_data.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        st.markdown("### 📈 市場行情資料")
        if not market_df.empty:
            st.dataframe(market_df.tail(20), use_container_width=True)
            st.download_button(
                "⬇️ 下載市場資料 CSV",
                data=market_df.to_csv(index=True).encode("utf-8-sig"),
                file_name="market_data.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("目前沒有可下載的市場資料。")

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#8995a8;font-size:0.9rem;'>🐻 小熊總經研究室｜資料僅供研究與教學參考，不構成投資建議。</div>",
    unsafe_allow_html=True,
)

        
