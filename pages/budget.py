import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CATEGORIES

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# delete_budget 함수가 추가되었습니다.
from database import load_data, save_budget, get_budgets, delete_budget

st.set_page_config(page_title="예산 관리", page_icon="💰")

st.title("💰 월별 예산 관리")
st.caption("카테고리별 목표 금액을 설정하고 지출 현황을 점검하세요.")

# --- 1. 예산 설정 (입력) ---
with st.container(border=True):
    st.subheader("➕ 새 예산 설정 / 수정")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # 카테고리 선택
        cat = st.selectbox("카테고리", CATEGORIES, label_visibility="collapsed", placeholder="카테고리 선택")
    with col2:
        # 금액 입력
        amt = st.number_input("목표 금액", min_value=0, step=10000, label_visibility="collapsed", placeholder="금액 (원)")
    with col3:
        # 저장 버튼
        if st.button("저장", type="primary", use_container_width=True):
            if amt > 0:
                save_budget(cat, amt)
                st.toast(f"✅ {cat} 예산이 {amt:,}원으로 설정되었습니다.")
                st.rerun()
            else:
                st.toast("⚠️ 금액을 0원 이상 입력해주세요.")

st.divider()

# --- 2. 예산 현황 및 수정 (메인) ---
# 현재 날짜 기준 '이번 달' 구하기
today = datetime.now()
current_month_str = today.strftime("%Y-%m")

# 데이터 가져오기
expenses_df = load_data(current_month_str)
budgets_df = get_budgets()

if budgets_df.empty:
    st.info("아직 설정된 예산이 없습니다. 위에서 예산을 등록해주세요.")
else:
    # 2-1. 데이터 병합 (예산 + 실제 지출)
    if not expenses_df.empty:
        spent_by_cat = expenses_df.groupby('category')['amount'].sum()
    else:
        spent_by_cat = pd.Series(dtype=int)
    
    # 예산 데이터프레임에 '실제 지출', '남은 돈', '달성률' 컬럼 추가
    # (원본 수정을 피하기 위해 copy)
    display_df = budgets_df.copy()
    
    # 실제 지출 매핑
    display_df['spent'] = display_df['category'].map(spent_by_cat).fillna(0).astype(int)
    
    # 남은 돈 & 달성률 계산
    display_df['remaining'] = display_df['amount'] - display_df['spent']
    display_df['percent'] = (display_df['spent'] / display_df['amount'] * 100).round(1)
    
    # 보기 좋게 정렬 (달성률 높은 순)
    display_df = display_df.sort_values(by='percent', ascending=False)

    # 2-2. 탭 구성 (현황 그래프 vs 수정 모드)
    tab1, tab2 = st.tabs(["📊 달성 현황", "✏️ 예산 수정/삭제"])
    
    # [Tab 1] 시각화 (기존 그래프 유지)
    with tab1:
        for index, row in display_df.iterrows():
            cat_name = row['category']
            budget_val = row['amount']
            spent_val = row['spent']
            remain_val = row['remaining']
            percent_val = row['percent']
            
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{cat_name}**")
                
                # 상태 메시지
                if remain_val < 0:
                    c2.markdown(f":red[**{abs(remain_val):,}원 초과**]")
                    bar_color = "red" # (참고: st.progress에 색상 지정은 불가하지만 로직상 구분)
                else:
                    c2.markdown(f":blue[**{remain_val:,}원 남음**]")
                
                # 진행바 (최대 1.0)
                prog = min(spent_val / budget_val, 1.0) if budget_val > 0 else 0
                st.progress(prog)
                st.caption(f"지출: {spent_val:,}원 / 예산: {budget_val:,}원 ({percent_val}%)")

    # [Tab 2] 엑셀형 수정 에디터 (핵심 기능)
    with tab2:
        st.caption("💡 금액을 더블 클릭하여 수정하거나, 행을 선택해 삭제할 수 있습니다.")
        
        # 수정 가능한 데이터프레임 (amount만 수정 가능하게)
        edited_df = st.data_editor(
            budgets_df,
            column_config={
                "category": "카테고리 (수정 불가)",
                "amount": st.column_config.NumberColumn("예산 금액 (원)", format="%d원", step=10000)
            },
            disabled=["category"], # 카테고리명은 수정 금지 (키 값이므로)
            num_rows="dynamic",    # 행 삭제 가능
            use_container_width=True,
            key="budget_editor",
            hide_index=True
        )
        
        # 수정 감지 및 DB 업데이트
        if st.session_state["budget_editor"]["edited_rows"]:
            updates = st.session_state["budget_editor"]["edited_rows"]
            for row_idx, changes in updates.items():
                # 원본 데이터에서 카테고리 찾기
                category = budgets_df.iloc[row_idx]['category']
                if "amount" in changes:
                    new_amount = changes["amount"]
                    save_budget(category, new_amount)
            
            st.toast("✅ 예산이 수정되었습니다.")
        
        # 삭제 감지 및 DB 업데이트
        if st.session_state["budget_editor"]["deleted_rows"]:
            deletes = st.session_state["budget_editor"]["deleted_rows"]
            for row_idx in deletes:
                category = budgets_df.iloc[row_idx]['category']
                delete_budget(category)
            
            st.toast("🗑️ 예산이 삭제되었습니다.")
            st.rerun()