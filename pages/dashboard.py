import streamlit as st
import pandas as pd
import sys
import os

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import load_data, delete_expense, update_expense

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

st.title("📊 소비 분석 대시보드")

# --- 1. 데이터 로드 ---
df = load_data()

if df.empty:
    st.info("아직 저장된 데이터가 없습니다. 'Home' 페이지에서 내역을 입력해주세요.")
    st.stop()

# 날짜 변환
df['date'] = pd.to_datetime(df['date'])

# --- 2. 사이드바 (CSV 다운로드) ---
with st.sidebar:
    st.header("📂 데이터 관리")
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 전체 내역 다운로드 (CSV)",
        data=csv,
        file_name="ai_ledger_backup.csv",
        mime="text/csv"
    )
    st.write(f"총 {len(df)}건의 데이터")

# --- 3. 통계 지표 ---
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
    st.subheader("일별 지출 흐름")
    daily_spend = df.groupby('date')['amount'].sum().reset_index()
    st.line_chart(daily_spend, x='date', y='amount', color='#FF4B4B')

with tab2:
    st.subheader("카테고리별 지출")
    category_spend = df.groupby('category')['amount'].sum()
    st.bar_chart(category_spend)

st.divider()

# --- 5. [핵심] 수정 가능한 내역 리스트 ---
st.subheader("📋 상세 내역 관리 (수정/삭제)")
st.caption("💡 팁: 표의 내용을 더블 클릭하면 바로 수정됩니다. 수정 사항은 즉시 자동 저장됩니다.")

# 카테고리 옵션 (드롭다운으로 보여주기 위함)
CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

# Streamlit Data Editor 설정
edited_df = st.data_editor(
    df,
    column_config={
        "id": None, # ID는 숨김 (수정 불가)
        "created_at": None, # 생성일자 숨김
        "amount": st.column_config.NumberColumn(
            "금액",
            format="%d원", # 원화 표시
            min_value=0,
            step=100
        ),
        "date": st.column_config.DateColumn(
            "날짜",
            format="YYYY-MM-DD"
        ),
        "category": st.column_config.SelectboxColumn(
            "카테고리",
            options=CATEGORIES,
            required=True
        ),
        "item": "내역",
    },
    hide_index=True,
    num_rows="dynamic", # 행 삭제 가능 (추가는 Home에서 권장하지만 여기서도 가능은 함)
    use_container_width=True,
    key="expense_editor" # 세션 상태 감지용 키
)

# --- 6. 변경 사항 감지 및 DB 업데이트 로직 ---
# st.data_editor는 변경된 내용을 session_state에 저장합니다.
if st.session_state["expense_editor"]["edited_rows"]:
    # 1. 수정된 행 처리
    updates = st.session_state["expense_editor"]["edited_rows"]
    
    for row_index, changes in updates.items():
        # 데이터프레임의 인덱스로 실제 DB ID 찾기
        # (df는 날짜순 정렬되어 있으므로 row_index로 원본 ID를 찾아야 함)
        target_id = df.iloc[row_index]['id']
        
        for col_name, new_value in changes.items():
            # 날짜 컬럼은 datetime 객체나 문자열로 올 수 있어 처리 필요
            if col_name == 'date':
                new_value = str(new_value).split('T')[0] # YYYY-MM-DD 형식 맞춤
                
            # DB 업데이트 함수 호출
            update_expense(target_id, col_name, new_value)
    
    # 수정 후 즉시 새로고침하여 반영
    st.toast("✅ 수정 내용이 저장되었습니다!")
    # 주의: rerun을 너무 빨리 하면 무한 루프 돌 수 있으므로 토스트 메시지로 대체하거나 
    # 필요시 st.rerun() 사용 (여기선 자연스러운 UX를 위해 자동 반영 기다림)

if st.session_state["expense_editor"]["deleted_rows"]:
    # 2. 삭제된 행 처리
    deletes = st.session_state["expense_editor"]["deleted_rows"]
    
    for row_index in deletes:
        target_id = df.iloc[row_index]['id']
        delete_expense(target_id)
    
    st.toast("🗑️ 내역이 삭제되었습니다.")
    st.rerun() # 삭제는 행이 사라져야 하므로 즉시 새로고침