import streamlit as st
import pandas as pd
import sys
import os

# 상위 폴더의 모듈을 불러오기 위한 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import load_data, delete_expense

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

st.title("📊 소비 분석 대시보드")

# --- 1. 데이터 로드 및 백업 기능 ---
df = load_data()

if df.empty:
    st.info("아직 저장된 데이터가 없습니다. 'Home' 페이지에서 내역을 입력해주세요.")
    st.stop()

# 날짜 형식 변환
df['date'] = pd.to_datetime(df['date'])

# [추가] CSV 다운로드 버튼 (사이드바 배치)
with st.sidebar:
    st.header("📂 데이터 관리")
    csv = df.to_csv(index=False).encode('utf-8-sig') # 엑셀 한글 깨짐 방지
    
    st.download_button(
        label="📥 전체 내역 다운로드 (CSV)",
        data=csv,
        file_name="ai_ledger_backup.csv",
        mime="text/csv",
        help="데이터를 엑셀 파일로 다운로드합니다."
    )
    st.write(f"총 {len(df)}건의 데이터가 있습니다.")

# --- 2. 상단 요약 (Metrics) ---
total_spend = df['amount'].sum()
col1, col2, col3 = st.columns(3)
col1.metric("총 지출액", f"{total_spend:,}원")
col2.metric("총 건수", f"{len(df)}건")
if not df.empty:
    top_cat = df.groupby('category')['amount'].sum().idxmax()
    col3.metric("최다 지출 카테고리", top_cat)

st.divider()

# --- 3. 그래프 섹션 ---
tab1, tab2 = st.tabs(["📈 날짜별 추이", "🍕 카테고리별 비중"])

with tab1:
    st.subheader("일별 지출 흐름")
    daily_spend = df.groupby('date')['amount'].sum().reset_index()
    st.line_chart(daily_spend, x='date', y='amount', color='#FF4B4B')

with tab2:
    st.subheader("카테고리별 지출")
    category_spend = df.groupby('category')['amount'].sum()
    st.bar_chart(category_spend)

st.divider()

# --- 4. 상세 내역 관리 (삭제 기능) ---
st.subheader("📋 상세 내역 리스트")

# 보기 좋게 출력 (최신순)
for index, row in df.iterrows():
    # 카드를 이용한 레이아웃
    with st.container(border=True):
        col_date, col_item, col_amt, col_cat, col_btn = st.columns([2, 4, 2, 2, 1])
        
        col_date.write(row['date'].strftime('%Y-%m-%d'))
        col_item.write(f"**{row['item']}**")
        col_amt.write(f"{row['amount']:,}원")
        col_cat.caption(row['category'])
        
        # 삭제 버튼 (고유키: id 사용)
        if col_btn.button("삭제", key=f"del_{row['id']}"):
            delete_expense(row['id'])
            st.rerun() # 화면 즉시 새로고침