import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta

# ================= ⚙️ 配置区 =================
POLL_INTERVAL = 10       # 刷新间隔
MAX_HISTORY_MINUTES = 30 # 最大记忆时长
CACHE_FILE = "opinion_data_pool.csv" 

# ================= 🎨 UI 深度定制 =================
st.set_page_config(layout="wide", page_title="OPINION 热门监控")

st.markdown("""
<style>
    /* 1. 全局深色背景 */
    .stApp {
        background-color: #0e0e0e; 
        color: #e0e0e0;
    }
    
    /* 2. 标签页按钮样式 */
    button[data-baseweb="tab"] {
        background-color: #1a1a1a;
        color: #888;
        border-radius: 5px;
        margin-right: 5px;
        border: 1px solid #333;
        padding: 5px 20px;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #00ff41 !important;
        color: #000000 !important;
        border: 1px solid #00ff41 !important;
        font-weight: bold;
    }

    /* 3. 表格样式 */
    [data-testid="stDataFrame"] {
        background-color: #161616 !important;
        border: 1px solid #333 !important;
        border-radius: 5px;
    }
    
    /* 4. 强制文字不折叠 */
    div[data-testid="stdataframe-cell-content"] {
        white-space: normal !important;
        line-height: 1.6 !important;
        padding: 10px 5px !important;
        color: #cccccc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        font-size: 14px;
    }
    
    /* 表头 */
    [data-testid="stDataFrame"] thead tr th {
        background-color: #1f1f1f !important;
        color: #888888 !important;
        font-size: 13px !important;
        font-weight: bold;
    }

    /* 5. 状态栏 */
    .status-bar {
        font-family: 'Courier New', monospace;
        color: #666;
        font-size: 12px;
        padding: 10px 0;
        border-top: 1px solid #333;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 =================
def fetch_raw_data():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    url = "https://opinionanalytics.xyz/activity"
    new_items = []
    
    try:
        driver.set_page_load_timeout(15)
        driver.get(url)
        time.sleep(2)
        
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        current_scrape_time = datetime.now()
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue
            try:
                side = cols[1].text
                market = cols[3].text
                event = cols[4].text
                amount = float(cols[6].text.replace('$', '').replace(',', ''))
                raw_time_str = cols[9].text 
                
                unique_key = f"{event}_{market}_{side}_{amount}_{raw_time_str}"
                
                new_items.append({
                    "unique_key": unique_key,
                    "Event": event,
                    "Market": market,
                    "Side": side,
                    "Amount": amount,
                    "ScrapeTime": current_scrape_time
                })
            except:
                continue
    except:
        pass
    finally:
        driver.quit()
        
    return pd.DataFrame(new_items)

# ================= 💾 数据核心 =================

if 'master_pool' not in st.session_state:
    if os.path.exists(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            df['ScrapeTime'] = pd.to_datetime(df['ScrapeTime'])
            st.session_state.master_pool = df
        except: st.session_state.master_pool = pd.DataFrame()
    else: st.session_state.master_pool = pd.DataFrame()

if 'app_start_time' not in st.session_state:
    st.session_state.app_start_time = datetime.now()

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
    pool.to_csv(CACHE_FILE, index=False)
    return pool

def get_view(minutes):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()
    
    cutoff = datetime.now() - timedelta(minutes=minutes)
    subset = pool[pool['ScrapeTime'] > cutoff]
    
    if subset.empty: return pd.DataFrame()
    
    df = subset.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum')
    ).reset_index()
    
    df = df.sort_values(by=['Count', 'Total'], ascending=[False, False])
    df.index = range(1, len(df) + 1)
    
    return df

# ================= 🖥️ 渲染逻辑 (关键修复区) =================

st.title("OPINION 热门交易看板")

# 1. 创建 Tabs
tab1, tab2, tab3 = st.tabs(["⚡ 1 分钟突发", "🌊 10 分钟主力", "💎 30 分钟趋势"])

# 2. 【关键】在 Tabs 内部预先创建“坑位”(Placeholder)
# 这样我们在循环里只更新这个坑位，就不会出现两个表格了
with tab1:
    placeholder_1m = st.empty()
with tab2:
    placeholder_10m = st.empty()
with tab3:
    placeholder_30m = st.empty()

status_ph = st.empty()

# 样式函数
def style_dataframe(df):
    def highlight(val):
        if 'BUY' in val or 'YES' in val:
            return 'color: #4ade80; font-weight: bold;' 
        return 'color: #f87171; font-weight: bold;'    
    return df.style.applymap(highlight, subset=['Side']).format({"Total": "${:,.0f}"})

# 渲染函数：接收 placeholder 而不是 tab
def render_to_placeholder(minutes, placeholder):
    df = get_view(minutes)
    
    with placeholder.container():
        if df.empty:
            st.info("正在接收交易数据流...")
        else:
            row_height = 35 
            dynamic_height = (len(df) + 1) * row_height + 3
            if dynamic_height > 800: dynamic_height = 800
            
            max_val = df['Count'].max()
            
            st.dataframe(
                style_dataframe(df),
                use_container_width=True, 
                height=int(dynamic_height),    
                column_config={
                    "Event": st.column_config.TextColumn("事件", width="large"), 
                    "Market": st.column_config.TextColumn("市场", width="medium"),
                    "Side": st.column_config.TextColumn("方向", width="small"),
                    "Total": st.column_config.NumberColumn("成交额 ($)", format="$%d"),
                    "Count": st.column_config.ProgressColumn(
                        "热度", 
                        format="%d", 
                        min_value=0, 
                        max_value=int(max_val * 1.2),
                    )
                }
            )

# ================= 🔄 LOOP =================
while True:
    new_data = fetch_raw_data()
    process_data(new_data)
    
    # 3. 循环中只更新坑位
    render_to_placeholder(1, placeholder_1m)
    render_to_placeholder(10, placeholder_10m)
    render_to_placeholder(30, placeholder_30m)
    
    # 底部状态
    pool_size = len(st.session_state.master_pool)
    status_ph.markdown(f"""
    <div class='status-bar'>
    系统状态: 在线 | 缓存池记录: {pool_size} | 刷新时间: {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)
    
    time.sleep(POLL_INTERVAL)
