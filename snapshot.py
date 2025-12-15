import streamlit as st
import pandas as pd
import time
import gc 
import os
from datetime import datetime, timedelta

# ================= 🛡️ 极简配置 =================
st.set_page_config(layout="wide", page_title="0xsong 终端")

MY_TWITTER_LINK = "https://twitter.com/songpeng_web3"
MY_BRAND_NAME = "0xsong"

# 白色图标
twitter_white_svg = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231h0.001zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="#ffffff"/></svg>"""

# 强制注入皮肤
st.markdown("""
<style>
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    [data-testid="stDataFrame"] { background-color: #161616 !important; border: 1px solid #333 !important; }
    
    .brand-link-container {
        display: flex; justify-content: center; align-items: center; text-decoration: none;
        background-color: #1f1f1f; border: 1px dashed #00ff41; padding: 12px;
        border-radius: 8px; color: #00ff41; margin-bottom: 25px; transition: 0.3s;
    }
    .brand-link-container:hover { background-color: #00ff41; color: #000; box-shadow: 0 0 15px rgba(0, 255, 65, 0.5); }
    .brand-text { margin-left: 8px; font-weight: bold; }
    
    button[data-baseweb="tab"] { background-color: #1a1a1a; border: 1px solid #333; color: #888; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #00ff41 !important; color: #000 !important; }
    
    .alert-card { padding: 10px; border-radius: 5px; margin-bottom: 8px; border-left: 4px solid; background: #1a1a1a; }
    .level-5 { border-color: #3b82f6; } .level-10 { border-color: #eab308; } .level-30 { border-color: #ef4444; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (极限内存版) =================
def fetch_raw_data(status_box):
    # 延迟导入，节省启动内存
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage") 
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions") # 禁用扩展
    options.add_argument("--disable-software-rasterizer") # 禁用软件渲染
    options.add_argument("--blink-settings=imagesEnabled=false") # 不加载图片
    
    driver = None
    try:
        status_box.update(label="🚀 启动极简浏览器...", state="running")
        driver = webdriver.Chrome(options=options)
        
        status_box.update(label="📡 连接数据源...", state="running")
        driver.set_page_load_timeout(20)
        driver.get("https://opinionanalytics.xyz/activity")
        time.sleep(3) 
        
        new_items = []
        rows = driver.find_elements("css selector", "table tbody tr")
        now = datetime.now()
        
        status_box.update(label="🔍 解析数据...", state="running")
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
            
        status_box.update(label=f"✅ 获取到 {len(new_items)} 条数据", state="complete")
        return pd.DataFrame(new_items)
        
    except Exception as e:
        status_box.update(label=f"⚠️ 抓取中断: {str(e)[:50]}...", state="error")
        return pd.DataFrame()
    finally:
        if driver:
            try: driver.quit()
            except: pass
        # 强制内存回收
        del driver
        gc.collect() 

# ================= 🧠 主逻辑 =================
st.title("Opinion热门交易看板")

st.markdown(f"""
<a href="{MY_TWITTER_LINK}" target="_blank" class="brand-link-container">
    {twitter_white_svg}
    <span class="brand-text">点击关注 {MY_BRAND_NAME} 获取更多 Alpha 信号</span>
</a>
""", unsafe_allow_html=True)

if 'pool' not in st.session_state: st.session_state.pool = pd.DataFrame()
if 'ranks' not in st.session_state: st.session_state.ranks = {}
if 'is_running' not in st.session_state: st.session_state.is_running = False

# 控制区
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚀 启动/暂停", type="primary"):
        st.session_state.is_running = not st.session_state.is_running
        st.rerun()

with col2:
    if st.session_state.is_running:
        st.caption("🟢 运行中... (15秒刷新)")
    else:
        st.caption("🔴 已暂停 (点击左侧按钮启动)")

status_box = st.status("准备就绪", expanded=False)

# 核心循环
if st.session_state.is_running:
    new_df = fetch_raw_data(status_box)
    
    if not new_df.empty:
        p = pd.concat([st.session_state.pool, new_df]).drop_duplicates(subset=['unique_key'], keep='last')
        p['ScrapeTime'] = pd.to_datetime(p['ScrapeTime'])
        st.session_state.pool = p[p['ScrapeTime'] > (datetime.now() - timedelta(minutes=30))]
        time.sleep(1) # 给用户看一眼状态
        status_box.update(label="等待下一次刷新...", state="running", expanded=False)

# 渲染 Tabs
t1, t2, t3, t4 = st.tabs(["⚡ 1 分钟", "🌊 10 分钟", "💎 30 分钟", "🚨 预警"])

def render(min_val, tab, key):
    with tab:
        p = st.session_state.pool
        if p.empty: 
            st.info("暂无数据，请点击启动...")
            return
        
        cutoff = datetime.now() - timedelta(minutes=min_val)
        sub = p[p['ScrapeTime'] > cutoff]
        if sub.empty: 
            st.caption("该时段暂无交易")
            return
        
        agg = sub.groupby(['Event', 'Market', 'Side']).agg(
            Count=('unique_key', 'count'), Total=('Amount', 'sum'), AvgPrice=('Price', 'mean')
        ).reset_index().sort_values(['Count', 'Total'], ascending=False).reset_index(drop=True)
        agg.index += 1
        
        try:
            total_map = sub.groupby(['Event', 'Market'])['Amount'].sum()
            long_map = sub[sub['Side'].isin(['BUY', 'YES'])].groupby(['Event', 'Market'])['Amount'].sum()
            agg['LongRatio'] = agg.apply(lambda r: (long_map.get((r['Event'], r['Market']), 0) / total_map.get((r['Event'], r['Market']), 1)), axis=1)
        except: agg['LongRatio'] = 0.5
        
        trends = []
        curr_ranks = {}
        hist = st.session_state.ranks.get(key, {})
        for r, row in agg.iterrows():
            k = f"{row['Event']}_{row['Market']}"
            curr_ranks[k] = r
            trends.append("🔥" if k not in hist else ("⬆️" if hist[k] > r else ("⬇️" if hist[k] < r else "➖")))
        agg['Trend'] = trends
        st.session_state.ranks[key] = curr_ranks

        st.dataframe(agg.style.format({"Total": "${:,.0f}", "AvgPrice": "{:.1f}%"}), use_container_width=True, height=500,
                     column_config={"LongRatio": st.column_config.ProgressColumn("多空", min_value=0, max_value=1),
                                    "Trend": st.column_config.TextColumn("趋势", width="small"),
                                    "Count": st.column_config.ProgressColumn("热度", max_value=int(agg['Count'].max()*1.2))})

render(1, t1, "1m"); render(10, t2, "10m"); render(30, t3, "30m")

with t4:
    if not st.session_state.pool.empty:
        for n, g in st.session_state.pool.groupby(['Event', 'Market', 'Side']):
            if len(g) < 2: continue
            g = g.sort_values('ScrapeTime')
            diff = g.iloc[-1]['Price'] - g.iloc[0]['Price']
            if abs(diff) >= 5:
                lvl = 30 if abs(diff)>=30 else (10 if abs(diff)>=10 else 5)
                st.markdown(f"<div class='alert-card level-{lvl}'><b>{n[0]}</b> ({n[2]}): {diff:+.1f}%</div>", unsafe_allow_html=True)

# 自动刷新
if st.session_state.is_running:
    time.sleep(15) 
    st.rerun()
