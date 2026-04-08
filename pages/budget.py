# pages/budget.py
# AI Ledger — 맞춤형 예산 설계 & AI 진단 (v2.1)
# -------------------------------------------------------
# 변경 사항 (v2.1):
#   1. [Tab1] "이 기준으로 예산 자동 세팅" → user_total_budget 연동 (session_state)
#   2. [Tab1] 경고 메시지 컬럼 정렬 수정 (전체 너비 단일 컬럼으로 변경)
#   3. [Tab1/Tab3] 모든 표 Sort Ascending(카테고리명 오름차순) 통일
#   4. [Tab2] 중복 시각화 제거 → 예산 대비 실지출 % 단일 바 차트로 통합
#   5. [Tab3] Gemini SDK ImportError 디버깅 — 신구 SDK 모두 지원
# -------------------------------------------------------

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# Import 상수 
from database import (
    load_data, save_budget, get_budgets, delete_budget,
    get_available_months, save_setting, get_setting,
    clear_all_budgets, get_categories,
)

def _s(key, default):
    return type(default)(get_setting(key) or default)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import (
    DEFAULT_CATEGORIES,
    INCOME_DECILES_BUDGET,
    MEDIAN_INCOME_3PERSON,
    GEMINI_MODEL_VER,
    VARIABLE_BUDGET_LIMIT,
    get_decile_summary,
)
from database import (
    load_data,
    save_budget,
    get_budgets,
    delete_budget,
    get_available_months,
    save_setting,
    get_setting,
    clear_all_budgets,   # ★ 예산 전체 초기화
    get_categories,      # ★ 유효 카테고리 목록 (재정규화용)
)


# ── Gemini SDK: 신구 버전 모두 지원 ──────────────────
# google-generativeai (구) : import google.generativeai as genai
# google-genai       (신) : from google import genai
GEMINI_AVAILABLE  = False
GEMINI_SDK_NEW    = False   # True → 신규 SDK 사용

try:
    # 신규 SDK 우선 시도 (pip install google-genai)
    from google import genai as _genai_new   # noqa: F401
    GEMINI_AVAILABLE = True
    GEMINI_SDK_NEW   = True
except ImportError:
    pass

if not GEMINI_AVAILABLE:
    try:
        # 구 SDK 폴백 (pip install google-generativeai)
        import google.generativeai as genai   # noqa: F401
        GEMINI_AVAILABLE = True
        GEMINI_SDK_NEW   = False
    except ImportError:
        pass

# ══════════════════════════════════════════════════════
# ▌ 3인 가구 육아 특성 반영 예산 배분 비중
#   (통계청 소득 분위 비중을 베이스로,
#    문화/교육 ↑ 생활소비 ↑ 의료/미용 ↓ 로 조정)
# ══════════════════════════════════════════════════════

TARGET_EQUITY          = _s("goal_equity",          TARGET_EQUITY)
TARGET_PURCHASE_PRICE  = _s("goal_purchase_price",  TARGET_PURCHASE_PRICE)
RETIREMENT_YEAR        = _s("goal_retirement_year", RETIREMENT_YEAR)

FAMILY_WEIGHTS = {
    # --- 필수소비 (Needs) ---
    "공과금/주거":   0.08,   # 고정 비용
    "교통비":        0.06,
    "의료/미용":     0.05,   # 아이 병원 포함, 비중은 낮게 유지
    # --- 선택소비 (Wants) ---
    "문화/교육":     0.20,   # ★ 육아·자기계발 비중 상향
    "생활소비":      0.20,   # ★ 식자재·생필품 비중 상향
    "외식/음료/간식": 0.13,
    "내구소비":      0.08,
    "경조/교제비":   0.06,
    "쇼핑":          0.05,
    "여행":          0.04,
    "기타":          0.05,
}
# 합계 = 1.00 (검증: sum = 1.00)


# ══════════════════════════════════════════════════════
# ▌ 기회비용 계산 헬퍼 함수
# ══════════════════════════════════════════════════════

def months_until(target_year: int, target_month: int) -> int:
    """오늘 기준으로 목표 시점까지의 잔여 개월 수를 반환합니다."""
    now = datetime.now()
    months = (target_year - now.year) * 12 + (target_month - now.month)
    return max(months, 1)


def future_value_lump_sum(pv: float, annual_rate: float, months: int) -> float:
    """
    일시금의 미래가치를 계산합니다.

    FV = PV × (1 + r/12)^n

    - PV  : 현재가치 (초과 지출액)
    - r   : 연 수익률 (소수, e.g. 0.06)
    - n   : 기간 (개월 수)
    - 월복리(monthly compounding) 가정:
        월 이자율 = r / 12
        n개월 후 복리 계수 = (1 + r/12)^n
    """
    monthly_rate = annual_rate / 12
    return pv * ((1 + monthly_rate) ** months)


def pyeong_lost(amount: float, price_per_pyeong: float) -> float:
    """금액이 평당 단가 기준으로 몇 평에 해당하는지 반환합니다."""
    return amount / price_per_pyeong


# ══════════════════════════════════════════════════════
# ▌ 페이지 레이아웃
# ══════════════════════════════════════════════════════

st.set_page_config(
    page_title="예산 관리 & AI 진단",
    page_icon="💰",
    layout="wide",
)

# ── 사이드바 ──────────────────────────────────────────
with st.sidebar:
    st.header("🔍 예산 검토 설정")
    available_months = get_available_months()
    current_month_str = datetime.now().strftime("%Y-%m")
    if current_month_str not in available_months:
        available_months.insert(0, current_month_str)
    selected_month = st.selectbox("📅 조회할 월 선택", available_months)
    st.divider()

    # ── 현재 설정 예산 요약 ───────────────────────────
    _sb_budgets = get_budgets()
    if _sb_budgets.empty:
        st.warning("⚠️ 설정된 예산이 없습니다.")
    else:
        _sb_total = int(_sb_budgets["amount"].sum())
        _sb_gap   = _sb_total - VARIABLE_BUDGET_LIMIT
        st.markdown("**📌 현재 설정 예산**")
        st.metric(
            label="카테고리 합계",
            value=f"{_sb_total:,}원",
            delta=f"{_sb_gap:+,}원 (목표 대비)",
            delta_color="inverse",
        )
        with st.expander("카테고리별 보기"):
            for _, r in _sb_budgets.sort_values("category").iterrows():
                st.caption(f"{r['category']}: **{int(r['amount']):,}원**")

    st.divider()
    st.info(
        "💡 설정하신 예산 기준은 모든 달에 공통으로 "
        "적용되는 '월간 목표'입니다."
    )

st.title("💰 맞춤형 예산 설계 & AI 진단")
st.caption(
    f"소득 분위에 맞춰 예산을 설정하고, "
    f"**{selected_month}**의 소비 현황을 AI에게 점검받아 보세요."
)

# ── 데이터 로드 ───────────────────────────────────────
expenses_df = load_data(selected_month)
budgets_df  = get_budgets()

if not expenses_df.empty:
    spent_by_cat = expenses_df.groupby("category")["amount"].sum()
    total_spent  = int(expenses_df["amount"].sum())
else:
    spent_by_cat = pd.Series(dtype=int)
    total_spent  = 0

tab1, tab2, tab3 = st.tabs(
    ["🎯 예산 추천 및 설정", "📊 소비 성향별 현황", "🤖 AI 예산 진단"]
)


# ══════════════════════════════════════════════════════
# ▌ TAB 1 — 예산 추천 및 설정
# ══════════════════════════════════════════════════════
with tab1:
    st.markdown("#### 🏛️ 3인 가구(자녀 1명) 기준 연도별 예산 추천")

    # 연도·분위 선택
    available_years = sorted(list(INCOME_DECILES_BUDGET.keys()), reverse=True)
    current_year    = datetime.now().year
    saved_year_str  = get_setting("budget_year", str(current_year))
    saved_year      = int(saved_year_str) if saved_year_str.isdigit() else current_year
    default_year_idx = (
        available_years.index(saved_year) if saved_year in available_years else 0
    )

    col_year, col_info = st.columns([1, 3])
    with col_year:
        selected_year = st.selectbox(
            "📅 통계 기준 연도", available_years, index=default_year_idx
        )
        if selected_year != saved_year:
            save_setting("budget_year", selected_year)

    current_median  = MEDIAN_INCOME_3PERSON.get(selected_year, 0)
    current_budgets = INCOME_DECILES_BUDGET.get(selected_year, {})
    quintile_list   = list(current_budgets.keys())

    with col_info:
        st.write("")
        st.info(
            f"💡 **참고:** {selected_year}년 보건복지부 고시 3인 가구 "
            f"기준중위소득은 **월 {current_median:,}원** 입니다."
        )

    col_q, col_btn = st.columns([3, 1])
    with col_q:
        saved_quintile  = get_setting("budget_quintile")
        default_q_idx   = (
            quintile_list.index(saved_quintile)
            if saved_quintile in quintile_list
            else min(4, len(quintile_list) - 1)
        )
        selected_quintile = st.selectbox(
            "우리 가족과 가장 가까운 소득 구간을 선택하세요",
            quintile_list,
            index=default_q_idx,
        )
        if selected_quintile != saved_quintile:
            save_setting("budget_quintile", selected_quintile)

        total_rec, needs_rec, wants_rec = get_decile_summary(
            selected_year, selected_quintile
        )

        with st.container(border=True):
            st.markdown(f"#### 🎯 추천 총 예산: :red[{total_rec:,}원]")
            mc1, mc2 = st.columns(2)
            mc1.metric("🛡️ 필수소비 (Needs)", f"{needs_rec:,}원")
            mc2.metric("🛒 선택소비 (Wants)", f"{wants_rec:,}원")

    with col_btn:
        st.write("")
        st.write("")
        st.write("")
        if st.button("✨ 이 기준으로 예산 자동 세팅", use_container_width=True):
            clear_all_budgets()   # ★ 고아 레코드 방지: 전체 초기화 후 덮어쓰기
            for cat, amt in current_budgets[selected_quintile].items():
                save_budget(cat, amt)
            # ★ total_rec 을 아래 섹션의 number_input 초기값으로 연동
            st.session_state["user_total_budget"] = total_rec
            st.toast(
                f"✅ {selected_year}년 기준 맞춤 추천 예산이 적용되었습니다!"
            )
            st.rerun()

    st.divider()

    # ── ★ 총 예산 입력 + 카테고리별 추천 배분 ─────────
    st.markdown("#### 🏠 내 집 마련 목표 기반 — 총 예산 직접 설정")
    st.caption(
        "아래에 실현 가능한 월 변동지출 총 예산을 입력하면, "
        "육아 가구 특성을 반영한 카테고리별 추천 금액을 자동으로 계산합니다."
    )

    with st.container(border=True):
        # ★ session_state 에 값이 있으면 그 값을 초기값으로 사용 (자동세팅 버튼 연동)
        default_budget = st.session_state.get(
            "user_total_budget", VARIABLE_BUDGET_LIMIT
        )

        user_total_budget = st.number_input(
            "💴 월 변동지출 목표 예산 (원)",
            min_value=500_000,
            max_value=10_000_000,
            value=int(default_budget),
            step=50_000,
            format="%d",
            help=(
                "로드맵 기준 월 저축액 325만 원을 지키려면 "
                "변동지출은 350만 원 이하로 유지해야 합니다. "
                "'이 기준으로 예산 자동 세팅' 버튼을 누르면 소득 분위 추천값으로 자동 변경됩니다."
            ),
        )
        # 입력값을 session_state 에 다시 동기화
        st.session_state["user_total_budget"] = user_total_budget

        # ★ 경고 메시지: number_input 아래 전체 너비로 표시 (컬럼 분리 제거)
        gap = user_total_budget - VARIABLE_BUDGET_LIMIT
        if gap > 0:
            st.warning(
                f"⚠️ 목표(350만 원) 대비 **+{gap:,}원** 초과 설정입니다. "
                f"월 저축 목표 325만 원이 위협받을 수 있어요."
            )
        elif gap < 0:
            st.success(
                f"✅ 목표보다 **{abs(gap):,}원** 여유 있게 설정했습니다. "
                f"초과분을 투자 계좌로 이체하면 어떨까요?"
            )
        else:
            st.info("🎯 로드맵 목표 예산과 정확히 일치합니다!")

        # ★ 유효 카테고리 교집합 + 비중 재정규화
        # categories 테이블 기준으로 필터링 → 카테고리 추가/삭제에도 합계 보장
        active_cats     = set(get_categories())
        valid_weights   = {c: w for c, w in FAMILY_WEIGHTS.items() if c in active_cats}
        total_w         = sum(valid_weights.values()) or 1   # 0 나누기 방지
        norm_weights    = {c: w / total_w for c, w in valid_weights.items()}

        rec_data = []
        for cat, weight in norm_weights.items():
            rec_amt = int(user_total_budget * weight)
            spent   = int(spent_by_cat.get(cat, 0))
            diff    = rec_amt - spent
            diff_str = (
                f"▲ {diff:,}원 여유" if diff >= 0 else f"▼ {abs(diff):,}원 초과"
            )
            rec_data.append(
                {
                    "카테고리":       cat,
                    "배분 비중":      f"{weight*100:.0f}%",
                    "추천 금액 (원)": rec_amt,
                    f"{selected_month} 실지출": spent,
                    "여유/초과":      diff_str,
                }
            )

        rec_df = pd.DataFrame(rec_data).sort_values("카테고리").reset_index(drop=True)
        st.markdown("##### 📋 육아 가구 맞춤 카테고리별 추천 예산")
        st.caption(
            "🍼 **문화/교육 20%, 생활소비 20%** 비중을 전략적으로 상향 설정했습니다. "
            "(영아 돌봄·식자재·생필품 특성 반영)"
        )
        st.dataframe(
            rec_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "추천 금액 (원)": st.column_config.NumberColumn(format="%d원"),
                f"{selected_month} 실지출": st.column_config.NumberColumn(format="%d원"),
            },
        )

        if st.button(
            "💾 위 추천 예산을 내 예산으로 저장", type="primary", use_container_width=True
        ):
            clear_all_budgets()   # ★ 고아 레코드 방지
            for row in rec_data:
                save_budget(row["카테고리"], row["추천 금액 (원)"])
            st.success("✅ 추천 예산이 저장되었습니다. [소비 성향별 현황] 탭에서 확인하세요.")
            st.rerun()

    st.divider()

    # ── 세부 예산 직접 조정 ────────────────────────────────
    st.markdown("#### ✏️ 세부 예산 직접 조정")
    st.caption(
        "추천받은 예산을 우리 집 상황에 맞게 더블 클릭하여 직접 수정해 보세요."
    )

    flat_cats, types = [], []
    for cat_type, cats in DEFAULT_CATEGORIES.items():
        for c in cats:
            flat_cats.append(c)
            types.append(cat_type)

    base_budget_df = pd.DataFrame({"category": flat_cats, "소비성향": types})
    if not budgets_df.empty:
        base_budget_df = base_budget_df.merge(
            budgets_df, on="category", how="left"
        ).fillna(0)
    else:
        base_budget_df["amount"] = 0

    base_budget_df["amount"] = base_budget_df["amount"].astype(int)
    # ★ 카테고리명 오름차순 정렬
    base_budget_df = base_budget_df.sort_values("category").reset_index(drop=True)

    edited_df = st.data_editor(
        base_budget_df,
        column_config={
            "소비성향": st.column_config.TextColumn("소비 성향", disabled=True),
            "category": st.column_config.TextColumn("카테고리", disabled=True),
            "amount": st.column_config.NumberColumn(
                "월 목표 예산 (원)", format="%d원", step=10000, min_value=0
            ),
        },
        hide_index=True,
        use_container_width=True,
        key="budget_bulk_editor",
    )

    if st.button("💾 수정한 예산 저장하기", type="primary"):
        for _, row in edited_df.iterrows():
            if row["amount"] > 0:
                save_budget(row["category"], row["amount"])
            else:
                delete_budget(row["category"])
        st.success("예산이 성공적으로 업데이트되었습니다.")
        st.rerun()


# ══════════════════════════════════════════════════════
# ▌ TAB 2 — 소비 성향별 현황
# ══════════════════════════════════════════════════════
with tab2:
    with st.container(border=True):
        st.markdown(
            f"**🔍 현재 기준:** {selected_year}년 "
            f"{selected_quintile.split('(')[0].strip()} "
            f"(기준중위소득: {current_median:,}원)"
        )
        st.markdown(
            f"**🎯 추천 예산:** 총 :red[{total_rec:,}원] "
            f"(🛡️ 필수소비 {needs_rec:,}원 | 🛒 선택소비 {wants_rec:,}원)"
        )

    if budgets_df.empty:
        st.info("👈 [예산 추천 및 설정] 탭에서 먼저 예산을 설정해 주세요.")
    else:
        # ── 데이터 준비 (카테고리 오름차순 정렬) ──────────
        display_df = budgets_df.copy()
        display_df["spent"]   = display_df["category"].map(spent_by_cat).fillna(0).astype(int)
        display_df["percent"] = (
            display_df["spent"] / display_df["amount"].replace(0, 1) * 100
        ).round(1)
        display_df = display_df.sort_values("category").reset_index(drop=True)

        # ── ★ 통합 시각화: 예산 100% 기준 실지출 퍼센트 바 ──
        st.markdown("#### 📊 카테고리별 예산 소진율 (예산 = 100%)")
        st.caption(
            "🟢 80% 미만 | 🟡 80~99% | 🔴 100% 이상(초과).  "
            "막대 끝의 점선이 예산 한도(100%)를 나타냅니다."
        )

        # HTML 커스텀 바 차트
        bar_html_rows = []
        for _, row in display_df.iterrows():
            pct    = float(row["percent"])
            budget = int(row["amount"])
            spent  = int(row["spent"])
            cat    = row["category"]

            # 색상 · 너비 결정 — 항상 max 100%, overflow 없음
            if pct >= 100:
                bar_w     = 100
                bar_color = "#ff4b4b"
                icon      = "🔴"
            elif pct >= 80:
                bar_w     = pct
                bar_color = "#ffa500"
                icon      = "🟡"
            else:
                bar_w     = pct
                bar_color = "#21c354"
                icon      = "🟢"

            label_pct = f"<b>{pct:.1f}%</b>" if pct >= 100 else f"{pct:.1f}%"

            bar_html_rows.append(f"""
<div style="margin-bottom:10px;">
  <div style="display:flex;align-items:center;margin-bottom:3px;">
    <span style="width:120px;font-size:13px;flex-shrink:0;">{icon} {cat}</span>
    <span style="font-size:12px;color:#888;margin-left:8px;">{spent:,}원 / {budget:,}원</span>
    <span style="margin-left:auto;font-size:13px;">{label_pct}</span>
  </div>
  <div style="background:#e0e0e0;border-radius:4px;height:18px;overflow:hidden;">
    <div style="width:{bar_w:.1f}%;height:18px;background:{bar_color};border-radius:4px;"></div>
  </div>
</div>
""")

        st.html("".join(bar_html_rows))


# ══════════════════════════════════════════════════════
# ▌ TAB 3 — AI 예산 진단 (★ 비주얼 쇼크 포함)
# ══════════════════════════════════════════════════════
with tab3:
    # ── 헤더 정보 ──────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            f"**🔍 현재 기준:** {selected_year}년 "
            f"{selected_quintile.split('(')[0].strip()} "
            f"(기준중위소득: {current_median:,}원)"
        )
        st.markdown(
            f"**🎯 추천 예산:** 총 :red[{total_rec:,}원] "
            f"(🛡️ 필수소비 {needs_rec:,}원 | 🛒 선택소비 {wants_rec:,}원)"
        )

    if budgets_df.empty:
        st.info("👈 [예산 추천 및 설정] 탭에서 먼저 예산을 설정해 주세요.")
    else:
        # ── ★ NEW: 비주얼 쇼크 섹션 ────────────────────────
        excess = total_spent - VARIABLE_BUDGET_LIMIT  # 초과액 계산

        st.markdown("---")
        st.markdown("## 💥 비주얼 쇼크 — 이 초과 지출의 진짜 대가")
        st.caption(
            f"**{selected_month}** 변동 지출 실적 "
            f"**{total_spent:,}원** vs 목표 **{VARIABLE_BUDGET_LIMIT:,}원** "
            f"| 연 수익률 **{ANNUAL_RETURN_RATE*100:.0f}%** 월복리 가정"
        )

        if excess <= 0:
            st.success(
                f"🎉 이번 달 변동 지출이 목표 예산 내에 있습니다! "
                f"({abs(excess):,}원 절약)"
            )
        else:
            # ── 기회비용 계산 ──────────────────────────────
            months_to_house = months_until(TARGET_DATE_YEAR, TARGET_DATE_MONTH)
            years_to_retire = RETIREMENT_YEAR - datetime.now().year
            months_to_retire = years_to_retire * 12

            fv_house   = future_value_lump_sum(excess, ANNUAL_RETURN_RATE, months_to_house)
            fv_retire  = future_value_lump_sum(excess, ANNUAL_RETURN_RATE, months_to_retire)
            pyeong_house  = pyeong_lost(fv_house,  PRICE_PER_PYEONG)
            pyeong_retire = pyeong_lost(fv_retire, PRICE_PER_PYEONG)

            # ── 경고 배너 ──────────────────────────────────
            st.error(
                f"🚨 이번 달 **{excess:,}원**이 목표를 초과했습니다.  \n"
                f"이 돈이 복리로 불어나면 아래와 같은 '사라진 미래 자산'이 됩니다."
            )

            # ── 메인 지표 카드 2개 ─────────────────────────
            col_house, col_retire = st.columns(2)

            with col_house:
                with st.container(border=True):
                    st.markdown(
                        f"### 🏠 2029년 2월  \n"
                        f"*(잔여 {months_to_house}개월 후)*"
                    )
                    st.metric(
                        label="사라진 미래 자산",
                        value=f"{fv_house:,.0f}원",
                        delta=f"+{fv_house - excess:,.0f}원 (복리 증식분)",
                        delta_color="inverse",
                    )
                    st.markdown(
                        f"**📐 아파트로 환산하면?**  \n"
                        f"평당 {PRICE_PER_PYEONG:,.0f}원 기준"
                    )
                    st.markdown(
                        f"### :red[{pyeong_house:.2f}평]이 사라집니다"
                    )
                    # 전체 목표 84㎡ 대비 손실 비율 시각화
                    loss_ratio_house = min(pyeong_house / TARGET_AREA_PYEONG, 1.0)
                    st.caption(
                        f"목표 주택({TARGET_AREA_PYEONG:.1f}평) 중 "
                        f"**{loss_ratio_house*100:.1f}%**에 해당"
                    )
                    st.progress(loss_ratio_house)

            with col_retire:
                with st.container(border=True):
                    st.markdown(
                        f"### 🌅 {RETIREMENT_YEAR}년 은퇴  \n"
                        f"*(약 {years_to_retire}년 후)*"
                    )
                    st.metric(
                        label="사라진 은퇴 자산",
                        value=f"{fv_retire:,.0f}원",
                        delta=f"+{fv_retire - excess:,.0f}원 (복리 증식분)",
                        delta_color="inverse",
                    )
                    st.markdown(
                        f"**📐 아파트로 환산하면?**  \n"
                        f"평당 {PRICE_PER_PYEONG:,.0f}원 기준"
                    )
                    st.markdown(
                        f"### :red[{pyeong_retire:.2f}평]이 사라집니다"
                    )
                    loss_ratio_retire = min(pyeong_retire / TARGET_AREA_PYEONG, 1.0)
                    st.caption(
                        f"목표 주택({TARGET_AREA_PYEONG:.1f}평) 중 "
                        f"**{loss_ratio_retire*100:.1f}%**에 해당"
                    )
                    st.progress(loss_ratio_retire)

            # ── 누적 충격 메시지 ────────────────────────────
            st.warning(
                f"💬 **만약 매달 {excess:,}원씩 초과 지출이 반복된다면?**  \n"
                f"12개월 기준 연간 초과액 **{excess * 12:,}원**이 2029년까지 "
                f"**{future_value_lump_sum(excess * 12, ANNUAL_RETURN_RATE, months_to_house):,.0f}원**으로 불어납니다."
            )

            # ── 간단한 절약 시뮬레이터 ──────────────────────
            st.markdown("---")
            st.markdown("#### 🧮 절약 시뮬레이터 — 내가 아낀다면?")
            st.caption("슬라이더를 움직여 절약 시나리오를 시뮬레이션하세요.")
            save_amount = st.slider(
                "매달 이만큼 더 아끼면...",
                min_value=10_000,
                max_value=min(excess, 1_000_000),
                value=min(excess // 2, 500_000),
                step=10_000,
                format="%d원",
            )
            sim_fv_house  = future_value_lump_sum(save_amount, ANNUAL_RETURN_RATE, months_to_house)
            sim_fv_retire = future_value_lump_sum(save_amount, ANNUAL_RETURN_RATE, months_to_retire)
            sc1, sc2 = st.columns(2)
            sc1.metric(
                f"2029년 2월 (+{months_to_house}개월)",
                f"{sim_fv_house:,.0f}원",
                f"절약 {save_amount:,}원의 미래가치",
            )
            sc2.metric(
                f"{RETIREMENT_YEAR}년 은퇴 (+{years_to_retire}년)",
                f"{sim_fv_retire:,.0f}원",
                f"절약 {save_amount:,}원의 미래가치",
            )

        st.markdown("---")

        # ── Gemini AI 진단 ──────────────────────────────
        st.markdown("## 🤖 Gemini AI 상세 진단")

        if budgets_df.empty or expenses_df.empty:
            st.info("예산과 지출 데이터가 모두 필요합니다.")
        else:
            display_df2 = budgets_df.copy()
            display_df2["spent"]     = display_df2["category"].map(spent_by_cat).fillna(0).astype(int)
            display_df2["remaining"] = display_df2["amount"] - display_df2["spent"]
            display_df2["percent"]   = (
                display_df2["spent"] / display_df2["amount"].replace(0, 1) * 100
            ).round(1)
            # ★ 카테고리 오름차순 정렬
            display_df2 = display_df2.sort_values("category").reset_index(drop=True)

            over_budget_df = display_df2[display_df2["remaining"] < 0].sort_values("remaining")

            # ── prompt 미리 조립 (버튼 안팎 모두 동일하게 사용) ──
            budget_summary = "\n".join(
                f"- {r['category']}: 예산 {r['amount']:,}원 / "
                f"지출 {r['spent']:,}원 ({r['percent']}%)"
                for _, r in display_df2.iterrows()
            )
            over_summary = (
                "\n".join(
                    f"- {r['category']}: {abs(r['remaining']):,}원 초과"
                    for _, r in over_budget_df.iterrows()
                )
                if not over_budget_df.empty
                else "없음"
            )
            prompt = f"""당신은 한국의 맞벌이 가정 재무 코치입니다. 아래 정보를 바탕으로 한국어로 진단해 주세요.

## 가구 프로필
- 3인 가족 (38세/35세 부부, 1세 자녀)
- 2029년 2월 목표: 서울·경기 상급지 84㎡ 아파트 자기자본 5억 확보 후 매수
- 월 변동지출 목표: {VARIABLE_BUDGET_LIMIT:,}원 / 이번 달 실지출: {total_spent:,}원
- 초과액: {excess:,}원

## {selected_month} 카테고리별 예산 현황
{budget_summary}

## 초과 카테고리
{over_summary}

## 요청 사항
1. 초과 원인을 2~3가지로 분석하세요.
2. 각 초과 카테고리에 대해 구체적이고 즉시 실행 가능한 절약 팁을 제안하세요.
3. 1세 영아 육아 가정이라는 특수성을 고려하여 현실적인 조언을 해주세요.
4. '이달의 재무 점수'를 100점 만점으로 매기고 이유를 설명하세요.
"""

            if not GEMINI_AVAILABLE:
                st.error(
                    "🔧 **Gemini 패키지를 찾을 수 없습니다.**  \n"
                    "터미널에서 아래 명령 중 하나를 실행한 뒤 앱을 재시작하세요.  \n\n"
                    "```bash\n"
                    "# 신규 SDK (권장)\n"
                    "pip install google-genai\n\n"
                    "# 또는 구 SDK\n"
                    "pip install google-generativeai\n"
                    "```"
                )
            else:
                api_key = get_setting("gemini_api_key", "")
                if not api_key:
                    api_key = st.text_input(
                        "🔑 Gemini API 키를 입력하세요",
                        type="password",
                        placeholder="AIza...",
                    )
                    if api_key:
                        save_setting("gemini_api_key", api_key)
                        st.rerun()

                if api_key and st.button("🚀 AI 진단 시작", type="primary", use_container_width=True):
                    with st.spinner("Gemini가 소비 패턴을 분석하고 있습니다..."):
                        try:
                            if GEMINI_SDK_NEW:
                                # 신규 SDK: google-genai
                                from google import genai as genai_new
                                client = genai_new.Client(api_key=api_key)
                                response = client.models.generate_content(
                                    model=GEMINI_MODEL_VER,
                                    contents=prompt,
                                )
                                result_text = response.text
                            else:
                                # 구 SDK: google-generativeai
                                import google.generativeai as genai_old
                                genai_old.configure(api_key=api_key)
                                model_obj = genai_old.GenerativeModel(GEMINI_MODEL_VER)
                                response  = model_obj.generate_content(prompt)
                                result_text = response.text

                            st.markdown(result_text)
                        except Exception as e:
                            st.error(
                                f"AI 진단 중 오류가 발생했습니다.  \n"
                                f"**오류 내용:** `{e}`  \n\n"
                                f"API 키가 올바른지, 또는 `GEMINI_MODEL_VER`(현재: `{GEMINI_MODEL_VER}`)이 "
                                f"유효한지 확인하세요."
                            )