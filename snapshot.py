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

# ================= 🎨 UI 深度定制 (Alpha123/Matrix 风格) =================
st.set_page_config(layout="wide", page_title="OPINION MONITOR")

st.markdown("""
<style>
    /* 1. 全局深色背景 */
    .stApp {
        background-color: #0e0e0e; /* 极深灰黑 */
        color: #e0e0e0;
    }
    
    /* 2. 标题风格 */
    h3 {
        color: #00ff41 !important; /* 黑客绿 */
        border-left: 4px solid #00ff41;
        padding-left: 12px;
        font-family: 'Courier New', monospace;
        letter-spacing: 1px;
        margin-top: 40px;
    }

    /* 3. 表格样式覆写 (去除白底，改为深灰卡片) */
    [data-testid="stDataFrame"] {
        background-color: #161616 !important;
        border: 1px solid #333 !important;
        border-radius: 5px;
    }
    
    /* 4. 强制文字不折叠，自动换行 */
    div[data-testid="stdataframe-cell-content"] {
        white-space: normal !important;
        line-height: 1.6 !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
        color: #cccccc; /* 数据行文字颜色 */
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 14px;
    }
    
    /* 表头样式 */
    [data-testid="stDataFrame"] thead tr th {
        background-color: #1f1f1f !important;
        color: #888888 !important;
        font-size: 12px !important;
        text-transform: uppercase;
    }

    /* 5. 状态栏微调 */
    .status-bar {
        font-family: monospace;
        color: #666;
        font-size: 12px;
        padding: 10px 0;
        border-top: 1px solid #333;
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
    # 反爬
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

# 记录开始运行时间，用于判断是否为冷启动
if 'app_start_time' not in st.session_state:
    st.session_state.app_start_time = datetime.now()

def process_data(new_df):
    pool = st.session_state.master_pool
    if not new_df.empty:
        pool = pd.concat([pool, new_df])
        pool = pool.drop_duplicates(subset=['unique_key'], keep='last')
    
    # 清理过期数据
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
    
    # 聚合
    df = subset.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum')
    ).reset_index()
    
    # 排序
    df = df.sort_values(by=['Count', 'Total'], ascending=[False, False])
    df.index = range(1, len(df) + 1)
    
    return df

# ================= 🖥️ 渲染逻辑 =================

st.title("OPINION // CORE")

# 占位符 (竖向堆叠)
ph_1m = st.empty()
ph_10m = st.empty()
ph_30m = st.empty()
status_ph = st.empty()

# 样式函数：给 Side 列上色，模仿 Alpha123 的胶囊效果
def style_dataframe(df):
    def highlight(val):
        if 'BUY' in val or 'YES' in val:
            return 'color: #4ade80; font-weight: bold;' # 亮绿
        return 'color: #f87171; font-weight: bold;'    # 亮红
    return df.style.applymap(highlight, subset=['Side']).format({"Total": "${:,.0f}"})

def render_table(title, minutes, placeholder):
    df = get_view(minutes)
    
    with placeholder.container():
        st.markdown(f"### ⚡ {title}")
        
        if df.empty:
            st.caption("Waiting for data stream...")
        else:
            # 动态计算高度：(行数 + 表头) * 行高 + 缓冲
            # 这样可以彻底解决 StreamlitInvalidHeightError 且不留白
            row_height = 35 
            dynamic_height = (len(df) + 1) * row_height + 3
            if dynamic_height > 800: dynamic_height = 800 # 设置最大上限，超过则滚动
            
            max_val = df['Count'].max()
            
            st.dataframe(
                style_dataframe(df),
                use_container_width=True, # 撑满宽度，解决折叠问题
                height=int(dynamic_height),    # 修复报错的关键：使用整数
                column_config={
                    "Event": st.column_config.TextColumn("Event", width="large"), # 宽列
                    "Market": st.column_config.TextColumn("Market", width="medium"),
                    "Side": st.column_config.TextColumn("Side", width="small"),
                    "Total": st.column_config.NumberColumn("Vol ($)", format="$%d"),
                    "Count": st.column_config.ProgressColumn(
                        "Freq", 
                        format="%d", 
                        min_value=0, 
                        max_value=int(max_val * 1.2),
                    )
                }
            )

# ================= 🔄 LOOP =================
while True:
    # 1. 抓取
    new_data = fetch_raw_data()
    process_data(new_data)
    
    # 2. 计算运行时长
    uptime = datetime.now() - st.session_state.app_start_time
    uptime_minutes = int(uptime.total_seconds() / 60)
    
    # 3. 渲染
    # 添加提示：如果运行时间不足，说明数据还在积累
    warmup_msg = ""
    if uptime_minutes < 10:
        warmup_msg = f"(System warming up: {uptime_minutes}m/10m - Data may look identical)"
    
    render_table("1 MINUTE BURST", 1, ph_1m)
    render_table(f"10 MINUTES FLOW {warmup_msg}", 10, ph_10m)
    render_table(f"30 MINUTES TREND {warmup_msg}", 30, ph_30m)
    
    # 4. 底部状态
    pool_size = len(st.session_state.master_pool)
    status_ph.markdown(f"""
    <div class='status-bar'>
    SYSTEM: ONLINE | POOL_SIZE: {pool_size} | LAST_SYNC: {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)
    
    time.sleep(POLL_INTERVAL)
