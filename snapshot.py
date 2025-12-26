import streamlit as st
import pandas as pd
import requests
import time
import os
import gc
from datetime import datetime, timedelta

# ================= ⚙️ 核心配置 =================
POLL_INTERVAL = 15  # 刷新速度
MAX_HISTORY_MINUTES = 30  # 记忆时长
CACHE_FILE = "opinion_final_data.csv"

# Dune 配置
DUNE_API_KEY = "b01rHNwx0xlGPOlQDRQ0YTS5ZXrHAWaM"
ACTIVITY_START = datetime(2025, 12, 22).date()

# 您的品牌信息
MY_TWITTER_LINK = "https://x.com/songsong7364"
MY_BRAND_NAME = "0xsong"

# ================= 🎨 UI 深度定制 =================
st.set_page_config(layout="wide", page_title="OPINION热门交易看板")

# 图标 SVG
twitter_x_svg = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231h0.001zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="currentColor"/></svg>"""

st.markdown("""
<style>
    /* 全局背景 */
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }

    /* 1. 顶部品牌条 */
    .brand-link-container {
        display: inline-flex; align-items: center; text-decoration: none;
        background-color: #1f1f1f; border: 1px solid #333; padding: 6px 16px;
        border-radius: 30px; transition: all 0.3s ease; color: #e0e0e0; margin-bottom: 10px;
    }
    .brand-link-container:hover { border-color: #00ff41; color: #00ff41; }
    .brand-icon-wrapper { display: flex; align-items: center; margin-right: 8px; }
    .brand-text { font-weight: 600; font-size: 14px; }

    /* 2. 宏观数据卡片 */
    .metric-container {
        background-color: #1a1a1a; border: 1px solid #333; border-radius: 8px;
        padding: 15px; text-align: center; height: 100px;
        display: flex; flex-direction: column; justify-content: center;
    }
    .metric-title { font-size: 12px; color: #888; margin-bottom: 5px; }
    .metric-value { font-size: 26px; font-weight: bold; color: #fff; margin: 0; }
    .metric-sub { font-size: 11px; opacity: 0.7; margin-top: 5px; }
    .c-green { color: #00ff41; } .c-yellow { color: #facc15; }
    .c-blue { color: #3b82f6; }  .c-purple { color: #a855f7; }

    /* 3. 异动预警卡片 */
    .alert-card { 
        padding: 12px; border-radius: 6px; margin-bottom: 12px; 
        border-left: 4px solid; background: #161616; border: 1px solid #222; border-left-width: 4px;
    }
    .level-5 { border-left-color: #3b82f6; }   /* 蓝色 */
    .level-10 { border-left-color: #eab308; }  /* 黄色 */
    .level-30 { border-left-color: #ef4444; animation: pulse 2s infinite; } /* 红色 */

    @keyframes pulse { 0% {box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);} 70% {box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);} 100% {box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);} }

    /* 表格背景 */
    [data-testid="stDataFrame"] { background-color: #161616 !important; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ================= 🌍 模块一：全网人数 (Dune) =================
@st.cache_data(ttl=600)
def fetch_dune_data():
    url = "https://api.dune.com/api/v1/query/6048188/results?limit=1000"
    try:
        res = requests.get(url, headers={"x-dune-api-key": DUNE_API_KEY}, timeout=10)
        if res.status_code == 200:
            df = pd.DataFrame(res.json().get('result', {}).get('rows', []))
            df.columns = [c.lower() for c in df.columns]
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def render_macro_section():
    st.markdown("### 实时用户数据")
    df = fetch_dune_data()
    if not df.empty and 'new' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['new'] = pd.to_numeric(df['new'])
        df['old'] = pd.to_numeric(df['old']) if 'old' in df.columns else 0
        df['dau'] = df['new'] + df['old']

        df_view = df[df['date'] >= ACTIVITY_START].sort_values('date')
        if not df_view.empty:
            today = datetime.now().date()
            yest = today - timedelta(days=1)

            row_t = df_view[df_view['date'] == today]
            rt_val = row_t.iloc[0]['new'] if not row_t.empty else 0

            row_y = df_view[df_view['date'] == yest]
            y_new = row_y.iloc[0]['new'] if not row_y.empty else 0
            y_dau = row_y.iloc[0]['dau'] if not row_y.empty else 0
            total = df_view['new'].sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(
                f"<div class='metric-container'><div class='metric-title'>🟢 今日实时新增</div><div class='metric-value c-green'>+{rt_val:,.0f}</div><div class='metric-sub'>Today</div></div>",
                unsafe_allow_html=True)
            c2.markdown(
                f"<div class='metric-container'><div class='metric-title'>📅 昨日新增 (T-1)</div><div class='metric-value c-yellow'>+{y_new:,.0f}</div><div class='metric-sub'>Yesterday</div></div>",
                unsafe_allow_html=True)
            c3.markdown(
                f"<div class='metric-container'><div class='metric-title'>🔵 每日日活 (DAU)</div><div class='metric-value c-blue'>{y_dau:,.0f}</div><div class='metric-sub'>Yesterday</div></div>",
                unsafe_allow_html=True)
            c4.markdown(
                f"<div class='metric-container'><div class='metric-title'>🎄 赛季累计新增</div><div class='metric-value c-purple'>{total:,.0f}</div><div class='metric-sub'>Total</div></div>",
                unsafe_allow_html=True)


# ================= ⚡ 模块二：交易热榜 (Headless) =================
def fetch_raw_data_headless():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 静默
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    new_items = []

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.get("https://opinionanalytics.xyz/activity")
        time.sleep(6)  # 确保加载

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        current_time = datetime.now()

        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 8: continue

                side = cols[1].text
                market = cols[3].text
                event = cols[4].text
                amount = float(cols[6].text.replace('$', '').replace(',', ''))
                price_str = cols[7].text
                price = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0.0
                raw_time = cols[9].text

                unique_key = f"{event}_{market}_{side}_{amount}_{raw_time}"
                new_items.append({
                    "unique_key": unique_key, "Event": event, "Market": market, "Side": side,
                    "Amount": amount, "Price": price, "ScrapeTime": current_time
                })
            except:
                continue
    except:
        pass
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        del driver
        gc.collect()

    return pd.DataFrame(new_items)


# ================= 💾 数据核心 =================
if 'master_pool' not in st.session_state:
    if os.path.exists(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            df['ScrapeTime'] = pd.to_datetime(df['ScrapeTime'])
            st.session_state.master_pool = df
        except:
            st.session_state.master_pool = pd.DataFrame()
    else:
        st.session_state.master_pool = pd.DataFrame()

if 'rank_history' not in st.session_state: st.session_state.rank_history = {}


def process_data(new_df):
    pool = st.session_state.master_pool
    if not new_df.empty:
        pool = pd.concat([pool, new_df])
        pool = pool.drop_duplicates(subset=['unique_key'], keep='last')

    if not pool.empty:
        pool['ScrapeTime'] = pd.to_datetime(pool['ScrapeTime'])
        cutoff = datetime.now() - timedelta(minutes=MAX_HISTORY_MINUTES)
        pool = pool[pool['ScrapeTime'] > cutoff]

    st.session_state.master_pool = pool
    try:
        pool.to_csv(CACHE_FILE, index=False)
    except:
        pass


def get_enhanced_ranking(minutes, window_name):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()

    cutoff = datetime.now() - timedelta(minutes=minutes)
    subset = pool[pool['ScrapeTime'] > cutoff]
    if subset.empty: return pd.DataFrame()

    df = subset.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum'),
    ).reset_index()

    # 多空比
    try:
        event_totals = subset.groupby(['Event', 'Market'])['Amount'].sum().to_dict()
        long_subset = subset[subset['Side'].isin(['BUY', 'YES'])]
        long_totals = long_subset.groupby(['Event', 'Market'])['Amount'].sum().to_dict()

        def calc_ratio(row):
            key = (row['Event'], row['Market'])
            total = event_totals.get(key, 0)
            if total == 0: return 0.5
            return long_totals.get(key, 0) / total

        df['Sentiment'] = df.apply(calc_ratio, axis=1)
    except:
        df['Sentiment'] = 0.5

    df = df.sort_values(by=['Count', 'Total'], ascending=[False, False]).reset_index(drop=True)
    df.index += 1

    # 趋势箭头
    current_ranks = {}
    trends = []
    prev_ranks = st.session_state.rank_history.get(window_name, {})

    for rank, row in df.iterrows():
        key = f"{row['Event']}_{row['Market']}_{row['Side']}"
        current_ranks[key] = rank
        if key not in prev_ranks:
            trends.append("🔥")
        else:
            diff = prev_ranks[key] - rank
            if diff > 0:
                trends.append("⬆️")
            elif diff < 0:
                trends.append("⬇️")
            else:
                trends.append("➖")

    df['Trend'] = trends
    st.session_state.rank_history[window_name] = current_ranks
    return df


def check_alerts():
    pool = st.session_state.master_pool
    if pool.empty: return [], [], []
    a5, a10, a30 = [], [], []
    for name, group in pool.groupby(['Event', 'Market', 'Side']):
        if len(group) < 2: continue
        group = group.sort_values('ScrapeTime')
        s, e = group.iloc[0]['Price'], group.iloc[-1]['Price']
        if s == 0: continue
        diff = e - s
        pct = (diff / s) * 100
        item = {"Title": name[0], "Market": name[1], "Side": name[2], "Diff": pct, "Start": s, "End": e}
        if abs(pct) >= 30:
            a30.append(item)
        elif abs(pct) >= 10:
            a10.append(item)
        elif abs(pct) >= 5:
            a5.append(item)
    return a5, a10, a30


# ================= 🖥️ 渲染主界面 =================
st.title("OPINION热门交易看板")

# 1. 品牌按钮
st.markdown(f"""
    <a href="{MY_TWITTER_LINK}" target="_blank" class="brand-link-container">
        <span class="brand-icon-wrapper">{twitter_x_svg}</span>
        <span class="brand-text">{MY_BRAND_NAME}</span>
    </a>
""", unsafe_allow_html=True)

# 2. 全网数据
render_macro_section()
st.divider()

# 3. 交易热榜 (后台自动刷新)
new_data = fetch_raw_data_headless()
process_data(new_data)

st.markdown("### 🔥 实时热点")
tab1, tab2, tab3, tab4 = st.tabs(["⚡ 1 分钟", "🌊 10 分钟", "💎 30 分钟", "🚨 异动预警"])


def style_df(df):
    def highlight(
            val): return 'color: #4ade80; font-weight: bold' if 'BUY' in val or 'YES' in val else 'color: #f87171; font-weight: bold'

    return df.style.applymap(highlight, subset=['Side']).format({"Total": "${:,.0f}"})


def render_tab(m, tab, win_name):
    with tab:
        df = get_enhanced_ranking(m, win_name)
        if df.empty:
            st.info("等待数据积累 (请保持页面开启)...")
        else:
            st.dataframe(
                style_df(df),
                use_container_width=True,
                height=600,
                column_config={
                    "Trend": st.column_config.TextColumn("趋势", width="small"),
                    "Event": st.column_config.TextColumn("事件", width="large"),
                    "Market": st.column_config.TextColumn("市场", width="medium"),
                    "Side": st.column_config.TextColumn("方向", width="small"),
                    "Count": st.column_config.ProgressColumn("热度", format="%d", min_value=0,
                                                             max_value=int(df['Count'].max() * 1.2)),
                    "Total": st.column_config.NumberColumn("成交额", format="$%d"),
                    "Sentiment": st.column_config.ProgressColumn(
                        "多空情绪", format="%.2f", min_value=0, max_value=1
                    ),
                }
            )
            st.caption("💡 交易频率越高挂单成功率越高、买卖情绪越靠近中间买入亏损概率越低")


render_tab(1, tab1, "1m")
render_tab(10, tab2, "10m")
render_tab(30, tab3, "30m")

# 4. 异动预警
a5, a10, a30 = check_alerts()
with tab4:
    def render_alert_cards(alerts, level_class):
        if not alerts:
            st.caption("无异动")
        else:
            for i in alerts:
                color = "#22c55e" if i['Diff'] > 0 else "#ef4444"
                arrow = "📈" if i['Diff'] > 0 else "📉"
                html = f"""
                <div class="alert-card {level_class}">
                    <div style="font-size:12px; color:#888">{i['Market']}</div>
                    <div style="font-weight:bold; font-size:14px; margin:4px 0; color:#fff">{i['Title']}</div>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="background:#333; padding:2px 8px; border-radius:4px; font-size:11px; color:#ccc">{i['Side']}</span>
                        <span style="color:{color}; font-weight:bold; font-size:13px">{arrow} {i['Start']:.1f} ➝ {i['End']:.1f} ({i['Diff']:+.1f}%)</span>
                    </div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)


    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("##### 波动 > 5%"); render_alert_cards(a5, "level-5")
    with c2:
        st.markdown("##### 波动 > 10%"); render_alert_cards(a10, "level-10")
    with c3:
        st.markdown("##### 波动 > 30%"); render_alert_cards(a30, "level-30")

# 底部状态
st.markdown(
    f"<div style='color:#555; font-size:12px; margin-top:20px; text-align:right'>缓存: {len(st.session_state.master_pool)} 条 | 更新: {datetime.now().strftime('%H:%M:%S')}</div>",
    unsafe_allow_html=True)

time.sleep(POLL_INTERVAL)
st.rerun()
