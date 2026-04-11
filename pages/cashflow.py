import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date

from database import load_data, get_available_months, get_budgets, get_fixed_expenses, save_monthly_income, get_monthly_income, save_setting
from core.finance import calculate_fv as _sv_fv, calculate_asset_fv as _as_fv, calculate_max_loan
from components.formatters import format_korean

from config import TARGET_DATE_YEAR, TARGET_DATE_MONTH, TARGET_EQUITY, MONTHLY_SAVING_TARGET
from database import get_setting

def _s(key, default):
    return type(default)(get_setting(key) or default)


# ── 상수 ────────────────────────────────────────────────────────
TARGET_DATE        = date(TARGET_DATE_YEAR, TARGET_DATE_MONTH, 1)


# ── 순수 계산 함수 ───────────────────────────────────────────────

def months_remaining(target: date = TARGET_DATE) -> int:
    today = date.today()
    return max(0, (target.year - today.year) * 12 + (target.month - today.month))


def build_yearly_chart(pmt, pv, annual_rate, chongsek, jeonse):
    """연도별 포인트 적립 추이 데이터 생성"""
    today = date.today()
    points = []
    year = today.year
    month = today.month

    while True:
        m = (TARGET_DATE.year - year) * 12 + (TARGET_DATE.month - month)
        if m < 0:
            break
        elapsed = months_remaining(TARGET_DATE) - m
        sv_fv = int(_sv_fv(pmt, annual_rate, elapsed))
        as_fv = int(_as_fv(pv, annual_rate, elapsed))
        total = sv_fv + as_fv + chongsek + jeonse
        points.append({"date": f"{year}-{month:02d}", "총 자기자본": total})

        # 다음 연도 같은 월 or 최종 목표월
        year += 1
        if year > TARGET_DATE.year or (year == TARGET_DATE.year and month > TARGET_DATE.month):
            # 마지막 포인트: 목표 시점
            sv_fv = int(_sv_fv(pmt, annual_rate, months_remaining(TARGET_DATE)))
            as_fv = int(_as_fv(pv, annual_rate, months_remaining(TARGET_DATE)))
            points.append({"date": f"{TARGET_DATE.year}-{TARGET_DATE.month:02d}", "총 자기자본": total})
            break

    return pd.DataFrame(points)


# ── 페이지 ──────────────────────────────────────────────────────

st.set_page_config(page_title="현금흐름 & 매수 시뮬레이터", layout="wide")
st.title("현금흐름 & 자기자본 시뮬레이터")

# ── Section A: 이번 달 현금흐름 요약 ────────────────────────────
st.header("Section A — 이번 달 현금흐름")

current_month = datetime.today().strftime("%Y-%m")
_default_income = _s("income_monthly", 10_800_000)
monthly_income = st.sidebar.number_input(
    "이번 달 실수령 합산 소득 (원)",
    min_value=0,
    value=get_monthly_income(current_month, _default_income),
    step=100_000,
    format="%d",
)
st.sidebar.caption(f"= {format_korean(monthly_income)}")
if st.sidebar.button("이번 달 소득 저장", use_container_width=True):
    save_monthly_income(current_month, monthly_income)
    st.sidebar.success("저장됨")
if st.sidebar.button("기본 소득 변경", use_container_width=True):
    save_setting("income_monthly", monthly_income)
    st.sidebar.success("기본값 업데이트됨")


df = load_data(current_month, None)
total_expense = int(df["amount"].sum()) if not df.empty else 0
net_savings   = monthly_income - total_expense

col1, col2, col3 = st.columns(3)
col1.metric("월 소득", f"{monthly_income:,}원")
col2.metric("총 지출", f"{total_expense:,}원")

st.divider()

# ── Section B: 2029년 2월 자기자본 적립 시뮬레이터 ──────────────
# 변경 후
st.header("Section B — 2029년 2월 자기자본 적립 시뮬레이터")

remaining_months = months_remaining()
st.caption(f"오늘({date.today()}) 기준 목표까지 **{remaining_months}개월** 남음")

# ── 저축 계산 모드 탭 ──────────────────────────────────
fixed_df = get_fixed_expenses()
if fixed_df.empty:
    fixed_expense_sum = 0
    savings_type_sum  = 0
elif "type" in fixed_df.columns:
    fixed_expense_sum = int(fixed_df[fixed_df["type"] != "저축성지출"]["amount"].sum())
    savings_type_sum  = int(fixed_df[fixed_df["type"] == "저축성지출"]["amount"].sum())
else:
    fixed_expense_sum = int(fixed_df["amount"].sum())
    savings_type_sum  = 0

tab_prev, tab_budget, tab_manual = st.tabs(
    ["📊 지난달 역산 (기본값)", "🎯 예산 기반", "✏️ 직접 입력 (시나리오 탐색)"]
)

with tab_prev:
    st.caption("가장 최근 확정 지출 실적을 기반으로 저축 가능액을 역산합니다.")
    prev_month_date = date.today().replace(day=1)

    if prev_month_date.month == 1:
        prev_month_date = prev_month_date.replace(year=prev_month_date.year - 1, month=12)
    else:
        prev_month_date = prev_month_date.replace(month=prev_month_date.month - 1)
    prev_month_str = prev_month_date.strftime("%Y-%m")

    # ── 변경 후 ──
    prev_df = load_data(prev_month_str)
    prev_variable = int(prev_df["amount"].sum()) if not prev_df.empty else 0

    # fixed_df는 탭 밖에서 이미 로드 — prev_fixed, savings_type_sum 재사용
    prev_fixed        = fixed_expense_sum
    prev_savings_type = savings_type_sum

    # 월별 소득 입력 + 저장
    _default_income = _s("income_monthly", 10_800_000)
    prev_income = st.number_input(
        f"{prev_month_str} 실수령 소득 (원)",
        min_value=0,
        value=get_monthly_income(prev_month_str, _default_income),
        step=100_000,
        format="%d",
        help="육아휴직 등 소득 변동이 있으면 수정 후 저장하세요.",
    )
    if st.button(f"{prev_month_str} 소득 저장", key="btn_save_prev_income"):
        save_monthly_income(prev_month_str, prev_income)
        st.success("저장됨")

    # 공식: 소득 - 변동지출 - 순고정지출 - 저축성지출
    prev_calculated = prev_income - prev_variable - prev_fixed - prev_savings_type

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("변동 지출",   f"{prev_variable:,}원")
    mc2.metric("순고정 지출", f"{prev_fixed:,}원",        help="저축성 지출 제외한 고정 지출")
    mc3.metric("저축성 지출", f"{prev_savings_type:,}원", help="DC, IRP, 보험 등 — 별도 자산 형성, 저축에서 차감")
    mc4.metric(
        "추정 월 저축",
        f"{prev_calculated:,}원",
        delta=f"{prev_calculated - MONTHLY_SAVING_TARGET:+,}원 (목표 대비)"
              if prev_calculated != MONTHLY_SAVING_TARGET else "목표 일치",
    )
    st.caption(
        f"📅 **{prev_month_str} 실적** 기준 | "
        f"소득 {prev_income:,}원 − 변동 {prev_variable:,}원 "
        f"− 순고정 {prev_fixed:,}원 − 저축성 {prev_savings_type:,}원"
    )
    monthly_saving_prev = max(prev_calculated, 0)

with tab_budget:
    st.caption("설정된 예산 합계를 기준으로 저축 가능액을 계산합니다. (계획값)")
    budgets_df_cf = get_budgets()
    if budgets_df_cf.empty:
        st.warning("설정된 예산이 없습니다. [예산 설계] 페이지에서 먼저 예산을 입력해 주세요.")
        budget_total = 0
    else:
        budget_total = int(budgets_df_cf["amount"].sum())
        st.metric("예산 합계", f"{budget_total:,}원")
    
    # 공식: 소득 - 예산합계 - 순고정지출 - 저축성지출
    budget_calculated = monthly_income - budget_total - fixed_expense_sum - savings_type_sum
    bc1, bc2 = st.columns(2)
    bc1.metric("순고정 지출", f"{fixed_expense_sum:,}원", help="저축성 지출 제외")
    bc2.metric("저축성 지출", f"{savings_type_sum:,}원",  help="DC, IRP, 보험 등")
    st.metric(
        "예산 기준 월 저축 예상액",
        f"{budget_calculated:,}원",
        delta=f"{budget_calculated - MONTHLY_SAVING_TARGET:+,}원 (목표 대비)"
              if budget_calculated != MONTHLY_SAVING_TARGET else "목표 일치",
    )
    st.caption(
        f"소득 {monthly_income:,}원 − 예산 {budget_total:,}원 "
        f"− 순고정 {fixed_expense_sum:,}원 − 저축성 {savings_type_sum:,}원"
    )
    monthly_saving_budget = max(budget_calculated, 0)

with tab_manual:
    st.caption("슬라이더로 직접 저축액을 설정하고 시나리오를 탐색합니다.")
    monthly_saving_manual = st.slider(
        "월 저축 목표액 (만원)",
        min_value=0, max_value=700, value=325, step=5
    ) * 10_000
    st.caption(f"= {format_korean(monthly_saving_manual)}")

# ── 탭 선택 결과 → monthly_saving 결정 ────────────────
# session_state로 마지막 활성 탭 추적
# Streamlit 탭은 활성 탭 인덱스를 직접 노출하지 않으므로
# 각 탭 내부에서 session_state에 값을 기록하는 방식으로 처리
if "cf_saving_mode" not in st.session_state:
    st.session_state["cf_saving_mode"] = "prev"

col_mode = st.columns(3)
with col_mode[0]:
    if st.button("📊 지난달 역산 적용", use_container_width=True):
        st.session_state["cf_saving_mode"] = "prev"
with col_mode[1]:
    if st.button("🎯 예산 기반 적용", use_container_width=True):
        st.session_state["cf_saving_mode"] = "budget"
with col_mode[2]:
    if st.button("✏️ 직접 입력 적용", use_container_width=True):
        st.session_state["cf_saving_mode"] = "manual"

mode = st.session_state["cf_saving_mode"]
if mode == "prev":
    monthly_saving = monthly_saving_prev
    st.info(f"📊 **지난달 역산** 모드 적용 중 — 월 저축 **{monthly_saving:,}원**")
elif mode == "budget":
    monthly_saving = monthly_saving_budget
    st.info(f"🎯 **예산 기반** 모드 적용 중 — 월 저축 **{monthly_saving:,}원**")
else:
    monthly_saving = monthly_saving_manual
    st.info(f"✏️ **직접 입력** 모드 적용 중 — 월 저축 **{monthly_saving:,}원**")

annual_return = st.slider(
    "예상 투자 연수익률 (%)",
    min_value=0.0, max_value=8.0, value=3.0, step=0.5
) / 100