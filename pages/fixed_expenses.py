import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import (
    save_fixed_expense, get_fixed_expenses, delete_fixed_expense, 
    insert_expense, load_data
)
from config import DEFAULT_CATEGORIES

st.set_page_config(page_title="고정 지출 관리", page_icon="🔄")

st.title("🔄 고정 지출 관리")
st.caption("매달 반복되는 지출(월세, 구독료 등)을 등록하고 간편하게 기록하세요.")

# --- 1. 이번 달 납부 현황 체크 (자동화 핵심) ---
st.subheader("📅 이번 달 납부 현황")

# 현재 날짜 기준
today = datetime.now()
current_month_str = today.strftime("%Y-%m") # 예: 2026-02

# 데이터 가져오기
fixed_list = get_fixed_expenses()
current_month_data = load_data(current_month_str) # 이번 달 이미 기록된 내역

if fixed_list.empty:
    st.info("등록된 고정 지출이 없습니다. 아래에서 먼저 등록해주세요.")
else:
    # 납부 여부 확인 로직
    # 고정 지출 항목 이름이 이번 달 내역에 똑같이 있는지 확인합니다.
    paid_items = current_month_data['item'].tolist() if not current_month_data.empty else []
    
    pending_expenses = []
    
    # 리스트 형태로 보여주기
    for index, row in fixed_list.iterrows():
        is_paid = row['item'] in paid_items
        status_icon = "✅" if is_paid else "❌"
        status_text = "납부 완료" if is_paid else "미납 (기록 필요)"
        
        # 카드 디자인
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 1, 2])
            c1.write(f"**{row['payment_day']}일**")
            c2.write(f"**{row['item']}**")
            c3.write(f"{row['amount']:,}원")
            item_type = row.get("type", "지출") if hasattr(row, "get") else (row["type"] if "type" in row.index else "지출")
            c4.markdown("💰 저축" if item_type == "저축성지출" else "💸 지출")
            c5.write(f"{status_icon} {status_text}")
        
        if not is_paid:
            # 기록할 데이터 미리 만들어두기
            # 날짜는 '이번 달'의 해당 '결제일'로 설정
            due_date = f"{current_month_str}-{str(row['payment_day']).zfill(2)}"
            pending_expenses.append({
                "date": due_date,
                "item": row['item'],
                "amount": row['amount'],
                "category": row['category']
            })

    # 미납 내역이 있다면 일괄 처리 버튼 표시
    if pending_expenses:
        st.warning(f"아직 기록되지 않은 고정 지출이 {len(pending_expenses)}건 있습니다.")
        if st.button("🚀 미납 내역 한 번에 기록하기", type="primary", use_container_width=True):
            if insert_expense(pending_expenses):
                st.success("✅ 모든 고정 지출이 가계부에 기록되었습니다!")
                st.rerun() # 화면 새로고침해서 '납부 완료'로 변경
    else:
        st.success("🎉 이번 달 모든 고정 지출이 기록되었습니다!")

st.divider()

# --- 2. 고정 지출 등록 및 관리 ---
st.subheader("⚙️ 고정 지출 항목 설정")

col1, col2 = st.columns([1, 1])

# [왼쪽] 등록 폼
with col1:
    # 변경 후
    with st.form("add_fixed_form", clear_on_submit=True):
        st.write("**새 항목 추가**")
        item_name = st.text_input("항목명 (예: 넷플릭스)")
        amount = st.number_input("금액", min_value=0, step=1000)

        expense_type = st.radio(
            "유형",
            ["지출", "저축성지출"],
            horizontal=True,
            help="저축성 지출: DC 퇴직연금, IRP, 개인연금, 청약저축 자동이체, 보험료(종신·실손·암보험), 자녀 학자금 적립",
        )

        category = st.selectbox("카테고리", DEFAULT_CATEGORIES)

        day = st.number_input("매월 결제일 (1~31)", min_value=1, max_value=31, value=1)

        if st.form_submit_button("등록"):
            if item_name and amount > 0:
                save_fixed_expense(item_name, amount, category, day, type=expense_type)
                st.success(f"'{item_name}' 등록 완료!")
                st.rerun()
            else:
                st.error("항목명과 금액을 정확히 입력해주세요.")

# [오른쪽] 삭제 목록
with col2:
    st.write("**등록된 목록 (삭제)**")
    if fixed_list.empty:
        st.caption("등록된 항목이 없습니다.")
    else:
        for index, row in fixed_list.iterrows():
            f_col1, f_col2 = st.columns([4, 1])
            f_col1.text(f"{row['item']} ({row['amount']:,}원)")
            if f_col2.button("삭제", key=f"del_fix_{row['id']}"):
                delete_fixed_expense(row['id'])
                st.rerun()