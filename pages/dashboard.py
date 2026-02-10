import streamlit as st
import pandas as pd
import sys
import os

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [중요] database.py에서 DB 경로 변수(DB_NAME)까지 가져옵니다.
from database import load_data, delete_expense, update_expense, get_available_months, DB_NAME

# config.py 로드 (없을 경우 대비)
try:
    from config import CATEGORIES
except ImportError:
    CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

st.title("📊 소비 분석 대시보드")

# --- 1. 사이드바 (조회 및 백업) ---
with st.sidebar:
    st.header("🔍 조회 설정")
    
    # 월 선택 필터
    available_months = get_available_months()
    if not available_months:
        selected_month = "전체 기간"
    else:
        options = ["전체 기간"] + available_months
        selected_month = st.selectbox("📅 월 선택", options, index=1 if len(options) > 1 else 0)

    st.divider()
    
    st.header("📂 데이터 관리")
    
    # DB 원본 백업
    st.subheader("🛡️ 시스템 백업")
    try:
        # DB_NAME 변수를 사용해 정확한 위치의 파일을 엽니다.
        with open(DB_NAME, "rb") as f:
            db_data = f.read()
            
        st.download_button(
            label="💾 데이터베이스 원본 백업 (.db)",
            data=db_data,
            file_name="ledger_backup.db",
            mime="application/octet-stream",
            help="이 파일을 잘 보관하면 나중에 데이터를 통째로 복구할 수 있습니다."
        )
    except FileNotFoundError:
        st.warning("아직 생성된 DB 파일이 없습니다.")

# --- 2. 데이터 로드 ---
df = load_data(selected_month)

if df.empty:
    st.info(f"'{selected_month}'에 해당하는 데이터가 없습니다. 내역을 입력해주세요.")
    st.stop()

# 날짜 변환
df['date'] = pd.to_datetime(df['date'])

# (사이드바에 CSV 다운로드 버튼 추가 - df가 로드된 후)
with st.sidebar:
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 현재 조회 내역 다운로드 (CSV)",
        data=csv,
        file_name=f"ledger_{selected_month}.csv",
        mime="text/csv"
    )

# --- 3. 통계 지표 (Metrics) ---
st.subheader(f"{selected_month} 지출 요약")
total_spend = df['amount'].sum()
col1, col2, col3 = st.columns(3)
col1.metric("총 지출액", f"{total_spend:,}원")
col2.metric("총 건수", f"{len(df)}건")
if not df.empty:
    top_cat = df.groupby('category')['amount'].sum().idxmax()
    col3.metric("최다 지출 카테고리", top_cat)

st.divider()

# --- 4. 그래프 섹션 ---
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

# 데이터 에디터 (수정 기능)
edited_df = st.data_editor(
    df,
    column_config={
        "id": None, # ID 숨김
        "created_at": None,
        "amount": st.column_config.NumberColumn("금액", format="%d원", step=100),
        "date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
        "category": st.column_config.SelectboxColumn("카테고리", options=CATEGORIES, required=True),
        "item": "내역",
    },
    hide_index=True,
    num_rows="dynamic", # 행 삭제 가능
    use_container_width=True,
    key="expense_editor"
)

# --- 6. 변경 사항 감지 및 DB 업데이트 ---
if st.session_state["expense_editor"]["edited_rows"]:
    updates = st.session_state["expense_editor"]["edited_rows"]
    for row_index, changes in updates.items():
        # 필터링된 df의 인덱스로 실제 DB ID 찾기
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