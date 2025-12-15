import streamlit as st
import pandas as pd
import time
import os
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime, timedelta

# ================= 🛡️ 安全启动配置 =================
st.set_page_config(layout="wide", page_title="0xsong 监控终端")

# 注入 CSS (保持黑客风)
st.markdown("""
<style>
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    [data-testid="stDataFrame"] { background-color: #161616 !important; }
    .error-box { background-color: #330000; border: 1px solid red; padding: 20px; border-radius: 5px; color: #ffcccc; }
</style>
""", unsafe_allow_html=True)

# ================= 🕵️‍♂️ 自动侦测环境 =================
def get_driver():
    """智能查找浏览器路径，防止云端路径不一致导致的崩溃"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # 1. 自动寻找 Chromium 浏览器
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or "/usr/bin/chromium"
    if chromium_path:
        chrome_options.binary_location = chromium_path
    
    # 2. 自动寻找 驱动 (Driver)
    driver_path = shutil.which("chromedriver") or shutil.which("chromium-driver") or "/usr/bin/chromedriver"
    
    # 3. 尝试启动
    if driver_path:
        service = Service(driver_path)
        return webdriver.Chrome(service=service, options=chrome_options)
    else:
        # 如果找不到驱动，尝试直接启动（依赖 PATH）
        return webdriver.Chrome(options=chrome_options)

# ================= 🕷️ 爬虫引擎 =================
def fetch_raw_data():
    driver = None
    try:
        driver = get_driver()
        url = "https://opinionanalytics.xyz/activity"
        
        driver.set_page_load_timeout(20)
        driver.get(url)
        time.sleep(2)
        
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
        # ⚠️ 关键：如果爬虫出错，不要崩溃，而是抛出异常让主程序捕获
        raise e 
    finally:
        if driver:
            try: driver.quit()
            except: pass

# ================= 🧠 主逻辑 (带防崩保护) =================
try:
    # 初始化
    if 'master_pool' not in st.session_state: st.session_state.master_pool = pd.DataFrame()
    
    st.title("🦅 Opinion Alpha 终端")
    
    # 运行一次爬虫
    with st.spinner("正在连接卫星数据..."):
        new_data = fetch_raw_data()
        
    # 处理数据
    if not new_data.empty:
        pool = st.session_state.master_pool
        pool = pd.concat([pool, new_data]).drop_duplicates(subset=['unique_key'], keep='last')
        # 只保留30分钟
        pool['ScrapeTime'] = pd.to_datetime(pool['ScrapeTime'])
        cutoff = datetime.now() - timedelta(minutes=30)
        st.session_state.master_pool = pool[pool['ScrapeTime'] > cutoff]

    # 渲染界面
    tab1, tab2 = st.tabs(["⚡ 1 分钟实时", "🌊 全局数据"])
    
    pool = st.session_state.master_pool
    if not pool.empty:
        # 简单处理用于展示
        df_show = pool.groupby(['Event', 'Market', 'Side']).agg(
            热度=('unique_key', 'count'),
            成交额=('Amount', 'sum'),
            最新价=('Price', 'last')
        ).sort_values('热度', ascending=False).reset_index()
        
        with tab1:
            st.dataframe(df_show, use_container_width=True, height=600)
    else:
        st.info("暂无数据，正在持续监听中...")

    # 自动刷新
    time.sleep(10)
    st.rerun()

except Exception as e:
    # 🚨 终极错误捕获：如果出错，直接把错误打印在屏幕上！
    st.markdown(f"""
    <div class="error-box">
        <h3>🚫 系统启动失败 (DEBUG模式)</h3>
        <p>检测到以下错误，请截图发给技术支持：</p>
        <pre>{str(e)}</pre>
        <p>可能的原因：packages.txt 未正确配置 或 内存不足。</p>
    </div>
    """, unsafe_allow_html=True)
    # 打印一些环境信息帮助调试
    st.write("Environment Debug Info:")
    st.write(f"Chromium Path: {shutil.which('chromium') or 'Not Found'}")
    st.write(f"Driver Path: {shutil.which('chromedriver') or shutil.which('chromium-driver') or 'Not Found'}")
