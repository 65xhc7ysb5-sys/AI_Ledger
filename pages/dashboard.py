import streamlit as st
import pandas as pd
import sys
import os

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# get_available_months 함수가 추가되었습니다.
from database import load_data, delete_expense, update_expense, get_available_months

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

st.title("📊 소비 분석 대시보드")

# --- 1. 사이드바 (필터 및 다운로드) ---
with st.sidebar:
    st.header("🔍 조회 설정")
    
    # [핵심] 월 선택 필터 추가
    available_months = get_available_months()
    
    # 데이터가 하나도 없으면 빈 리스트일 수 있음
    if not available_months:
        selected_month = "전체 기간"
    else:
        # 옵션에 '전체 기간' 추가
        options = ["전체 기간"] + available_months
        selected_month = st.selectbox("📅 월 선택", options, index=1 if len(options) > 1 else 0)

    st.divider()
    
    st.header("📂 데이터 관리")
    # CSV 다운로드는 필터링된 데이터(df)를 기준으로 할지, 전체를 할지 선택 가능
    # 여기서는 현재 보고 있는 데이터(df)를 다운로드하도록 구현
    if 'df' in locals() and not df.empty:
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 현재 조회 내역 다운로드",
            data=csv,
            file_name=f"ledger_{selected_month}.csv",
            mime="text/csv"
        )

# --- 2. 데이터 로드 (필터 적용) ---
# 선택된 월(selected_month)을 넘겨서 해당 데이터만 가져옴
df = load_data(selected_month)

if df.empty:
    st.info(f"'{selected_month}'에 해당하는 데이터가 없습니다. 내역을 입력해주세요.")
    st.stop()

# 날짜 변환
df['date'] = pd.to_datetime(df['date'])

# --- 3. 통계 지표 ---
st.subheader(f"{selected_month} 지출 요약")
total_spend = df['amount'].sum()
col1, col2, col3 = st.columns(3)
col1.metric("총 지출액", f"{total_spend:,}원")
col2.metric("총 건수", f"{len(df)}건")
if not df.empty:
    top_cat = df.groupby('category')['amount'].sum().idxmax()
    col3.metric("최다 지출 카테고리", top_cat)

st.divider()

# --- 4. 그래프 ---
tab1, tab2 = st.tabs(["📈 날짜별 추이", "🍕 카테고리별 비중"])
with tab1:
    st.caption("일별 지출 흐름")
    daily_spend = df.groupby('date')['amount'].sum().reset_index()
    st.line_chart(daily_spend, x='date', y='amount', color='#FF4B4B')

with tab2:
    st.caption("카테고리별 지출")
    category_spend = df.groupby('category')['amount'].sum()
    st.bar_chart(category_spend)

st.divider()

# --- 5. 상세 내역 관리 (수정/삭제) ---
st.subheader("📋 상세 내역 관리")
st.caption("💡 팁: 표의 내용을 더블 클릭하면 수정됩니다. (금액, 날짜, 카테고리 등)")

CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

# 데이터 에디터
edited_df = st.data_editor(
    df,
    column_config={
        "id": None, 
        "created_at": None,
        "amount": st.column_config.NumberColumn("금액", format="%d원", step=100),
        "date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
        "category": st.column_config.SelectboxColumn("카테고리", options=CATEGORIES, required=True),
        "item": "내역",
    },
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True,
    key="expense_editor"
)

# 변경 사항 감지 및 업데이트
if st.session_state["expense_editor"]["edited_rows"]:
    updates = st.session_state["expense_editor"]["edited_rows"]
    for row_index, changes in updates.items():
        target_id = df.iloc[row_index]['id']
        for col_name, new_value in changes.items():
            if col_name == 'date':
                new_value = str(new_value).split('T')[0]
            update_expense(target_id, col_name, new_value)
    st.toast("✅ 수정 내용이 저장되었습니다!")

if st.session_state["expense_editor"]["deleted_rows"]:
    deletes = st.session_state["expense_editor"]["deleted_rows"]
    for row_index in deletes:
        target_id = df.iloc[row_index]['id']
        delete_expense(target_id)
    st.toast("🗑️ 내역이 삭제되었습니다.")
    st.rerun()