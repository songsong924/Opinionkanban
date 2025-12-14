import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime

# ================= 参数设置 =================
REPORT_CYCLE = 180    # 汇总周期：3分钟
POLL_INTERVAL = 15    # 扫描频率：15秒
TEMP_RANKING_FILE = "temp_ranking_cache.csv"
TEMP_BUFFER_FILE = "temp_buffer_cache.csv"

st.set_page_config(layout="wide", page_title="Opinion 热点监控")

# --- 1. 云端专用爬虫函数 (内存优化版) ---
def fetch_raw_data():
    chrome_options = Options()
    # 核心：必须使用无头模式
    chrome_options.add_argument("--headless")
    # 核心：解决云端 Docker 内存崩溃问题
    chrome_options.add_argument("--disable-dev-shm-usage") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # 简单的反爬处理
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    url = "https://opinionanalytics.xyz/activity"
    raw_data = []
    
    try:
        driver.set_page_load_timeout(20) # 防止网页卡死
        driver.get(url)
        time.sleep(3) # 等待加载
        
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue
            try:
                side = cols[1].text
                market = cols[3].text
                event = cols[4].text
                amount = float(cols[6].text.replace('$', '').replace(',', ''))
                # 唯一ID
                unique_key = f"{event}_{market}_{side}_{amount}_{cols[9].text}"
                
                raw_data.append({
                    "unique_key": unique_key,
                    "Event": event,
                    "Market": market,
                    "Side": side,
                    "Amount": amount
                })
            except:
                continue
    except Exception as e:
        print(f"Scrape Error: {e}")
    finally:
        # 必须确保退出，释放内存
        driver.quit()
        
    return pd.DataFrame(raw_data)

# --- 2. 状态恢复 (防刷新) ---
if 'buffer' not in st.session_state:
    if os.path.exists(TEMP_BUFFER_FILE):
        try: st.session_state.buffer = pd.read_csv(TEMP_BUFFER_FILE)
        except: st.session_state.buffer = pd.DataFrame()
    else: st.session_state.buffer = pd.DataFrame()

if 'report_df' not in st.session_state:
    if os.path.exists(TEMP_RANKING_FILE):
        try: st.session_state.report_df = pd.read_csv(TEMP_RANKING_FILE)
        except: st.session_state.report_df = pd.DataFrame()
    else: st.session_state.report_df = pd.DataFrame()

if 'start_time' not in st.session_state:
    st.session_state.start_time = time.time()

if 'last_update_str' not in st.session_state:
    st.session_state.last_update_str = "等待首轮结算..."

def color_side(val):
    if 'BUY' in val or 'YES' in val: return 'color: #28a745; font-weight: bold'
    if 'SELL' in val or 'NO' in val: return 'color: #dc3545; font-weight: bold'
    return ''

# ================= 3. 界面布局 =================

st.title("🦅 Opinion 市场热点监控")

# 状态栏 (使用原生 Status 组件，防止堆叠)
status_box = st.status("正在初始化系统...", expanded=True)

st.markdown("### 📊 3分钟热度排行")
# 固定表格容器
table_placeholder = st.empty()

# ================= 4. 主循环逻辑 =================
while True:
    elapsed = time.time() - st.session_state.start_time
    remaining_seconds = REPORT_CYCLE - elapsed

    # === A. 3分钟结算逻辑 ===
    if remaining_seconds <= 0:
        status_box.update(label="⏳ 3分钟周期到达，正在生成报表...", state="running")
        
        df_final = st.session_state.buffer
        if not df_final.empty:
            ranking = df_final.groupby(['Event', 'Market', 'Side']).agg(
                出现次数=('unique_key', 'count'),
                总交易额=('Amount', 'sum')
            ).reset_index()
            ranking = ranking.sort_values(by=['出现次数', '总交易额'], ascending=[False, False])
            ranking.index = range(1, len(ranking) + 1)
            
            st.session_state.report_df = ranking
            st.session_state.last_update_str = datetime.now().strftime('%H:%M:%S')
            ranking.to_csv(TEMP_RANKING_FILE, index=False)
        else:
            st.session_state.report_df = pd.DataFrame()
            st.session_state.last_update_str = f"{datetime.now().strftime('%H:%M:%S')} (无交易)"
            # 存个空文件防止报错
            pd.DataFrame(columns=['Event', 'Market', 'Side', '出现次数', '总交易额']).to_csv(TEMP_RANKING_FILE, index=False)
        
        # 重置
        st.session_state.buffer = pd.DataFrame()
        if os.path.exists(TEMP_BUFFER_FILE): os.remove(TEMP_BUFFER_FILE)
        st.session_state.start_time = time.time()
        
        status_box.update(label=f"✅ 报表已更新 ({st.session_state.last_update_str})", state="complete")
        time.sleep(2) # 展示一下成功状态

    # === B. 渲染表格 (始终显示在上方) ===
    if not st.session_state.report_df.empty:
        styled_df = st.session_state.report_df.style.applymap(color_side, subset=['Side']).format({"总交易额": "${:,.2f}"})
        table_placeholder.dataframe(
            styled_df, 
            use_container_width=True, 
            height=600,
            column_config={
                "出现次数": st.column_config.ProgressColumn(
                    format="%d 次",
                    min_value=0,
                    max_value=int(st.session_state.report_df['出现次数'].max() * 1.25)
                )
            }
        )
    else:
        table_placeholder.info(f"👋 正在收集数据... 上次更新: {st.session_state.last_update_str}")

    # === C. 抓取数据 ===
    status_box.update(label=f"🔄 正在扫描数据... (当前缓存: {len(st.session_state.buffer)})", state="running")
    
    new_batch = fetch_raw_data()
    
    if not new_batch.empty:
        if st.session_state.buffer.empty:
            st.session_state.buffer = new_batch
        else:
            st.session_state.buffer = pd.concat([st.session_state.buffer, new_batch])
            st.session_state.buffer.drop_duplicates(subset=['unique_key'], inplace=True)
        st.session_state.buffer.to_csv(TEMP_BUFFER_FILE, index=False)
            
    # === D. 智能等待 (防止崩断前端) ===
    # 关键修改：不再使用每秒刷新的倒计时，改用 st.spinner
    # 这避免了 DOM 节点的频繁操作，解决了 NotFoundError
    status_box.update(label=f"💤 休眠中... (缓存: {len(st.session_state.buffer)} | 下次扫描: {POLL_INTERVAL}秒后)", state="running")
    
    # 这里的 sleep 不会报错，因为不涉及 UI 刷新
    time.sleep(POLL_INTERVAL)
