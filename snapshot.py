import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta

# ================= ⚙️ 配置区 =================
POLL_INTERVAL = 10
MAX_HISTORY_MINUTES = 30
CACHE_FILE = "opinion_data_pool.csv"
MY_TWITTER_LINK = "https://twitter.com/songpeng_web3"
MY_BRAND_NAME = "0xsong"

# ================= 🎨 UI 配置 =================
st.set_page_config(layout="wide", page_title=f"{MY_BRAND_NAME} 看板")

# 注入 CSS
st.markdown("""
<style>
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    button[data-baseweb="tab"] { background-color: #1a1a1a; color: #888; border: 1px solid #333; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #00ff41 !important; color: black !important; }
    [data-testid="stDataFrame"] { background-color: #161616 !important; }
    .brand-link { text-decoration: none; color: #00ff41; border: 1px dashed #00ff41; padding: 10px; display: block; text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (增强稳健性) =================
@st.cache_resource
def get_driver():
    """获取浏览器驱动，带缓存防止反复重启"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # 自动管理驱动安装
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def fetch_raw_data():
    try:
        # 每次重新配置 options 以防实例崩溃，但在 Streamlit Cloud 最好复用
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        
        url = "https://opinionanalytics.xyz/activity"
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(3) # 等待加载
        
        new_items = []
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
                
                # 价格处理
                price_str = cols[7].text
                price = 0.0
                if price_str.replace('.', '', 1).isdigit():
                    price = float(price_str)
                
                unique_key = f"{event}_{market}_{side}_{amount}_{cols[9].text}"
                
                new_items.append({
                    "unique_key": unique_key,
                    "Event": event,
                    "Market": market,
                    "Side": side,
                    "Amount": amount,
                    "Price": price,
                    "ScrapeTime": current_time
                })
            except:
                continue
        driver.quit()
        return pd.DataFrame(new_items)
        
    except Exception as e:
        # 如果出错，返回空表，不要让程序崩溃
        print(f"Error: {e}")
        return pd.DataFrame()

# ================= 💾 数据处理 =================
if 'master_pool' not in st.session_state:
    st.session_state.master_pool = pd.DataFrame()

def process_data(new_df):
    if new_df.empty: return
    
    pool = st.session_state.master_pool
    pool = pd.concat([pool, new_df]).drop_duplicates(subset=['unique_key'], keep='last')
    
    # 清理过期
    if not pool.empty:
        pool['ScrapeTime'] = pd.to_datetime(pool['ScrapeTime'])
        cutoff = datetime.now() - timedelta(minutes=MAX_HISTORY_MINUTES)
        pool = pool[pool['ScrapeTime'] > cutoff]
        
    st.session_state.master_pool = pool

def get_view(minutes):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()
    
    cutoff = datetime.now() - timedelta(minutes=minutes)
    df = pool[pool['ScrapeTime'] > cutoff]
    if df.empty: return pd.DataFrame()
    
    res = df.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum'),
        AvgPrice=('Price', 'mean')
    ).reset_index()
    
    return res.sort_values(['Count', 'Total'], ascending=[False, False]).reset_index(drop=True)

# ================= 🖥️ 渲染 =================
st.title(f"{MY_BRAND_NAME} Alpha 终端")

st.markdown(f'<a href="{MY_TWITTER_LINK}" target="_blank" class="brand-link">📡 点击关注 Twitter: {MY_BRAND_NAME} 获取更多信号</a>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["⚡ 1 分钟", "🌊 10 分钟", "💎 30 分钟"])

# 自动刷新逻辑
if st.button("🔄 手动刷新 (系统会自动运行，无需点击)"):
    pass

new_data = fetch_raw_data()
process_data(new_data)

# 渲染表格
def render(minutes, tab):
    with tab:
        df = get_view(minutes)
        if df.empty:
            st.info("等待数据流入...")
        else:
            df.index += 1
            st.dataframe(
                df.style.format({"Total": "${:,.0f}", "AvgPrice": "{:.1f}%"}),
                use_container_width=True,
                height=500
            )

render(1, tab1)
render(10, tab2)
render(30, tab3)

st.caption(f"上次更新: {datetime.now().strftime('%H:%M:%S')} | 数据池: {len(st.session_state.master_pool)}")
time.sleep(POLL_INTERVAL)
st.rerun()
