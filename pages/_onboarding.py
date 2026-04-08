import streamlit as st
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import save_setting, get_setting

# ── 인라인 format_korean ──────────────────────────────────────
def format_korean(value: float) -> str:
    """숫자를 억/만 단위 한국어 표기로 변환"""
    if value == 0:
        return "0원"
    eok = int(value) // 100_000_000
    man = (int(value) % 100_000_000) // 10_000
    parts = []
    if eok:
        parts.append(f"{eok}억")
    if man:
        parts.append(f"{man:,}만")
    return " ".join(parts) + "원" if parts else "0원"

# ── 기본값 ───────────────────────────────────────────────────
ONBOARDING_KEYS = {
    "profile_name":           "홍길동 가족",
    "profile_age_main":       "38",
    "profile_age_spouse":     "35",
    "profile_children":       "1",
    "income_monthly":         "10800000",
    "asset_investment":       "50000000",
    "asset_subscription":     "25000000",
    "asset_jeonse_recovery":  "260000000",
    "goal_equity":            "500000000",
    "goal_purchase_price":    "825000000",
    "goal_date_year":         "2029",
    "goal_date_month":        "2",
    "goal_retirement_year":   "2048",
    "mortgage_rate":          "0.04",
    "mortgage_years":         "30",
    "profile_completed":      "0",
}

# ── 수정 모드 감지 ────────────────────────────────────────────
def _is_edit_mode() -> bool:
    completed = get_setting("profile_completed", "0")
    params = st.query_params
    return completed == "1" and params.get("edit", "") == "true"

# ── Step 1: 가족 구성 ─────────────────────────────────────────
def _step1():
    st.markdown("## 👨‍👩‍👧 Step 1 / 3 — 가족 구성")
    st.progress(33)

    with st.form("ob_step1"):
        name = st.text_input(
            "가족 이름",
            value=get_setting("profile_name", ONBOARDING_KEYS["profile_name"]),
        )
        age_main = st.number_input(
            "본인 나이", min_value=20, max_value=70,
            value=int(get_setting("profile_age_main", ONBOARDING_KEYS["profile_age_main"])),
        )
        age_spouse = st.number_input(
            "배우자 나이", min_value=20, max_value=70,
            value=int(get_setting("profile_age_spouse", ONBOARDING_KEYS["profile_age_spouse"])),
        )
        children = st.number_input(
            "자녀 수", min_value=0, max_value=5,
            value=int(get_setting("profile_children", ONBOARDING_KEYS["profile_children"])),
        )
        submitted = st.form_submit_button("다음 →", use_container_width=True)

    if submitted:
        save_setting("profile_name", str(name))
        save_setting("profile_age_main", str(int(age_main)))
        save_setting("profile_age_spouse", str(int(age_spouse)))
        save_setting("profile_children", str(int(children)))
        st.session_state["ob_step"] = 2
        st.rerun()


# ── Step 2: 현재 자산 ─────────────────────────────────────────
def _step2():
    st.markdown("## 💰 Step 2 / 3 — 현재 자산")
    st.progress(66)

    income = st.number_input(
        "월 소득 (원)", min_value=0, max_value=100_000_000, step=100_000,
        value=int(get_setting("income_monthly", ONBOARDING_KEYS["income_monthly"])),
    )
    st.caption(f"→ {format_korean(income)}")

    investment = st.number_input(
        "현재 투자금 (원)", min_value=0, max_value=1_000_000_000, step=1_000_000,
        value=int(get_setting("asset_investment", ONBOARDING_KEYS["asset_investment"])),
    )
    st.caption(f"→ {format_korean(investment)}")

    subscription = st.number_input(
        "청약 저축 (원)", min_value=0, max_value=100_000_000, step=100_000,
        value=int(get_setting("asset_subscription", ONBOARDING_KEYS["asset_subscription"])),
    )
    st.caption(f"→ {format_korean(subscription)}")

    jeonse = st.number_input(
        "전세 보증금 회수 예정액 (원)", min_value=0, max_value=2_000_000_000, step=1_000_000,
        value=int(get_setting("asset_jeonse_recovery", ONBOARDING_KEYS["asset_jeonse_recovery"])),
    )
    st.caption(f"→ {format_korean(jeonse)}")

    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("← 이전", use_container_width=True):
            st.session_state["ob_step"] = 1
            st.rerun()
    with col_next:
        if st.button("다음 →", type="primary", use_container_width=True):
            save_setting("income_monthly",        str(int(income)))
            save_setting("asset_investment",      str(int(investment)))
            save_setting("asset_subscription",    str(int(subscription)))
            save_setting("asset_jeonse_recovery", str(int(jeonse)))
            st.session_state["ob_step"] = 3
            st.rerun()


# ── Step 3: 재정 목표 ─────────────────────────────────────────
def _step3():
    st.markdown("## 🎯 Step 3 / 3 — 재정 목표")
    st.progress(100)

    goal_equity = st.number_input(
        "목표 자기자본 (원)", min_value=0, max_value=2_000_000_000, step=10_000_000,
        value=int(get_setting("goal_equity", ONBOARDING_KEYS["goal_equity"])),
    )
    st.caption(f"→ {format_korean(goal_equity)}")

    goal_price = st.number_input(
        "목표 매수가 (원)", min_value=0, max_value=3_000_000_000, step=10_000_000,
        value=int(get_setting("goal_purchase_price", ONBOARDING_KEYS["goal_purchase_price"])),
    )
    st.caption(f"→ {format_korean(goal_price)}")

    g1, g2 = st.columns(2)
    with g1:
        goal_year = st.number_input(
            "목표 매수 연도", min_value=2025, max_value=2035,
            value=int(get_setting("goal_date_year", ONBOARDING_KEYS["goal_date_year"])),
        )
    with g2:
        goal_month = st.number_input(
            "목표 매수 월", min_value=1, max_value=12,
            value=int(get_setting("goal_date_month", ONBOARDING_KEYS["goal_date_month"])),
        )

    retire_year = st.number_input(
        "은퇴 목표 연도", min_value=2040, max_value=2060,
        value=int(get_setting("goal_retirement_year", ONBOARDING_KEYS["goal_retirement_year"])),
    )

    mortgage_rate = st.slider(
        "주담대 금리 (%)", min_value=2.0, max_value=7.0, step=0.1,
        value=float(get_setting("mortgage_rate", ONBOARDING_KEYS["mortgage_rate"])) * 100,
    )
    st.caption(f"→ 연 {mortgage_rate:.1f}% / 월 {mortgage_rate/12:.3f}%")

    mortgage_years = st.selectbox(
        "대출 기간 (년)", options=[5, 10, 15, 20, 25, 30, 35, 40],
        index=[5, 10, 15, 20, 25, 30, 35, 40].index(
            int(get_setting("mortgage_years", ONBOARDING_KEYS["mortgage_years"]))
        ),
    )

    col_prev, col_done = st.columns(2)
    with col_prev:
        if st.button("← 이전", use_container_width=True):
            st.session_state["ob_step"] = 2
            st.rerun()
    with col_done:
        if st.button("✅ 완료", type="primary", use_container_width=True):
            save_setting("goal_equity",          str(int(goal_equity)))
            save_setting("goal_purchase_price",  str(int(goal_price)))
            save_setting("goal_date_year",       str(int(goal_year)))
            save_setting("goal_date_month",      str(int(goal_month)))
            save_setting("goal_retirement_year", str(int(retire_year)))
            save_setting("mortgage_rate",        str(round(mortgage_rate / 100, 4)))
            save_setting("mortgage_years",       str(int(mortgage_years)))
            save_setting("profile_completed",    "1")
            st.session_state["ob_step"] = "done"
            st.rerun()


# ── Step done: 완료 화면 ──────────────────────────────────────
def _step_done():
    st.balloons()
    st.success("설정 완료! 이제 모든 페이지에 내 정보가 자동 반영됩니다.")
    if st.button("📊 대시보드로 이동", type="primary", use_container_width=True):
        st.switch_page("pages/cashflow.py")

# ── 수정 모드 ─────────────────────────────────────────────────
def show_edit_mode():
    st.markdown("# ✏️ 프로필 수정")
    st.caption("각 항목을 펼쳐 수정한 뒤 저장하세요.")

    # ── Expander 1: 가족 구성 ──
    with st.expander("👨‍👩‍👧 가족 구성", expanded=False):
        with st.form("ob_edit_step1"):
            name = st.text_input("가족 이름",
                value=get_setting("profile_name", ONBOARDING_KEYS["profile_name"]))
            age_main = st.number_input("본인 나이", 20, 70,
                value=int(get_setting("profile_age_main", ONBOARDING_KEYS["profile_age_main"])))
            age_spouse = st.number_input("배우자 나이", 20, 70,
                value=int(get_setting("profile_age_spouse", ONBOARDING_KEYS["profile_age_spouse"])))
            children = st.number_input("자녀 수", 0, 5,
                value=int(get_setting("profile_children", ONBOARDING_KEYS["profile_children"])))
            if st.form_submit_button("저장", use_container_width=True):
                save_setting("profile_name", str(name))
                save_setting("profile_age_main", str(int(age_main)))
                save_setting("profile_age_spouse", str(int(age_spouse)))
                save_setting("profile_children", str(int(children)))
                st.success("가족 구성 저장 완료")

    # ── Expander 2: 현재 자산 ──
    with st.expander("💰 현재 자산", expanded=False):
        with st.form("ob_edit_step2"):
            income = st.number_input("월 소득 (원)", 0, 100_000_000, step=100_000,
                value=int(get_setting("income_monthly", ONBOARDING_KEYS["income_monthly"])))
            st.caption(f"→ {format_korean(income)}")
            investment = st.number_input("현재 투자금 (원)", 0, 1_000_000_000, step=1_000_000,
                value=int(get_setting("asset_investment", ONBOARDING_KEYS["asset_investment"])))
            st.caption(f"→ {format_korean(investment)}")
            subscription = st.number_input("청약 저축 (원)", 0, 100_000_000, step=100_000,
                value=int(get_setting("asset_subscription", ONBOARDING_KEYS["asset_subscription"])))
            st.caption(f"→ {format_korean(subscription)}")
            jeonse = st.number_input("전세 보증금 회수 예정액 (원)", 0, 2_000_000_000, step=1_000_000,
                value=int(get_setting("asset_jeonse_recovery", ONBOARDING_KEYS["asset_jeonse_recovery"])))
            st.caption(f"→ {format_korean(jeonse)}")
            if st.form_submit_button("저장", use_container_width=True):
                save_setting("income_monthly", str(int(income)))
                save_setting("asset_investment", str(int(investment)))
                save_setting("asset_subscription", str(int(subscription)))
                save_setting("asset_jeonse_recovery", str(int(jeonse)))
                st.success("자산 정보 저장 완료")

    # ── Expander 3: 재정 목표 ──
    with st.expander("🎯 재정 목표", expanded=False):
        with st.form("ob_edit_step3"):
            goal_equity = st.number_input("목표 자기자본 (원)", 0, 2_000_000_000, step=10_000_000,
                value=int(get_setting("goal_equity", ONBOARDING_KEYS["goal_equity"])))
            st.caption(f"→ {format_korean(goal_equity)}")
            goal_price = st.number_input("목표 매수가 (원)", 0, 3_000_000_000, step=10_000_000,
                value=int(get_setting("goal_purchase_price", ONBOARDING_KEYS["goal_purchase_price"])))
            st.caption(f"→ {format_korean(goal_price)}")
            g1, g2 = st.columns(2)
            with g1:
                goal_year = st.number_input("목표 매수 연도", 2027, 2032,
                    value=int(get_setting("goal_date_year", ONBOARDING_KEYS["goal_date_year"])))
            with g2:
                goal_month = st.number_input("목표 매수 월", 1, 12,
                    value=int(get_setting("goal_date_month", ONBOARDING_KEYS["goal_date_month"])))
            retire_year = st.number_input("은퇴 목표 연도", 2040, 2060,
                value=int(get_setting("goal_retirement_year", ONBOARDING_KEYS["goal_retirement_year"])))
            mortgage_rate = st.slider("주담대 금리 (%)", 2.0, 7.0, step=0.1,
                value=float(get_setting("mortgage_rate", ONBOARDING_KEYS["mortgage_rate"])) * 100)
            mortgage_years = st.selectbox("대출 기간 (년)", [20, 25, 30],
                index=[20, 25, 30].index(
                    int(get_setting("mortgage_years", ONBOARDING_KEYS["mortgage_years"]))
                ))
            if st.form_submit_button("저장", use_container_width=True):
                save_setting("goal_equity", str(int(goal_equity)))
                save_setting("goal_purchase_price", str(int(goal_price)))
                save_setting("goal_date_year", str(int(goal_year)))
                save_setting("goal_date_month", str(int(goal_month)))
                save_setting("goal_retirement_year", str(int(retire_year)))
                save_setting("mortgage_rate", str(round(mortgage_rate / 100, 4)))
                save_setting("mortgage_years", str(int(mortgage_years)))
                st.success("재정 목표 저장 완료")

# ── 메인 라우터 ───────────────────────────────────────────────
st.set_page_config(page_title="온보딩", page_icon="🏁", layout="centered")

if _is_edit_mode():
    show_edit_mode()
else:
    # session_state 초기화
    if "ob_step" not in st.session_state:
        # 이미 완료된 경우 done으로 바로 진입하지 않고 wizard 진입 허용
        st.session_state["ob_step"] = 1

    step = st.session_state["ob_step"]

    if step == 1:
        _step1()
    elif step == 2:
        _step2()
    elif step == 3:
        _step3()
    elif step == "done":
        _step_done()
    else:
        st.session_state["ob_step"] = 1
        st.rerun()


# git add pages/onboarding.py
# git commit -m "feat: 3단계 온보딩 wizard + 수정 모드 구현 (onboarding.py)"
