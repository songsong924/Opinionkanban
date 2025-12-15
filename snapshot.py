import streamlit as st
import pandas as pd
import time
import gc 
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ================= 🛡️ 极简内存优化配置 =================
st.set_page_config(layout="wide", page_title="0xsong 终端")

MY_TWITTER_LINK = "https://x.com/songsong7364"
MY_BRAND_NAME = "0xsong"
REFRESH_RATE = 20 # 休眠时间 (秒)，调大一点可以让服务器“回血”，防止崩盘

# 白色图标
twitter_white_svg = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231h0.001zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="#ffffff"/></svg>"""

# 强制注入皮肤 (恢复经典黑客风)
st.markdown("""
<style>
    /* 全局去白边 */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    
    /* 表格样式 */
    [data-testid="stDataFrame"] { background-color: #161616 !important; border: 1px solid #333 !important; }
    [data-testid="stDataFrame"] thead tr th { background-color: #1f1f1f !important; color: #888 !important; }
    
    /* 品牌条 */
    .brand-link-container {
        display: flex; justify-content: center; align-items: center; text-decoration: none;
        background-color: #1f1f1f; border: 1px dashed #00ff41; padding: 10px;
        border-radius: 8px; color: #00ff41; margin-bottom: 20px; transition: 0.3s;
    }
    .brand-link-container:hover { background-color: #00ff41; color: #000; box-shadow: 0 0 15px rgba(0, 255, 65, 0.5); }
    .brand-text { margin-left: 8px; font-weight: bold; font-family: monospace; }
    
    /* Tabs 样式恢复 */
    button[data-baseweb="tab"] { background-color: #1a1a1a; border: 1px solid #333; color: #888; border-radius: 4px; margin-right: 4px; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #00ff41 !important; color: #000 !important; border-color: #00ff41 !important; font-weight: bold; }
    
    /* 异动卡片 */
    .alert-card { padding: 8px; border-radius: 4px; margin-bottom: 6px; border-left: 4px solid; background: #1a1a1a; font-size: 13px; }
    .level-5 { border-color: #3b82f6; } .level-10 { border-color: #eab308; } .level-30 { border-color: #ef4444; }
    
    /* 隐藏加载条 */
    .stStatusWidget { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (即用即毁模式) =================
def fetch_raw_data():
    # 延迟导入，减少启动时的内存压力
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage") 
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions") 
    options.add_argument("--blink-settings=imagesEnabled=false") # 不加载图片，极速
    
    driver = None
    try:
        # 1. 启动
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(20)
        
        # 2. 抓取
        driver.get("https://opinionanalytics.xyz/activity")
        time.sleep(2.5) # 给一点点时间渲染 JS
        
        new_items = []
        rows = driver.find_elements("css selector", "table tbody tr")
        now = datetime.now()
        
        for row in rows:
            try:
                cols = row.find_elements("tag name", "td")
                if len(cols) < 8: continue
                
                side = cols[1].text
                event = cols[4].text
                amt = float(cols[6].text.replace('$', '').replace(',', ''))
                price = float(cols[7].text) if cols[7].text.replace('.', '', 1).isdigit() else 0.0
                
                new_items.append({
                    "unique_key": f"{event}_{cols[3].text}_{side}_{amt}_{cols[9].text}",
                    "Event": event, "Market": cols[3].text, "Side": side, 
                    "Amount": amt, "Price": price, "ScrapeTime": now
                })
            except: continue
            
        return pd.DataFrame(new_items)
        
    except Exception:
        return pd.DataFrame()
    finally:
        # 3. 销毁 (关键步骤)
        if driver:
            try: driver.quit()
            except: pass
        del driver
        gc.collect() # 强制通知系统回收内存

# ================= 🧠 主逻辑 =================

# 1. 标题区
st.markdown(f"""
<a href="{MY_TWITTER_LINK}" target="_blank" class="brand-link-container">
    {twitter_white_svg}
    <span class="brand-text">点击关注 {MY_BRAND_NAME} | 监控运行中...</span>
</a>
""", unsafe_allow_html=True)

# 2. 初始化数据
if 'pool' not in st.session_state: st.session_state.pool = pd.DataFrame()
if 'ranks' not in st.session_state: st.session_state.ranks = {}

# 3. 自动执行抓取 (无按钮，直接跑)
# 使用 spinner 只要一瞬间，不会一直转圈
with st.empty():
    new_df = fetch_raw_data()
    
if not new_df.empty:
    p = pd.concat([st.session_state.pool, new_df]).drop_duplicates(subset=['unique_key'], keep='last')
    p['ScrapeTime'] = pd.to_datetime(p['ScrapeTime'])
    # 保持最近30分钟数据，防止内存无限增长
    st.session_state.pool = p[p['ScrapeTime'] > (datetime.now() - timedelta(minutes=30))]

# 4. 渲染界面 (恢复经典三列/Tabs布局)
t1, t2, t3, t4 = st.tabs(["⚡ 1 分钟", "🌊 10 分钟", "💎 30 分钟", "🚨 异动预警"])

def render(min_val, tab, key):
    with tab:
        p = st.session_state.pool
        if p.empty: 
            st.info("🛰️ 卫星连线中，等待数据流入...")
            return
        
        cutoff = datetime.now() - timedelta(minutes=min_val)
        sub = p[p['ScrapeTime'] > cutoff]
        
        if sub.empty:
            st.caption("⏳ 该时段暂无新交易")
            return
        
        # 聚合计算
        agg = sub.groupby(['Event', 'Market', 'Side']).agg(
            Count=('unique_key', 'count'), Total=('Amount', 'sum'), AvgPrice=('Price', 'mean')
        ).reset_index().sort_values(['Count', 'Total'], ascending=False).reset_index(drop=True)
        agg.index += 1
        
        # 多空比逻辑
        try:
            total_map = sub.groupby(['Event', 'Market'])['Amount'].sum()
