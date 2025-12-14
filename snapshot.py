import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta

# ================= ⚙️ 核心配置 =================
POLL_INTERVAL = 10       # 10秒刷新
MAX_HISTORY_MINUTES = 30 # 数据池保留30分钟
CACHE_FILE = "matrix_data_pool.csv" 

# ================= 🎨 极客 UI (MATRIX THEME) =================
st.set_page_config(layout="wide", page_title="OPINION // MATRIX_CORE")

# 注入深度 CSS (强制覆盖 Streamlit 原生样式)
st.markdown("""
<style>
    /* 1. 全局背景与字体 - 纯黑底色 */
    .stApp {
        background-color: #000000;
        color: #00ff41;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* 2. 标题特效 - 荧光绿 + 阴影 */
    h1, h2, h3 {
        color: #00ff41 !important;
        text-shadow: 0 0 10px #00ff41, 0 0 20px #00ff41;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* 3. 表格深度美化 (去除所有白底) */
    [data-testid="stDataFrame"] {
        border: 1px solid #003300;
        background-color: #000000 !important;
    }
    
    /* 表头 */
    [data-testid="stDataFrame"] thead tr th {
        background-color: #001100 !important;
        color: #00ff41 !important;
        border-bottom: 2px solid #00ff41 !important;
        font-size: 14px !important;
    }
    
    /* 表格内容区域背景 */
    [data-testid="stDataFrame"] tbody {
        background-color: #000000 !important;
    }
    
    /* 单元格文字 */
    [data-testid="stDataFrame"] tbody tr td {
        background-color: #000000 !important;
        color: #ccffcc !important; /* 稍微浅一点的绿，方便阅读 */
        border-bottom: 1px solid #003300 !important;
        font-family: 'Courier New', monospace;
    }

    /* --- 关键修改：防止文字截断 --- */
    /* 强制单元格内容换行，不显示省略号 */
    div[data-testid="stdataframe-cell-content"] {
        white-space: normal !important;
        height: auto !important;
        overflow-wrap: break-word !important;
        padding: 5px !important;
        line-height: 1.5 !important;
    }

    /* 4. 进度条颜色改为绿色 */
    .stProgress > div > div > div > div {
        background-color: #00ff41 !important;
    }
    
    /* 5. 状态栏 */
    .status-terminal {
        border: 1px dashed #00ff41;
        padding: 10px;
        color: #00ff41;
        background-color: #050505;
        font-size: 0.85em;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫核心 =================
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
    except Exception as e:
        pass # 静默失败
    finally:
        driver.quit()
        
    return pd.DataFrame(new_items)

# ================= 💾 数据逻辑 =================

if 'master_pool' not in st.session_state:
    if os.path.exists(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            df['ScrapeTime'] = pd.to_datetime(df['ScrapeTime'])
            st.session_state.master_pool = df
        except: st.session_state.master_pool = pd.DataFrame()
    else: st.session_state.master_pool = pd.DataFrame()

def process_data_pool(new_df):
    pool = st.session_state.master_pool
    if not new_df.empty:
        pool = pd.concat([pool, new_df])
        pool = pool.drop_duplicates(subset=['unique_key'], keep='last')
    
    if not pool.empty:
        cutoff_time = datetime.now() - timedelta(minutes=MAX_HISTORY_MINUTES)
        pool = pool[pool['ScrapeTime'] > cutoff_time]
    
    st.session_state.master_pool = pool
    pool.to_csv(CACHE_FILE, index=False)
    return pool

def get_ranking(minutes_window):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()
    
    cutoff = datetime.now() - timedelta(minutes=minutes_window)
    subset = pool[pool['ScrapeTime'] > cutoff]
    
    if subset.empty: return pd.DataFrame()
        
    ranking = subset.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum')
    ).reset_index()
    
    # 排序
    ranking = ranking.sort_values(by=['Count', 'Total'], ascending=[False, False])
    ranking.index = range(1, len(ranking) + 1)
    
    # 重命名列以配合 UI 宽度
    ranking = ranking.rename(columns={"Count": "Freq"})
    return ranking

# ================= 🖥️ 界面渲染 =================

st.title("OPINION // MATRIX_HUB")
st.markdown("---")

# 三栏布局
col1, col2, col3 = st.columns(3)

# 占位符
with col1:
    st.markdown("### ⚡ 1 MINUTE")
    c1_placeholder = st.empty()
with col2:
    st.markdown("### 🌊 10 MINUTES")
    c2_placeholder = st.empty()
with col3:
    st.markdown("### 💎 30 MINUTES")
    c3_placeholder = st.empty()

status_log = st.empty()

# 样式函数：给 Side 上色 (红/绿)
def apply_matrix_color(df):
    def highlight_text(val):
        if 'BUY' in val or 'YES' in val:
            return 'color: #00ff41; font-weight: bold;' # 亮绿
        return 'color: #ff0055; font-weight: bold;'    # 赛博红
    return df.style.applymap(highlight_text, subset=['Side']).format({"Total": "${:,.0f}"})

# 渲染函数 (关键：配置 column_config 防止截断)
def render_cyber_table(placeholder, df, max_val):
    if df.empty:
        placeholder.code("NO_DATA_SIGNAL...", language="bash")
    else:
        placeholder.dataframe(
            apply_matrix_color(df),
            use_container_width=True,
            height=600, # 增加高度
            column_config={
                # 关键：设置 width="medium" 或 "large" 配合 CSS 强制换行
                "Event": st.column_config.TextColumn("Event", width="medium"),
                "Market": st.column_config.TextColumn("Market", width="medium"),
                "Side": st.column_config.TextColumn("Side", width="small"),
                "Total": st.column_config.NumberColumn("$$$", format="$%d"),
                "Freq": st.column_config.ProgressColumn(
                    "Vol", 
                    format="%d", 
                    min_value=0, 
                    max_value=int(max_val * 1.2) if max_val > 0 else 10
                )
            }
        )

# ================= 🔄 LOOP =================
while True:
    # 1. 抓取
    new_batch = fetch_raw_data()
    process_data_pool(new_batch)
    
    # 2. 计算
    df_1m = get_ranking(1)
    df_10m = get_ranking(10)
    df_30m = get_ranking(30)
    
    # 3. 渲染
    # 获取最大值用于统一度量衡
    m1 = df_1m['Freq'].max() if not df_1m.empty else 0
    m10 = df_10m['Freq'].max() if not df_10m.empty else 0
    m30 = df_30m['Freq'].max() if not df_30m.empty else 0
    
    render_cyber_table(c1_placeholder, df_1m, m1)
    render_cyber_table(c2_placeholder, df_10m, m10)
    render_cyber_table(c3_placeholder, df_30m, m30)
    
    # 4. 底部终端状态栏
    now_str = datetime.now().strftime('%H:%M:%S')
    pool_len = len(st.session_state.master_pool)
    status_log.markdown(
        f"""<div class='status-terminal'>
        SYSTEM_STATUS: ACTIVE<br>
        LAST_SYNC: {now_str} | DATA_POOL_SIZE: {pool_len}<br>
        TARGET: opinionanalytics.xyz | MODE: CONTINUOUS
        </div>""", 
        unsafe_allow_html=True
    )
    
    time.sleep(POLL_INTERVAL)
