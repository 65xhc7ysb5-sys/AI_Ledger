import streamlit as st
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# add_category, delete_category_safe, get_categories 함수 추가됨
from database import (
    load_data, delete_expense, update_expense, get_available_months, 
    DB_NAME, get_categories, add_category, delete_category_safe
)

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")
st.title("📊 소비 분석 대시보드")

# --- 1. 사이드바 (필터 및 백업) ---
with st.sidebar:
    st.header("🔍 조회 설정")
    
    # [신규] 사용자(Spender) 필터
    spender_filter = st.radio("👤 사용자 선택", ["전체", "공동", "남편", "아내", "아이"])
    
    # 월 선택
    available_months = get_available_months()
    if not available_months:
        selected_month = "전체 기간"
    else:
        options = ["전체 기간"] + available_months
        selected_month = st.selectbox("📅 월 선택", options)

    st.divider()
    
    # 카테고리 관리 (사이드바 공간 활용)
    with st.expander("🏷️ 카테고리 관리"):
        new_cat = st.text_input("새 카테고리 추가", placeholder="예: 반려동물")
        if st.button("추가"):
            if new_cat:
                if add_category(new_cat):
                    st.success(f"'{new_cat}' 추가됨")
                    st.rerun()
                else: st.error("중복됨")
        
        st.write("---")
        st.write("**카테고리 삭제**")
        st.caption("삭제 시 해당 내역은 '미분류'로 이동됩니다.")
        current_cats = get_categories()
        del_cat = st.selectbox("삭제할 카테고리", ["선택 안 함"] + current_cats)
        if del_cat != "선택 안 함":
            if st.button(f"🗑️ '{del_cat}' 삭제"):
                if delete_category_safe(del_cat):
                    st.warning(f"'{del_cat}' 삭제 및 내역 이동 완료")
                    st.rerun()

    st.divider()
    st.subheader("🛡️ 시스템 백업")
    try:
        with open(DB_NAME, "rb") as f:
            st.download_button("💾 DB 원본 백업", f, "ledger_backup.db")
    except: pass

# --- 2. 데이터 로드 (필터 적용) ---
df = load_data(selected_month, spender_filter)

if df.empty:
    st.info("데이터가 없습니다.")
    st.stop()

df['date'] = pd.to_datetime(df['date'])

# --- 3. 통계 및 그래프 ---
st.subheader(f"{selected_month} ({spender_filter}) 요약")
col1, col2, col3 = st.columns(3)
col1.metric("총 지출액", f"{df['amount'].sum():,}원")
col2.metric("총 건수", f"{len(df)}건")
top_cat = df.groupby('category')['amount'].sum().idxmax() if not df.empty else "-"
col3.metric("최다 지출", top_cat)

tab1, tab2 = st.tabs(["📈 추이/비중", "📋 상세 내역"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.caption("일별 지출")
        st.line_chart(df.groupby('date')['amount'].sum(), color='#FF4B4B')
    with c2:
        st.caption("카테고리별 비중")
        st.bar_chart(df.groupby('category')['amount'].sum())

with tab2:
    st.caption("수정하려면 항목을 더블클릭하세요.")
    # 현재 존재하는 최신 카테고리 목록 가져오기
    latest_categories = get_categories()
    
    edited_df = st.data_editor(
        df,
        column_config={
            "id": None,
            "spender": st.column_config.SelectboxColumn("사용자", options=["공동", "남편", "아내", "아이"]),
            "amount": st.column_config.NumberColumn("금액", format="%d원"),
            "date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
            "category": st.column_config.SelectboxColumn("카테고리", options=latest_categories, required=True),
        },
        hide_index=True,
        num_rows="dynamic",
        key="editor"
    )

    if st.session_state["editor"]["edited_rows"]:
        for idx, changes in st.session_state["editor"]["edited_rows"].items():
            tid = df.iloc[idx]['id']
            for col, val in changes.items():
                if col == 'date': val = str(val).split('T')[0]
                update_expense(tid, col, val)
        st.toast("저장됨!")
        
    if st.session_state["editor"]["deleted_rows"]:
        for idx in st.session_state["editor"]["deleted_rows"]:
            delete_expense(df.iloc[idx]['id'])
        st.toast("삭제됨!")
        st.rerun()