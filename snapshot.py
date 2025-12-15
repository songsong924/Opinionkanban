import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime, timedelta

# ================= 🛡️ 极简配置 =================
st.set_page_config(layout="wide", page_title="0xsong 监控")

# CSS 样式
st.markdown("""
<style>
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    [data-testid="stDataFrame"] { background-color: #161616 !important; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (原生路径版) =================
@st.cache_resource
def get_driver():
    """直接使用 Streamlit Cloud 系统自带的 Chrome，不下载额外驱动"""
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 无头模式
    chrome_options.add_argument("--no-sandbox") # 必需
    chrome_options.add_argument("--disable-dev-shm-usage") # 内存优化
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # ⚠️ 关键修改：直接指定云端路径
    # Streamlit Cloud 的 Chrome 默认安装在这里
    return webdriver.Chrome(options=chrome_options)

def fetch_raw_data():
    driver = None
    try:
        driver = get_driver()
        url = "https://opinionanalytics.xyz/activity"
        
        driver.get(url)
        # 等待稍微久一点，确保数据加载
        time.sleep(3)
        
        new_items = []
        rows = driver.find_elements("css selector", "table tbody tr")
        current_time = datetime.now()
        
        for row in rows:
            try:
                cols = row.find_elements("tag name", "td")
                if len(cols) < 8: continue
                
                side = cols[1].text
                market = cols[3].text
                event = cols[4].text
                amount = float(cols[6].text.replace('$', '').replace(',', ''))
                
                # 价格
                price_str = cols[7].text
                price = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0.0
                
                unique_key = f"{event}_{market}_{side}_{amount}_{cols[9].text}"
                
                new_items.append({
                    "unique_key": unique_key, "Event": event, "Market": market,
                    "Side": side, "Amount": amount, "Price": price, "ScrapeTime": current_time
                })
            except: continue
            
        return pd.DataFrame(new_items)
        
    except Exception as e:
        st.error(f"数据抓取失败: {str(e)}")
        return pd.DataFrame()

# ================= 🧠 主逻辑 =================

st.title("🦅 Opinion Alpha 终端 (Lite版)")

# 状态指示灯
status = st.empty()
status.info("正在初始化...")

# 初始化数据池
if 'master_pool' not in st.session_state:
    st.session_state.master_pool = pd.DataFrame()

# 抓取数据
with st.spinner("正在连接数据源..."):
    new_data = fetch_raw_data()

# 处理数据
if not new_data.empty:
    pool = st.session_state.master_pool
    pool = pd.concat([pool, new_data]).drop_duplicates(subset=['unique_key'], keep='last')
    
    # 保留30分钟
    pool['ScrapeTime'] = pd.to_datetime(pool['ScrapeTime'])
    cutoff = datetime.now() - timedelta(minutes=30)
    st.session_state.master_pool = pool[pool['ScrapeTime'] > cutoff]
    
    status.success(f"系统在线 | 数据池: {len(st.session_state.master_pool)} | 更新时间: {datetime.now().strftime('%H:%M:%S')}")
else:
    status.warning("未获取到新数据，请等待下一次刷新...")

# 展示
tab1, tab2 = st.tabs(["⚡ 实时榜单", "📊 数据池"])

pool = st.session_state.master_pool
if not pool.empty:
    # 简单的聚合展示
    df_view = pool.groupby(['Event', 'Market', 'Side']).agg(
        热度=('unique_key', 'count'),
        总额=('Amount', 'sum'),
        均价=('Price', 'mean')
    ).sort_values('热度', ascending=False).reset_index()
    
    df_view.index += 1
    
    with tab1:
        st.dataframe(df_view, use_container_width=True, height=600)
    with tab2:
        st.dataframe(pool, use_container_width=True)

# 自动刷新 (最安全的写法)
time.sleep(10)
st.rerun()
