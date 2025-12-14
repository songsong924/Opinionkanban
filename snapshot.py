import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta

# ================= ⚙️ 核心配置 =================
POLL_INTERVAL = 10       # 扫描频率：10秒 (既快又安全)
MAX_HISTORY_MINUTES = 30 # 最大记忆时长：30分钟
CACHE_FILE = "cyberpunk_data_pool.csv" # 本地持久化文件

# ================= 🎨 科技风 UI 注入 =================
st.set_page_config(layout="wide", page_title="OPINION // CORE MONITOR")

# 注入自定义 CSS (赛博朋克风格)
st.markdown("""
<style>
    /* 全局背景微调 */
    .stApp {
        background-color: #0e1117;
    }
    
    /* 标题样式 */
    h1 {
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
        color: #00ff41; /* 黑客绿 */
        text-shadow: 0 0 10px #00ff41;
        border-bottom: 2px solid #00ff41;
        padding-bottom: 10px;
    }
    
    h3 {
        font-family: 'Courier New', monospace;
        color: #e0e0e0;
        border-left: 5px solid #ff00ff; /* 赛博粉 */
        padding-left: 10px;
    }

    /* 表格容器样式 */
    .stDataFrame {
        border: 1px solid #333;
        box-shadow: 0 0 15px rgba(0, 255, 65, 0.1);
    }

    /* 状态栏样式 */
    .status-text {
        font-family: 'Courier New', monospace;
        color: #00bfff;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫核心 =================
def fetch_raw_data():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage") # 云端防崩
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
        time.sleep(2) # 极速等待
        
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
                # 原始时间字符串 (网页上的 "10 mins ago" 或具体时间)
                raw_time_str = cols[9].text 
                
                # 生成唯一ID
                unique_key = f"{event}_{market}_{side}_{amount}_{raw_time_str}"
                
                new_items.append({
                    "unique_key": unique_key,
                    "Event": event,
                    "Market": market,
                    "Side": side,
                    "Amount": amount,
                    "ScrapeTime": current_scrape_time # 记录抓取时间作为基准
                })
            except:
                continue
    except Exception as e:
        print(f"Scrape Error: {e}")
    finally:
        driver.quit()
        
    return pd.DataFrame(new_items)

# ================= 💾 数据引擎 (滚动窗口) =================

# 初始化或加载历史数据
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

if 'last_update_str' not in st.session_state:
    st.session_state.last_update_str = "SYSTEM_BOOT..."

def process_data_pool(new_df):
    """
    1. 合并新数据
    2. 去重
    3. 清理超过30分钟的旧数据
    4. 保存快照
    """
    pool = st.session_state.master_pool
    
    if not new_df.empty:
        # 合并
        pool = pd.concat([pool, new_df])
        # 去重 (保留最新的)
        pool = pool.drop_duplicates(subset=['unique_key'], keep='last')
    
    # 清理旧数据 (只保留最近 MAX_HISTORY_MINUTES)
    if not pool.empty:
        cutoff_time = datetime.now() - timedelta(minutes=MAX_HISTORY_MINUTES)
        pool = pool[pool['ScrapeTime'] > cutoff_time]
    
    st.session_state.master_pool = pool
    # 存盘
    pool.to_csv(CACHE_FILE, index=False)
    return pool

def get_ranking(minutes_window):
    """
    从主池中切片，计算排名
    """
    pool = st.session_state.master_pool
    if pool.empty:
        return pd.DataFrame()
    
    # 筛选时间窗口
    cutoff = datetime.now() - timedelta(minutes=minutes_window)
    subset = pool[pool['ScrapeTime'] > cutoff]
    
    if subset.empty:
        return pd.DataFrame()
        
    # 聚合
    ranking = subset.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum')
    ).reset_index()
    
    # 排序
    ranking = ranking.sort_values(by=['Count', 'Total'], ascending=[False, False])
    ranking.index = range(1, len(ranking) + 1)
    return ranking

def style_ranking(df):
    """给表格上色"""
    if df.empty: return df
    
    # 颜色逻辑
    def highlight_side(val):
        color = '#00ff41' if ('BUY' in val or 'YES' in val) else '#ff0055'
        return f'color: {color}; font-weight: bold; text-shadow: 0 0 5px {color};'
    
    return df.style.applymap(highlight_side, subset=['Side']).format({"Total": "${:,.0f}"})

# ================= 🖥️ 指挥舱界面 =================

st.title("OPINION // ANALYTICS_HUB")
st.markdown("<div class='status-text'>System Status: ONLINE | Mode: CONTINUOUS_SCAN | Target: opinionanalytics.xyz</div>", unsafe_allow_html=True)

st.divider()

# 三栏布局
col1, col2, col3 = st.columns(3)

# 占位符 (防止页面跳动，先占坑)
with col1:
    st.markdown("### ⚡ 1 MINUTE (BURST)")
    c1_placeholder = st.empty()
with col2:
    st.markdown("### 🌊 10 MINUTES (FLOW)")
    c2_placeholder = st.empty()
with col3:
    st.markdown("### 💎 30 MINUTES (TREND)")
    c3_placeholder = st.empty()

# 底部状态条
st.divider()
status_log = st.empty()

# ================= 🔄 主循环 =================
while True:
    # 1. 抓取与更新数据池
    status_log.markdown(f"`[{datetime.now().strftime('%H:%M:%S')}] SCANNING NETWORK...`")
    
    new_batch = fetch_raw_data()
    process_data_pool(new_batch) # 更新主数据池
    
    current_time = datetime.now().strftime('%H:%M:%S')
    
    # 2. 生成三份报表
    df_1m = get_ranking(1)
    df_10m = get_ranking(10)
    df_30m = get_ranking(30)
    
    # 3. 渲染 UI (带进度条配置)
    def render_table(placeholder, df, max_count):
        if df.empty:
            placeholder.info("NO_DATA_SIGNAL")
        else:
            placeholder.dataframe(
                style_ranking(df),
                use_container_width=True,
                height=500, # 统一高度
                column_config={
                    "Count": st.column_config.ProgressColumn(
                        format="%d",
                        min_value=0,
                        max_value=int(max_count * 1.2) if max_count > 0 else 10,
                    ),
                    "Event": st.column_config.TextColumn(width="small"),
                    "Market": st.column_config.TextColumn(width="small")
                }
            )
            
    # 计算各自的最大值用于进度条比例
    max_1m = df_1m['Count'].max() if not df_1m.empty else 0
    max_10m = df_10m['Count'].max() if not df_10m.empty else 0
    max_30m = df_30m['Count'].max() if not df_30m.empty else 0
    
    render_table(c1_placeholder, df_1m, max_1m)
    render_table(c2_placeholder, df_10m, max_10m)
    render_table(c3_placeholder, df_30m, max_30m)
    
    # 4. 状态更新
    pool_size = len(st.session_state.master_pool)
    status_log.markdown(f"`[{current_time}] SYNC_COMPLETE | DATA_POOL_SIZE: {pool_size} | NEXT_SCAN: {POLL_INTERVAL}s`")
    
    # 5. 短暂等待 (不显示倒计时，静默等待)
    time.sleep(POLL_INTERVAL)
