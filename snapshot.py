import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime

# ================= 参数设置 =================
REPORT_CYCLE = 180  # 汇总周期：3分钟
POLL_INTERVAL = 15  # 扫描频率：15秒
# 临时缓存文件 (用于防刷新丢失数据)
TEMP_RANKING_FILE = "temp_ranking_cache.csv"
TEMP_BUFFER_FILE = "temp_buffer_cache.csv"
# ===========================================

st.set_page_config(layout="wide", page_title="Opinion 热点监控")


# --- 1. 爬虫函数 ---
def fetch_raw_data():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    url = "https://opinionanalytics.xyz/activity"
    raw_data = []

    try:
        driver.get(url)
        time.sleep(3)

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue
            try:
                side = cols[1].text
                market = cols[3].text
                event = cols[4].text
                amount = float(cols[6].text.replace('$', '').replace(',', ''))
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
        pass
    finally:
        driver.quit()

    return pd.DataFrame(raw_data)


# --- 2. 状态管理 (核心修改：增加从文件恢复的逻辑) ---

# A. 恢复缓冲池 (Buffer)
if 'buffer' not in st.session_state:
    if os.path.exists(TEMP_BUFFER_FILE):
        try:
            st.session_state.buffer = pd.read_csv(TEMP_BUFFER_FILE)
        except:
            st.session_state.buffer = pd.DataFrame()
    else:
        st.session_state.buffer = pd.DataFrame()

# B. 恢复排行榜 (Report DF)
if 'report_df' not in st.session_state:
    if os.path.exists(TEMP_RANKING_FILE):
        try:
            st.session_state.report_df = pd.read_csv(TEMP_RANKING_FILE)
        except:
            st.session_state.report_df = pd.DataFrame()
    else:
        st.session_state.report_df = pd.DataFrame()

# C. 恢复计时器 (简单的处理：刷新后虽然计时会重置，但数据还在)
if 'start_time' not in st.session_state:
    st.session_state.start_time = time.time()

if 'last_update_str' not in st.session_state:
    # 尝试从文件修改时间获取上次更新时间，如果不行则显示等待
    if os.path.exists(TEMP_RANKING_FILE):
        mtime = os.path.getmtime(TEMP_RANKING_FILE)
        st.session_state.last_update_str = datetime.fromtimestamp(mtime).strftime('%H:%M:%S')
    else:
        st.session_state.last_update_str = "等待首轮结算..."


# --- 3. 样式函数 ---
def color_side(val):
    if 'BUY' in val or 'YES' in val: return 'color: #28a745; font-weight: bold'
    if 'SELL' in val or 'NO' in val: return 'color: #dc3545; font-weight: bold'
    return ''


# ================= 4. 界面布局 =================

st.title("🦅 Opinion 市场热点监控")

top_col1, top_col2, top_col3 = st.columns([6, 2, 2])
with top_col3:
    countdown_placeholder = st.empty()

st.markdown("### 📊 3分钟热度排行")
table_placeholder = st.empty()
st.divider()
log_placeholder = st.empty()

# ================= 5. 主循环逻辑 =================
while True:
    elapsed = time.time() - st.session_state.start_time
    remaining_seconds = REPORT_CYCLE - elapsed

    # === A. 3分钟结算逻辑 ===
    if remaining_seconds <= 0:
        with table_placeholder.container():
            with st.spinner("⏳ 周期结束，正在计算排名..."):
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

                    # 【新增】保存排行榜快照
                    ranking.to_csv(TEMP_RANKING_FILE, index=False)
                else:
                    st.session_state.report_df = pd.DataFrame()
                    st.session_state.last_update_str = f"{datetime.now().strftime('%H:%M:%S')} (无交易)"
                    # 如果为空，也保存一个空文件或清除，这里选择保存空文件以覆盖旧数据
                    pd.DataFrame(columns=['Event', 'Market', 'Side', '出现次数', '总交易额']).to_csv(TEMP_RANKING_FILE,
                                                                                                     index=False)

                # 重置缓冲池并保存空状态
                st.session_state.buffer = pd.DataFrame()
                if os.path.exists(TEMP_BUFFER_FILE):
                    os.remove(TEMP_BUFFER_FILE)  # 3分钟清空一次缓存文件

                st.session_state.start_time = time.time()
                remaining_seconds = REPORT_CYCLE

    # === B. 渲染表格 ===
    if not st.session_state.report_df.empty:
        styled_df = st.session_state.report_df.style.applymap(color_side, subset=['Side']).format({
            "总交易额": "${:,.2f}"
        })
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
        table_placeholder.info(f"👋 正在进行本轮数据收集... 上次更新: {st.session_state.last_update_str}")

    # === C. 抓取数据 ===
    log_placeholder.markdown(f"**🟢 系统状态:** 正在扫描数据流... | 当前缓存记录数: `{len(st.session_state.buffer)}`")

    new_batch = fetch_raw_data()
    if not new_batch.empty:
        if st.session_state.buffer.empty:
            st.session_state.buffer = new_batch
        else:
            st.session_state.buffer = pd.concat([st.session_state.buffer, new_batch])
            st.session_state.buffer.drop_duplicates(subset=['unique_key'], inplace=True)

        # 【新增】每次抓取后，立即保存缓冲池到本地
        st.session_state.buffer.to_csv(TEMP_BUFFER_FILE, index=False)

    log_placeholder.markdown(
        f"**✅ 系统状态:** 休眠中 (等待下轮扫描) | 当前缓存记录数: `{len(st.session_state.buffer)}` | 上次更新: `{st.session_state.last_update_str}`")

    # === D. 倒计时 ===
    for i in range(POLL_INTERVAL):
        curr_remaining = int(REPORT_CYCLE - (time.time() - st.session_state.start_time))
        if curr_remaining <= 0: break

        mins, secs = divmod(curr_remaining, 60)
        countdown_placeholder.metric(
            label="距离下次刷新",
            value=f"{mins:02d}:{secs:02d}",
            delta="常驻保护已开启"
        )
        time.sleep(1)