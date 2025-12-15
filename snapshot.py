import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime, timedelta

# ================= 🛡️ 稳健启动配置 =================
st.set_page_config(layout="wide", page_title="0xsong Alpha 终端")

# 【👇 您的品牌配置】
MY_TWITTER_LINK = "https://twitter.com/songpeng_web3"
MY_BRAND_NAME = "0xsong"

# ================= 🎨 内置黑客风皮肤 (无需Config文件) =================
st.markdown("""
<style>
    /* 1. 强制全局黑底 (覆盖默认白底) */
    .stApp { background-color: #0e0e0e; color: #e0e0e0; }
    
    /* 2. 表格黑化 */
    [data-testid="stDataFrame"] { background-color: #161616 !important; border: 1px solid #333 !important; }
    [data-testid="stDataFrame"] thead tr th { background-color: #1f1f1f !important; color: #888 !important; }
    
    /* 3. 品牌横幅 */
    .brand-link-container {
        display: block; text-align: center; text-decoration: none;
        background-color: #1f1f1f; border: 1px dashed #00ff41; padding: 12px;
        border-radius: 8px; color: #00ff41; margin-bottom: 25px; transition: 0.3s;
    }
    .brand-link-container:hover {
        background-color: #00ff41; color: #000; box-shadow: 0 0 15px rgba(0, 255, 65, 0.5);
    }

    /* 4. Tabs样式 */
    button[data-baseweb="tab"] { background-color: #1a1a1a; border: 1px solid #333; color: #888; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #00ff41 !important; color: #000 !important; border: 1px solid #00ff41 !important; font-weight: bold; }
    
    /* 5. 异动卡片 */
    .alert-card { padding: 10px; border-radius: 5px; margin-bottom: 8px; border-left: 4px solid; background: #1a1a1a; }
    .level-5 { border-color: #3b82f6; }
    .level-10 { border-color: #eab308; }
    .level-30 { border-color: #ef4444; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (标准兼容版) =================
@st.cache_resource
def get_driver():
    """获取浏览器实例"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # Streamlit Cloud 常用参数
    chrome_options.add_argument("--window-size=1920,1080")
    
    return webdriver.Chrome(options=chrome_options)

def fetch_raw_data():
    try:
        driver = get_driver()
        url = "https://opinionanalytics.xyz/activity"
        
        driver.get(url)
        time.sleep(3) # 等待加载
        
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
    except Exception:
        return pd.DataFrame()

# ================= 💾 数据核心 =================
if 'master_pool' not in st.session_state:
    st.session_state.master_pool = pd.DataFrame()
if 'rank_history' not in st.session_state:
    st.session_state.rank_history = {}

def process_data(new_df):
    if new_df.empty: return
    pool = st.session_state.master_pool
    pool = pd.concat([pool, new_df]).drop_duplicates(subset=['unique_key'], keep='last')
    
    # 清理过期
    pool['ScrapeTime'] = pd.to_datetime(pool['ScrapeTime'])
    cutoff = datetime.now() - timedelta(minutes=30)
    st.session_state.master_pool = pool[pool['ScrapeTime'] > cutoff]

def get_enhanced_view(minutes, window_key):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()
    
    cutoff = datetime.now() - timedelta(minutes=minutes)
    df = pool[pool['ScrapeTime'] > cutoff]
    if df.empty: return pd.DataFrame()
    
    # 基础聚合
    res = df.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum'),
        AvgPrice=('Price', 'mean')
    ).reset_index()
    
    # 计算多空比
    try:
        total_map = df.groupby(['Event', 'Market'])['Amount'].sum()
        long_map = df[df['Side'].isin(['BUY', 'YES'])].groupby(['Event', 'Market'])['Amount'].sum()
        
        def get_ratio(row):
            t = total_map.get((row['Event'], row['Market']), 0)
            return (long_map.get((row['Event'], row['Market']), 0) / t) if t > 0 else 0
            
        res['LongRatio'] = res.apply(get_ratio, axis=1)
    except:
        res['LongRatio'] = 0.5

    # 排序
    res = res.sort_values(['Count', 'Total'], ascending=[False, False]).reset_index(drop=True)
    res.index += 1
    
    # 趋势计算
    velocity = []
    current_ranks = {}
    history = st.session_state.rank_history.get(window_key, {})
    
    for rank, row in res.iterrows():
        key = f"{row['Event']}_{row['Market']}"
        current_ranks[key] = rank
        if key not in history:
            velocity.append("🔥")
        else:
            diff = history[key] - rank
            velocity.append("⬆️" if diff > 0 else ("⬇️" if diff < 0 else "➖"))
            
    res['Trend'] = velocity
    st.session_state.rank_history[window_key] = current_ranks
    
    return res

def check_alerts():
    pool = st.session_state.master_pool
    if pool.empty: return [], [], []
    a5, a10, a30 = [], [], []
    
    for name, group in pool.groupby(['Event', 'Market', 'Side']):
        if len(group) < 2: continue
        group = group.sort_values('ScrapeTime')
        diff = group.iloc[-1]['Price'] - group.iloc[0]['Price']
        item = {"Event": name[0], "Market": name[1], "Side": name[2], "Diff": diff, "Start": group.iloc[0]['Price'], "End": group.iloc[-1]['Price']}
        
        if abs(diff) >= 30: a30.append(item)
        elif abs(diff) >= 10: a10.append(item)
        elif abs(diff) >= 5: a5.append(item)
    return a5, a10, a30

# ================= 🖥️ 渲染 =================
st.title("🦅 Opinion Alpha 终端")

# 品牌横幅
st.markdown(f"""
<a href="{MY_TWITTER_LINK}" target="_blank" class="brand-link-container">
    📡 点击关注 <b>{MY_BRAND_NAME}</b> 获取更多 Alpha 信号
</a>
""", unsafe_allow_html=True)

# 自动刷新
new_data = fetch_raw_data()
process_data(new_data)

# Tabs
t1, t2, t3, t4 = st.tabs(["⚡ 1 分钟", "🌊 10 分钟", "💎 30 分钟", "🚨 异动预警"])

def render_tab(min_val, tab, key):
    with tab:
        df = get_enhanced_view(min_val, key)
        if df.empty:
            st.info("正在接收信号...")
        else:
            st.dataframe(
                df.style.format({"Total": "${:,.0f}", "AvgPrice": "{:.1f}%"}),
                use_container_width=True,
                height=500,
                column_config={
                    "Trend": st.column_config.TextColumn("趋势", width="small"),
                    "LongRatio": st.column_config.ProgressColumn("多空情绪 (绿多/灰空)", min_value=0, max_value=1),
                    "Event": st.column_config.TextColumn("事件", width="large"),
                    "Count": st.column_config.ProgressColumn("热度", max_value=int(df['Count'].max()*1.2))
                }
            )

render_tab(1, t1, "1m")
render_tab(10, t2, "10m")
render_tab(30, t3, "30m")

# 异动
a5, a10, a30 = check_alerts()
with t4:
    if not (a5 or a10 or a30): st.caption("暂无剧烈波动")
    for item in a30: st.markdown(f"<div class='alert-card level-30'>🚨 <b>{item['Event']}</b> <br> {item['Diff']:+.1f}% ({item['Start']}➜{item['End']})</div>", unsafe_allow_html=True)
    for item in a10: st.markdown(f"<div class='alert-card level-10'>⚡ <b>{item['Event']}</b> <br> {item['Diff']:+.1f}% ({item['Start']}➜{item['End']})</div>", unsafe_allow_html=True)
    for item in a5: st.markdown(f"<div class='alert-card level-5'>🌊 <b>{item['Event']}</b> <br> {item['Diff']:+.1f}% ({item['Start']}➜{item['End']})</div>", unsafe_allow_html=True)

# 底部状态
st.caption(f"System Online | Pool: {len(st.session_state.master_pool)} | Updated: {datetime.now().strftime('%H:%M:%S')}")
time.sleep(10)
st.rerun()
