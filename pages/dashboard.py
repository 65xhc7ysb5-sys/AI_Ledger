import streamlit as st
import pandas as pd
from database import load_data, delete_expense

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")
st.title("📊 소비 분석 대시보드")

# [데이터 로드 방식 변경]
df = load_data()

if df.empty:
    st.info("아직 저장된 데이터가 없습니다.")
    st.stop()

# [중요] 날짜 변환 (문자열 -> 날짜객체)
try:
    df['date'] = pd.to_datetime(df['date'])
except:
    df['date'] = pd.to_datetime('today')

# 1. 상단 요약 (Metrics)
total_spend = df['amount'].sum()
col1, col2, col3 = st.columns(3)
col1.metric("총 지출액", f"{total_spend:,}원")
col2.metric("총 건수", f"{len(df)}건")
if not df.empty:
    top_cat = df.groupby('category')['amount'].sum().idxmax()
    col3.metric("최다 지출", top_cat)

st.divider()

# 2. 그래프 섹션
tab1, tab2 = st.tabs(["📈 날짜별 추이", "🍕 카테고리별 비중"])

with tab1:
    st.subheader("일별 지출 흐름")
    # 날짜별로 그룹화하여 합계 계산
    daily_spend = df.groupby('date')['amount'].sum().reset_index()
    # 꺾은선 그래프 (Line Chart)
    st.line_chart(daily_spend, x='date', y='amount', color='#FF4B4B')

with tab2:
    st.subheader("카테고리별 지출")
    category_spend = df.groupby('category')['amount'].sum()
    st.bar_chart(category_spend)

st.divider()

# 3. 상세 내역 관리 (삭제/수정)
st.subheader("📋 상세 내역")

# [삭제 기능 추가 팁]
# SQLite는 각 행마다 고유 ID가 있어서 삭제가 쉽습니다.
for index, row in df.iterrows():
    col1, col2 = st.columns([4, 1])
    col1.write(f"{row['date'].date()} | {row['item']} | {row['amount']:,}원")
    if col2.button("삭제", key=row['id']):
        delete_expense(row['id'])
        st.rerun()