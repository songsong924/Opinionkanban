import streamlit as st
import pandas as pd
import time
import gc 
from datetime import datetime, timedelta

# ================= 🛡️ 极简配置 =================
st.set_page_config(layout="wide", page_title="0xsong Opinion")

MY_TWITTER_LINK = "https://x.com/songsong7364"
MY_BRAND_NAME = "0xsong"
REFRESH_RATE = 20 # 刷新间隔(秒)

# 白色图标 (修复版)
twitter_white_svg = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231h0.001zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="#ffffff"/></svg>"""

# 强制注入皮肤
st.markdown("""
<style>
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
    
    /* Tabs 样式 */
    button[data-baseweb="tab"] { background-color: #1a1a1a; border: 1px solid #333; color: #888; border-radius: 4px; margin-right: 4px; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #00ff41 !important; color: #000 !important; border-color: #00ff41 !important; font-weight: bold; }
    
    /* 异动卡片 */
    .alert-card { padding: 8px; border-radius: 4px; margin-bottom: 6px; border-left: 4px solid; background: #1a1a1a; font-size: 13px; }
    .level-5 { border-color: #3b82f6; } .level-10 { border-color: #eab308; } .level-30 { border-color: #ef4444; }
    
    /* 隐藏加载条 */
    .stStatusWidget { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ================= 🕷️ 爬虫引擎 (修复版) =================
def fetch_raw_data():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage") 
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions") 
    options.add_argument("--blink-settings=imagesEnabled=false")
    
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(20)
        
        driver.get("https://opinionanalytics.xyz/activity")
        time.sleep(2.5) 
        
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
        if driver:
            try: driver.quit()
            except: pass
        del driver
        gc.collect()

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

# 3. 自动执行抓取
with st.empty():
    new_df = fetch_raw_data()
    
if not new_df.empty:
    p = pd.concat([st.session_state.pool, new_df]).drop_duplicates(subset=['unique_key'], keep='last')
    p['ScrapeTime'] = pd.to_datetime(p['ScrapeTime'])
    st.session_state.pool = p[p['ScrapeTime'] > (datetime.now() - timedelta(minutes=30))]

# 4. 渲染界面
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
        
        # 多空比逻辑 (修复了这里的 SyntaxError)
        try:
            total_map = sub.groupby(['Event', 'Market'])['Amount'].sum()
            long_map = sub[sub['Side'].isin(['BUY', 'YES'])].groupby(['Event', 'Market'])['Amount'].sum()
            agg['LongRatio'] = agg.apply(lambda r: (long_map.get((r['Event'], r['Market']), 0) / total_map.get((r['Event'], r['Market']), 1)), axis=1)
        except Exception: 
            agg['LongRatio'] = 0.5
        
        # 趋势逻辑
        trends = []
        curr_ranks = {}
        hist = st.session_state.ranks.get(key, {})
        for r, row in agg.iterrows():
            k = f"{row['Event']}_{row['Market']}"
            curr_ranks[k] = r
            trends.append("🔥" if k not in hist else ("⬆️" if hist[k] > r else ("⬇️" if hist[k] < r else "➖")))
        agg['Trend'] = trends
        st.session_state.ranks[key] = curr_ranks

        # 渲染表格
        st.dataframe(
            agg.style.format({"Total": "${:,.0f}", "AvgPrice": "{:.1f}%"}), 
            use_container_width=True, 
            height=600,
            column_config={
                "LongRatio": st.column_config.ProgressColumn("多空 (绿多)", min_value=0, max_value=1),
                "Trend": st.column_config.TextColumn("趋势", width="small"),
                "Count": st.column_config.ProgressColumn("热度", max_value=int(agg['Count'].max()*1.2) if not agg.empty else 100),
                "Event": st.column_config.TextColumn("事件", width="large")
            }
        )

render(1, t1, "1m")
render(10, t2, "10m")
render(30, t3, "30m")

with t4:
    if not st.session_state.pool.empty:
        alerts_found = False
        for n, g in st.session_state.pool.groupby(['Event', 'Market', 'Side']):
            if len(g) < 2: continue
            g = g.sort_values('ScrapeTime')
            diff = g.iloc[-1]['Price'] - g.iloc[0]['Price']
            if abs(diff) >= 5:
                alerts_found = True
                lvl = 30 if abs(diff)>=30 else (10 if abs(diff)>=10 else 5)
                color = "#ef4444" if diff < 0 else "#22c55e"
                arrow = "📉" if diff < 0 else "📈"
                st.markdown(
                    f"<div class='alert-card level-{lvl}'>"
                    f"<span style='color:#888'>{n[1]}</span><br>"
                    f"<b>{n[0]}</b> ({n[2]})<br>"
                    f"<span style='color:{color}; font-weight:bold'>{arrow} {diff:+.1f}%</span> "
                    f"<span style='font-size:12px; opacity:0.7'>({g.iloc[0]['Price']:.0f}% -> {g.iloc[-1]['Price']:.0f}%)</span>"
                    f"</div>", 
                    unsafe_allow_html=True
                )
        if not alerts_found:
            st.caption("暂无剧烈波动")

# 5. 自动循环
progress_text = "系统冷却中..."
my_bar = st.progress(0, text=progress_text)

for percent_complete in range(100):
    time.sleep(REFRESH_RATE / 100)
    my_bar.progress(percent_complete + 1, text=f"系统冷却中... {int((1 - (percent_complete+1)/100) * REFRESH_RATE)}s")

st.rerun()
