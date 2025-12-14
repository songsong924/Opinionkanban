import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta

# ================= ⚙️ 核心配置 =================
POLL_INTERVAL = 10       # 刷新频率
MAX_HISTORY_MINUTES = 30 # 最大记忆时间
CACHE_FILE = "matrix_data_pool.csv" 

# ================= 🎨 竖屏黑客 UI =================
st.set_page_config(layout="wide", page_title="OPINION // VERTICAL_CORE")

st.markdown("""
<style>
    /* 1. 彻底黑化背景 */
    .stApp {
        background-color: #000000;
        color: #00ff41;
        font-family: 'Courier New', monospace;
    }
    
    /* 2. 标题样式 */
    h1, h2, h3 {
        color: #00ff41 !important;
        text-shadow: 0 0 10px #00ff41;
        text-transform: uppercase;
        border-left: 5px solid #00ff41;
        padding-left: 15px;
        margin-top: 30px; /* 增加垂直间距 */
    }
    
    /* 3. 表格深度定制 (去除所有白底) */
    [data-testid="stDataFrame"] {
        border: 1px solid #003300;
        background-color: #000000 !important;
        box-shadow: 0 0 15px rgba(0, 255, 65, 0.1);
    }
    
    /* 表头 */
    [data-testid="stDataFrame"] thead tr th {
        background-color: #051105 !important;
        color: #00ff41 !important;
        border-bottom: 2px solid #00ff41 !important;
    }
    
    /* 单元格 */
    [data-testid="stDataFrame"] tbody tr td {
        background-color: #000000 !important;
        color: #ccffcc !important;
        border-bottom: 1px solid #112211 !important;
        font-family: 'Courier New', monospace;
    }

    /* --- 关键：解决文字折叠 --- */
    div[data-testid="stdataframe-cell-content"] {
        white-space: normal !important; /* 强制换行 */
        height: auto !important;
        line-height: 1.5 !important;
        padding: 8px !important;
    }

    /* 4. 去除 Streamlit 默认的白色区块装饰 */
    div[data-testid="stVerticalBlock"] {
        background-color: transparent !important;
    }
    
    /* 5. 状态栏 */
    .status-line {
        color: #005500;
        font-size: 0.8em;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫部分 (保持不变) =================
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

# ================= 💾 数据处理 (修复时间格式BUG) =================

if 'master_pool' not in st.session_state:
    if os.path.exists(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            # 【关键修复】确保读取后的时间列是 datetime 类型，否则无法比较大小
            df['ScrapeTime'] = pd.to_datetime(df['ScrapeTime'])
            st.session_state.master_pool = df
        except: st.session_state.master_pool = pd.DataFrame()
    else: st.session_state.master_pool = pd.DataFrame()

def process_data_pool(new_df):
    pool = st.session_state.master_pool
    if not new_df.empty:
        pool = pd.concat([pool, new_df])
        pool = pool.drop_duplicates(subset=['unique_key'], keep='last')
    
    # 清理旧数据
    if not pool.empty:
        # 确保 pool['ScrapeTime'] 是 datetime 类型
        pool['ScrapeTime'] = pd.to_datetime(pool['ScrapeTime'])
        cutoff_time = datetime.now() - timedelta(minutes=MAX_HISTORY_MINUTES)
        pool = pool[pool['ScrapeTime'] > cutoff_time]
    
    st.session_state.master_pool = pool
    pool.to_csv(CACHE_FILE, index=False)
    return pool

def get_ranking(minutes_window):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()
    
    # 筛选
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
    
    return ranking.rename(columns={"Count": "Freq"})

# ================= 🖥️ 竖向布局逻辑 =================

st.title("OPINION // MATRIX_VERTICAL")
st.markdown("<div class='status-line'>SYSTEM: ONLINE | LAYOUT: VERTICAL_STACK</div>", unsafe_allow_html=True)

# 样式着色
def apply_matrix_color(df):
    def highlight_text(val):
        if 'BUY' in val or 'YES' in val: return 'color: #00ff41; font-weight: bold;'
        return 'color: #ff0055; font-weight: bold;'
    return df.style.applymap(highlight_text, subset=['Side']).format({"Total": "${:,.0f}"})

# 渲染表格函数
def render_section(title, minutes, placeholder):
    df = get_ranking(minutes)
    
    # 获取最大值做进度条参考
    max_val = df['Freq'].max() if not df.empty else 0
    
    with placeholder.container():
        st.markdown(f"### {title}") # 标题在上方
        if df.empty:
            st.code("WAITING_FOR_DATA_STREAM...", language="bash")
        else:
            st.dataframe(
                apply_matrix_color(df),
                use_container_width=True, # 宽度铺满
                height=None, # 只有设置为None，才能自适应显示所有内容而不折叠，或者设置一个很大的值
                column_config={
                    # 设置为 large 确保宽列不换行太严重
                    "Event": st.column_config.TextColumn("Event Name", width="large"), 
                    "Market": st.column_config.TextColumn("Market Target", width="medium"),
                    "Side": st.column_config.TextColumn("Side", width="small"),
                    "Total": st.column_config.NumberColumn("$$$", format="$%d"),
                    "Freq": st.column_config.ProgressColumn(
                        "Volume", 
                        format="%d", 
                        min_value=0, 
                        max_value=int(max_val * 1.2) if max_val > 0 else 10
                    )
                },
                hide_index=False # 保留排名
            )
        st.markdown("---") # 分割线

# 占位符 (垂直排列)
p1 = st.empty()
p2 = st.empty()
p3 = st.empty()
log_p = st.empty()

# ================= 🔄 主循环 =================
while True:
    # 1. 抓取与更新
    new_batch = fetch_raw_data()
    process_data_pool(new_batch)
    
    # 2. 渲染三个板块 (垂直顺序)
    render_section("⚡ 1 MINUTE (BURST)", 1, p1)
    render_section("🌊 10 MINUTES (FLOW)", 10, p2)
    render_section("💎 30 MINUTES (TREND)", 30, p3)
    
    # 3. 底部日志
    pool_len = len(st.session_state.master_pool)
    log_p.markdown(f"`SYNC_TIME: {datetime.now().strftime('%H:%M:%S')} | POOL: {pool_len}`")
    
    time.sleep(POLL_INTERVAL)
