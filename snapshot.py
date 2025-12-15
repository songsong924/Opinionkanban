import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta

# ================= ⚙️ 配置区 =================
POLL_INTERVAL = 15       # 刷新间隔 (建议调大一点，给浏览器喘息时间)
MAX_HISTORY_MINUTES = 30 # 最大记忆时长
CACHE_FILE = "opinion_data_pool.csv"
MY_TWITTER_LINK = "https://twitter.com/songpeng_web3"
MY_BRAND_NAME = "0xsong"

# ================= 🎨 UI 深度定制 =================
st.set_page_config(layout="wide", page_title=f"{MY_BRAND_NAME} Alpha 终端")

# 图标资源
twitter_x_svg = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231h0.001zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="currentColor"/></svg>"""

st.markdown("""
<style>
    /* 全局 */
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    
    /* 品牌条 */
    .brand-link-container {
        display: inline-flex; align-items: center; text-decoration: none;
        background-color: #1f1f1f; border: 1px solid #333; padding: 8px 16px;
        border-radius: 30px; transition: all 0.3s ease; color: #e0e0e0; margin-bottom: 20px;
    }
    .brand-link-container:hover {
        background-color: #333; border-color: #00ff41; color: #00ff41;
        transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 255, 65, 0.2);
    }
    .brand-icon-wrapper { display: flex; align-items: center; margin-right: 8px; }
    .brand-text { font-weight: 600; font-size: 14px; }

    /* Tabs */
    button[data-baseweb="tab"] {
        background-color: #1a1a1a; color: #888; border-radius: 5px; margin-right: 5px; border: 1px solid #333;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #00ff41 !important; color: #000000 !important; border: 1px solid #00ff41 !important; font-weight: bold;
    }

    /* 表格优化 */
    [data-testid="stDataFrame"] { background-color: #161616 !important; border: 1px solid #333 !important; }
    [data-testid="stDataFrame"] thead tr th { background-color: #1f1f1f !important; color: #888 !important; }
    
    /* 异动卡片 */
    .alert-card { padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid; background: #1a1a1a; }
    .level-5 { border-color: #3b82f6; }
    .level-10 { border-color: #eab308; }
    .level-30 { border-color: #ef4444; animation: pulse 2s infinite; }
    @keyframes pulse { 0% {box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);} 70% {box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);} 100% {box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);} }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (带状态反馈) =================
def fetch_raw_data(status_container):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    
    driver = None
    new_items = []
    
    try:
        status_container.update(label="🚀 正在启动隐形浏览器...", state="running")
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        
        url = "https://opinionanalytics.xyz/activity"
        
        status_container.update(label="📡 正在连接 Opinion 数据源...", state="running")
        driver.set_page_load_timeout(30) # 延长超时时间
        driver.get(url)
        time.sleep(3) # 等待渲染
        
        status_container.update(label="🔍 正在解析交易数据...", state="running")
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
                price_str = cols[7].text 
                price = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0.0
                raw_time_str = cols[9].text 
                
                unique_key = f"{event}_{market}_{side}_{amount}_{raw_time_str}"
                
                new_items.append({
                    "unique_key": unique_key,
                    "Event": event,
                    "Market": market,
                    "Side": side,
                    "Amount": amount,
                    "Price": price,
                    "ScrapeTime": current_scrape_time
                })
            except:
                continue
        status_container.update(label=f"✅ 成功抓取 {len(new_items)} 条数据", state="complete")
        time.sleep(1) # 展示一下成功状态
    except Exception as e:
        status_container.update(label=f"❌ 抓取失败: {str(e)}", state="error")
    finally:
        if driver:
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

if 'rank_history' not in st.session_state:
    st.session_state.rank_history = {}
    
# 新增：运行状态控制
if 'is_running' not in st.session_state:
    st.session_state.is_running = False

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
