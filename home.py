import streamlit as st
from google import genai
import os
from PIL import Image
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from database import init_db, insert_expense, load_data, get_budgets, get_categories, get_last_entry_date, get_setting, cleanup_old_income_settings
from config import get_ledger_status_message

# [수정] google.api_core 의존성을 제거하고, tenacity만 사용합니다.
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

st.set_page_config(page_title="AI 가계부 - 홈", page_icon="🏠")

# ── 모듈 레벨: Gemini 클라이언트 초기화 (모든 페이지 로드 시 1회 실행) ──
_api_error: str | None = None
client = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        _api_key = st.secrets["GEMINI_API_KEY"]
    else:
        _api_key = os.getenv("GEMINI_API_KEY")

    if not _api_key:
        _api_error = "⚠️ API 키가 없습니다. GEMINI_API_KEY를 설정해주세요."
    else:
        client = genai.Client(api_key=_api_key)
except Exception as _e:
    _api_error = f"⚠️ Gemini 설정 오류: {_e}"

default_model_name = "gemini-2.5-flash"


def is_rate_limit_error(exception):
    msg = str(exception)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


@retry(
    retry=retry_if_exception(is_rate_limit_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True,
)
def generate_content_with_retry(model, contents):
    return client.models.generate_content(model=model, contents=contents)


# ── 홈 페이지 본문 함수 ────────────────────────────────────────
def home_page():
    # API 오류 시 조기 반환
    if _api_error:
        st.error(_api_error)
        return

    # ── 온보딩 완료 여부 체크 ──────────────────────────────────────
    if get_setting("profile_completed") != "1":
        st.warning(
            "⚙️ 프로필 설정을 완료해야 정확한 시뮬레이션이 가능합니다.",
            icon="⚠️",
        )
        if st.button("설정하기 →", type="primary"):
            st.switch_page("pages/_onboarding.py")
        st.divider()

    # --- 2. 상단 요약 (HUD) ---
    st.title("🏠 나의 자산 현황")
    today = datetime.now()
    current_month_str = today.strftime("%Y-%m")
    today_str = today.strftime("%Y-%m-%d")

    # DB에서 카테고리 목록 가져오기
    CATEGORIES = get_categories()
    if not CATEGORIES:
        CATEGORIES = ["미분류"]

    # 데이터 로드
    month_df = load_data(current_month_str)
    budget_df = get_budgets()

    total_spent_month = month_df["amount"].sum() if not month_df.empty else 0
    total_budget = budget_df["amount"].sum() if not budget_df.empty else 0

    if not month_df.empty:
        today_spent = month_df[month_df["date"].str.startswith(today_str)]["amount"].sum()
    else:
        today_spent = 0

    col1, col2, col3 = st.columns(3)
    col1.metric("📅 이번 달 지출", f"{total_spent_month:,}원")
    remaining = total_budget - total_spent_month
    col2.metric("💰 남은 예산", f"{remaining:,}원", delta=remaining)
    col3.metric("🔥 오늘 쓴 돈", f"{today_spent:,}원")

    st.divider()

    # --- 3. 입력 UI ---
    st.subheader("📝 새 내역 기록")

    last_date = get_last_entry_date()
    status_msg, msg_type = get_ledger_status_message(last_date)
    if msg_type == "info":
        st.info(status_msg)
    elif msg_type == "warning":
        st.warning(status_msg)
    else:
        st.error(status_msg)

    st.caption("💡 팁: 여러 건을 한 번에 입력해도 됩니다. (예: 점심 9000원, 커피 4500원)")

    input_type = st.radio(
        "입력 방식", ["텍스트", "이미지 캡처"], horizontal=True, label_visibility="collapsed"
    )

    with st.form("expense_form", clear_on_submit=False):
        st.write("👤 **누가 썼나요?**")
        spender = st.radio(
            "지출 주체", ["공동", "남편", "아내", "아이"], horizontal=True, label_visibility="collapsed"
        )

        st.write("---")

        user_content = None
        content_type = None
        if input_type == "텍스트":
            user_content = st.text_area(
                "내용 입력",
                height=100,
                placeholder="예: 오늘 점심 순대국 9000원\n저녁 마트 장보기 54000원",
            )
            content_type = "text"
        else:
            uploaded_file = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"])
            if uploaded_file:
                user_content = Image.open(uploaded_file)
                content_type = "image"
                st.image(user_content, caption="업로드된 이미지", width=300)

        col1, col2 = st.columns([1, 2])
        with col1:
            installment_months = st.selectbox("할부(개월)", options=[1] + list(range(2, 13)))
        with col2:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("기록하기 🚀", use_container_width=True)

    # --- 4. 실행 로직 ---
    if submitted:
        if not user_content:
            st.warning("⚠️ 내용을 입력해주세요.")
        else:
            with st.status("AI가 분석 중입니다...", expanded=True) as status:
                try:
                    status.write("⚙️ 1단계: 날짜 및 분류 기준 설정...")

                    prompt = f"""
                    당신은 가계부 정리 전문가입니다.

                    [기준 정보]
                    - 작성 기준일: {today_str}
                    - 기준 연도: {today.year}년
                    - 가능 카테고리: {", ".join(CATEGORIES)} (이 중에서만 선택, 없으면 '기타')

                    [추출 항목]
                    1. date (YYYY-MM-DD)
                    2. item (항목명)
                    3. amount (금액, 숫자만)
                    4. category (위 목록 중 하나)

                    입력된 내용에 여러 건의 지출이 있다면 반드시 배열([])로 반환하세요.
                    JSON 예시: [{{"date": "{today_str}", "item": "커피", "amount": 4500, "category": "외식"}}, {{"date": "{today_str}", "item": "택시", "amount": 12000, "category": "교통비"}}]
                    응답은 반드시 순수한 JSON 문자열이어야 합니다.
                    """

                    if content_type == "text":
                        contents = [prompt + "\n\n" + user_content]
                    else:
                        contents = [prompt, user_content]

                    status.write("📡 2단계: Gemini 분석 중 (재시도 기능 적용)...")
                    response = generate_content_with_retry(default_model_name, contents)

                    status.write("🔍 3단계: 응답 데이터 해석 중...")
                    if not response.text:
                        raise ValueError("Gemini로부터 빈 응답이 왔습니다.")

                    clean_res = response.text.replace("```json", "").replace("```", "").strip()
                    raw_data = json.loads(clean_res)

                    new_entries = []
                    items = raw_data if isinstance(raw_data, list) else [raw_data]

                    for item in items:
                        safe_entry = {
                            "date": item.get("date", today_str),
                            "item": item.get("item", "알 수 없음"),
                            "amount": int(str(item.get("amount", 0)).replace(",", "")),
                            "category": item.get("category", "기타"),
                            "spender": spender,
                        }
                        new_entries.append(safe_entry)

                    final_entries = []
                    if installment_months > 1:
                        status.write(f"➗ {installment_months}개월 할부 계산 중...")
                        for entry in new_entries:
                            total_amt = entry["amount"]
                            try:
                                base_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                            except Exception:
                                base_date = datetime.now()

                            monthly_amt = total_amt // installment_months
                            for i in range(installment_months):
                                next_date = base_date + relativedelta(months=i)
                                inst_entry = entry.copy()
                                inst_entry["date"] = next_date.strftime("%Y-%m-%d")
                                inst_entry["amount"] = monthly_amt
                                inst_entry["item"] = f"{entry['item']} ({i+1}/{installment_months})"
                                final_entries.append(inst_entry)
                    else:
                        final_entries = new_entries

                    status.write("💾 4단계: 저장 중...")
                    if insert_expense(final_entries):
                        status.update(label="완료!", state="complete", expanded=False)
                        st.success(f"✅ {len(final_entries)}건이 [{spender}] 명의로 저장되었습니다!")
                        st.json(final_entries)

                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        status.update(label="🚨 한도 초과", state="error")
                        st.error("오늘 사용량이 너무 많아 잠시 제한되었습니다. 1분 뒤에 다시 시도해주세요.")
                    else:
                        status.update(label="❌ 오류 발생", state="error")
                        st.error(f"상세 에러 내용: {e}")


# ── Navigation (함수 정의 후에 선언) ──────────────────────────
pg = st.navigation(
    {
        "가계부": [
            st.Page(home_page,                   title="📝 지출 입력",          default=True),
            st.Page("pages/dashboard.py",        title="📊 소비 분석"),
            st.Page("pages/fixed_expenses.py",   title="📌 고정 지출"),
            st.Page("pages/export_to_claude.py", title="📤 내보내기"),
        ],
        "재정 관리": [
            st.Page("pages/cashflow.py",         title="💰 자기자본 시뮬레이터"),
            st.Page("pages/budget.py",           title="🎯 예산 설계"),
            st.Page("pages/real_estate.py",      title="🏠 부동산 전략"),
            st.Page("pages/monthly_review.py", title="월간 리뷰", icon="📋")
        ],
        "설정": [
            st.Page("pages/_onboarding.py",      title="⚙️ 프로필 설정"),
        ],
    }
)

# 앱 시작 시 DB 초기화 (pg.run() 전 — 모든 페이지에서 실행)
init_db()
cleanup_old_income_settings()
pg.run()
