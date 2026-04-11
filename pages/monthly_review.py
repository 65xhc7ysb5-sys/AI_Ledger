# pages/monthly_review.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from google import genai
from datetime import datetime, date
from database import (
    load_data, get_budgets, get_fixed_expenses, get_setting, get_monthly_income, save_monthly_income
)
from core.finance import calculate_fv as _sv_fv, calculate_asset_fv as _as_fv
from components.formatters import format_korean
from config import (
    MONTHLY_SAVING_TARGET, TARGET_DATE_YEAR, TARGET_DATE_MONTH,
    TARGET_EQUITY, GEMINI_MODEL_VER
)


# ── 헬퍼 ────────────────────────────────────────────────────────

def _s(key, default):
    return type(default)(get_setting(key) or default)

def _months_remaining() -> int:
    today = date.today()
    y = _s("goal_date_year",  TARGET_DATE_YEAR)
    m = _s("goal_date_month", TARGET_DATE_MONTH)
    target = date(y, m, 1)
    return max(0, (target.year - today.year) * 12 + (target.month - today.month))


def _anonymize_amount(amount: int, total: int) -> str:
    """금액 → 비율/등급. Gemini 전송용 (export_to_claude._anonymize와 동일 로직)."""
    if total <= 0:
        return "0% (매우낮음)"
    pct = amount / total * 100
    if pct >= 30:   grade = "매우높음"
    elif pct >= 20: grade = "높음"
    elif pct >= 10: grade = "보통"
    elif pct >= 5:  grade = "낮음"
    else:           grade = "매우낮음"
    return f"총지출의 {pct:.0f}% ({grade})"


# ── 페이지 설정 ──────────────────────────────────────────────────

st.set_page_config(page_title="월간 리뷰", page_icon="📋", layout="wide")
st.title("📋 월간 리뷰 리포트")
st.caption("목표 대비 이달의 진행률을 자동으로 계산하고, AI가 재무 서사를 작성합니다.")
st.divider()


# ── 월 선택 ──────────────────────────────────────────────────────

from database import get_available_months
available_months = get_available_months()
if not available_months:
    st.info("📭 지출 데이터가 없습니다. 먼저 지출을 입력해 주세요.")
    st.stop()

col_sel, _ = st.columns([1, 3])
with col_sel:
    selected_month = st.selectbox("📅 리뷰할 월 선택", available_months)


# ── 데이터 로드 ──────────────────────────────────────────────────

df         = load_data(selected_month)
budgets_df = get_budgets()
fixed_df   = get_fixed_expenses()

if df.empty:
    st.warning(f"⚠️ {selected_month}에 해당하는 지출 내역이 없습니다.")
    st.stop()

total_expense = int(df["amount"].sum())


# ── 소득 (사이드바) ──────────────────────────────────────────────

_default_income = _s("income_monthly", 10_000_000)
monthly_income = st.sidebar.number_input(
    f"{selected_month} 실수령 합산 소득 (원)",
    min_value=0,
    value=get_monthly_income(selected_month, _default_income),
    step=100_000,
    format="%d",
)
st.sidebar.caption(f"= {format_korean(monthly_income)}")
if st.sidebar.button("이 달 소득 저장", use_container_width=True):
    save_monthly_income(selected_month, monthly_income)
    st.sidebar.success("저장됨")


# ── 저축성 지출 분리 ─────────────────────────────────────────────

if not fixed_df.empty and "type" in fixed_df.columns:
    fixed_expense_sum = int(fixed_df[fixed_df["type"] != "저축성지출"]["amount"].sum())
    savings_type_sum  = int(fixed_df[fixed_df["type"] == "저축성지출"]["amount"].sum())
else:
    fixed_expense_sum = int(fixed_df["amount"].sum()) if not fixed_df.empty else 0
    savings_type_sum  = 0

# 실저축 = 소득 - 변동지출 - 순고정지출 - 저축성지출
actual_saving = monthly_income - total_expense - fixed_expense_sum - savings_type_sum
saving_target = _s("monthly_saving_target", MONTHLY_SAVING_TARGET)
saving_delta  = actual_saving - saving_target
saving_delta_pct = saving_delta / saving_target * 100 if saving_target > 0 else 0


# ── 자기자본 계산 ────────────────────────────────────────────────
# 현재 자기자본: 현재 투자자산(수익률 반영) + 전세보증금 회수예정 + 청약저축
# cashflow.py build_yearly_chart과 동일 구조 (elapsed=0이 아닌 현재 PV 그대로)

eq_investment  = _s("asset_investment",      50_000_000)
eq_jeonse      = _s("asset_jeonse_recovery", 260_000_000)
eq_subscription = _s("asset_subscription",  25_000_000)
goal_equity    = _s("goal_equity",           TARGET_EQUITY)
annual_rate    = _s("annual_return_rate",    0.06)
months_rem     = _months_remaining()

# 현재 시점 자기자본: 투자자산은 현재 PV 그대로, 나머지는 고정값
current_equity_est = eq_investment + eq_jeonse + eq_subscription
equity_progress    = current_equity_est / goal_equity * 100 if goal_equity > 0 else 0

# 목표 시점 예상 자기자본 (시뮬레이션)
projected_equity = (
    _sv_fv(saving_target, annual_rate, months_rem)
    + _as_fv(eq_investment, annual_rate, months_rem)
    + eq_jeonse
    + eq_subscription
)
projected_progress = projected_equity / goal_equity * 100 if goal_equity > 0 else 0


# ─────────────────────────────────────────────────────────────────
# Section A — 이달의 숫자 요약
# ─────────────────────────────────────────────────────────────────

st.header("Section A — 이달의 숫자 요약")

# A-1. 저축 실적
col1, col2, col3 = st.columns(3)
col1.metric(
    "이달 저축 추정",
    f"{actual_saving:,}원",
    f"{saving_delta:+,}원 ({saving_delta_pct:+.1f}%)",
    delta_color="normal",
)
col2.metric("월 저축 목표", f"{saving_target:,}원")
col3.metric("이달 총 지출", f"{total_expense:,}원")

st.divider()

# A-2. 자기자본 현황
st.markdown("**📈 자기자본 현황**")

col_eq1, col_eq2, col_eq3, col_eq4 = st.columns(4)
col_eq1.metric(
    "현재 자기자본",
    format_korean(current_equity_est),
    help="투자자산 + 전세보증금 회수 예정액 + 청약저축 (수익률 미적용 현재가)",
)

_goal_y = _s("goal_date_year",  TARGET_DATE_YEAR),
_goal_m = _s("goal_date_month", TARGET_DATE_MONTH),
col_eq2.metric(
    "목표 시점 예상 자기자본",
    format_korean(int(projected_equity)),
    f"{projected_progress:.1f}%",
    delta_color="normal",        
    help=f"현재 월 저축 목표({saving_target:,}원) 유지 시 {_goal_y}년 {_goal_m}월 예상치"
)
col_eq3.metric("목표 자기자본", format_korean(goal_equity))
col_eq4.metric(
    "현재 달성률",
    f"{equity_progress:.1f}%",
    f"목표까지 {format_korean(goal_equity - current_equity_est)} 부족"
    if current_equity_est < goal_equity else "목표 달성!",
    delta_color="off",
)

bar_pct = min(equity_progress / 100, 1.0)
st.progress(bar_pct, text=f"자기자본 현재 달성률 {equity_progress:.1f}% — 목표까지 {months_rem}개월 남음")

st.divider()

# A-3. 예산 초과 카테고리
st.markdown("**🔴 예산 초과 카테고리**")

if budgets_df.empty:
    st.caption("설정된 예산이 없습니다. [예산 설계] 페이지에서 예산을 먼저 설정해 주세요.")
else:
    spent_by_cat = df.groupby("category")["amount"].sum()
    over_budget  = [
        (row["category"], int(row["amount"]), int(spent_by_cat.get(row["category"], 0)))
        for _, row in budgets_df.iterrows()
        if int(spent_by_cat.get(row["category"], 0)) > int(row["amount"])
    ]
    if over_budget:
        cols = st.columns(min(len(over_budget), 4))
        for i, (cat, budget, spent) in enumerate(over_budget):
            cols[i % 4].metric(
                cat,
                f"{spent:,}원",
                f"{spent - budget:+,}원",
                delta_color="inverse",
            )
    else:
        st.success("✅ 모든 카테고리가 예산 범위 내에 있습니다!")

st.divider()


# ─────────────────────────────────────────────────────────────────
# Section B — Gemini 재무 서사
# ─────────────────────────────────────────────────────────────────

st.header("Section B — AI 재무 서사")
st.caption("Gemini가 이달의 숫자를 해석해 '재무 서사'와 다음 달 액션 아이템을 작성합니다.")
st.caption("💡 지출 금액은 익명화(비율/등급)되어 전송됩니다. 목표 수치는 포함됩니다.")


def _build_gemini_prompt() -> str:
    year, month = selected_month.split("-")

    # 가구 프로필 (_s() 동적 삽입)
    goal_year    = _s("goal_date_year",       TARGET_DATE_YEAR)
    goal_month_v = _s("goal_date_month",      TARGET_DATE_MONTH)
    goal_price   = _s("goal_purchase_price",  825_000_000)
    retire_year  = _s("goal_retirement_year", 2048)
    saving_rate  = actual_saving / monthly_income * 100 if monthly_income > 0 else 0

    # 카테고리별 익명화
    cat_summary = df.groupby("category")["amount"].sum().sort_values(ascending=False)
    cat_lines   = "\n".join(
        f"  - {cat}: {_anonymize_amount(int(amt), total_expense)}"
        for cat, amt in cat_summary.items()
    )

    # 예산 초과 텍스트
    if budgets_df.empty:
        over_text = "예산 미설정"
    else:
        spent_by_cat_p = df.groupby("category")["amount"].sum()
        over_items = [
            f"{row['category']}({int(spent_by_cat_p.get(row['category'], 0)) - int(row['amount']):,}원 초과)"
            for _, row in budgets_df.iterrows()
            if int(spent_by_cat_p.get(row["category"], 0)) > int(row["amount"])
        ]
        over_text = ", ".join(over_items) if over_items else "예산 초과 없음"

    return f"""당신은 대한민국 맞벌이 가구를 위한 가계 재정 코치입니다.
아래 데이터를 바탕으로 {year}년 {int(month)}월의 재무 리뷰를 작성하세요.

[가구 프로필]
- 내 집 마련 목표: {goal_year}년 {goal_month_v}월, 목표 매수가 {goal_price:,}원
- 은퇴 목표 연도: {retire_year}년
- 월 저축 목표: {saving_target:,}원
- 목표까지 남은 기간: {months_rem}개월

[이달 실적]
- 저축 실적: 목표 대비 {saving_delta_pct:+.1f}% ({'달성' if saving_delta >= 0 else '미달'})
- 저축률: {saving_rate:.1f}%
- 자기자본 현재 달성률: {equity_progress:.1f}% (목표 시점 예상: {projected_progress:.1f}%)
- 예산 초과 현황: {over_text}

[카테고리별 지출 비중 (익명화)]
{cat_lines}

[작성 지침]
1. ## 이달의 재무 서사
   3~5문장. 숫자를 해석해 이달의 재정 흐름을 서술하세요.
   - 잘한 점과 아쉬운 점을 균형 있게 언급하세요.
   - 목표 달성 속도(충분 / 주의 / 위험)를 판단해 포함하세요.
   - 추상적 표현 금지. 숫자 근거를 제시하세요.

2. ## 다음 달 액션 아이템
   구체적 행동 3가지. 각 항목은 한 문장으로.
   - 반드시 구체적 수치나 행동을 포함하세요 ("아끼세요" 수준 금지).
   - 예: "외식/음료 예산을 X만원으로 고정하고 배달앱 주 2회로 제한"

마크다운 형식으로 작성하세요."""


if st.button("🤖 AI 재무 서사 생성", type="primary", use_container_width=True):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY 환경변수가 설정되지 않았습니다. `.env` 파일을 확인하세요.")
    else:
        client = genai.Client(api_key=api_key)
        
        with st.spinner("Gemini가 이달의 재무 서사를 작성 중입니다..."):
            try:
                response = client.models.generate_content(
                    model=GEMINI_MODEL_VER,
                    contents=_build_gemini_prompt(),
                )
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Gemini API 오류: {e}")

st.divider()


# ─────────────────────────────────────────────────────────────────
# Section C — 월간 체크리스트
# ─────────────────────────────────────────────────────────────────

st.header("Section C — 월간 체크리스트")
st.caption("DB 데이터로 자동 판정 가능한 항목은 자동 체크됩니다.")


def _row(ok: bool | None, label_ok: str, label_fail: str, auto: bool = True) -> None:
    if ok is None:
        st.markdown(f"⬜ **{label_ok}** `수동`")
        return
    icon  = "✅" if ok else "⚠️"
    label = label_ok if ok else label_fail
    badge = "`자동`" if auto else "`수동`"
    st.markdown(f"{icon} **{label}** {badge}")


# 판정값 계산
has_expense    = not df.empty
saving_ok      = actual_saving >= saving_target

if budgets_df.empty:
    no_over_budget = None
else:
    spent_by_cat_c = df.groupby("category")["amount"].sum()
    no_over_budget = all(
        int(spent_by_cat_c.get(row["category"], 0)) <= int(row["amount"])
        for _, row in budgets_df.iterrows()
    )

# 자기자본 진행 속도: 목표 시점까지 선형으로 쌓아야 할 기준 달성률과 비교
_start_str   = get_setting("profile_completed_at") or \
               f"{_s('goal_date_year', TARGET_DATE_YEAR) - 3}-01"  # fallback: 목표 3년 전
_sy, _sm     = int(_start_str[:4]), int(_start_str[5:7])
_gy          = _s("goal_date_year",  TARGET_DATE_YEAR)
_gm          = _s("goal_date_month", TARGET_DATE_MONTH)
total_months = max((_gy - _sy) * 12 + (_gm - _sm), 1)

elapsed_share = (total_months - months_rem) / total_months if total_months > 0 else 1
expected_progress = elapsed_share * 100
equity_on_track = equity_progress >= expected_progress * 0.9  # 10% 여유 허용


st.markdown("**📊 현금흐름**")
_row(has_expense, "이달 지출 기록 완료", "이달 지출 미입력 — 가계부를 업데이트하세요")
_row(saving_ok,   "월 저축 목표 달성",   f"저축 목표 미달 — {abs(saving_delta):,}원 부족")

st.markdown("**🏠 주택 자금**")
_row(equity_on_track, "자기자본 목표 속도 유지 중",  "자기자본 적립 속도 점검 필요 — cashflow 시뮬레이터 확인")
_row(no_over_budget,  "모든 카테고리 예산 준수",     "예산 초과 카테고리 있음 — Section A 참고")

st.markdown("**💼 은퇴 자산 / 청약 (수동 확인)**")
st.checkbox("DC 퇴직연금 수익률 점검 (vs 코스피/글로벌 ETF) `수동`",  key="chk_dc")
st.checkbox("IRP 추가 납입 여부 확인 `수동`",                          key="chk_irp")
st.checkbox("청약 분양 일정 점검 (분기 1회 이상) `수동`",              key="chk_subscription")
st.checkbox("소득 변화(육아휴직·이직) 대응 필요 여부 `수동`",          key="chk_income")