import streamlit as st
import pandas as pd
import time
import os
import gc
from datetime import datetime, timedelta

# ================= ⚙️ 配置区 =================
POLL_INTERVAL = 15       # 刷新间隔 (秒)
MAX_HISTORY_MINUTES = 30 # 最大记忆时长
CACHE_FILE = "opinion_data_pool.csv"

# 【👇 您的信息】
MY_TWITTER_LINK = "https://x.com/songsong7364"
MY_BRAND_NAME = "0xsong"
# ===========================================

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
    
    /* 隐藏部分干扰元素 */
    .stStatusWidget { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (内存防爆优化版) =================
def fetch_raw_data():
    # 延迟导入：只在需要时加载 selenium，节省启动内存
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage") # 关键：防止共享内存崩溃
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu") # 关键：禁用显卡加速
    chrome_options.add_argument("--single-process") # 关键：单进程模式省内存
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") # 关键：不加载图片
    
    driver = None
    new_items = []
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(20) # 防止网页卡死
        
        url = "https://opinionanalytics.xyz/activity"
        driver.get(url)
        time.sleep(2.5) # 给一点点时间让 JS 渲染
        
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        current_scrape_time = datetime.now()
        
        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 8: continue
                
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
    except Exception:
        pass # 忽略单次抓取错误，保证程序不崩
    finally:
        # 🛡️ 终极内存释放逻辑
        if driver:
            try: driver.quit()
            except: pass
        del driver
        gc.collect() # 强制回收内存垃圾
        
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

# 【新增】用于存储上一次排名的字典
if 'rank_history' not in st.session_state:
    st.session_state.rank_history = {}

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
    # 云端尝试保存，失败则忽略
    try: pool.to_csv(CACHE_FILE, index=False)
    except: pass
    return pool

def get_enhanced_ranking(minutes, window_name):
    pool = st.session_state.master_pool
    if pool.empty: return pd.DataFrame()
    
    cutoff = datetime.now() - timedelta(minutes=minutes)
    subset = pool[pool['ScrapeTime'] > cutoff]
    if subset.empty: return pd.DataFrame()
    
    # 1. 计算基础排行
    df = subset.groupby(['Event', 'Market', 'Side']).agg(
        Count=('unique_key', 'count'),
        Total=('Amount', 'sum'),
        AvgPrice=('Price', 'mean')
    ).reset_index()
    
    # 2. 【核心逻辑】计算多空博弈比 (Long Ratio)
    try:
        event_totals = subset.groupby(['Event', 'Market'])['Amount'].sum().to_dict()
        long_subset = subset[subset['Side'].isin(['BUY', 'YES'])]
        long_totals = long_subset.groupby(['Event', 'Market'])['Amount'].sum().to_dict()
        
        def calc_long_ratio(row):
            key = (row['Event'], row['Market'])
            total = event_totals.get(key, 0)
            if total == 0: return 0
            long_amt = long_totals.get(key, 0)
            return long_amt / total # 返回 0.0 - 1.0
            
        df['LongRatio'] = df.apply(calc_long_ratio, axis=1)
    except:
        df['LongRatio'] = 0.5 # 容错

    # 3. 排序
    df = df.sort_values(by=['Count', 'Total'], ascending=[False, False])
    df.reset_index(drop=True, inplace=True)
    df.index += 1 # 排名从1开始
    
    # 4. 【核心逻辑】计算趋势 (Velocity)
    current_ranks = {}
    velocity_icons = []
    
    # 获取上一次的排名记录
    prev_ranks = st.session_state.rank_history.get(window_name, {})
    
    for rank, row in df.iterrows():
        # 生成唯一标识 key
        key = f"{row['Event']}_{row['Market']}_{row['Side']}"
        current_ranks[key] = rank
        
        if key not in prev_ranks:
            velocity_icons.append("🔥") # 新上榜
        else:
            prev = prev_ranks[key]
            diff = prev - rank # 如果上次第5，这次第2，5-2=3 (上升)
            if diff > 0: velocity_icons.append("⬆️")
            elif diff < 0: velocity_icons.append("⬇️")
            else: velocity_icons.append("➖")
            
    df['Trend'] = velocity_icons
    
    # 更新历史记录供下次使用
    st.session_state.rank_history[window_name] = current_ranks
    
    return df

def check_alerts():
    pool = st.session_state.master_pool
    if pool.empty: return [], [], []
    alerts_5, alerts_10, alerts_30 = [], [], []
    grouped = pool.groupby(['Event', 'Market', 'Side'])
    for name, group in grouped:
        if len(group) < 2: continue
        group = group.sort_values('ScrapeTime')
        start_price, end_price = group.iloc[0]['Price'], group.iloc[-1]['Price']
        if start_price == 0: continue
        diff = end_price - start_price
        item = {"Event": name[0], "Market": name[1], "Side": name[2], "Start": start_price, "End": end_price, "Diff": diff}
        if abs(diff) >= 30: alerts_30.append(item)
        elif abs(diff) >= 10: alerts_10.append(item)
        elif abs(diff) >= 5: alerts_5.append(item)
    return alerts_5, alerts_10, alerts_30

# ================= 🖥️ 渲染逻辑 =================

st.title("OPINION热门交易看板")

st.markdown(f"""
    <a href="{MY_TWITTER_LINK}" target="_blank" class="brand-link-container">
        <span class="brand-icon-wrapper">{twitter_x_svg}</span>
        <span class="brand-text">{MY_BRAND_NAME}</span>
    </a>
""", unsafe_allow_html=True)

# 1. 抓取与处理 (移除了 while True，改为单次执行 + rerun)
new_data = fetch_raw_data()
process_data(new_data)

# 2. 界面渲染 (保持不变)
tab1, tab2, tab3, tab4 = st.tabs(["⚡ 1 分钟", "🌊 10 分钟", "💎 30 分钟", "🚨 异动预警"])

def style_dataframe(df):
    def highlight_side(val):
        if 'BUY' in val or 'YES' in val: return 'color: #4ade80; font-weight: bold;' 
        return 'color: #f87171; font-weight: bold;'
    return df.style.applymap(highlight_side, subset=['Side']).format({"Total": "${:,.0f}", "AvgPrice": "{:.1f}%"})

def render_table(minutes, tab, window_name):
    with tab:
        df = get_enhanced_ranking(minutes, window_name)
        if df.empty:
            st.info("数据积累中...")
        else:
            row_h = 35 
            h = (len(df) + 1) * row_h + 3
            if h > 800: h = 800
            
            st.dataframe(
                style_dataframe(df),
                use_container_width=True, 
                height=int(h),    
                column_config={
                    "Trend": st.column_config.TextColumn("趋势", width="small"),
                    "Event": st.column_config.TextColumn("事件", width="large"), 
                    "Market": st.column_config.TextColumn("市场", width="medium"),
                    "Side": st.column_config.TextColumn("方向", width="small"),
                    "Total": st.column_config.NumberColumn("成交额", format="$%d"),
                    "LongRatio": st.column_config.ProgressColumn(
                        "多空情绪", 
                        format="%.2f", 
                        min_value=0, 
                        max_value=1
                    ),
                    "AvgPrice": st.column_config.NumberColumn("均价", format="%.1f"),
                    "Count": st.column_config.ProgressColumn("热度", format="%d", min_value=0, max_value=int(df['Count'].max()*1.2) if not df.empty else 100),
                }
            )

def render_alerts(tab, level, alerts):
    with tab:
        st.markdown(f"##### 波动 > {level}%")
        if not alerts:
            st.markdown(f"<div style='color:#666; font-size:12px; padding:10px'>无异常</div>", unsafe_allow_html=True)
        else:
            for item in alerts:
                color = "#ef4444" if item['Diff'] < 0 else "#22c55e"
                arrow = "📉" if item['Diff'] < 0 else "📈"
                html = f"""
                <div class="alert-card level-{level}">
                    <div style="font-size:12px; color:#888">{item['Market']}</div>
                    <div style="font-weight:bold; margin:2px 0; font-size:13px">{item['Event']}</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px">
                        <span style="background:#333; padding:2px 6px; border-radius:4px; font-size:11px; color:#ccc">{item['Side']}</span>
                        <span style="color:{color}; font-weight:bold; font-size:13px">{arrow} {item['Start']:.1f} ➝ {item['End']:.1f} ({item['Diff']:+.1f}%)</span>
                    </div>
                </div>"""
                st.markdown(html, unsafe_allow_html=True)

# 渲染表格
render_table(1, tab1, "1m")
render_table(10, tab2, "10m")
render_table(30, tab3, "30m")

# 渲染预警
a5, a10, a30 = check_alerts()
with tab4:
    col_a, col_b, col_c = st.columns(3)
    render_alerts(col_a, 5, a5)
    render_alerts(col_b, 10, a10)
    render_alerts(col_c, 30, a30)

# 底部状态栏
pool_size = len(st.session_state.master_pool)
st.markdown(f"""
    <div style='font-family:monospace; color:#666; font-size:12px; padding:10px 0; border-top:1px solid #333; margin-top:20px'>
    系统在线 | 缓存池: {pool_size} | 刷新: {datetime.now().strftime('%H:%M:%S')}
    </div>
""", unsafe_allow_html=True)

# ================= 🔄 核心调度 (替代 while True) =================
# 等待一段时间后，自动刷新页面，重新执行脚本
time.sleep(POLL_INTERVAL)
st.rerun()
