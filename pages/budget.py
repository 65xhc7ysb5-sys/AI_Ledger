import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import load_data, save_budget, get_budgets

st.set_page_config(page_title="예산 관리", page_icon="💰")

st.title("💰 월별 예산 관리")
st.caption("카테고리별 목표 금액을 설정하고 지출 현황을 점검하세요.")

# --- 1. 예산 설정 섹션 ---
with st.expander("⚙️ 예산 설정하기 (열기/닫기)", expanded=False):
    st.write("카테고리별 월 예산을 설정합니다.")
    
    CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]
    
    with st.form("budget_form"):
        col1, col2 = st.columns(2)
        with col1:
            cat = st.selectbox("카테고리", CATEGORIES)
        with col2:
            amt = st.number_input("목표 금액 (원)", min_value=0, step=10000)
            
        if st.form_submit_button("예산 저장"):
            if amt > 0:
                save_budget(cat, amt)
                st.success(f"✅ {cat} 예산이 {amt:,}원으로 설정되었습니다.")
                st.rerun()
            else:
                st.warning("금액을 입력해주세요.")

st.divider()

# --- 2. 이번 달 현황 분석 ---
# 현재 날짜 기준 '이번 달' 구하기
today = datetime.now()
current_month_str = today.strftime("%Y-%m")

st.subheader(f"📊 {today.month}월 예산 달성 현황")

# 데이터 가져오기
expenses_df = load_data(current_month_str)  # 이번 달 지출 내역
budgets_df = get_budgets()                 # 설정된 예산 내역

if budgets_df.empty:
    st.info("설정된 예산이 없습니다. 위에서 예산을 먼저 등록해주세요.")
else:
    # 1. 실제 지출 집계 (카테고리별 합계)
    if not expenses_df.empty:
        spent_by_cat = expenses_df.groupby('category')['amount'].sum()
    else:
        spent_by_cat = pd.Series()

    # 2. 예산 데이터와 병합해서 보여주기
    # 예산이 설정된 카테고리 순회
    for index, row in budgets_df.iterrows():
        category = row['category']
        budget_amount = row['amount']
        
        # 실제 쓴 돈 (없으면 0원)
        spent_amount = spent_by_cat.get(category, 0)
        
        # 퍼센트 계산
        percent = (spent_amount / budget_amount) * 100 if budget_amount > 0 else 0
        
        # UI 구성
        with st.container(border=True):
            # 상단: 카테고리 이름과 금액 정보
            c1, c2 = st.columns([1, 1])
            c1.write(f"**{category}**")
            
            # 남은 금액 계산
            remaining = budget_amount - spent_amount
            
            if remaining < 0:
                c2.markdown(f":red[**{abs(remaining):,}원 초과**]")
            else:
                c2.markdown(f":blue[**{remaining:,}원 남음**]")
            
            # 진행바 (100% 넘어가면 빨간색 경고 느낌을 위해 1.0으로 고정하되 텍스트로 강조)
            progress_val = min(percent / 100, 1.0)
            
            # 색상 로직: 100% 초과면 빨간색 바는 지원 안되므로, 텍스트로 강력 경고
            st.progress(progress_val)
            
            # 하단 상세 텍스트
            st.caption(f"지출: {spent_amount:,}원 / 예산: {budget_amount:,}원 ({percent:.1f}%)")

    # 예산 미설정 카테고리 중 지출이 있는 경우 경고
    if not expenses_df.empty:
        budget_cats = budgets_df['category'].tolist()
        spent_cats = spent_by_cat.index.tolist()
        
        no_budget_cats = [c for c in spent_cats if c not in budget_cats]
        
        if no_budget_cats:
            with st.expander("⚠️ 예산 없이 지출한 항목 보기"):
                for cat in no_budget_cats:
                    amt = spent_by_cat[cat]
                    st.write(f"- **{cat}**: {amt:,}원 (예산 미설정)")